# API

## MCP server

### HTTP endpoint
- Base path: `/mcp`
- Transport: Streamable HTTP
- Required request header: `Accept: application/json, text/event-stream`

### Typical flow
1. `initialize`
2. `notifications/initialized`
3. `tools/list` or `tools/call`

### Example `initialize`
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-03-26",
    "capabilities": {},
    "clientInfo": {
      "name": "example-client",
      "version": "0.1.0"
    }
  }
}
```

### Example `tools/call`
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "bespoke.safe.set_param",
    "arguments": {
      "path": "filter~cutoff",
      "value": 0.25,
      "idempotency_key": "demo-1"
    }
  }
}
```

## Tool reference

All tools are called via `tools/call` with `"name"` and `"arguments"`.

### `bespoke.safe.health`
No arguments. Returns `{ok, ts_ms, server}`.

### `bespoke.safe.list_modules`
| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `prefix` | string | null | Filter module names by prefix |

### `bespoke.safe.get_param`
| Argument | Type | Description |
|----------|------|-------------|
| `path` | string | Module parameter path, e.g. `"filter~cutoff"` |

### `bespoke.safe.set_param`
| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `path` | string | — | Parameter path |
| `value` | number/string/bool | — | New value |
| `mode` | `"immediate"` \| `"ramp"` | `"immediate"` | Apply mode |
| `ramp_ms` | int | `0` | Ramp duration in ms |

### `bespoke.safe.batch_set_params`
| Argument | Type | Description |
|----------|------|-------------|
| `ops` | array | Up to 500 `{path, value, at_ms?}` objects |

### `bespoke.safe.automate`
Ramp or sequence a parameter over time.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `path` | string | — | Parameter path |
| `start_value` | float | null | Ramp start (ramp mode) |
| `end_value` | float | null | Ramp end (ramp mode) |
| `duration_ms` | int | null | Total ramp duration |
| `steps` | int | `16` | Interpolation steps |
| `curve` | `"linear"` \| `"exp"` \| `"log"` | `"linear"` | Interpolation curve |
| `points` | array | null | Explicit `{value, at_ms}` list (alternative to ramp mode) |

### `bespoke.safe.play_note`
| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `label` | string | — | Human-readable note label |
| `pitch` | int 0-127 | — | MIDI pitch |
| `velocity` | int 0-127 | — | MIDI velocity |
| `duration_ms` | int | `250` | Note duration |

### `bespoke.safe.schedule_notes`
| Argument | Type | Description |
|----------|------|-------------|
| `notes` | array | Up to 256 `{label, pitch, velocity, at_ms, duration_ms}` objects |

### `bespoke.safe.transport_set`
| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `playing` | bool | — | Start (`true`) or stop (`false`) |
| `bpm` | float | null | Set tempo (optional) |
| `beat` | int | null | Jump to beat position (optional) |

### `bespoke.safe.snapshot_load`
| Argument | Type | Description |
|----------|------|-------------|
| `name` | string | Snapshot name to load |

### `bespoke.safe.telemetry_last`
| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `limit` | int | `20` | Max items to return (1-200) |
| `prefix` | string | null | Filter by OSC address prefix |

### `bespoke.admin.raw_command`
Disabled by default. Set `ALLOW_ADMIN_TOOLS=true` to enable.

| Argument | Type | Description |
|----------|------|-------------|
| `op` | string | OSC op string |
| `payload` | object | Additional key/value pairs merged into the envelope |

---

### `bespoke.theory.info`
No arguments. Returns lists of supported modes and chord types.

### `bespoke.theory.scale`
| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `root` | string | — | Root note: `"C"`, `"F#"`, `"Bb"`, etc. |
| `mode` | string | `"major"` | Scale mode |
| `octave` | int | `4` | Starting octave |
| `num_octaves` | int | `1` | How many octaves to return (1-4) |

### `bespoke.theory.chord`
| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `root` | string | — | Root note |
| `chord_type` | string | `"maj"` | Chord quality |
| `octave` | int | `4` | Root octave |
| `inversion` | int | `0` | Inversion (0=root position) |

### `bespoke.theory.transpose`
| Argument | Type | Description |
|----------|------|-------------|
| `notes` | array | List of `{name, midi, freq_hz}` dicts |
| `semitones` | int | Semitones to shift (positive=up, negative=down, range ±48) |

### `bespoke.theory.quantize`
Snap a free frequency to the nearest scale degree.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `freq_hz` | float | — | Input frequency in Hz |
| `root` | string | — | Scale root note |
| `mode` | string | `"major"` | Scale mode |

Returns `{input_freq_hz, quantized: {name, midi, freq_hz}, cents_deviation}`.

### `bespoke.theory.progression`
Generate a chord progression from Roman numeral notation.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `root` | string | — | Root note |
| `mode` | string | `"major"` | Diatonic mode (7-degree modes only) |
| `pattern` | string | `"I-IV-V-I"` | Dash-separated Roman numerals |
| `octave` | int | `4` | Chord voicing octave |

Returns `{chords: [{degree, roman, root, type, notes}]}`.

### `bespoke.theory.arpeggiate`
Expand a chord into a timed note sequence ready for `bespoke.safe.schedule_notes`.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `root` | string | — | Root note |
| `chord_type` | string | `"maj"` | Chord quality |
| `octave` | int | `4` | Root octave |
| `pattern` | `"up"` \| `"down"` \| `"updown"` \| `"random"` | `"up"` | Sequence pattern |
| `subdivision` | `"8th"` \| `"16th"` \| `"triplet"` | `"16th"` | Note grid |
| `bpm` | float | `120.0` | Tempo used to calculate timing |
| `bars` | int | `1` | Number of bars (4/4 time) |
| `velocity` | int | `100` | MIDI velocity |

---

### `bespoke.compose.list_presets`
No arguments. Returns list of preset summaries.

### `bespoke.compose.get_preset`
| Argument | Type | Description |
|----------|------|-------------|
| `name` | string | Preset name (without `.json`) |

### `bespoke.compose.save_preset`
| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `name` | string | — | Preset name (alphanumeric, hyphens, underscores) |
| `bpm` | float | — | Tempo |
| `steps` | array | — | List of `{preset, duration_ms, delay_ms?, velocity?}` |
| `description` | string | `""` | Human-readable description |

### `bespoke.compose.render_workflow`
| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `name` | string | — | Preset name to render |
| `dry_run` | bool | `false` | Validate only, do not write audio |

### `bespoke.compose.list_tracks`
| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `limit` | int | `20` | Max tracks to return |

### `bespoke.compose.delete_track`
| Argument | Type | Description |
|----------|------|-------------|
| `file` | string | Filename only (e.g. `"track_20260320.mp3"`) — no path separators |

### `bespoke.compose.tag_track`
| Argument | Type | Description |
|----------|------|-------------|
| `file` | string | Filename only |
| `tags` | object | Key/value pairs to merge into the companion JSON |

### `compose.export_midi`
Export a workflow preset or explicit note list to a MIDI file. Requires `mido`.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `name` | string | null | Preset name (mode 1) |
| `notes` | array | null | `{pitch, velocity, at_ms, duration_ms}` list (mode 2) |
| `bpm` | float | `120.0` | Tempo for tick calculation |
| `filename` | string | null | Output filename (auto-generated if omitted) |

Provide `name` **or** `notes`, not both.

---

### `audio.analyze`
Analyze an audio file for BPM, key, and loudness. Requires scipy + pydub; pyloudnorm + soundfile for LUFS.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `file` | string | — | Filename in `tracks/` dir or absolute path |
| `analyze_bpm` | bool | `true` | Detect tempo |
| `analyze_key` | bool | `true` | Detect musical key |
| `analyze_loudness` | bool | `true` | Measure LUFS |

Returns `{bpm, bpm_confidence, key, key_confidence, loudness_lufs, duration_s}`.

### `audio.stems`
Separate an audio file into instrument stems using demucs. Requires demucs + torch + torchaudio.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `file` | string | — | Filename in `tracks/` dir or absolute path |
| `stems` | array | all four | Subset of `["vocals", "drums", "bass", "other"]` |

Returns `{stems: {name: path}}` with absolute paths to WAV files under `tracks/stems/<trackname>/`.
Downloads ~2 GB htdemucs model on first call. Slow on CPU.

---

## Orchestrator

### `GET /health`
Returns orchestrator health and current policy mode.

### `POST /plan`
Accepts:
```json
{
  "user_text": "set cutoff to 0.25",
  "provider": "mock"
}
```

Returns a validated execution plan.

### `POST /execute`
Accepts a validated plan plus `confirmed`.

### `POST /chat`
Combines plan generation and execution. If confirmation is required and not provided, the response includes `status: confirmation_required`.

### `GET /telemetry`
Returns the orchestrator-side execution history buffer.

