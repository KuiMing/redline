# FACTION_DETAIL_AFTER_BASE_SELECTION

日期：2026-05-05

## 本輪修正

根據使用者回饋：
- 若 faction 的最終能力 / 規則 / 獲勝條件會隨根據地分支而改變
- 就不應該在根據地選擇前提前顯示最終版本

## 目前調整

### 維吾爾 / 西藏
在 faction selection 階段：
- 不再提前顯示最終能力與最終獲勝條件
- 改為只顯示：
  - 根據地分支列表
  - 提示文字：需先完成根據地選擇，之後再顯示最終能力 / 獲勝條件

### 一般 faction
- 若能力 / 規則 / 獲勝條件不依賴後續 base variant
- 則仍可在 faction selection 階段直接顯示 detail panel

## 修改內容

### server/main.py
- `uyghur_family` / `tibet_family` 在 `/factions` 中改成提供：
  - `base_variants`
  - 說明用 `special_rules`
- 不再直接塞最終 `abilities` / `win_conditions`

### static/app.js
- `renderFactionDetails()` 現在若偵測到 `base_variants`
  - 先顯示根據地分支列表
  - 能力 / 獲勝條件顯示為待根據地選完後再揭示

## 驗證

### 維吾爾
- 顯示根據地分支：伊斯坦堡 / 慕尼黑 / 華盛頓 / 阿拉木圖
- 能力區顯示提示而非最終能力
- 截圖：`uyghur_prebase_detail_ui.png`

### 民運派（一般 faction 對照）
- 仍直接顯示能力 / 規則 / 獲勝條件
- 截圖：`rebel_preconfirm_detail_ui.png`
