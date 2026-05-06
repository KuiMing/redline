# HU_TAIWAN_SHARED_MAP_FIX_2026_05_06

日期：2026-05-06

## 問題
先前實戰截圖顯示：
- backend `shared_access["上海"] = ["hu"]` 已存在
- 但 stable map 頁 `static/leaflet_game_map.html` 仍未把上海視為 shared 起點

根因是：
- stable map 頁仍內嵌舊版地圖邏輯
- 沒有真正使用已更新的 `static/leaflet_game_map_logic.js`

## 本輪修正
### 1. stable map 頁改為直接載入外部邏輯檔
#### static/leaflet_game_map.html
- 移除舊版 inline map logic
- 改為：
  - `<script src="/static/leaflet_game_map_logic.js"></script>`

這讓 stable map source of truth 與目前實作的 shared-aware 邏輯真正收斂成同一份。

## 實戰驗證
使用測試入口：
- `POST /test/setup-hu-taiwan-shared`

情境：
- hu：紐約 1 組織
- taiwan_green：上海 1、臺北 1
- current player：hu

### 結果
#### 選取上海
- `highlighted: true`
- `road: 0`
- `rail: 2`
- `owns: false`
- `shared: true`
- `canAct: true`

#### shared move
- 從 `上海 -> 南京`
- `move_result.ok: true`
- 結算後：
  - hu：`紐約 1, 南京 1`
  - taiwan_green：`臺北 1`

這代表：
- 上海已被 stable map 正確辨識為 shared 起點
- shared rail move 已成功在實戰地圖頁面上成立

## 產物
- `hu_taiwan_shared_map_select_shanghai_fixed.png`
- `hu_taiwan_shared_map_move_to_nanjing_fixed.png`
- `HU_TAIWAN_SHARED_MAP_BATTLESHOT_FIXED.json`

## 備註
- 驗證尾端再次呼叫 `__selectTownForTest('上海')` 時，因為 state 已變成 hu 在南京、台灣僅留臺北，故 `shared_access_shanghai` 變空，屬於移動後的正常結果，不是 regression。
