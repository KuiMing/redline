# 香港根據地遷移驗證（S5-1＋機場根據地用途）

可重跑指令：`python3 scripts/validate_hk_base_relocation.py`

- total: 5 / passed: 5 / failed: 0

## Results

- PASS free_window_after_event_settlement: checks={"window_opens_on_settlement_even_on_failure": true, "free_relocation_succeeds_without_moves": true, "base_moved": true, "window_consumed": true, "state_exposes_window": true}
- PASS window_closes_when_next_round_starts: checks={"window_closed": true, "no_free_relocation_after_close": true}
- PASS airport_is_not_paid_base_relocation: checks={"relocation_blocked_without_event_window": true, "moves_not_spent": true, "base_unchanged": true}
- PASS relocation_restrictions: checks={"only_four_cities": true, "other_faction_occupied_destination_blocked": true, "own_organization_destination_allowed": true, "free_window_allows_hk_choice_out_of_turn": true, "non_hk_faction_blocked": true}
- PASS base_anchor_and_base_ability_follow_relocation: checks={"new_base_ability_active": true, "anchor_cannot_move_from_new_base": true}
