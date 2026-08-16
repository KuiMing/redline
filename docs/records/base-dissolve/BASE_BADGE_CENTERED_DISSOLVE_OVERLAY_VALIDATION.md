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

## 後續調整（同日）：根據地圓圈外框改用陣營色並加粗

使用者回饋：根據地的圓圈外框也該搭配該根據地的陣營色，並加粗一點。原本
`markerStyleForTown()` 的外框色只依「是否為目前檢視玩家所擁有／是否有共享組織」決定
（白／中性灰／黃三種），跟城鎮所屬陣營色無關。新增 `baseFactionIdForTown()` 判斷該城
鎮是不是某玩家的根據地，是的話外框改用 `factionCampColor()` 取得的陣營色，並在原本的
粗細基礎上再加粗 1px（沒有共享組織的情況下）；有共享組織時仍優先顯示黃色提示，語意
不變。

驗證：程式化讀取 `markerStyleForTown()` 的實際回傳值確認三個陣營各自的根據地城鎮：
紅軍（北京）`#f04f56`、香港（香港城）`#a855f7`、臺灣綠線（臺北）`#4ade80`，皆與
`palette` 定義一致，且粗細比修改前多 1px。另外用 Playwright 對戰略地圖各自的根據地
城鎮貼近裁切放大截圖，肉眼也能明顯分辨三種顏色（`base_badge_outline_red_army_beijing.png`、
`base_badge_outline_hong_kong.png`、`base_badge_outline_taiwan.png`）。完整 pytest
366/366 passed。
