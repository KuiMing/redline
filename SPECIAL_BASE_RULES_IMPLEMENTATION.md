# SPECIAL_BASE_RULES_IMPLEMENTATION

日期：2026-05-04

## 本輪已完成

已開始把特殊根據地規則從 deterministic fallback 升級為正式可選擇流程的第一版。

## 主要變更

### 1. 新增 `GamePhase.BASE_SELECTION`
當一局遊戲中存在：
- 多候選根據地 faction
- flex_base faction
- 特殊可選根據地 faction

遊戲現在會先進入：
- `game_phase = base_selection`

而不是直接進入主流程。

### 2. 新增 pending base choice 機制
`Game` 現在會計算：
- `pending_base_choices`

內容是：
- 哪些 player 還需要選根據地
- 每個 player 合法可選的候選城鎮清單

### 3. 新增 `set_base_choice()`
現在 server 端已有正式 API / action 能力：
- `action = set_base`
- 由玩家自己提交想選的根據地

驗證內容：
- 必須在 `BASE_SELECTION` phase
- 必須是自己的 pending choice
- 必須在合法候選清單內
- 不可與其他玩家已選根據地衝突

### 4. 固定唯一根據地仍可自動建立
如果 faction 是唯一 fixed base：
- 仍直接自動建立
- 不進 pending choice

## 目前產品化到什麼程度

### 已具備
- 多候選 / flex_base / special base 可由 server 正式進入選擇流程
- 狀態會顯示在 `pending_base_choices`
- 玩家可透過 websocket action `set_base` 正式提交選擇

### 尚未完成
- 主頁 UI 尚未做根據地選擇介面
- 香港根據地遷移（對局中動態改 base）尚未產品化
- 目前完整流程驗證腳本還沒改成覆蓋 `BASE_SELECTION` 互動流程

## 這代表什麼

現在已經不是「特殊根據地只能 deterministic 自動選」，而是：

> server / state machine 層已經開始支援正式的根據地選擇流程。
