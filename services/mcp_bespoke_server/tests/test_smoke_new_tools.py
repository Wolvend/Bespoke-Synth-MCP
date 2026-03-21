"""
Smoke tests for the 15 new tools added in batch 2 (tools 30-44).

Run with: pytest tests/test_smoke_new_tools.py -v
All tests are pure-Python (no BespokeSynth / OSC connection required).

Beat used in MIDI export test:
  Style:  hardstyle / techno / breakcore + chibi cute sparkle lead
  BPM:    160
  Key:    F# minor
  Length: 4 bars (208 notes, 5 layers)
"""

import pytest

# ── Theory ─────────────────────────────────────────────────────────────────


def test_detect_chord_fsharp_minor():
    from mcp_bespoke_server.theory import detect_chord

    r = detect_chord([66, 69, 73])   # F#4, A4, C#5
    assert r["ok"]
    assert r["root"] == "F#"
    assert r["chord_type"] == "min"
    assert r["confidence"] == 1.0


def test_detect_chord_b_minor():
    from mcp_bespoke_server.theory import detect_chord

    r = detect_chord([71, 74, 78])   # B4, D5, F#5
    assert r["ok"]
    assert r["root"] == "B"
    assert r["chord_type"] == "min"
    assert r["confidence"] == 1.0


def test_rhythm_euclidean_length():
    """Pattern string must always be exactly `steps` characters long."""
    from mcp_bespoke_server.theory import rhythm

    for hits, steps in [(3, 8), (5, 8), (7, 16), (11, 16), (1, 4), (4, 4)]:
        r = rhythm(hits, steps)
        assert len(r["pattern"]) == steps, f"({hits},{steps}): len={len(r['pattern'])}"
        assert r["note_count"] == hits
        assert r["pattern"].count("x") == hits


def test_rhythm_known_patterns():
    """Validate well-known Euclidean patterns."""
    from mcp_bespoke_server.theory import rhythm

    assert rhythm(3, 8)["pattern"] == "x..x.x.."    # tresillo
    assert rhythm(5, 8)["pattern"] == "x.xx.xx."    # quintillo


def test_rhythm_notes_length():
    """Note list length should be hits * bars."""
    from mcp_bespoke_server.theory import rhythm

    r = rhythm(3, 8, bars=2)
    assert r["note_count"] == 6


def test_voice_lead_minimises_movement():
    from mcp_bespoke_server.theory import voice_lead, get_chord

    from_notes = get_chord("C", "maj", 4)["notes"]
    r = voice_lead(from_notes, "G", "maj")
    assert r["ok"]
    assert r["total_movement_semitones"] <= 6     # tight voice leading
    assert len(r["to_notes"]) >= 3


def test_modulate_pivot_chords():
    from mcp_bespoke_server.theory import modulate

    r = modulate("C", "major", "G", "major")
    assert r["ok"]
    assert len(r["pivot_chords"]) >= 4


def test_modulate_fsharp_minor_to_a_major():
    from mcp_bespoke_server.theory import modulate

    r = modulate("F#", "minor", "A", "major")
    assert r["ok"]
    # A major is the relative major of F# minor — lots of pivots expected
    assert len(r["pivot_chords"]) >= 5


# ── Compose ────────────────────────────────────────────────────────────────


def test_humanize_preserves_count():
    from mcp_bespoke_server.compose import humanize

    notes = [
        {"label": "C4", "pitch": 60, "velocity": 100, "at_ms": 0,   "duration_ms": 250},
        {"label": "E4", "pitch": 64, "velocity": 100, "at_ms": 375, "duration_ms": 250},
        {"label": "G4", "pitch": 67, "velocity": 100, "at_ms": 750, "duration_ms": 250},
    ]
    r = humanize(notes, timing_ms=10, velocity_pct=0.05, seed=1)
    assert r["ok"]
    assert r["note_count"] == 3


def test_humanize_clamps_values():
    from mcp_bespoke_server.compose import humanize

    notes = [{"label": "X", "pitch": 36, "velocity": 1, "at_ms": 0, "duration_ms": 100}]
    r = humanize(notes, timing_ms=100, velocity_pct=0.5, seed=99)
    assert r["ok"]
    assert 0 <= r["notes"][0]["velocity"] <= 127
    assert r["notes"][0]["at_ms"] >= 0


def test_humanize_reproducible_with_seed():
    from mcp_bespoke_server.compose import humanize

    notes = [{"label": "C4", "pitch": 60, "velocity": 100, "at_ms": 0, "duration_ms": 250}]
    r1 = humanize(notes, seed=42)
    r2 = humanize(notes, seed=42)
    assert r1["notes"][0]["velocity"] == r2["notes"][0]["velocity"]
    assert r1["notes"][0]["at_ms"] == r2["notes"][0]["at_ms"]


def test_generate_sequence_length():
    from mcp_bespoke_server.compose import generate_sequence

    r = generate_sequence("C", "major", length=16, rest_probability=0.0, seed=1)
    assert r["ok"]
    assert r["note_count"] == 16


def test_generate_sequence_rest_probability():
    from mcp_bespoke_server.compose import generate_sequence

    r = generate_sequence("C", "major", length=32, rest_probability=1.0, seed=1)
    assert r["note_count"] == 0


def test_generate_sequence_scale_bound():
    """All pitches must come from the requested scale."""
    from mcp_bespoke_server.compose import generate_sequence
    from mcp_bespoke_server.theory import get_scale

    r = generate_sequence("F#", "minor", octave=4, num_octaves=2, length=32, seed=7)
    scale_pitches = {n["midi"] for n in get_scale("F#", "minor", 4, 2)["notes"]}
    for note in r["notes"]:
        assert note["pitch"] in scale_pitches, f"pitch {note['pitch']} not in scale"


def test_export_midi_hardstyle_chibi_beat():
    """
    Export the full hardstyle / techno / breakcore + chibi cute beat as MIDI.

    160 BPM, F# minor, 4 bars:
      Layer 1 - Kick   (C2=36)  hardstyle + breakcore double kicks
      Layer 2 - Snare  (D2=38)  beats 2&4 + ghost notes
      Layer 3 - HH     (F#2=42) 8th-note closed hat grid
      Layer 4 - Bass   (F#3 area) syncopated reverse-bass line
      Layer 5 - Lead   (F#5-F#6) chibi sparkle arpeggio
    """
    from mcp_bespoke_server.compose import export_midi

    BPM = 160.0
    S = 60_000 / BPM / 4   # 16th note = 93.75 ms

    def note(pitch, vel, step, dur):
        return {"pitch": pitch, "velocity": vel,
                "at_ms": round(step * S), "duration_ms": dur}

    beat = []

    # Kick — hardstyle + breakcore fills
    for s in [0, 8, 16, 24, 32, 36, 40, 42, 44, 48, 50, 54, 56, 58, 60, 62]:
        beat.append(note(36, 127, s, 80))

    # Snare — 2 & 4
    for s in [4, 12, 20, 28, 36, 44, 52, 60]:
        beat.append(note(38, 100, s, 80))

    # Ghost snares
    for s in [2, 6, 10, 14, 22, 26, 30, 38, 46, 50, 54, 58]:
        beat.append(note(38, 40, s, 50))

    # Closed hi-hat every 8th note
    for s in range(0, 64, 2):
        beat.append(note(42, 65 + (5 if s % 4 == 0 else 0), s, 30))

    # Bass line — syncopated F# minor
    for s, p, v in [
        (0, 54, 100), (3, 57, 90), (6, 54, 95), (11, 59, 85),
        (16, 61, 100), (19, 59, 90), (22, 57, 88), (27, 56, 82),
        (32, 54, 100), (35, 57, 95), (38, 54, 92), (40, 62, 100), (43, 61, 95),
        (48, 54, 100), (50, 57, 95), (52, 54, 90), (54, 64, 100), (56, 62, 97), (58, 61, 93),
    ]:
        beat.append(note(p, v, s, 140))

    # Chibi sparkle lead — F#5 to F#6
    lead = [
        (0,78,95),(1,81,100),(2,85,105),(3,88,110),(4,85,105),(5,81,100),(6,80,90),(7,78,85),
        (8,81,95),(9,85,100),(10,88,105),(11,86,108),(12,85,100),(13,83,95),(14,81,90),(15,80,85),
        (16,90,110),(17,88,105),(18,85,100),(19,83,95),(20,81,90),(21,83,95),(22,85,100),(23,88,105),
        (24,90,110),(25,88,105),(26,85,100),(27,81,95),(28,80,90),(29,81,92),(30,83,95),(31,85,100),
        (32,78,110),(33,81,110),(34,85,110),(35,88,110),(36,90,110),(37,88,105),(38,85,100),(39,81,95),
        (40,90,110),(41,88,105),(42,85,100),(43,81,95),(44,80,90),(45,81,92),(46,83,95),(47,85,100),
        (48,88,105),(49,86,102),(50,85,100),(51,83,97),(52,81,95),(53,80,90),(54,78,85),(55,80,88),
        (56,81,92),(57,83,95),(58,85,100),(59,88,105),(60,90,110),(61,88,105),(62,85,100),(63,81,95),
    ]
    for s, p, v in lead:
        beat.append(note(p, v, s, 78))

    r = export_midi(notes=beat, bpm=BPM, filename="hardstyle_chibi_smoke.mid")

    assert r["ok"], f"export_midi failed: {r}"
    assert r["note_count"] > 100     # rich composition
    assert r["duration_s"] > 5.0    # longer than 5 seconds
    assert r["size_kb"] > 0.1       # actual bytes written
