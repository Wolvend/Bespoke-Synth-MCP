from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from typing import Any
from typing import cast

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient


def _now_ms() -> int:
    return int(time.time() * 1000)


class OscBridge:
    def __init__(
        self,
        cmd_host: str,
        cmd_port: int,
        reply_listen_host: str,
        reply_listen_port: int,
        telemetry_listen_host: str,
        telemetry_listen_port: int,
        telemetry_capacity: int = 500,
    ) -> None:
        self._cmd_client = SimpleUDPClient(cmd_host, cmd_port)
        self._reply_endpoint = (reply_listen_host, reply_listen_port)
        self._telemetry_endpoint = (telemetry_listen_host, telemetry_listen_port)
        self._reply_transport: Any | None = None
        self._telemetry_transport: Any | None = None
        self._started = False
        self._start_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._telemetry: deque[dict[str, Any]] = deque(maxlen=telemetry_capacity)

    async def start(self) -> None:
        if self._started:
            return
        async with self._start_lock:
            if self._started:
                return

            loop = cast(asyncio.BaseEventLoop, asyncio.get_running_loop())

            reply_dispatcher = Dispatcher()
            reply_dispatcher.map("/mcp/reply", self._handle_reply)
            reply_server = AsyncIOOSCUDPServer(self._reply_endpoint, reply_dispatcher, loop)
            self._reply_transport, _ = await reply_server.create_serve_endpoint()

            telemetry_dispatcher = Dispatcher()
            telemetry_dispatcher.set_default_handler(self._handle_telemetry)
            telemetry_server = AsyncIOOSCUDPServer(self._telemetry_endpoint, telemetry_dispatcher, loop)
            self._telemetry_transport, _ = await telemetry_server.create_serve_endpoint()
            self._started = True

    async def close(self) -> None:
        if self._reply_transport is not None:
            self._reply_transport.close()
        if self._telemetry_transport is not None:
            self._telemetry_transport.close()
        self._reply_transport = None
        self._telemetry_transport = None
        self._started = False

    async def send_cmd_and_wait_reply(
        self,
        envelope: dict[str, Any],
        timeout_ms: int,
    ) -> dict[str, Any]:
        await self.start()
        correlation_id = str(
            envelope.get("idempotency_key")
            or envelope.get("correlation_id")
            or f"cmd-{_now_ms()}"
        )
        envelope.setdefault("correlation_id", correlation_id)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[correlation_id] = future
        self._cmd_client.send_message("/mcp/cmd", json.dumps(envelope))
        try:
            return await asyncio.wait_for(future, timeout_ms / 1000)
        finally:
            self._pending.pop(correlation_id, None)

    def telemetry_last(self, limit: int, prefix: str | None = None) -> list[dict[str, Any]]:
        items = list(self._telemetry)
        if prefix:
            items = [item for item in items if item["address"].startswith(prefix)]
        return items[-limit:]

    def _handle_reply(self, address: str, *args: Any) -> None:
        if not args:
            return
        try:
            payload = json.loads(str(args[0]))
        except json.JSONDecodeError:
            payload = {"ok": False, "error": "invalid_reply_json", "raw": str(args[0])}
        correlation_id = str(payload.get("idempotency_key") or payload.get("correlation_id") or "")
        if not correlation_id:
            return
        future = self._pending.get(correlation_id)
        if future is not None and not future.done():
            future.set_result(payload)

    def _handle_telemetry(self, address: str, *args: Any) -> None:
        self._telemetry.append(
            {
                "address": address,
                "args": list(args),
                "ts_ms": _now_ms(),
            }
        )
