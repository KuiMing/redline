# 貿易戰加劇 UI Proof

日期：2026-05-24

## 驗證目標

確認正式 browser UI 可承接 `貿易戰加劇` 的 runtime pending card choice：

1. 行動階段購買總費用 4 點的 `擴大戰果`。
2. 事件達成，UI 顯示卡牌選擇 modal。
3. Modal prompt 顯示「從棄牌堆選 1 張牌置於牌庫頂」。
4. 選擇 `擴大戰果` 後，modal 關閉，事件面板顯示成功已結算、進度 1/1。

## Browser UI proof

- Pending choice screenshot：`docs/records/event-cards/TRADE_WAR_UI_PENDING_CHOICE_2026_05_24.png`
  - 可見 `卡牌選擇 / 貿易戰加劇` modal。
  - Prompt：`貿易戰加劇：從棄牌堆選 1 張牌置於牌庫頂。`
  - 選項包含 `舊棄牌` 與 `擴大戰果`。
- Resolved screenshot：`docs/records/event-cards/TRADE_WAR_UI_RESOLVED_2026_05_24.png`
  - 無 choice modal 遮罩。
  - 事件面板：`貿易戰加劇`、`狀態：成功已結算`、`進度：1/1`。

## State / log proof

詳見 `docs/records/event-cards/TRADE_WAR_UI_PROOF_2026_05_24.json`。

重點狀態：

- `current_event.status`: `success`
- `current_event.progress`: `count=1`, `required=1`, `succeeded=true`, `settled=true`
- `pending_choice`: `null`
- `modal_display`: `none`
- `action_log`:
  - `[Turn 1] viewer bought 擴大戰果`
  - `[Turn 1] viewer placed 擴大戰果 on deck top via 貿易戰加劇`
- `viewer.deck_count`: `2`
- `viewer.discard_pile`: `["舊棄牌"]`

## 結論

UI 驗證通過：既有 pending card choice UI 可顯示並 resolve `event_topdeck_from_discard`，不需新增 target choice map highlight 或 UI 專用改動。
