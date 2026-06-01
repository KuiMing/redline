# 一帶一路南洋：地圖選鎮後可建立組織 UI 驗證

日期：2026-06-01

## 問題

在紅軍事件階段觸發 `一帶一路 南洋` 後，地圖上橘色可選城鎮雖然顯示，但點選城鎮後左側 sidebar 仍顯示「尚未選取城鎮」，因此「在目前城鎮建立組織」按鈕維持不可用，也沒有顯示城鎮資訊。

## 修正

- `static/leaflet_game_map.html`
  - 城鎮 label 加上 `pointer-events: none`，避免標籤蓋住 canvas/marker 點擊。
  - `leaflet_game_map_logic.js` 加 cache-busting query，確保瀏覽器取得新版地圖互動邏輯。
- `static/leaflet_game_map_logic.js`
  - `eventBuildChoiceForTown()` 若 pending choice 的 towns 沒有 index，會依 towns 陣列位置補出可送回後端的 index。
  - 在 Leaflet map click 上加入橘色事件城鎮的 proximity hit-test，點到橘色圈附近也會選取對應城鎮。
  - game state refresh 時若已有 selected town，會同步刷新城鎮資訊 panel，建立後能顯示最新控制者/組織數。

## Browser proof

測試 setup：

```json
{
  "endpoint": "/test/setup-belt-road-red-turn-proof",
  "payload": {
    "advance_to_red": true,
    "event_name": "一帶一路 南洋"
  }
}
```

實測：

```json
{
  "afterSelect": {
    "selected": "仰光",
    "status": "仰光",
    "button": "在目前城鎮建立組織（效果）",
    "disabled": false,
    "infoIncludes": ["仰光", "靜態統治者：南洋", "當前控制者：無組織"]
  },
  "afterBuild": {
    "pending": null,
    "redOrgs": {"北京": 1, "仰光": 1},
    "iframeTownState": [{"player": "紅軍", "count": 1}],
    "infoIncludes": ["當前控制者：紅軍", "當前組織總數：1", "視覺狀態：有組織（1）"]
  }
}
```

Action log：

```text
[Turn 1] Event drawn: 一帶一路 南洋 (auto deferred)
[Turn 1] End of turn for BEN
[Turn 1] 紅軍 built organization in 仰光 via event
```

Screenshot：`BELT_ROAD_NANYANG_MAP_TOWN_SELECTED_BUILD_READY_2026_06_01.png`
