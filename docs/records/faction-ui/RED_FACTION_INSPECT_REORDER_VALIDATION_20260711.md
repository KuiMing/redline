# 紅軍派系（改革開放派）實作驗證

可重跑指令：`python3 scripts/validate/validate_red_faction_inspect_reorder.py`

- total: 5
- passed: 5
- failed: 0

## Results

- PASS reorder_and_draw: checks={"action_pending": true, "ability_used_flag": true, "inspected_top_three": true, "choice_key_reused": true, "resolve_success": true, "drew_one_card": true, "deck_top_matches_chosen_order": true, "no_stray_era_log": true}
- PASS once_per_turn: checks={"second_use_blocked": true}
- PASS ownership_gate: checks={"wrong_faction_blocked": true, "ethnic_ritual_blocked_for_wrong_faction": true}
- PASS short_deck: checks={"inspected_two_only": true, "resolved": true, "drew_new_top": true, "remaining_deck": true}
- PASS existing_abilities_still_pass_ownership_gate: checks={"liberals_probe_ok": true, "zhuang_ritual_ok": true}
