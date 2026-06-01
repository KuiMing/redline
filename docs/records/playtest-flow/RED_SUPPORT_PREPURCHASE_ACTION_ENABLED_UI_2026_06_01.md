# 紅軍奧援：開始購買階段前可按行動 UI 驗證

日期：2026-06-01

## 修正目標

紅軍在 EVENT 階段、尚未按「開始購買階段」前，`紅軍奧援` 應可直接按「行動」。先前修正把所有手牌按鈕都鎖到 ACTION 階段，導致不符合規則。

## 修正後行為

- 紅軍 EVENT 階段：`紅軍奧援` 的「行動」按鈕啟用，可按。
- 紅軍 EVENT 階段：`紅軍奧援` 的「資源」按鈕仍停用，因為資源玩法仍屬購買／ACTION 階段。
- 其他一般手牌仍維持 ACTION-only，避免在事件階段誤打一般手牌。
- 後端 `play_card` 允許紅軍在 EVENT 階段以 `action` 模式打出 `紅軍奧援`，並維持在 EVENT 階段產生 `red_support_target_player` 待選。

## Browser evidence

Before clicking：

```json
[
  {
    "mode": "resource",
    "text": "資源",
    "disabled": true,
    "opacity": "0.42",
    "cursor": "not-allowed"
  },
  {
    "mode": "action",
    "text": "行動",
    "disabled": false,
    "opacity": "1",
    "cursor": "pointer"
  }
]
```

Click result：

```json
{
  "phase": "event",
  "current": "紅軍",
  "choiceKey": "red_support_target_player",
  "prompt": "紅軍奧援：請選擇要將本牌放入哪位反共玩家的棄牌堆。",
  "hand": [],
  "logTail": ["[Turn 1] 紅軍 played 紅軍奧援"]
}
```

Screenshot：`RED_SUPPORT_PREPURCHASE_ACTION_ENABLED_UI_2026_06_01.png`
