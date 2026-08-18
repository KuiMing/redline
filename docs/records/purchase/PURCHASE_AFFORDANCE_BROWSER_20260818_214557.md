# Purchase affordance browser validation

```json
{
  "summary": {
    "total": 3,
    "passed": 3,
    "failed": 0
  },
  "checks": [
    {
      "name": "initial_action_phase_offers_single_end_action_phase_button",
      "passed": true,
      "details": {
        "turn_phase": "action",
        "meta": "目前：行動｜下一步：結束行動階段",
        "advance_text": "結束行動階段",
        "phase_bar_display": "flex",
        "screenshot": "docs/records/purchase/purchase-affordance-browser-20260818_214557/01_initial_action_phase_no_continue_button.png"
      }
    },
    {
      "name": "purchase_selectable_in_action_phase_but_buy_blocked_without_resources",
      "passed": true,
      "details": {
        "turn_phase": "action",
        "buy_title": "所選卡牌的合計費用超過目前資源。",
        "hk_resources": {
          "money": 0,
          "propaganda": 0
        },
        "screenshot": "docs/records/purchase/purchase-affordance-browser-20260818_214557/02_action_phase_no_resources_buy_disabled.png"
      }
    },
    {
      "name": "after_resources_purchase_enabled_and_real_click_buys_card_in_action_phase",
      "passed": true,
      "details": {
        "resources_before_purchase_step": {
          "money": 0,
          "propaganda": 3
        },
        "turn_phase_after_buy": "action",
        "checkbox_title_before_buy": "勾選此卡（3宣傳）",
        "static_supply_after_buy": {
          "宣傳家": 13,
          "思想家": 15,
          "資助者": 15,
          "資本家": 15,
          "分神": 30,
          "內鬥": 20
        },
        "hk_resources_after_buy": {
          "money": 0,
          "propaganda": 0
        },
        "hk_discard_pile": [
          "追隨者",
          "追隨者",
          "追隨者",
          "宣傳家"
        ],
        "action_log_tail": [
          "[Turn 1] Event drawn: 全國人大召開",
          "[Turn 1] hk played 追隨者 as resource",
          "[Turn 1] hk played 追隨者 as resource",
          "[Turn 1] hk played 追隨者 as resource",
          "[Turn 1] hk bought 宣傳家"
        ],
        "screenshot": "docs/records/purchase/purchase-affordance-browser-20260818_214557/03_after_real_click_buy_static_card.png"
      }
    }
  ]
}
```
