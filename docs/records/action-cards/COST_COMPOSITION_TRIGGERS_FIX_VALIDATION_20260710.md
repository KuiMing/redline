# 點燃熱情/樹立信心/陣營能力購買費用觸發修正驗證

可重跑指令：`python3 scripts/validate/validate_cost_composition_triggers.py`

- total: 9
- passed: 9
- failed: 0

## Results

- PASS ignite_passion_bonus_after_mismatched_category_card: checks={"play_success": true, "drew_2_cards": true}
- PASS build_confidence_bonus_after_mismatched_category_card: checks={"play_success": true, "drew_2_cards": true}
- PASS ignite_passion_no_bonus_without_qualifying_play: checks={"play_success": true, "drew_only_1_card": true}
- PASS support_card_counts_for_printed_purchase_cost_triggers: checks={"play_success": true, "drew_2_cards_with_bonus": true}
- PASS faction_ability_商貿組織_triggers_on_mismatched_category_card: checks={"play_success": true, "triggered_flag_set": true, "drew_3_cards_total": true}
- PASS faction_ability_基金會_triggers_on_mismatched_category_card: checks={"play_success": true, "triggered_flag_set": true, "gained_2_money": true}
- PASS faction_ability_民族調和_triggers_on_mismatched_category_card: checks={"play_success": true, "triggered_flag_set": true, "drew_3_cards_total": true}
- PASS faction_ability_人同此心_triggers_on_mismatched_category_card: checks={"play_success": true, "triggered_flag_set": true, "gained_2_propaganda": true}
- PASS faction_ability_still_triggers_after_reaction_skip: checks={"reaction_prompt_raised": true, "reaction_choice_type_correct": true, "skip_resolved_success": true, "skipped_reaction_flag": true, "triggered_flag_set": true, "drew_3_cards_total": true}
