# Event Card Zoom Preview Validation

Summary: 9/9 passed

- Open screenshot: `docs/records/event-cards/event_card_zoom_preview_open.png`
- Pinned screenshot: `docs/records/event-cards/event_card_zoom_preview_pinned.png`

## PASS — dedicated_event_reveal_overlay_exists

```json
"event reveal DOM"
```

## PASS — plain_text_only_no_art_asset_binding

```json
"event renderer does not reference generated art"
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
  "text": "本回合事件\n香港抗暴之戰\n任務事件｜進行中\n事件結果：\n非紅軍任務進行中\n任務條件：\n打出購買費用含資金的卡牌至少 1 次\n進度：0/1\n成功獎勵：\n非紅軍：獲得 2 張宣傳家\n失敗／紅軍效果：\n紅軍：選 1 張手牌棄掉\n點擊任意地方關閉",
  "imageCount": 0,
  "centerDelta": {
    "x": 0,
    "y": 0
  },
  "cardRect": {
    "left": 260,
    "top": 104.703125,
    "width": 760,
    "height": 510.59375
  }
}
```

## PASS — expanded_preview_shows_current_plain_text_event

```json
{
  "text": "本回合事件\n香港抗暴之戰\n任務事件｜進行中\n事件結果：\n非紅軍任務進行中\n任務條件：\n打出購買費用含資金的卡牌至少 1 次\n進度：0/1\n成功獎勵：\n非紅軍：獲得 2 張宣傳家\n失敗／紅軍效果：\n紅軍：選 1 張手牌棄掉\n點擊任意地方關閉",
  "imageCount": 0
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
    "text": "目前事件\n香港抗暴之戰\n任務事件｜進行中\n事件結果：非紅軍任務進行中\n任務條件：打出購買費用含資金的卡牌至少 1 次\n進度：0/1\n成功獎勵：非紅軍：獲得 2 張宣傳家\n失敗／紅軍效果：紅軍：選 1 張手牌棄掉\n點擊放大查看"
  },
  "reopened": {
    "display": "flex",
    "animation": "event-card-zoom-in",
    "text": "本回合事件\n香港抗暴之戰\n任務事件｜進行中\n事件結果：\n非紅軍任務進行中\n任務條件：\n打出購買費用含資金的卡牌至少 1 次\n進度：0/1\n成功獎勵：\n非紅軍：獲得 2 張宣傳家\n失敗／紅軍效果：\n紅軍：選 1 張手牌棄掉\n點擊任意地方關閉"
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
