# PURCHASE_DECK_STATIC_SLOT_FIX_2026_05_08

日期：2026-05-08

## 問題
使用者指出：
- 宣傳家是常設卡牌
- 印度奧援不是
- 不應該補到常設位置

這是正確的。先前那條 UI 截圖路徑把常設區與隨機區混為同一層 buy 補位，造成錯誤示範。

## 修正
### server/game.py
- 新增 `_static_purchase_cards()`
- 常設 6 張固定為：
  - 宣傳家
  - 思想家
  - 資助者
  - 資本家
  - 分神
  - 內鬥
- `buy_card()` 現在禁止購買前 6 格：
  - 回傳 `Static purchase cards cannot be bought from random slot logic`
- 買走隨機區牌後，只補隨機區，維持總長度 `6 + 5 = 11`

### server/main.py
- `POST /test/setup-purchase-deck-ui`
  現在會補滿完整主畫面用的：
  - 6 常設 + 5 隨機購買區

### static/app.js
- 前 6 格顯示 `（常設）`
- 其後顯示 `（隨機）`

## 修正後截圖結果
### before
- 前 6 格：常設卡
- 後 5 格：隨機區

### after
- 買掉第 7 格 `地下黨`
- 補進第 11 格的是 `武裝集團`
- 常設卡位置不動

## 產物
- `purchase_deck_full_ui_before_fixed.png`
- `purchase_deck_full_ui_after_fixed.png`
- `PURCHASE_DECK_FULL_UI_BATTLESHOT_FIXED.json`
