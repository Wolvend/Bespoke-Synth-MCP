$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$image = if ($env:BESPOKESYNTH_MCP_IMAGE) { $env:BESPOKESYNTH_MCP_IMAGE } else { "bespokesynth_mcp-mcp_bespoke_server:latest" }

$cmdHost = if ($env:BESPOKE_CMD_HOST) { $env:BESPOKE_CMD_HOST } else { "host.docker.internal" }
$cmdPort = if ($env:BESPOKE_CMD_PORT) { $env:BESPOKE_CMD_PORT } else { "9001" }
$replyHost = if ($env:REPLY_LISTEN_HOST) { $env:REPLY_LISTEN_HOST } else { "0.0.0.0" }
$replyPort = if ($env:REPLY_LISTEN_PORT) { $env:REPLY_LISTEN_PORT } else { "9002" }
$telemetryHost = if ($env:TELEMETRY_LISTEN_HOST) { $env:TELEMETRY_LISTEN_HOST } else { "0.0.0.0" }
$telemetryPort = if ($env:TELEMETRY_LISTEN_PORT) { $env:TELEMETRY_LISTEN_PORT } else { "9010" }
$knownModules = if ($env:BESPOKE_KNOWN_MODULES) { $env:BESPOKE_KNOWN_MODULES } else { "transport,filter~cutoff,main~volume,snapshots" }
$allowAdminTools = if ($env:ALLOW_ADMIN_TOOLS) { $env:ALLOW_ADMIN_TOOLS } else { "false" }

docker image inspect $image *> $null
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine("Docker image '$image' was not found. Run '.\bespokesynth_mcp\scripts\build_windows_docker_mcp.ps1' first.")
    exit 1
}

$args = @(
    "run",
    "--rm",
    "-i",
    "--name", "bespokesynth_mcp_stdio",
    "-e", "MCP_TRANSPORT=stdio",
    "-e", "BESPOKE_CMD_HOST=$cmdHost",
    "-e", "BESPOKE_CMD_PORT=$cmdPort",
    "-e", "REPLY_LISTEN_HOST=$replyHost",
    "-e", "REPLY_LISTEN_PORT=$replyPort",
    "-e", "TELEMETRY_LISTEN_HOST=$telemetryHost",
    "-e", "TELEMETRY_LISTEN_PORT=$telemetryPort",
    "-e", "BESPOKE_KNOWN_MODULES=$knownModules",
    "-e", "ALLOW_ADMIN_TOOLS=$allowAdminTools",
    "-p", "${replyPort}:${replyPort}/udp",
    "-p", "${telemetryPort}:${telemetryPort}/udp",
    $image,
    "python",
    "-m",
    "mcp_bespoke_server.server"
)

& docker @args
exit $LASTEXITCODE
