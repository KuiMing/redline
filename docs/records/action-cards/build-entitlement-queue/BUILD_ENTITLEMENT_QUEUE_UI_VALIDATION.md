# 多張建立牌累積結算 UI Validation

- 結果：**10/10 passed**
- 正式流程：先在指揮中心依序打出組織經驗丙、組織經驗乙，再由正式Leaflet地圖連續建立3次。
- 驗證：第二張按鈕在首張pending期間仍可用；剩餘數1→3→2→1→0；每次重新投影合法城鎮。

## Checks
- PASS `fixture_has_two_different_build_cards`
- PASS `first_build_card_keeps_formal_ui_in_command_center`
- PASS `second_build_card_action_remains_enabled`
- PASS `formal_leaflet_map_shows_three_remaining_builds`
- PASS `three_builds_resolve_through_leaflet_selection_and_visible_build_button`
- PASS `remaining_builds_decrements_three_two_one_zero`
- PASS `authoritative_state_has_base_plus_three_new_organizations`
- PASS `both_cards_commit_to_discard_and_queue_clears`
- PASS `formal_log_records_each_card_build`
- PASS `browser_console_has_no_errors`

## Screenshots
- `docs/records/action-cards/build-entitlement-queue/build-queue-collecting.png`
- `docs/records/action-cards/build-entitlement-queue/build-queue-three-remaining.png`
- `docs/records/action-cards/build-entitlement-queue/build-queue-resolved.png`
