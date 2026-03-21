from __future__ import annotations

import json
import sys
from typing import Any

import httpx


def _post_json(client: httpx.Client, path: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    response = client.post(path, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def main() -> None:
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10) as mcp_client:
        health = mcp_client.get("/healthz")
        health.raise_for_status()
        print("mcp health:", health.json())

        headers = {"Accept": "application/json, text/event-stream"}
        init_result = _post_json(
            mcp_client,
            "/mcp",
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "smoke-stack", "version": "0.1.0"},
                },
            },
            headers=headers,
        )
        print("mcp initialize:", json.dumps(init_result, indent=2))

        tool_result = _post_json(
            mcp_client,
            "/mcp",
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "bespoke.safe.health", "arguments": {}},
            },
            headers=headers,
        )
        print("mcp tool:", json.dumps(tool_result, indent=2))

    with httpx.Client(base_url="http://127.0.0.1:8088", timeout=10) as orch_client:
        orch_health = orch_client.get("/health")
        orch_health.raise_for_status()
        print("orchestrator health:", orch_health.json())

        plan = _post_json(
            orch_client,
            "/plan",
            {"user_text": "set cutoff to 0.25", "provider": "mock"},
        )
        print("orchestrator plan:", json.dumps(plan, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"smoke stack failed: {exc}", file=sys.stderr)
        raise
