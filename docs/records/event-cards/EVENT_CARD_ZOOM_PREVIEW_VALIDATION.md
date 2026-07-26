# Event Card Zoom Preview Validation

Summary: 9/9 passed

- Open screenshot: `docs/records/event-cards/event_card_zoom_preview_open.png`
- Pinned screenshot: `docs/records/event-cards/event_card_zoom_preview_pinned.png`

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

## PASS — zoom_animation_and_cache_bust_exist

```json
"zoom keyframes + CSS/JS cache bust"
```

## PASS — turn_start_auto_opens_centered_zoom_preview

```json
{
  "overlayDisplay": "flex",
  "animationName": "event-card-zoom-in",
  "text": "進行中\n任務進度 0/1\n非紅軍任務進行中\n點擊任意地方關閉",
  "imageCount": 1,
  "image": {
    "src": "http://127.0.0.1:8000/static/card-art/events/%E9%A6%99%E6%B8%AF%E6%8A%97%E6%9A%B4%E4%B9%8B%E6%88%B0.png",
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
    "src": "http://127.0.0.1:8000/static/card-art/events/%E9%A6%99%E6%B8%AF%E6%8A%97%E6%9A%B4%E4%B9%8B%E6%88%B0.png",
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

## PASS — top_right_event_panel_reopens_preview

```json
{
  "panel": {
    "role": "button",
    "tabindex": "0",
    "text": "任務進度 0/1\n點擊放大查看",
    "imageLoaded": true
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

## PASS — browser_console_has_no_errors

```json
[]
```
