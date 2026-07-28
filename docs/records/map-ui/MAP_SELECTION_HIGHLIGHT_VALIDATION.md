# Map selection highlight validation

- game_id: 6eedfc8d-9f08-4719-a78a-119985d9f17f
- total: 7
- passed: 7
- failed: 0
- screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/map-ui/map_selection_highlight_validation.png

## Results
- ✅ `green_line_org_town_is_green_before_selection` — {"臺北": {"fill": "#4ade80", "fillOpacity": 0.98, "color": "#f8fafc"}}
- ✅ `selecting_org_town_keeps_solid_faction_fill` — {"臺北": {"fill": "#4ade80", "fillOpacity": 1, "color": "#ffffff"}}
- ✅ `reachable_move_target_uses_neutral_outline_and_keeps_base_fill` — {"基隆": {"fill": "#6b7280", "fillOpacity": 0.32, "color": "#e2e8f0"}}
- ✅ `unrelated_town_keeps_base_style_not_dimmed` — {"臺中": {"fill": "#6b7280", "fillOpacity": 0.32, "color": "#07111f"}}
- ✅ `selecting_empty_town_is_solid_white` — {"高雄": {"fill": "#f8fafc", "fillOpacity": 1, "color": "#ffffff"}}
- ✅ `other_org_town_returns_to_solid_green_after_reselect` — {"臺北": {"fill": "#4ade80", "fillOpacity": 0.98, "color": "#f8fafc"}}
- ✅ `reselecting_a_different_empty_town_resets_the_previous_one` — {"南投_prev": {"fill": "#6b7280", "fillOpacity": 0.32, "color": "#07111f"}, "臺中_curr": {"fill": "#f8fafc", "fillOpacity": 1, "color": "#ffffff"}}
