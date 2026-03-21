# Security

## Defaults
- Admin tools are disabled by default.
- Planner outputs are schema-validated before execution.
- Remote HTTP hardening is expected to happen at a reverse proxy, VPN, or private tunnel layer.

## Policy modes
- `local-only`: local inference only.
- `cloud-ok-no-train`: paid cloud APIs or local models.
- `opt-in`: allow any configured provider.

## Operational guidance
- Keep BespokeSynth off the public internet.
- Prefer localhost binding, a VPN, or a private tunnel for remote use.
- Treat OSC as untrusted input and keep the Bespoke script agent minimal.
- If you expose HTTP remotely, add TLS, authentication, and IP restrictions outside the Python process.
