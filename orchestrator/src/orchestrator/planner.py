from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str
    arguments: dict[str, Any]
    why: str | None = None


class RollbackStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str
    arguments: dict[str, Any]


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: str
    requires_user_confirmation: bool = False
    steps: list[PlanStep] = Field(min_length=1)
    rollback: list[RollbackStep] = Field(default_factory=list)


class ChatRequest(BaseModel):
    user_text: str = Field(min_length=1)
    mode: str | None = None
    session_id: str | None = None
    confirmed: bool = False
    provider: str | None = None


class PlanRequest(ChatRequest):
    pass


class ExecuteRequest(BaseModel):
    plan: ExecutionPlan
    confirmed: bool = False
    session_id: str | None = None


class ExecutionResult(BaseModel):
    tool: str
    result: dict[str, Any]


class ExecuteResponse(BaseModel):
    ok: bool
    plan: ExecutionPlan
    results: list[ExecutionResult]
    summary: str

