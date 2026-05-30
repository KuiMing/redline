# Lobby join room-code UI validation

- total: 13
- passed: 13
- failed: 0

## Checks
- ✅ `room_code_label_mentions_join` — The room-code field label must tell non-host players this is also where they paste a room code.
- ✅ `room_code_placeholder_explains_paste` — Placeholder must explain both paste-to-join and create-room flows.
- ✅ `join_helper_text_visible` — A visible helper line must tell another player to paste the shared code then press enter/join room.
- ✅ `join_room_trims_code` — joinRoom() should trim copied room codes and write the trimmed value back to the field.
- ✅ `join_room_empty_feedback` — Pressing join with an empty field should show clear in-page feedback instead of sending an empty request.
- ✅ `top_banner_exists_after_room_created` — Lobby must include a top room-code banner so the created room code stays visible above faction selection.
- ✅ `top_banner_syncs_from_game_id` — The banner must sync from the active game id and toggle lobby room-active spacing when a room exists.
- ✅ `copy_fallback_selects_room_code` — If automatic copy is blocked, fallback should select the full room code and give explicit manual-copy instructions.
- ✅ `copy_uses_exec_command_before_clipboard_api` — Copy should first use a click-gesture execCommand path so LAN/http browsers can copy even when navigator.clipboard is unavailable.
- ✅ `copy_records_runtime_result_for_browser_proof` — Browser proof can inspect the last copy result to distinguish real automatic copy from manual-select fallback.
- ✅ `copy_status_survives_lobby_sync` — The copied/manual-select status should stay visible instead of being overwritten by the lobby polling refresh.
- ✅ `banner_is_top_sticky_not_covering_actions` — The banner must be placed at the top of the lobby and reserve visual space instead of overlapping faction/action controls.
- ✅ `confirm_faction_bar_remains_clickable` — Long faction details should keep the confirm-faction button sticky inside the faction panel instead of under the fixed action bar.
