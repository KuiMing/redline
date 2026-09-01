# FACTION_ABILITY_PHASE8_SHARED_INTERACTION_UI

日期：2026-05-06

## 本輪完成

把共用組織從純視覺提示，進一步推到第一版 shared-aware 互動層。

## 已完成

### 1. shared-aware 起點判斷
#### static/leaflet_game_map_logic.js
- 新增 `canActFromTown(townName)`
- 規則：
  - 自己有組織，或
  - 對當前玩家具有 shared access
  - 都視為可操作起點

### 2. movement highlight 改成 shared-aware 第一版
#### static/leaflet_game_map_logic.js
- `movementOptionsForTown()` 不再只限 own org
- 現在改成 `canActFromTown(townName)`
- 若是 shared-only 起點：
  - 起點 marker 會用金色強化
  - 額外畫出 `共享組織起點` 虛線圈

注意：
- 這一版是 UI / highlight shared-aware
- backend `move_organization()` 仍然只接受 own org 起點，尚未改 engine 規則

### 3. direct build button
#### static/leaflet_game_map.html
- 新增：`#directBuildBtn`
- 新增：`#directBuildHint`

#### static/leaflet_game_map_logic.js
- 新增 `sendDirectBuildAction(townName)`
- 新增 `refreshDirectBuildUi()`

效果：
- 選取具有自己組織或共享組織可用性的城鎮後
- 左側可直接點按「在目前城鎮建立組織」
- hint 會區分：
  - 從自己的組織直接發展
  - 從共享組織直接發展

### 4. test helper 更完整
#### static/leaflet_game_map_logic.js
- `window.__selectTownForTest()` 現在會回傳：
  - `shared`
  - `canAct`

## 驗證
新增：
- `scripts/validate/validate_shared_interaction_ui_phase8.py`

輸出：
- `SHARED_INTERACTION_UI_PHASE8_VALIDATION.json`
- `SHARED_INTERACTION_UI_PHASE8_VALIDATION.md`

### 結果
- total: 6
- passed: 6
- failed: 0

## 重要限制
這一輪故意只先做 UI / highlight / build button 層：
- backend `move_organization()` 仍要求 own organization in origin
- 所以 shared move 目前是「前端能看見 shared 起點」，但還不是完整 engine 規則收斂

## 下一步
1. backend move / dissolve 是否正式 shared-aware
2. shared build / move / dissolve 的錯誤訊息與 UI 回饋一致化
3. 真瀏覽器截圖驗證
