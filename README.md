# bespokesynth_mcp

`bespokesynth_mcp` is a production-oriented MCP platform for controlling BespokeSynth over OSC while exposing a FastMCP server and a separate orchestration layer for local and cloud models.

## Status
- 44 MCP tools across OSC control, music theory, composition, and audio analysis
- FastMCP server with `stdio` and Streamable HTTP support
- OSC command bridge with correlation, reply handling, and telemetry capture
- Safe and admin tool namespaces
- Orchestrator API with planner validation, privacy modes, and consent gating
- Docker, tests, docs, sample client configs, and GitHub Actions workflows

## Repository layout
- `services/mcp_bespoke_server`: MCP tool server
- `orchestrator`: planner, executor, and provider router
- `examples`: Bespoke script agent and client config examples
- `docs`: setup, architecture, security, ops, CLI integration, and testing docs
- `scripts`: local helper scripts for validation and startup
- `.github/workflows`: CI and nightly validation

## What works today
- MCP `initialize`, `tools/list`, and `tools/call`
- `stdio` operation for local MCP clients
- Streamable HTTP at `/mcp`
- Safe tools for health, params, batches, notes, transport, snapshots, and telemetry
- Mock-provider orchestration for end-to-end testing
- Provider adapters for OpenAI, Anthropic, Gemini, Ollama, and llama.cpp

## Quick start
1. Copy [.env.example](./.env.example) to `.env`.
2. Follow [docs/setup.md](./docs/setup.md).
3. Load [examples/bespoke_script_agent.py](./examples/bespoke_script_agent.py) into a Bespoke `script` module.
4. Create an `oscoutput` module named `oscout` in Bespoke for replies.
5. Start the MCP server and, if needed, the orchestrator.
6. Point your MCP client at the example config in [examples/client-configs](./examples/client-configs).

## Local development
### MCP server
```powershell
cd services/mcp_bespoke_server
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python -m mcp_bespoke_server.server
```

### MCP server over HTTP
```powershell
cd services/mcp_bespoke_server
$env:MCP_TRANSPORT="streamable-http"
python -m mcp_bespoke_server.server
```

### Orchestrator
```powershell
cd orchestrator
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python -m orchestrator.api
```

## Bespoke patch requirements
- A `script` module running the code from [examples/bespoke_script_agent.py](./examples/bespoke_script_agent.py)
- An `oscoutput` module named `oscout` targeting UDP port `9002`
- Optional `oscoutput` modules for `/bespoke/*` telemetry to port `9010`
- Parameter paths in your patch that match the tool calls you intend to send

## Client compatibility
This repo is designed for MCP-aware CLIs that support either stdio or Streamable HTTP.

- Claude Code and Claude Desktop: stdio is the simplest path
- Cursor and VS Code MCP clients: use stdio or HTTP depending on client support
- OpenCode-style and custom CLIs: use stdio or JSON-RPC over HTTP
- Sample configs: [examples/client-configs](./examples/client-configs)
- Generic MCP config: [.mcp.json.example](./.mcp.json.example)

## Tool summary (44 tools)

### OSC / synth control
- `bespoke.safe.health` — ping the server
- `bespoke.safe.list_modules` — list known BespokeSynth modules
- `bespoke.safe.get_param` — read a module parameter
- `bespoke.safe.set_param` — write a module parameter (immediate or ramp)
- `bespoke.safe.batch_set_params` — write up to 500 parameters in one call
- `bespoke.safe.automate` — ramp or explicitly sequence a parameter over time
- `bespoke.safe.play_note` — play a single MIDI note
- `bespoke.safe.schedule_notes` — schedule up to 256 timed MIDI notes
- `bespoke.safe.transport_set` — start/stop and set BPM and beat position
- `bespoke.safe.snapshot_load` — load a named BespokeSynth snapshot
- `bespoke.safe.telemetry_last` — retrieve recent OSC telemetry events
- `bespoke.admin.raw_command` — send arbitrary OSC ops (disabled by default)

### Music theory
- `bespoke.theory.info` — list all available scale modes and chord types
- `bespoke.theory.scale` — return notes in a scale with MIDI + frequency
- `bespoke.theory.chord` — return notes in a chord voicing with MIDI + frequency
- `bespoke.theory.transpose` — shift a note list up or down by semitones
- `bespoke.theory.quantize` — snap a free frequency to the nearest scale degree
- `bespoke.theory.progression` — build a chord progression from Roman numerals (e.g. I-IV-V-I)
- `bespoke.theory.arpeggiate` — expand a chord into a timed note sequence for schedule_notes

### Composition and track management
- `bespoke.compose.list_presets` — list saved workflow presets
- `bespoke.compose.get_preset` — inspect a preset's full step definition
- `bespoke.compose.save_preset` — save a new workflow preset to disk
- `bespoke.compose.render_workflow` — render a preset to MP3
- `bespoke.compose.list_tracks` — list generated tracks with metadata
- `bespoke.compose.delete_track` — delete an MP3 and its companion JSON
- `bespoke.compose.tag_track` — merge metadata tags into a track's JSON
- `compose.export_midi` — export a preset or note list to a MIDI file

### Audio analysis
- `audio.analyze` — detect BPM, musical key, and integrated loudness (LUFS) from an audio file
- `audio.stems` — separate a track into vocals/drums/bass/other stems via demucs

## Security notes
- Admin tools are disabled by default.
- The current server implementation does not terminate TLS or enforce bearer auth itself.
- For remote HTTP access, put the MCP endpoint behind a reverse proxy or tunnel that handles auth, TLS, and origin policy.
- BespokeSynth should remain on a trusted local network or private host.

## Docker
```powershell
docker compose up --build
```

`docker compose` forces the MCP service into Streamable HTTP mode and wires the orchestrator to it automatically.

## Testing
```powershell
.\scripts\test_all.ps1
```

## Docs map
- [docs/README.md](./docs/README.md)
- [docs/api.md](./docs/api.md)
- [docs/setup.md](./docs/setup.md)
- [docs/docker.md](./docs/docker.md)
- [docs/windows_docker_mcp.md](./docs/windows_docker_mcp.md)
- [docs/cli_clients.md](./docs/cli_clients.md)
- [docs/architecture.md](./docs/architecture.md)
- [docs/security.md](./docs/security.md)
- [docs/ops_runbook.md](./docs/ops_runbook.md)
- [docs/release_checklist.md](./docs/release_checklist.md)
- [docs/workflows.md](./docs/workflows.md)
- [docs/testing.md](./docs/testing.md)
- [docs/troubleshooting.md](./docs/troubleshooting.md)

## References
- MCP specification: https://modelcontextprotocol.io/specification/2025-03-26
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- BespokeSynth docs: https://www.bespokesynth.com/docs/
- Ollama docs: https://docs.ollama.com/
- llama.cpp server README: https://github.com/ggml-org/llama.cpp
