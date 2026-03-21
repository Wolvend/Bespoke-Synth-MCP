# Windows Docker MCP

This is the recommended way to use `bespokesynth_mcp` from a Windows MCP client when BespokeSynth is running on the Windows host.

## Why this works
- The MCP server runs inside a Docker container.
- OSC commands go from the container to Windows via `host.docker.internal`.
- OSC replies and telemetry come back through published UDP ports on the host.
- Your MCP client talks to the container over stdio through `docker run -i`.

## One-time build
```powershell
.\bespokesynth_mcp\scripts\build_windows_docker_mcp.ps1
```

## Root MCP config
The workspace root `.mcp.json` includes a `bespokesynth_mcp_docker` entry that launches:
- `powershell`
- `.\bespokesynth_mcp\scripts\run_docker_stdio.ps1`

## Bespoke patch settings
- Script agent listens on `9001`
- `oscout` reply module targets `127.0.0.1:9002`
- Telemetry modules target `127.0.0.1:9010`

## Defaults used by the launcher
- `BESPOKE_CMD_HOST=host.docker.internal`
- `BESPOKE_CMD_PORT=9001`
- `REPLY_LISTEN_HOST=0.0.0.0`
- `REPLY_LISTEN_PORT=9002`
- `TELEMETRY_LISTEN_HOST=0.0.0.0`
- `TELEMETRY_LISTEN_PORT=9010`

## Notes
- Build the image once before using the MCP client entry.
- Keep Docker Desktop running.
- Keep BespokeSynth on the Windows host, not inside the container.

