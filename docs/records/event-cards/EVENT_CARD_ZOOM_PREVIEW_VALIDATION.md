# Event Card Zoom Preview Validation

Summary: 13/13 passed

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
  "text": "進行中\n任務進度 0/1\n非紅軍任務進行中\n點擊任意地方關閉",
  "imageCount": 1,
  "image": {
    "src": "http://127.0.0.1:8767/static/card-art/events/%E9%A6%99%E6%B8%AF%E6%8A%97%E6%9A%B4%E4%B9%8B%E6%88%B0.png",
    "alt": "香港抗暴之戰完整卡面",
    "naturalWidth": 1350,
    "naturalHeight": 1100
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
  "text": "進行中\n任務進度 0/1\n非紅軍任務進行中\n點擊任意地方關閉",
  "imageCount": 1,
  "image": {
    "src": "http://127.0.0.1:8767/static/card-art/events/%E9%A6%99%E6%B8%AF%E6%8A%97%E6%9A%B4%E4%B9%8B%E6%88%B0.png",
    "alt": "香港抗暴之戰完整卡面",
    "naturalWidth": 1350,
    "naturalHeight": 1100
  }
}
```

## PASS — click_anywhere_closes_without_same_turn_reopen

```json
{
  "displayAfterRerender": "none"
}
```

## PASS — compact_pinned_event_card_does_not_cover_map_toolbar

```json
{
  "role": "button",
  "tabindex": "0",
  "ariaLabel": "香港抗暴之戰，進行中，點擊放大查看",
  "title": "香港抗暴之戰｜進行中｜點擊放大查看",
  "text": "",
  "imageLoaded": true,
  "controls": [],
  "panel": {
    "left": 1076,
    "top": 0,
    "right": 1256,
    "bottom": 147,
    "width": 180,
    "height": 147
  },
  "toolbar": {
    "left": 948,
    "top": 244,
    "right": 1252,
    "bottom": 283,
    "width": 304,
    "height": 39
  },
  "overlaps": false
}
```

## PASS — compact_event_card_has_no_controls_over_artwork

```json
{
  "controls": [],
  "ariaLabel": "香港抗暴之戰，進行中，點擊放大查看",
  "title": "香港抗暴之戰｜進行中｜點擊放大查看"
}
```

## PASS — compact_event_card_stays_clear_at_narrow_viewport

```json
{
  "panel": {
    "left": 860.7999877929688,
    "top": 96,
    "right": 1004.7999877929688,
    "bottom": 213.60000610351562,
    "width": 144,
    "height": 117.60000610351562
  },
  "toolbar": {
    "left": 758.400036769308,
    "top": 291.20002366573874,
    "right": 1001.6000485875803,
    "bottom": 322.4000218416996
  },
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
    "ariaLabel": "香港抗暴之戰，進行中，點擊放大查看",
    "title": "香港抗暴之戰｜進行中｜點擊放大查看",
    "text": "",
    "imageLoaded": true,
    "controls": [],
    "panel": {
      "left": 1076,
      "top": 0,
      "right": 1256,
      "bottom": 147,
      "width": 180,
      "height": 147
    },
    "toolbar": {
      "left": 948,
      "top": 244,
      "right": 1252,
      "bottom": 283,
      "width": 304,
      "height": 39
    },
    "overlaps": false
  },
  "reopened": {
    "display": "flex",
    "animation": "event-card-zoom-in",
    "text": "進行中\n任務進度 0/1\n非紅軍任務進行中\n點擊任意地方關閉",
    "imageAlt": "香港抗暴之戰完整卡面"
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
