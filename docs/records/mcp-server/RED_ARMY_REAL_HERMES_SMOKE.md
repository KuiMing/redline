# REDLINE automatic Red Army — real Hermes smoke

A real isolated Docker Compose game/MCP stack was used with the dedicated `redarmy` Hermes profile and the `mcp-redline` toolset. A human smoke seat completed its turn through legal MCP actions. The controller then invoked the real Hermes Agent without a manual turn message. Hermes completed the Red Army turn and handed control back.

The controller captured and discarded Hermes stdout/stderr. This record contains no runtime game ID, player ID, resume token, hand data, or model response.

- total: 3 / passed: 3 / failed: 0

- ✅ `dedicated_hermes_profile_loads_only_mcp_redline_toolset`
- ✅ `controller_invokes_real_hermes_agent_without_manual_turn_trigger`
- ✅ `real_hermes_agent_completes_red_army_turn_handoff`
