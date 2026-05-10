# Negotiation Card Validation

- total: 1
- passed: 1
- failed: 0

## PASS — negotiation_draws_actor_and_one_target_only_and_grants_2_propaganda

```json
{
  "result": {
    "success": true
  },
  "actor_hand": [
    "actor_draw"
  ],
  "target_hand": [
    "target_draw"
  ],
  "third_hand": [],
  "actor_deck": [
    "actor_bottom"
  ],
  "target_deck": [
    "target_bottom"
  ],
  "third_deck": [
    "third_bottom",
    "third_should_not_draw"
  ],
  "actor_resources": {
    "money": 0,
    "propaganda": 2
  },
  "actor_discard": [
    "合作談判"
  ],
  "action_log_tail": [
    "[Turn 1] P1 played 合作談判"
  ]
}
```
