# 戰略地圖連線中斷後重連 UI Validation

- 結果：**7/7 passed**
- 情境：打出組織經驗丙 → 兩條 WebSocket 同時斷線 → 地圖自動重連 → 點選廈門 → 按建立組織。
- 回歸重點：修好前地圖 socket 斷線後永不重連，按鈕仍亮著但按下去靜默失效。

## Checks
- PASS `xiamen_is_a_legal_card_build_candidate`
- PASS `strategic_map_socket_reconnects_after_a_drop`
- PASS `build_button_arms_for_xiamen_after_reconnect`
- PASS `authoritative_state_shows_the_organization_in_xiamen`
- PASS `card_is_committed_to_discard_and_choice_clears`
- PASS `reconnected_map_iframe_also_sees_the_new_organization`
- PASS `browser_console_has_no_errors`

## Screenshots
- `docs/records/map-ui/socket-reconnect/map-socket-reconnect-xiamen-armed.png`
- `docs/records/map-ui/socket-reconnect/map-socket-reconnect-xiamen-built.png`
