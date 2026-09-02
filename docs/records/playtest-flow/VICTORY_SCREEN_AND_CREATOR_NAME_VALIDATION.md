# 勝利畫面／建房者行動代號 驗證

可重跑指令：`python3 scripts/validate/validate_victory_screen_and_creator_name.py`

- total: 5 / passed: 5 / failed: 0
- screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/playtest-flow/victory_screen.png

## Results
- ✅ `creator_typed_name_is_used_not_host` — {"roster_name": "測試代號X"}
- ✅ `green_winner_modal_shows_name_in_faction_color` — {"visible": true, "title": "GREEN 獲勝", "title_color": "rgb(74, 222, 128)"}
- ✅ `modal_shows_faction_turn_and_player_summary` — {"subtitle": "臺灣（綠線）｜第 21 回合結算", "rows": 2, "winner_row": "GREEN 🏆"}
- ✅ `minimize_shows_badge_and_badge_reopens_modal` — {"minimized": {"modal": "none", "badge": "block", "badge_text": "遊戲結束：GREEN 獲勝｜點擊查看結果"}, "reopened": "flex"}
- ✅ `red_army_winner_resolves_to_red_player_in_red` — {"title": "RED 獲勝", "color": "rgb(240, 79, 86)"}
