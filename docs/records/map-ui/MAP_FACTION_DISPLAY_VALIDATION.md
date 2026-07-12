# Map town/base faction display validation

- game_id: 1e32230c-99c4-4b1e-a025-8beefba5c7c3
- total: 6
- passed: 6
- failed: 0
- screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/map-ui/map_faction_display_validation.png

## Results
- ✅ `faction_selection_succeeded` — {"choose_host": {"success": true, "factions": {"95c52f16-281f-49ed-97ae-29da5dfd32c8": "red_army"}, "bases": {}}, "choose_ally": {"success": true, "factions": {"95c52f16-281f-49ed-97ae-29da5dfd32c8": "red_army", "5d2409f7-e922-4540-b65f-f11e43a20662": "taiwan_green"}, "bases": {"5d2409f7-e922-4540-b65f-f11e43a20662": "臺北"}}}
- ✅ `taipei_label_shows_owner_faction_and_count` — {"taipei": {"latlng": [25.033, 121.5654], "content": "臺北 1（臺灣（綠線））", "fillColor": "#3fb6ff"}, "near_taipei": [{"latlng": [25.033, 121.5654], "content": "臺北 1（臺灣（綠線））", "fillColor": "#3fb6ff"}, {"latlng": [25.012, 121.4657], "content": "新北", "fillColor": "#6b7280"}, {"latlng": [25.1276, 121.7392], "content": "基隆", "fillColor": "#6b7280"}, {"latlng": [24.9936, 121.3], "content": "桃園", "fillColor": "#6b7280"}, {"latlng": [24.7591, 121.753], "content": "宜蘭", "fillColor": "#6b7280"}], "expected": "臺北 1（臺灣（綠線））"}
- ✅ `taipei_marker_uses_taiwan_camp_color_not_gray_fallback` — {"fillColor": "#3fb6ff"}
- ✅ `unowned_neighbor_town_keeps_plain_label_and_gray_fill` — {"empty_neighbor": {"latlng": [25.012, 121.4657], "content": "新北", "fillColor": "#6b7280"}}
- ✅ `beijing_label_shows_red_army_owner_and_count` — {"beijing": {"latlng": [39.9042, 116.4074], "content": "北京 1（紅軍）", "fillColor": "#f04f56"}}
- ✅ `beijing_marker_uses_red_army_camp_color_not_gray_fallback` — {"fillColor": "#f04f56"}
