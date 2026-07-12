# 紅軍奧援歸屬驗證（非紅軍打出後回紅軍棄牌堆）

可重跑指令：`python3 scripts/validate_red_support_ownership.py`

- total: 3 / passed: 3 / failed: 0

## Results

- PASS non_red_action_play_returns_to_red_discard: checks={"play_ok": true, "returned_flag": true, "card_in_red_discard": true, "not_in_caster_discard": true, "caster_drew_one": true}
- PASS non_red_resource_play_returns_to_red_discard: checks={"play_ok": true, "card_in_red_discard": true, "not_in_caster_discard": true}
- PASS red_play_pass_flow_unchanged: checks={"target_choice_opened": true, "resolved": true, "card_in_opponent_discard": true, "not_in_red_discard": true}
