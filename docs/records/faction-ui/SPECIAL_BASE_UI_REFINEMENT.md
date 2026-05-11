# SPECIAL_BASE_UI_REFINEMENT

日期：2026-05-04

## 本輪修正

根據使用者回饋，根據地選擇 UI 不應直接一次列出所有展開後的合法城鎮，而應先只列出 faction 卡面上的「可選根據地」選項。

## 已實作的新流程

### 第一層：根據地類別
主頁 UI 現在先顯示 faction `bases` 原始選項，例如：
- `任意牆內`
- `任意英美城鎮`

### 第二層：具體城鎮
當玩家點某個泛型選項後，才展開對應的合法城鎮清單。

## 已做的程式修改

### server/game.py
- `pending_base_choices` 現在不再只是單純 town list
- 改為：
  - `labels`: 原始 bases 選項
  - `resolved`: 每個 label 對應的合法城鎮清單
- `set_base_choice()` 現在同時接受：
  - `label`
  - `town`

### static/app.js
- `renderBaseSelection()` 改為兩段式流程
- 第一層先顯示 labels
- 第二層才顯示具體 towns
- 新增返回類別按鈕

## 截圖驗證

已產生並傳送：
- `base_selection_ui_labels.png`
- `base_selection_ui_towns.png`

## 結果

現在主頁 UI 已符合：
- 先只列出陣營卡上的可選根據地
- 不再直接把所有展開後的合法城鎮一次丟給玩家
