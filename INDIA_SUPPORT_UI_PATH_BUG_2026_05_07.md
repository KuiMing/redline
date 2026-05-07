# INDIA_SUPPORT_UI_PATH_BUG_2026_05_07

日期：2026-05-07

## 現況
backend / runtime 已完成：
- `印度奧援` 可進 purchase_area
- `tibet_dehradun` 可買 `印度奧援`
- `tibet_dehradun` 會被禁止買 `英美奧援`

但在主畫面實戰截圖時發現：
- 透過 `/test/setup-india-support-purchase` 建好的支援卡購買情境
- 進主畫面後，`#purchase` 仍顯示預設 purchase area
- 沒有正確承接 test setup 指定的單張 support card state

## 已保存的截圖
- `india_support_purchase_success.png`
- `anglo_support_purchase_blocked.png`

## 結論
這是一個 UI / 進房 / state 承接路徑 bug，不是 backend 印度研究分析室規則 bug。

下一步應直接修：
- `/test/setup-india-support-purchase` -> 主畫面進房 -> websocket 初始 state -> `#purchase` render
這條鏈。