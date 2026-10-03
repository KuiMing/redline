# Event Effect Vocabulary (v1.1)

This document defines the **allowed structured effect types** for event cards.
All events in `events_structured.v1.1.json` must use ONLY these types.

---

## ✅ Trigger Types

| type | description | parameters |
|------|------------|------------|
| play_card_with_money | Player played a card that grants money | count |
| play_card_with_propaganda | Player played a card that grants propaganda | count |
| build_organization | Player built organization | count, scope |
| move_organization | Player moved organization | count |
| use_faction_ability | Player used faction ability | count |

---

## ✅ Success / Failure Effect Types

| type | description | parameters |
|------|------------|------------|
| draw | Player draws cards | count |
| gain_card | Player gains a specific card | card, count |
| discard_self | Current player discards cards | count |
| discard_random | Target discards random cards | count |
| red_dissolve | Red army dissolves organization | count, scope |
| add_internal_conflict | Add 內鬥 cards | count |
| add_distraction | Add 分神 cards | count |
| move | Allow additional moves | count |
| reduce_cost | Reduce purchase cost | amount, duration |
| restrict_build | Restrict building ability | duration |
| ignore_distance | Ignore distance for building | duration |
| cancel_card | Cancel a played card | none |
| none | No effect | none |

---

## ✅ Per-player missions

Every `mission` event is judged **per non-Red player** (`trigger.each_non_red_player: true`): each player
tracks their own progress toward `trigger.count`, and each player's success/failure effect applies only to
that player. All outcomes are settled when the Red Army turn ends (see `rules.md`).

---

## ✅ Rule

- No new effect types may be introduced without updating this file.
- Effects must be machine-executable (no natural language logic).
- All parameters must be explicit.

---

This ensures:
- Predictable engine behavior
- No natural language parsing
- Deterministic event resolution
