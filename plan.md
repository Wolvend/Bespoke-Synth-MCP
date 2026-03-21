# plan.md — Production MCP Platform: BespokeSynth + FastMCP + Multi-Model Orchestration
## Purpose
Build a production-ready multi-component platform that:
- Controls and observes BespokeSynth in real time via OSC and Bespoke’s scripting APIs.
- Exposes a safe, deterministic FastMCP tool surface for MCP clients and CLIs.
- Adds an orchestrator that routes planning and summarization across OpenAI, Anthropic, Gemini, Ollama, and llama.cpp under explicit privacy and consent policies.
- Ships with tests, CI, container artifacts, and operational documentation.

## Deliverables
- `services/mcp_bespoke_server`: FastMCP server with stdio and Streamable HTTP transports.
- `orchestrator`: FastAPI service with plan/execute/chat endpoints and multi-provider routing.
- `examples/bespoke_script_agent.py`: BespokeSynth script module snippet for OSC command execution and reply/telemetry.
- `examples/client-configs`: sample MCP client config for common CLIs.
- `docs`: architecture, security, ops, and troubleshooting guides.

## Assumptions
- Default deployment is hybrid: BespokeSynth stays on-prem, orchestration may run local or remote.
- Target concurrency is 1–10 interactive sessions with short bursts above that.
- Safe tools are enabled by default; admin tools are disabled unless explicitly allowed.
- OSC communication is UDP and therefore replay-safe behavior requires idempotency keys.
- BespokeSynth is not bundled or redistributed by this repo.

## Implementation priorities
1. Reliable OSC round-trip with correlation, timeout handling, and telemetry capture.
2. Strong schemas around tool inputs and planner outputs.
3. CLI compatibility through stdio plus optional Streamable HTTP `/mcp`.
4. Policy-based model routing with privacy modes and consent gates.
5. Tests that validate MCP lifecycle, tool calls, and mock Bespoke integration.

## MCP requirements
- Implement `initialize`, `notifications/initialized`, `tools/list`, and `tools/call` through the official MCP SDK.
- Support stdio for local clients and Streamable HTTP for remote/multi-client use.
- Keep stdout protocol-clean in stdio mode.
- Handle remote HTTP hardening through a reverse proxy or trusted tunnel when exposing the endpoint outside localhost.

## BespokeSynth contract
- Bespoke script listens for `/mcp/cmd` on a configured port.
- The first argument is a JSON envelope with `op`, operation-specific fields, and `idempotency_key`.
- Reply channel uses `/mcp/reply` with JSON payload.
- Telemetry uses `/bespoke/<label>` from Bespoke `oscoutput`.

## Tool surface
- `bespoke.safe.health`
- `bespoke.safe.list_modules`
- `bespoke.safe.get_param`
- `bespoke.safe.set_param`
- `bespoke.safe.batch_set_params`
- `bespoke.safe.play_note`
- `bespoke.safe.schedule_notes`
- `bespoke.safe.transport_set`
- `bespoke.safe.snapshot_load`
- `bespoke.safe.telemetry_last`
- `bespoke.admin.raw_command`

## Orchestrator modes
- `local-only`: only Ollama or llama.cpp.
- `cloud-ok-no-train`: paid cloud APIs or local providers.
- `opt-in`: any configured provider.

## Verification targets
- Unit tests for schemas, cache, routing, and policy decisions.
- Integration tests for MCP stdio and HTTP using a mock Bespoke OSC agent.
- Manual validation against a real Bespoke patch using the provided script snippet.

## Success criteria
- MCP tools callable from local CLI clients over stdio.
- MCP tools callable from HTTP clients over `/mcp`.
- Idempotent repeated commands do not replay into Bespoke.
- Orchestrator can return plans, enforce confirmation rules, and execute approved plans.
- Docs are sufficient for local setup, Docker deployment, and client integration.
