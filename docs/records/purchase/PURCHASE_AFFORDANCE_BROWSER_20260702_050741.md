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
      "name": "initial_action_phase_has_no_continue_action_button",
      "passed": true,
      "details": {
        "turn_phase": "action",
        "meta": "目前：行動｜下一步：開始購買階段",
        "advance_text": "開始購買階段",
        "phase_bar_display": "flex",
        "screenshot": "docs/records/purchase/purchase-affordance-browser-20260702_050741/01_initial_action_phase_no_continue_button.png"
      }
    },
    {
      "name": "purchase_button_disabled_when_resources_insufficient",
      "passed": true,
      "details": {
        "turn_phase": "end",
        "title": "資源不足，需要 3宣傳",
        "hk_resources": {
          "money": 0,
          "propaganda": 0
        },
        "screenshot": "docs/records/purchase/purchase-affordance-browser-20260702_050741/02_purchase_phase_no_resources_buy_disabled.png"
      }
    },
    {
      "name": "after_resources_purchase_button_enabled_and_real_click_buys_card",
      "passed": true,
      "details": {
        "resources_before_purchase_step": {
          "money": 0,
          "propaganda": 3
        },
        "button_title_before_buy": "購買此卡（3宣傳）",
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
          "宣傳家",
          "追隨者",
          "追隨者",
          "追隨者",
          "宣傳家"
        ],
        "action_log_tail": [
          "[Turn 1] hk played 追隨者 as resource",
          "[Turn 1] hk played 追隨者 as resource",
          "[Turn 1] hk played 追隨者 as resource",
          "[Turn 1] hk bought 宣傳家"
        ],
        "screenshot": "docs/records/purchase/purchase-affordance-browser-20260702_050741/03_after_real_click_buy_static_card.png"
      }
    }
  ]
}
```
