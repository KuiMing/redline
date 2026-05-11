# FACTION_ABILITY_PHASE8_SHARED_MAP_VISUAL

日期：2026-05-06

## 本輪完成

把共用組織從「只有 popup 文字」往前推到真正可見的地圖視覺層。

## 已完成項目

### 1. shared marker 視覺提示
#### static/leaflet_game_map_logic.js
- 新增 `sharedAccessForTown(name)`
- 新增 `sharedAccessSummary(name)`
- 對有 shared access 的城鎮，地圖上額外加一個 `S` badge marker
- 若 shared faction 不只一個，badge 會顯示 `S2`、`S3` ...

### 2. marker 外框改為 shared-aware
#### static/leaflet_game_map_logic.js
- `markerStyleForTown()` 現在會看 `sharedAccessForTown(name)`
- 若城鎮具有 shared access：
  - marker 外框改成金色
  - 外框變粗
  - 半徑略增
- 但主填色仍維持原本 control leader 顏色

這樣做的目的是：
- 保留既有控制判讀
- 同時讓 shared 狀態一眼看得出來

### 3. popup / info panel 更人話
#### static/leaflet_game_map_logic.js
- popup 現在除了 `共享可用：...` 之外
- 還會顯示：
  - `共享說明：此城鎮可被 X / Y 視為共用組織`

- info panel 額外增加：
  - `共享中（n）` / `無共享`

### 4. status hint 補 shared 視覺說明
#### static/leaflet_game_map_logic.js
- 未選城鎮時的 hint 現在會說明：
  - 共享組織會以 `金色外框與 S 標記` 顯示
- 若當前選取城鎮對 current player 具有 shared access，會在 hint 中明示

### 5. badge CSS
#### static/leaflet_game_map.html
- 新增 `.shared-badge-wrap`
- 新增 `.shared-badge`
- 新增 `.shared-badge-multi`

## 驗證
新增：
- `scripts/validate_shared_map_visual_phase8.py`

輸出：
- `SHARED_MAP_VISUAL_PHASE8_VALIDATION.json`
- `SHARED_MAP_VISUAL_PHASE8_VALIDATION.md`

### 結果
- total: 6
- passed: 6
- failed: 0

## 仍未完成
- shared-aware move/build/dissolve 高亮還沒完整接上
- control color 本身仍未改寫成 shared 重算
- 真實瀏覽器截圖驗證尚未在這一輪補跑
