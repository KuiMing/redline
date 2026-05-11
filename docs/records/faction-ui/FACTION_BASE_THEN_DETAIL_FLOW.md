# FACTION_BASE_THEN_DETAIL_FLOW

日期：2026-05-05

## 本輪修正

根據使用者最新要求，流程改為：

1. 選擇陣營
2. 選擇根據地
3. 顯示能力 / 特殊規則 / 勝利條件
4. 顯示確認按鈕

## 重要調整

### 維吾爾 / 西藏
不再採用：
- 選主陣營後進 BASE_SELECTION，再看 detail panel

改為：
- 第一層先選主陣營
- 第二層直接選根據地分支（例如慕尼黑 / 德拉敦）
- 一旦選定具體根據地分支，detail panel 才顯示該 variant 的：
  - 能力
  - 特殊規則
  - 勝利條件
- 確認按鈕仍放在 detail panel 下方

### 代表意義
這代表對維吾爾 / 西藏而言：
- 根據地選擇已提前併入 faction picker 階段
- 避免在能力尚未確定前就顯示錯誤或不完整資訊

## 修改內容

### server/main.py
- `/factions` 中的 `uyghur` / `tibet` 改回 `mode: variant`
- 第二層選項直接列出具體根據地分支對應 faction：
  - 維吾爾：伊斯坦堡 / 慕尼黑 / 華盛頓 / 阿拉木圖
  - 西藏：達蘭薩拉 / 德拉敦 / 哲古宗

### static/app.js
- `factionDisplayName()` 支援顯示：
  - `維吾爾（慕尼黑）`
  - `西藏（德拉敦）`
- `renderFactionDetails()` 改為：
  - 一旦已選到具體 variant faction，就直接顯示該分支 detail
- faction picker 流程現在可直接支援：
  - 主陣營 → 根據地分支 → detail panel → 確認

## 驗證

### 維吾爾（慕尼黑）
- 點選維吾爾後，第二層列出：伊斯坦堡 / 慕尼黑 / 華盛頓 / 阿拉木圖
- 點選慕尼黑後：
  - 顯示 `目前陣營：維吾爾（慕尼黑）`
  - detail panel 顯示該分支能力 / 規則 / 勝利條件
  - 顯示確認按鈕
- 截圖：`uyghur_base_then_detail_ui.png`
