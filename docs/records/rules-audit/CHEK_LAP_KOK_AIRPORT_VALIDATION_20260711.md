# 赤鱲角機場規則驗證（S5-2）

可重跑指令：`python3 scripts/validate/validate_chek_lap_kok_airport.py`

- total: 7 / passed: 7 / failed: 0

## Results

- PASS airport_move_to_outer_dev_space_costs_two: checks={"move_succeeds": true, "org_arrived_london": true, "cost_two_moves": true}
- PASS insufficient_moves_blocked: checks={"blocked_with_one_move": true}
- PASS reverse_direction_not_allowed: checks={"reverse_blocked": true}
- PASS non_hong_kong_faction_blocked: checks={"non_hk_blocked": true}
- PASS outside_hk_dev_space_blocked: checks={"outside_dev_space_blocked": true}
- PASS normal_adjacent_move_costs_one: checks={"adjacent_move_ok": true, "cost_one": true}
- PASS enemy_occupied_destination_blocked: checks={"enemy_destination_blocked": true}
