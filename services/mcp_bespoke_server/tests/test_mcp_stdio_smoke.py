from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest


@pytest.mark.skipif(sys.platform.startswith("win"), reason="stdio subprocess handling is flaky on Windows CI shells")
async def test_mcp_stdio_smoke(mock_bespoke_agent) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str((__import__("pathlib").Path(__file__).resolve().parents[1] / "src"))
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "mcp_bespoke_server.server",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=str((__import__("pathlib").Path(__file__).resolve().parents[1])),
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0.1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "bespoke.safe.health",
                "arguments": {},
            },
        },
    ]
    for message in messages:
        proc.stdin.write((json.dumps(message) + "\n").encode())
        await proc.stdin.drain()

    response = None
    for _ in range(10):
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=5)
        if not line:
            continue
        payload = json.loads(line.decode())
        if payload.get("id") == 2:
            response = payload
            break

    proc.terminate()
    await proc.wait()
    assert response is not None
    assert response["result"]["structuredContent"]["ok"] is True
