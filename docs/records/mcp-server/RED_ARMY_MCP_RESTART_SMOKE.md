# REDLINE Red Army controller — MCP restart smoke

An isolated Docker Compose stack creates a Red Army seat, restarts only `redline-mcp`, and resumes through the new MCP process while the game process remains alive. No model or `/test/*` route is used. Proof contains no runtime identifiers.

- total: 7 / passed: 7 / failed: 0

- ✅ `compose_build_succeeds`
- ✅ `compose_up_succeeds`
- ✅ `mcp_becomes_healthy`
- ✅ `mcp_container_restart_succeeds`
- ✅ `restarted_mcp_becomes_healthy`
- ✅ `controller_resumes_seat_after_mcp_process_restart`
- ✅ `compose_down_succeeds`
