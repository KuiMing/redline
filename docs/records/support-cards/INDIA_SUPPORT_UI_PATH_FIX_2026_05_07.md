# INDIA_SUPPORT_UI_PATH_FIX_2026_05_07

日期：2026-05-07

## 問題
先前 `/test/setup-india-support-purchase` 建好的 runtime 狀態，進入主畫面後會被 `/start` 重建新 Game，導致：
- purchase 區回到預設內容
- 前端實戰截圖無法真實反映 support 購買情境

## 修正
### server/main.py
在 `/start` 中新增：
- 若 `game_id` 已存在於 `manager.games`
- 直接回傳 `{success: true, reused: true}`
- 不再重建 fresh Game

這讓 test/setup endpoint 建好的 state 可以被主畫面 / websocket 初始 state 正確承接。

## 修正後實戰結果
### 印度奧援情境
- purchase 區只顯示：`印度奧援`
- 點擊後卡片消失
- log 出現：`tibet bought 印度奧援`

### 英美奧援情境
- purchase 區只顯示：`英美奧援`
- 點擊後卡片仍留在場上
- 符合 `印度研究分析室` 限制

## 產物
- `INDIA_SUPPORT_UI_BATTLESHOT_FIXED.json`
- `india_support_purchase_success_fixed.png`
- `anglo_support_purchase_blocked_fixed.png`

## 結論
這條前端 / 進房 / state 承接 bug 已修正，
現在 support 購買情境終於能在主畫面上被真實呈現與截圖驗證。
