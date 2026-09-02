# 東洋奧援 no-target modal Browser 驗證

結果：**11/11 passed**

情境：東洋奧援 tier 3；臺北反共組織供應已達 22，後端回傳無合法互動目標且交易回滾。

- PASS: `raw_server_error_received`
- PASS: `modal_visible_with_east_support_title_and_localized_message`
- PASS: `hud_notice_remains_empty_and_invisible`
- PASS: `rejected_play_retains_card_discard_and_pending_state`
- PASS: `icon_close_hides_modal`
- PASS: `same_server_state_render_stays_closed`
- PASS: `second_same_turn_click_is_new_attempt_and_reopens`
- PASS: `second_rejection_also_preserves_zones_and_pending`
- PASS: `modal_fits_1024x768_viewport`
- PASS: `native_dialog_count_is_zero`
- PASS: `browser_console_error_count_is_zero`

Screenshot: `docs/records/support-cards/east-support-no-target-modal/east_support_no_target_modal_1024x768.png`

重跑：`REDLINE_BASE_URL=http://127.0.0.1:8769 uv run --with playwright python scripts/validate/validate_support_no_target_modal.py`
