# Era Effects Runtime Validation

- Date: 2026-07-14
- Summary: 15/15 passed

## PASS: mongolia_adds_internal_conflict_with_static_supply_cap

```json
{
  "rule": "蒙古時代關卡 activation effect 將內鬥加入蒙古棄牌堆，但最多消耗既有 static supply（此處 supply=2 封頂）。",
  "active_eras": [
    "mongolia"
  ],
  "discard_internal_conflict": 2,
  "supply_before": 2,
  "supply_after": 0,
  "runtime_effects": {
    "red_suppression": {
      "type": "add_static_cards_to_discard",
      "added": {
        "actor": 4
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
  "rule": "臺灣時代關卡觸發時，將內鬥加入臺灣棄牌堆並消耗 static supply（此處 supply=2 封頂）。",
  "active_eras": [
    "taiwan"
  ],
  "discard_internal_conflict": 2,
  "supply_after": 0,
  "runtime_effects": {
    "red_suppression": {
      "type": "add_static_cards_to_discard",
      "added": {
        "actor": 4
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
  "rule": "滿洲時代關卡 activation effect 將分神加入滿洲棄牌堆並消耗 static supply（此處 supply=2 封頂）。",
  "active_eras": [
    "manchuria"
  ],
  "discard_distraction": 2,
  "supply_after": 0,
  "runtime_effects": {
    "red_suppression": {
      "type": "add_static_cards_to_discard",
      "added": {
        "actor": 2
      }
    },
    "revolution_counterattack": {
      "type": "inspect_deck_top_and_reorder",
      "status": "pending_reorder_choice",
      "player_id": "actor",
      "inspected_count": 6,
      "top_count": 2
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

## PASS: hong_kong_red_spy_play_forces_bonus_discard_after_spy_resolution

```json
{
  "rule": "香港紅軍壓制效果：紅軍打出間諜類卡牌並完成原本目標選擇後，香港玩家再以既有 card choice UI 棄 1 張手牌。",
  "play_result": {
    "success": true,
    "pending_choice": true
  },
  "spy_choice_key": "card_dissolve_interaction",
  "spy_result": {
    "success": true,
    "town": "天津",
    "target_player_id": "actor",
    "pending_choice": true
  },
  "discard_choice_key": "era_bonus_discard_on_red_card",
  "discard_prompt": "[香港]香港人被自殺：紅軍打出 內應間諜，請棄掉 1 張手牌。",
  "discard_result": {
    "success": true,
    "discarded_card": "香港目標手牌",
    "target_player_name": "actor",
    "initiator_player_name": "red",
    "choice_key": "era_bonus_discard_on_red_card"
  },
  "actor_orgs_after": {},
  "actor_discard_count": 1,
  "era_effects_applied": [
    {
      "era": "hong_kong",
      "type": "bonus_discard_on_red_card",
      "status": "pending_discard_choice",
      "target_player_id": "actor",
      "discard_count": 1
    },
    {
      "era": "hong_kong",
      "type": "bonus_discard_on_red_card",
      "status": "resolved",
      "discarded_count": 1,
      "target_player_id": "actor"
    }
  ]
}
```

## PASS: era_notification_payloads_have_complete_ui_text

```json
{
  "rule": "時代關卡達成 modal 應顯示觸發條件、紅軍壓制、革命反撲與期限文字，不應出現暫缺 fallback。",
  "missing_notifications": [],
  "notification_details": {
    "hong_kong": {
      "trigger_text": "[香港抗爭遍地開花]香港在牆內擁有至少10個有效組織",
      "success_text": "[新型態的血腥鎮壓]紅軍每次對香港使用間諜類卡牌時，可再隨機棄掉香港1張手牌。持續2回合。",
      "fail_text": "[沉冤待雪香港報仇]香港購買每張武裝類卡牌之費用額外減少2點資金。持續2回合。",
      "duration_text": "持續 2 回合"
    },
    "mongolia": {
      "trigger_text": "[牧民維權團體成形]蒙古在牆內擁有至少4個有效組織",
      "success_text": "[知識分子互相猜疑]將3張內鬥放進蒙古棄牌堆。",
      "fail_text": "[南蒙古人世代覺醒]蒙古當回合手牌中的每張宣傳類卡牌 用於購買時可額外提供1點宣傳。",
      "duration_text": "持續 1 回合"
    },
    "tibet": {
      "trigger_text": "[藏人完成示威準備]藏國在牆內擁有至少7個有效組織",
      "success_text": "[青藏鐵路運兵鎮壓]紅軍當回合可棄掉任意張數手牌，無視距離在藏國有效組織１格內建立與張數同數量的組織。",
      "fail_text": "[心向法王達賴喇嘛]藏國當回合手牌中的每張宣傳類卡牌 用於購買時可額外提供1點宣傳。",
      "duration_text": "持續 1 回合"
    },
    "kazakh": {
      "trigger_text": "[三玉茲與三區革命]哈薩克在北國擁有至少7個有效組織，在牆內擁有至少3個有效組織",
      "success_text": "[紅軍提防哈薩克人]哈薩克此後無法再無視距離建立牆內組織。",
      "fail_text": "[出逃同胞加入隊伍]當回合哈薩克立即額外抽2張牌。",
      "duration_text": "持續至遊戲結束"
    },
    "uyghur": {
      "trigger_text": "[突厥戰士踏遍七城]維吾爾在牆內擁有至少7個有效組織",
      "success_text": "[武力清剿叛軍基地]紅軍每次對維吾爾使用武裝類卡牌時，可再瓦解己方組織1格內的1個維吾爾組織。持續2回合。",
      "fail_text": "[壯士去兮弔民伐罪]維吾爾每打出1張武裝類卡牌，獲得2點宣傳。持續2回合。",
      "duration_text": "持續 2 回合"
    },
    "manchuria": {
      "trigger_text": "[山海關外故國甦生]滿洲在牆內擁有至少10個有效組織",
      "success_text": "[試圖清洗地方勢力]將5張分神放進滿洲棄牌堆。",
      "fail_text": "[行政資源固守地盤]滿洲當回合可檢視己方牌庫頂7張牌，將其中2張牌移到牌庫最頂，其餘順序不變。",
      "duration_text": "持續 1 回合"
    },
    "rebels": {
      "trigger_text": "[寒冬將至新芽始生]反賊在牆內擁有至少4個有效組織",
      "success_text": "[互聯網管控全面化]反賊此後無法再無視距離建立牆內組織。",
      "fail_text": "[反賊結社潛入地下]反賊在回合中建立至少3個組織，則當回合可再抽1張牌。持續至遊戲結束。",
      "duration_text": "持續至遊戲結束"
    },
    "taiwan": {
      "trigger_text": "[臺灣重建敵後工作]臺灣在牆內擁有至少7個有效組織",
      "success_text": "[鼓吹停止挑釁紅軍]將3張內鬥放進臺灣棄牌堆",
      "fail_text": "[打擊國內綏靖主義]每當臺灣在臺灣城鎮建立至少1個組織時，獲得1點宣傳。持續2回合。",
      "duration_text": "持續 2 回合"
    }
  }
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

## PASS: uyghur_red_armed_play_dissolves_uyghur_org_after_discard_choice

```json
{
  "rule": "維吾爾紅軍壓制效果：紅軍打出武裝類卡牌後，在既有武裝棄牌 pending choice 完成後，選擇 1 個紅軍組織 1 格內的維吾爾組織瓦解。",
  "play_result": {
    "success": true,
    "pending_choice": true
  },
  "discard_choice_key": "armed_target_discard",
  "discard_result": {
    "success": true,
    "discarded_card": "維吾爾目標手牌",
    "target_player_name": "actor",
    "initiator_player_name": "red",
    "choice_key": "armed_target_discard",
    "pending_choice": true
  },
  "dissolve_choice_key": "era_red_bonus_dissolve_target",
  "dissolve_targets": [
    {
      "id": "actor::天津",
      "label": "actor｜天津",
      "player_id": "actor",
      "town": "天津"
    }
  ],
  "dissolve_result": {
    "success": true,
    "choice_index": 0,
    "target_id": "actor::天津",
    "selected": {
      "id": "actor::天津",
      "label": "actor｜天津",
      "player_id": "actor",
      "town": "天津"
    },
    "choice_key": "era_red_bonus_dissolve_target",
    "target_player_name": "actor",
    "town": "天津"
  },
  "actor_orgs_after": {},
  "actor_discard_count": 1,
  "era_effects_applied": [
    {
      "era": "uyghur",
      "type": "bonus_dissolve_on_red_card_near_self",
      "status": "pending_target_choice",
      "target_count": 1
    },
    {
      "era": "uyghur",
      "type": "bonus_dissolve_on_red_card_near_self",
      "status": "resolved",
      "town": "天津",
      "target_player_id": "actor"
    }
  ]
}
```

## PASS: manchuria_inspects_top_seven_and_reorders_two_to_top

```json
{
  "rule": "滿洲革命反撲效果：檢視牌庫頂 7 張，依玩家點選順序選 2 張放回牌庫頂。",
  "runtime_effects": {
    "red_suppression": {
      "type": "add_static_cards_to_discard",
      "added": {
        "actor": 5
      }
    },
    "revolution_counterattack": {
      "type": "inspect_deck_top_and_reorder",
      "status": "pending_reorder_choice",
      "player_id": "actor",
      "inspected_count": 7,
      "top_count": 2
    }
  },
  "choice_key": "era_inspect_deck_top_and_reorder",
  "choice_count": 2,
  "inspected_cards": [
    "第一張",
    "第二張",
    "第三張",
    "第四張",
    "第五張",
    "第六張",
    "第七張"
  ],
  "resolve_result": {
    "success": true,
    "choice_key": "era_inspect_deck_top_and_reorder",
    "inspected_cards": [
      "第一張",
      "第二張",
      "第三張",
      "第四張",
      "第五張",
      "第六張",
      "第七張"
    ],
    "chosen_cards": [
      "第三張",
      "第一張"
    ],
    "deck_top": [
      "第三張",
      "第一張"
    ]
  },
  "first_two_drawn_after_reorder": [
    "第三張",
    "第一張"
  ],
  "era_effects_applied": [
    {
      "era": "manchuria",
      "type": "inspect_deck_top_and_reorder",
      "inspected": [
        "第一張",
        "第二張",
        "第三張",
        "第四張",
        "第五張",
        "第六張",
        "第七張"
      ],
      "selected_top": [
        "第三張",
        "第一張"
      ]
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
    "南京"
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

## PASS: tibet_red_discards_any_number_then_builds_same_count_near_tibet_org

```json
{
  "rule": "藏國紅軍壓制效果：紅軍可棄任意張手牌，並在藏國組織 1 格內免費建立同數量紅軍組織。",
  "tibet_org_town": "列城",
  "runtime_effects": {
    "red_suppression": {
      "type": "red_discard_to_build_near_target",
      "status": "pending_discard_choice",
      "player_id": "red",
      "town_count": 2,
      "max_discard": 2
    },
    "revolution_counterattack": {
      "type": "hand_card_resource_bonus",
      "status": "active_modifier_or_pending_runtime"
    }
  },
  "first_choice": {
    "choice_key": "era_red_discard_to_build_near_target",
    "type": "multi_card_choice",
    "count": 2,
    "min_count": 1,
    "prompt": "[藏國]藏國騷亂：紅軍可棄掉任意張手牌，接著在目標組織 1 格內免費建立同數量組織。"
  },
  "discard_result": {
    "success": true,
    "discarded_cards": [
      "紅軍棄牌測試一",
      "紅軍棄牌測試二"
    ],
    "discarded_count": 2,
    "choice_key": "era_red_discard_to_build_near_target",
    "pending_choice": true,
    "town_count": 2,
    "remaining_builds": 2
  },
  "first_build_choice_towns": [
    "吉爾吉特",
    "阿里"
  ],
  "first_build_result": {
    "success": true,
    "choice_index": 0,
    "town": "吉爾吉特",
    "selected": {
      "town": "吉爾吉特",
      "near_target_towns": [
        "列城"
      ]
    },
    "choice_key": "era_red_build_near_target",
    "pending_choice": true,
    "remaining_builds": 1
  },
  "second_build_choice_towns": [
    "阿里"
  ],
  "second_build_result": {
    "success": true,
    "choice_index": 0,
    "town": "阿里",
    "selected": {
      "town": "阿里",
      "near_target_towns": [
        "列城"
      ]
    },
    "choice_key": "era_red_build_near_target",
    "remaining_builds": 0
  },
  "red_discard_counts": {
    "紅軍棄牌測試一": 1,
    "紅軍棄牌測試二": 1
  },
  "red_orgs": {
    "北京": 1,
    "吉爾吉特": 1,
    "阿里": 1
  },
  "red_hand_after": [
    "紅軍保留手牌"
  ],
  "era_effects_applied": [
    {
      "era": "tibet",
      "type": "red_discard_to_build_near_target",
      "town": "吉爾吉特",
      "discarded_cards": [
        "紅軍棄牌測試一",
        "紅軍棄牌測試二"
      ],
      "build_index": 1,
      "build_total": 2
    },
    {
      "era": "tibet",
      "type": "red_discard_to_build_near_target",
      "town": "阿里",
      "discarded_cards": [
        "紅軍棄牌測試一",
        "紅軍棄牌測試二"
      ],
      "build_index": 2,
      "build_total": 2
    }
  ]
}
```
