# 北國奧援 I級兩段式瓦解驗證

可重跑指令：`python3 scripts/validate_beiguo_two_stage_dissolve.py`

- total: 6 / passed: 6 / failed: 0
- screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/support-cards/beiguo_two_stage_dissolve.png

## Results
- ✅ `sacrifice_step_has_no_close_button_so_it_cannot_be_stranded` — {"step1": {"step": "sacrifice_town", "modalVisible": true, "closeVisible": false}}
- ✅ `picking_sacrifice_advances_to_enemy_target_step` — {"step2": {"step": "target", "modalVisible": true, "closeVisible": true}}
- ✅ `target_step_keeps_a_close_button_for_the_map_path` — {"closeVisible": true}
- ✅ `modal_path_dissolves_enemy_and_sacrifices_own_org` — {"enemy": {}, "mine": {"巴黎": 1}}
- ✅ `closing_target_modal_keeps_pending_and_map_sidebar_can_finish` — {"still_pending": "target", "dissolve_btn": {"text": "瓦解目前城鎮（效果）", "disabled": false}}
- ✅ `map_path_dissolves_enemy_and_sacrifices_own_org` — {"enemy": {}, "mine": {"巴黎": 1}}
