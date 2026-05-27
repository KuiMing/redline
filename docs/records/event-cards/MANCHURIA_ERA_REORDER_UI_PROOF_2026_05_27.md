# Manchuria Era Reorder UI Proof — 2026-05-27

- Scenario: `[滿洲]滿洲地方派系凝聚` 革命反撲 `inspect_deck_top_and_reorder`
- Endpoint: `POST /test/setup-manchuria-era-reorder-proof`
- UI screenshot: `MANCHURIA_ERA_REORDER_CHOICE_UI_2026_05_27.png`

## UI evidence

- Modal title: `卡牌選擇`
- Prompt: `檢視牌庫頂 7 張，請依序選擇 2 張放回牌庫頂。第一張會成為下一張抽到的牌。`
- Visible candidates: `第一張`、`第二張`、`第三張`、`第四張`、`第五張`、`第六張`、`第七張`
- Selection summary: `已選 2/2 張置頂（依點選順序放回牌庫頂）`
- Submit button: `確認置頂 2 張` enabled

## Runtime evidence after submit

```json
{
  "pending_choice": null,
  "last_action_result": {
    "success": true,
    "choice_key": "era_inspect_deck_top_and_reorder",
    "inspected_cards": [
      "第一張",
      "第二張",
      "第三張",
      "第四張",
      "第五張",
      "第六張",
      "第七張"
    ],
    "chosen_cards": [
      "第三張",
      "第一張"
    ],
    "deck_top": [
      "第三張",
      "第一張"
    ]
  },
  "action_log_tail": [
    "viewer gained 1 分神 from event",
    "Era [滿洲]滿洲地方派系凝聚: added 1 分神 to viewer discard",
    "viewer reordered deck top via [滿洲]滿洲地方派系凝聚: 第三張, 第一張"
  ]
}
```

## Static supply note

`分神` uses the existing static-supply path: one card was gained, supply became `0`, and extra requested copies were not created.
