# Purchase Section Alignment Validation

summary: {'total': 2, 'passed': 2, 'failed': 0}

screenshot: /Users/benmini/.openclaw/workspace/redline/purchase_section_alignment_validation.png

## PASS — static_purchase_title_aligns_with_random_market_title

```json
{
  "static_title_box": {
    "x": 21,
    "y": 219,
    "width": 282,
    "height": 17
  },
  "random_title_box": {
    "x": 333,
    "y": 219,
    "width": 442,
    "height": 17
  },
  "top_delta_px": 0,
  "allowed_delta_px": 4,
  "base_selection_panel_display": "block"
}
```

## PASS — purchase_zones_populated_for_visual_comparison

```json
{
  "static_cards": 6,
  "random_cards": 5
}
```
