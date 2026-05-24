# 全國人大召開 red_dissolve map highlight UI proof — 2026-05-24

Status: passed

## Scenario

`全國人大召開` 失敗後，紅軍必須從其他玩家的牆內組織中選 1 個瓦解。本 proof 使用正式 browser UI 與測試 endpoint 建立 deterministic 狀態：

- Current event: `全國人大召開`
- Event status: `failure`
- Pending choice: `event_red_dissolve`
- Acting choice player: red
- Target: `viewer｜北京`

## UI evidence

- Choice modal 顯示：`全國人大召開：紅軍選擇要瓦解的組織。`
- Choice modal 顯示目標按鈕：`viewer｜北京`
- Modal 顯示地圖同步提示：`地圖會同步高亮可選目標`
- 戰略地圖 tab 可見，地圖上 `北京` 以橘色外框標示為可選目標。

Screenshot:

- `docs/records/event-cards/NATIONAL_PEOPLE_CONGRESS_RED_DISSOLVE_MAP_HIGHLIGHT_UI_2026_05_24.png`

## Implementation note

`event_red_dissolve` now reuses the existing target-choice map-highlight pipeline:

- `targetChoicesWithMapHighlight`
- map payload mode: `support-targets`

No new intel-network highlight implementation was added.
