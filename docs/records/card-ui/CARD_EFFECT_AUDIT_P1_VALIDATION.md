# Card Effect Audit P1 Validation

- total: 2
- passed: 2
- failed: 0

## PASS — 思想建設_action_mode_draws_one_card_from_raw_text

```json
{
  "result": {
    "success": true
  },
  "before_deck": [
    "牌庫底",
    "應抽到的牌"
  ],
  "hand_after": [
    "應抽到的牌"
  ],
  "deck_after": [
    "牌庫底"
  ],
  "discard_after": [
    "思想建設"
  ],
  "resources_after": {
    "money": 0,
    "propaganda": 0
  },
  "build_range_bonus": 1,
  "action_log_tail": [
    "[Turn 1] P1 played 思想建設"
  ],
  "expected_build_range_bonus": 1
}
```

## PASS — 誘導虛耗_action_mode_draws_one_card_from_raw_text

```json
{
  "result": {
    "success": true
  },
  "before_deck": [
    "牌庫底",
    "應抽到的牌"
  ],
  "hand_after": [
    "應抽到的牌"
  ],
  "deck_after": [
    "牌庫底"
  ],
  "discard_after": [],
  "resources_after": {
    "money": 0,
    "propaganda": 0
  },
  "build_range_bonus": 0,
  "action_log_tail": [
    "[Turn 1] 誘導虛耗 returned to purchase deck discard",
    "[Turn 1] P1 removed 誘導虛耗 and it returned to deck_discard",
    "[Turn 1] P1 played 誘導虛耗"
  ]
}
```
