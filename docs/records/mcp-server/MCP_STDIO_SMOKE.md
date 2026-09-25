# REDLINE MCP server — stdio protocol smoke

Real `python -m mcp_server` subprocess talking MCP-over-stdio to a real REDLINE HTTP+WS server (isolated port, /test/* routes disabled). Rerun: `uv run python scripts/validate/mcp_stdio_smoke.py`

- total: 14 / passed: 14 / failed: 0

## Results
- ✅ `initialize_succeeds`
- ✅ `tool_count_is_32`
- ✅ `rules_resource_listed`
- ✅ `rules_resource_readable`
- ✅ `create_room_ok`
- ✅ `join_room_ok`
- ✅ `start_game_ok`
- ✅ `get_state_ok_and_privacy_scoped`
- ✅ `other_players_hand_redacted`
- ✅ `legal_actions_lists_play_card`
- ✅ `play_card_ok`
- ✅ `advance_turn_ok`
- ✅ `get_card_detail_ok`
- ✅ `get_faction_detail_ok`
