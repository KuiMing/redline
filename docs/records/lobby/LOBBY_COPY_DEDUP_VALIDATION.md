# Lobby room-code copy dedup validation

- game_id: 94597400-36b7-49df-8fc8-9660851b9a41
- total: 5
- passed: 5
- failed: 0
- screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/lobby/lobby_copy_dedup_validation.png

## Results
- ✅ `banner_copy_button_removed` — {}
- ✅ `banner_code_is_non_interactive_display` — {"present": true, "tag": "span", "hasOnclick": false}
- ✅ `banner_still_displays_room_code` — {"banner_text": "94597400-36b7-49df-8fc8-9660851b9a41", "game_id": "94597400-36b7-49df-8fc8-9660851b9a41"}
- ✅ `exactly_one_copy_button_remains` — {"remaining_copy_buttons": ["copyRoomBtn"]}
- ✅ `remaining_copy_button_still_copies_room_code` — {"ok": true, "method": "execCommand", "value": "94597400-36b7-49df-8fc8-9660851b9a41"}
