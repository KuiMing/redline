# Redline TODO

最後更新：2026-05-18

## 工作規則
- 每次開始新工作前，先把對應項目加入此檔。
- 同一時間只保留一個 `in_progress`。
- 完成後立刻改成 `done`，並在項目下補一行簡短結果紀錄。
- `todo` 只放真正下一步要做的事；已完成紀錄集中放在下方「已完成」。
- `note` 不是立即待做，只保留盤點或後續提醒。

## 下一 session 接手提示
- 先跑 `git status --short` 與 `git log --oneline -5`，確認最新 TODO commit 與 `c690f5b` 都在目前分支。
- 除非使用者明確要求，不要重做情報網 target choice map highlight；下一步依使用者新指示處理。
- 若回到奧援卡，先確認指定卡名與級別；不要用北國奧援 I級規則推測 II級。

## 目前 active todo

### P0：已確認 UI 缺口
- 目前無 P0 active todo。

### P1：已實作但缺正式 UI 證據
- [todo] 補 Action 卡正式 UI 證據與回歸紀錄。
  - 範圍：合作談判、網羅人才、地下黨、走漏風聲、派遣間諜、內應間諜。
  - 完成條件：每張卡至少有可重跑驗證腳本或正式 UI 截圖，能證明前／中／後狀態與 action log。

### P2：repo hygiene / validator hygiene
- [todo] 第二輪 root validation artifacts 整理。
  - 盤點依據：repo root 目前仍有 63 個 validation/report/screenshot 類檔案，例如 `*_VALIDATION.md`、`*_VALIDATION.json`、`*_validation.png`、`multiplayer_lobby_flow_*.png`。
  - 完成條件：依 README 規則搬到 `docs/records/<topic>/`，修正 stale references，確認 root 只保留 `README.md`、`TODO.md`、`rules.md`、`North.md` 等真正根層文件。
- [todo] 修正仍輸出到 repo root 的 validator scripts。
  - 盤點依據：目前約 33 個 `scripts/validate_*.py` 仍把 `*_VALIDATION.*` 或截圖寫到 root，例如 base selection、card effect audit、faction ability、lobby、movement、shared action、support runtime 等驗證腳本。
  - 完成條件：所有相關 validator 直接輸出到對應 `docs/records/<topic>/`；重跑被改動 validator，確認新路徑產物存在且舊 root 產物不再回生。
- [todo] 補 validator failure exit-code 檢查。
  - 盤點依據：整理 validator 時需避免「報告顯示 failed 但 process exit 0」的靜默回歸。
  - 完成條件：高使用率 validator 在 failed/exception 時會非 0 結束；文件或測試紀錄可證明行為。

### P3：後續 UI polish
- [todo] 清理 faction action centered modal 上線後的殘留 UI 狀態。
  - 盤點依據：faction action centered modal 已上線，但仍可能有多餘按鈕／面板殘留狀態需要收斂。
  - 完成條件：正式 UI 操作中不再殘留過期提示、按鈕或面板；補最小截圖／console 驗證。

## 已完成

### 地圖／target choice UI
- [done] 情報網：把 `target_choice` 瓦解目標同步接上地圖 highlight。
  - 2026-05-18：已修正 `static/leaflet_game_map_logic.js`，讓戰略地圖 iframe 接收 `redline-choice-highlight` postMessage，並在情報網 `intel_network_dissolve_target` 狀態同步高亮可瓦解組織。
  - 正式 UI 已驗證：情報網選「瓦解己方組織1格內的1個對手組織」後，modal 列出 `enemyA｜天津`、`enemyA｜香港城`、`enemyA｜廣州`；`choiceModalMapHint` 顯示地圖同步提示；iframe 內 `supportChoiceHighlightLayer.getLayers().length = 6`，payload towns = 天津／香港城／廣州，地圖 zoom = 8 並顯示橘色高亮。
  - 測試：`python3 -m compileall -q server scripts static` 通過；`python3 -m pytest -q scripts/tests/test_intel_network_cancel_reaction_proof.py` 通過（2 passed）。
  - 提交：`c690f5b fix: highlight intel network dissolve targets on map`。
  - 證據截圖：`/Users/benmini/.hermes/cache/screenshots/browser_screenshot_c506238701ce4e3ca9e5ecf730d1d028.png`。

### 行動卡／指令卡邏輯與回歸測試
- [done] 擴大戰果：補正式 UI 截圖證據。
  - 2026-05-18：以 `POST /test/setup-expand-results-proof` 建立真實 UI 場景，截圖證明起始手牌有 `擴大戰果`、打出後 `card_choice` modal 列出己方棄牌堆 `宣傳家` / `合作談判` / `走漏風聲`，其中總費用 4 的 `合作談判` 仍可選，選取後手牌變為 `合作談判`。
  - 產物：`docs/records/action-cards/ACTION_CARD_EXPAND_RESULTS_UI_SCREENSHOTS_2026_05_18.md`、`docs/records/action-cards/ACTION_CARD_EXPAND_RESULTS_UI_2026_05_18_*.png`。
  - 戰況紀錄：棄牌堆變為 `宣傳家` / `走漏風聲` / `擴大戰果`，log 寫入 `viewer gained 合作談判 from discard via 擴大戰果`。
- [done] 乘勝追擊：補可重跑 runtime validator、回歸測試與正式 UI 截圖證據。
  - 2026-05-18：已驗證 `gain_from_discard` pending choice 只列出己方棄牌堆總費用 3 點以下卡牌，總費用以資金 + 宣傳計算；測試同時證明總費用 4 的 `合作談判` 不會被列為候選，解析後選中的 `走漏風聲` 進入手牌，未選／不合格牌留在棄牌堆，並寫入 action log。
  - 2026-05-18 UI 證據：以 `POST /test/setup-press-advantage-proof` 建立真實 UI 場景，截圖證明起始手牌有 `乘勝追擊`、打出後 modal 只列出 `宣傳家` / `走漏風聲`、選 `宣傳家` 後手牌變為 `宣傳家`，戰況紀錄顯示 `合作談判` / `走漏風聲` / `乘勝追擊` 留在棄牌堆並寫入 `viewer gained 宣傳家 from discard via 乘勝追擊`。
  - 產物：`scripts/validate_action_card_press_advantage_runtime.py`、`docs/records/action-cards/ACTION_CARD_PRESS_ADVANTAGE_RUNTIME_VALIDATION.{json,md}`、`docs/records/action-cards/ACTION_CARD_PRESS_ADVANTAGE_UI_SCREENSHOTS_2026_05_18.md`、`docs/records/action-cards/ACTION_CARD_PRESS_ADVANTAGE_UI_2026_05_18_*.png`。
  - 測試：`python3 scripts/validate_action_card_press_advantage_runtime.py` 通過（1 passed）；`python3 -m pytest -q scripts/tests/test_action_card_regressions.py -k 'press_advantage'` 通過（2 passed）；`python3 -m compileall -q server scripts static` 通過。
- [done] 行動預告、行動募資：補回合結束前提示與補牌置頂驗證。
  - 2026-05-18：END 階段真正結束回合／補滿手牌前，若手上有 `行動預告` / `行動募資` 且本回合購得牌仍在棄牌堆，會先跳 `end_turn_topdeck_action` 選項提示；玩家可選擇不使用或使用其中一張。
  - 使用後會先把本回合購得牌置於牌庫頂，再執行棄手牌／補到 5 張，因此剛購得的牌會在補牌時進手牌；選擇不使用則購得牌維持在棄牌堆。
  - 產物：`scripts/validate_action_card_end_turn_topdeck_runtime.py`、`docs/records/action-cards/ACTION_CARD_END_TURN_TOPDECK_RUNTIME_VALIDATION.{json,md}`。
  - UI 截圖：`docs/records/action-cards/ACTION_CARD_END_TURN_TOPDECK_UI_SCREENSHOTS_2026_05_18.md`；包含 `ACTION_ANNOUNCEMENT_END_TURN_*.png` 與 `ACTION_FUNDRAISING_END_TURN_*.png`，逐步證明起始 END 階段、提示 modal、補牌後手牌、戰況紀錄。
  - 測試：`python3 scripts/validate_action_card_end_turn_topdeck_runtime.py` 通過（3 passed）；`python3 -m pytest -q scripts/tests/test_action_card_regressions.py -k 'action_announcement or action_fundraising or end_turn'` 通過（3 passed）；`python3 -m compileall -q server scripts static` 通過。
- [done] 武裝者、武裝小隊、武裝集團：補可重跑 runtime validator 與目標玩家自選棄牌流程。
  - 2026-05-18：已修正 `force_discard` 對武裝系列改走 `armed_target_discard` pending choice，不再由系統自動從手牌尾端棄牌；目標玩家可自選棄牌，武裝集團在成功棄牌後才讓出牌者抽 1 張。
  - 產物：`scripts/validate_action_card_armed_series_runtime.py`、`docs/records/action-cards/ACTION_CARD_ARMED_SERIES_RUNTIME_VALIDATION.{json,md}`。
  - 測試：`python3 scripts/validate_action_card_armed_series_runtime.py` 通過（3 passed）；`python3 -m pytest -q scripts/tests/test_action_card_regressions.py -k 'armed'` 通過（5 passed）；`python3 -m compileall -q server scripts static` 通過。
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
- [done] 英美奧援、歐洲奧援、南洋奧援、印度奧援：補可重跑 runtime validator。
  - 2026-05-18：已擴充 `scripts/validate_support_card_effects_runtime.py`，針對 4 張卡各跑 I／II／III 級共 12 個情境，驗證 tier 判定、實際資源／抽牌／棄牌堆效果與 action log。
  - 產物：`docs/records/support-cards/SUPPORT_CARD_EFFECTS_RUNTIME_VALIDATION.{json,md}`。
  - 測試：`python3 scripts/validate_support_card_effects_runtime.py` 通過（12 passed）。
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
- [note] 2026-05-18 通盤檢查補充。
  - 已搜尋 repo 內 `TODO` / `FIXME` / `待辦` / `後續` / `未實作` / `not implemented` 等標記，未找到額外明確程式碼註記。
  - 已跑 `python3 -m compileall -q server scripts`，目前 server/scripts 語法檢查通過。
  - `search_files` 在此 repo 對檔名列舉回傳 0，但用 Python 直接列舉確認 root 與 scripts 狀態；後續盤點不要只依賴單一檔名搜尋工具輸出。
