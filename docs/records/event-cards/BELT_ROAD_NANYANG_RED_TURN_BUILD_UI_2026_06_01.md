# 一帶一路南洋：紅軍回合發動與地圖選點 UI 驗證

日期：2026-06-01

## 驗證目標

- 「一帶一路 南洋」若在非紅軍（BEN）回合抽出，不應立刻要求紅軍選地點；事件狀態應為等待紅軍回合。
- 輪到紅軍事件階段時才發動自動效果，並產生 `event_build_organization` 待選。
- 地圖上的橘色可選城鎮可被點選；左側「在目前城鎮建立組織（效果）」按鈕會啟用，按下後能成功建立組織。

## Runtime 證據

使用 `/test/setup-belt-road-red-turn-proof` 建立 proof game，並將 `advance_to_red=true`：

- 初始事件抽出者：BEN
- 初始階段：`event`
- 初始事件狀態：`auto_pending`
- 初始 pending choice：`null`
- 紅軍回合階段：`event`
- 紅軍回合事件狀態：`auto`
- 紅軍 pending choice：`event_build_organization`
- pending choice player：紅軍
- 範例可選城鎮：`仰光`, `佬沃`, `吉隆坡`, `新加坡`, `曼谷`

## UI 互動證據

在官方 UI 的戰略地圖 iframe 中：

1. 紅軍事件階段顯示「一帶一路 南洋」。
2. 地圖顯示南洋可選城鎮橘色高亮。
3. 呼叫同一套地圖點選流程選取 `新加坡` 後，側欄按鈕文字變為「在目前城鎮建立組織（效果）」且 `disabled=false`。
4. 按下該按鈕後，WebSocket resolve choice 成功，紅軍在 `新加坡` 的組織數變成 `1`，pending choice 清空。

## 截圖

- `BELT_ROAD_NANYANG_RED_TURN_BUILD_UI_2026_06_01.png`

## 相關修正

- `server/game.py`：自動事件若指定 `player_faction` 且目前玩家不是該 faction，先設為 `auto_pending`；輪到目標玩家事件階段才套用效果。
- `static/leaflet_game_map_logic.js`：讓橘色事件可選城鎮高亮本身也能點選並啟用側欄建組織按鈕，避免點擊被高亮圖層攔截後無法選地點。
- `server/main.py`：新增 `/test/setup-belt-road-red-turn-proof` 供 UI proof 與回歸驗證使用。
