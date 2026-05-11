# PHASE3_SAFEHOUSE_FRONTEND_FIXED

日期：2026-05-05

## 本輪結論

安全屋前端 panel 已經接通並成功顯示。

## 關鍵發現

先前 `buildSupportPanel` 一直沒出現，不是 engine 沒接好，
而是測試過程實際上沒有真正建立 websocket game session。

也就是：
- 只用 lobby 的 `JOIN OPERATION` + `START`
- 並不會自動進入我們測試 endpoint 建好的 live game session

因此 `renderBuildSupport(state)` 根本沒有拿到正確的遊戲 state 更新。

## 解法

這次改用：
- 先呼叫 `POST /test/setup-hong-kong-safehouse`
- 取得 `game_id` / `player_id`
- 在 browser 中直接執行：
  - `gameId = ...`
  - `playerId = ...`
  - `connect()`

如此一來前端就真的接上該測試局面的 websocket state。

## 成果

在香港 `ACTION` phase 測試局面中：
- `buildSupportPanel` 成功顯示
- `buildSupportInfo` 正常顯示提示
- `buildSupportOrigins` 顯示：`香港城`
- 選取後，`buildSupportTargets` 正常列出安全屋 +1 後可建立的城鎮

### 已觀察到的目標城鎮
- 九龍城
- 廣州
- 柴灣
- 沙田
- 油尖旺
- 澳門
- 葵青
- 西貢
- 觀塘
- 赤柱
- 赤臘角

## 截圖
- `safehouse_build_support_connected_direct.png`
