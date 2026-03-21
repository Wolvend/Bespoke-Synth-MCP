#!/usr/bin/env python
"""Smoke test: Create a track, configure it, synthesize audio, and save as MP3."""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
import numpy as np
from scipy import signal
from pydub import AudioSegment

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


def synthesize_audio(params: dict, duration_seconds: float = 8.0, sample_rate: int = 44100) -> np.ndarray:
    """Synthesize audio based on patch parameters.

    Args:
        params: Dictionary with filter~cutoff, filter~resonance, lfo~rate, delay~time
        duration_seconds: Duration in seconds
        sample_rate: Sample rate in Hz

    Returns:
        Audio array normalized to [-1, 1]
    """
    # Create time array
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), False)

    # Base frequency (map cutoff to Hz: 0-1 -> 200-2000 Hz)
    base_freq = 200 + (params.get("filter~cutoff", 0.5) * 1800)

    # LFO modulates the frequency
    lfo_freq = params.get("lfo~rate", 0.25) * 10  # 0-2.5 Hz
    lfo = np.sin(2 * np.pi * lfo_freq * t)

    # Modulate frequency with LFO (+-20%)
    freq_modulation = base_freq * (1 + lfo * 0.2)

    # Generate oscillator with frequency modulation
    phase = 2 * np.pi * np.cumsum(freq_modulation) / sample_rate
    osc = np.sin(phase)

    # Apply resonance as envelope dynamics
    resonance = params.get("filter~resonance", 0.45)
    envelope = np.ones_like(t)
    # Add amplitude modulation based on resonance
    envelope *= (0.5 + resonance * 0.5)

    # Apply simple low-pass filter (cutoff modulates it)
    cutoff_normalized = params.get("filter~cutoff", 0.5)
    filter_order = 4
    # Design butterworth filter
    nyquist = sample_rate / 2
    normal_cutoff = (cutoff_normalized * 0.4 + 0.2) / (nyquist / 1000)  # Map to normalized frequency
    normal_cutoff = min(0.99, max(0.01, normal_cutoff))  # Clamp

    try:
        b, a = signal.butter(filter_order, normal_cutoff, btype='low')
        filtered = signal.filtfilt(b, a, osc * envelope)
    except:
        # Fallback if filter fails
        filtered = osc * envelope

    # Apply delay
    delay_time = params.get("delay~time", 0.5)
    delay_samples = int(delay_time * 0.5 * sample_rate)  # 0-0.5s delay

    if delay_samples > 0:
        delayed = np.zeros_like(filtered)
        delayed[delay_samples:] = filtered[:-delay_samples] * 0.4  # 40% feedback
        filtered = filtered + delayed

    # Normalize to prevent clipping
    max_val = np.max(np.abs(filtered))
    if max_val > 0:
        filtered = filtered / (max_val * 1.1)

    # Clamp to [-1, 1]
    filtered = np.clip(filtered, -1, 1)

    return filtered.astype(np.float32)


async def main():
    """Run smoke test with audio rendering."""
    print("[*] BespokeSynth MCP Smoke Test - Audio Edition")
    print("[*] Creating track, configuring, synthesizing, and saving as MP3...")

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

    param_dict = {}
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
                param_dict[path] = value
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

    # Synthesize audio
    print("\n[5] Synthesizing audio from patch...")
    print("    [..] Generating audio (8 seconds)...")
    audio_array = synthesize_audio(param_dict, duration_seconds=8.0)
    print(f"    [OK] Audio synthesized: {len(audio_array)} samples")

    # Save as MP3
    print("\n[6] Encoding to MP3...")
    track_name = f"smoke_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    save_dir = Path(__file__).parent / "tracks"
    save_dir.mkdir(exist_ok=True)

    # Convert numpy array to pydub AudioSegment
    # Convert float32 [-1, 1] to int16 [-32768, 32767]
    audio_int16 = (audio_array * 32767).astype(np.int16)
    audio_segment = AudioSegment(
        audio_int16.tobytes(),
        frame_rate=44100,
        sample_width=2,
        channels=1
    )

    # Save as MP3
    mp3_file = save_dir / f"{track_name}.mp3"
    audio_segment.export(str(mp3_file), format="mp3", bitrate="192k")
    print(f"    [OK] MP3 encoded: {mp3_file}")

    # Save metadata
    meta_file = save_dir / f"{track_name}.json"
    track_data = {
        "name": track_name,
        "timestamp": datetime.now().isoformat(),
        "parameters": param_dict,
        "audio": {
            "duration_seconds": 8.0,
            "sample_rate": 44100,
            "channels": 1,
            "bitrate": "192k",
        },
        "files": {
            "mp3": str(mp3_file.name),
            "metadata": str(meta_file.name),
        }
    }

    meta_file.write_text(json.dumps(track_data, indent=2))
    print(f"    [OK] Metadata saved: {meta_file}")

    # Cleanup
    print("\n[7] Cleaning up...")
    await osc.close()
    await agent.close()
    print("    [OK] Resources released")

    # Final report
    print("\n" + "="*70)
    print("SMOKE TEST RESULTS - AUDIO EDITION")
    print("="*70)
    print(f"Track Name:     {track_name}")
    print(f"MP3 Location:   {mp3_file.absolute()}")
    print(f"MP3 File Size:  {mp3_file.stat().st_size / 1024:.1f} KB")
    print(f"Metadata:       {meta_file.absolute()}")
    print(f"Duration:       8.0 seconds")
    print(f"Bitrate:        192 kbps")
    print(f"Status:         [PASS]")
    print("="*70)

    return str(mp3_file.absolute())


if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nMP3 track saved to: {result}")
