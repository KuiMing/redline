# FACTION_ABILITY_PHASE8_SHARED_INTEGRATION

日期：2026-05-06

## 本輪完成

延續 phase6 / phase6b，共用組織現在往前整合到：
- victory 計數
- map state 額外資訊

## 已完成

### 1. VictoryEngine 改吃共享組織計數
#### server/victory.py
- `_count_scope()` 現在改用 `game._shared_org_count(player, town)`
- `count_and_required` 也改為用共享組織判斷必要城市是否達成

這表示：
- 若 faction 與共享對象在某城鎮共用組織
- 該城鎮的組織總數可被計入牆內 / 總組織數條件

### 2. map state 新增 `shared_access`
#### server/game.py
- `state()` 現在會輸出：
  - `map.shared_access`

內容是：
- 哪些 town 對哪些 faction 目前具有共享組織可用性

### 3. Leaflet popup 顯示共享可用資訊
#### static/leaflet_game_map_logic.js
- `popupHtml()` 現在會顯示：
  - `共享可用：...`

也就是地圖城鎮資訊現在開始能看到共享 access 狀態。

## 驗證
新增：
- `scripts/validate_shared_victory_phase8.py`

輸出：
- `SHARED_VICTORY_PHASE8_VALIDATION.json`
- `SHARED_VICTORY_PHASE8_VALIDATION.md`

### 驗證結果
以：
- `taiwan_green`
- `underground_church`

共享北京組織的案例：
- `count = 16`
- 驗證通過

## 目前仍未完成
- map marker / control color 還未真正用共享組織重算
- 共享組織對移動 / 瓦解的完整規則尚未最終拍板
- 印度研究分析室尚未實作
- 非暴力的持有 / 得牌深層限制尚未補完
