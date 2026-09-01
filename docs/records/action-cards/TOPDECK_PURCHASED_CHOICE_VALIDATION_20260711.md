# 行動預告/行動募資 頂牌選擇驗證

可重跑指令：`python3 scripts/validate/validate_topdeck_purchased_choice.py`

- total: 7 / passed: 7 / failed: 0

## Results

- PASS playing_card_banks_right_and_grants_resource_immediately: checks={"no_pending_choice_at_play_time": true, "resource_granted_immediately": true, "right_banked": true, "purchases_untouched": true}
- PASS two_purchases_player_chooses_which_to_topdeck: checks={"pending_choice_raised": true, "choice_key": true, "both_offered": true, "right_already_spent": true, "resolved": true, "chosen_first_purchase_on_top": true, "other_purchase_stays_in_discard": true, "turn_not_ended_by_manual_use": true}
- PASS single_purchase_auto_topdeck_one_shot: checks={"no_pending_choice": true, "auto_topdecked": true, "money_plus_1_applied_at_play_time": true, "right_consumed": true}
- PASS no_purchase_use_errors_right_still_banked: checks={"play_success_without_choice": true, "resource_still_granted": true, "manual_use_errors": true, "right_not_consumed": true}
- PASS two_cards_played_stack_independent_topdeck_rights: checks={"two_rights_banked": true, "two_propaganda_granted": true, "first_use_placed_chosen_card": true, "one_right_remaining": true, "second_use_auto_placed_last_candidate": true, "second_use_placed_remaining_card": true, "no_rights_remaining": true}
- PASS end_turn_auto_drains_unused_right_with_two_purchases: checks={"end_turn_auto_prompted": true, "choice_key": true, "both_offered": true, "resolved": true, "no_dangling_choice": true, "chosen_card_drawn_into_new_hand": true, "turn_passed_to_next_player": true}
- PASS end_turn_drops_right_with_no_candidates_without_blocking_turn: checks={"no_pending_choice": true, "turn_still_completes": true, "dropped_right_logged": true}
