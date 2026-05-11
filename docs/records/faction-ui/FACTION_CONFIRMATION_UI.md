# FACTION_CONFIRMATION_UI

日期：2026-05-05

## 本輪修正

根據使用者回饋，faction selection UI 補上三件事：

1. 選到的按鈕要用亮色呈現
2. 說明文字要顯示玩家看得懂的中文名稱，而不是內部英文 id
3. 在真正送出 faction 前，要有一個最後確認按鈕

## 修改內容

### static/index.html
- 新增 `#factionConfirmBar`
- 新增 `#confirmFactionBtn`

### static/app.js
- `chooseFaction()` 改為先暫存 `pendingFactionChoice`
- 新增 `confirmFactionChoice()`，按下確認後才真正 POST `/choose-faction`
- 新增 `factionDisplayName()`：
  - `uyghur_family` → `維吾爾`
  - `tibet_family` → `西藏`
  - `taiwan_green` → `臺灣（綠線）`
  - `taiwan_blue` → `臺灣（藍線）`
- `renderFactionPicker()` 現在會：
  - 高亮目前選中的第一層 / 第二層按鈕
  - 顯示 `目前陣營：...`
  - 顯示最後確認按鈕

### static/style.css
- 新增第一層 / 第二層 `.active` 亮色樣式
- 新增確認按鈕樣式（橘色強調）

## 驗證

### 維吾爾
- 顯示：`目前陣營：維吾爾`
- 主陣營按鈕亮起
- 有確認按鈕
- 截圖：`uyghur_confirm_ui.png`

### 臺灣（綠線）
- 顯示：`目前陣營：臺灣（綠線）`
- 第二層按鈕亮起
- 有確認按鈕
- 截圖：`taiwan_confirm_ui_v2.png`
