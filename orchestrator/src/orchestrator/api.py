from __future__ import annotations

import json
import logging
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException

from .config import Settings
from .mcp_client import MCPClient, MCPClientConfig
from .model_router import ModelRouter
from .planner import ChatRequest, ExecuteRequest, ExecuteResponse, ExecutionPlan, ExecutionResult, PlanRequest
from .policies import PolicyEngine
from .telemetry import TelemetryBuffer


settings = Settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

app = FastAPI(title="bespokesynth_orchestrator")
router = ModelRouter(settings)
policy_engine = PolicyEngine(
    mode=settings.policy_mode,
    consent_required_for_risky=settings.consent_required_for_risky,
)
mcp_client = MCPClient(
    MCPClientConfig(
        transport=settings.mcp_client_transport,
        server_url=settings.mcp_server_url,
        server_cmd=settings.mcp_server_cmd,
        timeout_s=settings.mcp_client_timeout_s,
    )
)
telemetry = TelemetryBuffer()

PLANNER_SYSTEM_PROMPT = """You are the planning model for a BespokeSynth MCP system.
Return only JSON matching this schema:
{"goal":"string","requires_user_confirmation":true|false,"steps":[{"tool":"string","arguments":{},"why":"string"}],"rollback":[{"tool":"string","arguments":{}}]}
Use safe tools unless the user explicitly requests an admin action."""


def _choose_provider(requested: str | None) -> str:
    provider = requested or settings.default_planner_provider
    if not policy_engine.provider_allowed(provider):
        raise HTTPException(status_code=403, detail=f"provider {provider} not allowed in mode {settings.policy_mode}")
    return provider


async def _plan_from_text(user_text: str, provider: str) -> ExecutionPlan:
    response = await router.generate(provider=provider, system_prompt=PLANNER_SYSTEM_PROMPT, user_prompt=user_text)
    try:
        payload = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"planner returned invalid JSON from {provider}: {exc}") from exc
    plan = ExecutionPlan.model_validate(payload)
    decision = policy_engine.plan_decision(plan)
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)
    if decision.requires_confirmation:
        plan = plan.model_copy(update={"requires_user_confirmation": True})
    return plan


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "service": "bespokesynth_orchestrator", "mode": settings.policy_mode}


@app.post("/plan", response_model=ExecutionPlan)
async def plan_endpoint(req: PlanRequest) -> ExecutionPlan:
    provider = _choose_provider(req.provider)
    return await _plan_from_text(req.user_text, provider)


@app.post("/execute", response_model=ExecuteResponse)
async def execute_endpoint(req: ExecuteRequest) -> ExecuteResponse:
    decision = policy_engine.plan_decision(req.plan)
    if decision.requires_confirmation and not req.confirmed:
        raise HTTPException(status_code=409, detail="plan requires confirmation")
    results: list[ExecutionResult] = []
    for step in req.plan.steps:
        result = await mcp_client.call_tool(step.tool, step.arguments)
        results.append(ExecutionResult(tool=step.tool, result=result))
        telemetry.add({"tool": step.tool, "result": result})
    summary = f"Executed {len(results)} tool step(s) successfully."
    return ExecuteResponse(ok=True, plan=req.plan, results=results, summary=summary)


@app.post("/chat")
async def chat_endpoint(req: ChatRequest) -> dict[str, Any]:
    provider = _choose_provider(req.provider)
    plan = await _plan_from_text(req.user_text, provider)
    if plan.requires_user_confirmation and not req.confirmed:
        return {
            "ok": True,
            "status": "confirmation_required",
            "plan": plan.model_dump(),
            "message": "Plan requires confirmation before execution.",
        }
    execute_response = await execute_endpoint(
        ExecuteRequest(plan=plan, confirmed=req.confirmed, session_id=req.session_id)
    )
    return execute_response.model_dump()


@app.get("/telemetry")
async def telemetry_endpoint(limit: int = 20) -> dict[str, Any]:
    return {"ok": True, "items": telemetry.last(limit=limit)}


def main() -> None:
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
