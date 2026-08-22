# 一帶一路南洋集中聚焦驗證

Summary: **7/7 passed**

- Screenshot: `docs/records/event-cards/belt-road-nanyang-focus/belt_road_nanyang_concentrated_focus_20260822.png`
- Session credentials and identifiers: `[REDACTED]`

## PASS — prior_build_session_and_player_view_are_established

```json
{
  "center": {
    "lat": 39.9042,
    "lng": 116.4074
  },
  "zoom": 9
}
```

## PASS — formal_red_turn_has_nanyang_event_choice

```json
{
  "choice_key": "event_build_organization",
  "region": "southeast_asia",
  "candidate_names": [
    "仰光",
    "佬沃",
    "吉隆坡",
    "新加坡",
    "曼谷",
    "老街",
    "芒賽",
    "賀猛",
    "邦康",
    "雅加達",
    "馬尼拉"
  ]
}
```

## PASS — nanyang_focus_uses_concentrated_region_view

```json
{
  "center": {
    "lat": 8,
    "lng": 104
  },
  "zoom": 5,
  "bounds": {
    "north": 19.145168196205297,
    "south": -3.425691524418062,
    "east": 124.14550781250001,
    "west": 83.89160156250001
  },
  "primary": {
    "曼谷": {
      "lat": 13.7563,
      "lng": 100.5018,
      "visible": true
    },
    "吉隆坡": {
      "lat": 3.139,
      "lng": 101.6869,
      "visible": true
    },
    "新加坡": {
      "lat": 1.3521,
      "lng": 103.8198,
      "visible": true
    }
  },
  "hint": "一帶一路 南洋：在指定區域免費建立 1 個組織。 可建立城鎮：11 個。尚可建立組織：1 個。地圖上已用中性色外框標出可選城鎮。請點選中性色外框城鎮，然後使用左側「在目前城鎮建立組織（效果）」按鈕完成建立。"
}
```

## PASS — primary_nanyang_towns_are_visible

```json
{
  "曼谷": {
    "lat": 13.7563,
    "lng": 100.5018,
    "visible": true
  },
  "吉隆坡": {
    "lat": 3.139,
    "lng": 101.6869,
    "visible": true
  },
  "新加坡": {
    "lat": 1.3521,
    "lng": 103.8198,
    "visible": true
  }
}
```

## PASS — all_legal_targets_remain_in_choice_and_hint

```json
{
  "candidate_count": 11,
  "candidate_names": [
    "仰光",
    "佬沃",
    "吉隆坡",
    "新加坡",
    "曼谷",
    "老街",
    "芒賽",
    "賀猛",
    "邦康",
    "雅加達",
    "馬尼拉"
  ],
  "hint": "一帶一路 南洋：在指定區域免費建立 1 個組織。 可建立城鎮：11 個。尚可建立組織：1 個。地圖上已用中性色外框標出可選城鎮。請點選中性色外框城鎮，然後使用左側「在目前城鎮建立組織（效果）」按鈕完成建立。"
}
```

## PASS — non_acting_viewer_keeps_own_base_focus

```json
{
  "center": {
    "lat": 25.033,
    "lng": 121.5654
  },
  "zoom": 9
}
```

## PASS — browser_console_has_no_errors

```json
[]
```
