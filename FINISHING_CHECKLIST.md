# Redline 完成度審核清單

## 一、尚未完成（按優先順序）

### P0 — 必修：阻止「完成版」成立的缺口

1. **地圖與遊戲引擎尚未真正閉環整合**
   - 現況：Leaflet 地圖以 iframe 形式嵌入，可視化存在，但尚未成為遊戲主互動層。
   - 缺口：
     - 地圖未即時反映真實控制權 / 組織數
     - 點擊城鎮未直接驅動 move / build / action
     - 合法移動高亮尚未接上 rules / current player / turn lock
     - Era / Event 對地圖的視覺效果未接上
   - 完成標準：
     - 地圖成為真正可互動的遊戲操作介面之一
     - 地圖狀態與 WebSocket state 完全同步

2. **完整對局尚未驗證跑通**
   - 現況：局部流程已測，完整一局尚未證明可從 create → join → start → play → victory → end 全程無人工修補跑完。
   - 缺口：
     - 未完成 2 人完整對局驗證
     - 未完成 3/4 人完整流程驗證
   - 完成標準：
     - 至少 2 人完整跑完一局
     - 再驗證 4 人局流程穩定

3. **多人開局/房主流程剛修，仍需穩定性驗證**
   - 現況：host_id / join / start 的對齊 bug 已修補，但仍需回歸測試。
   - 缺口：
     - room host 身分流
     - reconnect / duplicate join / room full / invalid start
   - 完成標準：
     - 開局流程穩定且錯誤訊息明確

4. **前端整合債尚未清理**
   - 現況：Tabs、iframe、gameShell、commandView/mapView 為後補架構；app.js 仍有舊抽象地圖殘留。
   - 缺口：
     - loadTownCoordinates 等舊碼未清
     - map-module.js 舊骨架殘留
     - style.css 含過時抽象地圖樣式
   - 完成標準：
     - 刪除不再使用的抽象地圖殘碼
     - 前端結構清楚、單一路徑

### P1 — 重要：從 Alpha 走向可玩版

5. **Hidden information / turn lock / legality 驗證不足**
   - 非當前玩家操作限制需完整驗證
   - 玩家手牌與資訊隔離需完整驗證
   - 非法行動需在 UI / server 兩邊都清楚阻擋

6. **Era / Event 整合尚未完全產品化**
   - 雖然 engine 存在，但尚未完整驗證視覺與遊戲效果全鏈路
   - 需移除暫時測試用 forced activation

7. **地圖視覺互動仍未收尾**
   - Focus Asia / Fit All 現在能用，但仍需確認：
     - 地圖在 iframe / tab 切換時穩定顯示
     - map.invalidateSize / 初始視角時機穩定

### P2 — 收尾：接近完成版前的 polish

8. **UI/UX 最後整理**
   - 指揮中心與戰略地圖的切換體驗
   - panel 高度與資訊密度
   - 行動提示 / 錯誤提示一致性

9. **壓測與回歸測試**
   - 多回合
   - 多玩家
   - 重整 / 重連
   - 長 log / 多牌局

## 二、建議處理順序

1. 清理前端整合債（P0-4）
2. 穩定多人開局流程（P0-3）
3. 完成地圖 ↔ 引擎閉環（P0-1）
4. 做 2 人完整對局驗證（P0-2）
5. 做 4 人驗證（P0-2）
6. 驗證 hidden info / legality（P1-5）
7. 收掉 Era/Event 測試殘留（P1-6）
8. 最後做 UX polish + 壓測（P2）

## 三、目前判定

- 現階段：**Alpha / Internal Playtest Build**
- 尚不能判定為 Finished
- 若完成 P0 全部項目，才可開始討論是否進入「完成版候選」
