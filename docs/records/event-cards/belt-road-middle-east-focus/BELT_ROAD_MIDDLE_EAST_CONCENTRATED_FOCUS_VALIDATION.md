# 一帶一路天方集中聚焦驗證

Summary: **7/7 passed**

- Screenshot: `docs/records/event-cards/belt-road-middle-east-focus/belt_road_middle_east_concentrated_focus_20260823.png`
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

## PASS — formal_red_turn_has_middle_east_event_choice

```json
{
  "choice_key": "event_build_organization",
  "region": "middle_east",
  "candidate_names": [
    "吉爾吉特",
    "喀布爾",
    "拉瓦爾品第",
    "米蘭沙阿",
    "費札巴德",
    "霍斯特"
  ]
}
```

## PASS — middle_east_focus_matches_current_legal_build_town_bounds

```json
{
  "center": {
    "lat": 35.05,
    "lng": 71.83574999999999
  },
  "zoom": 6,
  "bounds": {
    "north": 39.605688178320804,
    "south": 30.221101852485987,
    "east": 81.89208984375001,
    "west": 61.76513671875001
  },
  "primary": {
    "吉爾吉特": {
      "lat": 35.92,
      "lng": 74.464,
      "visible": true
    },
    "喀布爾": {
      "lat": 34.5553,
      "lng": 69.2075,
      "visible": true
    },
    "拉瓦爾品第": {
      "lat": 33.5651,
      "lng": 73.0479,
      "visible": true
    },
    "米蘭沙阿": {
      "lat": 32.984,
      "lng": 70.07,
      "visible": true
    },
    "費札巴德": {
      "lat": 37.116,
      "lng": 70.58,
      "visible": true
    },
    "霍斯特": {
      "lat": 33.333,
      "lng": 69.92,
      "visible": true
    }
  },
  "legalVisibility": {
    "吉爾吉特": true,
    "喀布爾": true,
    "拉瓦爾品第": true,
    "米蘭沙阿": true,
    "費札巴德": true,
    "霍斯特": true
  },
  "legalBounds": {
    "center": {
      "lat": 35.05,
      "lng": 71.83574999999999
    },
    "north": 37.116,
    "south": 32.984,
    "east": 74.464,
    "west": 69.2075
  },
  "legalFitZoom": {
    "0": 7,
    "8": 7,
    "12": 7,
    "16": 7,
    "24": 7,
    "32": 7,
    "48": 7,
    "110": 6
  },
  "hint": "一帶一路 天方：在指定區域免費建立 1 個組織。 可建立城鎮：6 個。尚可建立組織：1 個。地圖上已用中性色外框標出可選城鎮。請點選中性色外框城鎮，然後使用左側「在目前城鎮建立組織（效果）」按鈕完成建立。"
}
```

## PASS — all_primary_middle_east_towns_are_visible

```json
{
  "吉爾吉特": {
    "lat": 35.92,
    "lng": 74.464,
    "visible": true
  },
  "喀布爾": {
    "lat": 34.5553,
    "lng": 69.2075,
    "visible": true
  },
  "拉瓦爾品第": {
    "lat": 33.5651,
    "lng": 73.0479,
    "visible": true
  },
  "米蘭沙阿": {
    "lat": 32.984,
    "lng": 70.07,
    "visible": true
  },
  "費札巴德": {
    "lat": 37.116,
    "lng": 70.58,
    "visible": true
  },
  "霍斯特": {
    "lat": 33.333,
    "lng": 69.92,
    "visible": true
  }
}
```

## PASS — all_legal_targets_remain_in_choice_and_hint

```json
{
  "candidate_count": 6,
  "candidate_names": [
    "吉爾吉特",
    "喀布爾",
    "拉瓦爾品第",
    "米蘭沙阿",
    "費札巴德",
    "霍斯特"
  ],
  "hint": "一帶一路 天方：在指定區域免費建立 1 個組織。 可建立城鎮：6 個。尚可建立組織：1 個。地圖上已用中性色外框標出可選城鎮。請點選中性色外框城鎮，然後使用左側「在目前城鎮建立組織（效果）」按鈕完成建立。"
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
