# 翻牆移動成本＋目的城鎮陣營適用驗證

可重跑指令：`python3 scripts/validate/validate_wall_crossing_movement.py`

- total: 6 / passed: 6 / failed: 0

## Results

- PASS dongsha_to_kwuntong_allowed_despite_faction_inapplicability: checks={"not_blocked_by_faction_applicability": true, "wall_crossing_cost_two_consumed": true}
- PASS wall_crossing_costs_two_moves: checks={"one_move_not_enough": true, "two_moves_succeed": true, "cost_two_consumed": true}
- PASS reverse_crossing_inner_to_outer_costs_two: checks={"inner_to_outer_also_two": true}
- PASS rail_multi_step_cannot_cross_wall: checks={"bfs_does_not_cross_wall": true, "two_step_crossing_move_rejected": true}
- PASS direct_rail_crossing: checks={"adjacent_rail_crossing_costs_two": true}
- PASS same_side_rail_three_still_costs_one: checks={"same_side_rail3_costs_one": true}
