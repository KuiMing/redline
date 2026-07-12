# 第20回合勝利宣告時機驗證

可重跑指令：`python3 scripts/validate_turn20_victory_declaration.py`

- total: 3 / passed: 3 / failed: 0

## Results

- PASS red_survival_declared_at_round20_rollover: checks={"red_army_declared_immediately": true, "turn_advanced_to_21": true, "no_round_21_event_drawn": true}
- PASS no_premature_declaration_entering_round_20: checks={"not_finished_at_20_start": true, "turn_is_20": true, "round_20_event_drawn": true}
- PASS mid_round_player_victory_unaffected: checks={"anti_communist_win_still_declared_mid_round": true}
