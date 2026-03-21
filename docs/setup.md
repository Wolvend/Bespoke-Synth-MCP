# Setup

## Prerequisites
- Python 3.11 or newer
- BespokeSynth installed separately
- A local network path between the MCP server and BespokeSynth
- Optional: Docker and Docker Compose

## Environment
1. Copy `.env.example` to `.env`.
2. Review these values first:
   - `MCP_TRANSPORT`
   - `BESPOKE_CMD_PORT`
   - `REPLY_LISTEN_PORT`
   - `TELEMETRY_LISTEN_PORT`
   - `POLICY_MODE`
   - provider API keys if you want real model routing

## MCP server install
```powershell
cd services/mcp_bespoke_server
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

## Orchestrator install
```powershell
cd orchestrator
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

## BespokeSynth setup
1. Add a `script` module.
2. Paste in the contents of `examples/bespoke_script_agent.py`.
3. Add an `oscoutput` module named `oscout` pointed at `127.0.0.1:9002`.
4. Add any telemetry `oscoutput` modules you want, pointed at `127.0.0.1:9010`.
5. Confirm that the patch exposes stable parameter paths for the controls you want to automate.

## First run
### MCP stdio
```powershell
cd services/mcp_bespoke_server
python -m mcp_bespoke_server.server
```

### MCP HTTP
```powershell
cd services/mcp_bespoke_server
$env:MCP_TRANSPORT="streamable-http"
python -m mcp_bespoke_server.server
```

### Orchestrator
```powershell
cd orchestrator
python -m orchestrator.api
```

### Docker stack
```powershell
docker compose up --build
```

In Docker, the MCP server is forced to Streamable HTTP on port `8000`, and the orchestrator is preconfigured to call `http://mcp_bespoke_server:8000/mcp`.
