# 金門地圖標籤驗證

Summary: 6/6 passed

- Screenshot: `docs/records/map-ui/KINMEN_LABEL_UI_2026_07_28.png`
- Re-run: `uv run --with playwright python scripts/validate_kinmen_map_label.py`

## PASS — kinmen_has_explicit_collision_safe_label_placement_and_cache_bust

```json
"town-specific tooltip options + map script cache bust"
```

## PASS — kinmen_and_xiamen_labels_exist_at_auto_label_zooms

```json
[
  {
    "zoom": 5,
    "labels": {
      "金門": {
        "text": "金門",
        "rect": {
          "left": 760,
          "top": 378.6000061035156,
          "right": 792,
          "bottom": 399.1000061035156,
          "width": 32,
          "height": 20.5
        },
        "classes": [
          "leaflet-tooltip",
          "town-label",
          "town-label-kinmen",
          "leaflet-zoom-animated",
          "leaflet-tooltip-bottom"
        ],
        "display": "block",
        "opacity": "0.9"
      },
      "廈門": {
        "text": "廈門",
        "rect": {
          "left": 755,
          "top": 321.3999938964844,
          "right": 787,
          "bottom": 341.8999938964844,
          "width": 32,
          "height": 20.5
        },
        "classes": [
          "leaflet-tooltip",
          "town-label",
          "leaflet-zoom-animated",
          "leaflet-tooltip-top"
        ],
        "display": "block",
        "opacity": "0.9"
      }
    },
    "mapRect": {
      "left": 340,
      "top": 0,
      "right": 1280,
      "bottom": 720
    },
    "overlapArea": 0
  },
  {
    "zoom": 6,
    "labels": {
      "金門": {
        "text": "金門",
        "rect": {
          "left": 727,
          "top": 383.0666809082031,
          "right": 759,
          "bottom": 403.5666809082031,
          "width": 32,
          "height": 20.5
        },
        "classes": [
          "leaflet-tooltip",
          "town-label",
          "town-label-kinmen",
          "leaflet-zoom-animated",
          "leaflet-tooltip-bottom"
        ],
        "display": "block",
        "opacity": "0.9"
      },
      "廈門": {
        "text": "廈門",
        "rect": {
          "left": 716,
          "top": 320.9333190917969,
          "right": 748,
          "bottom": 341.4333190917969,
          "width": 32,
          "height": 20.5
        },
        "classes": [
          "leaflet-tooltip",
          "town-label",
          "leaflet-zoom-animated",
          "leaflet-tooltip-top"
        ],
        "display": "block",
        "opacity": "0.9"
      }
    },
    "mapRect": {
      "left": 340,
      "top": 0,
      "right": 1280,
      "bottom": 720
    },
    "overlapArea": 0
  },
  {
    "zoom": 7,
    "labels": {
      "金門": {
        "text": "金門",
        "rect": {
          "left": 660,
          "top": 387.5333251953125,
          "right": 692,
          "bottom": 408.0333251953125,
          "width": 32,
          "height": 20.5
        },
        "classes": [
          "leaflet-tooltip",
          "town-label",
          "town-label-kinmen",
          "leaflet-zoom-animated",
          "leaflet-tooltip-bottom"
        ],
        "display": "block",
        "opacity": "0.9"
      },
      "廈門": {
        "text": "廈門",
        "rect": {
          "left": 639,
          "top": 320.4666748046875,
          "right": 671,
          "bottom": 340.9666748046875,
          "width": 32,
          "height": 20.5
        },
        "classes": [
          "leaflet-tooltip",
          "town-label",
          "leaflet-zoom-animated",
          "leaflet-tooltip-top"
        ],
        "display": "block",
        "opacity": "0.9"
      }
    },
    "mapRect": {
      "left": 340,
      "top": 0,
      "right": 1280,
      "bottom": 720
    },
    "overlapArea": 0
  }
]
```

## PASS — kinmen_label_uses_bottom_placement

```json
{
  "text": "金門",
  "rect": {
    "left": 727,
    "top": 383.0666809082031,
    "right": 759,
    "bottom": 403.5666809082031,
    "width": 32,
    "height": 20.5
  },
  "classes": [
    "leaflet-tooltip",
    "town-label",
    "town-label-kinmen",
    "leaflet-zoom-animated",
    "leaflet-tooltip-bottom"
  ],
  "display": "block",
  "opacity": "0.9"
}
```

## PASS — kinmen_label_does_not_overlap_xiamen_at_zooms_5_to_7

```json
[
  {
    "zoom": 5,
    "overlapArea": 0,
    "labels": {
      "金門": {
        "text": "金門",
        "rect": {
          "left": 760,
          "top": 378.6000061035156,
          "right": 792,
          "bottom": 399.1000061035156,
          "width": 32,
          "height": 20.5
        },
        "classes": [
          "leaflet-tooltip",
          "town-label",
          "town-label-kinmen",
          "leaflet-zoom-animated",
          "leaflet-tooltip-bottom"
        ],
        "display": "block",
        "opacity": "0.9"
      },
      "廈門": {
        "text": "廈門",
        "rect": {
          "left": 755,
          "top": 321.3999938964844,
          "right": 787,
          "bottom": 341.8999938964844,
          "width": 32,
          "height": 20.5
        },
        "classes": [
          "leaflet-tooltip",
          "town-label",
          "leaflet-zoom-animated",
          "leaflet-tooltip-top"
        ],
        "display": "block",
        "opacity": "0.9"
      }
    }
  },
  {
    "zoom": 6,
    "overlapArea": 0,
    "labels": {
      "金門": {
        "text": "金門",
        "rect": {
          "left": 727,
          "top": 383.0666809082031,
          "right": 759,
          "bottom": 403.5666809082031,
          "width": 32,
          "height": 20.5
        },
        "classes": [
          "leaflet-tooltip",
          "town-label",
          "town-label-kinmen",
          "leaflet-zoom-animated",
          "leaflet-tooltip-bottom"
        ],
        "display": "block",
        "opacity": "0.9"
      },
      "廈門": {
        "text": "廈門",
        "rect": {
          "left": 716,
          "top": 320.9333190917969,
          "right": 748,
          "bottom": 341.4333190917969,
          "width": 32,
          "height": 20.5
        },
        "classes": [
          "leaflet-tooltip",
          "town-label",
          "leaflet-zoom-animated",
          "leaflet-tooltip-top"
        ],
        "display": "block",
        "opacity": "0.9"
      }
    }
  },
  {
    "zoom": 7,
    "overlapArea": 0,
    "labels": {
      "金門": {
        "text": "金門",
        "rect": {
          "left": 660,
          "top": 387.5333251953125,
          "right": 692,
          "bottom": 408.0333251953125,
          "width": 32,
          "height": 20.5
        },
        "classes": [
          "leaflet-tooltip",
          "town-label",
          "town-label-kinmen",
          "leaflet-zoom-animated",
          "leaflet-tooltip-bottom"
        ],
        "display": "block",
        "opacity": "0.9"
      },
      "廈門": {
        "text": "廈門",
        "rect": {
          "left": 639,
          "top": 320.4666748046875,
          "right": 671,
          "bottom": 340.9666748046875,
          "width": 32,
          "height": 20.5
        },
        "classes": [
          "leaflet-tooltip",
          "town-label",
          "leaflet-zoom-animated",
          "leaflet-tooltip-top"
        ],
        "display": "block",
        "opacity": "0.9"
      }
    }
  }
]
```

## PASS — kinmen_label_is_visible_inside_map

```json
{
  "kinmen": {
    "text": "金門",
    "rect": {
      "left": 727,
      "top": 383.0666809082031,
      "right": 759,
      "bottom": 403.5666809082031,
      "width": 32,
      "height": 20.5
    },
    "classes": [
      "leaflet-tooltip",
      "town-label",
      "town-label-kinmen",
      "leaflet-zoom-animated",
      "leaflet-tooltip-bottom"
    ],
    "display": "block",
    "opacity": "0.9"
  },
  "mapRect": {
    "left": 340,
    "top": 0,
    "right": 1280,
    "bottom": 720
  }
}
```

## PASS — browser_console_has_no_errors

```json
[]
```
