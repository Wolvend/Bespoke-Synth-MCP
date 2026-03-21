"""
bespoke.theory — Music theory helpers.
Pure computation, no OSC, no I/O.
"""
from __future__ import annotations

import math
import random
from typing import Literal

# ─── Note table ──────────────────────────────────────────────────────────────

# Chromatic note names (two spellings where needed)
_CHROMA: list[list[str]] = [
    ["C"],
    ["C#", "Db"],
    ["D"],
    ["D#", "Eb"],
    ["E"],
    ["F"],
    ["F#", "Gb"],
    ["G"],
    ["G#", "Ab"],
    ["A"],
    ["A#", "Bb"],
    ["B"],
]

# MIDI note number for C0
_MIDI_C0 = 12  # C0 = 12, C4 = 60


def _note_to_semitone(note: str) -> int:
    """Return 0-11 semitone index for a note name like 'C', 'F#', 'Bb'."""
    note = note.strip().capitalize()
    # Normalise flats/sharps
    note = note.replace("♭", "b").replace("♯", "#")
    for idx, group in enumerate(_CHROMA):
        if note in group:
            return idx
    raise ValueError(f"Unknown note name: {note!r}")


def _midi_to_freq(midi: int) -> float:
    """Standard MIDI note number → frequency in Hz (A4 = 440, MIDI 69)."""
    return 440.0 * (2 ** ((midi - 69) / 12))


def _note_name(semitone: int, prefer_sharp: bool = True) -> str:
    group = _CHROMA[semitone % 12]
    return group[0] if prefer_sharp else group[-1]


# ─── Scale interval patterns ──────────────────────────────────────────────────

ModeType = Literal[
    "major", "minor", "dorian", "phrygian", "lydian",
    "mixolydian", "locrian", "harmonic_minor", "melodic_minor",
    "pentatonic_major", "pentatonic_minor", "blues",
    "whole_tone", "diminished", "chromatic",
]

_MODE_INTERVALS: dict[str, list[int]] = {
    "major":           [0, 2, 4, 5, 7, 9, 11],
    "minor":           [0, 2, 3, 5, 7, 8, 10],
    "dorian":          [0, 2, 3, 5, 7, 9, 10],
    "phrygian":        [0, 1, 3, 5, 7, 8, 10],
    "lydian":          [0, 2, 4, 6, 7, 9, 11],
    "mixolydian":      [0, 2, 4, 5, 7, 9, 10],
    "locrian":         [0, 1, 3, 5, 6, 8, 10],
    "harmonic_minor":  [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor":   [0, 2, 3, 5, 7, 9, 11],
    "pentatonic_major":[0, 2, 4, 7, 9],
    "pentatonic_minor":[0, 3, 5, 7, 10],
    "blues":           [0, 3, 5, 6, 7, 10],
    "whole_tone":      [0, 2, 4, 6, 8, 10],
    "diminished":      [0, 2, 3, 5, 6, 8, 9, 11],
    "chromatic":       list(range(12)),
}

ChordType = Literal[
    "maj", "min", "dim", "aug",
    "maj7", "min7", "dom7", "dim7", "half_dim7",
    "sus2", "sus4", "add9",
    "maj9", "min9",
]

_CHORD_INTERVALS: dict[str, list[int]] = {
    "maj":       [0, 4, 7],
    "min":       [0, 3, 7],
    "dim":       [0, 3, 6],
    "aug":       [0, 4, 8],
    "maj7":      [0, 4, 7, 11],
    "min7":      [0, 3, 7, 10],
    "dom7":      [0, 4, 7, 10],
    "dim7":      [0, 3, 6, 9],
    "half_dim7": [0, 3, 6, 10],
    "sus2":      [0, 2, 7],
    "sus4":      [0, 5, 7],
    "add9":      [0, 4, 7, 14],
    "maj9":      [0, 4, 7, 11, 14],
    "min9":      [0, 3, 7, 10, 14],
}


# ─── Public API ───────────────────────────────────────────────────────────────

def get_scale(
    root: str,
    mode: ModeType = "major",
    octave: int = 4,
    num_octaves: int = 1,
) -> dict:
    """
    Return notes in a scale.

    Args:
        root: Root note name, e.g. "C", "F#", "Bb".
        mode: Scale mode.
        octave: Starting octave (4 = middle octave, C4 = 261.6 Hz).
        num_octaves: How many octaves to return.

    Returns:
        {
          "root": "C", "mode": "major", "octave": 4,
          "notes": [
            {"name": "C4", "midi": 60, "freq_hz": 261.63},
            ...
          ]
        }
    """
    intervals = _MODE_INTERVALS[mode]
    root_semi = _note_to_semitone(root)
    root_midi = _MIDI_C0 + root_semi + octave * 12

    notes = []
    for oct_offset in range(num_octaves):
        for interval in intervals:
            midi = root_midi + oct_offset * 12 + interval
            semi = midi % 12
            oct_ = (midi - _MIDI_C0) // 12
            name = _note_name(semi) + str(oct_)
            notes.append({
                "name":    name,
                "midi":    midi,
                "freq_hz": round(_midi_to_freq(midi), 3),
            })

    return {
        "root":      root,
        "mode":      mode,
        "octave":    octave,
        "num_notes": len(notes),
        "notes":     notes,
    }


def get_chord(
    root: str,
    chord_type: ChordType = "maj",
    octave: int = 4,
    inversion: int = 0,
) -> dict:
    """
    Return notes in a chord voicing.

    Args:
        root: Root note name.
        chord_type: Chord quality.
        octave: Root octave.
        inversion: 0 = root position, 1 = first, 2 = second, etc.

    Returns:
        {
          "root": "C", "type": "maj7", "octave": 4, "inversion": 0,
          "notes": [{"name": ..., "midi": ..., "freq_hz": ...}, ...]
        }
    """
    intervals = list(_CHORD_INTERVALS[chord_type])
    root_semi = _note_to_semitone(root)
    root_midi = _MIDI_C0 + root_semi + octave * 12

    # Apply inversion: rotate bass note up an octave
    inv = inversion % len(intervals)
    for _ in range(inv):
        intervals = intervals[1:] + [intervals[0] + 12]

    notes = []
    for interval in intervals:
        midi = root_midi + interval
        semi = midi % 12
        oct_ = (midi - _MIDI_C0) // 12
        name = _note_name(semi) + str(oct_)
        notes.append({
            "name":    name,
            "midi":    midi,
            "freq_hz": round(_midi_to_freq(midi), 3),
        })

    return {
        "root":      root,
        "type":      chord_type,
        "octave":    octave,
        "inversion": inversion,
        "num_notes": len(notes),
        "notes":     notes,
    }


def transpose(notes: list[dict], semitones: int) -> list[dict]:
    """
    Shift a list of note dicts by semitones.

    Args:
        notes: List of {"name": ..., "midi": ..., "freq_hz": ...}.
        semitones: Positive = up, negative = down.

    Returns:
        New list with shifted notes.
    """
    result = []
    for n in notes:
        midi = n["midi"] + semitones
        semi = midi % 12
        oct_ = (midi - _MIDI_C0) // 12
        result.append({
            "name":    _note_name(semi) + str(oct_),
            "midi":    midi,
            "freq_hz": round(_midi_to_freq(midi), 3),
        })
    return result


def quantize_to_scale(
    freq_hz: float,
    root: str,
    mode: ModeType = "major",
) -> dict:
    """
    Snap a free frequency to the nearest scale degree.

    Returns the closest note in the scale (searching all octaves 0-8).
    """
    scale_notes = get_scale(root, mode, octave=0, num_octaves=9)["notes"]
    best = min(
        scale_notes,
        key=lambda n: abs(n["freq_hz"] - freq_hz),
    )
    return {
        "input_freq_hz":    round(freq_hz, 3),
        "quantized":        best,
        "cents_deviation":  round(1200 * math.log2(freq_hz / best["freq_hz"]), 2),
    }


def list_modes() -> list[str]:
    return sorted(_MODE_INTERVALS.keys())


def list_chord_types() -> list[str]:
    return sorted(_CHORD_INTERVALS.keys())


# ─── Chord progression support ────────────────────────────────────────────────

_ROMAN_TO_DEGREE: dict[str, int] = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7,
}

_MODE_DEGREE_QUALITY: dict[str, list[str]] = {
    "major":          ["maj", "min", "min", "maj", "maj", "min", "dim"],
    "minor":          ["min", "dim", "maj", "min", "min", "maj", "maj"],
    "dorian":         ["min", "min", "maj", "maj", "min", "dim", "maj"],
    "phrygian":       ["min", "maj", "maj", "min", "dim", "maj", "min"],
    "lydian":         ["maj", "maj", "min", "dim", "maj", "min", "min"],
    "mixolydian":     ["maj", "min", "dim", "maj", "min", "min", "maj"],
    "locrian":        ["dim", "maj", "min", "min", "maj", "maj", "min"],
    "harmonic_minor": ["min", "dim", "aug", "min", "maj", "maj", "dim"],
    "melodic_minor":  ["min", "min", "aug", "maj", "maj", "dim", "dim"],
}


def progression(
    root: str,
    mode: str = "major",
    pattern: str = "I-IV-V-I",
    octave: int = 4,
) -> dict:
    """
    Generate a chord progression from a Roman numeral pattern.

    Args:
        root: Root note, e.g. "C", "F#", "Bb".
        mode: Scale mode (must be a 7-note diatonic mode).
        pattern: Dash-separated Roman numerals, e.g. "I-IV-V-I", "ii-V-I".
        octave: Octave for chord voicing.

    Returns:
        {"ok": True, "root", "mode", "pattern", "chords": [{"degree", "roman", "root", "type", "notes"}]}
    """
    if mode not in _MODE_DEGREE_QUALITY:
        raise ValueError(
            f"Mode {mode!r} is not supported for progressions. "
            f"Supported: {sorted(_MODE_DEGREE_QUALITY)}"
        )
    intervals = _MODE_INTERVALS[mode]
    root_semi = _note_to_semitone(root)
    romans = [r.strip() for r in pattern.split("-") if r.strip()]
    chords = []
    for roman in romans:
        roman_upper = roman.upper()
        if roman_upper not in _ROMAN_TO_DEGREE:
            raise ValueError(f"Unknown Roman numeral: {roman!r}")
        degree = _ROMAN_TO_DEGREE[roman_upper]
        degree_idx = degree - 1
        scale_int = intervals[degree_idx]
        chord_root_semi = (root_semi + scale_int) % 12
        chord_root = _note_name(chord_root_semi)
        chord_type = _MODE_DEGREE_QUALITY[mode][degree_idx]
        chord_data = get_chord(chord_root, chord_type, octave)  # type: ignore[arg-type]
        chords.append({
            "degree": degree,
            "roman":  roman,
            "root":   chord_root,
            "type":   chord_type,
            "notes":  chord_data["notes"],
        })
    return {"ok": True, "root": root, "mode": mode, "pattern": pattern, "chords": chords}


# ─── Arpeggiator ──────────────────────────────────────────────────────────────

_SUBDIVISION_BEATS: dict[str, float] = {
    "8th":     0.5,
    "16th":    0.25,
    "triplet": 1.0 / 3.0,
}


def arpeggiate(
    root: str,
    chord_type: str = "maj",
    octave: int = 4,
    pattern: str = "up",
    subdivision: str = "16th",
    bpm: float = 120.0,
    bars: int = 1,
    velocity: int = 100,
) -> dict:
    """
    Expand a chord into a timed note sequence compatible with bespoke.safe.schedule_notes.

    Args:
        root: Root note name.
        chord_type: Chord quality (maj, min, dim, etc.).
        octave: Root octave.
        pattern: up | down | updown | random
        subdivision: 8th | 16th | triplet
        bpm: Beats per minute (used to calculate note timing in ms).
        bars: Number of bars to fill (assumes 4/4 time).
        velocity: MIDI velocity 0-127.

    Returns:
        {"ok": True, "note_count": N, "notes": [{"label", "pitch", "velocity", "at_ms", "duration_ms"}]}
    """
    chord_data = get_chord(root, chord_type, octave)  # type: ignore[arg-type]
    base_notes = chord_data["notes"]
    ms_per_sub = _SUBDIVISION_BEATS[subdivision] * (60_000.0 / bpm)
    total_slots = int(bars * 4 * (60_000.0 / bpm) / ms_per_sub)
    n = len(base_notes)
    if pattern == "up":
        seq = list(range(n))
    elif pattern == "down":
        seq = list(range(n - 1, -1, -1))
    elif pattern == "updown":
        seq = list(range(n)) + list(range(n - 2, 0, -1))
    elif pattern == "random":
        seq = list(range(n))
        random.shuffle(seq)
    else:
        raise ValueError(f"Unknown arpeggio pattern: {pattern!r}")
    notes = []
    for slot in range(total_slots):
        note = base_notes[seq[slot % len(seq)]]
        at_ms = int(slot * ms_per_sub)
        dur_ms = min(max(1, int(ms_per_sub) - 10), 60000)
        notes.append({
            "label":       note["name"],
            "pitch":       note["midi"],
            "velocity":    velocity,
            "at_ms":       at_ms,
            "duration_ms": dur_ms,
        })
    return {
        "ok":         True,
        "root":       root,
        "chord_type": chord_type,
        "pattern":    pattern,
        "note_count": len(notes),
        "notes":      notes,
    }
