# CLI Clients

## Supported patterns
- `stdio`: recommended for local desktop MCP clients
- Streamable HTTP: recommended for remote or multi-client access

## Claude Code or Claude Desktop
Use the sample config in [examples/client-configs/claude-code.mcp.json](../examples/client-configs/claude-code.mcp.json) or [.mcp.json.example](../.mcp.json.example).

## Cursor
Use [examples/client-configs/cursor-http.json](../examples/client-configs/cursor-http.json) when Cursor is configured for HTTP MCP access.

## VS Code
Use [examples/client-configs/vscode-stdio.json](../examples/client-configs/vscode-stdio.json) for local stdio usage.

## Custom client requirements
Your client should:
1. Send `initialize`
2. Send `notifications/initialized`
3. Call `tools/list` or `tools/call`
4. Use `Accept: application/json, text/event-stream` for HTTP transport

## Remote access guidance
If you expose the HTTP endpoint remotely:
- terminate TLS at a reverse proxy
- add authentication at the proxy or tunnel layer
- restrict network access to trusted callers
