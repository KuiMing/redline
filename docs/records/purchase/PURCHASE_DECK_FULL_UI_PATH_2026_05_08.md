# PURCHASE_DECK_FULL_UI_PATH_2026_05_08

日期：2026-05-08

## 本輪完成

補出完整 purchase deck 主畫面截圖路徑，不再依賴單張 support card 測試入口。

## 新增測試入口
### server/main.py
新增：
- `POST /test/setup-purchase-deck-ui`

用途：
- 建立一般 runtime 購買區畫面
- 保留完整常設 6 張購買區
- 讓主畫面截圖能驗證 buy 後的 deck 補牌

## 截圖結果
### 截圖 1：before
- `purchase_before`：
  - 宣傳家
  - 思想家
  - 資助者
  - 資本家
  - 分神（常設）
  - 內鬥（常設）

### 截圖 2：after
- 買走 `宣傳家` 後
- `purchase_after` 變成：
  - 思想家
  - 資助者
  - 資本家
  - 分神（常設）
  - 內鬥（常設）
  - 印度奧援

## 結論
這證明：
- 常設 6 張購買區已在主畫面成立
- 購買後會從 purchase deck 真正補進新牌
- 而且補進來的 support card（本次為 `印度奧援`）能在 UI 上直接可見

## 產物
- `purchase_deck_full_ui_before.png`
- `purchase_deck_full_ui_after.png`
- `PURCHASE_DECK_FULL_UI_BATTLESHOT.json`
