# FACTION_ABILITY_PHASE3_SAFEHOUSE

日期：2026-05-05

## 本輪完成

已開始實作 `安全屋` 的 engine 行為。

### 能力效果
- 建立牆內組織時，可建立組織距離額外增加 1 格。

## 實作內容

### server/game.py
新增：
- `build_organization_with_support(origin_town, target_town)`

作用：
- 允許從一個己方組織所在城鎮，向距離內的目標城鎮建立組織
- 以 road / rail 圖結構作為距離搜尋基礎
- `安全屋` 會提供 `+1` build range bonus

### build range 計算
- 基礎距離：1
- `build_range_bonus` 額外加成：保留
- `安全屋`：再額外 +1

### server/main.py
- websocket `build` action 現在支援：
  - 舊格式：`{ town }`
  - 新格式：`{ from, town }`
- 若有 `from` 與 `town`，就走 `build_organization_with_support()`

## 驗證
新增：
- `scripts/validate/validate_safehouse_build_range.py`

輸出：
- `SAFEHOUSE_BUILD_RANGE_VALIDATION.json`
- `SAFEHOUSE_BUILD_RANGE_VALIDATION.md`

### 目前驗證結果
- 從 `香港城` 可成功向距離 2 內的 `廣州` 建立組織（安全屋 +1 後成立）
- 超出合法 camp / 距離的城鎮仍會被擋下

## 目前狀態
這一輪已先把 `安全屋` 的核心距離加成能力接進 engine。
前端若要完整操作這能力，下一步還需要在 UI / map 端加入：
- build origin 選擇
- build target 選擇
- 可建範圍高亮
