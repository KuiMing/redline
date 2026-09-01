# FACTION_ABILITY_PHASE10_SUPPORT_CARD_EFFECTS

日期：2026-05-07

## 本輪完成

把奧援卡從「可出現在購買區」再往前推進到：
- 依 `ruler` 判定區域主導者優待
- 依 I / II / III 級效果結算
- 真正接進 `play_card()` runtime

## 權威規則採用
使用者已明確補充：
- 區域主導者就是城鎮的 `ruler`

本輪即依此實作。

## 已完成

### 1. 區域主導者判定
#### server/game.py
新增：
- `_player_ruler_presence(player)`
- `_support_card_tier(player, card_name)`

規則：
- 讀玩家目前所有有組織城鎮
- 收集這些城鎮的 `ruler`
- 與 support card 的 `preferred_rulers` 比對
- tier = `1 + matched_count`，上限 3

因此：
- match 0 個 → I 級
- match 1 個 → II 級
- match 2 個 → III 級

### 2. support card effect resolver
#### server/game.py
新增：
- `_support_card_effect_text(card_name, tier, region_entry)`
- `_resolve_support_card_effect(card_name, tier, region_entry)`
- `_execute_support_card(player, card)`

### 3. 已接入 runtime 的奧援卡效果
目前先完成可驗證的三張：

#### 印度奧援
- I：放 1 張分神到紅軍棄牌堆
- II：放 2 張分神到紅軍棄牌堆
- III：放 3 張分神到紅軍棄牌堆

#### 英美奧援
- I：+1 資金
- II：+2 資金
- III：+3 資金

#### 南洋奧援
- I：抽 1 張，再棄 1 張
- II：抽 1 張
- III：抽 2 張

### 4. support card 已正式接到 `play_card()`
#### server/game.py::play_card()
- 若 `effective_type == 'support'`
- 直接走 `_execute_support_card(...)`
- 不再進 action card engine

## 驗證
新增：
- `scripts/validate/validate_support_card_effects_runtime.py`

輸出：
- `SUPPORT_CARD_EFFECTS_RUNTIME_VALIDATION.json`
- `SUPPORT_CARD_EFFECTS_RUNTIME_VALIDATION.md`

### 驗證結果
- total: 3
- passed: 3
- failed: 0

### 已驗證內容
1. `印度奧援` 在 III 級時會往紅軍棄牌堆放 3 張分神
2. `英美奧援` 在 II 級時會獲得 2 點資金
3. `南洋奧援` 在 I 級時會抽 1 棄 1，淨手牌變化正確

## 目前限制
- 尚未完整覆蓋所有奧援卡效果
- 尚未把隨機 18 張奧援卡混入正式購買區牌庫
- 前端支援卡 UI / 實戰截圖仍待補
