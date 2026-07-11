# 誘導虛耗僅可移除本牌驗證

可重跑指令：`python3 scripts/validate_bait_exhaustion_self_only.py`

- total: 3 / passed: 3 / failed: 0

## Results

- PASS only_the_played_card_offered: checks={"choice_opened": true, "exactly_two_options": true, "first_is_the_card_itself": true, "second_is_skip": true, "no_hand_cards_offered": true}
- PASS remove_self_then_force_target_discard: checks={"remove_ok": true, "followup_target_choice": true, "target_hand_discard_opened": true, "target_discarded": true}
- PASS decline_keeps_card_in_discard_and_skips_forced_discard: checks={"declined_ok": true, "no_followup": true, "card_goes_to_own_discard_not_removed": true, "target_hand_untouched": true}
