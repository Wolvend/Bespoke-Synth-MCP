# mcp_bespoke_server

FastMCP server for BespokeSynth OSC control, music theory, composition management, and audio analysis.

## Installation

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -e .
```

**Optional dependencies** (install as needed):

```powershell
# BPM/key detection and LUFS measurement
pip install -e ".[audio]"   # scipy, pydub, pyloudnorm, numpy

# Stem separation (large download ~2 GB on first use)
pip install -e ".[stems]"   # demucs, torch, torchaudio

# MIDI export (included in core deps)
# mido, soundfile are always installed
```

## Running

```powershell
# stdio (default — for Claude Code / Claude Desktop)
python -m mcp_bespoke_server.server

# Streamable HTTP (for remote clients, Docker)
$env:MCP_TRANSPORT="streamable-http"
python -m mcp_bespoke_server.server
```

## Configuration

Copy `.env.example` to `.env` and adjust as needed. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `BESPOKE_CMD_HOST` | `127.0.0.1` | BespokeSynth OSC command host |
| `BESPOKE_CMD_PORT` | `9001` | BespokeSynth OSC command port |
| `REPLY_LISTEN_PORT` | `9002` | Port the server listens on for OSC replies |
| `TELEMETRY_LISTEN_PORT` | `9010` | Port for telemetry events from Bespoke |
| `ALLOW_ADMIN_TOOLS` | `false` | Enable `bespoke.admin.raw_command` |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http` |
| `MCP_HTTP_PORT` | `8000` | HTTP listen port (streamable-http only) |

## Tools (44 total)

### OSC / synth control

| Tool | Description |
|------|-------------|
| `bespoke.safe.health` | Ping the server — returns ok + timestamp |
| `bespoke.safe.list_modules` | List known BespokeSynth module names |
| `bespoke.safe.get_param` | Read a module parameter value |
| `bespoke.safe.set_param` | Write a parameter (immediate or ramped) |
| `bespoke.safe.batch_set_params` | Write up to 500 parameters in one OSC call |
| `bespoke.safe.automate` | Ramp or sequence a parameter over time (linear/exp/log curves or explicit points) |
| `bespoke.safe.play_note` | Trigger a single MIDI note |
| `bespoke.safe.schedule_notes` | Schedule up to 256 timed MIDI notes |
| `bespoke.safe.transport_set` | Start/stop playback, set BPM and beat position |
| `bespoke.safe.snapshot_load` | Load a named BespokeSynth snapshot |
| `bespoke.safe.save_snapshot` | Save current BespokeSynth state as a named snapshot |
| `bespoke.safe.list_snapshots` | List available snapshots from `BESPOKE_SNAPSHOTS_DIR` |
| `bespoke.safe.midi_cc` | Send a MIDI Control Change (CC) message via OSC |
| `bespoke.safe.get_all_params` | Read multiple parameter values in one batch |
| `bespoke.safe.telemetry_last` | Retrieve recent OSC telemetry events |
| `bespoke.admin.raw_command` | Send arbitrary OSC ops (disabled by default — set `ALLOW_ADMIN_TOOLS=true`) |

### Music theory

| Tool | Description |
|------|-------------|
| `bespoke.theory.info` | List all available scale modes and chord types |
| `bespoke.theory.scale` | Return every note in a scale with MIDI numbers and Hz |
| `bespoke.theory.chord` | Return chord voicing with MIDI numbers and Hz |
| `bespoke.theory.transpose` | Shift a note list by semitones |
| `bespoke.theory.quantize` | Snap a free frequency to the nearest scale degree |
| `bespoke.theory.progression` | Build a chord progression from Roman numerals (e.g. `I-IV-V-I`) |
| `bespoke.theory.arpeggiate` | Expand a chord into a timed note sequence ready for `schedule_notes` |
| `bespoke.theory.detect_chord` | Identify the most likely chord name from a list of MIDI pitches |
| `bespoke.theory.rhythm` | Generate a Euclidean (Bjorklund) rhythm pattern as a timed note sequence |
| `bespoke.theory.voice_lead` | Find a target chord voicing that minimises semitone movement from source |
| `bespoke.theory.modulate` | Find pivot chords shared between two diatonic keys |

Supported scale modes: `major`, `minor`, `dorian`, `phrygian`, `lydian`, `mixolydian`, `locrian`, `harmonic_minor`, `melodic_minor`, `pentatonic_major`, `pentatonic_minor`, `blues`, `whole_tone`, `diminished`, `chromatic`.

Supported chord types: `maj`, `min`, `dim`, `aug`, `maj7`, `min7`, `dom7`, `dim7`, `half_dim7`, `sus2`, `sus4`, `add9`, `maj9`, `min9`.

### Composition and track management

| Tool | Description |
|------|-------------|
| `bespoke.compose.list_presets` | List all workflow presets saved in `workflow_presets/` |
| `bespoke.compose.get_preset` | Return a preset's full step definition |
| `bespoke.compose.save_preset` | Save a new workflow preset to disk |
| `bespoke.compose.render_workflow` | Render a preset to an MP3 file |
| `bespoke.compose.list_tracks` | List generated MP3 tracks with metadata |
| `bespoke.compose.delete_track` | Delete a track and its companion JSON |
| `bespoke.compose.tag_track` | Merge metadata tags into a track's companion JSON |
| `compose.export_midi` | Export a preset or note list to a MIDI file (requires `mido`) |
| `compose.export_wav` | Export a workflow preset to a lossless WAV file (requires `soundfile`, `numpy`) |
| `compose.humanize` | Add random timing jitter and velocity variation to a note list |
| `compose.generate_sequence` | Generate a random melodic sequence within a scale |

### Audio analysis

| Tool | Description |
|------|-------------|
| `audio.analyze` | Detect BPM, musical key, and integrated loudness (LUFS) from an audio file |
| `audio.stems` | Separate a track into vocals/drums/bass/other stems via demucs (htdemucs model) |
| `audio.normalize` | Normalize a file to a target LUFS level (requires `pyloudnorm`, `soundfile`, `pydub`) |
| `audio.trim` | Trim leading and trailing silence (requires `pydub`) |
| `audio.splice` | Extract a time region from an audio file (requires `pydub`) |
| `audio.convert` | Convert between mp3/wav/flac/ogg formats (requires `pydub`) |

`audio.analyze` uses scipy + pydub for BPM and key detection, and pyloudnorm + soundfile for LUFS. All analysis sections are independent — a missing optional dep disables only that section.

`audio.stems` downloads the ~2 GB htdemucs model on first call and is slow on CPU (minutes per track). GPU reduces this to seconds.

## Example tool calls

### Play a C major arpeggio through BespokeSynth

```python
# 1. Generate the note sequence
arp = call("bespoke.theory.arpeggiate", {
    "root": "C", "chord_type": "maj", "octave": 4,
    "pattern": "up", "subdivision": "16th", "bpm": 120, "bars": 2
})

# 2. Send it to BespokeSynth
call("bespoke.safe.schedule_notes", {"notes": arp["notes"]})
```

### Analyze a track then export its MIDI representation

```python
# Analyze
info = call("audio.analyze", {"file": "my_track.mp3"})
# -> {"bpm": 128.0, "key": "A minor", "loudness_lufs": -12.4, ...}

# Export MIDI (note list mode)
call("compose.export_midi", {
    "notes": [{"pitch": 69, "velocity": 100, "at_ms": 0, "duration_ms": 500}],
    "bpm": info["bpm"]
})
```

### Build a ii-V-I progression and automate a filter sweep

```python
# Chord progression
prog = call("bespoke.theory.progression", {
    "root": "C", "mode": "major", "pattern": "ii-V-I", "octave": 4
})

# Automate filter cutoff over 4 bars at 120 BPM
call("bespoke.safe.automate", {
    "path": "filter~cutoff",
    "start_value": 0.1, "end_value": 0.9,
    "duration_ms": 8000, "steps": 32, "curve": "exp"
})
```

## Development

```powershell
pip install -e ".[dev]"
pytest
```

Tests live in `tests/`. The test suite uses `pytest-asyncio` with `asyncio_mode = "auto"`.
