# Map town/base faction display validation

- game_id: 73a4325c-debc-4ccb-ac3d-a8d6986f8180
- total: 6
- passed: 6
- failed: 0
- screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/map-ui/map_faction_display_validation.png

## Results
- ✅ `faction_selection_succeeded` — {"choose_host": {"success": true, "factions": {"ceea9276-225a-460b-a771-843f951f3d92": "red_army"}, "bases": {}}, "choose_ally": {"success": true, "factions": {"ceea9276-225a-460b-a771-843f951f3d92": "red_army", "f1c551cb-4e8d-4f50-b623-2c35c62a89fb": "taiwan_green"}, "bases": {"f1c551cb-4e8d-4f50-b623-2c35c62a89fb": "臺北"}}}
- ✅ `taipei_label_shows_owner_faction_and_count` — {"taipei": {"latlng": [25.033, 121.5654], "content": "臺北 1（臺灣（綠線））", "fillColor": "#22c55e"}, "near_taipei": [{"latlng": [25.033, 121.5654], "content": "臺北 1（臺灣（綠線））", "fillColor": "#22c55e"}, {"latlng": [25.012, 121.4657], "content": "新北", "fillColor": "#6b7280"}, {"latlng": [25.1276, 121.7392], "content": "基隆", "fillColor": "#6b7280"}, {"latlng": [24.9936, 121.3], "content": "桃園", "fillColor": "#6b7280"}, {"latlng": [24.7591, 121.753], "content": "宜蘭", "fillColor": "#6b7280"}], "expected": "臺北 1（臺灣（綠線））"}
- ✅ `taipei_marker_uses_green_line_color_not_gray_fallback` — {"fillColor": "#22c55e"}
- ✅ `unowned_neighbor_town_keeps_plain_label_and_gray_fill` — {"empty_neighbor": {"latlng": [25.012, 121.4657], "content": "新北", "fillColor": "#6b7280"}}
- ✅ `beijing_label_shows_red_army_owner_and_count` — {"beijing": {"latlng": [39.9042, 116.4074], "content": "北京 1（紅軍）", "fillColor": "#f04f56"}}
- ✅ `beijing_marker_uses_red_army_camp_color_not_gray_fallback` — {"fillColor": "#f04f56"}
