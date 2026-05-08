# FACTION_ABILITY_PHASE11_SUPPORT_PURCHASE_DECK_UI

日期：2026-05-08

## 本輪完成

補齊常設購買區 6 種卡，並做正式 purchase deck UI 截圖驗證。

## 已完成

### 1. 常設購買區補齊 6 種
#### server/game.py
`_initial_purchase_area()` 現在固定包含：
- 宣傳家
- 思想家
- 資助者
- 資本家
- 分神
- 內鬥

符合 `rules.md` 的常設 6 種卡牌要求。

### 2. 主畫面顯示補強
#### static/app.js
- `分神`
- `內鬥`

現在在購買區會顯示成：
- `分神（常設）`
- `內鬥（常設）`

使常設卡與抽出的購買區牌更容易辨識。

### 3. purchase deck UI 截圖
產出：
- `support_purchase_deck_ui_before.png`
- `support_purchase_deck_ui_after.png`
- `SUPPORT_PURCHASE_DECK_UI_BATTLESHOT.json`

## 驗證
更新：
- `scripts/validate_support_purchase_deck_runtime.py`

### 最新結果
- total: 7
- passed: 7
- failed: 0

### 已驗證內容
1. `purchase_deck` 存在
2. 初始 `purchase_area` 長度為 6
3. `purchase_deck.draw_pile` 長度為 53
4. 其中 support card 為 18 張
5. 常設區含 `分神`
6. 常設區含 `內鬥`
7. 買走一張後會自動補牌，長度維持 6

## 備註
- `/test/setup-india-support-purchase` 仍是單張 support 測試入口，所以該入口主畫面截圖會只看到指定 support 卡，這是測試入口特性，不代表一般 runtime 的完整常設區畫面。
- 若要驗證一般 runtime 的完整 6 常設 + 抽牌區，下一步應補一個專門給 purchase deck UI 的 setup / screenshot 路徑。
