# FACTION_PICKER_WITH_LOBBY_BASES

日期：2026-05-05

## 本輪修正

使用者指出蒙古其實也有 3 個根據地可以選，不能像先前那樣直接進 detail panel。

因此 faction picker 流程進一步改為：

1. 選擇陣營
2. 選擇根據地
3. 顯示能力 / 特殊規則 / 勝利條件
4. 顯示確認按鈕
5. 按下確認後，才正式寫入 lobby faction + lobby base

## 新增後端狀態

### server/main.py
新增：
- `lobby_bases = {game_id: {player_id: base_name}}`

### /choose-faction
- 現在支援 `base_name`
- 會驗證該 faction 可用的 base options
- 成功後寫入：
  - `lobby_factions`
  - `lobby_bases`

### /lobby/{game_id}
- 現在會額外回傳 `bases`

### /factions
- 每個 faction option 現在都會補上 `base_options`
- 特別對以下 faction 明確補齊：
  - 蒙古：烏蘭巴托 / 東京 / 紐約
  - 滿洲：東京 / 舊金山 / 海參崴
  - 哈薩克：阿拉木圖
  - 香港：香港城
  - 維吾爾：伊斯坦堡 / 慕尼黑 / 華盛頓 / 阿拉木圖
  - 西藏：達蘭薩拉 / 德拉敦 / 哲古宗

## 前端改動

### static/app.js
- 新增 `pendingFactionBaseChoice`
- faction picker 現在支援：
  - 第一層主陣營
  - 第二層變體（若有）
  - 第三層根據地按鈕 `#factionBaseList`
- 只有在 faction 與 base 都選好後，才顯示 detail panel 與確認按鈕
- `confirmFactionChoice()` 現在會把 `base_name` 一起送到 server

### static/index.html
- 新增 `#factionBaseList`

## 驗證

### 蒙古
- 現在會先顯示 3 個根據地：
  - 烏蘭巴托
  - 東京
  - 紐約
- 選完後才顯示 detail panel 與確認按鈕
- 截圖：`mongol_base_selection_ui.png`
