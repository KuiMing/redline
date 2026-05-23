# Lobby join room-code UI validation

- total: 5
- passed: 5
- failed: 0

## Checks
- ✅ `room_code_label_mentions_join` — The room-code field label must tell non-host players this is also where they paste a room code.
- ✅ `room_code_placeholder_explains_paste` — Placeholder must explain both paste-to-join and create-room flows.
- ✅ `join_helper_text_visible` — A visible helper line must tell another player to paste the shared code then press enter/join room.
- ✅ `join_room_trims_code` — joinRoom() should trim copied room codes and write the trimmed value back to the field.
- ✅ `join_room_empty_feedback` — Pressing join with an empty field should show clear in-page feedback instead of sending an empty request.
