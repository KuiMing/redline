# 組織經驗甲 重複建立子句驗證

可重跑指令：`python3 scripts/validate_org_exp_a_repeat_build.py`

- total: 5 / passed: 5 / failed: 0

## Results

- PASS full_repeat_loop_build_discard_build: checks={"build_choice_opened": true, "first_build_done": true, "repeat_prompt_opened": true, "discard_choice_opened": true, "only_qualifying_cards_offered": true, "card_discarded": true, "second_build_choice_opened": true, "second_build_done": true, "loop_ends_without_qualifying_cards": true}
- PASS decline_keeps_hand_and_ends_flow: checks={"declined_ok": true, "no_pending_after_decline": true, "qualifying_card_kept_in_hand": true, "only_one_build": true}
- PASS no_qualifying_cards_no_prompt: checks={"build_done": true, "no_repeat_prompt": true}
- PASS two_repeats_with_two_qualifying_cards: checks={"three_builds_total": true, "loop_ended": true, "both_cards_discarded": true}
- PASS restricted_faction_repeat_respects_inner_distance: checks={"first_list_inner_limited_to_1_step": true, "repeat_list_inner_limited_to_1_step": true}
