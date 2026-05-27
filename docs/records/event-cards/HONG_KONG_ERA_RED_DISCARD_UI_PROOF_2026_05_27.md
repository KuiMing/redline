# Hong Kong Era Red Discard UI Proof — 2026-05-27

- Scenario: `[香港]香港人被自殺` 紅軍壓制 `bonus_discard_on_red_card`
- Endpoint: `POST /test/setup-hong-kong-era-red-discard-proof`
- UI screenshots:
  - `HONG_KONG_ERA_RED_DISCARD_CHOICE_UI_2026_05_27.png`
  - `HONG_KONG_ERA_RED_DISCARD_RESOLVED_UI_2026_05_27.png`

## UI evidence

- Red Army browser used the real hand `行動` button to play `內應間諜`.
- The original spy target choice appeared as the existing `卡牌選擇` modal and listed `香港｜天津`.
- After resolving the spy target, the Hong Kong browser received the follow-up existing card-choice modal:
  - Title: `卡牌選擇`
  - Source: `[香港]香港人被自殺`
  - Prompt: `[香港]香港人被自殺：紅軍打出 內應間諜，請棄掉 1 張手牌。`
  - Visible choices: `香港目標手牌`, `香港保留手牌`
- After choosing `香港目標手牌`, the modal closed and the main UI still showed the active era panel `條件已達成｜剩餘 2 回合` plus the remaining hand card `香港保留手牌`.

## Runtime evidence after resolve

```json
{
  "pending_choice": null,
  "action_log": [
    "[Turn 1] 紅軍 played 內應間諜",
    "[Turn 1] 紅軍 dissolved 1 organization from 香港 at 天津",
    "[Turn 1] Era [香港]香港人被自殺: 香港 must discard 1 after Red Army played 內應間諜",
    "[Turn 1] 紅軍 used [香港]香港人被自殺 to force 香港 to discard 香港目標手牌"
  ],
  "hong_kong_after": {
    "hand": ["香港保留手牌"],
    "discard_pile": ["香港目標手牌"],
    "orgs": {}
  },
  "red_army_after": {
    "discard_pile": ["內應間諜"],
    "orgs": {"北京": 1}
  },
  "active_era": "[香港]香港人被自殺",
  "remaining": 2
}
```

## Notes

This proof reuses the existing pending-choice/card-choice UI path. No new intelligence-network target-highlight path was created.
