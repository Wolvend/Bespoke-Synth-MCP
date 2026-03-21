from __future__ import annotations

from mcp_bespoke_server.osc_bridge import OscBridge


async def test_osc_bridge_round_trip(mock_bespoke_agent) -> None:
    bridge = OscBridge(
        cmd_host="127.0.0.1",
        cmd_port=9001,
        reply_listen_host="127.0.0.1",
        reply_listen_port=9002,
        telemetry_listen_host="127.0.0.1",
        telemetry_listen_port=9010,
    )
    reply = await bridge.send_cmd_and_wait_reply(
        {"op": "set", "path": "filter~cutoff", "value": 0.4, "idempotency_key": "abc"},
        timeout_ms=1000,
    )
    assert reply["ok"] is True
    await bridge.close()

