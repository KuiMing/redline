# REDLINE MCP server — Docker Compose stack smoke

Real `docker compose build` + `up -d` + teardown of docker-compose.yml, using an isolated project name and isolated free host ports (never the production 8000 port or an existing container). This proves the test stack starts and the MCP service can reach `redline` over the Compose-internal network — it does NOT mean anything was deployed. Rerun: `uv run python scripts/validate/mcp_docker_compose_smoke.py` (needs Docker; a few minutes).

- total: 6 / passed: 6 / failed: 0

## Results
- ✅ `docker_compose_build_succeeds`
- ✅ `docker_compose_up_succeeds`
- ✅ `redline_service_becomes_healthy`
- ✅ `mcp_service_becomes_healthy`
- ✅ `mcp_tool_call_reaches_redline_over_compose_internal_network`
- ✅ `docker_compose_down_succeeds`
