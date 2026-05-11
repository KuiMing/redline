# PHASE3_SAFEHOUSE_MAP_HIGHLIGHT

日期：2026-05-05

## 本輪完成

安全屋可建立範圍現在已經真正顯示在 Leaflet 地圖上。

## 修改內容

### static/leaflet_game_map_logic.js
新增 / 補上：
- `buildHighlightLayer`
- `selectedBuildTargets`
- `resetBuildSelection()`
- `currentPlayerState()`
- `playerHasSafehouse()`
- `buildOptionsForTown(originTown)`

### 地圖互動邏輯
當前玩家若是香港，且擁有：
- `香港城`
- 或 `臺北`

則點選自己的城鎮時：
- 原本的移動高亮仍照常顯示
- 額外用粉色圈標出 `安全屋 +1` 後可建立的城鎮

### 點擊目標
若點到安全屋可建立目標：
- 會送出 websocket `build` action
- payload 為：
  - `{ action: 'build', from: selectedTown, town: targetTown }`

## 驗證
### 測試方式
- 使用 `POST /test/setup-hong-kong-safehouse`
- 在 `static/leaflet_game_map.html` 直接 `connectGameMap({ gameId, playerId })`
- 再用 `__selectTownForTest('香港城')` 驗證高亮

### 驗證結果
- 選取 `香港城` 成功
- 地圖高亮成功
- 截圖：`safehouse_map_highlight_ui.png`

## 效果
現在安全屋不再只是控制面板清單，
而是會在戰略地圖上直接把可建立目標高亮出來。
