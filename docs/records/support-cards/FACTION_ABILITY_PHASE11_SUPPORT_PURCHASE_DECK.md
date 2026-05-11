# FACTION_ABILITY_PHASE11_SUPPORT_PURCHASE_DECK

日期：2026-05-08

## 本輪完成

把 support cards 從固定展示，推進到正式 purchase deck 模式第一版。

## 已完成

### 1. 購買區牌庫
#### server/game.py
新增：
- `self.purchase_deck`
- `_initial_purchase_deck()`
- `_draw_purchase_cards(count)`

### 2. 依 rules.md 第一版落地
目前 purchase deck 組成：
- 隨機 18 張奧援卡
- 隨機 35 張非起始牌一般行動卡

總共：
- 53 張 purchase deck

### 3. 常設購買區
目前 `purchase_area` 固定常設 6 張：
- 宣傳家
- 思想家
- 資助者
- 資本家
- 分神
- 內鬥

### 4. 隨機購買區
- 由 `purchase_deck` 額外抽出 5 張補在常設區之後
- 常設區前 6 格不會被隨機牌取代

### 5. 補牌時機
#### server/game.py::_end_turn()
- 不再是買完立即補
- 改成玩家行動結束時，在 `_end_turn()` 內統一補滿隨機購買區

## 驗證
新增：
- `scripts/validate_support_purchase_deck_runtime.py`

輸出：
- `SUPPORT_PURCHASE_DECK_RUNTIME_VALIDATION.json`
- `SUPPORT_PURCHASE_DECK_RUNTIME_VALIDATION.md`

### 驗證結果
- total: 5
- passed: 5
- failed: 0

### 已驗證內容
1. `purchase_deck` 已存在
2. 初始 `purchase_area` 長度為 4（常設區）
3. 初始 `purchase_deck.draw_pile` 長度為 53
4. 其中 support card 數量為 18
5. 買走一張後會自動補 1 張，`purchase_area` 長度維持 4

## 備註
- 目前這一版是「常設區 + purchase deck」混合模式
- 還沒完全重現 rules.md 的完整展示方式（例如分神 / 內鬥常設展示是否也要回來）
- 但 support purchase deck 這條主幹已正式進 runtime，可作為後續 UI / 截圖驗證基礎
