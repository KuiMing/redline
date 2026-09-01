# 連續建立組織：地圖鏡頭保留驗證

可重跑指令：`python3 scripts/validate/validate_build_queue_preserves_map_viewport.py`

- total: 5 / passed: 5 / failed: 0
- screenshots: /Users/benmini/.openclaw/workspace/redline/docs/records/action-cards/build-queue-viewport/viewport_before_manual_pan.png, /Users/benmini/.openclaw/workspace/redline/docs/records/action-cards/build-queue-viewport/viewport_after_manual_pan.png, /Users/benmini/.openclaw/workspace/redline/docs/records/action-cards/build-queue-viewport/viewport_preserved_after_build.png

## Results
- ✅ `entering_build_session_auto_focuses_once` — {"zoom": 3, "center": {"lat": 29.20905008277816, "lng": 106.5}}
- ✅ `manual_pan_applied_before_next_build` — {"zoom": 4, "center": {"lat": 5, "lng": 100}}
- ✅ `three_builds_resolve_in_sequence` — [2, 1, 0]
- ✅ `map_viewport_never_resets_across_any_of_the_three_builds` — [{"expected_remaining_after": 2, "before": {"zoom": 4, "center": {"lat": 5, "lng": 100}}, "after": {"zoom": 4, "center": {"lat": 5, "lng": 100}}, "preserved": true}, {"expected_remaining_after": 1, "before": {"zoom": 4, "center": {"lat": 5, "lng": 100}}, "after": {"zoom": 4, "center": {"lat": 5, "lng": 100}}, "preserved": true}, {"expected_remaining_after": 0, "before": {"zoom": 4, "center": {"lat": 5, "lng": 100}}, "after": {"zoom": 4, "center": {"lat": 5, "lng": 100}}, "preserved": true}]
- ✅ `viewport_after_all_builds_still_matches_the_manual_pan_not_the_original_auto_focus` — {"final_view": {"zoom": 4, "center": {"lat": 5, "lng": 100}}, "manual_view": {"lat": 5.0, "lng": 100.0, "zoom": 4}}
