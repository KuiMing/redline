# Action Card Effect Vocabulary (v1.1)

This file defines the allowed structured effect types for action cards.
All structured action cards must use ONLY these effect types.

---

## ✅ Card Flow Effects

| type | description | parameters |
|------|------------|------------|
| draw | Draw cards | count |
| discard_self | Current player discards cards | count |
| discard_random | Discard random cards | count |
| gain_from_discard | Gain card from discard pile with max cost | max_cost |
| gain_any_from_discard | Gain any card from discard pile | none |
| peek_deck | View top N cards of deck | count |
| reorder_deck | Reorder top N cards of deck | count |
| topdeck_to_hand | Move top deck card to hand | none |

---

## ✅ Conditional Effects

| type | description | parameters |
|------|------------|------------|
| conditional_draw | Draw cards if condition met | condition, count |
| conditional_bonus | Gain resource if condition met | condition, money, propaganda |
| conditional_trash_bonus | Gain resource if trash condition met | money, propaganda |

---

## ✅ Control Effects

| type | description | parameters |
|------|------------|------------|
| cancel_card | Cancel a played card | none |
| force_discard | Target player discards | count |
| shared_draw | Both players draw | count |

---

## ✅ Action Modifiers

| type | description | parameters |
|------|------------|------------|
| extend_build_range | Increase build distance | amount |
| extra_move | Additional movement actions | count |

---

## ✅ Rule

- No new effect types may be introduced without updating this file.
- Effects must be machine-executable.
- All parameters must be explicit and deterministic.

This vocabulary is binding for all structured action cards.
