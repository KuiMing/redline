# 地下黨 UI Screenshots（2026-05-18）

## Scope
- Card: `地下黨`
- Effect key: `underground_party`
- UI requirement: `card_choice` pending choice
- Purpose: prove the live UI reveals 3 purchase-deck cards, lets the acting player choose 1 card to hand, and returns/removes the other revealed cards through the purchase-deck/supply system.

## Fixture
- Endpoint: `POST /test/setup-underground-party`
- Acting player: `viewer`
- Phase: turn 1 action phase
- Starting hand: `地下黨`
- Purchase-deck reveal order: `宣傳家`, `合作談判`, `走漏風聲`
- Selected card during proof: `合作談判`

The fixture uses real named card records for the reveal candidates so the UI modal can show normal card faces. It intentionally includes `宣傳家` as a static supply card and `走漏風聲` as a random purchase-deck card to prove the unchosen cards return to their proper purchase system locations.

## Screenshots
1. `ACTION_CARD_UNDERGROUND_PARTY_UI_2026_05_18_01_START.png`
   - Command center before playing the card.
   - HUD shows action phase, hand count 1, resources 4/4.
   - Hand card is `地下黨`.

2. `ACTION_CARD_UNDERGROUND_PARTY_UI_2026_05_18_02_CHOICE_MODAL.png`
   - After clicking `地下黨` action.
   - `卡牌選擇` modal shows prompt: `地下黨：從購買區牌庫頂拿取3張牌，任選其中1張加入手牌，其餘移除。`
   - Modal candidates are `宣傳家`, `合作談判`, `走漏風聲`.

3. `ACTION_CARD_UNDERGROUND_PARTY_UI_2026_05_18_03_AFTER_HAND.png`
   - After choosing `合作談判`.
   - HUD shows hand count 1.
   - Hand card is now `合作談判`.

4. `ACTION_CARD_UNDERGROUND_PARTY_UI_2026_05_18_04_LOG.png`
   - Battle overview / log after resolution.
   - Viewer shows hand 1 and discard pile contains `地下黨`.
   - Event log shows reveal, play, unchosen-card returns, and chosen-card result.

## Runtime state evidence
Browser console state after choosing `合作談判`:

```json
{
  "pending_choice": null,
  "hand": ["合作談判"],
  "discard_pile": ["地下黨"],
  "action_log": [
    "[Turn 1] UI proof setup: viewer has 地下黨; purchase deck top reveals 宣傳家 / 合作談判 / 走漏風聲.",
    "[Turn 1] viewer revealed 3 cards for 地下黨",
    "[Turn 1] viewer played 地下黨",
    "[Turn 1] 宣傳家 returned to static purchase supply",
    "[Turn 1] 走漏風聲 returned to purchase deck discard",
    "[Turn 1] viewer chose 合作談判 via 地下黨"
  ]
}
```

## Verification
- `python3 -m pytest -q scripts/tests/test_action_card_regressions.py -k 'underground_party or underground'`
- `python3 -m compileall -q server/main.py`
- `curl -X POST /test/setup-underground-party` returned HTTP 200 and the expected fixture state.
- PNG header/dimension check:
  - `ACTION_CARD_UNDERGROUND_PARTY_UI_2026_05_18_01_START.png`: 1280x1740
  - `ACTION_CARD_UNDERGROUND_PARTY_UI_2026_05_18_02_CHOICE_MODAL.png`: 1280x1740
  - `ACTION_CARD_UNDERGROUND_PARTY_UI_2026_05_18_03_AFTER_HAND.png`: 1280x1740
  - `ACTION_CARD_UNDERGROUND_PARTY_UI_2026_05_18_04_LOG.png`: 1280x633
