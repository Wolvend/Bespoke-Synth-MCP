$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$image = "bespokesynth_mcp-mcp_bespoke_server:latest"

Push-Location $repoRoot
try {
    docker build -f "infra/docker/mcp_bespoke_server.Dockerfile" -t $image .
    Write-Host "Built $image"
} finally {
    Pop-Location
}

