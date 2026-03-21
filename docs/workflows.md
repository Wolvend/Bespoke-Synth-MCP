# Workflows

This repo ships with two GitHub Actions workflows.

## `ci.yml`
Runs on every push and pull request.

It performs:
- package install for `services/mcp_bespoke_server`
- package install for `orchestrator`
- `ruff`
- `mypy`
- `pytest`
- Docker image builds for both services
- verifies both Python packages remain buildable in CI

Use this workflow as the required branch protection check.

## `nightly-smoke.yml`
Runs on a daily schedule and can also be triggered manually.

It performs:
- package install for both Python packages
- test execution for both packages

Use this workflow to catch dependency drift and breakage that may not show up during active development.
