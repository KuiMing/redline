# REDLINE MCP server — Streamable HTTP protocol smoke

Real `python -m mcp_server --transport streamable-http` subprocess on a real socket, talking real MCP-over-HTTP to a real REDLINE HTTP+WS server (isolated ports, /test/* routes disabled). No room/game is created (see module docstring), so there is no per-run credential/id content to redact. Rerun: `uv run python scripts/validate/mcp_streamable_http_smoke.py`

- total: 8 / passed: 8 / failed: 0

## Results
- ✅ `health_endpoint_ok_without_any_game_backend_dependency`
- ✅ `dns_rebinding_protection_rejects_spoofed_host_header`
- ✅ `dns_rebinding_protection_rejects_spoofed_origin_header`
- ✅ `initialize_succeeds`
- ✅ `tool_count_is_32`
- ✅ `rules_resource_listed`
- ✅ `get_rules_text_ok`
- ✅ `list_factions_reaches_real_redline_server`
