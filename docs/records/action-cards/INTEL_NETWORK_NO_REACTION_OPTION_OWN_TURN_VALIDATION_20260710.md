# 情報網 own-turn choose_one fix validation

可重跑指令：`python3 scripts/validate_intel_network_no_reaction_option_own_turn.py`

- total: 2
- passed: 2
- failed: 0

## Results

- PASS own_turn_play_offers_only_two_options: checks={"play_card_success": true, "choose_one_offered": true, "exactly_two_options": true, "no_cancel_option_label": true}
- PASS reaction_path_still_cancels_correctly: checks={"reaction_prompt_raised": true, "reaction_choice_type_correct": true, "reaction_offered_to_holder": true, "reaction_candidate_is_intel_network": true, "resolved_success": true, "used_intel_network_as_reaction": true, "canceled_correct_card": true, "acting_player_did_not_draw": true}
