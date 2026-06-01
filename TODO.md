# Redline TODO

最後更新：2026-06-01

## 工作規則
- 開始新工作前先做 intake：讀 `TODO.md`、跑 `git status --short`、跑 `git log --oneline -5`。
- 同一時間只保留一個 `in_progress`；完成後移到「已完成摘要」或在項目下補一行結果。
- `todo` 只放真正下一步要做的事；歷史證據集中放 `docs/records/<topic>/`，不要堆在 repo root。
- UI 變更必須用正式 browser UI 截圖 proof；不要用假的 DOM/CSS proof。
- 事件卡與常設牌互動時，遵守 static supply：`宣傳家`、`思想家`、`資助者`、`資本家`、`分神`、`內鬥` 等固定購買牌不可憑空新增。

## 下一 session 接手提示
- 目前事件卡是 **MVP 完成、可 playtest**；不是所有事件／時代關卡原文規則都完整完成。
- 不要重做情報網 target choice map highlight；若事件卡需要目標選擇，只重用既有 pending choice / map highlight 架構。
- 新增 validator / proof records 一律放 `docs/records/event-cards/`。
- 若回到奧援卡，先確認指定卡名與級別；不要用北國奧援 I級規則推測 II級。

## 目前 active todo

### P0：事件卡完整化規劃（MVP 後下一階段）
- [done] 事件／時代卡資料盤點與 canonical scope 決定。
  - 2026-05-23：已新增 `scripts/validate_event_card_canonical_scope.py`，產出 `docs/records/event-cards/EVENT_CARD_CANONICAL_SCOPE_AUDIT_2026_05_23.{json,md}`。
  - 盤點結論（已於 2026-05-27 收斂）：raw 檔共有 13 張事件列、8 張時代關卡列；事件 runtime deck 只包含 raw 13 張事件列（含副本共 25 張），8 張時代關卡以 `data/era_structured.v1.1.json` era-stage mechanics 實作，不進事件牌堆。
  - canonical scope 決策：事件卡 MVP scope 為「13 張 raw event rows 進 runtime event deck」；8 張 raw era-stage rows 只作為 era-stage mechanics，不作為 event-deck cards。
  - 2026-05-27：`[反賊]公知世代的終結`、`[臺灣]綏靖派反對介入對岸` 的 event-like MVP adaptation 已移除，避免同一張時代關卡同時出現在事件牌堆與時代關卡系統。

- [done] 修正 structured event data 與 raw card text 不一致的事件。
  - 2026-05-30 live intake：目前無已知 raw 13 張事件卡 raw/structured mismatch；事件 runtime deck 維持 raw 13 event rows（含副本 25 張），8 張 bracketed raw 時代關卡只由 `data/era_structured.v1.1.json` 作為 era-stage mechanics 表示，不進事件牌堆。
  - 既有 validator / records：`scripts/validate_event_card_canonical_scope.py`、`scripts/validate_event_cards_runtime.py`、`docs/records/event-cards/EVENT_CARD_CANONICAL_SCOPE_AUDIT_2026_05_27.{md,json}`、`docs/records/event-cards/EVENT_CARDS_RUNTIME_VALIDATION.{md,json}`。
  - raw 8 張時代關卡 runtime 目前由 `scripts/validate_era_effects_runtime.py` 覆蓋 15 項 checks；records：`docs/records/event-cards/ERA_EFFECTS_RUNTIME_VALIDATION.{md,json}`。

- [done] 補事件卡玩家選擇 UI / map proof。
  - 2026-05-30 live intake：目前互動型事件／時代效果已各有正式 browser UI proof 或共用 UI proof：事件 pending card choice、target choice map highlight、Strategic Map sidebar build、區域免費建組織、紅軍失敗瓦解、香港棄牌、維吾爾追加瓦解、滿洲 reorder、藏國 multi-discard-to-build。
  - 原則仍維持：若 playtest 新增互動效果，只重用既有 pending choice modal / target choice map highlight / Strategic Map sidebar 架構；不要重做情報網 highlight。
  - 既有 proof records 集中於 `docs/records/event-cards/`；新增 proof 也放同資料夾。

- [done] 事件卡完整化總驗證。
  - 2026-05-27：事件牌堆 canonical scope、event/era validators、compileall、diff check、root record-like count 已完成；事件牌堆不再包含 raw 時代關卡 adaptation。
  - 必跑：事件卡 runtime validator、`python3 -m compileall -q server scripts static`、`git diff --check`、root record-like count 檢查。
  - 若有 UI 變更：補正式 browser UI screenshot proof。
  - 若要 LAN playtest：重啟 server 綁 `0.0.0.0:8000` 並確認 `TCP *:8000 (LISTEN)`。

### P1：LAN / end-to-end playtest feedback
- [todo] 下一步建議：開 LAN 桌測／端到端 playtest，記錄實際遊戲中出現的 UI polish 或規則落差，再回寫成具體 P0/P1 項目。
  - 目前事件／時代 scope 已可 playtest；不要再以 speculative implementation 延伸 P0，除非 playtest 或規則文本指出具體 bug。
  - 事件面板 polish 待 playtest 後再決定是否需要展開/收合、詳細文字、或事件歷史紀錄。
  - 目前面板位置：右上紅框區，`.event-card-panel` 為 `width: 300px; height: 200px; max-height: 200px; top: 0; right: 24px`。
  - 現有 proof：`docs/records/event-cards/EVENT_CARD_LAYOUT_REDFRAME_300X200_PROOF_2026_05_23.md` 與同名截圖。

### P2：repo hygiene / validator hygiene
- [todo] 維持 root record-like count = 0。
  - 新增 validation reports、proof markdown、screenshots 時，直接放到 `docs/records/<topic>/`。
  - 若新增 validator，確認輸出路徑不是 repo root，且失敗時 exit non-zero。

## 已完成摘要

### 事件卡 MVP
- [done] 事件卡 runtime / UI MVP。
  - 2026-05-23：已補 `Game` event deck / current event / progress / modifier 狀態、EVENT 階段抽牌展示、任務條件追蹤、成功/失敗結算與 UI 事件卡面板。
  - 支援 trigger MVP：`play_card_with_money`、`play_card_with_propaganda`、`build_organization`、`move_organization`、`use_faction_ability`、`draw`。
  - 支援 effect MVP：`draw`、`gain_card`（遵守 static supply）、`discard_self`、`discard_random`、`red_dissolve`、`add_internal_conflict`、`move`、`reduce_cost`、`restrict_build`、`ignore_distance`、`build_organization`、`none`。
  - 驗證：`python3 scripts/validate_event_cards_runtime.py` 通過（10 passed）。
  - 證據：`docs/records/event-cards/EVENT_CARDS_RUNTIME_VALIDATION.{json,md}`、`EVENT_CARD_UI_PROOF_2026_05_23.md`、`EVENT_CARD_HONG_KONG_UI_2026_05_23.png`。

- [done] 事件面板 layout 調整。
  - 2026-05-23：事件面板移到全域舞台右上，不遮住手牌/購買區；最後試看尺寸為 300×200。
  - 證據：`docs/records/event-cards/EVENT_CARD_LAYOUT_REDFRAME_300X200_PROOF_2026_05_23.md`、`EVENT_CARD_LAYOUT_REDFRAME_300X200_UI_2026_05_23.png`。

### 近期 UI / hygiene
- [done] Lobby 加入房間代碼提示與陣營選擇畫面捲動修正。
  - 驗證紀錄：`docs/records/lobby/`；陣營資訊 proof：`docs/records/faction-ui/`。
  - 2026-05-30：建立房間後，房間代碼改為直接顯示在 lobby 畫面最上方 sticky 橫幅，含複製與手動選取 fallback；同時確認紅軍→北京→確認陣營→我已準備流程仍可點。proof：`docs/records/lobby/LOBBY_ROOM_CODE_TOP_BANNER_UI_PROOF_2026_05_30.{md,json}` 與同名 PNG。
  - 2026-05-30：修正「複製」在 LAN/http browser 可能無法寫入剪貼簿的問題：點擊時先走 `document.execCommand('copy')`，再 fallback 到 Clipboard API，最後才選取完整房間代碼並提示手動複製；複製成功提示也不再被 lobby polling 立刻蓋掉。proof：`docs/records/lobby/LOBBY_ROOM_CODE_COPY_UI_PROOF_2026_05_30.{md,json}` 與同名 PNG。
  - 2026-05-30：修正維吾爾／西藏 family 陣營在選擇根據地後資訊缺漏；Lobby `/factions` 現在帶出各根據地對應 variant detail，前端依已選根據地顯示能力、規則與獲勝條件，不再顯示 `（暫無資料）`。validator：`scripts/validate_lobby_family_faction_details.py`；proof：`docs/records/faction-ui/LOBBY_FAMILY_FACTION_DETAILS_UI_PROOF_2026_05_30.{md,json}` 與維吾爾/西藏截圖。
  - 2026-05-31：修正西藏 family 選達蘭薩拉時的能力名稱，從錯誤的 `共合會` 改為 `基金會`；同步更新 integrated/source faction JSON，並讓 `scripts/validate_lobby_family_faction_details.py` 明確檢查達蘭薩拉能力名稱。proof：`docs/records/faction-ui/LOBBY_TIBET_DHARAMSALA_FOUNDATION_UI_2026_05_31.{md,json,png}`。
  - 2026-05-31：修正進入 MAIN / 換手後 EVENT 階段未先抽出事件，導致第一次 advance 只抽事件、沒有進 ACTION 的回合流程問題；新回合現在立即建立 `current_event`，advance 可穩定從 EVENT → ACTION。新增 validator：`scripts/validate_turn_phase_action_gating.py`；records：`docs/records/playtest-flow/TURN_PHASE_ACTION_GATING_VALIDATION.{md,json}`。同步整理 `scripts/validate_full_gameplay_multi.py`，讓 full gameplay validator 解析事件 pending choice 並避免無移動點時硬測移動。
  - 2026-05-31 follow-up：修正正式 lobby `/start` 路徑覆寫陣營/根據地並進入 MAIN 後沒有重新啟動 EVENT 階段，導致遊戲一開始看不到事件卡；現在正式開局會立即建立 `current_event` 並顯示事件面板。validator 已補正式 lobby start 覆蓋；UI proof：`docs/records/playtest-flow/FORMAL_START_EVENT_CARD_VISIBLE_UI_2026_05_31.{md,json,png}`。
  - 2026-05-31 follow-up：修正 2P 正式開局由非紅軍先手時，Ben 結束回合後直接跳第 2 回合的錯誤；現在以實際先手玩家作為 round start，需輪到紅軍操作並結束後才進第 2 回合。validator：`scripts/validate_turn_phase_action_gating.py`，records：`docs/records/playtest-flow/TURN_PHASE_ACTION_GATING_VALIDATION.{md,json}`。
  - 2026-05-31：將 EVENT 階段的階段推進按鈕文字從 `結束事件階段` 改為 `開始購買階段`，讓事件卡顯示後的下一步語意更清楚；正式 browser UI proof：`docs/records/playtest-flow/PHASE_EVENT_START_PURCHASE_LABEL_UI_2026_05_31.{md,json,png}`。
  - 2026-05-31 follow-up：修正事件卡 lifecycle 從每玩家回合抽取/結算改為每輪共用；任務條件達成後先顯示 `success_pending`，等全體玩家 ACTION 結束才結算效果，新事件只在回到 round start 進入下一輪時抽取。validators：`scripts/validate_turn_phase_action_gating.py`、`scripts/validate_event_cards_runtime.py`；records：`docs/records/playtest-flow/TURN_PHASE_ACTION_GATING_VALIDATION.{md,json}`、`docs/records/event-cards/EVENT_CARDS_RUNTIME_VALIDATION.{md,json}`；UI proof：`docs/records/playtest-flow/EVENT_CARD_ROUND_WIDE_SUCCESS_PENDING_UI_2026_05_31.{md,json,png}`。
  - 2026-06-01：修正 `一帶一路 南洋`／指定紅軍 faction 的自動事件不應在 BEN 等非紅軍回合立刻發動；現在會先顯示 `auto_pending`，輪到紅軍事件階段才產生 `event_build_organization` 選點。同時修正地圖橘色事件可選城鎮高亮會攔截點擊、導致左側建組織按鈕無法啟用的問題。validator：`scripts/validate_event_cards_runtime.py`；proof：`docs/records/event-cards/BELT_ROAD_NANYANG_RED_TURN_BUILD_UI_2026_06_01.{md,json,png}`。
- [done] 常設購買區可購買性、常設牌不混入隨機購買區、手牌資源/行動按鈕 listener 修正。
- [done] 紅軍奧援起始牌庫歸屬修正。
  - 2026-05-25：已修正 `紅軍奧援` 不應進隨機奧援購買樣本，而應作為紅軍起始牌庫專屬卡；Lobby 選定紅軍後會重建起始牌庫，確保實際選紅軍玩家擁有 1 張 `紅軍奧援`，非紅軍與購買牌庫不含該卡。驗證紀錄：`docs/records/support-cards/SUPPORT_PURCHASE_DECK_RUNTIME_VALIDATION.{md,json}`。
- [done] 紅軍陣營能力 runtime / UI 說明補齊。
  - 2026-05-25：已實作紅軍能力 `統戰部`、`政工部`、`國安部`、`中紀委` runtime 與前端按鈕；紅軍能力彈窗文字說明區已列出四項效果說明。驗證紀錄與正式 browser UI proof：`docs/records/event-cards/RED_ARMY_FACTION_ABILITIES_RUNTIME_VALIDATION.{md,json}`、`RED_ARMY_FACTION_ABILITIES_HELP_UI_PROOF_2026_05_25.{md,json}`、`RED_ARMY_FACTION_ABILITIES_HELP_UI_2026_05_25.png`。
  - 2026-05-25：已修正 `政工部` 從錯誤的 `內宣` 改為將常設牌 `內鬥` 放到目標玩家牌庫頂，並遵守 static supply（供應歸零時不憑空新增）。補 runtime validator 與正式 browser UI proof：`docs/records/event-cards/RED_ARMY_POLITICAL_WORK_INTERNAL_CONFLICT_UI_PROOF_2026_05_25.{md,json}`、`RED_ARMY_POLITICAL_WORK_INTERNAL_CONFLICT_HELP_UI_2026_05_25.png`、`RED_ARMY_POLITICAL_WORK_INTERNAL_CONFLICT_RESULT_UI_2026_05_25.png`。
  - 2026-05-25：已補紅軍特殊規則 runtime：4 種紅軍能力視同行動卡可被既有取消反應牌取消；同一玩家同回合成功瓦解紅軍根據地 2 次後根據地消失且不可重建；紅軍組織移動不得離開紅軍發展空間。驗證紀錄：`docs/records/event-cards/RED_ARMY_SPECIAL_RULES_RUNTIME_VALIDATION.{md,json}`。
  - 2026-06-01：紅軍能力改為手動按鈕觸發，不再自動彈出；紅軍可在購買階段前（EVENT/ACTION）自行決定何時發動，並補 WebSocket event-phase regression 與正式 browser UI proof。驗證：`scripts/validate_red_army_faction_abilities.py`、`scripts/tests/test_red_army_ability_timing_ws.py`；proof：`docs/records/event-cards/RED_ARMY_ABILITY_MANUAL_BUTTON_UI_2026_06_01.{md,json,png}`。
  - 2026-06-01 follow-up：修正紅軍事件階段仍可點手牌 `紅軍奧援` 的「行動／資源」按鈕、導致 `Not in ACTION phase` alert 的問題；現在手牌按鈕只在 ACTION／購買階段啟用，EVENT 階段會灰暗停用並提示先按「開始購買階段」，紅軍能力按鈕仍可在購買前使用。validator：`scripts/validate_turn_phase_action_gating.py`；proof：`docs/records/playtest-flow/RED_SUPPORT_EVENT_PHASE_HAND_BUTTON_GATING_UI_2026_06_01.{md,json,png}`。
- [done] 第二輪 root validation artifacts / validator output path / failure exit-code 整理。
  - root record-like count 已確認為 0。

### 已有完整紀錄的其他模組
- [done] 情報網 target choice map highlight。
  - 提交：`c690f5b fix: highlight intel network dissolve targets on map`。
- [done] 多張行動卡/指令卡 UI 與 runtime regression：`網羅人才`、`地下黨`、`擴大戰果`、`乘勝追擊`、`行動預告`、`行動募資`、武裝系列、`合作談判`、`走漏風聲`、間諜系列、`企業人脈`、`企畫遊說`、`模仿戰術`、`誘導虛耗`、`批判`、`批鬥`。
- [done] pending-choice / modal / UI 系統層：multi-card choice、card choice completion guard、option/town/target/reaction/modal 基礎流程。
- [done] 奧援/支援卡多數 runtime/UI 驗證：英美、歐洲、南洋、印度、東洋、北國、臺灣、天方、紅軍奧援。

## note（不是 active todo）
- 事件卡目前應以「MVP 可 playtest」理解；若 playtest 先於完整化，也可以直接測目前版本，再把發現寫回 P0/P1。
- `search_files` 在此 repo 曾對檔名列舉回傳 0；盤點檔案時可用 Python `Path.rglob()` 交叉確認。
