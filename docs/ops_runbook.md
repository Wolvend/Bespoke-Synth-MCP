# Ops Runbook

## Start stack
```powershell
docker compose up --build
```

Docker starts the MCP service in Streamable HTTP mode on port `8000` and points the orchestrator at that internal service URL automatically.

## Local start
```powershell
cd services/mcp_bespoke_server
pip install -e .[dev]
python -m mcp_bespoke_server.server
```

```powershell
cd orchestrator
pip install -e .[dev]
python -m orchestrator.api
```

## Health checks
- MCP HTTP: `GET /mcp` is transport-dependent; validate with MCP `initialize`
- Orchestrator: `GET /health`
- Telemetry: `GET /telemetry`

## Useful commands
```powershell
cd services/mcp_bespoke_server
python -m ruff check src tests
python -m mypy src
python -m pytest
```

```powershell
cd orchestrator
python -m ruff check src tests
python -m mypy src
python -m pytest
```

## Common env changes
- `MCP_TRANSPORT=streamable-http`
- `ALLOW_ADMIN_TOOLS=true`
- `POLICY_MODE=local-only`

## Remote access recommendation
Expose the HTTP MCP endpoint only behind a trusted reverse proxy or tunnel. The current app does not terminate TLS or enforce auth itself.
