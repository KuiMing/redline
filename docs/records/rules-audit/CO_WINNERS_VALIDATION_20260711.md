# 共同勝利（2/3 進度）驗證（A4）

可重跑指令：`python3 scripts/validate/validate_co_winners.py`

- total: 4 / passed: 4 / failed: 0

## Results

- PASS co_winner_at_or_above_two_thirds: checks={"winner_is_W": true, "C_is_co_winner": true, "state_exposes_co_winners": true}
- PASS below_two_thirds_not_co_winner: checks={"winner_is_W": true, "C_not_co_winner": true}
- PASS red_army_victory_no_co_winners: checks={"red_wins": true, "no_co_winners_on_red_victory": true}
- PASS red_army_never_co_winner: checks={"winner_is_W": true, "red_not_co_winner": true}
