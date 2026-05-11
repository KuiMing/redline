# FACTION_ABILITY_PHASE8_SHARED_DISSOLVE_UI

日期：2026-05-07

## 本輪完成

把 shared dissolve 從 backend 規則，推進到 stable map 的第一版可操作 UI 與實戰截圖驗證。

## 已完成

### 1. 地圖側欄新增 shared dissolve 控制
#### static/leaflet_game_map.html
新增：
- `#dissolveBtn`
- `#dissolveHint`

用途：
- 選取 shared 城鎮後，顯示是否可對實際 owner 發動瓦解

### 2. stable map 邏輯新增 shared dissolve helper
#### static/leaflet_game_map_logic.js
新增：
- `actualTownOwnerName(townName)`
- `sharedDissolveTargetForTown(townName)`
- `sendDissolveAction(defender, townName)`
- `window.__dissolveFromSharedForTest(townName)`

### 3. dissolve UI 文案同步
#### static/leaflet_game_map_logic.js
`refreshDirectBuildUi()` 現在同時維護：
- direct build hint
- dissolve hint

當 shared dissolve 可用時，會顯示：
- 目前可瓦解哪個實際擁有者的共享組織

### 4. shared dissolve 實戰截圖
使用：
- `POST /test/setup-hu-taiwan-shared`
- stable map 頁 `static/leaflet_game_map.html`

情境：
- hu：紐約 1
- taiwan_green：上海 1、臺北 1
- hu 對上海有 shared access

### 實戰結果
#### 選取上海前
- `highlighted: true`
- `shared: true`
- `canAct: true`

#### shared dissolve
- `window.__dissolveFromSharedForTest('上海')`
- 結果：`ok: true`
- defender：`taiwan`

#### 結算後
- 地圖上 `上海` 從 `map.towns` 消失
- `players_after`：
  - `hu: {紐約: 1}`
  - `taiwan_green: {臺北: 1}`

代表：
- shared dissolve 已能在 stable map 實戰頁面上成功操作
- 實際被扣掉的是 shared actual owner（taiwan_green）在上海的組織

## 驗證
新增：
- `scripts/validate_shared_dissolve_ui_phase8.py`

輸出：
- `SHARED_DISSOLVE_UI_PHASE8_VALIDATION.json`
- `SHARED_DISSOLVE_UI_PHASE8_VALIDATION.md`
- `SHARED_DISSOLVE_MAP_BATTLESHOT_FIXED.json`

截圖：
- `shared_dissolve_map_before_fixed.png`
- `shared_dissolve_map_after_fixed.png`

### 結果
- UI structural validation: 6 / 6 passed
- 實戰 dissolve 也成功

## 限制
- dissolve 後 hint 會變成「沒有可用的 shared dissolve 目標」與「這不是當前玩家可操作的城鎮」
- 這是因為上海組織已被移除，shared_access 同步消失，屬正常結算後狀態
