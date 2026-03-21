# Release Checklist

Before handing off or tagging a release:

1. Run `scripts/test_all.ps1`
2. Run `docker compose config`
3. Build both Docker images
4. Verify the Bespoke patch still matches the documented OSC ports
5. Confirm README links and docs links render correctly
6. Confirm sample MCP client configs still match current startup commands
7. If using remote HTTP access, confirm reverse proxy or tunnel auth is in place

