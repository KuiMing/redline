# 東突厥集中營 × 臺灣奧援 UI Validation

- 結果：**8/8 passed**
- 正式流程：從手牌按下臺灣奧援「使用行動」，在瓦解目標仍待選時檢查事件進度。
- 預期：臺灣奧援印刷購買費用含 2 宣傳，因此事件進度立即達成 1/1。

## Checks
- PASS `fixture_uses_canonical_east_turkestan_mission`
- PASS `fixture_starts_with_zero_event_progress`
- PASS `formal_hand_action_commits_taiwan_support_before_target_resolution`
- PASS `authoritative_event_progress_is_success_while_support_target_is_pending`
- PASS `formal_ui_shows_taiwan_support_pending_choice`
- PASS `formal_pinned_event_ui_shows_completed_progress`
- PASS `formal_event_reveal_shows_success_and_one_of_one`
- PASS `browser_console_has_no_errors`

## Screenshots
- `docs/records/event-cards/support-event-progress/taiwan-support-event-progress-pending.png`
- `docs/records/event-cards/support-event-progress/east-turkestan-event-success.png`
