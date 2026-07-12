# Map selection highlight validation

- game_id: 5eb4e362-4886-4248-950c-413e8e170460
- total: 7
- passed: 7
- failed: 0
- screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/map-ui/map_selection_highlight_validation.png

## Results
- ✅ `green_line_org_town_is_green_before_selection` — {"臺北": {"fill": "#22c55e", "fillOpacity": 0.98, "color": "#f8fafc"}}
- ✅ `selecting_org_town_keeps_solid_faction_fill` — {"臺北": {"fill": "#22c55e", "fillOpacity": 1, "color": "#ffffff"}}
- ✅ `reachable_move_target_is_solid_white_highlight` — {"基隆": {"fill": "#f8fafc", "fillOpacity": 1, "color": "#67e8f9"}}
- ✅ `unrelated_town_keeps_base_style_not_dimmed` — {"臺中": {"fill": "#6b7280", "fillOpacity": 0.32, "color": "#07111f"}}
- ✅ `selecting_empty_town_is_solid_white` — {"高雄": {"fill": "#f8fafc", "fillOpacity": 1, "color": "#ffffff"}}
- ✅ `other_org_town_returns_to_solid_green_after_reselect` — {"臺北": {"fill": "#22c55e", "fillOpacity": 0.98, "color": "#f8fafc"}}
- ✅ `reselecting_a_different_empty_town_resets_the_previous_one` — {"南投_prev": {"fill": "#6b7280", "fillOpacity": 0.32, "color": "#07111f"}, "臺中_curr": {"fill": "#f8fafc", "fillOpacity": 1, "color": "#ffffff"}}
