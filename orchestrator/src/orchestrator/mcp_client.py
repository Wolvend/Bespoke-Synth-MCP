from __future__ import annotations

import asyncio
import json
import shlex
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class MCPClientConfig:
    transport: str
    server_url: str
    server_cmd: str
    timeout_s: int = 10


class MCPClient:
    def __init__(self, config: MCPClientConfig) -> None:
        self.config = config

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.config.transport == "http":
            return await self._call_tool_http(tool_name, arguments)
        if self.config.transport == "stdio":
            return await self._call_tool_stdio(tool_name, arguments)
        raise ValueError(f"unsupported MCP transport: {self.config.transport}")

    async def _call_tool_http(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        init_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "bespokesynth-orchestrator", "version": "0.1.0"},
            },
        }
        tool_message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        headers = {"Accept": "application/json, text/event-stream"}
        async with httpx.AsyncClient(timeout=self.config.timeout_s) as client:
            init_response = await client.post(self.config.server_url, json=init_message, headers=headers)
            init_response.raise_for_status()
            call_response = await client.post(self.config.server_url, json=tool_message, headers=headers)
            call_response.raise_for_status()
        payload = call_response.json()
        result = payload.get("result")
        if isinstance(result, dict):
            return result
        raise RuntimeError(f"invalid MCP tool response: {payload}")

    async def _call_tool_stdio(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        process = await asyncio.create_subprocess_exec(
            *shlex.split(self.config.server_cmd),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert process.stdin is not None
        assert process.stdout is not None

        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "bespokesynth-orchestrator", "version": "0.1.0"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
        ]
        for message in messages:
            process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
            await process.stdin.drain()

        result: dict[str, Any] | None = None
        deadline = asyncio.get_running_loop().time() + self.config.timeout_s
        while asyncio.get_running_loop().time() < deadline:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=self.config.timeout_s)
            if not line:
                break
            payload = json.loads(line.decode("utf-8"))
            if payload.get("id") == 2:
                maybe = payload.get("result")
                if isinstance(maybe, dict):
                    result = maybe
                    break
        stderr_reader = process.stderr
        process.terminate()
        await process.wait()
        if result is None:
            stderr = b"" if stderr_reader is None else await stderr_reader.read()
            raise RuntimeError(f"stdio MCP tool call failed: {stderr.decode('utf-8', errors='ignore')}")
        return result
