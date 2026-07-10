# 南洋奧援 tier1 discard choice validation

可重跑指令：`python3 scripts/validate_south_seas_support_tier1_discard_choice.py`

- total: 2
- passed: 2
- failed: 0

## Results

- PASS choice_is_offered_not_auto_resolved: checks={"play_success": true, "pending_choice_raised": true, "choice_key_correct": true, "both_hand_cards_offered": true}
- PASS player_can_keep_the_drawn_card_and_discard_the_other: checks={"resolved_success": true, "discarded_the_other_card": true, "drawn_card_kept_in_hand": true, "other_card_actually_discarded": true}
