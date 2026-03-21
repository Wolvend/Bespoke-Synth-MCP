<div align="center">

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     ██████╗ ███████╗███████╗██████╗  ██████╗ ██╗  ██╗      ║
║     ██╔══██╗██╔════╝██╔════╝██╔══██╗██╔═══██╗██║ ██╔╝      ║
║     ██████╔╝█████╗  ███████╗██████╔╝██║   ██║█████╔╝       ║
║     ██╔══██╗██╔══╝  ╚════██║██╔═══╝ ██║   ██║██╔═██╗       ║
║     ██████╔╝███████╗███████║██║     ╚██████╔╝██║  ██╗      ║
║     ╚═════╝ ╚══════╝╚══════╝╚═╝      ╚═════╝ ╚═╝  ╚═╝      ║
║                                                              ║
║           S Y N T H   M C P   P L A T F O R M               ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

**Control BespokeSynth with AI — 44 tools across OSC, music theory, composition & audio**

[![CI](https://github.com/Wolvend/Bespoke-Synth-MCP/actions/workflows/ci.yml/badge.svg)](https://github.com/Wolvend/Bespoke-Synth-MCP/actions)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)](https://python.org)
[![MCP](https://img.shields.io/badge/protocol-MCP-purple)](https://modelcontextprotocol.io)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

</div>

---

## What is this?

BespokeSynth MCP is a **Model Context Protocol server** that lets AI assistants (Claude, GPT-4, Gemini, local models) compose, control, and render music through [BespokeSynth](https://www.bespokesynth.com/) — a free, open-source modular synthesizer.

You describe what you want. The AI uses the tools. Music comes out.

```
  You  ──►  Claude  ──►  MCP Tools  ──►  BespokeSynth  ──►  Audio
 "play       "I'll        44 tools         OSC bridge        .mp3
  jazz        use         validated        live synth
  chords"     theory      + typed          engine
              tools"
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR AI CLIENT                           │
│            (Claude Code · Cursor · VS Code · Custom)            │
└──────────────────────────┬──────────────────────────────────────┘
                           │  MCP Protocol (stdio or HTTP)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MCP BESPOKE SERVER                           │
│  ┌────────────┐  ┌─────────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Theory    │  │  Compose    │  │  Audio   │  │   OSC    │  │
│  │  11 tools  │  │  11 tools   │  │  6 tools │  │ 16 tools │  │
│  └────────────┘  └─────────────┘  └──────────┘  └──────────┘  │
│               FastMCP · Pydantic v2 · Python 3.11               │
└──────────────────────────┬──────────────────────────────────────┘
                           │  UDP OSC  (port 9001 → 9002)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BESPOKESYNTH                               │
│         Modular synth + Script Agent (Python in-DAW)            │
│              Applies params · plays notes · renders              │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ORCHESTRATOR  (optional)                       │
│      Multi-model router · Privacy modes · Planner/executor       │
│      Providers: OpenAI · Anthropic · Gemini · Ollama             │
└─────────────────────────────────────────────────────────────────┘
```

**Key design principle:** LLMs never touch BespokeSynth directly. Every action routes through typed, validated MCP tools — the AI can only do what the tools explicitly allow.

---

## Quick Start

### Option 1 — Docker (recommended)

```bash
git clone https://github.com/Wolvend/Bespoke-Synth-MCP.git
cd Bespoke-Synth-MCP

cp .env.example .env
# Edit .env: set BESPOKE_CMD_HOST to your BespokeSynth machine IP

docker compose up --build
# MCP server  ->  http://localhost:8000
# Orchestrator ->  http://localhost:8088
```

### Option 2 — Claude Code on Windows (stdio)

```powershell
# Build the image
.\scripts\build_windows_docker_mcp.ps1

# Add to your .mcp.json (see examples/client-configs/claude-code.mcp.json)
# Claude Code starts the container automatically on first tool call
```

### Option 3 — Local Python

```bash
cd services/mcp_bespoke_server
pip install -e ".[dev,audio]"

# stdio mode
python -m mcp_bespoke_server.server

# HTTP mode
MCP_TRANSPORT=streamable-http python -m mcp_bespoke_server.server
```

---

## All 44 Tools

### OSC & Synth Control

*Send commands to BespokeSynth. All tools support `dry_run=true` for safe validation.*

| Tool | Description |
|------|-------------|
| `bespoke.safe.health` | Ping the server — confirms connection is live |
| `bespoke.safe.list_modules` | List all loaded BespokeSynth modules |
| `bespoke.safe.get_param` | Read a single module parameter value |
| `bespoke.safe.get_all_params` | Read multiple parameters in one batch |
| `bespoke.safe.set_param` | Write a parameter (immediate or ramped transition) |
| `bespoke.safe.batch_set_params` | Write up to 500 parameters in one call |
| `bespoke.safe.play_note` | Play a single MIDI note (pitch, velocity, duration) |
| `bespoke.safe.schedule_notes` | Schedule up to 256 timed MIDI notes |
| `bespoke.safe.midi_cc` | Send a MIDI CC message (modwheel, cutoff, etc.) |
| `bespoke.safe.transport_set` | Set BPM and start / stop playback |
| `bespoke.safe.automate` | Ramp or sequence a parameter over time |
| `bespoke.safe.list_snapshots` | List saved BespokeSynth snapshots |
| `bespoke.safe.snapshot_load` | Load a named snapshot |
| `bespoke.safe.save_snapshot` | Save current state as a named snapshot |
| `bespoke.safe.telemetry_last` | Retrieve recent OSC telemetry events |
| `bespoke.admin.raw_command` | Send arbitrary OSC ops *(disabled by default)* |

---

### Music Theory

*Build scales, chords, progressions, rhythms — all rooted in real music theory.*

| Tool | Description | Example |
|------|-------------|---------|
| `bespoke.theory.info` | List all available modes and chord types | 15 modes, 14 chord types |
| `bespoke.theory.scale` | Notes in a scale with MIDI numbers + Hz | `root=G, mode=major` |
| `bespoke.theory.chord` | Build a chord voicing | `root=C, type=maj7` |
| `bespoke.theory.progression` | Roman-numeral chord progression | `I-IV-V-I` in any key |
| `bespoke.theory.arpeggiate` | Expand chord into timed note sequence | up / down / updown / random |
| `bespoke.theory.transpose` | Shift notes by semitones | `+12` = octave up |
| `bespoke.theory.quantize` | Snap a frequency to nearest scale degree | returns cents deviation |
| `bespoke.theory.detect_chord` | Identify chord name from MIDI pitches | `[60,64,67]` → C major |
| `bespoke.theory.voice_lead` | Find voicing that minimizes semitone movement | smooth transitions |
| `bespoke.theory.modulate` | Find pivot chords between two keys | for key changes |
| `bespoke.theory.rhythm` | Euclidean rhythm via Bjorklund algorithm | `hits=5, steps=16` |

**Scales:** major · minor · dorian · phrygian · lydian · mixolydian · locrian · harmonic minor · melodic minor · pentatonic major/minor · blues · whole tone · diminished · chromatic

**Chords:** maj · min · dim · aug · maj7 · min7 · dom7 · dim7 · half_dim7 · sus2 · sus4 · add9 · maj9 · min9

---

### Composition

*From raw notes to finished tracks.*

| Tool | Description |
|------|-------------|
| `compose.generate_sequence` | Generate a melodic sequence within a scale |
| `compose.humanize` | Add timing jitter + velocity variation |
| `compose.export_midi` | Export a note list to a `.mid` file |
| `compose.export_wav` | Export a workflow preset to lossless WAV |
| `bespoke.compose.save_preset` | Save a multi-step workflow as a named preset |
| `bespoke.compose.get_preset` | Inspect a preset's full step definition |
| `bespoke.compose.list_presets` | List all available presets |
| `bespoke.compose.render_workflow` | Render a preset to MP3 |
| `bespoke.compose.list_tracks` | List recently generated tracks with metadata |
| `bespoke.compose.tag_track` | Write metadata tags to a track |
| `bespoke.compose.delete_track` | Remove a track and its metadata file |

---

### Audio Processing

*Analyze, normalize, cut, and convert your renders.*

| Tool | Description | Extra deps needed |
|------|-------------|------------------|
| `audio.analyze` | Detect BPM, musical key, and loudness (LUFS) | scipy, pydub |
| `audio.normalize` | Normalize to a target LUFS level | pyloudnorm, soundfile |
| `audio.trim` | Strip leading / trailing silence | pydub |
| `audio.splice` | Extract a time region from a file | pydub |
| `audio.convert` | Convert between mp3 / wav / flac / ogg | pydub |
| `audio.stems` | Separate into drums / bass / vocals / other | demucs, torch (~2 GB) |

```bash
# Install audio tools
pip install ".[audio]"

# Install stem separation (large download)
pip install ".[stems]"
```

---

## End-to-End Example

```
Claude Code conversation:

You:     "Make a hardstyle track in D minor at 174 BPM"

Claude:  1. bespoke.theory.scale(root="D", mode="minor")
         2. bespoke.theory.progression(root="D", mode="minor")
         3. bespoke.theory.rhythm(hits=5, steps=16)
         4. compose.generate_sequence(root="D", scale="minor", length=32)
         5. compose.humanize(notes=[...], timing_variation_ms=8)
         6. bespoke.safe.transport_set(bpm=174, playing=False, dry_run=True)
         7. bespoke.safe.schedule_notes(notes=[...], dry_run=True)
         8. bespoke.compose.save_preset(name="drop", bpm=174, steps=[...])
         9. bespoke.compose.render_workflow(name="drop")
        10. audio.analyze(file="drop.mp3")
        11. audio.normalize(file="drop.mp3", target_lufs=-7)
        12. audio.convert(file="drop_norm.mp3", format="flac")
        13. bespoke.compose.tag_track(file="drop.flac", tags={...})

Result:  drop.flac — 174 BPM, D minor, mastered to -7 LUFS
```

---

## Audio QC

Run this on every render before listening:

```bash
python check_audio.py tracks/my_track.wav
```

Checks: clipping · silence ratio · frequency balance (sub/bass/mid/high) · sidechain pumping · dead sections · stereo width

```
============================================================
  Audio QC: sunrise.wav
============================================================
  [PASS] No NaN/Inf
  [PASS] No clipping
  [PASS] Silence: 14.7%
  [PASS] sub    20-80Hz    -30.2 dBFS  #######################
  [PASS] bass  80-250Hz    -27.0 dBFS  #########################
  [PASS] mid  250-2kHz     -31.5 dBFS  #######################
  [PASS] high  2k-8kHz     -40.9 dBFS  #################
  [PASS] Sidechain: 2% near-silent windows (OK)
  [PASS] Stereo width: -6.7dB (wide)
  [PASS] All checks passed -- ready to deliver
============================================================
```

---

## Project Layout

```
bespokesynth_mcp/
│
├── services/mcp_bespoke_server/    # The MCP server (all 44 tools)
│   └── src/mcp_bespoke_server/
│       ├── server.py               # Tool definitions + FastMCP wiring
│       ├── theory.py               # Music theory engine
│       ├── compose.py              # Composition + preset management
│       ├── audio.py                # Audio analysis + processing
│       ├── osc_bridge.py           # BespokeSynth OSC communication
│       └── schemas.py              # Pydantic input/output models
│
├── orchestrator/                   # Optional multi-model orchestration
│   └── src/orchestrator/
│       ├── api.py                  # FastAPI REST endpoints
│       ├── model_router.py         # OpenAI / Anthropic / Gemini / Ollama
│       ├── planner.py              # Task planning + decomposition
│       └── policies.py             # Privacy modes + consent gating
│
├── infra/docker/                   # Dockerfiles for both services
├── examples/client-configs/        # Claude Code, Cursor, VS Code configs
├── docs/                           # Full documentation (12 pages)
├── tracks/                         # Generated audio output
├── check_audio.py                  # Audio QC checker
└── docker-compose.yml              # One-command startup
```

---

## Configuration

```env
# .env — copy from .env.example

BESPOKE_CMD_HOST=127.0.0.1      # BespokeSynth machine IP
BESPOKE_CMD_PORT=9001            # OSC command port
REPLY_LISTEN_PORT=9002           # OSC reply port
TELEMETRY_LISTEN_PORT=9010       # OSC telemetry port

MCP_TRANSPORT=stdio              # or: streamable-http

ALLOW_ADMIN_TOOLS=false          # true = enables raw_command
BESPOKE_KNOWN_MODULES=transport,filter~cutoff,main~volume
```

---

## Documentation

| Guide | Contents |
|-------|---------|
| [Setup](docs/setup.md) | Installation, Python env, BespokeSynth script agent |
| [API Reference](docs/api.md) | Every tool, every parameter, every return value |
| [Architecture](docs/architecture.md) | System design, data flow, security boundary |
| [Docker](docs/docker.md) | Container setup, volumes, networking |
| [Windows + Claude Code](docs/windows_docker_mcp.md) | stdio mode on Windows with Docker Desktop |
| [CLI Clients](docs/cli_clients.md) | Claude Code, Cursor, VS Code integration |
| [Security](docs/security.md) | Auth, TLS, admin tool gating, consent modes |
| [Ops Runbook](docs/ops_runbook.md) | Health checks, restart procedures, monitoring |
| [Testing](docs/testing.md) | Unit tests, E2E with mocks, smoke tests |
| [Troubleshooting](docs/troubleshooting.md) | Common errors and fixes |

---

## Requirements

| Component | Requires |
|-----------|---------|
| MCP server | Python 3.11+, Docker Desktop |
| Audio analysis | `pip install ".[audio]"` — pydub, scipy, pyloudnorm |
| Stem separation | `pip install ".[stems]"` — demucs + torch (large) |
| BespokeSynth | [bespokesynth.com](https://www.bespokesynth.com/) — free |
| Orchestrator | Python 3.11+ + one API key, or Ollama for local |

---

<div align="center">

Built on [BespokeSynth](https://www.bespokesynth.com/) · [FastMCP](https://github.com/jlowin/fastmcp) · Python · Docker

</div>
