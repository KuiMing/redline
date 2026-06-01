# 紅軍事件階段：紅軍奧援手牌按鈕停用 UI 驗證

日期：2026-06-01

## 問題

玩家在紅軍的事件階段點手牌 `紅軍奧援` 的「行動」按鈕時，後端回傳 `Not in ACTION phase`。這表示前端在 EVENT 階段仍讓手牌資源／行動按鈕可點，容易誤導玩家。

## 修正後行為

- EVENT 階段：手牌下方「資源」「行動」按鈕停用，游標為 `not-allowed`，並提供 title 提示：`目前仍在事件階段，請先按「開始購買階段」再打出手牌。`
- ACTION / 購買階段：當前玩家且無待選擇效果時，手牌按鈕恢復可用。
- 紅軍能力按鈕不受此限制：紅軍仍可在購買階段前的 EVENT / ACTION 自行發動紅軍能力。

## 正式 UI proof

場景由 `/test/setup-support-proof` 建立：

- `support_name`: `紅軍奧援`
- `turn_phase`: `event`
- `player_name`: `紅軍`
- `faction_id`: `red_army`

Browser console evidence：

```json
{
  "current": "紅軍",
  "setupPhase": "event",
  "statePhase": "event",
  "buttons": [
    {
      "card": "紅軍奧援",
      "mode": "resource",
      "text": "資源",
      "disabled": true,
      "opacity": "0.42",
      "cursor": "not-allowed"
    },
    {
      "card": "紅軍奧援",
      "mode": "action",
      "text": "行動",
      "disabled": true,
      "opacity": "0.42",
      "cursor": "not-allowed"
    }
  ]
}
```

Screenshot：`RED_SUPPORT_EVENT_PHASE_HAND_BUTTON_GATING_UI_2026_06_01.png`
