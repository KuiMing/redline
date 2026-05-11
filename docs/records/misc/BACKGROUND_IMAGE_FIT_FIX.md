# BACKGROUND_IMAGE_FIT_FIX

日期：2026-05-05

## 本輪修正

修正主頁背景圖左右兩側被裁切的問題。

## 修改

### static/style.css
原本：
- `background-size: cover`

現在改為：
- `background-size: contain`
- `background-repeat: no-repeat`
- `background-position: center center`
- 額外保留 `background-color: #05080C` 作為留白底色

## 效果

- 背景圖會完整保留在 viewport 內
- 不再為了鋪滿整個畫面而裁掉左右內容
- 若畫面比例不同，空白區域由深色背景補齊

## 驗證

- 已重新啟動 server
- 已在瀏覽器截圖驗證：`background_contain_fixed.png`
