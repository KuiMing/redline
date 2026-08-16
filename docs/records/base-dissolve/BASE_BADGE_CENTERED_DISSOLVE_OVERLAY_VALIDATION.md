# 根據地標示置中／瓦解 💀 覆蓋驗證

使用者回報：根據地 🏕 標示原本畫在城鎮圓圈旁邊（左上方偏移），應該置中畫在圓圈正中央；
當北京（紅軍根據地，唯一可被瓦解的根據地——`_can_dissolve_base_target()` 明文規定非紅軍
根據地一律不可瓦解）成為合法瓦解目標時，應該直接用 💀 蓋過根據地標示。

## 根因與修法

`static/leaflet_game_map_logic.js` 的 `renderParticipatingFactionBaseBadges()`：根據地
divIcon 的 `iconAnchor` 原本是 `[28 + index * 24, 25]`（`iconSize` 為 `[28,28]`），把整個
標示往城鎮座標的左上方推開，並未與城鎮圓圈中心對齊。改成 `[14 + index * 10, 14]`——單一
根據地時精準置中（14 恰為 28 的一半），同城鎮多個根據地的極少數情況才用小幅偏移避免完全
重疊。

瓦解目標的 💀 標示（`dissolve-target-badge`）本來就已置中（`iconSize:[26,26]`、
`iconAnchor:[13,13]`），且 `zIndexOffset`（1000）高於根據地標示（800+index）。兩者座標
重合後，💀 自然會蓋過 🏕，不需要額外處理。

## 驗證

Playwright 實際開一局（A=紅軍、B=臺灣），切到戰略地圖聚焦北京：

1. `base_badge_centered_plain.png`——一般狀態下，🏕 置中疊在北京圓圈正中央。
2. `base_badge_dissolve_skull_overlay.png`——模擬情報網等瓦解互動（`applySupportChoiceHighlight`，
   `actionKind: 'dissolve'`，目標為北京），💀 完全蓋過 🏕，紅色瓦解外框正確圈住北京。

完整 pytest 366/366 passed（純前端地圖渲染改動，不影響後端邏輯）。
