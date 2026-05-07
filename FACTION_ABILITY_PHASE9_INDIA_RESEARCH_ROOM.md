# FACTION_ABILITY_PHASE9_INDIA_RESEARCH_ROOM

日期：2026-05-07

## 本輪完成

把西藏（德拉敦）的 `印度研究分析室` 接進 engine，先落地到可驗證、最小且不亂猜的版本。

## 採用的保守規則解讀
資料目前只明確寫到：
- `禁止持有印度旗幟以外的旗幟卡；當您每回合第1次打出印度旗幟時，獲得2點資金。`

在使用者後續明確澄清前，曾短暫採用「某些 action card type 近似旗幟」的 MVP 解讀；
但目前已被更新的權威解釋覆蓋：

> 在所有奧援卡中，只能持有 `印度奧援`；其他奧援卡一律不能持有。

因此這份文件中最初那個 action-card-type 近似解讀，現在只應視為過渡歷史，不再作為最終規則依據。

## 已完成

### 1. 印度旗幟類型判定
#### server/game.py
新增：
- `_is_india_flag_card(card)`

目前最終定義已收斂為：
- 若 support taxonomy 明確標成 `counts_as_flag_card=true`（目前即 `印度奧援`）才算
- 一般 action cards 不再被視為印度旗幟

### 2. ability presence helper
#### server/game.py
新增：
- `_player_has_india_research_room(player)`

### 3. 第一次打出印度旗幟 +2 資金
#### server/game.py::play_card()
- 若玩家有 `印度研究分析室`
- 且本回合第一次打出印度旗幟類牌
- 則：
  - `+2 money`
  - 並設置 `turn_log['india_flag_money_triggered'] = True`

### 4. turn log 支援
#### server/game.py::_new_turn_log()
新增：
- `india_flag_money_triggered`

## 驗證
新增：
- `scripts/validate_india_research_room.py`

輸出：
- `INDIA_RESEARCH_ROOM_VALIDATION.json`
- `INDIA_RESEARCH_ROOM_VALIDATION.md`

### 驗證結果
- total: 4
- passed: 4
- failed: 0

### 已驗證內容
1. 非 support 一般行動卡打出時：
   - 不會被錯算成印度旗幟額外拿錢
2. 非 support 一般行動卡購買：
   - 仍允許
3. 非 support 一般行動卡從棄牌堆取得：
   - 仍允許

## 備註
- 這份第一版文件已被後續 `SUPPORT_CARD_TAXONOMY` 與使用者權威規則澄清所收斂
- 現在最終方向是：
  - 只在奧援卡集合內處理印度旗限制
  - `印度奧援` 合法
  - 其他奧援卡不合法
