# Tibet Era Red Multi-Discard Build UI Proof

- Date: 2026-05-28
- Scenario: `[藏國]藏國騷亂` red suppression, Red Army has 3 hand cards and a Tibet organization is at `列城`.
- Proof endpoint: `POST /test/setup-tibet-era-red-build-proof` with `resolve_discard=false`.

## Official UI evidence

- `TIBET_ERA_RED_MULTI_DISCARD_MODAL_UI_2026_05_28.png`
  - Official browser UI pending multi-card modal.
  - Modal text shows Red Army may discard any number of hand cards.
  - Snapshot evidence showed `已選 2/2 張（可選 1～2 張）` and button `確認棄掉 2 張並建立 2 個組織`.
- `TIBET_ERA_RED_MULTI_BUILD_MAP_UI_2026_05_28.png`
  - Official browser UI after confirming 2 discarded cards.
  - Strategic Map sidebar shows the era effect prompt: `已棄 2 張手牌，請依序選擇 2 個城鎮免費建立紅軍組織`.
  - Pending town choice reused the existing map/sidebar build pipeline for `era_red_build_near_target`.

## Runtime state evidence

```json
{
  "pending_choice": {
    "type": "town_choice",
    "choice_key": "era_red_build_near_target",
    "prompt": "[藏國]藏國騷亂：已棄 2 張手牌，請依序選擇 2 個城鎮免費建立紅軍組織。",
    "towns": ["吉爾吉特", "阿里"]
  },
  "red_hand": ["紅軍保留 UI proof"],
  "red_discard": ["紅軍棄牌 UI proof 一", "紅軍棄牌 UI proof 二"],
  "action_log_tail": ["[Turn 1] 紅軍 discarded 2 card(s) for [藏國]藏國騷亂"]
}
```

Note: browser vision analysis hit a 429 usage limit after screenshot capture, so proof is paired with browser snapshot/console state evidence instead of vision text.
