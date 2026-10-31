# Purchase Section Alignment Validation

summary: {'total': 3, 'passed': 3, 'failed': 0}

screenshot: docs/records/purchase/purchase_section_alignment_validation.png

## PASS — static_purchase_title_aligns_with_random_market_title

```json
{
  "static_title_box": {
    "x": 21,
    "y": 219,
    "width": 294,
    "height": 17
  },
  "random_title_box": {
    "x": 345,
    "y": 219,
    "width": 442,
    "height": 17
  },
  "top_delta_px": 0,
  "allowed_delta_px": 4,
  "base_selection_panel_display": "none"
}
```

## PASS — static_purchase_first_card_top_aligns_with_random_market_first_card

```json
{
  "static_first_card_box": {
    "x": 21,
    "y": 250,
    "width": 220,
    "height": 270
  },
  "random_first_card_box": {
    "x": 345,
    "y": 250,
    "width": 220,
    "height": 270
  },
  "top_delta_px": 0,
  "allowed_delta_px": 4
}
```

## PASS — purchase_zones_populated_for_visual_comparison

```json
{
  "static_cards": 6,
  "random_cards": 5
}
```
