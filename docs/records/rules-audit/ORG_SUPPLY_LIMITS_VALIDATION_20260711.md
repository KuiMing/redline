# 組織棋供應上限驗證（S1）

可重跑指令：`python3 scripts/validate/validate_org_supply_limits.py`

- 反共陣營上限: 22
- 紅軍上限: 40（2026-07-11 使用者決定，取代規則書 8×N+8 公式）
- total: 6 / passed: 6 / failed: 0

## Results

- PASS anti_communist_limit_22: checks={"constant_is_22": true, "build_allowed_at_21": true, "build_blocked_at_22": true, "total_stays_22": true}
- PASS red_army_limit_40_user_decision: checks={"constant_is_40": true, "red_can_build_past_22": true, "build_allowed_at_39": true, "build_blocked_at_40": true}
- PASS dissolve_frees_supply: checks={"blocked_at_limit": true, "allowed_after_dissolve": true}
- PASS ui_eligibility_gate_via_can_develop: checks={"develop_gate_false_at_limit": true, "develop_gate_true_below_limit": true}
- PASS shared_org_move_consumes_supply: checks={"shared_move_blocked_at_limit": true, "shared_move_allowed_below_limit": true, "total_after_transfer_at_limit": true}
- PASS own_org_move_free_at_limit: checks={"own_move_allowed_at_limit": true, "total_unchanged": true}
