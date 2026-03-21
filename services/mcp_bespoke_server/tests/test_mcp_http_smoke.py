from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time

import httpx


def test_mcp_http_initialize_and_tool_call(mock_bespoke_agent) -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    env["MCP_TRANSPORT"] = "streamable-http"
    env["MCP_HTTP_HOST"] = "127.0.0.1"
    env["MCP_HTTP_PORT"] = "8011"

    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_bespoke_server.server"],
        cwd=str(root),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        headers = {"Accept": "application/json, text/event-stream"}
        with httpx.Client(base_url="http://127.0.0.1:8011", timeout=10) as client:
            init_resp = None
            for _ in range(20):
                try:
                    init_resp = client.post(
                        "/mcp",
                        headers=headers,
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2025-03-26",
                                "capabilities": {},
                                "clientInfo": {"name": "pytest", "version": "0.1"},
                            },
                        },
                    )
                    break
                except httpx.ConnectError:
                    time.sleep(0.5)
            assert init_resp is not None
            assert init_resp.status_code == 200

            call_resp = client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "bespoke.safe.health",
                        "arguments": {},
                    },
                },
            )
            assert call_resp.status_code == 200
            payload = call_resp.json()
            assert payload["result"]["structuredContent"]["ok"] is True
    finally:
        proc.terminate()
        proc.wait(timeout=5)
