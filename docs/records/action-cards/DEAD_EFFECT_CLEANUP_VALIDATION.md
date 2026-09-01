# 凝聚共識/武裝集團 死代碼 JSON 宣告清理驗證

可重跑指令：`python3 scripts/validate/validate_dead_effect_cleanup.py`

- total: 3 / passed: 3 / failed: 0

## Results

- PASS forge_consensus_bonus_flows_through_choice_flag: checks={"bonus_flag_on_choice": true, "bonus_granted_once": true, "hand_after": true}
- PASS armed_unit_success_draw_flows_through_draw_on_success: checks={"choice_key": true, "draw_on_success_flag": true, "initiator_drew_one": true, "target_discarded_two": true}
- PASS dead_declarations_removed_from_json: checks={"forge_has_no_conditional_bonus": true, "armed_has_no_conditional_draw": true}
