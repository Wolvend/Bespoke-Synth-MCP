#!/usr/bin/env python
"""Smoke test: Generate a breakcore brainworm beat using MCP workflows."""

import asyncio
import json
from pathlib import Path
from datetime import datetime

from synth_engine import save_audio_mp3
from workflow_composer import (
    BuiltinWorkflows,
    WorkflowPresetManager,
    WorkflowRenderer,
)


async def main():
    """Generate brainworm beat using workflow system."""
    print("\n" + "="*70)
    print("BESPOKE SYNTH MCP - BREAKCORE BRAINWORM BEAT GENERATOR")
    print("="*70)

    # Create directories
    tracks_dir = Path(__file__).parent / "tracks"
    tracks_dir.mkdir(exist_ok=True)

    presets_dir = Path(__file__).parent / "workflow_presets"
    presets_dir.mkdir(exist_ok=True)

    print("\n[1] Initializing workflow system...")
    manager = WorkflowPresetManager(str(presets_dir))
    renderer = WorkflowRenderer(sample_rate=44100)
    print("    [OK] Workflow manager ready")
    print("    [OK] Synth engine initialized (44.1 kHz, 320kbps MP3)")

    # Create and save the breakcore workflow
    print("\n[2] Creating breakcore brainworm workflow...")
    workflow = BuiltinWorkflows.breakcore_brainworm()
    manager.save_workflow(workflow)

    duration_seconds = workflow.duration_seconds()
    print(f"    [OK] Workflow created: {workflow.name}")
    print(f"    [OK] BPM: {workflow.bpm}")
    print(f"    [OK] Duration: {duration_seconds:.2f} seconds")
    print(f"    [OK] Steps: {len(workflow.steps)}")

    # Show step breakdown
    print("\n[3] Workflow composition:")
    print("    " + "-" * 65)
    print("    Preset               | Duration | Delay | Cumulative Time")
    print("    " + "-" * 65)

    cumulative_ms = 0
    for i, step in enumerate(workflow.steps[:15]):  # Show first 15 steps
        cumulative_ms += step.delay_ms + step.duration_ms
        time_str = f"{cumulative_ms/1000:.2f}s"
        print(
            f"    {step.preset:20} | {step.duration_ms:7.0f}ms | {step.delay_ms:5.0f}ms | {time_str}"
        )

    if len(workflow.steps) > 15:
        print(f"    ... and {len(workflow.steps) - 15} more steps")
    print("    " + "-" * 65)

    # Render audio
    print("\n[4] Rendering audio from workflow...")
    print(f"    [..] Synthesizing {len(workflow.steps)} events...")

    try:
        # Render workflow
        from synth_engine import SynthEngine
        engine = SynthEngine()

        # Create pattern
        pattern = [
            (step.preset, step.duration_ms, step.delay_ms) for step in workflow.steps
        ]

        # Render
        audio = engine.render_sequence(pattern)
        print(f"    [OK] Audio synthesized: {len(audio):,} samples")

        # Save to MP3
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mp3_filename = f"brainworm_beat_{timestamp}.mp3"
        mp3_path = tracks_dir / mp3_filename

        save_audio_mp3(audio, str(mp3_path), sample_rate=44100)
        file_size_kb = mp3_path.stat().st_size / 1024
        print(f"    [OK] MP3 encoded: {file_size_kb:.1f} KB @ 320kbps")

    except Exception as e:
        print(f"    [FAIL] Error rendering: {e}")
        raise

    # Create metadata
    print("\n[5] Saving workflow metadata...")
    metadata = {
        "name": f"brainworm_beat_{timestamp}",
        "timestamp": datetime.now().isoformat(),
        "workflow": workflow.to_dict(),
        "audio": {
            "duration_seconds": duration_seconds,
            "sample_rate": 44100,
            "channels": 1,
            "bitrate": "320kbps",
            "file_format": "mp3",
        },
        "synthesis_info": {
            "preset_count": len(set(s.preset for s in workflow.steps)),
            "total_steps": len(workflow.steps),
            "bpm": workflow.bpm,
        },
        "files": {
            "mp3": mp3_filename,
            "metadata": f"brainworm_beat_{timestamp}.json",
        },
    }

    meta_path = tracks_dir / f"brainworm_beat_{timestamp}.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"    [OK] Metadata saved")

    # List available presets and workflows
    print("\n[6] Available presets and workflows:")
    print("    " + "-" * 65)

    from synth_engine import PRESETS

    print(f"    Synth Presets ({len(PRESETS)}):")
    for preset_name in sorted(PRESETS.keys()):
        print(f"      - {preset_name}")

    print(f"\n    Saved Workflows:")
    workflows = manager.list_workflows()
    for wf in workflows:
        print(f"      - {wf}")

    # Summary
    print("\n" + "="*70)
    print("BRAINWORM BEAT GENERATION COMPLETE")
    print("="*70)
    print(f"File Name:      {mp3_filename}")
    print(f"Location:       {mp3_path.absolute()}")
    print(f"File Size:      {file_size_kb:.1f} KB")
    print(f"Duration:       {duration_seconds:.2f} seconds")
    print(f"BPM:            {workflow.bpm}")
    print(f"Sample Rate:    44.1 kHz")
    print(f"Channels:       Mono")
    print(f"Bitrate:        320 kbps")
    print(f"Status:         [PASS] Ready to play!")
    print("="*70)

    return str(mp3_path.absolute())


if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nBrainworm beat saved to:")
    print(f"  {result}")
    print(
        "\nNext steps:"
    )
    print("  - Download the file and play it")
    print("  - Edit workflow_presets/breakcore_brainworm.json to customize")
    print("  - Use WorkflowPresetManager to create new workflows")
    print("  - Export workflows as MCP presets for fast generation")
