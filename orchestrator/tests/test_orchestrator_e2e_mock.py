from __future__ import annotations

from fastapi.testclient import TestClient

from orchestrator import api


class DummyMCPClient:
    async def call_tool(self, tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
        return {"tool": tool_name, "arguments": arguments, "ok": True}


def test_chat_executes_mock_plan(monkeypatch) -> None:
    monkeypatch.setattr(api, "mcp_client", DummyMCPClient())
    client = TestClient(api.app)
    response = client.post("/chat", json={"user_text": "set cutoff to 0.25", "confirmed": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["results"][0]["tool"] == "bespoke.safe.set_param"

