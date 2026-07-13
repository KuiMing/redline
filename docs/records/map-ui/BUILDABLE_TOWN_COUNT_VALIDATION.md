# Buildable town count validation

可重跑指令：`python3 scripts/validate_buildable_town_count.py`

- total: 4 / passed: 4 / failed: 0

## Results

- PASS build_choice_shows_buildable_count_matching_towns: {"hint": "宣傳家：選擇要建立組織的城鎮。 可建立城鎮：5 個。地圖上已用橘色外框標出可選城鎮。請點選橘色城鎮，然後使用左側「在目前城鎮建立組織（效果）」按鈕完成建立。", "expected": 5}
- PASS build_count_matches_rendered_orange_markers: {"orangeMarkers": 5, "towns": 5}
- PASS build_hint_does_not_duplicate_the_source_prefix: {"hint": "宣傳家：選擇要建立組織的城鎮。 可建立城鎮：5 個。地圖上已用橘色外框標出可選城鎮。請點選橘色城鎮，然後使用左側「在目前城鎮建立組織（效果）」按鈕完成建立。"}
- PASS non_build_target_choice_shows_target_count: {"hint": "天方奧援：請選擇要瓦解的目標。 可選目標：3 個。地圖上已用橘色外框標出可選城鎮。請點選橘色城鎮，然後使用左側「瓦解目前城鎮（效果）」按鈕完成瓦解；也可回到選擇視窗確認。", "expected": 3}
