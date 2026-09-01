# PURCHASE ALIGNMENT STATUS 2026-05-10

## 本次處理目標
修正「常設購買區」與「隨機購買區」卡牌視覺未對齊的問題，並產出可直接檢查的截圖證據。

## 已完成修改

### 1. `static/style.css`
已調整 command 區三欄版面：

- 原本：`grid-template-columns: 300px 460px 460px;`
- 後續改為：`grid-template-columns: 312px 460px 460px;`

說明：
- `312px`：常設購買區 / 控制欄
- `460px`：隨機購買區
- `460px`：手牌欄
- 312 + 460 + 460 + padding 24 + gap 24 = 1280，剛好符合 1280px 舞台寬度

已調整購買區標題與卡牌起始垂直節奏：

- `#purchaseSection` 的 `gap` 從 `8px` 改為 `0`
- 新增：
  - `#purchaseSection .panel-title,`
  - `#randomMarketPanel .panel-title { margin-bottom: 14px; }`

### 2. `scripts/validate/validate_purchase_section_alignment.py`
已補強驗證腳本，避免只驗證「標題對齊」卻忽略「卡牌本體對齊」。

現在驗證包含：
- `static_purchase_title_aligns_with_random_market_title`
- `static_purchase_first_card_top_aligns_with_random_market_first_card`
- `purchase_zones_populated_for_visual_comparison`

## 最新驗證結果
重新執行：

```bash
python3 scripts/validate/validate_purchase_section_alignment.py
```

結果：

- total: 3
- passed: 3
- failed: 0

最新驗證檔：
- `docs/records/purchase/PURCHASE_SECTION_ALIGNMENT_VALIDATION.json`
- `docs/records/purchase/PURCHASE_SECTION_ALIGNMENT_VALIDATION.md`
- `docs/records/purchase/purchase_section_alignment_validation.png`

## 最新量測結果
來自 `docs/records/purchase/PURCHASE_SECTION_ALIGNMENT_VALIDATION.json`：

- 常設第一張卡：
  - `x = 21`
  - `y = 250`
- 隨機第一張卡：
  - `x = 345`
  - `y = 250`
- `top_delta_px = 0`

說明：
- 兩區位於不同欄位，所以 `x` 不會相同
- 本次修正目標是讓「各自欄位中的第一張卡上緣」對齊
- 目前此目標已達成

## 目前可直接檢查的截圖
- `docs/records/purchase/purchase_section_alignment_validation.png`

## 如果後續還要再調
可能的下一步：
1. 如果使用者希望兩區看起來像同一個大購買區的左右半部，可再改整體欄位節奏與 panel 視覺結構
2. 如果需要，也可以補「修前 / 修後」對照截圖
3. 若還有主觀視覺差異，可再做更細的卡片左側內距與 panel padding 微調
