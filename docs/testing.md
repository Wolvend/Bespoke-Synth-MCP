# Testing

## Server package
```powershell
cd services/mcp_bespoke_server
python -m ruff check src tests
python -m mypy src
python -m pytest
```

## Orchestrator package
```powershell
cd orchestrator
python -m ruff check src tests
python -m mypy src
python -m pytest
```

## Notes
- The server suite includes HTTP smoke coverage and OSC bridge tests.
- The stdio subprocess smoke test is skipped on Windows because of shell-level flakiness.
- The orchestrator suite uses a dummy MCP client for fast end-to-end validation.
- The root helper script `scripts/test_all.ps1` runs the full local validation path.
