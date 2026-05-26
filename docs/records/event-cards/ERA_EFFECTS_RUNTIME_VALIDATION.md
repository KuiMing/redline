# Era Effects Runtime Validation

- Date: 2026-05-26
- Summary: 11/11 passed

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

## PASS: mongolia_propaganda_resource_card_bonus_adds_one_propaganda

```json
{
  "rule": "蒙古反撲效果：宣傳類手牌用於購買/資源時額外提供 1 宣傳。",
  "play_result": {
    "success": true
  },
  "resources_after": {
    "money": 0,
    "propaganda": 3
  },
  "era_effects_applied": [
    {
      "era": "mongolia",
      "type": "hand_card_resource_bonus",
      "resource": "propaganda",
      "amount": 1
    }
  ]
}
```

## PASS: uyghur_armed_play_grants_two_propaganda

```json
{
  "rule": "維吾爾反撲效果：每打出 1 張武裝類卡牌，獲得 2 宣傳。",
  "play_result": {
    "success": true,
    "pending_choice": true
  },
  "resources_after": {
    "money": 0,
    "propaganda": 2
  },
  "pending_choice": "armed_target_discard",
  "era_effects_applied": [
    {
      "era": "uyghur",
      "type": "gain_resource_on_play_card",
      "resource": "propaganda",
      "amount": 2
    }
  ]
}
```

## PASS: taiwan_build_in_taiwan_grants_one_propaganda

```json
{
  "rule": "臺灣反撲效果：在臺灣城鎮建立至少 1 個組織時，獲得 1 宣傳。",
  "town": "南投",
  "build_result": {
    "success": true
  },
  "resources_after": {
    "money": 0,
    "propaganda": 1
  },
  "era_effects_applied": [
    {
      "era": "taiwan",
      "type": "gain_resource_on_build_in_region",
      "resource": "propaganda",
      "amount": 1,
      "town": "南投"
    }
  ]
}
```

## PASS: rebels_third_build_draws_one_card_once

```json
{
  "rule": "反賊反撲效果：回合中建立至少 3 個組織時，當回合抽 1 張；同一回合只觸發一次。",
  "towns": [
    "三亞",
    "上海",
    "北京"
  ],
  "build_results": [
    {
      "success": true
    },
    {
      "success": true
    },
    {
      "success": true
    }
  ],
  "hand_before": 5,
  "hand_after": 6,
  "era_effects_applied": [
    {
      "era": "rebels",
      "type": "build_count_draw_bonus",
      "drawn": [
        "樂捐者"
      ],
      "built_count": 3
    }
  ]
}
```

## PASS: kazakh_restricts_ignore_distance_build_in_china

```json
{
  "rule": "哈薩克紅軍壓制效果：此後無法再無視距離建立牆內組織。",
  "origin": "伊寧",
  "target": "克拉瑪依",
  "build_result": {
    "error": "Target out of build range"
  },
  "active_eras": [
    "kazakh"
  ]
}
```

## PASS: tibet_red_discards_then_builds_near_tibet_org

```json
{
  "rule": "藏國紅軍壓制效果：紅軍棄 1 張手牌後，在藏國組織 1 格內免費建立 1 個紅軍組織。",
  "tibet_org_town": "加德滿都",
  "runtime_effects": {
    "red_suppression": {
      "type": "red_discard_to_build_near_target",
      "status": "pending_discard_choice",
      "player_id": "red",
      "town_count": 3
    },
    "revolution_counterattack": {
      "type": "hand_card_resource_bonus",
      "status": "active_modifier_or_pending_runtime"
    }
  },
  "first_choice_key": "era_red_discard_to_build_near_target",
  "discard_result": {
    "success": true,
    "discarded_card": "紅軍棄牌測試",
    "choice_key": "era_red_discard_to_build_near_target",
    "pending_choice": true,
    "town_count": 3
  },
  "build_choice_key": "era_red_build_near_target",
  "build_town_count": 3,
  "build_result": {
    "success": true,
    "choice_index": 0,
    "town": "加德滿都",
    "selected": {
      "town": "加德滿都",
      "near_target_towns": [
        "加德滿都"
      ]
    },
    "choice_key": "era_red_build_near_target"
  },
  "red_discard_count": 1,
  "red_orgs": {
    "北京": 1,
    "加德滿都": 1
  },
  "era_effects_applied": [
    {
      "era": "tibet",
      "type": "red_discard_to_build_near_target",
      "town": "加德滿都",
      "discarded_card": "紅軍棄牌測試"
    }
  ]
}
```
