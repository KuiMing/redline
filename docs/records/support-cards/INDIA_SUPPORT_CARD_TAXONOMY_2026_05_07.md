# INDIA_SUPPORT_CARD_TAXONOMY_2026_05_07

日期：2026-05-07

## 本輪完成

將 `data/cards/support_cards.v1.1.json` 先整理成可執行前置 taxonomy，避免之後在 `印度研究分析室` 上繼續靠自然語言硬猜。

## 新增
- `scripts/build_support_card_taxonomy.py`
- `SUPPORT_CARD_TAXONOMY.json`
- `SUPPORT_CARD_TAXONOMY.md`

## 本輪 taxonomy 結論

### 1. 奧援卡資料來源已確認
- source: `data/cards/support_cards.v1.1.json`
- 共整理出 9 種奧援卡分類：
  - 英美奧援
  - 東洋奧援
  - 南洋奧援
  - 印度奧援
  - 天方奧援
  - 歐洲奧援
  - 北國奧援
  - 臺灣奧援
  - 紅軍奧援

### 2. `印度奧援` 已被明確標成可計入 `counts_as_flag_card`
這是本輪最重要的落點。

- `counts_as_flag_card: true` 目前只對 `印度奧援` 開啟
- 目的：先讓 `印度研究分析室` 有一個不亂擴張的正式資料錨點
- 避免把所有奧援卡或所有一般卡都錯誤算成「印度旗幟卡」

### 3. 區域主導者優待已正規化
每張奧援卡現在都整理出：
- `preferred_rulers`
- `preferred_ruler_ids`

之後如果要把奧援卡真正接進 runtime / purchase_area / effect pipeline，這層可直接沿用。

### 4. tier effect 先做 bucket 分類
暫時依文字內容粗分成：
- `gain_resource`
- `draw`
- `disruption_or_dissolve`
- `dissolve`
- `build`
- `discard`
- `none`
- `unknown`

這一層不是最終 runtime effect schema，
但足夠作為之後正式結構化支援卡的橋接層。

## 對印度研究分析室的意義
現在我們至少有一個清楚的、repo 內真實存在的資料結論：

> `印度奧援` 是最應優先被視為「印度旗幟 / 印度旗類型」的正式 support card 類別。

因此後續若要把：
- 持有限制
- 購買限制
- 得牌限制
- 棄牌堆回收限制

接進 `印度研究分析室`，應優先以這份 taxonomy 為資料基礎，而不是直接猜 action card type。
