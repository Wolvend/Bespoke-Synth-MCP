# Architecture

`bespokesynth_mcp` uses a hybrid control architecture.

## Core components
- BespokeSynth patch: owns real-time audio behavior
- Bespoke script agent: receives OSC command envelopes and emits replies
- MCP server: validates tool inputs, sends OSC, waits for replies, captures telemetry
- Orchestrator: plans, validates, requests confirmation, and executes
- Model providers: OpenAI, Anthropic, Gemini, Ollama, or llama.cpp

## Control boundary
- LLMs do not talk to BespokeSynth directly.
- MCP tools are the deterministic execution layer.
- The script agent is the minimal actuator boundary inside the Bespoke patch.

## Data flow
1. A client or orchestrator sends an MCP request.
2. The MCP server validates the tool arguments.
3. The OSC bridge emits `/mcp/cmd` with a JSON envelope.
4. The Bespoke script agent applies the change and sends `/mcp/reply`.
5. Telemetry on `/bespoke/*` can be inspected after execution.
6. The orchestrator records results and can summarize the outcome.

## Deployment modes
- `stdio`: best for local CLIs and desktop workflows
- `streamable-http`: best for remote automation or multi-client access
- `hybrid`: recommended for production, with BespokeSynth local and orchestration local or remote

## Current implementation notes
- The HTTP transport is served directly by the MCP SDK app.
- Auth, TLS, and origin policy should be enforced at a reverse proxy or private tunnel when using remote HTTP access.
