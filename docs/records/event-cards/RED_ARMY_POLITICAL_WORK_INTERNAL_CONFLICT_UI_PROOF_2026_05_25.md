# Red Army 政工部：內鬥 UI Proof (2026-05-25)

- Scope: 政工部改為將常設牌 `內鬥` 放到目標玩家牌庫頂，不再使用不存在／非常設的 `內宣`。
- Browser URL: `http://127.0.0.1:8000/`
- Scenario: `/test/setup-red-army-abilities-proof` 建立正式 UI 狀態，透過原 UI 點擊 `發動 政工部`，再選擇 `自由派` 目標。

## Screenshots

- Help UI: `docs/records/event-cards/RED_ARMY_POLITICAL_WORK_INTERNAL_CONFLICT_HELP_UI_2026_05_25.png`
- Result UI: `docs/records/event-cards/RED_ARMY_POLITICAL_WORK_INTERNAL_CONFLICT_RESULT_UI_2026_05_25.png`

## PASS evidence

- 說明文字顯示：`政工部：選擇 1 名非紅軍玩家，將 1 張內鬥放到其牌庫頂；同一目標每回合限 1 次。`
- 發動結果顯示：`政工部結果：已將 內鬥 放到 自由派 的牌庫頂`
- Browser state evidence:
  - `static_purchase_supply['內鬥'] = 0`
  - `自由派 deck_count = 1`
  - `red_army_action_count = 1`
  - `pending_choice = null`
  - 常設購買區 `內鬥` 購買按鈕 disabled = true

## Runtime validator

- `scripts/validate_red_army_faction_abilities.py` now covers:
  - 政工部 topdeck `內鬥` and decrements static supply.
  - `內鬥` static supply empty: no card is created/topdecked.
