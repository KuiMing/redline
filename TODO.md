# Redline TODO

最後更新：2026-05-23

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

### P0：事件卡 MVP 實作規劃（下一個新 session 優先）
- [done] 事件卡 runtime / UI MVP：已補 `Game` event deck / current event / progress / modifier 狀態、EVENT 階段抽牌展示、任務條件追蹤、成功／失敗結算與 UI 事件卡面板。
  - 2026-05-23：完成 MVP。事件牌庫會依 `data/events_structured.v1.1.json` 與 `data/cards/event_and_era_cards.v1.1.json` 張數建立；EVENT 階段第一次 advance 抽牌並停留展示，第二次 advance 進 ACTION；ACTION 結束結算 mission success/failure。已支援 trigger：`play_card_with_money`、`play_card_with_propaganda`、`build_organization`、`move_organization`、`use_faction_ability`；購買費用判定用卡牌購買成本。已接 effect MVP：`draw`、`gain_card`（遵守 static supply）、`discard_self`、`discard_random`、`red_dissolve`、`add_internal_conflict`、`move`、`reduce_cost` / `restrict_build` / `ignore_distance` modifier、`build_organization`、`none`。
  - 產物：`scripts/validate_event_cards_runtime.py`、`docs/records/event-cards/EVENT_CARDS_RUNTIME_VALIDATION.{json,md}`、`docs/records/event-cards/EVENT_CARD_UI_PROOF_2026_05_23.md`、`docs/records/event-cards/EVENT_CARD_HONG_KONG_UI_2026_05_23.png`。
  - 驗證：`python3 scripts/validate_event_cards_runtime.py` 通過（10 passed：idle、mission success/failure、static supply consumption、draw trigger、auto modifier、event deck declared counts、modifier runtime consumption、pending-choice advance guard、deck reshuffle）；正式 browser UI 截圖證明 `香港抗暴之戰` 事件卡面板顯示名稱、任務條件、進度、成功獎勵、失敗懲罰。
  - Scope 原則：先做可 playtest 的 MVP，不一次補所有精緻例外；每一階段都要有 runtime validator，UI 變更要有正式 UI proof。
  - Phase 1｜事件牌庫與狀態：在 `server/game.py` 初始化事件牌庫、棄牌堆、目前事件、事件任務進度；從 `data/events_structured.v1.1.json` 載入 structured events，依 `data/cards/event_and_era_cards.v1.1.json` 的張數建立 deck；`歲月靜好` 可作 idle no-op。
  - Phase 2｜EVENT 階段抽牌與展示：`advance_turn_phase()` 在 EVENT 階段抽 1 張事件卡並寫入 state；前端 `static/app.js` / `static/style.css` 顯示事件卡名稱、類型、任務條件、成功獎勵、失敗懲罰；事件展示後可由當前玩家按「進入行動階段」。
  - Phase 3｜任務條件追蹤：把本回合 action 計數寫進 `turn_log` / event progress，至少支援 structured triggers：`play_card_with_money`、`play_card_with_propaganda`、`build_organization`、`move_organization`、`use_faction_ability`；需確認購買費用有資金／宣傳的判定用卡牌購買成本，不是打出時獲得資源。
  - Phase 4｜成功／失敗結算：在 END 階段或結束事件任務時判定 mission success/failure，實作/串接 effect types：`draw`、`gain_card`、`discard_self`、`discard_random`、`red_dissolve`、`add_internal_conflict`、`move`、`reduce_cost`、`restrict_build`、`ignore_distance`、`none`；涉及常設牌（宣傳家、分神、內鬥）必須扣 static supply，供應為 0 就不新增。
  - Phase 5｜自動事件：`上海合作組織`、`一帶一路 南洋`、`一帶一路 天方` 等 auto event 先以 turn-scoped modifier 實作；作用範圍與距離規則若不明，先寫 TODO / validator characterization，不用猜規則。
  - Phase 6｜紅軍瓦解／玩家選擇 UI：`red_dissolve`、`discard_self`、`move`、`build_organization` 若需要玩家指定目標，沿用現有 pending choice modal / target choice map highlight 架構；但不要重做情報網 target choice map highlight，只重用既有機制。
  - Phase 7｜驗證與證據：新增 `scripts/validate_event_cards_runtime.py` 覆蓋 idle、mission success、mission failure、auto event、deck reshuffle、static supply consumption；新增 UI proof scenario endpoint（例如 `/test/setup-event-card-proof`）與 `docs/records/event-cards/` validation/screenshots；跑 `python3 -m compileall -q server scripts static`、`git diff --check`、root record-like count。
  - 建議首張驗證路線：先用 `歲月靜好` 驗 no-op，再用 `香港抗暴之戰` 驗 `play_card_with_money -> gain_card 宣傳家 x2` 與 failure `discard_self`，再用 `重大災難` 驗 `play_card_with_propaganda -> gain_card 宣傳家 x1`。

### P1：已實作但缺正式 UI 證據
- 目前無 P1 active todo。
  - 2026-05-19 重新確認：`合作談判` 已有可重跑 validator 與回歸測試；`走漏風聲` 已有 rule validator、target UI validator 與截圖紀錄。

### P2：repo hygiene / validator hygiene
- 目前無 P2 active todo。
  - 2026-05-19 已完成第二輪 root validation artifacts / validator output path / failure exit-code 整理；root record-like 檔案數確認為 0。

### P3：後續 UI polish
- 目前無 P3 active todo。
  - 2026-05-23 已調整事件卡 MVP 版面：`目前事件` 區塊改放指揮中心右上角並上移到卡牌區上方，不遮住手牌／購買區卡牌；`結束事件階段` 按鈕在階段操作列水平置中；proof 截圖放在 `docs/records/event-cards/EVENT_CARD_LAYOUT_NO_OVERLAP_UI_2026_05_23.png`。
  - 2026-05-23 已修正常設購買區卡牌可購買性：常設牌現在也有明確「購買」按鈕，供應量大於 0 時可購買，購買後進棄牌堆並扣該常設供應量。
  - 2026-05-23 已修正常設購買區卡牌混入隨機購買區與手牌資源／行動按鈕失效問題：`分神`、`內鬥` 等常設牌不再進 purchase deck，手牌按鈕改用綁定事件 listener。
  - 2026-05-23 已修正 lobby 房間代碼輸入提示，讓非 host 玩家清楚知道可貼上對方分享的代碼後按「進入作戰室」。
  - 2026-05-23 已修正 lobby / 陣營選擇畫面在內容超高時可上下捲動，避免臺灣等陣營資訊／規則／獲勝條件被固定 720px 舞台切掉。
  - 2026-05-19 已清理 faction action centered modal 殘留狀態：猜奇偶按鈕改為動態建立，陣營能力本回合已發動後不再殘留「發動」或猜奇偶按鈕，舊 `#factionActionPanel` 維持隱藏。
  - 2026-05-19 已補 `賭徒耳語` / `民族祭儀` resolve 後的結果顯示：modal 會列出猜奇偶、翻到卡牌、費用奇偶、猜中／沒中與資源獎勵。

## 已完成

- [done] Lobby：補清楚的加入房間代碼輸入提示。
  - 2026-05-23：已將房間代碼欄位標成「建立 / 加入房間代碼」，placeholder 改為「貼上房間代碼，或建立新作戰室」，並新增提示「要加入別人的房間：把對方分享的代碼貼在這格，再按『進入作戰室』。」
  - `joinRoom()` 現在會 trim 代碼，空白時直接在 lobby 顯示「請先把房間代碼貼到…」提示，不會送出空房號 request。
  - 產物：`scripts/validate_lobby_join_room_code_ui.py`、`docs/records/lobby/LOBBY_JOIN_ROOM_CODE_UI_VALIDATION.{json,md}`、`docs/records/lobby/LOBBY_JOIN_ROOM_CODE_UI_2026_05_23.png`。
  - 驗證：`python3 scripts/validate_lobby_join_room_code_ui.py` 通過（5 passed）；browser console/vision 確認欄位標籤、placeholder、helper 與「進入作戰室」按鈕都清楚可見；`python3 -m compileall -q server scripts static` 與 `git diff --check` 通過。

- [done] Lobby / 陣營選擇畫面：內容超高時可上下捲動。
  - 2026-05-23：已修正 `static/style.css`，將 `#lobby` 從 `overflow: hidden` 改為 `overflow-y: auto` 並保留水平裁切，讓陣營資訊、規則與獲勝條件在小螢幕或內容較長時可往下滑完整查看。
  - 產物：`scripts/validate_lobby_scroll_layout.py`、`docs/records/lobby/LOBBY_SCROLL_LAYOUT_VALIDATION.{json,md}`、`docs/records/lobby/LOBBY_FACTION_PICKER_SCROLL_UI_2026_05_23.png`。
  - 驗證：`python3 scripts/validate_lobby_scroll_layout.py` 通過（4 passed）；正式 browser console 驗證 `#lobby` 可捲動（`scrollHeight=952`, `clientHeight=720`, `scrollTop` 可由 0 變 232）；browser vision 確認臺灣（綠線）陣營資訊、規則、獲勝條件與「確認陣營」可見；`python3 -m compileall -q server scripts static` 與 `git diff --check` 通過。

- [done] 賭徒耳語／民族祭儀：補 resolve 後的結果顯示。
  - 2026-05-19：`server/game.py` 現在會為 `賭徒耳語` / `民族祭儀` 回傳 `last_action_result` payload，包含翻到卡牌、總費用、猜奇偶、是否猜中、獎勵與棄牌去向。
  - `static/app.js` 的 centered modal 會在發動後顯示結果文字，例如「賭徒耳語結果：猜奇數，翻到 追隨者（費用 1） 是奇數，猜中，獲得 資金 +3、宣傳 +3」；民族祭儀同樣顯示 +2/+2 或沒猜中仍 +2 宣傳的結果。
  - 產物：`scripts/validate_faction_action_guess_result.py`、`docs/records/faction-ui/FACTION_ACTION_GUESS_RESULT_VALIDATION.{json,md}`、`FACTION_ACTION_GAMBLER_GUESS_RESULT_UI_2026_05_19.png`、`FACTION_ACTION_ETHNIC_RITUAL_RESULT_UI_2026_05_19.png`。
  - 驗證：`python3 scripts/validate_faction_action_guess_result.py` 通過（5 passed）；`python3 scripts/validate_faction_action_centered_modal_cleanup.py` 通過；正式 browser console/vision 驗證兩張卡結果 modal 只剩 `取消`，且顯示猜測、翻牌、費用與獎勵；`python3 -m compileall -q server scripts static` 與 `git diff --check` 通過。

- [done] 清理 faction action centered modal 上線後的殘留 UI 狀態。
  - 2026-05-19：已修正 `static/app.js`，猜奇偶 modal 改為動態建立「猜奇數／猜偶數」按鈕，避免 centered modal 先清空 `#factionActionModalChoices` 後仍呼叫舊 `guessOddBtn` / `guessEvenBtn` 造成按鈕殘留或失效。
  - 已在 `server/game.py` 的 state 補出 `faction_action_used`，UI 於本回合陣營能力已發動後只顯示「本回合已發動陣營能力」與取消按鈕，不再殘留「發動 立場試探／民族祭儀」或猜奇偶按鈕；舊 `#factionActionPanel` 維持隱藏。
  - 產物：`scripts/validate_faction_action_centered_modal_cleanup.py`、`docs/records/faction-ui/FACTION_ACTION_CENTERED_MODAL_CLEANUP_VALIDATION.{json,md}`、`docs/records/faction-ui/FACTION_ACTION_CENTERED_MODAL_CLEANUP_UI_2026_05_19.png`。
  - 驗證：`python3 scripts/validate_faction_action_centered_modal_cleanup.py` 通過（2 passed）；正式 browser console 驗證 `faction_action_used=true`、modal 只剩 `取消`、`#factionActionPanel` display=`none`；`python3 -m compileall -q server scripts static` 通過。

- [done] 第二輪 root validation artifacts / validator output path / failure exit-code 整理。
  - 2026-05-19：已將第二輪根層 `*_VALIDATION.{json,md}` 與相關截圖移入對應 `docs/records/<topic>/`（card-ui、faction-ui、lobby、layout-ui、map-ui、purchase、safehouse、setup-ui、shared-actions、support-cards），並移除舊 `docs/records/misc` / 錯 topic 重複副本。
  - 已修正相關 `scripts/validate_*.py` 直接輸出到 `docs/records/<topic>/`；root record-like 檔案數以 Python 盤點確認為 0。
  - 已補高使用率 validator 的 failure exit-code 檢查，並修正 rerun fixture：`validate_market_mode_and_removed_supply.py` 依 53 張 sampled market deck 檢查、解析 `宣傳家` optional trash 後再確認 supply；`validate_shared_move_phase8.py` fixture 補 move point；`validate_india_research_room.py` / support runtime validator 改為穩定 pending-choice / support fixture。
  - 驗證：23 個 touched runtime/static validators 全部 exit 0；`git diff --check` 通過；`python3 -m compileall -q server scripts static` 通過。

### 地圖／target choice UI
- [done] 情報網：把 `target_choice` 瓦解目標同步接上地圖 highlight。
  - 2026-05-18：已修正 `static/leaflet_game_map_logic.js`，讓戰略地圖 iframe 接收 `redline-choice-highlight` postMessage，並在情報網 `intel_network_dissolve_target` 狀態同步高亮可瓦解組織。
  - 正式 UI 已驗證：情報網選「瓦解己方組織1格內的1個對手組織」後，modal 列出 `enemyA｜天津`、`enemyA｜香港城`、`enemyA｜廣州`；`choiceModalMapHint` 顯示地圖同步提示；iframe 內 `supportChoiceHighlightLayer.getLayers().length = 6`，payload towns = 天津／香港城／廣州，地圖 zoom = 8 並顯示橘色高亮。
  - 測試：`python3 -m compileall -q server scripts static` 通過；`python3 -m pytest -q scripts/tests/test_intel_network_cancel_reaction_proof.py` 通過（2 passed）。
  - 提交：`c690f5b fix: highlight intel network dissolve targets on map`。
  - 證據截圖：`/Users/benmini/.hermes/cache/screenshots/browser_screenshot_c506238701ce4e3ca9e5ecf730d1d028.png`。

### 行動卡／指令卡邏輯與回歸測試
- [done] 網羅人才：補正式 UI 截圖證據。
  - 2026-05-18：以 `POST /test/setup-recruit-talent-proof` 建立真實 UI 場景，截圖證明一般版本起始手牌有 `網羅人才`，打出後 `card_choice` / `recruit_talent` modal 列出己方牌庫候選 `宣傳家` / `合作談判` / `走漏風聲`，選 `合作談判` 後手牌變為 `合作談判`。
  - 2026-05-18：補紅軍特例 regression 與正式 UI 證據；紅軍 viewer（北京）打出 `網羅人才` 時，modal 同時列出牌庫 `宣傳家` / `走漏風聲` 與棄牌堆 `合作談判`，選棄牌堆 `合作談判` 後手牌變為 `合作談判`，棄牌堆只剩 `網羅人才`。
  - 產物：`docs/records/action-cards/ACTION_CARD_RECRUIT_TALENT_UI_SCREENSHOTS_2026_05_18.md`、`docs/records/action-cards/ACTION_CARD_RECRUIT_TALENT_UI_2026_05_18_*.png`、`docs/records/action-cards/ACTION_CARD_RECRUIT_TALENT_RED_ARMY_UI_2026_05_18_*.png`。
  - 戰況紀錄：一般版 log 寫入 `viewer recruited 合作談判 from deck`；紅軍版 modal 明確標示 `合作談判` 來源為 `棄牌堆`，log 寫入 `deck/discard choices include 宣傳家 / 走漏風聲 / 合作談判` 與 `viewer recruited 合作談判 from discard via 網羅人才`。
- [done] 地下黨：補正式 UI 截圖證據。
  - 2026-05-18：以 `POST /test/setup-underground-party` 建立真實 UI 場景，截圖證明起始手牌有 `地下黨`，打出後 `card_choice` modal 揭示購買牌庫頂 3 張 `宣傳家` / `合作談判` / `走漏風聲`，選 `合作談判` 後手牌變為 `合作談判`。
  - 產物：`docs/records/action-cards/ACTION_CARD_UNDERGROUND_PARTY_UI_SCREENSHOTS_2026_05_18.md`、`docs/records/action-cards/ACTION_CARD_UNDERGROUND_PARTY_UI_2026_05_18_*.png`。
  - 戰況紀錄：`宣傳家 returned to static purchase supply`、`走漏風聲 returned to purchase deck discard`、`viewer chose 合作談判 via 地下黨`。
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
- [done] 合作談判、走漏風聲：重新確認既有驗證紀錄，從 P1 active todo 移除。
  - 2026-05-19：`合作談判` 已有 `scripts/validate_negotiation_card.py` 與 `docs/records/shared-actions/NEGOTIATION_CARD_VALIDATION.{json,md}`，並在 `scripts/tests/test_action_card_regressions.py::test_negotiation_draws_actor_and_chosen_other_player_only_and_gains_two_propaganda` 覆蓋 actor + 指定目標各抽 1、actor 獲得 2 宣傳。
  - 2026-05-19：`走漏風聲` 已有 `scripts/validate_leak_card.py`、`scripts/validate_leak_card_target_ui.py`、`docs/records/leak-card/LEAK_CARD_VALIDATION.{json,md}`、`docs/records/leak-card/LEAK_CARD_TARGET_UI_VALIDATION.{json,md}` 與 `docs/records/leak-card/leak_card_target_modal.png`；重新執行 rule / UI validators 皆通過。
- [done] 派遣間諜、內應間諜：補北國奧援式互動瓦解流程與正式 UI 證據。
  - 2026-05-19：`派遣間諜` 改為兩段式 pending choice，先選己方犧牲組織，再只列出該組織 1 格內的敵方組織；正式 UI 證明可先選 `北京` / `上海`，選 `上海` 後只可瓦解 `enemy｜杭州`，完成後 viewer 組織 1、enemy 組織 2。
  - 2026-05-19：`內應間諜` 改為直接 target pending choice，不犧牲己方組織；正式 UI 證明只列出 `enemy｜天津`，完成後 viewer 組織仍 1、enemy 組織 1，log 沒有己方犧牲紀錄。
  - 產物：`docs/records/action-cards/ACTION_CARD_SPY_CARDS_UI_SCREENSHOTS_2026_05_19.md`、`docs/records/action-cards/ACTION_CARD_SPY_CARDS_UI_2026_05_19_*.png`；後續已補 `10_FIELD_AGENT_MAP_HIGHLIGHT` / `11_EMBEDDED_AGENT_MAP_HIGHLIGHT`，證明 target choice 會同步在戰略地圖以北國奧援同款橘色外框標出可瓦解目標。
  - 測試：`python3 -m pytest -q scripts/tests/test_action_card_regressions.py -k 'field_agent or embedded_agent or support'` 通過（16 passed）；`python3 -m compileall -q server scripts static` 通過；`git diff --check` 通過。
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
