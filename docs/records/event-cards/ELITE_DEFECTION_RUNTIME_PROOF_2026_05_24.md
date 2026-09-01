# 紅軍權貴出逃 Runtime Proof — 2026-05-24

## Scope
- Event: `紅軍權貴出逃`
- Raw alignment target from TODO.md: success is 「從手牌或棄牌移除 1 張」, not `discard_self`.
- Structured effect implemented: `trash_from_hand_or_discard`, `count: 1`.

## Validator coverage
`python3 scripts/validate/validate_event_cards_runtime.py` now includes:

- `test_elite_defection_trashes_from_hand_after_three_moves`
  - Sets event to `紅軍權貴出逃`.
  - Performs 3 legal organization moves.
  - Verifies pending choice key `trash_from_hand_or_discard`.
  - Chooses a hand card and verifies it leaves hand/discard and is returned to purchase deck/supply removal flow.

- `test_elite_defection_trashes_from_discard_after_three_moves`
  - Performs the same 3-move trigger.
  - Chooses a discard-pile card and verifies discard pile is emptied and the card is removed/returned via existing removal flow.

- `test_elite_defection_structured_matches_raw_rule`
  - Verifies base and duplicate structured event rows use:
    - trigger: `move_organization`, `count: 3`
    - success: `trash_from_hand_or_discard`, `count: 1`
    - failure: `discard_self`, `count: 1`

## Result
Runtime validator passed with 17 tests after adding the above coverage.
