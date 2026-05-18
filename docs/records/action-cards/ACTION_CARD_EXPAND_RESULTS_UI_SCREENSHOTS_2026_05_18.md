# 擴大戰果 UI Screenshots（2026-05-18）

## Scope
- Card: `擴大戰果`
- Effect key: `gain_any_from_discard`
- UI requirement: `card_choice` pending choice
- Purpose: prove the live UI lets the acting player choose any one card from their own discard pile and moves the chosen card to hand.

## Fixture
- Endpoint: `POST /test/setup-expand-results-proof`
- Acting player: `viewer`
- Phase: turn 1 action phase
- Starting hand: `擴大戰果`
- Starting discard pile: `宣傳家`, `合作談判`, `走漏風聲`
- Selected card during proof: `合作談判`

The fixture intentionally includes `合作談判` because its total purchase cost is 4 (`資金2+宣傳2`). The modal should still list it, proving `擴大戰果` has no `乘勝追擊`-style cost-3-or-less filter.

## Screenshots
1. `ACTION_CARD_EXPAND_RESULTS_UI_2026_05_18_01_START.png`
   - Command center before playing the card.
   - HUD shows action phase and hand count 1.
   - Hand card is `擴大戰果`.

2. `ACTION_CARD_EXPAND_RESULTS_UI_2026_05_18_02_CHOICE_MODAL.png`
   - After clicking `擴大戰果` action.
   - `卡牌選擇` modal shows all three discard candidates: `宣傳家`, `合作談判`, `走漏風聲`.
   - `合作談判` appears despite total cost 4.

3. `ACTION_CARD_EXPAND_RESULTS_UI_2026_05_18_03_AFTER_HAND.png`
   - After choosing `合作談判`.
   - HUD shows hand count 1.
   - Hand card is now `合作談判`.

4. `ACTION_CARD_EXPAND_RESULTS_UI_2026_05_18_04_LOG.png`
   - Battle overview / log after resolution.
   - Viewer shows hand 1 / discard 3.
   - Discard pile shows `宣傳家`, `走漏風聲`, `擴大戰果`.
   - Event log includes `viewer gained 合作談判 from discard via 擴大戰果`.

## Runtime state evidence
Browser console state after choosing `合作談判`:

```json
{
  "pending_choice": null,
  "hand": ["合作談判"],
  "discard_pile": ["宣傳家", "走漏風聲", "擴大戰果"],
  "discard_count": 3,
  "action_log": [
    "[Turn 1] UI proof setup: viewer has 擴大戰果; discard pile contains 宣傳家 / 合作談判 / 走漏風聲.",
    "[Turn 1] viewer may gain 1 card from discard",
    "[Turn 1] viewer played 擴大戰果",
    "[Turn 1] viewer gained 合作談判 from discard via 擴大戰果"
  ]
}
```

## Verification
- `python3 -m compileall -q server/main.py`
- PNG header/dimension check:
  - `ACTION_CARD_EXPAND_RESULTS_UI_2026_05_18_01_START.png`: 1280x1740
  - `ACTION_CARD_EXPAND_RESULTS_UI_2026_05_18_02_CHOICE_MODAL.png`: 1280x1740
  - `ACTION_CARD_EXPAND_RESULTS_UI_2026_05_18_03_AFTER_HAND.png`: 1280x1740
  - `ACTION_CARD_EXPAND_RESULTS_UI_2026_05_18_04_LOG.png`: 1280x633
