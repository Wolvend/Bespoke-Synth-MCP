# Troubleshooting

## No OSC replies
- Confirm Bespoke loaded the script and is listening on `CMD_PORT`.
- Confirm the `oscout` `oscoutput` module exists and targets the reply port.
- Check local firewall rules for UDP 9001, 9002, and 9010.

## MCP HTTP returns 406
- The client must include `Accept: application/json, text/event-stream`.

## MCP stdio hangs
- Ensure the server logs only to stderr, not stdout.
- Validate the client sends `initialize` before `tools/call`.

## HTTP endpoint does not start remotely
- Confirm `MCP_TRANSPORT=streamable-http`.
- Confirm the port is not already in use.
- If exposing the port outside localhost, use a reverse proxy or tunnel rather than direct public exposure.

## Planner returns invalid JSON
- Use `mock` provider to isolate orchestration issues.
- Tighten the system prompt or switch providers.

## Docs and workflow checks
- Run the CI-equivalent commands from `docs/testing.md`.
- Inspect `.github/workflows` if local behavior differs from CI behavior.
