# Docker

## Compose services
- `mcp_bespoke_server`: FastMCP service on port `8000`
- `orchestrator`: FastAPI service on port `8088`

## Behavior
- The MCP service is forced into Streamable HTTP mode in Docker.
- The orchestrator is configured to call `http://mcp_bespoke_server:8000/mcp`.
- Both services have HTTP healthchecks.
- The orchestrator waits until the MCP service is healthy before starting.

## Start
```powershell
docker compose up --build
```

## Detached start
```powershell
docker compose up --build -d
```

## Smoke test
```powershell
python .\scripts\smoke_stack.py
```

## Stop
```powershell
docker compose down
```

