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
      "name": "initial_action_phase_offers_single_end_action_button",
      "passed": true,
      "details": {
        "turn_phase": "action",
        "meta": "目前：行動｜下一步：結束行動",
        "advance_text": "結束行動",
        "advance_display": "flex",
        "ui_geometry": {
          "randomPanel": {
            "left": 6,
            "top": 110,
            "right": 1274,
            "bottom": 307.328125,
            "width": 1268,
            "height": 197.328125
          },
          "staticPanel": {
            "left": 6,
            "top": 313.328125,
            "right": 1274,
            "bottom": 510.65625,
            "width": 1268,
            "height": 197.328125
          },
          "handPanel": {
            "left": 6,
            "top": 516.65625,
            "right": 1274,
            "bottom": 713.984375,
            "width": 1268,
            "height": 197.328125
          },
          "handCard": {
            "left": 15,
            "top": 549.65625,
            "right": 218,
            "bottom": 705.65625,
            "width": 203,
            "height": 156
          },
          "cardWidth": 203,
          "buttonWidth": 203,
          "labelCenterDelta": 0,
          "countRightInset": 9,
          "halfHeightImages": 14,
          "wrongRuntimeImages": [],
          "legacyCheckboxes": 0
        },
        "screenshot": "docs/records/purchase/purchase-affordance-browser-20261018_093730/01_initial_action_phase_no_continue_button.png"
      }
    },
    {
      "name": "purchase_selectable_in_action_phase_but_buy_blocked_without_resources",
      "passed": true,
      "details": {
        "turn_phase": "action",
        "buy_title": "所選卡牌的合計費用超過目前資源。",
        "selected_visual": {
          "buttonText": "取消選擇",
          "buttonBackground": "rgb(22, 101, 52)",
          "overlayDisplay": "block",
          "overlayBackground": "rgba(255, 255, 255, 0.28)",
          "previewDisplayAfterButtonClick": "none"
        },
        "full_preview": {
          "display": "flex",
          "src": "http://127.0.0.1:8000/static/card-art/actions/%E5%AE%A3%E5%82%B3%E5%AE%B6.png?v=head-safe-20260726"
        },
        "hk_resources": {
          "money": 0,
          "propaganda": 0
        },
        "screenshot": "docs/records/purchase/purchase-affordance-browser-20261018_093730/02_action_phase_no_resources_buy_disabled.png"
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
        "select_button_title_before_buy": "選擇此卡（3宣傳）",
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
          "[Turn 1] Event drawn: 歲月靜好 (no-op)",
          "[Turn 1] hk played 追隨者 as resource",
          "[Turn 1] hk played 追隨者 as resource",
          "[Turn 1] hk played 追隨者 as resource",
          "[Turn 1] hk bought 宣傳家"
        ],
        "screenshot": "docs/records/purchase/purchase-affordance-browser-20261018_093730/03_after_real_click_buy_static_card.png"
      }
    }
  ]
}
```
