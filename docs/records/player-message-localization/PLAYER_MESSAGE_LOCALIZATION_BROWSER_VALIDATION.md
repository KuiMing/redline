# 玩家提示繁體中文化 Browser Validation

- 結果：**10/10 passed**
- 正式端點：`http://127.0.0.1:8000`
- 情境：不存在房間的 REST error、武裝者範圍外目標的 WebSocket error。

| 檢查 | 結果 | 證據 |
|---|---:|---|
| `lobby_missing_game_is_zh_tw` | PASS | 找不到遊戲房間。 |
| `lobby_missing_game_has_no_raw_english` | PASS | 找不到遊戲房間。 |
| `range_setup_created` | PASS | 已建立 2 人 deterministic range fixture |
| `range_card_prepared` | PASS | 行動玩家手牌已固定為武裝者 |
| `reported_range_error_is_zh_tw` | PASS | {"notice": "目標玩家在範圍內沒有組織。", "dialogs": ["目標玩家在範圍內沒有組織。"], "runtime_error": ""} |
| `reported_range_dialog_is_zh_tw` | PASS | ["目標玩家在範圍內沒有組織。"] |
| `reported_range_error_has_no_raw_english` | PASS | 目標玩家在範圍內沒有組織。 |
| `map_range_error_is_zh_tw` | PASS | 操作失敗：目標玩家在範圍內沒有組織。 |
| `map_range_error_has_no_raw_english` | PASS | 操作失敗：目標玩家在範圍內沒有組織。 |
| `browser_console_has_no_errors` | PASS | [] |

## Screenshots

- `docs/records/player-message-localization/player-message-lobby-zh-tw.png`
- `docs/records/player-message-localization/player-message-range-error-zh-tw.png`
- `docs/records/player-message-localization/player-message-map-error-zh-tw.png`
