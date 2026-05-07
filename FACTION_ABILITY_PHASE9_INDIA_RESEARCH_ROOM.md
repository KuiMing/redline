# FACTION_ABILITY_PHASE9_INDIA_RESEARCH_ROOM

日期：2026-05-07

## 本輪完成

把西藏（德拉敦）的 `印度研究分析室` 接進 engine，先落地到可驗證、最小且不亂猜的版本。

## 採用的保守規則解讀
資料目前只明確寫到：
- `禁止持有印度旗幟以外的旗幟卡；當您每回合第1次打出印度旗幟時，獲得2點資金。`

但 repo 裡沒有額外的 card metadata 明確標註「旗幟卡」子類。

因此本輪採用的 MVP 解讀是：
- 將 `transport / organization / spy / purge` 視為印度旗幟卡類別
- 先把「第一次打出印度旗幟 +2 資金」接進 engine
- 不額外亂加購買 / 得牌 / discard 攔截規則，避免超出明文

## 已完成

### 1. 印度旗幟類型判定
#### server/game.py
新增：
- `_is_india_flag_card(card)`

目前定義：
- `transport`
- `organization`
- `spy`
- `purge`

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
1. 第一次打出印度旗幟牌時：
   - 原卡資源 + `印度研究分析室` 額外 `+2 money`
2. 同回合第二張印度旗幟牌：
   - 不再重複拿額外 `+2 money`
3. 非印度旗幟牌購買：
   - 目前仍允許（本輪採保守實作，不擴張明文）
4. 從棄牌堆取得非印度旗幟牌：
   - 目前仍允許（同上）

## 備註
- 這一輪只實作「第一次打出印度旗幟 +2 資金」這條最可確定規則
- `禁止持有印度旗幟以外的旗幟卡` 之中的「旗幟卡」資料分類在 repo 仍不足，若要更進一步，需要先建立明確 card taxonomy，避免把一般非旗幟牌誤封禁
