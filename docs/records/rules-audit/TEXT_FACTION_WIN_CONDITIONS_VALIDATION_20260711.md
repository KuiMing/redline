# 45 個 text-only 陣營勝利條件實作驗證（A1）

可重跑指令：`python3 scripts/validate_text_faction_win_conditions.py`

- total: 7 / passed: 7 / failed: 0

## Results

- PASS all_factions_have_structured_conditions: checks={"all_60_factions_have_win_conditions": true}
- PASS count_only_inner_liberals_14: checks={"thirteen_not_enough": true, "fourteen_wins": true}
- PASS outer_orgs_excluded_from_inner_scope: checks={"thirteen_inner_plus_outer_not_win": true}
- PASS count_and_required_yue: checks={"missing_required_town_blocks_win": true, "eleven_with_required_wins": true}
- PASS chaoxian_required_any_of: checks={"pyongyang_branch_wins": true, "seoul_branch_wins": true, "neither_blocks_win": true}
- PASS wan_region_scope_fails_closed_until_expansion_map_exists: checks={"orgs_outside_wan_do_not_count": true, "stacked_nanyang_fails_closed": true, "nanyang_counts_as_one_effective_town": true}
- PASS co_winner_now_works_for_text_factions: checks={"winner": true, "text_faction_co_winner": true}
