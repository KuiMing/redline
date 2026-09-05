# 移除頂部窄條通知 Browser 驗證

Summary: **13/13 passed**

RED baseline: **2/13 passed**
RED evidence: `docs/records/ui-layout/no-top-notice-bar/NO_TOP_NOTICE_BAR_RED_BASELINE.json`

- PASS `top_notice_bar_dom_is_removed`
- PASS `invalid_phase_card_play_uses_prompt_modal`
- PASS `business_network_result_uses_prompt_modal`
- PASS `unrelated_purchase_index_is_not_business_network_result`
- PASS `generic_player_error_uses_prompt_modal`
- PASS `closed_error_prompt_does_not_reopen_for_same_state`
- PASS `new_action_attempt_can_show_same_error_again`
- PASS `queued_action_is_counted_once_across_flush`
- PASS `base_selection_wait_uses_phase_meta_not_notification`
- PASS `layout_has_no_secondary_row_1280x720`
- PASS `layout_has_no_secondary_row_1024x768`
- PASS `no_native_browser_dialogs`
- PASS `browser_console_has_no_errors`
