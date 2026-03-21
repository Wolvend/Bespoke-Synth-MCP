from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient


class MockBespokeAgent:
    def __init__(self, cmd_port: int = 9001, reply_port: int = 9002) -> None:
        self._cmd_port = cmd_port
        self._reply_port = reply_port
        self._transport = None
        self._client = SimpleUDPClient("127.0.0.1", reply_port)
        self.state = {"filter~cutoff": 0.10}

    async def start(self) -> None:
        dispatcher = Dispatcher()
        dispatcher.map("/mcp/cmd", self._handle_cmd)
        server = AsyncIOOSCUDPServer(("127.0.0.1", self._cmd_port), dispatcher, asyncio.get_running_loop())
        self._transport, _ = await server.create_serve_endpoint()

    async def close(self) -> None:
        if self._transport is not None:
            self._transport.close()

    def _handle_cmd(self, address: str, *args) -> None:
        payload = json.loads(str(args[0]))
        op = payload.get("op")
        if op == "set":
            self.state[payload["path"]] = payload["value"]
            reply = {"ok": True, "path": payload["path"]}
        elif op == "get":
            reply = {"ok": True, "path": payload["path"], "value": self.state.get(payload["path"])}
        elif op == "batch_set":
            for step in payload["ops"]:
                self.state[step["path"]] = step["value"]
            reply = {"ok": True, "count": len(payload["ops"])}
        else:
            reply = {"ok": True, "op": op}
        reply["correlation_id"] = payload.get("correlation_id") or payload.get("idempotency_key")
        reply["idempotency_key"] = payload.get("idempotency_key")
        self._client.send_message("/mcp/reply", json.dumps(reply))


@pytest.fixture
async def mock_bespoke_agent() -> AsyncIterator[MockBespokeAgent]:
    agent = MockBespokeAgent()
    await agent.start()
    try:
        yield agent
    finally:
        await agent.close()

