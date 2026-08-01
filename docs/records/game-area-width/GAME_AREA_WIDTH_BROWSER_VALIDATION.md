# 遊戲區域寬度 Browser Validation

- 結果：**20/20 passed**
- 正式端點：`http://127.0.0.1:8000`
- 目標欄寬：常設 284px／隨機 474px／手牌 474px（依舞台縮放同比例）。

## 1280x720

- PASS `static_panel_is_narrower_than_wide_panels`
- PASS `columns_match_target_distribution`
- PASS `all_cards_inside_panel_bounds`
- PASS `no_zone_horizontal_overflow`
- PASS `hand_controls_inside_cards`
- PASS `no_document_horizontal_overflow`
- PASS `command_grid_inside_viewport`
- PASS `all_panels_inside_viewport`
- PASS `expected_card_inventory_visible`
- PASS `browser_console_has_no_errors`

- panel widths：`284.00` / `474.00` / `474.00`
- `purchaseStatic` client/scroll：`266/266`
- `purchaseRandom` client/scroll：`456/456`
- `hand` client/scroll：`456/456`

## 1024x768

- PASS `static_panel_is_narrower_than_wide_panels`
- PASS `columns_match_target_distribution`
- PASS `all_cards_inside_panel_bounds`
- PASS `no_zone_horizontal_overflow`
- PASS `hand_controls_inside_cards`
- PASS `no_document_horizontal_overflow`
- PASS `command_grid_inside_viewport`
- PASS `all_panels_inside_viewport`
- PASS `expected_card_inventory_visible`
- PASS `browser_console_has_no_errors`

- panel widths：`227.20` / `379.20` / `379.20`
- `purchaseStatic` client/scroll：`266/266`
- `purchaseRandom` client/scroll：`456/456`
- `hand` client/scroll：`456/456`

## Screenshots

- `docs/records/game-area-width/game-area-width-1280x720.png`
- `docs/records/game-area-width/game-area-width-1024x768.png`
