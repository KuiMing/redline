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
目前 `purchase_area` 仍保留常設 4 張：
- 宣傳家
- 思想家
- 資助者
- 資本家

然後會再從 `purchase_deck` 抽牌補入：
- 買走一張後，自動補 1 張

### 4. buy 後補牌
#### server/game.py::buy_card()
- `purchase_area.pop(index)` 後
- 會自動 `extend(self._draw_purchase_cards(1))`

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
