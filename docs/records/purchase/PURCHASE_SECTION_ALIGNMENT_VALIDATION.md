# Purchase Section Alignment Validation

summary: {'total': 6, 'passed': 6, 'failed': 0}

screenshot: docs/records/purchase/purchase_section_alignment_validation.png

## PASS — command_centre_uses_equal_random_static_hand_rows

```json
{
  "random_panel_box": {
    "x": 6,
    "y": 110,
    "width": 1268,
    "height": 197.328125
  },
  "static_panel_box": {
    "x": 6,
    "y": 313.328125,
    "width": 1268,
    "height": 197.328125
  },
  "hand_panel_box": {
    "x": 6,
    "y": 516.65625,
    "width": 1268,
    "height": 197.328125
  },
  "row_heights": [
    197.328125,
    197.328125,
    197.328125
  ],
  "base_selection_panel_display": "none"
}
```

## PASS — first_card_stays_inside_each_assigned_row

```json
{
  "random_first_card_box": {
    "x": 15,
    "y": 143,
    "width": 203,
    "height": 125
  },
  "static_first_card_box": {
    "x": 15,
    "y": 346.328125,
    "width": 203,
    "height": 125
  },
  "hand_first_card_box": {
    "x": 15,
    "y": 549.65625,
    "width": 203,
    "height": 156
  }
}
```

## PASS — purchase_zones_populated_for_visual_comparison

```json
{
  "static_cards": 6,
  "random_cards": 5,
  "hand_cards": 5
}
```

## PASS — card_rows_never_show_horizontal_scrollbars

```json
{
  "purchaseRandom": {
    "client_width": 1250,
    "scroll_width": 1250,
    "overflow_x": "hidden",
    "has_horizontal_overflow": false
  },
  "purchaseStatic": {
    "client_width": 1250,
    "scroll_width": 1250,
    "overflow_x": "hidden",
    "has_horizontal_overflow": false
  },
  "hand": {
    "client_width": 1250,
    "scroll_width": 1250,
    "overflow_x": "hidden",
    "has_horizontal_overflow": false
  }
}
```

## PASS — controller_focus_uses_yellow_overlay_distinct_from_selected_state

```json
{
  "card_name": "宣傳家",
  "focus_background": "rgba(255, 216, 61, 0.16)",
  "focus_pointer_events": "none",
  "selected_overlay_display": "block",
  "button_background": "rgb(21, 128, 61)"
}
```

## PASS — living_room_keeps_three_rows_without_scrollbars_or_focus_glow

```json
{
  "boxes": {
    "randomMarketPanel": {
      "x": 6,
      "y": 114,
      "width": 1268,
      "height": 170.65625
    },
    "controlPanel": {
      "x": 6,
      "y": 290.65625,
      "width": 1268,
      "height": 170.671875
    },
    "handPanel": {
      "x": 6,
      "y": 467.328125,
      "width": 1268,
      "height": 170.671875
    }
  },
  "rows": {
    "purchaseRandom": {
      "client_width": 1250,
      "scroll_width": 1250,
      "overflow_x": "hidden",
      "has_horizontal_overflow": false
    },
    "purchaseStatic": {
      "client_width": 1250,
      "scroll_width": 1250,
      "overflow_x": "hidden",
      "has_horizontal_overflow": false
    },
    "hand": {
      "client_width": 1250,
      "scroll_width": 1250,
      "overflow_x": "hidden",
      "has_horizontal_overflow": false
    }
  },
  "controls_outside_panel": [
    {
      "selector": "#purchaseRandom .purchase-card-select-button",
      "count": 5,
      "outside": 0
    },
    {
      "selector": "#purchaseStatic .purchase-card-select-button",
      "count": 6,
      "outside": 0
    },
    {
      "selector": "#hand .hand-card-action-btn",
      "count": 10,
      "outside": 0
    }
  ],
  "focus_background": "rgba(255, 216, 61, 0.16)",
  "focus_outline": "none",
  "focus_shadow": "rgba(0, 0, 0, 0.34) 0px 12px 32px 0px",
  "peer_outline": "none",
  "peer_shadow": "rgba(0, 0, 0, 0.34) 0px 12px 32px 0px"
}
```
