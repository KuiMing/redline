# Era Effects Runtime Validation

- Date: 2026-05-26
- Summary: 5/5 passed

## PASS: mongolia_adds_internal_conflict_with_static_supply_cap

```json
{
  "rule": "蒙古時代關卡 activation effect 將內鬥加入蒙古棄牌堆，但最多消耗既有 static supply。",
  "active_eras": [
    "mongolia"
  ],
  "discard_internal_conflict": 1,
  "supply_before": 1,
  "supply_after": 0,
  "runtime_effects": {
    "red_suppression": {
      "type": "add_static_cards_to_discard",
      "added": {
        "actor": 1
      }
    },
    "revolution_counterattack": {
      "type": "hand_card_resource_bonus",
      "status": "active_modifier_or_pending_runtime"
    }
  }
}
```

## PASS: taiwan_adds_internal_conflict_to_discard

```json
{
  "rule": "臺灣時代關卡觸發時，將內鬥加入臺灣棄牌堆並消耗 static supply。",
  "active_eras": [
    "taiwan"
  ],
  "discard_internal_conflict": 1,
  "supply_after": 0,
  "runtime_effects": {
    "red_suppression": {
      "type": "add_static_cards_to_discard",
      "added": {
        "actor": 1
      }
    },
    "revolution_counterattack": {
      "type": "gain_resource_on_build_in_region",
      "status": "active_modifier_or_pending_runtime"
    }
  }
}
```

## PASS: manchuria_adds_distraction_to_discard

```json
{
  "rule": "滿洲時代關卡 activation effect 將分神加入滿洲棄牌堆並消耗 static supply。",
  "active_eras": [
    "manchuria"
  ],
  "discard_distraction": 1,
  "supply_after": 0,
  "runtime_effects": {
    "red_suppression": {
      "type": "add_static_cards_to_discard",
      "added": {
        "actor": 1
      }
    },
    "revolution_counterattack": {
      "type": "inspect_deck_top_and_reorder",
      "status": "active_modifier_or_pending_runtime"
    }
  }
}
```

## PASS: kazakh_immediate_draw_two_on_activation

```json
{
  "rule": "哈薩克時代關卡觸發時，哈薩克立即抽 2 張牌。",
  "active_eras": [
    "kazakh"
  ],
  "hand_before": 5,
  "hand_after": 7,
  "runtime_effects": {
    "red_suppression": {
      "type": "restrict_ignore_distance_build",
      "status": "active_modifier_or_pending_runtime"
    },
    "revolution_counterattack": {
      "type": "draw",
      "drawn": {
        "actor": [
          "樂捐者",
          "追隨者"
        ]
      }
    }
  }
}
```

## PASS: hong_kong_armed_purchase_cost_reduced_by_two_money

```json
{
  "rule": "香港時代關卡生效時，香港購買武裝類卡牌費用減 2 資金；武裝小隊原價 3 資金，1 資金可購買。",
  "buy_result": {
    "success": true
  },
  "remaining_money": 0,
  "discard_armed": 1,
  "active_era_effects": [
    {
      "id": "hong_kong",
      "name": "[香港]香港人被自殺",
      "trigger": {
        "type": "count_only",
        "camp": "hong_kong",
        "region": "hong_kong",
        "count": 10
      },
      "duration": {
        "type": "turns",
        "value": 2
      },
      "remaining": 2,
      "effects": {
        "red_suppression": {
          "type": "bonus_discard_on_red_card",
          "player_faction": "red_army",
          "target_camp": "hong_kong",
          "card_types": [
            "spy"
          ],
          "discard_count": 1,
          "duration": 2
        },
        "revolution_counterattack": {
          "type": "reduce_purchase_cost",
          "target_camp": "hong_kong",
          "card_types": [
            "armed"
          ],
          "resource": "money",
          "amount": 2,
          "duration": 2
        }
      }
    }
  ]
}
```
