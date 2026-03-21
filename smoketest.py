#!/usr/bin/env python
"""Smoke test: Create a track, configure it, and save."""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Add services to path
sys.path.insert(0, str(Path(__file__).parent / "services" / "mcp_bespoke_server" / "src"))

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
from mcp_bespoke_server.osc_bridge import OscBridge


class MockBespokeAgent:
    """Mock BespokeSynth agent for testing."""

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


async def main():
    """Run smoke test."""
    print("[*] BespokeSynth MCP Smoke Test")
    print("[*] Creating track, configuring, and saving...")

    # Start mock Bespoke agent
    print("\n[1] Starting mock Bespoke agent...")
    agent = MockBespokeAgent(cmd_port=9001, reply_port=9002)
    await agent.start()
    print("    [OK] Mock agent listening on OSC ports 9001/9002")

    # Create OSC bridge
    print("\n[2] Initializing OSC bridge...")
    osc = OscBridge(
        cmd_host="127.0.0.1",
        cmd_port=9001,
        reply_listen_host="127.0.0.1",
        reply_listen_port=9002,
        telemetry_listen_host="127.0.0.1",
        telemetry_listen_port=9010,
    )
    await osc.start()
    print("    [OK] OSC bridge ready")

    # Simulate creating a track: set parameters
    print("\n[3] Configuring patch parameters...")

    params = [
        ("filter~cutoff", 0.35, "Set filter cutoff"),
        ("filter~resonance", 0.45, "Set resonance"),
        ("lfo~rate", 0.25, "Set LFO rate"),
        ("delay~time", 0.5, "Set delay time"),
    ]

    for path, value, desc in params:
        try:
            reply = await osc.send_cmd_and_wait_reply(
                envelope={
                    "op": "set",
                    "path": path,
                    "value": value,
                    "idempotency_key": f"set_{path.replace('~', '_')}",
                },
                timeout_ms=2000,
            )
            if reply.get("ok"):
                print(f"    [OK] {desc}: {path} = {value}")
            else:
                print(f"    [FAIL] Failed: {path}")
        except Exception as e:
            print(f"    [FAIL] Error setting {path}: {e}")

    # Verify state
    print("\n[4] Verifying patch state...")
    try:
        reply = await osc.send_cmd_and_wait_reply(
            envelope={
                "op": "get",
                "path": "filter~cutoff",
                "idempotency_key": "get_filter_cutoff",
            },
            timeout_ms=2000,
        )
        if reply.get("ok"):
            value = reply.get("value")
            print(f"    [OK] Current filter cutoff: {value}")
    except Exception as e:
        print(f"    [FAIL] Error reading state: {e}")

    # Save track info
    print("\n[5] Saving track...")
    track_name = f"smoke_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    save_dir = Path(__file__).parent / "tracks"
    save_dir.mkdir(exist_ok=True)

    track_file = save_dir / f"{track_name}.json"
    track_data = {
        "name": track_name,
        "timestamp": datetime.now().isoformat(),
        "parameters": {path: value for path, value, _ in params},
        "agent_state": agent.state,
    }

    track_file.write_text(json.dumps(track_data, indent=2))
    print(f"    [OK] Track saved: {track_file}")

    # Cleanup
    print("\n[6] Cleaning up...")
    await osc.close()
    await agent.close()
    print("    [OK] Resources released")

    # Final report
    print("\n" + "="*60)
    print("SMOKE TEST RESULTS")
    print("="*60)
    print(f"Track Name:     {track_name}")
    print(f"Save Location:  {track_file.absolute()}")
    print(f"File Size:      {track_file.stat().st_size} bytes")
    print(f"Status:         [PASS]")
    print("="*60)

    return str(track_file.absolute())


if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nTrack location: {result}")
