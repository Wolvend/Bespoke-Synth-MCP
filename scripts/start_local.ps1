$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

param(
    [ValidateSet("stdio", "http")]
    [string]$McpTransport = "stdio"
)

Write-Host "Starting MCP server with transport: $McpTransport"
$mcpJob = Start-Job -ScriptBlock {
    param($transport, $root)
    Set-Location (Join-Path $root "services/mcp_bespoke_server")
    $env:MCP_TRANSPORT = $transport
    python -m mcp_bespoke_server.server
} -ArgumentList $McpTransport, $repoRoot

Write-Host "Starting orchestrator"
$orchJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location (Join-Path $root "orchestrator")
    python -m orchestrator.api
} -ArgumentList $repoRoot

Write-Host "MCP job id: $($mcpJob.Id)"
Write-Host "Orchestrator job id: $($orchJob.Id)"
Write-Host "Use Get-Job / Receive-Job / Stop-Job to manage them."
