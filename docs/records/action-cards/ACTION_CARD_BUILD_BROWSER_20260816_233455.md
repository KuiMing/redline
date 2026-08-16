# Action Card Build Browser Validation

Generated: 20260816_233455

Summary: 6/6 passed

## PASS — 宣傳家

```json
{
  "card": "宣傳家",
  "ok": true,
  "url": "http://127.0.0.1:8000/?v=card-build-browser-20260816_233455-宣傳家",
  "action_button_before_click": {
    "disabled": false,
    "title": "打出這張手牌"
  },
  "pending_choice_after_action": {
    "choice_key": "card_build_organization",
    "prompt": "宣傳家：選擇要建立組織的城鎮（尚可建立 1 個）。",
    "town_count": 11
  },
  "map_resolutions": [
    {
      "target": "九龍城",
      "select_result": {
        "ok": true,
        "town": "九龍城",
        "highlighted": false,
        "road": 0,
        "rail": 0,
        "owns": false,
        "shared": false,
        "canAct": false
      },
      "button_state_before_click": {
        "text": "在目前城鎮建立組織（效果）",
        "disabled": false,
        "title": ""
      },
      "map_hint": "已選取 九龍城：合法移動目的地 13 個。"
    }
  ],
  "before_orgs": 1,
  "final_orgs": 2,
  "expected_final_orgs": 2,
  "moves_left": 1,
  "expected_moves": 1,
  "organizations": {
    "香港城": 1,
    "九龍城": 1
  },
  "action_log_tail": [
    "[Turn 1] Event drawn: 香港抗暴之戰",
    "[Turn 1] 宣傳家 returned to static purchase supply",
    "[Turn 1] hk removed 宣傳家 and returned it to static purchase supply",
    "[Turn 1] hk played 宣傳家",
    "[Turn 1] hk triggered 安全屋 while building in 九龍城",
    "[Turn 1] hk built organization in 九龍城 via 宣傳家"
  ],
  "screenshots": [
    "docs/records/action-cards/card-build-browser-20260816_233455/01_propagandist_after_action_map_prompt.png",
    "docs/records/action-cards/card-build-browser-20260816_233455/02_propagandist_after_map_build.png"
  ]
}
```

## PASS — 思想家

```json
{
  "card": "思想家",
  "ok": true,
  "url": "http://127.0.0.1:8000/?v=card-build-browser-20260816_233455-思想家",
  "action_button_before_click": {
    "disabled": false,
    "title": "打出這張手牌"
  },
  "pending_choice_after_action": {
    "choice_key": "card_build_organization",
    "prompt": "思想家：選擇要建立組織的城鎮（尚可建立 1 個）。",
    "town_count": 43
  },
  "map_resolutions": [
    {
      "target": "上粉沙打",
      "select_result": {
        "ok": true,
        "town": "上粉沙打",
        "highlighted": false,
        "road": 0,
        "rail": 0,
        "owns": false,
        "shared": false,
        "canAct": false
      },
      "button_state_before_click": {
        "text": "在目前城鎮建立組織（效果）",
        "disabled": false,
        "title": ""
      },
      "map_hint": "已選取 上粉沙打：合法移動目的地 13 個。"
    }
  ],
  "before_orgs": 1,
  "final_orgs": 2,
  "expected_final_orgs": 2,
  "moves_left": 3,
  "expected_moves": 3,
  "organizations": {
    "香港城": 1,
    "上粉沙打": 1
  },
  "action_log_tail": [
    "[Turn 1] Event drawn: 一帶一路 南洋 (auto deferred)",
    "[Turn 1] 思想家 returned to static purchase supply",
    "[Turn 1] hk removed 思想家 and returned it to static purchase supply",
    "[Turn 1] hk played 思想家",
    "[Turn 1] hk triggered 安全屋 while building in 上粉沙打",
    "[Turn 1] hk built organization in 上粉沙打 via 思想家"
  ],
  "screenshots": []
}
```

## PASS — 組織經驗丙

```json
{
  "card": "組織經驗丙",
  "ok": true,
  "url": "http://127.0.0.1:8000/?v=card-build-browser-20260816_233455-組織經驗丙",
  "action_button_before_click": {
    "disabled": false,
    "title": "打出這張手牌"
  },
  "pending_choice_after_action": {
    "choice_key": "card_build_organization",
    "prompt": "組織經驗丙：選擇要建立組織的城鎮（尚可建立 1 個）。",
    "town_count": 11
  },
  "map_resolutions": [
    {
      "target": "九龍城",
      "select_result": {
        "ok": true,
        "town": "九龍城",
        "highlighted": false,
        "road": 0,
        "rail": 0,
        "owns": false,
        "shared": false,
        "canAct": false
      },
      "button_state_before_click": {
        "text": "在目前城鎮建立組織（效果）",
        "disabled": false,
        "title": ""
      },
      "map_hint": "已選取 九龍城：合法移動目的地 0 個。"
    }
  ],
  "before_orgs": 1,
  "final_orgs": 2,
  "expected_final_orgs": 2,
  "moves_left": 0,
  "expected_moves": 0,
  "organizations": {
    "香港城": 1,
    "九龍城": 1
  },
  "action_log_tail": [
    "[Turn 1] Event drawn: 歲月靜好 (no-op)",
    "[Turn 1] hk played 組織經驗丙",
    "[Turn 1] hk triggered 安全屋 while building in 九龍城",
    "[Turn 1] hk built organization in 九龍城 via 組織經驗丙"
  ],
  "screenshots": []
}
```

## PASS — 組織經驗乙

```json
{
  "card": "組織經驗乙",
  "ok": true,
  "url": "http://127.0.0.1:8000/?v=card-build-browser-20260816_233455-組織經驗乙",
  "action_button_before_click": {
    "disabled": false,
    "title": "打出這張手牌"
  },
  "pending_choice_after_action": {
    "choice_key": "card_build_organization",
    "prompt": "組織經驗乙：選擇要建立組織的城鎮（尚可建立 2 個）。",
    "town_count": 11
  },
  "map_resolutions": [
    {
      "target": "九龍城",
      "select_result": {
        "ok": true,
        "town": "九龍城",
        "highlighted": false,
        "road": 0,
        "rail": 0,
        "owns": false,
        "shared": false,
        "canAct": false
      },
      "button_state_before_click": {
        "text": "在目前城鎮建立組織（效果）",
        "disabled": false,
        "title": ""
      },
      "map_hint": "組織經驗乙：選擇要建立組織的城鎮（尚可建立 1 個）。 可建立城鎮：14 個。尚可建立組織：1 個。地圖上已用中性色外框標出可選城鎮。請點選中性色外框城鎮，然後使用左側「在目前城鎮建立組織（效果）」按鈕完成建立。"
    },
    {
      "target": "大埔",
      "select_result": {
        "ok": true,
        "town": "大埔",
        "highlighted": false,
        "road": 0,
        "rail": 0,
        "owns": false,
        "shared": false,
        "canAct": false
      },
      "button_state_before_click": {
        "text": "在目前城鎮建立組織（效果）",
        "disabled": false,
        "title": ""
      },
      "map_hint": "已選取 大埔：合法移動目的地 0 個。"
    }
  ],
  "before_orgs": 1,
  "final_orgs": 3,
  "expected_final_orgs": 3,
  "moves_left": 0,
  "expected_moves": 0,
  "organizations": {
    "香港城": 1,
    "九龍城": 1,
    "大埔": 1
  },
  "action_log_tail": [
    "[Turn 1] Event drawn: 歲月靜好 (no-op)",
    "[Turn 1] hk played 組織經驗乙",
    "[Turn 1] hk triggered 安全屋 while building in 九龍城",
    "[Turn 1] hk built organization in 九龍城 via 組織經驗乙",
    "[Turn 1] hk triggered 安全屋 while building in 大埔",
    "[Turn 1] hk built organization in 大埔 via 組織經驗乙"
  ],
  "screenshots": []
}
```

## PASS — 組織經驗甲

```json
{
  "card": "組織經驗甲",
  "ok": true,
  "url": "http://127.0.0.1:8000/?v=card-build-browser-20260816_233455-組織經驗甲",
  "action_button_before_click": {
    "disabled": false,
    "title": "打出這張手牌"
  },
  "pending_choice_after_action": {
    "choice_key": "card_build_organization",
    "prompt": "組織經驗甲：選擇要建立組織的城鎮（尚可建立 1 個）。",
    "town_count": 43
  },
  "map_resolutions": [
    {
      "target": "上粉沙打",
      "select_result": {
        "ok": true,
        "town": "上粉沙打",
        "highlighted": false,
        "road": 0,
        "rail": 0,
        "owns": false,
        "shared": false,
        "canAct": false
      },
      "button_state_before_click": {
        "text": "在目前城鎮建立組織（效果）",
        "disabled": false,
        "title": ""
      },
      "map_hint": "已選取 上粉沙打：合法移動目的地 0 個。"
    }
  ],
  "before_orgs": 1,
  "final_orgs": 2,
  "expected_final_orgs": 2,
  "moves_left": 0,
  "expected_moves": 0,
  "organizations": {
    "香港城": 1,
    "上粉沙打": 1
  },
  "action_log_tail": [
    "[Turn 1] Event drawn: 香港抗暴之戰",
    "[Turn 1] hk played 組織經驗甲",
    "[Turn 1] hk triggered 安全屋 while building in 上粉沙打",
    "[Turn 1] hk built organization in 上粉沙打 via 組織經驗甲"
  ],
  "screenshots": []
}
```

## PASS — 全部建立組織行動卡（無合法城鎮）

```json
{
  "card": "全部建立組織行動卡（無合法城鎮）",
  "ok": true,
  "url": "http://127.0.0.1:8000/?v=no-legal-build-20260816_233455",
  "button_checks": [
    {
      "card": "宣傳家",
      "action_disabled": true,
      "action_text": "無城鎮可建立",
      "action_title": "目前沒有城鎮可以建立組織。",
      "resource_enabled": true,
      "legality": {
        "playable": false,
        "reason": "目前沒有城鎮可以建立組織。",
        "no_legal_build_town": true
      }
    },
    {
      "card": "思想家",
      "action_disabled": true,
      "action_text": "無城鎮可建立",
      "action_title": "目前沒有城鎮可以建立組織。",
      "resource_enabled": true,
      "legality": {
        "playable": false,
        "reason": "目前沒有城鎮可以建立組織。",
        "no_legal_build_town": true
      }
    },
    {
      "card": "組織經驗丙",
      "action_disabled": true,
      "action_text": "無城鎮可建立",
      "action_title": "目前沒有城鎮可以建立組織。",
      "resource_enabled": true,
      "legality": {
        "playable": false,
        "reason": "目前沒有城鎮可以建立組織。",
        "no_legal_build_town": true
      }
    },
    {
      "card": "組織經驗乙",
      "action_disabled": true,
      "action_text": "無城鎮可建立",
      "action_title": "目前沒有城鎮可以建立組織。",
      "resource_enabled": true,
      "legality": {
        "playable": false,
        "reason": "目前沒有城鎮可以建立組織。",
        "no_legal_build_town": true
      }
    },
    {
      "card": "組織經驗甲",
      "action_disabled": true,
      "action_text": "無城鎮可建立",
      "action_title": "目前沒有城鎮可以建立組織。",
      "resource_enabled": true,
      "legality": {
        "playable": false,
        "reason": "目前沒有城鎮可以建立組織。",
        "no_legal_build_town": true
      }
    }
  ],
  "hand_unchanged": true,
  "screenshots": [
    "docs/records/action-cards/card-build-browser-20260816_233455/03_no_legal_build_cards_disabled_upper.png",
    "docs/records/action-cards/card-build-browser-20260816_233455/04_no_legal_build_cards_disabled_lower.png"
  ]
}
```
