# TAIWAN_UNIQUE_BASE_AUTOFILL

日期：2026-05-05

## 問題

臺灣（綠線 / 藍線）屬於：
- 有 faction variant
- 但 base 其實只有唯一合法選項（臺北）

先前 faction picker 改成必須 faction + base 都選完才顯示 detail panel / confirm，
結果在第二層點了綠線後：
- `pendingFactionChoice` 有值
- 但 `pendingFactionBaseChoice` 沒自動填入唯一根據地
- 導致 detail panel 與確認按鈕不出現

## 本輪修正

### static/app.js
- `chooseFaction(factionId)` 現在會檢查該 faction 的 `base_options`
- 若 `base_options.length === 1`
  - 直接自動填入 `pendingFactionBaseChoice`

## 效果

### 臺灣（綠線 / 藍線）
- 選完 variant 後
- 自動帶入唯一根據地：`臺北`
- 立即顯示：
  - 根據地
  - 能力
  - 規則
  - 勝利條件
  - 確認按鈕

## 驗證

### 臺灣（綠線）
- 顯示：`目前陣營：臺灣（綠線）｜根據地：臺北`
- detail panel 正常顯示
- 確認按鈕正常顯示
- 截圖：`taiwan_green_selection_ui_fixed3.png`
