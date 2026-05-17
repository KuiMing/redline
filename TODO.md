# Redline TODO

最後更新：2026-05-18

## 工作規則
- 每次開始新工作前，先把對應項目加入此檔。
- 同一時間只保留一個 `in_progress`。
- 完成後立刻改成 `done`，並在項目下補一行簡短結果紀錄。
- `todo` 只放真正下一步要做的事；已完成紀錄集中放在下方「已完成」。
- `note` 不是立即待做，只保留盤點或後續提醒。

## 目前 active todo
- 目前沒有 active `todo` / `in_progress` 項目。

## 已完成

### 行動卡／指令卡邏輯與回歸測試
- [done] 補齊多張 action card regression coverage（合作談判、思想建設、思想家、宣傳家、資本家等）。
  - 2026-05-12：完成多張行動卡測試補強與既有 regressions 擴充。
- [done] 修正情報網 choose-one branching、商業網絡借用行為、共識鍛造棄牌後 bonus 流程。
  - 2026-05-12：完成相關行動卡／指令卡邏輯修補。
- [done] 情報網：補完整 UI 驗證與收尾整理。
  - 2026-05-18：已修正第一選項改為至多 3 位其他玩家各獲得 1 張內鬥，補 `discard_pile` state 序列化與戰況總覽棄牌堆顯示；正式 UI 截圖已可同畫面證明 enemyA/enemyB/enemyC 各自「棄牌 1／棄牌堆 內鬥」；提交 `27f2ab1` `[verified] finish intel network discard proof flow`。
- [done] 企業人脈：補完整 UI 驗證與收尾整理。
  - 2026-05-15：已完成購買區借牌選擇 UI、交通經驗乙續行 +4 驗證、正式 UI 截圖與 follow-up commit。
- [done] 企畫遊說：補完整 UI 驗證與收尾整理。
  - 2026-05-15：已完成高費用（思想家→資金4）與低費用（領導→資金2）兩種正式 UI 驗證。
- [done] 模仿戰術：補完整 UI 驗證與收尾整理。
  - 2026-05-15：已補目標玩家選擇 modal、完成正式手牌 UI 截圖，並提交 `6e5c48b` `Add imitation tactics target selection modal`。
- [done] 誘導虛耗：補完整 UI 驗證與收尾整理。
  - 2026-05-16：已完成正式 UI 逐步截圖、目標玩家自選棄牌流程驗證，並將提示文案修正為「你可以移除誘導虛耗這張卡牌」。
- [done] 批判：完成完整 UI 驗證與收尾整理。
  - 2026-05-15：依目前驗證與整理結果，批判已完成，不再列入 active todo。
- [done] 批鬥：完成完整 UI 驗證與收尾整理。
  - 2026-05-15：依目前驗證與整理結果，批鬥已完成，不再列入 active todo。

### pending-choice / modal / UI 系統層
- [done] 修正 multi-card choice modal flow。
  - 2026-05-14：完成多選 modal 流程修正。
- [done] 修正 pending card choice 時 action completion 過早完成問題。
  - 2026-05-14：已改為 pending choice 未解前不提早完成效果鏈。
- [done] 補 pending-choice consensus flow regression coverage。
  - 2026-05-14：已補對應回歸測試。
- [done] 補齊系統層缺口（option_choice / multi_card_choice / reveal / peek / 選 town / target 互動 UI）。
  - 2026-05-15：依使用者最新確認，這批系統層缺口已補上，不再列為待辦。
- [done] 修正 card UI validator 與 current-player hand action guard。
  - 2026-05-13：已修 validator button interactions、turn guard、current player hand action 限制。
- [done] faction action centered modal 已上線。
  - 2026-05-18：提示類 faction action 已改為置中 modal；後續若需要，可再清理多餘按鈕／面板殘留狀態。

### 地圖／資料／文件整理
- [done] 以 map ruler 取代 board_towns 作為 authoritative region source。
  - 2026-05-13：已移除剩餘 board_towns 依賴與未使用資料。
- [done] 將 validation records 與 card UI 紀錄整理到 `docs/records` 下。
  - 2026-05-13 ~ 2026-05-14：已完成 docs topics 路由、snapshot 與剩餘 map/UI assets 整理。
- [done] 更新 root-level records 整理後的文件描述。
  - 2026-05-16：已將 root 目錄 120 個紀錄／截圖檔歸檔至 `docs/records/*` 並更新文件。

### 陣營／基礎能力 UI
- [done] 修正自由派根據地確認／落盤流程，讓真實 UI 可正常開局。
  - 2026-05-15：前端確認陣營時會正確送出單一根據地，並在 lobby state 立即刷新。
- [done] 在正式 UI 驗證立場試探 modal 內結果顯示並截圖。
  - 2026-05-15：已用正式 UI 進入行動階段，按下立場試探並取得截圖。
- [done] 修正立場試探相關 UI 文案與能力歸屬，移除錯誤的福建／閩綁定。
  - 2026-05-15：立場試探已改綁自由派，文案由「福建」修正為「自由派」。
- [done] 驗證修正後的立場試探 UI／modal／log 顯示並截圖。
  - 2026-05-15：已確認行動畫面顯示「自由派可在行動階段發動一次立場試探」。
- [done] 整理本輪立場試探與自由派根據地修正後提交 commit。
  - 2026-05-15：已提交 `bd8700a` `[verified] fix liberals stance-probe lobby and ui flow`。

### 奧援／支援卡 UI 與效果驗證
- [done] 東洋奧援完成。
  - 2026-05-15：依使用者確認，東洋奧援已完成，不再列入待辦。
- [done] 北國奧援：補玩家指定瓦解目標 UI／驗證與收尾整理。
  - 2026-05-17：已修正 I級為先選己方犧牲組織、再選該組織 1 格內敵方組織；正式 UI 證據改為日內瓦→慕尼黑場景，並移除錯誤舊截圖後重新補圖。
- [done] 臺灣奧援：補完整 UI／驗證與收尾整理。
  - 2026-05-16：已完成 I級誤判修正與正式 UI 驗證；I級現在正確改為獲得 1 點宣傳。
- [done] 臺灣奧援 I級：修正 tier 判定與效果邏輯。
  - 2026-05-16：修正 `_support_card_tier()`，I級不再誤判成 II/III 級。
- [done] 臺灣奧援 I級：正式 UI 前後對照驗證。
  - 2026-05-16：已確認打出後為手牌 0／資金 0／宣傳 1，且未再跳出瓦解目標選擇視窗。
- [done] 天方奧援：補指定對手 / 範圍確認 UI／驗證與收尾整理。
  - 2026-05-17：已完成 III級正式 UI 前 / 中 / 後對照截圖；可直接看到出牌前 `red` 手牌 2、選目標 modal 僅有 `red`、結算後 `red` 手牌 0 與 action log「player resolved 天方奧援 targeting red and discarded 2 random card(s)」。
- [done] 紅軍奧援：修正卡牌說明文字與 action 手牌數驗證。
  - 2026-05-16：已修正 `/card-presentation` / live UI 的紅軍奧援卡牌說明，並修正 action 打出後最終手牌為 5；提交 `c0d325f`、`db93978`。

## note（不是 active todo）
- [note] 已實作但缺 UI 證據。
  - Action：合作談判、乘勝追擊、擴大戰果、網羅人才、地下黨、走漏風聲、武裝者、武裝小隊、武裝集團、派遣間諜、內應間諜、行動預告、行動募資。
  - Support：英美奧援、歐洲奧援、南洋奧援、印度奧援。
- [note] 後續可清理 UI 殘留狀態。
  - faction action centered modal 已上線，但後續仍可再清理多餘按鈕／面板殘留狀態。
