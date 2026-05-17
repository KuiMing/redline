# Redline TODO

最後更新：2026-05-17

## 工作規則
- 每次開始新工作前，先把對應項目加入此檔。
- 同一時間只保留一個 `in_progress`。
- 完成後立刻改成 `done`，並在項目下補一行簡短結果紀錄。
- 每次收尾時，先看這份檔案決定下一步要做什麼。
- 這份檔案不只記「現在要做什麼」，也要保留最近完成項目的脈絡，避免重複盤點。
- `todo` 只放真正下一步要做的事；純盤點、現況分類、已完成但缺證據，放在 `note`。

## 狀態定義
- `todo`：尚未開始，且是現在應該排進工作序列的項目
- `in_progress`：進行中
- `done`：已完成
- `blocked`：卡住，等待資訊或前置條件
- `note`：不是立即待做，但要保留的狀態盤點／後續提醒

## 近期工作主線（最近三天）

### 已完成：行動卡回歸測試補強
- [done] 補齊多張 action card regression coverage（合作談判、思想建設、思想家、宣傳家、資本家等）。
  - 2026-05-12：完成多張行動卡測試補強與既有 regressions 擴充。
- [done] 修正情報網 choose-one branching、商業網絡借用行為、共識鍛造棄牌後 bonus 流程。
  - 2026-05-12：完成相關行動卡／指令卡邏輯修補。

### 已完成：pending-choice / modal 流程修正
- [done] 修正 multi-card choice modal flow。
  - 2026-05-14：完成多選 modal 流程修正。
- [done] 修正 pending card choice 時 action completion 過早完成問題。
  - 2026-05-14：已改為 pending choice 未解前不提早完成效果鏈。
- [done] 補 pending-choice consensus flow regression coverage。
  - 2026-05-14：已補對應回歸測試。
- [done] 補齊系統層缺口（option_choice / multi_card_choice / reveal / peek / 選 town / target 互動 UI）。
  - 2026-05-15：依使用者最新確認，這批系統層缺口已補上，不再列為待辦。

### 已完成：card UI / 當前玩家防護
- [done] 修正 card UI validator 與 current-player hand action guard。
  - 2026-05-13：已修 validator button interactions、turn guard、current player hand action 限制。

### 已完成：地圖／board_towns 整理
- [done] 以 map ruler 取代 board_towns 作為 authoritative region source。
  - 2026-05-13：已移除剩餘 board_towns 依賴與未使用資料。

### 已完成：驗證紀錄／docs 整理
- [done] 將 validation records 與 card UI 紀錄整理到 docs/records 下。
  - 2026-05-13 ~ 2026-05-14：已完成 docs topics 路由、snapshot 與剩餘 map/UI assets 整理。
- [done] 更新 root-level records 整理後的文件描述。
  - 2026-05-16：已將 root 目錄 120 個紀錄／截圖檔歸檔至 `docs/records/*` 並更新文件。

### 已完成：自由派／立場試探 UI 流程
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

### 已完成：東洋奧援
- [done] 東洋奧援完成。
  - 2026-05-15：依使用者確認，東洋奧援已完成，不再列入待辦。

### 已完成：批判／批鬥 UI 驗證收尾
- [done] 批判：完成完整 UI 驗證與收尾整理。
  - 2026-05-15：依目前驗證與整理結果，批判已完成，不再列入 active todo。
- [done] 批鬥：完成完整 UI 驗證與收尾整理。
  - 2026-05-15：依目前驗證與整理結果，批鬥已完成，不再列入 active todo。

### 已完成：臺灣奧援 I級修正
- [done] 修正臺灣奧援 I級 tier 判定與效果邏輯。
  - 2026-05-16：修正 `_support_card_tier()`，I級不再誤判成 II/III 級。
- [done] 正式 UI 驗證臺灣奧援 I級修正後前後對照並截圖。
  - 2026-05-16：已確認打出後為手牌 0／資金 0／宣傳 1，且未再跳出瓦解目標選擇視窗。

## 真正該放進待辦的項目

### todo
- [todo] 情報網：補完整 UI 驗證與收尾整理。
- [done] 企業人脈：補完整 UI 驗證與收尾整理。
  - 2026-05-15：已完成購買區借牌選擇 UI、交通經驗乙續行 +4 驗證、正式 UI 截圖與 follow-up commit。
- [done] 企畫遊說：補完整 UI 驗證與收尾整理。
  - 2026-05-15：已完成高費用（思想家→資金4）與低費用（領導→資金2）兩種正式 UI 驗證。
- [done] 模仿戰術：補完整 UI 驗證與收尾整理。
  - 2026-05-15：已補目標玩家選擇 modal、完成正式手牌 UI 截圖，並提交 `6e5c48b` `Add imitation tactics target selection modal`。
- [done] 誘導虛耗：補完整 UI 驗證與收尾整理。
  - 2026-05-16：已完成正式 UI 逐步截圖、目標玩家自選棄牌流程驗證，並將提示文案修正為「你可以移除誘導虛耗這張卡牌」。
- [done] 北國奧援：補玩家指定瓦解目標 UI／驗證與收尾整理。
  - 2026-05-17：已修正 I級為先選己方犧牲組織、再選該組織 1 格內敵方組織；正式 UI 證據改為日內瓦→慕尼黑場景，並移除錯誤舊截圖後重新補圖。
- [done] 臺灣奧援：補完整 UI／驗證與收尾整理。
  - 2026-05-16：已完成 I級誤判修正與正式 UI 驗證；I級現在正確改為獲得 1 點宣傳。
- [todo] 天方奧援：補指定對手 / 範圍確認 UI／驗證與收尾整理。
- [done] 紅軍奧援：修正卡牌說明文字與 action 手牌數驗證。
  - 2026-05-16：已修正 `/card-presentation` / live UI 的紅軍奧援卡牌說明，並修正 action 打出後最終手牌為 5；提交 `c0d325f`、`db93978`。

## 狀態盤點／提醒（不要直接當成 todo）

### note
- [note] 北國奧援：已完成玩家指定瓦解目標 UI、I級犧牲流程與正式 UI 證據。
  - 2026-05-17：I級現在先選己方可犧牲組織，再選該城 1 格內敵方組織；正式 UI 證據使用日內瓦→慕尼黑場景，且已排除立場試探 modal 干擾。
- [note] 臺灣奧援：已完成 I級修正與正式 UI 驗證。
  - 依據：`gain_resource` 已正確套用於 I級，正式 UI 也已驗證不再誤開瓦解目標選擇。
- [note] 天方奧援：部分實作。
  - 依據：`force_discard_near` 已做。
  - 問題：目前自動找第一個有手牌的對手；缺指定對手 / 範圍確認 UI。
- [note] 紅軍奧援：已完成說明文字修正、action 手牌數驗證與 live UI 驗證。
  - 2026-05-16：已修正 `/card-presentation`／live UI 卡牌說明，確認 action 打出後最終手牌為 5，並完成正式 UI 驗證。
- [note] 已實作，但缺 UI 證據。
  - Action：合作談判、乘勝追擊、擴大戰果、網羅人才、地下黨、走漏風聲、武裝者、武裝小隊、武裝集團、派遣間諜、內應間諜、行動預告、行動募資。
  - Support：英美奧援、歐洲奧援、南洋奧援、印度奧援。
- [note] 部分實作（MVP / 自動化）。
  - Action：情報網、企業人脈、企畫遊說、模仿戰術、批判、批鬥。
  - Support：北國奧援、天方奧援。
- [note] faction action centered modal 已上線，但後續仍可再清理多餘按鈕／面板殘留狀態。
