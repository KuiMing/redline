# 「我的陣營」按鈕與 modal 驗證

可重跑指令：`python3 scripts/validate/validate_my_faction_modal.py`

- total: 5 / passed: 5 / failed: 0
- screenshots: /Users/benmini/.openclaw/workspace/redline/docs/records/playtest-flow/my_faction_modal.png, /Users/benmini/.openclaw/workspace/redline/docs/records/playtest-flow/my_faction_modal_hong_kong.png

## Results
- ✅ `my_faction_button_visible_in_game_tabs` — {"visible": true}
- ✅ `modal_opens_with_faction_colored_title_and_all_sections` — {"modal_visible": true, "title": "臺灣（綠線）", "title_color": "rgb(74, 222, 128)", "sections": ["根據地", "能力", "規則與限制", "獲勝條件"], "non_empty": true}
- ✅ `base_section_shows_actual_base` — {"base_text": "臺北"}
- ✅ `close_button_hides_modal` — {"display": "none"}
- ✅ `hong_kong_faction_also_renders_correctly` — {"title": "香港", "ability_count": 1}
