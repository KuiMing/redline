# FACTION_ABILITY_PHASE10_SUPPORT_CARD_EFFECTS_TIANFANG

日期：2026-05-08

## 本輪完成

把 `天方奧援` 接進 support card runtime，完成目前最後一張尚未落地的主支援卡語義第一版。

## 已完成

### 天方奧援
#### server/game.py
新增：
- III：`force_discard_near`, `count=2`, `random=true`
- II：`force_discard_near`, `count=1`, `random=true`
- I：`force_discard_near`, `count=1`, `random=false`

### 執行語義
#### server/game.py::_execute_support_card()
新增 `force_discard_near`：
- 目前先以 MVP 語義實作
- 從第一個可用對手開始處理
- I 級：固定棄 1（先取 index 0）
- II / III：隨機棄牌

## 驗證
更新：
- `scripts/validate_support_card_effects_runtime.py`

### 最新結果
- total: 7
- passed: 7
- failed: 0

### 新增覆蓋
- `天方奧援` I 級：成功讓對手從 2 張手牌變成 1 張

## 備註
- 這一版仍是 MVP：
  - 尚未做「由您隨機選」與「由該玩家選」的前端互動 UI
  - 目前先以 engine 可結算 / 可驗證優先
- 但 support card runtime 主骨架到這一步已經很接近完整，可進一步考慮正式 purchase deck 混牌與 UI 精修
