# FACTION_DETAIL_PANEL_UI

日期：2026-05-05

## 本輪修正

根據使用者要求，faction selection UI 現在補上：
- 陣營能力面板
- 規則面板
- 獲勝條件面板
- 並將確認按鈕移到說明面板的下方

## 修改內容

### server/main.py
- `/factions` 現在對 `uyghur_family` / `tibet_family` 補上可供 UI 顯示的：
  - `abilities`
  - `special_rules`
  - `win_conditions`
- 其中維吾爾 / 西藏的規則說明會額外提示：根據地將在下一步決定

### static/index.html
- 新增 `#factionDetailPanel`
- 內含：
  - `#factionDetailTitle`
  - `#factionDetailAbilities`
  - `#factionDetailRules`
  - `#factionDetailWin`
- `確認陣營` 按鈕移到 detail panel 底部

### static/app.js
- 新增 `factionOptionById()`
- 新增 `renderFactionDetails(factionId)`
- `renderFactionPicker()` 現在會根據目前選中的 faction 顯示說明面板
- 面板可顯示：
  - `abilities_text`
  - `abilities`
  - `setup_effects`
  - `special_rules`
  - `restrictions`
  - `win_condition_text`
  - `win_conditions`

### static/style.css
- 新增 detail panel 視覺樣式
- 確認按鈕保持放在說明面板底部

## 驗證

### 維吾爾
- 顯示完整說明面板
- 顯示標題：`維吾爾`
- 確認按鈕位於面板底部
- 截圖：`uyghur_detail_panel_ui.png`

### 反賊（民運派示例）
- 顯示完整說明面板
- 顯示標題：`民運派`
- 確認按鈕位於面板底部
- 截圖：`rebel_detail_panel_ui.png`
