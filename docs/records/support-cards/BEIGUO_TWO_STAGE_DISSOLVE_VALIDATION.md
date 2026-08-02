# 北國奧援 I級兩段式瓦解驗證

可重跑指令：`python3 scripts/validate_beiguo_two_stage_dissolve.py`

- total: 5 / passed: 5 / failed: 0
- screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/support-cards/beiguo_two_stage_dissolve.png

## Results
- ✅ `initial_cancel_restores_card_and_leaves_board_unchanged` — {"hand_count": 1, "mine": {"巴黎": 1, "日內瓦": 1}, "enemy": {"慕尼黑": 1}}
- ✅ `sacrifice_step_stays_modal_based_with_cancel_button` — {"step1": {"step": "sacrifice_town", "interactionKind": null, "modalVisible": true, "closeVisible": true, "activeView": "commandView"}}
- ✅ `picking_sacrifice_auto_switches_to_map_with_dissolve_interaction_kind` — {"step2": {"step": "target", "interactionKind": "dissolve_organization", "modalVisible": false, "closeVisible": true, "activeView": "mapView"}}
- ✅ `target_step_marks_the_legal_enemy_organization_with_a_skull` — {"skull_count": 1}
- ✅ `clicking_the_skull_marker_dissolves_enemy_and_sacrifices_own_org_in_one_click` — {"enemy": {}, "mine": {"巴黎": 1}}
