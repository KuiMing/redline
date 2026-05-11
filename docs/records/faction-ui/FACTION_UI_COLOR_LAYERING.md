# FACTION_UI_COLOR_LAYERING

日期：2026-05-05

## 本輪修正

根據使用者回饋，faction selection UI 現在將：
- 第一層主陣營
- 第二層細項選擇

做出更明確的視覺分層。

## 修改內容

### static/app.js
- 第一層按鈕加上 `faction-primary-btn`
- 第二層按鈕加上 `faction-variant-btn`

### static/style.css
- 第一層主陣營按鈕維持紫色系
- 第二層選項按鈕改為藍色系
- `#factionVariantList` 額外加入：
  - 藍色虛線框
  - 深藍背景
  - 區塊化視覺分離

## 驗證

- 已於瀏覽器驗證點選「臺灣」後，第二層 `綠線 / 藍線` 會以新顏色區分顯示
- 截圖：`taiwan_selection_color_refined.png`
