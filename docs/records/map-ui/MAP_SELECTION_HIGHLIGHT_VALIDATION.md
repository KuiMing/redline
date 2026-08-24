# Map selection highlight validation

- game_id: 97795a2e-c478-4162-a82e-79d6bd8a68f0
- total: 8
- passed: 8
- failed: 0
- screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/map-ui/map_selection_highlight_validation.png
- paris detail screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/map-ui/paris_selection_detail_sync_20260824.png

## Results
- ✅ `green_line_org_town_is_green_before_selection` — {"臺北": {"fill": "#4ade80", "fillOpacity": 0.98, "color": "#f8fafc"}}
- ✅ `selecting_org_town_keeps_solid_faction_fill` — {"臺北": {"fill": "#4ade80", "fillOpacity": 1, "color": "#ffffff"}}
- ✅ `reachable_move_target_uses_neutral_outline_and_keeps_base_fill` — {"基隆": {"fill": "#6b7280", "fillOpacity": 0.32, "color": "#e2e8f0"}}
- ✅ `unrelated_town_keeps_base_style_not_dimmed` — {"臺中": {"fill": "#6b7280", "fillOpacity": 0.32, "color": "#07111f"}}
- ✅ `selecting_empty_town_is_solid_white` — {"高雄": {"fill": "#f8fafc", "fillOpacity": 1, "color": "#ffffff"}}
- ✅ `other_org_town_returns_to_solid_green_after_reselect` — {"臺北": {"fill": "#4ade80", "fillOpacity": 0.98, "color": "#f8fafc"}}
- ✅ `reselecting_a_different_empty_town_resets_the_previous_one` — {"南投_prev": {"fill": "#6b7280", "fillOpacity": 0.32, "color": "#07111f"}, "臺中_curr": {"fill": "#f8fafc", "fillOpacity": 1, "color": "#ffffff"}}
- ✅ `paris_selection_keeps_paris_detail_and_omits_visual_status` — {"selected": "巴黎", "detailName": "巴黎", "detailText": "\n    巴黎\n    座標：2.352, 48.857\n    靜態統治者：歐洲\n    陣營：無\n    城鎮類型：一般城鎮\n    \n    當前控制者：無組織\n    組織狀態：無組織\n    共享可用：無\n    共享說明：無\n    \n    一般道路：無\n    鐵路：日內瓦"}
