# FACTION_ABILITY_PHASE9_INDIA_RESEARCH_ROOM_SUPPORT

日期：2026-05-07

## 本輪完成

把上一輪建立的 `data/cards/support_taxonomy.v1.1.json` 真正接進 `印度研究分析室` 的 engine 判定，讓限制不再只依賴 action card type 猜測。

## 已完成

### 1. Game 載入 support taxonomy
#### server/game.py
新增載入：
- `SUPPORT_CARDS_PATH`
- `SUPPORT_TAXONOMY_PATH`
- `self.support_cards`
- `self.support_taxonomy`

### 2. support taxonomy helper
#### server/game.py
新增：
- `_support_taxonomy_entry(card_name)`
- `_is_support_card(card)`

### 3. `印度研究分析室` 改吃 support taxonomy
#### server/game.py
- `_is_india_flag_card(card)` 現在會先查 support taxonomy
- 若 support taxonomy 有定義：
  - 直接吃 `counts_as_flag_card`
- 若查不到 support taxonomy：
  - 才 fallback 到舊的 action card type 判定

### 4. 持有 / 購買 / 得牌限制正式落到 support cards
#### server/game.py
新增：
- `_can_player_gain_flag_card(player, card)`

規則：
- 若玩家沒有 `印度研究分析室`：放行
- 若牌不是 support card：放行
- 若牌是 support card 且為 `印度奧援`：放行
- 若牌是 support card 但不是印度旗類：
  - 擋下並回：`印度研究分析室：不能持有印度旗幟以外的旗幟卡`

### 5. 限制入口
#### server/game.py::buy_card()
- 購買 support card 時會檢查 `_can_player_gain_flag_card(...)`

#### server/effect_engine.py
- `gain_from_discard`
- `gain_any_from_discard`

現在從棄牌堆回收 support card 時，也會檢查 `_can_player_gain_flag_card(...)`

## 驗證
新增：
- `scripts/validate_india_research_room_support_taxonomy.py`

輸出：
- `INDIA_RESEARCH_ROOM_SUPPORT_TAXONOMY_VALIDATION.json`
- `INDIA_RESEARCH_ROOM_SUPPORT_TAXONOMY_VALIDATION.md`

### 驗證結果
- total: 4
- passed: 4
- failed: 0

### 已驗證內容
1. `印度奧援` 會被 taxonomy 判成 `is_india_flag = true`
2. `tibet_dehradun` 可正常購買 `印度奧援`
3. `tibet_dehradun` 會被禁止購買 `英美奧援`
4. `tibet_dehradun` 會被禁止從棄牌堆取得 `英美奧援`

## 結論
`印度研究分析室` 現在已不只會給第一次打出印度旗幟 `+2 money`，
也開始真正限制 support card 層的：
- 購買
- 得牌 / 回收

而且資料基礎已經改成 support taxonomy，不再只是純靠 action card type 猜測。
