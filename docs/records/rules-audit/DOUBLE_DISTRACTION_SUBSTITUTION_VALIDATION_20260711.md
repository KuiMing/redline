# 內鬥耗盡改雙倍分神替代驗證（C1）

可重跑指令：`python3 scripts/validate_double_distraction_substitution.py`

- total: 5 / passed: 5 / failed: 0

## Results

- PASS helper_normal_and_substitution: checks={"normal_two_internal_conflicts": true, "normal_consumed_supply": true, "substituted_two_distractions": true, "distraction_supply_consumed": true}
- PASS helper_partial_and_both_empty: checks={"partial_gives_one_distraction": true, "empty_gives_nothing": true, "both_empty_logged": true}
- PASS divide_card_consumes_supply_and_substitutes: checks={"target_gained_two_internal_conflicts": true, "supply_consumed": true, "mixed_substitution_when_supply_runs_out_midway": true, "distraction_supply_consumed": true}
- PASS event_gain_internal_conflict_substitutes: checks={"gained_two_substitutes": true}
- PASS leak_top_deck_substitutes: checks={"top_card_discarded_plus_two_distractions": true}
