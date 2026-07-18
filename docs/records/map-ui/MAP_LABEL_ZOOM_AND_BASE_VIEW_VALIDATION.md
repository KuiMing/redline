# 地圖標籤 zoom 門檻／開局根據地視角／玩家名陣營色 驗證

可重跑指令：`python3 scripts/validate_map_label_zoom_and_base_view.py`

- total: 6 / passed: 6 / failed: 0
- screenshots: /Users/benmini/.openclaw/workspace/redline/docs/records/map-ui/map_label_far_zoom.png, /Users/benmini/.openclaw/workspace/redline/docs/records/map-ui/map_label_near_zoom.png

## Results
- ✅ `initial_view_centers_on_own_base_at_zoom_9` — {"view": {"lat": 25.033, "lon": 121.5654, "zoom": 9}}
- ✅ `map_sidebar_current_player_name_uses_faction_color` — {"sidebar_color": "rgb(34, 197, 94)", "current_player": "ally", "expected": "rgb(34, 197, 94)"}
- ✅ `far_zoom_label_omits_faction_text` — {"has_taipei_org": true, "label_far": "臺北 1"}
- ✅ `near_zoom_label_includes_faction_text` — {"label_near": "臺北 1（臺灣（綠線））"}
- ✅ `status_overview_names_use_faction_colors` — {"status_colors": [{"name": "host", "color": "rgb(240, 79, 86)"}, {"name": "ally", "color": "rgb(34, 197, 94)"}]}
- ✅ `hud_current_player_name_uses_faction_color` — {"hud_color": "rgb(34, 197, 94)", "expected": "rgb(34, 197, 94)"}
