# Lobby room-code copy dedup validation

- game_id: 00e4038e-e1d4-4e76-9262-791d9dbbf42f
- total: 5
- passed: 5
- failed: 0
- screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/lobby/lobby_copy_dedup_validation.png

## Results
- ✅ `top_room_code_banner_fully_removed` — {}
- ✅ `exactly_one_copy_button_remains` — {"remaining_copy_buttons": ["copyRoomBtn"]}
- ✅ `room_code_input_shows_the_code` — {"room_input_value": "00e4038e-e1d4-4e76-9262-791d9dbbf42f", "game_id": "00e4038e-e1d4-4e76-9262-791d9dbbf42f"}
- ✅ `no_other_element_repeats_the_room_code_as_text` — {"other_visible_room_code_text": []}
- ✅ `remaining_copy_button_still_copies_room_code` — {"ok": true, "method": "execCommand", "value": "00e4038e-e1d4-4e76-9262-791d9dbbf42f"}
