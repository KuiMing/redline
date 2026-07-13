# 可取消 pending choice 驗證

可重跑指令：`python3 scripts/validate_cancellable_choice.py`

- total: 7 / passed: 7 / failed: 0

## Browser proof

- `CANCELLABLE_CHOICE_CCDI_BROWSER.png`（中紀委：關閉鈕為「取消」）
- `CANCELLABLE_CHOICE_MANDATORY_NOCLOSE_BROWSER.png`（強制型 topdeck：無關閉鈕）

## Results

- PASS ccdi_cancel_reverts_cleanly_without_consuming: checks={"pending_is_ccdi": true, "state_flag_cancellable": true, "cancel_succeeded": true, "pending_cleared": true, "ability_not_consumed": true, "hand_untouched": true}
- PASS propaganda_and_state_security_are_cancellable: checks={"propaganda_key": true, "propaganda_cancellable": true, "state_security_key": true, "state_security_cancellable": true}
- PASS cancelled_ability_can_be_reactivated: checks={"re_triggers_pending": true, "still_not_consumed_before_resolve": true}
- PASS confirm_zero_cards_consumes_unlike_cancel: checks={"resolve_ok": true, "ability_consumed": true}
- PASS mandatory_choice_cannot_be_cancelled: checks={"state_flag_not_cancellable": true, "cancel_rejected": true, "pending_still_present": true}
- PASS cannot_cancel_another_players_choice: checks={"rejected_not_your_choice": true, "pending_still_present": true}
- PASS cancellable_set_is_scoped_to_the_three_abilities: checks={"exactly_the_three_red_army_abilities": true}
