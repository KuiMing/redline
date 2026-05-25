# RED ARMY FACTION ABILITIES HELP UI PROOF

- date: 2026-05-25
- scenario: 正式 browser UI 透過 `/test/setup-red-army-abilities-proof` 建立紅軍行動階段狀態，檢查紅軍能力彈窗文字說明。
- screenshot: `docs/records/event-cards/RED_ARMY_FACTION_ABILITIES_HELP_UI_2026_05_25.png`
- game_id: `75e67806-4386-44d3-9bf8-e398ee8a1656`
- player_id: `red-proof`

## UI checks

- PASS: 紅軍能力彈窗顯示四個按鈕：`發動 統戰部`、`發動 政工部`、`發動 國安部`、`發動 中紀委`。
- PASS: 文字說明區顯示四項效果：
  - 統戰部：抽 1 張牌。
  - 政工部：選擇 1 名非紅軍玩家，將 1 張內宣放到其牌庫頂；同一目標每回合限 1 次。
  - 國安部：選擇其他玩家在紅軍組織 1 格內的 1 個牆內組織瓦解；同一目標每回合限 1 次。
  - 中紀委：可棄掉任意張手牌，然後抽等量的牌。
- PASS: 截圖來自正式 browser UI，不是 DOM/CSS fake proof。

## State evidence

- current_player: 紅軍
- turn_phase: action
- red_army_action_count: 0
- red_army_action_limit: 2
