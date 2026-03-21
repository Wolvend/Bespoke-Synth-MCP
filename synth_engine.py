#!/usr/bin/env python
"""Advanced synth engine for MCP workflows with presets."""

import json
import numpy as np
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Callable
from enum import Enum
from scipy import signal
from pydub import AudioSegment
import math


class WaveType(Enum):
    """Oscillator waveform types."""
    SINE = "sine"
    SQUARE = "square"
    SAWTOOTH = "sawtooth"
    TRIANGLE = "triangle"
    NOISE = "noise"


@dataclass
class ADSR:
    """Attack, Decay, Sustain, Release envelope."""
    attack_ms: float = 10
    decay_ms: float = 100
    sustain_level: float = 0.7
    release_ms: float = 200

    def generate(self, duration_ms: float, sample_rate: int) -> np.ndarray:
        """Generate ADSR envelope."""
        samples = int(duration_ms * sample_rate / 1000)
        envelope = np.ones(samples)

        attack_samples = int(self.attack_ms * sample_rate / 1000)
        decay_samples = int(self.decay_ms * sample_rate / 1000)
        release_samples = int(self.release_ms * sample_rate / 1000)

        if attack_samples > 0:
            envelope[:attack_samples] = np.linspace(0, 1, attack_samples)

        decay_start = attack_samples
        decay_end = min(attack_samples + decay_samples, samples)
        if decay_end > decay_start:
            envelope[decay_start:decay_end] = np.linspace(
                1, self.sustain_level, decay_end - decay_start
            )

        sustain_end = max(0, samples - release_samples)
        if sustain_end > decay_end:
            envelope[decay_end:sustain_end] = self.sustain_level

        release_start = sustain_end
        if release_start < samples:
            envelope[release_start:] = np.linspace(
                self.sustain_level, 0, samples - release_start
            )

        return envelope


@dataclass
class OscillatorConfig:
    """Oscillator configuration."""
    wave_type: WaveType = WaveType.SINE
    frequency: float = 440
    amplitude: float = 1.0
    phase_offset: float = 0.0


class Oscillator:
    """Basic oscillator."""

    def __init__(self, config: OscillatorConfig):
        self.config = config

    def generate(self, duration_seconds: float, sample_rate: int) -> np.ndarray:
        """Generate oscillator signal."""
        t = np.linspace(0, duration_seconds, int(duration_seconds * sample_rate), False)
        phase = 2 * np.pi * self.config.frequency * t + self.config.phase_offset

        if self.config.wave_type == WaveType.SINE:
            signal_data = np.sin(phase)
        elif self.config.wave_type == WaveType.SQUARE:
            signal_data = np.sign(np.sin(phase))
        elif self.config.wave_type == WaveType.SAWTOOTH:
            signal_data = 2 * (phase / (2 * np.pi) - np.floor(phase / (2 * np.pi) + 0.5))
        elif self.config.wave_type == WaveType.TRIANGLE:
            signal_data = 2 * np.abs(2 * (phase / (2 * np.pi) - np.floor(phase / (2 * np.pi) + 0.5))) - 1
        elif self.config.wave_type == WaveType.NOISE:
            signal_data = np.random.uniform(-1, 1, len(t))
        else:
            signal_data = np.sin(phase)

        return signal_data * self.config.amplitude


@dataclass
class SynthPreset:
    """Complete synth preset configuration."""
    name: str
    oscillators: List[OscillatorConfig]
    envelope: ADSR
    filter_cutoff: float = 1.0
    filter_resonance: float = 0.5
    effects: dict = None

    def __post_init__(self):
        if self.effects is None:
            self.effects = {}


# Built-in presets
PRESETS = {
    "kick_808": SynthPreset(
        name="kick_808",
        oscillators=[
            OscillatorConfig(WaveType.SINE, 150, 1.0),
            OscillatorConfig(WaveType.SINE, 80, 0.7),
        ],
        envelope=ADSR(attack_ms=5, decay_ms=400, sustain_level=0.0, release_ms=50),
        filter_cutoff=0.4,
    ),
    "snare_crisp": SynthPreset(
        name="snare_crisp",
        oscillators=[
            OscillatorConfig(WaveType.NOISE, 200, 0.9),
        ],
        envelope=ADSR(attack_ms=2, decay_ms=150, sustain_level=0.1, release_ms=100),
        filter_cutoff=0.7,
    ),
    "hihat_closed": SynthPreset(
        name="hihat_closed",
        oscillators=[
            OscillatorConfig(WaveType.NOISE, 400, 0.8),
            OscillatorConfig(WaveType.SQUARE, 150, 0.3),
        ],
        envelope=ADSR(attack_ms=1, decay_ms=60, sustain_level=0.0, release_ms=30),
        filter_cutoff=0.85,
    ),
    "hihat_open": SynthPreset(
        name="hihat_open",
        oscillators=[
            OscillatorConfig(WaveType.NOISE, 400, 0.8),
            OscillatorConfig(WaveType.SQUARE, 150, 0.3),
        ],
        envelope=ADSR(attack_ms=2, decay_ms=300, sustain_level=0.3, release_ms=200),
        filter_cutoff=0.85,
    ),
    "bass_deep": SynthPreset(
        name="bass_deep",
        oscillators=[
            OscillatorConfig(WaveType.SAWTOOTH, 55, 0.8),
            OscillatorConfig(WaveType.SINE, 110, 0.5),
        ],
        envelope=ADSR(attack_ms=20, decay_ms=100, sustain_level=0.8, release_ms=150),
        filter_cutoff=0.3,
        filter_resonance=0.7,
    ),
    "lead_bright": SynthPreset(
        name="lead_bright",
        oscillators=[
            OscillatorConfig(WaveType.SAWTOOTH, 440, 0.7),
            OscillatorConfig(WaveType.SQUARE, 220, 0.4),
        ],
        envelope=ADSR(attack_ms=30, decay_ms=200, sustain_level=0.6, release_ms=300),
        filter_cutoff=0.7,
        filter_resonance=0.8,
    ),
    "synth_pad": SynthPreset(
        name="synth_pad",
        oscillators=[
            OscillatorConfig(WaveType.SINE, 220, 0.5),
            OscillatorConfig(WaveType.SINE, 330, 0.4),
            OscillatorConfig(WaveType.SINE, 440, 0.3),
        ],
        envelope=ADSR(attack_ms=100, decay_ms=300, sustain_level=0.7, release_ms=500),
        filter_cutoff=0.6,
    ),
    "tom_high": SynthPreset(
        name="tom_high",
        oscillators=[
            OscillatorConfig(WaveType.SINE, 250, 1.0),
        ],
        envelope=ADSR(attack_ms=5, decay_ms=120, sustain_level=0.0, release_ms=50),
        filter_cutoff=0.5,
    ),
    "tom_mid": SynthPreset(
        name="tom_mid",
        oscillators=[
            OscillatorConfig(WaveType.SINE, 180, 1.0),
        ],
        envelope=ADSR(attack_ms=5, decay_ms=150, sustain_level=0.0, release_ms=50),
        filter_cutoff=0.5,
    ),
    "tom_low": SynthPreset(
        name="tom_low",
        oscillators=[
            OscillatorConfig(WaveType.SINE, 120, 1.0),
        ],
        envelope=ADSR(attack_ms=5, decay_ms=180, sustain_level=0.0, release_ms=50),
        filter_cutoff=0.5,
    ),
}


class SynthEngine:
    """Synth engine for generating audio from presets."""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate

    def render_note(self, preset: SynthPreset, duration_ms: float) -> np.ndarray:
        """Render a single note from preset."""
        duration_seconds = duration_ms / 1000.0
        audio = np.zeros(int(duration_seconds * self.sample_rate))

        # Mix oscillators
        for osc_config in preset.oscillators:
            osc = Oscillator(osc_config)
            audio += osc.generate(duration_seconds, self.sample_rate)

        # Normalize oscillators
        if len(preset.oscillators) > 0:
            audio /= len(preset.oscillators)

        # Apply envelope
        envelope = preset.envelope.generate(duration_ms, self.sample_rate)
        audio *= envelope

        # Apply filter
        if preset.filter_cutoff < 1.0:
            nyquist = self.sample_rate / 2
            normal_cutoff = max(0.01, min(0.99, preset.filter_cutoff))
            order = 2 if preset.filter_resonance < 0.5 else 4
            try:
                b, a = signal.butter(order, normal_cutoff, btype='low')
                audio = signal.filtfilt(b, a, audio)
            except:
                pass

        # Clamp and normalize
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / (max_val * 1.1)
        audio = np.clip(audio, -1, 1)

        return audio.astype(np.float32)

    def render_sequence(self, pattern: List[tuple]) -> np.ndarray:
        """Render a sequence of notes.

        pattern: List of (preset_name, duration_ms, delay_ms)
        """
        all_audio = []

        for preset_name, duration_ms, delay_ms in pattern:
            preset = PRESETS.get(preset_name) or PRESETS["kick_808"]

            # Add delay (silence)
            if delay_ms > 0:
                all_audio.append(np.zeros(int(delay_ms * self.sample_rate / 1000)))

            # Render note
            audio = self.render_note(preset, duration_ms)
            all_audio.append(audio)

        return np.concatenate(all_audio)


def save_audio_mp3(audio_array: np.ndarray, filename: str, sample_rate: int = 44100):
    """Save audio array to MP3."""
    # Convert to int16
    audio_int16 = (audio_array * 32767).astype(np.int16)

    # Create AudioSegment
    audio_segment = AudioSegment(
        audio_int16.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,
        channels=1
    )

    # Export
    audio_segment.export(filename, format="mp3", bitrate="320k")
