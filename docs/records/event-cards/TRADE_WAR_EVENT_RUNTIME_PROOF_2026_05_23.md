# 貿易戰加劇事件卡 Runtime Proof

日期：2026-05-23

## 範圍

本次依 TODO.md P0 規劃，修正 `貿易戰加劇` 與 raw card text 不一致處：

- Trigger：購買 `英美奧援` 或總購買費用 4 點以上的卡牌。
- Success：從自己的棄牌堆選 1 張牌置於牌庫頂。
- Failure：無效果。

## 實作重點

- `data/events_structured.v1.1.json`
  - `貿易戰加劇` 與 `貿易戰加劇（副本）` 改為 `buy_card` trigger。
  - success 改為 `topdeck_from_discard`。
- `server/game.py`
  - 新增購買事件 trigger 判定：指定卡名或原始總購買費用門檻。
  - 購牌完成後追蹤 `buy_card` 事件進度。
  - 新增 `topdeck_from_discard` effect，重用既有 `card_choice` pending choice 架構。
  - 新增 `event_topdeck_from_discard` pending choice resolution。
- `scripts/validate/validate_event_cards_runtime.py`
  - 新增成功路徑：購買 4 點卡後 pending choice，選購買卡置頂。
  - 新增負向路徑：購買 3 點非 `英美奧援` 卡不觸發。
  - 新增 structured data 對齊 raw rule 斷言。

## Validator proof

`python3 scripts/validate/validate_event_cards_runtime.py` 通過（14 passed），輸出寫入：

- `docs/records/event-cards/EVENT_CARDS_RUNTIME_VALIDATION.json`
- `docs/records/event-cards/EVENT_CARDS_RUNTIME_VALIDATION.md`

本次重點測項：

- `test_trade_war_purchase_trigger_topdecks_from_discard`
  - `choice_key`: `event_topdeck_from_discard`
  - `deck_top`: `四點行動`
  - `discard`: `['舊棄牌']`
- `test_trade_war_purchase_trigger_ignores_low_cost_non_anglo_support`
  - 事件進度維持 `count: 0`、`succeeded: False`
  - `pending_choice: None`
- `test_trade_war_purchase_trigger_accepts_anglo_support_by_name`
  - 購買 `英美奧援` 即使測試中 mock 成 0 費用，也會依卡名觸發。
  - `choice_key`: `event_topdeck_from_discard`
- `test_trade_war_structured_matches_raw_rule`
  - trigger = `{"type": "buy_card", "count": 1, "min_cost": 4, "card_names": ["英美奧援"]}`
  - success = `{"type": "topdeck_from_discard", "count": 1}`
