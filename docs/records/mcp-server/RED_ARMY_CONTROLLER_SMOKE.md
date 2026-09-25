# REDLINE automatic Red Army controller smoke

Real Docker game server + Streamable HTTP MCP + host controller. The Agent is deterministic and fake, so no model token is used. No `/test/*` route is enabled or called. Proof contains no runtime game/player identifiers.

- total: 7 / passed: 7 / failed: 0

- ✅ `creates_and_selects_red_army`
- ✅ `credential_file_is_0600`
- ✅ `auto_starts_when_all_seats_ready`
- ✅ `automatically_invokes_agent_for_red_army`
- ✅ `fake_agent_completes_red_army_handoff`
- ✅ `resume_token_never_enters_agent_prompt`
- ✅ `controller_restart_rehydrates_seat`
