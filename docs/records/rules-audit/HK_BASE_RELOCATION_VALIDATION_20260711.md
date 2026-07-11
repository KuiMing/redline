# 香港根據地遷移驗證（S5-1＋機場根據地用途）

可重跑指令：`python3 scripts/validate_hk_base_relocation.py`

- total: 5 / passed: 5 / failed: 0

## Results

- PASS free_window_after_event_settlement: checks={"window_opens_on_settlement_even_on_failure": true, "free_relocation_succeeds_without_moves": true, "base_moved": true, "window_consumed": true, "state_exposes_window": true}
- PASS window_closes_when_next_round_starts: checks={"window_closed": true, "no_free_relocation_after_close": true}
- PASS airport_base_relocation_costs_two: checks={"relocation_succeeds": true, "costs_two_moves": true, "base_moved": true, "blocked_with_one_move": true}
- PASS relocation_restrictions: checks={"only_four_cities": true, "enemy_occupied_blocked": true, "airport_requires_own_action_turn": true, "non_hk_faction_blocked": true}
- PASS base_anchor_and_base_ability_follow_relocation: checks={"new_base_ability_active": true, "anchor_cannot_move_from_new_base": true}
