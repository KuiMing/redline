# FACTION_SELECTION_IMPLEMENTATION

日期：2026-05-04

## 本輪已完成

已把「玩家先選陣營」正式接進主頁與 server 開局流程。

## 已新增內容

### server/main.py
- `lobby_factions`
- `GET /factions`
- `POST /choose-faction`
- `/start` 現在會檢查：
  - 所有玩家都已選 faction
  - 恰好 1 名玩家選 `red_army`
- 建局後，會用玩家自己選的 faction 覆蓋原本隨機分配結果

### static/index.html
- 新增 `#factionPicker`
- 新增 `#factionPickerInfo`
- 新增 `#factionList`

### static/app.js
- 新增 `loadFactions()`
- 新增 `renderFactionPicker()`
- 新增 `chooseFaction()`
- `joinRoom()` 後會顯示 faction selection UI
- `connect()` 後會隱藏 faction picker，進入正式遊戲 UI

## 流程改變

### 舊流程
- create / join
- start
- server 隨機分配 faction
- 再進 base selection / main

### 新流程
- create / join
- 玩家先選 faction
- `/start` 前檢查 faction 是否選完
- 恰好 1 人必須選紅軍
- start 後再依 faction 進入：
  - 固定唯一根據地自動建立
  - 或 `BASE_SELECTION`

## 截圖

已產生並傳送：
- `faction_selection_ui.png`
