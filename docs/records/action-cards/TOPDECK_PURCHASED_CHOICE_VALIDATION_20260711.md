# 行動預告/行動募資 頂牌選擇驗證

可重跑指令：`python3 scripts/validate_topdeck_purchased_choice.py`

- total: 4 / passed: 4 / failed: 0

## Results

- PASS two_purchases_player_chooses_which_to_topdeck: checks={"pending_choice_raised": true, "choice_key": true, "both_offered": true, "resource_not_granted_yet": true, "resolved": true, "chosen_first_purchase_on_top": true, "other_purchase_stays_in_discard": true, "remaining_effect_resumed_propaganda_plus_1": true}
- PASS single_purchase_auto_topdeck_one_shot: checks={"no_pending_choice": true, "auto_topdecked": true, "money_plus_1_applied": true}
- PASS no_purchase_noop_still_grants_resource: checks={"success_without_choice": true, "resource_still_granted": true, "noop_logged": true}
- PASS end_turn_flow_two_purchases_choice_then_end_turn: checks={"end_turn_prompted": true, "use_returns_pending": true, "turn_not_ended_yet": true, "both_offered": true, "resolved": true, "no_dangling_choice": true, "chosen_card_drawn_into_new_hand": true, "resources_reset_by_end_turn": true}
