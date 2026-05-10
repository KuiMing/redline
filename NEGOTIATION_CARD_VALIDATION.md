# Negotiation Card Validation

- total: 2
- passed: 2
- failed: 0

## PASS — negotiation_default_target_does_not_draw_all_players_and_grants_2_propaganda

```json
{
  "result": {
    "success": true
  },
  "hands": {
    "p1": [
      "actor_draw"
    ],
    "p2": [
      "p2_draw"
    ],
    "p3": []
  },
  "decks": {
    "p1": [
      "actor_bottom"
    ],
    "p2": [
      "p2_bottom"
    ],
    "p3": [
      "p3_bottom",
      "p3_draw"
    ]
  },
  "resources": {
    "p1": {
      "money": 0,
      "propaganda": 2
    },
    "p2": {
      "money": 0,
      "propaganda": 0
    },
    "p3": {
      "money": 0,
      "propaganda": 0
    }
  },
  "discard": {
    "p1": [
      "合作談判"
    ],
    "p2": [],
    "p3": []
  },
  "action_log_tail": [
    "[Turn 1] P1 played 合作談判"
  ]
}
```

## PASS — negotiation_can_choose_draw_target_in_four_player_game

```json
{
  "result": {
    "success": true
  },
  "target_player_id": "p4",
  "hands": {
    "p1": [
      "actor_draw"
    ],
    "p2": [],
    "p3": [],
    "p4": [
      "p4_draw"
    ]
  },
  "decks": {
    "p1": [
      "actor_bottom"
    ],
    "p2": [
      "p2_bottom",
      "p2_draw"
    ],
    "p3": [
      "p3_bottom",
      "p3_draw"
    ],
    "p4": [
      "p4_bottom"
    ]
  },
  "resources": {
    "p1": {
      "money": 0,
      "propaganda": 2
    },
    "p2": {
      "money": 0,
      "propaganda": 0
    },
    "p3": {
      "money": 0,
      "propaganda": 0
    },
    "p4": {
      "money": 0,
      "propaganda": 0
    }
  },
  "discard": {
    "p1": [
      "合作談判"
    ],
    "p2": [],
    "p3": [],
    "p4": []
  },
  "action_log_tail": [
    "[Turn 1] P1 played 合作談判"
  ]
}
```
