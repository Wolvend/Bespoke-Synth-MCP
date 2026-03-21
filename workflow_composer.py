#!/usr/bin/env python
"""MCP Workflow Composer - Complex beat generation with presets."""

import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from synth_engine import SynthEngine, PRESETS


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    preset: str  # Preset name
    duration_ms: float
    delay_ms: float = 0
    velocity: float = 1.0  # 0-1
    modulation: Optional[Dict] = None  # Extra modulation params

    def to_dict(self):
        return asdict(self)


@dataclass
class Workflow:
    """Complete workflow definition."""
    name: str
    bpm: float = 140
    description: str = ""
    steps: List[WorkflowStep] = None

    def __post_init__(self):
        if self.steps is None:
            self.steps = []

    def duration_seconds(self) -> float:
        """Calculate total duration."""
        total_ms = sum(step.duration_ms + step.delay_ms for step in self.steps)
        return total_ms / 1000.0

    def to_dict(self):
        return {
            "name": self.name,
            "bpm": self.bpm,
            "description": self.description,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Load workflow from dict."""
        steps = [WorkflowStep(**s) for s in data.get("steps", [])]
        return cls(
            name=data["name"],
            bpm=data.get("bpm", 140),
            description=data.get("description", ""),
            steps=steps,
        )


class WorkflowPresetManager:
    """Manage workflow presets."""

    def __init__(self, presets_dir: str = "workflow_presets"):
        self.presets_dir = Path(presets_dir)
        self.presets_dir.mkdir(exist_ok=True)
        self._loaded_presets: Dict[str, Workflow] = {}

    def save_workflow(self, workflow: Workflow):
        """Save workflow to file."""
        filepath = self.presets_dir / f"{workflow.name}.json"
        with open(filepath, "w") as f:
            json.dump(workflow.to_dict(), f, indent=2)
        print(f"[OK] Workflow saved: {workflow.name}")

    def load_workflow(self, name: str) -> Optional[Workflow]:
        """Load workflow from file."""
        filepath = self.presets_dir / f"{name}.json"
        if not filepath.exists():
            return None
        with open(filepath) as f:
            data = json.load(f)
        return Workflow.from_dict(data)

    def list_workflows(self) -> List[str]:
        """List all available workflows."""
        return [f.stem for f in self.presets_dir.glob("*.json")]


# Built-in workflow presets
class BuiltinWorkflows:
    """Pre-configured workflows for quick generation."""

    @staticmethod
    def breakcore_brainworm() -> Workflow:
        """High-energy breakcore with brainworm hook."""
        return Workflow(
            name="breakcore_brainworm",
            bpm=180,
            description="Fast-paced breakcore with infectious synth hook",
            steps=[
                # Intro: Build tension
                WorkflowStep("kick_808", 500, 0),
                WorkflowStep("kick_808", 500, 0),
                WorkflowStep("snare_crisp", 250, 250),
                WorkflowStep("hihat_closed", 125, 0),
                WorkflowStep("hihat_closed", 125, 0),

                # Drop 1: Full rhythm
                WorkflowStep("kick_808", 250, 0),
                WorkflowStep("hihat_closed", 125, 0),
                WorkflowStep("snare_crisp", 250, 0),
                WorkflowStep("hihat_closed", 125, 0),
                WorkflowStep("kick_808", 250, 0),
                WorkflowStep("hihat_closed", 125, 0),
                WorkflowStep("tom_high", 125, 0),
                WorkflowStep("tom_mid", 125, 0),
                WorkflowStep("tom_low", 125, 0),

                # Synth hook enters (brainworm element)
                WorkflowStep("lead_bright", 250, 0),
                WorkflowStep("hihat_closed", 125, 0),
                WorkflowStep("lead_bright", 250, 0),
                WorkflowStep("hihat_closed", 125, 0),

                # Break with bass
                WorkflowStep("bass_deep", 500, 0),
                WorkflowStep("snare_crisp", 250, 250),
                WorkflowStep("hihat_open", 300, 0),
                WorkflowStep("bass_deep", 500, 200),

                # Chaotic breakcore section
                WorkflowStep("kick_808", 125, 0),
                WorkflowStep("snare_crisp", 125, 0),
                WorkflowStep("hihat_closed", 62, 0),
                WorkflowStep("hihat_closed", 62, 0),
                WorkflowStep("kick_808", 125, 0),
                WorkflowStep("tom_high", 62, 0),
                WorkflowStep("tom_mid", 62, 0),
                WorkflowStep("snare_crisp", 125, 0),

                # Lead synth acceleration
                WorkflowStep("lead_bright", 125, 0),
                WorkflowStep("lead_bright", 125, 0),
                WorkflowStep("lead_bright", 125, 0),
                WorkflowStep("lead_bright", 125, 0),

                # Outro: Build to climax
                WorkflowStep("kick_808", 250, 0),
                WorkflowStep("kick_808", 250, 0),
                WorkflowStep("snare_crisp", 250, 0),
                WorkflowStep("hihat_closed", 125, 0),
                WorkflowStep("hihat_closed", 125, 0),
                WorkflowStep("bass_deep", 500, 0),
                WorkflowStep("lead_bright", 250, 0),
                WorkflowStep("lead_bright", 250, 0),

                # Final snare
                WorkflowStep("snare_crisp", 500, 0),
            ],
        )

    @staticmethod
    def minimal_beat() -> Workflow:
        """Simple 4-on-the-floor beat."""
        return Workflow(
            name="minimal_beat",
            bpm=128,
            description="Basic kick-snare pattern",
            steps=[
                WorkflowStep("kick_808", 250, 0),
                WorkflowStep("hihat_closed", 125, 0),
                WorkflowStep("snare_crisp", 250, 0),
                WorkflowStep("hihat_closed", 125, 0),
            ] * 4,
        )

    @staticmethod
    def synth_pad_ambient() -> Workflow:
        """Ambient synth pad piece."""
        return Workflow(
            name="synth_pad_ambient",
            bpm=80,
            description="Relaxing pad progression",
            steps=[
                WorkflowStep("synth_pad", 2000, 0),
                WorkflowStep("synth_pad", 2000, 500),
                WorkflowStep("hihat_open", 500, 0),
                WorkflowStep("synth_pad", 2000, 1500),
                WorkflowStep("bass_deep", 2000, 0),
                WorkflowStep("synth_pad", 2000, 0),
            ],
        )

    @staticmethod
    def drum_solo() -> Workflow:
        """Drum machine solo."""
        return Workflow(
            name="drum_solo",
            bpm=150,
            description="Intricate drum pattern",
            steps=[
                # Bar 1: Kick and hat
                WorkflowStep("kick_808", 250, 0),
                WorkflowStep("hihat_closed", 125, 0),
                WorkflowStep("hihat_closed", 125, 0),
                WorkflowStep("kick_808", 125, 0),
                WorkflowStep("hihat_closed", 125, 0),

                # Bar 2: Snare fills
                WorkflowStep("snare_crisp", 250, 0),
                WorkflowStep("tom_high", 125, 0),
                WorkflowStep("tom_mid", 125, 0),
                WorkflowStep("tom_low", 125, 0),
                WorkflowStep("snare_crisp", 250, 0),

                # Bar 3: Poly-rhythm
                WorkflowStep("kick_808", 166, 0),
                WorkflowStep("snare_crisp", 166, 0),
                WorkflowStep("hihat_closed", 166, 0),

                # Bar 4: Climax
                WorkflowStep("kick_808", 125, 0),
                WorkflowStep("kick_808", 125, 0),
                WorkflowStep("snare_crisp", 250, 0),
            ],
        )


class WorkflowRenderer:
    """Render workflows to audio."""

    def __init__(self, sample_rate: int = 44100):
        self.engine = SynthEngine(sample_rate)
        self.sample_rate = sample_rate

    def render(self, workflow: Workflow) -> Tuple[bytes, int]:
        """Render workflow to MP3 bytes.

        Returns:
            (mp3_bytes, duration_ms)
        """
        from synth_engine import save_audio_mp3
        import tempfile

        # Create pattern from workflow
        pattern = [
            (step.preset, step.duration_ms, step.delay_ms) for step in workflow.steps
        ]

        # Render
        audio = self.engine.render_sequence(pattern)

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            save_audio_mp3(audio, f.name, self.sample_rate)
            duration_ms = int((len(audio) / self.sample_rate) * 1000)
            with open(f.name, "rb") as mp3_file:
                mp3_bytes = mp3_file.read()

        return mp3_bytes, duration_ms
