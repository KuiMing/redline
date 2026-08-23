# Event Card Zoom Preview Validation

Summary: 14/14 passed

- Open screenshot: `docs/records/event-cards/EVENT_CARD_ZOOM_PREVIEW_OPEN_2026_08_20.png`
- Pinned screenshot: `docs/records/event-cards/EVENT_CARD_COMPACT_MAP_1280_2026_08_20.png`
- Narrow pinned screenshot: `docs/records/event-cards/EVENT_CARD_COMPACT_MAP_1024_2026_08_20.png`
- Idle unobstructed screenshot: `docs/records/event-cards/EVENT_CARD_IDLE_UNOBSTRUCTED_2026_08_20.png`

## PASS — dedicated_event_reveal_overlay_exists

```json
"event reveal DOM"
```

## PASS — all_event_art_assets_are_bound

```json
[
  "一帶一路 南洋.png",
  "一帶一路 天方.png",
  "上海合作組織.png",
  "全國人大召開.png",
  "北京政爭.png",
  "東突厥集中營.png",
  "歲月靜好.png",
  "烏魯木齊七五事件.png",
  "紅軍權貴出逃.png",
  "藏印邊境軍事對峙.png",
  "貿易戰加劇.png",
  "重大災難.png",
  "香港抗暴之戰.png"
]
```

## PASS — zoom_animation_compact_panel_and_cache_busting_exist

```json
"zoom keyframes + compact event panel + semantic cache-busting references"
```

## PASS — turn_start_auto_opens_centered_zoom_preview

```json
{
  "overlayDisplay": "flex",
  "animationName": "event-card-zoom-in",
  "text": "進行中\n達成次數 0 / 3\n非紅軍任務進行中\n點擊任意地方關閉",
  "imageCount": 1,
  "image": {
    "src": "http://127.0.0.1:8767/static/card-art/events/%E7%B4%85%E8%BB%8D%E6%AC%8A%E8%B2%B4%E5%87%BA%E9%80%83.png",
    "alt": "紅軍權貴出逃完整卡面",
    "naturalWidth": 1350,
    "naturalHeight": 1100
  },
  "runtimeStatus": {
    "text": "進行中\n達成次數 0 / 3\n非紅軍任務進行中",
    "rect": {
      "left": 263,
      "top": 644.359375,
      "right": 1017,
      "bottom": 690.359375,
      "width": 754,
      "height": 46
    },
    "fullyInsideCard": true,
    "fullyInsideViewport": true,
    "overlapsArtwork": false
  },
  "artworkRect": {
    "left": 263,
    "top": 30,
    "right": 1017,
    "bottom": 644.359375,
    "width": 754,
    "height": 614.359375
  },
  "centerDelta": {
    "x": 0,
    "y": 0
  },
  "cardRect": {
    "left": 261,
    "top": 28,
    "width": 758,
    "height": 664
  }
}
```

## PASS — expanded_preview_shows_complete_event_art_and_runtime_status

```json
{
  "text": "進行中\n達成次數 0 / 3\n非紅軍任務進行中\n點擊任意地方關閉",
  "imageCount": 1,
  "image": {
    "src": "http://127.0.0.1:8767/static/card-art/events/%E7%B4%85%E8%BB%8D%E6%AC%8A%E8%B2%B4%E5%87%BA%E9%80%83.png",
    "alt": "紅軍權貴出逃完整卡面",
    "naturalWidth": 1350,
    "naturalHeight": 1100
  }
}
```

## PASS — expanded_runtime_progress_is_visible_below_not_over_artwork

```json
{
  "runtimeStatus": {
    "text": "進行中\n達成次數 0 / 3\n非紅軍任務進行中",
    "rect": {
      "left": 263,
      "top": 644.359375,
      "right": 1017,
      "bottom": 690.359375,
      "width": 754,
      "height": 46
    },
    "fullyInsideCard": true,
    "fullyInsideViewport": true,
    "overlapsArtwork": false
  },
  "artworkRect": {
    "left": 263,
    "top": 30,
    "right": 1017,
    "bottom": 644.359375,
    "width": 754,
    "height": 614.359375
  },
  "cardRect": {
    "left": 261,
    "top": 28,
    "width": 758,
    "height": 664
  }
}
```

## PASS — click_anywhere_closes_without_same_turn_reopen

```json
{
  "displayAfterRerender": "none"
}
```

## PASS — compact_event_card_uses_reserved_rail_without_covering_game_ui

```json
{
  "role": "button",
  "tabindex": "0",
  "ariaLabel": "紅軍權貴出逃，進行中，點擊放大查看",
  "title": "紅軍權貴出逃｜進行中｜點擊放大查看",
  "text": "達成次數 0 / 3\n進行中",
  "imageLoaded": true,
  "controls": [],
  "compactStatus": {
    "text": "達成次數 0 / 3\n進行中",
    "rect": {
      "left": 937,
      "top": 1,
      "right": 1075,
      "bottom": 146
    },
    "fullyInsidePanel": true,
    "overlapsArtwork": false
  },
  "gameShell": {
    "left": 0,
    "top": 203,
    "right": 1280,
    "bottom": 773
  },
  "overlapsGameShell": false,
  "protectedUi": [
    {
      "id": "topBar",
      "rect": {
        "left": 0,
        "top": 0,
        "right": 920,
        "bottom": 48
      },
      "overlaps": false
    },
    {
      "id": "hud",
      "rect": {
        "left": 0,
        "top": 48,
        "right": 920,
        "bottom": 127
      },
      "overlaps": false
    },
    {
      "id": "phaseActionBar",
      "rect": {
        "left": 0,
        "top": 135,
        "right": 920,
        "bottom": 195
      },
      "overlaps": false
    }
  ],
  "panel": {
    "left": 936,
    "top": 0,
    "right": 1256,
    "bottom": 147,
    "width": 320,
    "height": 147
  },
  "toolbar": {
    "left": 948,
    "top": 279,
    "right": 1252,
    "bottom": 318,
    "width": 304,
    "height": 39
  },
  "overlaps": false
}
```

## PASS — compact_event_progress_is_visible_outside_artwork

```json
{
  "controls": [],
  "compactStatus": {
    "text": "達成次數 0 / 3\n進行中",
    "rect": {
      "left": 937,
      "top": 1,
      "right": 1075,
      "bottom": 146
    },
    "fullyInsidePanel": true,
    "overlapsArtwork": false
  },
  "ariaLabel": "紅軍權貴出逃，進行中，點擊放大查看",
  "title": "紅軍權貴出逃｜進行中｜點擊放大查看"
}
```

## PASS — compact_event_card_stays_clear_at_narrow_viewport

```json
{
  "panel": {
    "left": 748.7999877929688,
    "top": 96,
    "right": 1004.7999877929688,
    "bottom": 213.60000610351562,
    "width": 256,
    "height": 117.60000610351562
  },
  "toolbar": {
    "left": 758.400036769308,
    "top": 319.20002366573874,
    "right": 1001.6000485875803,
    "bottom": 350.4000218416996
  },
  "status": {
    "text": "達成次數 0 / 3\n進行中",
    "left": 749.6000366210938,
    "top": 96.80000305175781,
    "right": 860,
    "bottom": 212.8000030517578
  },
  "protectedOverlaps": false,
  "viewport": {
    "width": 1024,
    "height": 768
  },
  "overlaps": false
}
```

## PASS — top_right_event_panel_reopens_preview

```json
{
  "panel": {
    "role": "button",
    "tabindex": "0",
    "ariaLabel": "紅軍權貴出逃，進行中，點擊放大查看",
    "title": "紅軍權貴出逃｜進行中｜點擊放大查看",
    "text": "達成次數 0 / 3\n進行中",
    "imageLoaded": true,
    "controls": [],
    "compactStatus": {
      "text": "達成次數 0 / 3\n進行中",
      "rect": {
        "left": 937,
        "top": 1,
        "right": 1075,
        "bottom": 146
      },
      "fullyInsidePanel": true,
      "overlapsArtwork": false
    },
    "gameShell": {
      "left": 0,
      "top": 203,
      "right": 1280,
      "bottom": 773
    },
    "overlapsGameShell": false,
    "protectedUi": [
      {
        "id": "topBar",
        "rect": {
          "left": 0,
          "top": 0,
          "right": 920,
          "bottom": 48
        },
        "overlaps": false
      },
      {
        "id": "hud",
        "rect": {
          "left": 0,
          "top": 48,
          "right": 920,
          "bottom": 127
        },
        "overlaps": false
      },
      {
        "id": "phaseActionBar",
        "rect": {
          "left": 0,
          "top": 135,
          "right": 920,
          "bottom": 195
        },
        "overlaps": false
      }
    ],
    "panel": {
      "left": 936,
      "top": 0,
      "right": 1256,
      "bottom": 147,
      "width": 320,
      "height": 147
    },
    "toolbar": {
      "left": 948,
      "top": 279,
      "right": 1252,
      "bottom": 318,
      "width": 304,
      "height": 39
    },
    "overlaps": false
  },
  "reopened": {
    "display": "flex",
    "animation": "event-card-zoom-in",
    "text": "進行中\n達成次數 0 / 3\n非紅軍任務進行中\n點擊任意地方關閉",
    "imageAlt": "紅軍權貴出逃完整卡面"
  }
}
```

## PASS — escape_also_closes_preview

```json
"Escape closed the overlay"
```

## PASS — idle_event_thumbnail_keeps_no_effect_status_off_the_artwork

```json
{
  "ariaLabel": "歲月靜好，無效果，點擊放大查看",
  "title": "歲月靜好｜無效果｜點擊放大查看",
  "imageLoaded": true,
  "controls": []
}
```

## PASS — browser_console_has_no_errors

```json
[]
```
