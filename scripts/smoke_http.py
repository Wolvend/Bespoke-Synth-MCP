from __future__ import annotations

import argparse
import json

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test the BespokeSynth MCP HTTP endpoint.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL for the MCP server")
    args = parser.parse_args()

    headers = {"Accept": "application/json, text/event-stream"}
    with httpx.Client(base_url=args.base_url, timeout=10) as client:
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
                    "clientInfo": {"name": "smoke-http", "version": "0.1.0"},
                },
            },
        )
        init_resp.raise_for_status()
        print("initialize:", init_resp.json())

        call_resp = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "bespoke.safe.health", "arguments": {}},
            },
        )
        call_resp.raise_for_status()
        print("health:", json.dumps(call_resp.json(), indent=2))


if __name__ == "__main__":
    main()

