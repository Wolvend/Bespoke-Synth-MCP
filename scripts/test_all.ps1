$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "Running MCP server checks..."
Push-Location (Join-Path $repoRoot "services/mcp_bespoke_server")
python -m pip install -e .[dev]
python -m ruff check src tests
python -m mypy src
python -m pytest
Pop-Location

Write-Host "Running orchestrator checks..."
Push-Location (Join-Path $repoRoot "orchestrator")
python -m pip install -e .[dev]
python -m ruff check src tests
python -m mypy src
python -m pytest
Pop-Location

Write-Host "Rendering docker-compose config..."
Push-Location $repoRoot
docker compose config | Out-Null
Pop-Location

Write-Host "All checks completed."
