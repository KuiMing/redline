# Redline TODO

最後更新：2026-07-04

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
- [done] 修復 P2 過期驗證腳本時挖出的真 bug：事件延後結算撞上整輪繞回，會對「被重置的事件進度」結算。
  - 2026-07-15 發現（修 `validate_event_cards_runtime.py` 過期假設時）：mission 事件的結算被 `_should_defer_event_settlement_until_after_refill()` 延後到 `_end_turn()` 之後（設計原意：讓獎懲作用在補牌後的新手牌）。但若「最後一位非紅軍玩家結束回合」的同一次 advance 也讓**整輪繞回**，`_end_turn()` 會重置 `current_event`／`event_progress` 並抽下一輪新事件；延後的 `_settle_current_event()` 於是讀到**被重置的新進度**（succeeded=False）——結果①本回合已達成的成功獎勵直接消失；②新抽的事件被當「失敗」立刻對玩家套失敗懲罰（一張還沒人動過的事件）。觸發條件：任何「非紅軍玩家是繞回前最後一位」的座位排列（例如 3 人以上紅軍坐中間；常見 2 人局紅軍恰好當緩衝所以測不到）。
  - 2026-07-15 已修正並提交：`advance_turn_phase` 在 `_end_turn()` **之前**先快照該回合的 `current_event`＋`event_progress`（結算目標玩家 id 本就在 `_end_turn` 前 stamp 進 progress）；`_end_turn()` 後偵測是否已繞回（事件物件被換掉），是則暫時把快照換回 `current_event`/`event_progress` 執行 `_settle_current_event()`（結算標記寫在快照上、效果 prompt 顯示正確事件名），結算完換回新回合的事件與 notification（畫面維持顯示當前回合事件，結算結果在戰況 log）。未繞回的路徑行為完全不變。
  - 驗證：`python3 scripts/validate_event_cards_runtime.py` 修復後 35/35（連跑 3 次穩定）——含香港抗暴之戰成功（正確獲得宣傳家、扣 static supply）與失敗（懲罰給正確玩家）兩路徑；server 相關回歸全綠：turn20 victory、end_turn refill、turn_phase gating（13/13）、end_turn topdeck、era effects（15/15）、faction abilities、support gating、support purchase deck。
  - 同 commit 一併修復 `validate_event_cards_runtime.py` 的其餘過期假設（皆為腳本問題、非遊戲 bug）：`settle_round_event` helper 改為 advance 至結算或跳出選擇（並追蹤該回合自己的 progress 物件）；買牌測試補進 END 階段；`民主陣線` 測試改用民運派（能力歸屬檢查）；建立/移動測試改用非敵佔且陣營適用的城鎮（北京敵佔、臺灣城鎮不適用反賊）；「隨機棄牌/移除選擇」測試依「結算作用在補牌後手牌」語意控制牌庫（清空或墊 4 張 filler）；紅軍 auto 事件測試的 EVENT 階段斷言改為現行 ACTION 模型。

- [done] Playtest bug：城鎮曾有紅軍組織、紅軍移走後，其他玩家仍無法在該城鎮建立組織。
  - 2026-07-04 回報情境：紅軍曾在 `新北` 建立組織，之後紅軍組織已移到 `新竹`；輪到 `f`（台灣綠線）時，照規則應可在 `新北` 建立，但 UI/系統阻擋建立。
  - 需檢查：`can_develop_in_town` / map state / sidebar selected town / shared-org gating 是否把歷史佔領狀態當成目前佔領狀態。
  - 回報截圖：`/Users/benmini/.hermes/image_cache/img_ca2f10a480ad.jpg`。
  - 2026-07-04 已修正並提交：`b7de423 block enemy-occupied movement and builds`；驗證：`scripts/validate_enemy_occupancy_rules.py` 5/5 passed。

- [done] Playtest bug：組織遷移不得移入或跨越敵方組織城鎮；目前可移到已有紅軍組織的 `新竹`。
  - 2026-07-04 log：`[Turn 5] f moved 1 organization from 桃園 to 新竹 via rail`；當時紅軍組織在 `新竹`，台灣綠線應不能移動到 `新竹`。
  - 需檢查：`Game.move_organization()` 目前只檢查 rail/road 連線與移動點，缺少「目的地有敵方組織不可進入」；鐵路 3 格 BFS 也需確認中途與目的地都遵守「可跨越己方，不可跨越敵方」。
  - 回報截圖：`/Users/benmini/.hermes/image_cache/img_ca2f10a480ad.jpg`。
  - 2026-07-04 已修正並提交：`b7de423 block enemy-occupied movement and builds`；驗證：`scripts/validate_enemy_occupancy_rules.py` 5/5 passed、`scripts/validate_movement_rules.py` 13/13 passed。

- [done] Playtest bug：第 12 回合打出南洋奧援後無法按「開始購買階段」。
  - 2026-07-04 回報 log：`f resolved 南洋奧援 at tier 3` 後，按開始購買階段被系統阻擋。
  - root cause：奧援卡效果已經立即結算，但若其他玩家手上有取消反應牌，系統仍把奧援卡當成可取消的行動／指令卡建立 reaction pending_choice；玩家看起來已完成動作，卻被殘留 pending_choice 擋住 phase advance。
  - 2026-07-04 已修正：奧援卡（support card）不再觸發取消反應 prompt；新增 `scripts/validate_support_no_reaction_phase_gating.py` 覆蓋「南洋奧援 + 其他玩家持有爆料黑幕」後仍可進入購買階段。

- [done] Playtest UI polish：任何移動選擇／移動後可達城鎮高亮都不應畫大量放射狀直線。
  - 2026-07-04 回報情境：使用 `宣傳家` 後，在 `石家莊` 建立組織；地圖顯示所有可到達城鎮與 `石家莊` 的連線，造成大量放射狀線條。
  - 2026-07-09 補充：這個項目不只適用於 `宣傳家`；只要進入需要移動或顯示可移動城鎮的流程，都應套用同一視覺規則。
  - 期望：只顯示「可以到達的位置」標記/高亮，以及地圖原本就有的鐵路和道路；不要額外畫出從目前城鎮連到所有可達位置的直線。
  - 需檢查：`static/leaflet_game_map_logic.js` 的 movement/build highlight layer 是否把 reachable targets 以 temporary route lines 全部連回 selected town；所有移動來源（卡牌效果、建立組織後移動、一般組織遷移、事件/能力造成的移動）都應保留既有 road/rail layer，移除或限制放射狀可達連線。
  - 回報截圖：`/Users/benmini/.hermes/image_cache/img_4830826f26cd.jpg`。
  - 2026-07-12 已修正並提交：`renderMovementHighlights()` 移除了 road/rail 高亮各自新增的臨時 `L.polyline`（橘色粗線與青色虛線都連回起點城鎮），只保留城鎮 marker 本身的高亮與地圖既有的道路/鐵路網；適用所有移動來源（同一函式）。驗證 `python3 scripts/validate_map_no_radial_lines.py`（PASS：選取城鎮前後 polyline 總數不變、亮色臨時直線數為 0）；proof `docs/records/map-ui/MAP_NO_RADIAL_LINES_20260712_200103.{json,md,png}`。

- [done] Playtest UI polish：奧援卡卡面需提供各等級詳情入口，並把原本「資源」按鈕改成「詳情」。
  - 2026-07-04 回報想法：奧援卡每一等級的細節仍應能從卡牌上看到；若因字數太多不適合全部放在卡面，可在卡牌上做一個「詳情」按鈕。
  - 2026-07-04 補充：奧援卡其實只能作為行動使用，才可能透過行動效果產生資源；不應保留一般卡牌的「資源」按鈕。
  - 期望：卡牌本體維持簡潔，但提供可點擊的詳情入口，讓玩家查看 I / II / III 級完整效果文字與條件。
  - 期望：把奧援卡原本的「資源」按鈕直接改成「詳情」；按下去顯示卡牌詳情，不執行資源使用。
  - 需檢查：`static/app.js` 支援卡/奧援卡 render、手牌 action/resource button gating、`/card-presentation` 或 support card presentation catalog 是否已有完整 `effect_text` 可供 modal/detail panel 顯示；若資料不足需回查 `data/raw/support_cards.csv`。
  - 2026-07-16 調查：`/card-presentation`（`server/main.py` `_load_card_presentation_catalog()`）早就把 support CSV 的 `effect_text` 組成 `"III級：…\nII級：…\nI級：…"` 三行完整文字；`renderCardFace()` 手牌用 `compact=true` 只截前 3 行，而奧援卡效果文字剛好就是 3 行——實測截圖確認**卡面本身已完整顯示 I/II/III 級全文，無截斷**（回報當下的「字數太多看不到」在後續卡面重排時已解決）。真正仍存在的落差只剩「資源」按鈕：手牌任一卡在行動階段目前一律顯示可點的「資源」鈕；伺服器對奧援卡的 resource 模式雖已安全防呆（不給資源、卡片直接棄掉，見 `play_card` 的 `card_type == 'support'` 分支），但按鈕本身存在會誤導玩家以為有作用。
  - 2026-07-16 已修正並提交：手牌渲染時偵測奧援卡（`/奧援/.test(card)`，含特例 `紅軍奧援`），把「資源」按鈕換成「詳情」按鈕（`data-card-mode="detail"`，**永不 disabled**，不受行動階段限制）；`bindHandCardActionButtons` 對 `mode==='detail'` 改綁 `flashCardDetail()`——不呼叫 `sendAction`/`playHandCard`，只把卡片本身（效果文字已在卡面）做一次 0.9 秒的高亮閃爍聚焦，讓「詳情」有明確互動回饋但不消耗任何動作。非奧援卡的資源按鈕行為完全不變。
  - 驗證 `python3 scripts/validate_support_card_detail_button.py`（7/7：一般奧援卡顯示詳情非資源、詳情鈕永不 disabled、點擊不消耗卡牌／不觸發任何動作、點擊觸發閃爍回饋、卡面確實完整列出 III/II/I 三級文字、`紅軍奧援`特例同樣顯示詳情、一般非奧援卡的資源按鈕不受影響）；proof `docs/records/action-cards/SUPPORT_CARD_DETAIL_BUTTON_VALIDATION.{json,md}` + 截圖。既有 `scripts/validate_playtest_targeted_browser.py` 第 3 段斷言原本把「奧援卡有資源按鈕、點了無效果」當作預期行為（正是這次回報的問題），已同步改寫為「奧援卡沒有資源按鈕、詳情鈕不消耗卡牌」；該腳本後段有一個跟本次修正無關的既有卡點（購買宣傳家時 `行動階段結束後才能購買` 一直逾時，`git stash` 比對確認修正前後行為一致），不在本次範圍內。相關回歸（模仿戰術、中紀委可取消、北國奧援兩段瓦解、移動確認、可建數量、棄牌捲動）全綠。
  - **2026-07-16 修正上一則調查的誤判**：使用者指出 `data/raw/support_cards.csv` 不是只有單純 I/II/III 級文字——每種奧援卡實際上有兩列，代表兩種不同的實體印刷變體：III 級門檻地區與三級效果文字都相同，只有 II 級門檻地區（區域主導者優待欄）不同（例如英美奧援兩列的 II 級地區分別是「歐洲、天方」與「東洋、臺灣」），且每列的「卡牌張數」都是 4，代表這種卡實體總共有 8 張，不是 4 張。上一則調查只確認「卡面有列出 I/II/III 三行字」，沒發現 `_load_card_presentation_catalog()` 其實只讀了兩列中的第一列（`seen` 去重邏輯把第二列整個跳過），完全沒有把「哪個地區才觸發哪一級」的資訊放進顯示文字——玩家看到的效果文字其實是不完整的。已一併修正，見下方新條目。

- [done] 奧援卡「實體變體」資料修正：張數補回 8 張、卡牌只認自己印的那組 II 級地區、詳情文字補上地區標示；另加「棄置」按鈕。
  - 2026-07-16 使用者回報：仔細看 `support_cards.csv` 後發現每種奧援卡兩列不是「同卡兩份資料」，而是兩種不同的實體印刷變體，兩種都要各自呈現、各 4 張；同時要求新增「把奧援卡直接送進棄牌堆、不使用」的功能。
  - 資料修正：`data/cards/support_taxonomy.v1.1.json` 每種奧援卡的 `regions[]` 兩個項目各自補上 `copies: "4"`，頂層 `copies` 改為兩者加總（8）；`紅軍奧援`維持 1 張不變。
  - 規則修正（使用者裁決）：手上一張奧援卡只看自己印的那組 II 級地區，不再把同名卡兩種變體的地區併查。`server/game.py` 新增 `Card.variant_index`（`_make_support_card(name, variant_index=0)` 設定），`_initial_purchase_deck()` 改成依 `regions[]` 逐一變體建立對應張數的卡，`_support_card_tier(player, card)` 改吃卡物件、只查該卡自己的 `variant_index` 對應地區（不再取兩組地區的聯集）；`_execute_support_card` 呼叫處同步改傳卡物件。新增 `_support_card_variant_info(card)` 供序列化使用。
  - 顯示修正：`server/main.py` `_load_card_presentation_catalog()` 改讀支援卡 CSV 全部列（不再靠 `seen` 去重只取第一列），把兩種變體個別的 II 級地區與張數都收進 `support_variants`，`effect_text` 補上「區域主導者優待」地區標示（例如「III級（英美主導）」「II級（歐洲/天方其一主導，此變體4張）」）。`state()` 序列化新增 `hand_variants` / `purchase_area_variants`（每張手牌/購買區卡片各自的變體地區資訊），`static/app.js` 的 `renderCardFace()` 用這個資訊只顯示該張牌實際印的那組地區文字，不會把兩種變體混在一起顯示。
  - 新功能：奧援卡手牌新增「棄置」按鈕（第三顆，`詳情／棄置／行動`），沿用 `play_card(mode='resource')` 對奧援卡本來就有的「不給資源、直接棄置」行為，只是重新掛一顆清楚標示用途的按鈕；`static/style.css` 新增 3 欄按鈕排版 class。
  - 回歸修正：`scripts/validate_support_card_effects_runtime.py`（英美奧援 tier2 情境對到第二種變體，補 `variant_by_tier`）、`scripts/validate_east_asia_support_taxonomy_fix.py`（北國/英美配對情境改標 `variant_index: 1`）、`server/main.py` 兩處 `/test/setup-support-card-play`、`/test/setup-support-proof` 的 `_support_card_tier` 呼叫與 monkey-patch 改吃卡物件、`scripts/tests/test_action_card_regressions.py` 一處同款 monkey-patch同步修正。
  - 驗證：`validate_purchase_area_composition.py`（9/9，新增 `support_taxonomy_copies_match_csv_row_totals` 硬性檢查，原本標成「待規則書確認」的 deviation_3 已解除）、`validate_support_card_effects_runtime.py`（12/12）、`validate_east_asia_support_taxonomy_fix.py`（6/6）、`validate_support_card_detail_button.py`（7/7，改為斷言「詳情＋棄置」而非「只有詳情、沒有資源」）、新增 `scripts/validate_support_card_variant_and_discard.py`（6/6：同一張英美奧援卡的兩種變體地區判定互相獨立、卡面只顯示自己印的那組地區、棄置鈕移除手牌且不給任何資源）、`validate_event_cards_runtime.py`（35/35）、`test_action_card_regressions.py`（跟修正前 24 個既有失敗完全一致，非本次造成，屬既有技術債不在本次範圍）。
  - 2026-07-17 後續（截圖檢視發現）：天方奧援 I 級文字較長，加上地區標示後被固定卡高（318px）截斷、跟卡面下方「奧援卡」字樣糊在一起。修法：奧援卡卡面省略沒有資訊量的含義行（「奧援卡」）與徽章列（「資源 依效果而定」「隨機購買區」），騰出的空間讓三級文字完整顯示（實測 `clientHeight == scrollHeight`，零截斷）；非奧援卡不受影響。commit `69a8774`。
  - 2026-07-17 後續（使用者裁決）：卡面完整顯示三級文字後，「詳情」按鈕只剩閃爍聚焦一個功能、已無存在意義，移除。奧援卡最終為「棄置／行動」兩顆按鈕；`flashCardDetail`、`hand-card-detail-flash` 動畫、三欄按鈕排版等相關程式碼一併清除。`validate_support_card_detail_button.py` 改寫為斷言最終狀態（棄置＋行動、無資源無詳情、卡面文字完整且不截斷、棄置直接進棄牌堆零資源、紅軍奧援同款、非奧援卡維持資源／行動，6/6）；`validate_playtest_targeted_browser.py` 第 3 段同步改寫（原本點詳情驗 no-op，改為點棄置驗棄牌）。

- [done] Playtest UI polish：地圖已建立組織的城鎮／根據地應直接顯示所屬陣營。
  - 2026-07-04 回報想法：已建立組織的根據地和城鎮，應該在地名後面直接顯示是哪個陣營，避免只靠側欄或點選狀態辨識。
  - 期望：例如地名標籤可顯示 `臺北 1（f）`、`臺北 1（臺灣）` 或其他清楚的陣營文字；實際格式待 UI 設計時統一。
  - 期望：城鎮圓圈內的填色也可以使用該陣營代表色，讓地圖一眼看出各城鎮／根據地歸屬。
  - 需檢查：`static/leaflet_game_map_logic.js` 的 city marker/label render 是否可取得 organization owner/faction；同步確認 base marker 與一般城鎮 marker 樣式一致。
  - 回報截圖：`/Users/benmini/.hermes/image_cache/img_e4a4c7db0c4d.jpg`。
  - 2026-07-13 調查發現：城鎮圓圈填色其實「早就」寫了陣營配色邏輯（`markerStyleForTown` 的 `controlColor`），但一直是死碼——它直接用 `palette[player.faction]` 查色，`palette` 的 key 是中文陣營大類（`臺灣`／`紅軍`／`香港`…14 類），但 `player.faction` 是伺服器的英文 `faction_id`（如 `taiwan_green`／`red_army`），兩者從未對得上，永遠 fallback 成灰色 `#cbd5e1`。也就是說回報當下地圖確實完全沒有陣營配色可言，不是誤判。
  - 2026-07-13 已修正並提交：新增 `CAMP_COLOR_KEY`（9 個陣營大類 slug → 中文 palette key 的靜態對照，對應 `data/factions/all_faction.integrated.v2.json` 的 `camp` 欄位分類）與 `loadFactionMeta()`（頁面載入時 fetch 一次 `/factions`，攤平 60 個陣營子系〔含維吾爾/西藏的 family variant_details〕成 `factionId → {camp, label}`，`label` 直接用 `variant ? \`${name}（${variant}）\` : name` 組出，與 `app.js` 既有 `factionDisplayName()` 輸出一致但改為此 iframe 獨立的資料來源，因為地圖是獨立 WS 連線的 iframe，跟 app.js 不共用 window scope）；`markerStyleForTown` 的 `controlColor` 改用新的 `factionCampColor()`（修正配色死碼）；新增 `labelTextForTown()` 統一產生「城鎮名 組織數（陣營標籤）」，取代 `renderMap()`／`applyGameStateToMap()` 兩處原本重複的「城鎮名 組織數」邏輯；無組織的城鎮維持純城鎮名＋灰色，行為不變。proof `docs/records/map-ui/MAP_FACTION_DISPLAY_VALIDATION.{json,md}` + `map_faction_display_validation.png`。根據地與一般城鎮共用同一套 marker 渲染邏輯，本來就無需額外處理。
  - 2026-07-13 使用者複測回報三個後續問題並一併修正：
    - ① 綠線顯示藍色：`factionCampColor` 用「陣營大類」查色，台灣大類 palette 是藍色 `#3fb6ff`，導致綠線／藍線共用藍色。新增 `FACTION_COLOR_OVERRIDE`（`taiwan_green→#22c55e` 綠、`taiwan_blue→#3fb6ff` 藍），`factionCampColor` 先查 override 再 fallback camp 色。
    - ② 選取有組織城鎮後實心填色消失：`renderMovementHighlights` 在設好起點樣式後，又用 `markerLayer.eachLayer` 把**所有** marker（含起點）的 `fillOpacity` 壓成 `0.12`，蓋掉實心填色。移除該全域 dimming。
    - ③ 其他未選未建城鎮被一起壓淡（非「維持原狀」）：同上全域 dimming 造成，移除後其他城鎮回到 base 樣式（灰 `#6b7280`、fillOpacity 0.32）不受影響。
    - 選取視覺重新定義：選取的起點城鎮＝有組織則保留陣營實心色＋白框、空城鎮則實心白 `#f8fafc`＋白框；可移動目標城鎮＝實心白 `#f8fafc`＋道路（金 `#ffd166`）／鐵路（青 `#67e8f9`）色外框；其餘城鎮維持原狀。
    - 驗證：更新 `python3 scripts/validate_map_faction_display.py`（6/6，臺北配色斷言改綠 `#22c55e`）＋新增 `python3 scripts/validate_map_selection_highlight.py`（6/6：綠線組織城鎮選取前後皆綠實心、可移動目標實心白、無關城鎮維持 base 樣式未被壓淡、選取空城鎮實心白、重新選取後其他組織城鎮回綠實心）；既有 `validate_map_no_radial_lines.py`／`validate_move_confirmation.py`（8/8）皆無退化；proof `docs/records/map-ui/MAP_SELECTION_HIGHLIGHT_VALIDATION.{json,md}` + `map_selection_highlight_validation.png`。
    - ④ 2026-07-13 再複測回報回歸（本次移除全域 dimming 引入）：連續改選兩個空城鎮（南投→臺中）時兩個都亮、舊選取沒有暗回去。根因是 `selectTownForCurrentMapAction` 重選時先 `renderMap()`（乾淨）再 `applyGameStateToMap()`，而 `applyGameStateToMap` 內部會用**尚未更新的舊 `selectedTown`** 先重跑一次高亮（把南投再點亮），最後才用新城鎮跑第二次；舊版全域 dimming 剛好在第二次呼叫時把南投壓回去而遮住此 bug，移除後就暴露。修法：`renderMovementHighlights` 開頭先用 `currentMarkers.forEach` 把所有 marker 重設回 `markerStyleForTown` base 樣式，使每次呼叫都是完整、與呼叫順序無關的乾淨結果（不論 `applyGameStateToMap` 的舊 `selectedTown` 重跑或新城鎮重跑，最後一次都會把非當前選取的城鎮重置）。驗證新增回歸案例 `reselecting_a_different_empty_town_resets_the_previous_one`（`validate_map_selection_highlight.py` 7/7：南投→臺中後南投回灰 base、臺中實心白）。

- [done] Playtest UI polish：大量棄牌選擇／展示區需要可捲動。
  - 2026-07-04 回報情境：觸發 `貿易戰加劇` 的成功條件時，因棄牌數量太多，畫面只看得到一部分棄牌。
  - 期望：棄牌卡牌區應提供 scrollbar/slider，可滑動查看所有卡牌，避免卡牌超出視窗或被遮住。
  - 需檢查：事件成功條件結算時的 discard selection/display modal 或 panel；可能在 `static/app.js` 的事件結果／棄牌 UI render，或相關 CSS overflow 設定。
  - 2026-07-13 已修正並提交：root cause 是 `貿易戰加劇` 成功效果 `topdeck_from_discard`（count=1）會建立 `card_choice`、把**整個棄牌堆**列進選擇 modal 的 `#choiceModalCards`（`.choice-card-grid`，3 欄卡片格），但該 grid 沒有 `max-height`／`overflow`，卡片一多就往下撐破固定 720px 的 `.modal-overlay`，底部卡片與「關閉」按鈕被切到畫面外。修正（純 CSS）：`.choice-card-grid` 加 `max-height: 460px` + `overflow-y: auto` + `overscroll-behavior: contain` + 右側 padding 讓捲軸不壓到卡片；標題／說明／關閉按鈕都是 grid 的兄弟節點，故 grid 內捲動時它們維持可見。此修正對所有卡牌選擇 modal 通用（不限貿易戰）。為了驗證新增 test-only endpoint `POST /test/setup-discard-topdeck-choice`（`server/main.py`，`discard_count` 預設 18，直接呼叫 `_apply_event_effect` 產生 `event_topdeck_from_discard` 選擇，免跑買 `英美奧援` 觸發任務的長流程）。驗證 `python3 scripts/validate_discard_choice_scroll.py`（6/6：18 張全列出、grid `overflow-y:auto`、`scrollHeight 1684 > clientHeight 460` 確實可捲、關閉按鈕在 `.modal-overlay` 範圍內未被切、可捲到底露出最後幾張）；proof `docs/records/playtest-flow/DISCARD_CHOICE_SCROLL_VALIDATION.{json,md}` + `.png`。

- [done] Playtest UI/flow bug：紅軍能力「紀委」視窗關閉不應視為動作結束。
  - 2026-07-04 回報情境：紅軍選擇紅軍能力中的 `紀委` 時，如果使用者關閉能力視窗，目前流程似乎不能重新選能力／或被視為已結束選擇。
  - 期望：關閉視窗只代表取消／返回，不代表紅軍能力動作已完成；使用者應可重新選擇能力，或再次打開能力選擇視窗。
  - 需檢查：紅軍能力 selection modal 的 close/cancel handler 是否誤呼叫 end action / resolve ability；特別檢查 `紀委` 分支與其他紅軍能力是否一致。
  - 2026-07-13 調查（與使用者討論後確認為**系統性問題**）：`closeChoiceModal()` 是所有卡牌選擇視窗共用的關閉函式，只把視窗隱藏（client-side）、**完全不通知伺服器**；全 repo 沒有任何「取消 pending choice」機制（只有 resolve）。所以關閉任何 blocking 選擇視窗後，伺服器的 `pending_choice` 仍在、擋住所有操作，且 `renderChoiceModal` 會在下一次狀態更新時重新叫出視窗——但自己的選擇不會有別人的動作觸發更新，於是視窗隱藏、pending 卡著、重開能力視窗顯示「請先處理待選擇效果」。`中紀委` 的能力次數要 resolve 才扣（`_activated_faction_action` 建立選擇時未扣），所以卡住時其實沒消耗、但玩家回不去，正是回報的「被視為已結束／不能重新選」。
  - 2026-07-13 已修正並提交（系統性修法，使用者裁決 A/B）：引入**可取消 pending choice** 機制。①`server/game.py` 新增 `CANCELLABLE_CHOICE_KEYS = {red_army_ccdi_discard_draw(中紀委), red_army_propaganda_department_target(政工部), red_army_state_security_target(國安部)}`——這三個是**次數只在 resolve 才消耗**的紅軍主動能力，取消＝乾淨還原。`state()` 依 choice_key 統一標上 `cancellable` 旗標（不必動各建立點）；新增 `cancel_pending_choice(player_id)`：只接受帶旗標且屬該玩家的選擇，清 pending、不扣次數、記 log，其餘一律拒絕。`server/main.py` 新增 WS action `cancel_choice`。②`static/app.js` `renderChoiceModal` 關閉鈕政策：可取消→文字改「取消」、送 `cancel_choice`；地圖類→維持「關閉／改從地圖完成」；**其餘強制型（事件結算、懲罰、卡片已打出的中途步驟等）→直接隱藏關閉鈕**（必須結算，消除「關閉後卡住隱藏」症狀，使用者裁決 B）。「確認棄掉 0 張」（resolve、扣次數）與「取消」（不扣、可重發）語意明確分離。為驗證新增 test endpoint `POST /test/setup-ccdi-choice`。驗證 `python3 scripts/validate_cancellable_choice.py`（7/7：三個能力皆 cancellable、取消不扣次數且可重新發動、確認0張仍扣次數、強制型 state 標記 false 且 cancel 被拒、不能取消他人選擇、可取消集合鎖定三個能力）＋瀏覽器 E2E（中紀委關閉鈕為「取消」按下即清 pending 且可重開能力視窗選擇；強制型 topdeck 無關閉鈕）；proof `docs/records/playtest-flow/CANCELLABLE_CHOICE_VALIDATION.{json,md}` + `CANCELLABLE_CHOICE_{CCDI,MANDATORY_NOCLOSE}_BROWSER.png`。既有 `validate_discard_choice_scroll.py` 因強制型關閉鈕改為隱藏，已把「關閉鈕在框內」檢查改為「整個 modal 在框內」（6/6）；`imitate`/`red_support`/`move_confirmation`/`buildable_count`/`lobby` 等回歸無退化。

- [done] Playtest rule/flow bug：回合結束抽牌應補到 5 張，不應清空手牌後抽 5 張。
  - 2026-07-04 回報規則：每回合最後是抽牌補足到五張牌；如果玩家手上還有手牌，不可以把既有手牌清掉再抽五張。
  - 期望：回合結束／refill hand 時，保留玩家手上的牌；若手牌數少於 5，才從牌庫抽到 5 張；若已經 5 張或更多，則不抽。
  - 需檢查：end turn / discard-refill 流程是否在所有情境都先 discard hand；特別注意事件成功/失敗結算後、紅軍回合、pending choice 完成後的 refill 是否共用同一函式。
  - 2026-07-12 已修正：`_end_turn` 移除 `discard_hand()`，改為保留手牌、`draw_to_five()` 只補足到 5（已有 5 張以上不抽）；所有回合結束路徑共用 `_end_turn` 一處生效。驗證 `python3 scripts/validate_end_turn_hand_refill.py`（4/4）；proof `docs/records/playtest-flow/END_TURN_HAND_REFILL_VALIDATION_20260711.{json,md}`。

- [done] Playtest rule/flow bug：臺灣綠線 `本土社團` 觸發後應在回合結束手牌補滿流程之外額外多抽 1 張，不能最後仍只有 5 張。
  - 2026-07-06 回報情境：第 9 回合玩家 `f` 為台灣綠線，已在 `昆明` 透過 `思想家` 建立組織；log 顯示 `[Turn 9] f triggered 本土社團 and drew 1 card`，但該回合最後仍只讓玩家抽到 5 張卡。
  - 回報 log：`[Turn 9] End of turn for f`; `[Turn 9] f triggered 本土社團 and drew 1 card`; `[Turn 9] f bought 宣傳家`; `[Turn 9] f built organization in 昆明 via 思想家`; `[Turn 9] f played 思想家`; `[Turn 9] f played 擴大戰果`; `[Turn 9] Event drawn: 歲月靜好 (no-op)`。
  - 期望：依 `本土社團`，若本回合曾在牆內建立組織，行動階段結束時應額外抽 1 張；若一般結束流程是補到 5 張，能力觸發後的結果應可達 6 張（或至少不能被後續補牌/棄牌流程覆蓋回 5 張）。
  - 需檢查：`Game.end_turn()` / refill hand 順序、`on_build_draw_inner` / `本土社團` 觸發點、`turn_log['built_towns']`、行動階段結束與購買/END 階段的抽牌時機是否一致；確認 UI 顯示的手牌數與後端實際手牌一致。
  - 2026-07-12 已修正（與上一項同 commit）：root cause 是 `_end_turn` 先觸發回合結束能力（本土社團加抽進手牌）、再 `discard_hand()` 把整手（含剛加抽的牌）棄掉重抽 5 張。修正後順序為「補滿到 5 → 才觸發回合結束能力」，額外抽的牌保留（可達 6 張）。驗證同上（含牆內建立後 6 張、未建立仍 5 張兩案例）。

- [done] Playtest UI/flow polish：移動到可移動城鎮前應跳出確認視窗。
  - 2026-07-05 回報情境：進行組織移動時，玩家點到可移動城鎮後，目前可能直接執行移動，容易誤點。
  - 2026-07-09 補充：當玩家先選定某一組織，接著點選可移動的城鎮時，系統應先出現選項詢問是否要移動到該城鎮。
  - 期望：使用者點到可移動城鎮時，先跳出視窗確認是否要移動到該城鎮；確認後才送出移動，取消則保留在移動選擇狀態。
  - 需檢查：`static/leaflet_game_map_logic.js` / `static/app.js` 的 movement highlight click handler、sidebar move action、WebSocket `move` action 送出點；需避免影響事件/卡牌 pending choice 的選點流程。
  - 2026-07-13 已修正並提交：root cause 是點擊可移動城鎮 marker 的 click handler（`renderMap()` 內）在確認合法目標後直接呼叫 `sendMoveAction()`，完全沒有確認步驟。沿用既有「選取 → 側欄按鈕 → 再按一次才真的執行」模式（與 `#directBuildBtn`/`#dissolveBtn` 一致，不另外發明 modal 系統，避免牽動 `app.js` 的 modal/pending_choice 邏輯）：`static/leaflet_game_map.html` 新增 `#confirmMoveBtn`/`#cancelMoveBtn`/`#confirmMoveHint`；點擊可移動城鎮改為只設定 `pendingMoveTarget`（不送出）並呼叫新的 `refreshMoveConfirmUi()`；按「確認移動」才呼叫既有 `sendMoveAction()`；按「取消」只清空 `pendingMoveTarget`，`selectedTown`／`selectedMoveTargets`／地圖高亮完全不受影響（`resetMoveSelection()` 同步清空 `pendingMoveTarget`，只在使用者主動重新選取城鎮時才觸發）。新增測試 hook `window.__clickMoveTargetForTest`（實際觸發 marker click，取代直接呼叫 `sendMoveAction` 的舊 low-level hook）、`__confirmPendingMoveForTest`、`__cancelPendingMoveForTest`、`__mapDebugStateForTest`（因為地圖 iframe 的 `let` 模組變數不會出現在 `window` 上，需要明確的除錯 hook 才能讓瀏覽器驗證腳本讀到 `pendingMoveTarget`/`selectedTown`）。新增 test-only endpoint `POST /test/setup-move-confirmation-proof`（`server/main.py`，比照既有 `/test/setup-*-proof` 慣例）直接建立可控 `moves_left`／組織位置的對局，避免真實 lobby 流程下新回合 `moves_left=0` 導致測試移動送出必然被伺服器拒絕。驗證 `python3 scripts/validate_move_confirmation.py`（8/8：點擊合法目標不送出 move、確認/取消按鈕正確 enable 並顯示 from/to/mode 提示、取消後選取狀態與可達城鎮清單不變且未送出、確認才送出且 payload 正確、伺服器狀態確實反映移動結果）；proof `docs/records/map-ui/MOVE_CONFIRMATION_VALIDATION.{json,md}` + `move_confirmation_validation.png`。**附帶修正**：過程中意外發現本機開發伺服器因先前一次不當的 `uv run --with uvicorn` 重啟指令，缺少 `websockets`/`wsproto`，導致所有 WebSocket 連線 404（HTTP 路由正常，只有 WS handshake 失敗）；已改用 `uv run --with fastapi --with "uvicorn[standard]" --with websockets` 重新啟動修正，並以既有 lobby／map 驗證腳本回歸確認無殘留影響。

- [done] Playtest rule/flow bug：移動路線需同時檢查翻牆成本與城鎮適用陣營。
  - 2026-07-05 回報情境：玩家剛剛從 `東沙` 移動到 `觀塘`，看起來好像只花 1 次移動。
  - 2026-07-05 補充：當時玩家陣營是 `台灣綠線`，理應不能從 `東沙` 移動到 `觀塘`；移動路線視覺化與功能都應注意該城鎮／路線的適用陣營。
  - 期望：依 `rules.md`「組織遷移」規則，牆外 ↔ 牆內屬於翻牆，需花費 2 次移動，且僅移動 1 格；若路線或目的城鎮不適用目前陣營，前端不應高亮為可移動，後端也應拒絕移動。
  - 需檢查：`Game.move_organization()` / route cost 計算 / map route metadata 是否正確判斷 `東沙` 到 `觀塘` 為翻牆與台灣綠線不可用路線；同時檢查前端可移動城鎮高亮、路線視覺化與剩餘移動點顯示是否使用相同 faction-aware cost/eligibility。
  - 2026-07-12 後端已修正：①翻牆（牆內↔牆外）花費 2 次移動且僅能移動 1 格（多步鐵路 BFS 改為同側限定，不得跨牆）；②目的城鎮必須適用移動者陣營（`can_faction_develop_in_town`）——回報案例臺灣綠線 `東沙`→`觀塘` 現在直接被陣營適用擋下。既有 `validate_movement_rules` 兩個情境改用適用陣營後 13/13 全綠；赤鱲角機場（本就2點）不受影響。驗證 `python3 scripts/validate_wall_crossing_movement.py`（6/6）；proof `docs/records/map-ui/WALL_CROSSING_MOVEMENT_VALIDATION_20260712.{json,md}`。**前端可移動高亮／成本顯示尚未 faction/cost-aware**，歸 P1 UI 批次（移動 UI 重做時一併）。

- [done] Playtest UI polish：顯示目前還有幾個城鎮可以建立組織。
  - 2026-07-05 回報想法：玩家應能直接看到目前還有幾個城鎮可以建立，避免只能靠地圖高亮逐一判斷。
  - 期望：在建立組織相關 UI 中顯示可建立城鎮數量；若受陣營適用城鎮、牆內/牆外、敵方佔領、事件/卡牌限制影響，數字應跟實際可點擊/可建立名單一致。
  - 需檢查：`static/leaflet_game_map_logic.js` 建立高亮資料、`static/app.js` sidebar/action prompt 顯示、後端 build eligibility/state projection 是否能提供一致的可建立城鎮 count。
  - 2026-07-13 已修正並提交：建立組織（`宣傳家`／`思想家`／組織經驗甲／事件／時代 build）觸發時，後端 `_card_build_town_choices()` 已算好一份可建立城鎮清單、透過 pending choice 的 `towns` 送到前端、由地圖以橘色外框高亮（`renderSupportChoiceHighlights`），但畫面一直沒把數量寫出來。修正：在地圖左側 `#interactionHint` 的 build 提示前加上「可建立城鎮：N 個」，N＝`bounds.length`（實際渲染上地圖、可點擊的橘圈數，等同可建清單長度，天然與高亮一致，也自動反映陣營適用／牆內外／敵佔／`restrict_build` 事件等所有後端過濾）；非 build 的目標選擇（瓦解等）則顯示「可選目標：N 個」。不動後端規則，資料源就是既有 `towns` 陣列。驗證 `python3 scripts/validate_buildable_town_count.py`（4/4：build 選擇顯示「可建立城鎮：N 個」且 N＝橘圈數、非 build 顯示「可選目標：N 個」且不含「可建立城鎮」字樣、build hint 不重複卡名前綴）；另以真實出牌端到端確認：`宣傳家`（range 1、組織在臺北）打出後 build 選擇實際可建＝基隆／桃園／臺北 3 城，地圖 hint 顯示「可建立城鎮：3 個」與伺服器清單一致。proof `docs/records/map-ui/BUILDABLE_TOWN_COUNT_VALIDATION.{json,md}` + `.png`。
  - 2026-07-13 附帶修正（同批）：伺服器 build/target prompt 已含 `{source_name}：` 前綴、而地圖 hint 又用 `${sourceName}：${prompt}` 組合，導致 hint 開頭重複顯示卡名（例「宣傳家：宣傳家：…」）。此重複在本計數功能之前就已存在。修正：`renderSupportChoiceHighlights` 顯示前，若 prompt 已以 `${sourceName}：` 開頭則去掉該前綴再組合（event 等 prompt 未帶前綴者維持 `來源：prompt` 不受影響）。驗證涵蓋於上述 `validate_buildable_town_count.py` 第 4 條並以真實出牌確認 hint 不再重複。

- [done] Playtest card rule bug：`誘導虛耗` 只能移除剛打出的 `誘導虛耗` 本身，不能移除其他卡牌。
  - 2026-07-05 回報情境：使用 `誘導虛耗` 後，UI 顯示「你可以移除剛打出的這張牌，或移除 1 張手牌」，並列出手牌中的 `天方奧援`、`內鬥`、`追隨者`、`樂捐者` 等可移除選項。
  - 期望：依卡牌規則，`誘導虛耗` 的可移除對象應只限於剛打出的 `誘導虛耗` 這張牌；不應允許移除其他手牌，也不應在選擇視窗列出其他手牌作為可移除選項。
  - 需檢查：`誘導虛耗` action effect 的 optional trash / pending choice 建立邏輯、`pending_choice.cards` 來源、`static/app.js` 的 card-choice modal 呈現；確認 runtime 後端也拒絕移除非 `誘導虛耗` 的卡。
  - 回報截圖：`/Users/benmini/.hermes/image_cache/img_fe2d5d612086.jpg`。
  - 2026-07-12 已修正：`optional_trash` 對 `誘導虛耗` 的可移除清單改為僅列「剛打出的誘導虛耗本身」＋明確的「不移除本牌」選項（後端也不再接受手牌項）；移除本牌才進入「選 1 位玩家棄 1 張手牌」的後續流程，選擇不移除則本牌照常進棄牌堆、不觸發後續效果（符合卡面「若移除本牌」條件）。驗證 `python3 scripts/validate_bait_exhaustion_self_only.py`（3/3）；proof `docs/records/action-cards/BAIT_EXHAUSTION_SELF_ONLY_VALIDATION_20260711.{json,md}`。

- [done] Playtest card ownership bug：非紅軍陣營打出 `紅軍奧援` 後，卡牌應回到紅軍棄牌堆。
  - 2026-07-06 回報情境：非紅軍陣營打出 `紅軍奧援` 後，此卡沒有回到紅軍的棄牌堆。
  - 期望：`紅軍奧援` 屬於紅軍專屬卡；即使因借用／取得／特殊流程由非紅軍玩家打出，結算後也應回到紅軍玩家的棄牌堆，而不是留在非紅軍玩家棄牌堆、消失、或進入錯誤區域。
  - 需檢查：`play_card()` / played-card discard destination、紅軍奧援 ownership/original owner metadata、借用卡牌規則、`_make_support_card('紅軍奧援')` 或起始牌庫歸屬、UI 棄牌堆投影是否使用實際 card owner 而非 acting player。
  - 2026-07-12 已修正：root cause 是 `play_card` 的紅軍奧援專屬分支對非紅軍玩家 fallback `player.deck.discard()`（進自己棄牌堆）；行動模式與資源模式現在都改為回到紅軍玩家棄牌堆（找不到紅軍玩家才留原地）；紅軍自己打出的「選反共玩家放入其棄牌堆」既有流程不受影響。驗證 `python3 scripts/validate_red_support_ownership.py`（3/3）；proof `docs/records/support-cards/RED_SUPPORT_OWNERSHIP_VALIDATION_20260712.{json,md}`。

- [done] Playtest card/flow bug：使用 `模仿戰術` 後沒有跳出可使用卡牌的選擇。
  - 2026-07-06 回報情境：玩家使用 `模仿戰術` 後，似乎沒有跳出可讓玩家選擇／使用的卡牌清單。
  - 期望：打出 `模仿戰術` 後，若依規則應可選擇某些可模仿／可使用的卡牌，UI 應顯示對應選擇視窗或明確提示沒有合法目標；不能沒有回饋或讓玩家以為流程卡住。
  - 需檢查：`模仿戰術` card effect 定義、pending choice 建立邏輯、可模仿卡牌來源與合法性篩選、`static/app.js` choice/card modal render，以及無合法目標時的 log/提示與 phase gating。
  - 卡面規則（`data/raw/action_cards.csv`）：「選擇1位玩家展示其牌庫頂牌，本回合您可以使用該牌。使用後將該牌放回擁有者的牌庫頂。」故選擇對象是「玩家」（無法預看對方牌庫），選完展示其頂牌並可於本回合使用。
  - 2026-07-13 已修正並提交：root cause 是**兩層問題**。①前端 `app.js` 的 `openCardTargetModal` 對 `players.length === 1`（2 人局，測試最常見）會**自動選定唯一對手、完全不跳 modal**，直接送 `play_card` 帶 `target_player_id`——這就是「沒跳出選擇」；②前端選單也沒過濾牌庫全空的對手。②伺服器 `imitate_topdeck` 效果原本直接抓「第一個其他玩家」的頂牌塞進手牌，沒有任何選擇步驟。修法：改為**伺服器統一驅動**選擇——`imitate_topdeck` 在未帶 target 時呼叫新的 `_prompt_imitate_topdeck_target()` 建立 `imitate_topdeck_target` 目標選擇（`type: target_choice`，前端既有 target_choice modal 通用渲染，**單一對手也會跳 modal**）；目標清單 `_imitate_topdeck_targets()` 只列「牌庫堆或棄牌堆任一有牌」的對手（`draw()` 會在 draw_pile 空時重洗棄牌堆，故只有兩堆全空才無牌可展示）；resolve 時 `_perform_imitate_topdeck()` 抽該玩家頂牌進手牌、標記 `_return_to_owner_topdeck`（既有歸還機制）；無合法目標時記 log、不建立 pending、不卡住。前端把 `模仿戰術` 從 `playerTargetCards` 自動選清單移除，改由伺服器處理。驗證 `python3 scripts/validate_imitate_tactics.py`（5/5：單一對手仍跳選擇、多對手全列、只有棄牌堆也算合法目標、全空不卡住、resolve 後模仿到手牌並標記歸還）＋真實出牌瀏覽器 E2E 確認 2 人局也跳出「模仿戰術」選擇 modal（proof `docs/records/action-cards/IMITATE_TACTICS_MODAL_BROWSER.png`、`IMITATE_TACTICS_VALIDATION.{json,md}`）；既有 `validate_red_support_ownership.py`（3/3）、`validate_divide_targets_others_only.py`（2/2）target-choice 回歸無退化。無合法目標的提示目前為戰況紀錄 log（極罕見：需所有對手兩堆全空）；如需更顯眼的 phase notice 可後續加強。

- [done] Playtest card rule bug：紅軍使用 `離間` 時，`內鬥` 應只放到對方牌堆，不應放到紅軍自己的牌堆。
  - 2026-07-11 進度註記：`離間` 憑空創造內鬥、不扣供應的部分已隨 C1 修正（commit `9c59dc2`）。
  - 2026-07-12 已修正：`離間` 效果改為 `target_scope: others / max_targets: 3 / 每人1張`（資料驅動），對象為施放者以外最多 3 位玩家、每人棄牌堆各放 1 張；`add_internal_conflict` 移除「無目標時 fallback 給施放者自己」的錯誤路徑（改為記 log 不放置）；`情報網`選項A 共用同一路徑。驗證 `python3 scripts/validate_divide_targets_others_only.py`（2/2：3人局施放者牌堆無內鬥、其他兩人各1張、供應扣2；4人局最多3個目標各1張）。proof `docs/records/action-cards/DIVIDE_TARGETS_OTHERS_ONLY_VALIDATION_20260711.{json,md}`。
  - 2026-07-06 回報情境：紅軍使用 `離間` 後，效果似乎把 `內鬥` 放到了紅軍自己的牌堆。
  - 期望：`離間` 應只將 `內鬥` 放到指定對方／目標玩家的牌堆；紅軍自己不應成為此效果的放置目標。
  - 需檢查：`離間` card effect 定義、target player selection、`add_internal_conflict` / static supply 消耗、紅軍作為 actor 時的 target/recipient 判定，以及 UI/log 是否正確顯示內鬥進入哪位玩家牌堆。

- [done] Playtest card/flow polish：使用 `組織經驗甲` 時，應確認是否還要花其他 4 點以上卡牌來建立組織。
  - 2026-07-06 回報情境：玩家使用 `組織經驗甲` 時，目前流程似乎沒有先詢問玩家是否要額外花其他 4 點以上的卡牌來建立組織。
  - 2026-07-11 已修正：連同卡面「棄4點以上可重複建立」子句一併實作，每次建立後跳出明確確認（不再建立／棄1張再建立1次），4點判定使用總購買成本（資金+宣傳），拒絕時不消耗任何東西。詳見「規則資料 vs 程式實作落差修正」區塊的對應條目；驗證 `python3 scripts/validate_org_exp_a_repeat_build.py`（5/5）；proof `docs/records/action-cards/ORG_EXP_A_REPEAT_BUILD_VALIDATION_20260711.{json,md}`。

- [done] Playtest card rule bug：`點燃熱情` 在本回合曾打出宣傳費用卡牌時應抽 2 張，但實際只拿到 1 張。
  - 2026-07-10 已修正（與 `樹立信心` 同根因一起修，commit `7c066fd`）：條件判定由「卡牌種類」改為「實際購買費用組成」；驗證 `python3 scripts/validate_cost_composition_triggers.py`（9/9）。詳見「規則資料 vs 程式實作落差修正」區塊對應條目。
  - 2026-07-06 回報情境：Turn 19 使用 `點燃熱情`，且該回合曾經打出過有宣傳費用的卡牌；log 顯示 `[Turn 19] f played 點燃熱情`、`[Turn 19] f chose 點燃熱情 via 地下黨`，但最終只有拿到 1 張卡牌。
  - 期望：若本回合曾打出有宣傳費用的卡牌，`點燃熱情` 應多抽 1 張，也就是總共抽 2 張；透過 `地下黨` 選擇／取得後使用時也應套用同一條件。
  - 需檢查：`點燃熱情` card effect 條件判定、turn log/旗標是否正確記錄「本回合曾打出有宣傳費用的卡牌」、`地下黨` 觸發或選牌後是否保留/套用 acting card context，以及抽牌數與 UI 手牌顯示是否一致。

- [done] Playtest card/flow bug：紅軍使用 `北國奧援` 觸發先瓦解己方組織、再瓦解敵方組織時，關閉/離開視窗後無法繼續瓦解。
  - 2026-07-06 回報情境：紅軍使用 `北國奧援`，觸發「可以瓦解自己組織，再瓦解敵方組織」的流程；按了離開或關閉後，就無法再瓦解組織，畫面無法動彈，即使按 `瓦解目前城鎮組織` 也無法完成。
  - 期望：關閉/離開選擇視窗不應清除或破壞後續 target pending choice；玩家應可回到地圖繼續選擇合法己方/敵方組織並完成兩步瓦解，或可明確取消整個效果且不卡住階段。
  - 需檢查：`北國奧援` support tier effect 的兩段式 dissolve pending choice、choice modal close handler、map highlight preservation、`瓦解目前城鎮組織` sidebar action、pending_choice state machine，以及與先前 `情報網` 關閉後仍可地圖瓦解修正是否可共用同一 target-choice close behavior。
  - 2026-07-13 調查：`北國奧援` I級（`interactive_dissolve_self_and_enemy`）是 `support_interaction` 兩段流程——step1 `sacrifice_town`（選要犧牲的己方組織）、step2 `target`（選鄰近敵方組織瓦解）。root cause 與 `中紀委` 同一個系統性根因：step1 的 `sacrifice_town` 不是 map-context（`shouldUseMapContextModal` 只在 `step==='target'` 為真），舊版關閉鈕會 `closeChoiceModal()` 只隱藏、不清伺服器 pending，導致卡住——這正是回報症狀。
  - 2026-07-13 已由 commit `d0fa562`（可取消 pending choice／關閉鈕政策）**順帶修好**：step1 `sacrifice_town` 屬「非可取消且非地圖」的 blocking 選擇，關閉鈕現在**直接隱藏**，無法再靠關閉卡住、必須選 1 個犧牲城鎮才前進；step2 `target` 維持 map-context（保留「關閉」＝保留地圖高亮、可從地圖側欄「瓦解目前城鎮（效果）」完成，比照 `情報網` 既有 pattern）。本次補上專門驗證鎖住此流程。驗證 `python3 scripts/validate_beiguo_two_stage_dissolve.py`（6/6：step1 無關閉鈕不會卡住、選犧牲後前進到 target step、target step 保留關閉鈕、modal 路徑完成瓦解敵方＋犧牲己方、關閉 target modal 後 pending 仍在且地圖側欄瓦解鈕可用、地圖路徑同樣完成）；proof `docs/records/support-cards/BEIGUO_TWO_STAGE_DISSOLVE_VALIDATION.{json,md}` + `beiguo_two_stage_dissolve.png`。至此 **P1 UI 批次全部完成**。

- [done] Playtest victory/flow bug：到第 20 回合時沒有直接宣告勝利者。
  - 2026-07-06 回報情境：遊戲看起來已到第 20 回合，但系統沒有直接宣告勝利者是誰。
  - 期望：依 `rules.md` 勝利條件，第 20 回合結束前無人勝利則紅軍勝利；到達應結算時點時，UI/後端應明確進入 finished 狀態並宣告勝利者，不應讓遊戲繼續停在未結算狀態。
  - 需檢查：`VictoryChecker` / `Game.end_turn()` / round-turn advancement、Turn 20 結束階段判定時機、事件獎懲與勝利判定順序、`winner` state projection、UI 勝利提示/finished modal，以及是否 off-by-one（第 20 回合開始 vs 第 20 回合結束）。
  - 2026-07-12 後端已修正：root cause 是 `_check_victory` 只在 `_end_turn` 開頭執行（此時回合數仍為 20），輪次翻到 21 的當下沒有再判定，遊戲滑進第 21 回合、直到下一位玩家結束回合才宣告。現在 `_end_turn` 在輪次翻頁（`turn += 1`）後立刻判定——第 20 輪完成的瞬間宣告紅軍保底勝利（含 A4 共同勝利者），且不再抽第 21 回合事件。驗證 `python3 scripts/validate_turn20_victory_declaration.py`（3/3：20輪翻頁即宣告且不抽新事件、19→20 不會提早宣告、輪中反共玩家達成條件仍即時宣告）。proof `docs/records/rules-audit/TURN20_VICTORY_DECLARATION_VALIDATION_20260712.{json,md}`。**勝利/共同勝利的 UI 顯示（finished modal）仍屬 P1 UI 批次**。

- [done] Playtest UI polish：Lobby 房間代碼複製功能保留一個即可，移除最上方重複複製入口。
  - 2026-07-09 回報情境：Lobby 畫面同時在最上方房間代碼橫幅與下方「建立 / 加入房間代碼」輸入列各有一個 `複製` 按鈕，功能重複。
  - 期望：複製功能保留一個就好；最上面的房間代碼橫幅複製入口可以移除，避免 UI 重複與視覺干擾。
  - 需檢查：`static/index.html` lobby room banner / room-code input row、`static/app.js` 的 `copyRoomId()` 綁定與 lobby room banner 顯示邏輯；確認移除上方入口後仍能從保留的複製按鈕成功複製房間代碼。
  - 回報截圖：`/Users/benmini/.hermes/image_cache/img_3c6a990786b4.jpg`。
  - 2026-07-12 第一輪修正：移除橫幅內重複的 `copyRoomBannerBtn` 按鈕，`lobbyRoomBannerCode` 由可點擊的 `<button onclick="copyRoomId()">` 改為純顯示用的 `<span>`；橫幅仍保留，顯示房間代碼供辨識/分享。
  - 2026-07-12 使用者複測後指出：即使拿掉複製按鈕，最上方那條橫幅仍整條顯示房間代碼，跟下方輸入列的房間代碼是同一組資料重複顯示（不需捲動即可同時看到兩處），本身就是多餘的顯示區域，不只是複製按鈕重複。裁決：整條橫幅移除（而非保留成唯讀顯示）。
  - 2026-07-12 已修正並提交（最終版）：完全移除 `#lobbyRoomBanner`（含 `lobbyRoomBannerCode`、`lobby-room-banner-*` 全部 CSS 規則、`#lobby.room-active .lobby-brand/.lobby-briefing` 的橫幅讓位偏移）；`syncLobbyRoomCode()`／`selectRoomCodeForManualCopy()` 移除橫幅相關的死路徑。房間代碼現在只在下方「建立 / 加入房間代碼」輸入列顯示，`copyRoomBtn` 是唯一複製入口。驗證 `python3 scripts/validate_lobby_copy_dedup.py`（5/5：橫幅三個元素皆確認不存在、僅剩一個 `copyRoomId()` 按鈕、輸入框正確顯示代碼且無其他元素重複顯示同一組代碼文字）＋更新後的 `python3 scripts/validate_lobby_join_room_code_ui.py`（12/12：移除橫幅存在性斷言、改為斷言橫幅不存在，並把原本夾帶在「橫幅不遮擋操作區」檢查裡的陣營面板可捲動高度斷言拆成獨立檢查保留覆蓋）＋既有 `python3 scripts/validate_lobby_polish.py`（3/3）與 `python3 scripts/validate_multiplayer_lobby_flow.py`（9/9）皆無退化；proof `docs/records/lobby/LOBBY_COPY_DEDUP_VALIDATION.{json,md}` + `lobby_copy_dedup_validation.png`。

- [todo] 下一步建議：開 LAN 桌測／端到端 playtest，記錄實際遊戲中出現的 UI polish 或規則落差，再回寫成具體 P0/P1 項目。
  - 目前事件／時代 scope 已可 playtest；不要再以 speculative implementation 延伸 P0，除非 playtest 或規則文本指出具體 bug。
  - 事件面板 polish 待 playtest 後再決定是否需要展開/收合、詳細文字、或事件歷史紀錄。
  - 目前面板位置：右上紅框區，`.event-card-panel` 為 `width: 300px; height: 200px; max-height: 200px; top: 0; right: 24px`。
  - 現有 proof：`docs/records/event-cards/EVENT_CARD_LAYOUT_REDFRAME_300X200_PROOF_2026_05_23.md` 與同名截圖。

### P2：repo hygiene / validator hygiene
- [todo] 維持 root record-like count = 0。
  - 新增 validation reports、proof markdown、screenshots 時，直接放到 `docs/records/<topic>/`。
  - 若新增 validator，確認輸出路徑不是 repo root，且失敗時 exit non-zero。

- [done] `scripts/validate_event_cards_runtime.py` 已長期失效（stale），需更新至現行事件生命週期後恢復可跑。
  - 2026-07-11 發現：`test_hong_kong_success_static_supply` 起穩定失敗；用 git worktree 往回跑 20+ 個 commit（含 `8191639` 之前）全部 FAIL，證明壞掉已久、沒有人在跑。
  - root cause：2026-05-31 事件卡生命週期改為「任務條件達成先 `success_pending`，等全體玩家 ACTION 結束才結算」（TODO 已記錄的刻意設計），但腳本裡的 `settle_round_event()` helper 還停留在舊設計（`advance_turn_phase()` 一次就期待 `settled=True`）；單人 advance 後實際狀態是 `success_pending`＋輪到下一位玩家，不是結算完成。屬於驗證腳本過期，不是 runtime bug。
  - 需修：把 `settle_round_event()` 改成推進到整輪結束（所有玩家含紅軍完成 ACTION）再斷言 `settled`；逐一檢查該檔 20+ 個 test 是否還有其他依賴舊生命週期的斷言。修好前，該腳本的 FAIL 不應被當成 regression 訊號（例如 S3 修正時已另建 `validate_event_deck_draw_twenty.py` 獨立驗證）。
  - 2026-07-11 追加：`scripts/validate_era_effects_runtime.py` 同樣為既有穩定 FAIL（stash 比對確認早於 S2 修正），需一併排查是否同一類生命週期過期問題。
  - 2026-07-11 追加：`scripts/validate_action_card_end_turn_topdeck_runtime.py` 亦為既有 FAIL（期待單人結束回合直接推進到 EVENT 的過期斷言），同一類問題。
  - 2026-07-12 已修復兩支：`validate_support_no_reaction_phase_gating.py`（南洋奧援 I 級在 B1-b 之後合法開棄牌選擇，斷言改為「不得是 reaction_choice、棄牌選擇需可解決」）與 `validate_support_purchase_deck_runtime.py`（2026-06-26 起 buy_card 僅限購買階段，腳本補設 END phase），兩支恢復全綠。
  - 2026-07-13 已修復兩支：`validate_faction_abilities_phase5.py`（華文傳媒買牌測試改 END 階段，4/4）、`validate_action_card_end_turn_topdeck_runtime.py`（斷言改為「turn 傳給下一位玩家」而非固定停在 EVENT，3/3）。
  - 2026-07-13 已修復：`validate_era_effects_runtime.py`（內鬥/分神 static-supply 封頂測試改真的把 supply 設低才測到封頂、香港買牌補 END 階段、反賊建立測試避開敵佔的北京，15/15）與 `validate_turn_phase_action_gating.py`（整支改寫成現行「開局即 ACTION＋回合事件已抽好、每回合 ACTION→END、整輪繞回才抽新事件」模型，取代過期的「每人 EVENT 階段」模型，13/13）。
  - 2026-07-15 已修復 `validate_event_cards_runtime.py` 本體，過程中**額外挖出一個真的 runtime bug**（非驗證腳本問題）：mission 事件的結算被延後到 `_end_turn()` 之後執行（讓獎懲作用在補牌後的手牌），但若這次 `_end_turn()` 剛好也讓整輪繞回，`_end_turn()` 會先重置 `current_event`/`event_progress`、抽新事件，導致延後的結算讀到「被重置的新事件進度」——本回合已達成的成功獎勵消失、新抽的事件被誤判為失敗並套用懲罰到錯的情境。修法：`advance_turn_phase` 在 `_end_turn()` 前先快照該回合的事件與進度，若偵測到整輪繞回，就對快照結算（結算完再換回新回合事件顯示）。commit `ac77e74`；驗證 `python3 scripts/validate_event_cards_runtime.py`（35/35，連跑 3 次穩定）；server 相關回歸（turn20 victory、end_turn refill、phase gating 13/13、end_turn topdeck、era effects 15/15、faction abilities、support gating、support purchase deck）全綠。
  - **至此本區塊列出的 5 支過期驗證腳本全數修復完成**（`validate_event_cards_runtime`、`validate_era_effects_runtime`、`validate_action_card_end_turn_topdeck_runtime`、`validate_turn_phase_action_gating`、`validate_faction_abilities_phase5`）；相關 commits：`0f1e7bc`（前 4 支）、`ac77e74`（最後一支＋真 bug 修復）。

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
  - 2026-06-01 follow-up：修正實際桌測點選橘色城鎮後 sidebar 仍未選取、無法建立組織與無城鎮資訊的問題；城鎮標籤不再攔截點擊，地圖 click 會對事件可選城鎮做 proximity hit-test，建立後 sidebar 會刷新目前城鎮資訊。proof：`docs/records/event-cards/BELT_ROAD_NANYANG_MAP_TOWN_SELECTED_BUILD_READY_2026_06_01.{md,json,png}`。
- [done] 常設購買區可購買性、常設牌不混入隨機購買區、手牌資源/行動按鈕 listener 修正。
- [done] 紅軍奧援起始牌庫歸屬修正。
  - 2026-05-25：已修正 `紅軍奧援` 不應進隨機奧援購買樣本，而應作為紅軍起始牌庫專屬卡；Lobby 選定紅軍後會重建起始牌庫，確保實際選紅軍玩家擁有 1 張 `紅軍奧援`，非紅軍與購買牌庫不含該卡。驗證紀錄：`docs/records/support-cards/SUPPORT_PURCHASE_DECK_RUNTIME_VALIDATION.{md,json}`。
- [done] 紅軍陣營能力 runtime / UI 說明補齊。
  - 2026-05-25：已實作紅軍能力 `統戰部`、`政工部`、`國安部`、`中紀委` runtime 與前端按鈕；紅軍能力彈窗文字說明區已列出四項效果說明。驗證紀錄與正式 browser UI proof：`docs/records/event-cards/RED_ARMY_FACTION_ABILITIES_RUNTIME_VALIDATION.{md,json}`、`RED_ARMY_FACTION_ABILITIES_HELP_UI_PROOF_2026_05_25.{md,json}`、`RED_ARMY_FACTION_ABILITIES_HELP_UI_2026_05_25.png`。
  - 2026-05-25：已修正 `政工部` 從錯誤的 `內宣` 改為將常設牌 `內鬥` 放到目標玩家牌庫頂，並遵守 static supply（供應歸零時不憑空新增）。補 runtime validator 與正式 browser UI proof：`docs/records/event-cards/RED_ARMY_POLITICAL_WORK_INTERNAL_CONFLICT_UI_PROOF_2026_05_25.{md,json}`、`RED_ARMY_POLITICAL_WORK_INTERNAL_CONFLICT_HELP_UI_2026_05_25.png`、`RED_ARMY_POLITICAL_WORK_INTERNAL_CONFLICT_RESULT_UI_2026_05_25.png`。
  - 2026-05-25：已補紅軍特殊規則 runtime：4 種紅軍能力視同行動卡可被既有取消反應牌取消；同一玩家同回合成功瓦解紅軍根據地 2 次後根據地消失且不可重建；紅軍組織移動不得離開紅軍發展空間。驗證紀錄：`docs/records/event-cards/RED_ARMY_SPECIAL_RULES_RUNTIME_VALIDATION.{md,json}`。
  - 2026-06-01：紅軍能力改為手動按鈕觸發，不再自動彈出；紅軍可在購買階段前（EVENT/ACTION）自行決定何時發動，並補 WebSocket event-phase regression 與正式 browser UI proof。驗證：`scripts/validate_red_army_faction_abilities.py`、`scripts/tests/test_red_army_ability_timing_ws.py`；proof：`docs/records/event-cards/RED_ARMY_ABILITY_MANUAL_BUTTON_UI_2026_06_01.{md,json,png}`。
  - 2026-06-01 follow-up：修正紅軍事件階段仍可點手牌 `紅軍奧援` 的「行動／資源」按鈕、導致 `Not in ACTION phase` alert 的問題；現在一般手牌仍只在 ACTION／購買階段啟用，但紅軍可在 EVENT／開始購買階段前直接按 `紅軍奧援` 的「行動」；`紅軍奧援` 的「資源」仍需等購買階段。validator：`scripts/validate_turn_phase_action_gating.py`；proof：`docs/records/playtest-flow/RED_SUPPORT_PREPURCHASE_ACTION_ENABLED_UI_2026_06_01.{md,json,png}`。
- [done] 第二輪 root validation artifacts / validator output path / failure exit-code 整理。
  - root record-like count 已確認為 0。

### 規則資料 vs 程式實作落差修正（源自 `docs/records/rules-audit/RULES_VS_IMPLEMENTATION_GAP_AUDIT_20260710.md`）
- [done] B1-a：`東洋奧援` 的中介資料檔損毀，且順帶修正因此曝露的 tier2 誤判 bug。
  - root cause 1（資料）：`data/cards/support_taxonomy.v1.1.json` 的 `東洋奧援` 條目與其產生腳本 `scripts/build_support_card_taxonomy.py` 根據的來源資料 `data/cards/support_cards.v1.1.json` 不同步，導致其中一個地區變體只剩「本地區（東洋）」的 III 級條件、缺 II 級條件；另一個變體只保留「臺灣、南洋」配對，CSV 規定的第二組配對「北國、英美」完全遺失，玩家同時主導北國＋英美時會被錯誤卡在 I 級。
  - root cause 2（程式，因修正資料後才被暴露）：`server/game.py:_resolve_support_card_effect` 對 `東洋奧援` tier2 多了一段 `region_index == 0` 的特例，回傳跟 tier3 相同的 `interactive_build_anywhere_inner`（無視距離建立）而不是 tier2 該有的 `interactive_build_near_inner`（1格內建立）；資料損毀時 index0 剛好幾乎不可能真的走到 tier2 分支，所以這段錯誤程式碼從未在正常遊戲中被觸發，直到這次把資料修正回正確的雙地區配對後才會被觸發（此時 index0 變成「臺灣、南洋」配對）。其餘所有奧援卡的 tier 分派都只看 `tier` 數值、不看 `region_index`，這是唯一一張有這種特例的卡，判斷為遺留 bug 而非刻意設計。
  - 修正：重新執行 `scripts/build_support_card_taxonomy.py` 重新產生 `data/cards/support_taxonomy.v1.1.json`（含補回「北國、英美」配對）；移除 `server/game.py` 裡 `東洋奧援` tier2 的 `region_index == 0` 特例分支，統一回傳 `interactive_build_near_inner`。
  - 驗證：`python3 scripts/validate_east_asia_support_taxonomy_fix.py`（4/4 passed，涵蓋 tier3 本地區、tier2 兩種配對、tier1 fallback 四種情境）。
  - proof：`docs/records/support-cards/EAST_ASIA_SUPPORT_TAXONOMY_FIX_VALIDATION_20260710.{json,md}`。
  - 落差盤點報告已同步更新對應項目狀態：`docs/records/rules-audit/RULES_VS_IMPLEMENTATION_GAP_AUDIT_20260710.md`。

- [done] A3：粵/澳門與香港的共用組織規則只有單向生效。
  - root cause：`server/game.py:_factions_sharing_with` 用寫死的中文子字串比對各陣營 `special_rules` 文字來判斷共用組織關係；`hong_kong` 自己的文字「可與粵、澳門反賊共用組織。」有命中 `粵、澳門` pattern，但 `yue`（粵）與 `aomen`（澳門）各自的文字「遊戲過程中可與香港共用組織。」沒有任何 pattern 包含『香港』，導致從 `yue`/`aomen` 玩家視角呼叫 `_factions_sharing_with` 時看不到 `hong_kong` 的組織，只有 `hong_kong` 看得到 `yue`/`aomen`，關係只單向生效。
  - 修正：在 `_factions_sharing_with` 的 pattern 清單補上 `if '香港' in text: shared.update(['hong_kong'])`，使 `yue`/`aomen` ↔ `hong_kong` 雙向對稱。
  - 驗證：`python3 scripts/validate_yue_aomen_hongkong_shared_org.py`（5/5 passed，涵蓋 yue→hong_kong、aomen→hong_kong 兩個新修正方向、hong_kong→yue、hong_kong→aomen 兩個既有方向回歸測試，以及一個無關陣營不應被誤判共用的 sanity check）。
  - proof：`docs/records/faction-ui/YUE_AOMEN_HONGKONG_SHARED_ORG_FIX_VALIDATION_20260710.{json,md}`。
  - 落差盤點報告已同步更新對應項目狀態：`docs/records/rules-audit/RULES_VS_IMPLEMENTATION_GAP_AUDIT_20260710.md`。

- [done] `企業人脈` 借用範圍誤排除常設購買區。
  - root cause：`data/action_cards_structured.v1.1.json` 的 `企業人脈` 效果定義 `prefer_random_market: true`，導致 `server/effect_engine.py` 的 `use_purchase_area_card` 分派只從隨機購買區（`static_count` 之後的槽位）列出可借用選項，排除了常設購買區的 6 張牌（`宣傳家`/`思想家`/`資助者`/`資本家`/`分神`/`內鬥`）；但卡面文字「將購買區面朝上的任1張牌暫時移出購買區」沒有限定只能是隨機購買區。
  - 修正：把 `企業人脈` 的 `prefer_random_market` 改成 `false`，可借用範圍涵蓋整個購買區（常設 + 隨機）。
  - 驗證：`python3 scripts/validate_business_network_static_purchase_area.py`（1/1 case、6 項 check 全過，確認選項列出全部 11 個購買區槽位，且成功借用並使用常設購買區的 `宣傳家`）。
  - proof：`docs/records/action-cards/BUSINESS_NETWORK_STATIC_PURCHASE_AREA_FIX_VALIDATION_20260710.{json,md}`。
  - 落差盤點報告已同步更新對應項目狀態：`docs/records/rules-audit/RULES_VS_IMPLEMENTATION_GAP_AUDIT_20260710.md`。

- [done] `情報網` 非反應時機下選項C選了沒效果。
  - root cause：`情報網` 卡面效果「三選一：Ａ放內鬥／Ｂ瓦解／Ｃ其他玩家行動時打出，取消對方能力」，其中 C 依卡面文字只在「別人打牌、自己手上握著情報網跳出來反應」的情境才有意義。但 `data/action_cards_structured.v1.1.json` 的 `choose_one` 效果定義把 A/B/C 三個選項無條件全部列出，不管是不是在反應情境；玩家在自己回合正常打出情報網選了 C，會呼叫 `cancel_card`（`server/effect_engine.py:524-529`），但 context 裡沒有真正「被取消的牌」資訊，只會印一行「canceled unknown card」，沒有任何實際效果，等於白白浪費一整張卡。真正的反應取消用法完全由另一套獨立流程處理（`_reaction_prompt_candidates`／`_build_reaction_context`／`_resolve_reaction_context`，`server/game.py` 約 3646-3866 行），該流程從不經過 `choose_one`，所以選項 C 在 `choose_one` 這條路徑裡本來就永遠不會有正確結果。
  - 修正：直接把選項 C 從 `data/action_cards_structured.v1.1.json` 的 `情報網` `choose_one` 選項清單移除，自己回合正常打出時只保留 A/B 兩個真正有效果的選項；反應取消能力完全交給既有的獨立反應流程，不受影響。
  - 驗證：`python3 scripts/validate_intel_network_no_reaction_option_own_turn.py`（2/2 case、8 項 check 全過：確認自己回合正常打出只剩 2 個選項且不含取消字樣；同時回歸驗證反應流程仍可正確取消對方的牌，且被取消的牌效果沒有執行）。
  - proof：`docs/records/action-cards/INTEL_NETWORK_NO_REACTION_OPTION_OWN_TURN_VALIDATION_20260710.{json,md}`。
  - 落差盤點報告已同步更新對應項目狀態：`docs/records/rules-audit/RULES_VS_IMPLEMENTATION_GAP_AUDIT_20260710.md`。

- [done] `點燃熱情`／`樹立信心` 條件判定看錯欄位（種類而非購買費用），且同一根因也影響4個陣營能力。
  - root cause：兩張卡的觸發條件都是「若本回合曾打出其它購買費用有資金/宣傳的牌」，但 `server/game.py:play_card()` 判斷「這回合有沒有打過資金/宣傳牌」時，用的是 `effective_type = getattr(played_card, "card_type", None)`（也就是卡牌的「種類」分類），而不是實際購買費用組成。實際比對全部46張行動卡的「種類」與「購買費用」欄位，發現兩者經常對不上（例如`謀劃`種類是「指揮」，購買費用卻是「資金1+宣傳1」），導致打出這類卡完全不會被算進「本回合曾打出資金/宣傳牌」，`點燃熱情`/`樹立信心`因此常態性漏觸發。同一組 `effective_type` 判斷還驅動另外4個陣營能力（`商貿組織`、`基金會`/`共合會`、`民族調和`/`星星之火`、`人同此心`，規則文字同樣是「打出購買費用有資金/宣傳的牌時」），一併有同樣的低觸發問題。
  - 修正：改成用 `_card_purchase_cost()` 判斷實際購買費用是否含資金/宣傳（`cost_has_money`/`cost_has_propaganda`），取代 `effective_type` 判斷；維持既有「奧援卡不算」的行為不變；沿用既有 `國際線` 能力（資金可折抵宣傳）把資金費用轉記為宣傳費用的邏輯。修正時額外抓到一個因此次修正而浮現的新問題：`點燃熱情`/`樹立信心`的條件文字明講是「其它」（別的）牌，但改成看購買費用後，這兩張卡自己的購買費用本身就含資金/宣傳，會變成觸發到自己身上；修法是在 `play_card()` 記錄「本回合這張牌打出前」的旗標快照存進 `action_context['prior_played_money_card']`/`prior_played_propaganda_card`，`server/effect_engine.py` 的 `conditional_draw` 改讀這個「打出前」快照而非即時旗標，恢復「排除自己」的正確語意。另外也發現並補上一個獨立於本次根因、但同樣影響這兩張卡的既有缺口：透過反應延遲流程（`_resume_reaction_pending_action`，例如某張牌打出後別人可以選擇是否用`情報網`/`爆料黑幕`取消，即使最後選擇跳過）播放的牌，先前完全不會設定`played_money_card`/`played_propaganda_card`旗標，這次一併補上。
  - 驗證：`python3 scripts/validate_cost_composition_triggers.py`（9/9 case 全過：`點燃熱情`/`樹立信心`用種類/費用不一致的卡觸發成功；沒有合格出牌時維持只抽1張的基線；奧援卡仍不算入的回歸測試；4個陣營能力都用種類/費用不一致的卡驗證成功觸發；反應延遲流程中即使選擇跳過反應，旗標與能力仍正確觸發）。
  - proof：`docs/records/action-cards/COST_COMPOSITION_TRIGGERS_FIX_VALIDATION_20260710.{json,md}`。
  - 落差盤點報告已同步更新對應項目狀態：`docs/records/rules-audit/RULES_VS_IMPLEMENTATION_GAP_AUDIT_20260710.md`。

- [done] B1-b：`南洋奧援` I級「抽1張牌，再從所有手牌中棄掉1張牌」等於沒抽沒棄。
  - root cause：`server/game.py:_execute_support_card()` 的 `draw_then_discard` 分支原本是抽牌後直接 `player.hand.pop()`；因為 `_draw_player_cards()` 把抽到的牌加到手牌**尾端**，`pop()` 彈出的正好就是剛抽到的那張，等於「抽1張又立刻棄掉同一張」，淨效果是 no-op，玩家完全沒有選擇棄哪張牌的機會，跟卡面文字「從所有手牌中棄掉1張牌」暗示的玩家選擇不符。
  - 修正：抽牌後改成用既有的 `_set_pending_card_choice()` 對整副手牌（含剛抽到的牌）開一個真正的棄牌選擇（新 choice_key `draw_then_discard_choice`），`_resolve_card_choice()` 補上對應解析：把玩家選中的牌從手牌移到棄牌堆（棄牌堆，不是移除出局）。
  - 驗證：新增 `python3 scripts/validate_south_seas_support_tier1_discard_choice.py`（2/2 case 全過：確認會跳出涵蓋全部手牌的棄牌選擇、不會自動解決；確認玩家可以選擇棄掉「別的」那張牌、保留剛抽到的牌，證明是真選擇而非固定結果）；同步更新既有回歸測試 `python3 scripts/validate_support_card_effects_runtime.py`（12/12 case 全過，含南洋奧援三個等級）讓它改成先解決棄牌選擇（選擇棄掉剛抽到的牌）再檢查最終手牌/棄牌堆狀態。
  - proof：`docs/records/support-cards/SOUTH_SEAS_SUPPORT_TIER1_DISCARD_CHOICE_VALIDATION_20260711.{json,md}`、更新後的 `docs/records/support-cards/SUPPORT_CARD_EFFECTS_RUNTIME_VALIDATION.{json,md}`。
  - 落差盤點報告已同步更新對應項目狀態：`docs/records/rules-audit/RULES_VS_IMPLEMENTATION_GAP_AUDIT_20260710.md`。

- [done] A2（部分）：`民運派`／`性別革命` 的 `非暴力` 能力未被解析，武裝卡限制形同虛設。
  - root cause：`民運派`（minyun）與`性別革命`（gender_revolution）的 `abilities_text` 各有一條「【非暴力】禁止持有武裝類卡牌。」，但 `server/game.py:_resolve_ability_text()` 的名稱對照表（`mapping`/`direct` 兩個字典）沒有「非暴力」這個名稱，導致這條能力被 `_resolve_faction_abilities()` 悄悄丟棄；`_player_is_nonviolent()`／`_card_is_banned_for_player()` 永遠查不到這兩個陣營有「非暴力」能力，武裝類卡牌的打出/購買限制完全沒有生效。
  - 修正：在 `direct` 對照表補上 `"非暴力": {"name": "非暴力", "type": "restriction", "effect": "禁止持有武裝類卡牌。"}`，沿用既有 `_player_is_nonviolent()`/`_card_is_banned_for_player()` 的檢查邏輯（跟結構化陣營如西藏達蘭薩拉、維吾爾慕尼黑共用同一套機制），不需要新增任何檢查點。已確認範圍風險：`_card_is_banned_for_player()` 目前擋的是 `{"armed","equipment"}` 兩種卡牌種類，但實際核對 `data/raw/action_cards.csv` 全部46張卡的種類欄，這個遊戲的卡牌資料裡完全沒有「裝備」種類的卡，所以在目前資料下擋 `{"armed","equipment"}` 跟只擋 `{"armed"}` 效果一致，沒有把限制範圍意外擴大到「裝備類」的疑慮。
  - 驗證：`python3 scripts/validate_minyun_gender_revolution_nonviolent.py`（7/7 case 全過：兩個陣營的能力都能正確解析、打出與購買武裝卡都被正確擋下且卡牌保留在原本位置；另外驗證一個沒有此能力的陣營仍可正常打出武裝卡，作為回歸 sanity check）。
  - proof：`docs/records/faction-ui/MINYUN_GENDER_REVOLUTION_NONVIOLENT_FIX_VALIDATION_20260711.{json,md}`。
  - 落差盤點報告已同步更新對應項目狀態：`docs/records/rules-audit/RULES_VS_IMPLEMENTATION_GAP_AUDIT_20260710.md`；A2 剩下兩個能力（`紅軍派系`、`民族祭儀`）仍待處理。

- [done] S3（第二輪盤點）：事件牌庫未依 `rules.md` 步驟⑦「混洗後抽出20張」，全部事件卡都直接入庫。
  - root cause：`server/game.py:_initial_event_cards()` 依「卡牌張數」展開全部事件卡（共 25 張——第二輪盤點報告原寫 33 張是勘誤，那個數字誤把同一份 CSV 裡的時代卡張數也算進去了）後整批餵給 `EventDeck`，從不抽樣 20 張，導致每場事件組成分佈與實體規則不同（例如 5 張 `歲月靜好` 必定全部在庫）。
  - 修正：新增常數 `EVENT_DECK_SIZE = 20` 與 `_draw_event_deck_cards()`（全池 `random.sample` 抽 20 張，池小於 20 時全取），`EventDeck` 建構改用它；`_initial_event_cards()` 保持回傳完整全池不變，既有的 declared-counts 回歸測試（`validate_event_cards_runtime.py` 內）不受影響。C2（開局可選抽除至多 5 張歲月靜好的難度選項）尚未做，仍待處理。
  - 驗證：`python3 scripts/validate_event_deck_draw_twenty.py`（12 場開局全過：牌庫+已抽出的當前事件合計恰為 20、組成是全池子集、多場之間組成有變化證明是真抽樣；注意 `Game.__init__` 開局進 MAIN 會立刻抽第 1 張事件，驗證需把 discard_pile 算入總量）。另確認 `scripts/validate_event_card_canonical_scope.py` 仍 PASS。
  - proof：`docs/records/event-cards/EVENT_DECK_DRAW_TWENTY_VALIDATION_20260711.{json,md}`。
  - 落差盤點報告已同步更新（含 33→25 勘誤）：`docs/records/rules-audit/RULES_VS_IMPLEMENTATION_GAP_AUDIT_SECOND_PASS_20260711.md`。

- [done] A2（部分）：改革開放派 `紅軍派系` 能力未實作；順帶補上陣營能力後端歸屬檢查、更正 `民族祭儀`「完全未實作」的盤點誤判。
  - root cause 1（紅軍派系）：`reform_opening` 的 abilities_text「【紅軍派系】每回合可檢視1次牌庫頂3張牌，將其以任意順序放回牌庫頂，並抽1張牌。」在 `_resolve_ability_text` 沒有對應名稱、`_activated_faction_action` 也沒有分支，前端也沒有按鈕，完全無法使用。
  - root cause 2（歸屬檢查漏洞）：`_activated_faction_action` 對非紅軍能力**完全沒有檢查發動者陣營是否擁有該能力**，只靠前端依陣營顯示按鈕；任何玩家都能直接透過 WebSocket `faction_action` 呼叫別家的 `立場試探`/`賭徒耳語`/`民族祭儀`/`民主陣線`。
  - 盤點誤判更正（民族祭儀）：第一輪盤點 A2 說 `民族祭儀` 完全未實作——實際上 runtime 分支（`game.py` 與 `賭徒耳語` 共用的猜奇偶分支）與前端 UI（12 陣營的按鈕、猜奇偶 modal、結果顯示）**都已存在**，缺的只是能力名稱對照（導致 `_player_has_ability` 查不到）。仍殘留與能力文字的偏差，另列待辦：①放牌庫底的手牌是寫死 `hand.pop()` 最後一張，未讓玩家選擇（`賭徒耳語` 同文字模式、同問題）；②沒猜中應「獲得2點宣傳**或**2點資金」二選一，目前固定給2點宣傳；③展示的牌庫頂牌目前直接進棄牌堆，能力文字只說「展示」，去向需確認（`賭徒耳語` 亦同）——③歸入第三梯隊待確認語意。
  - 修正：`_resolve_ability_text` 補上 `紅軍派系` 與 `民族祭儀`；`_activated_faction_action` 開頭對非紅軍能力加 `_player_has_ability` 歸屬檢查；新增 `紅軍派系` 分支——重用既有 `era_inspect_deck_top_and_reorder` 多選卡重排機制（`top_count=look_count=min(3,牌庫)`），新增 `draw_after_reorder` context 旗標讓重排完成後自動抽1張；`static/app.js` 加 `reform_opening` 的發動按鈕分支。
  - 驗證：`python3 scripts/validate_red_faction_inspect_reorder.py`（5/5：重排順序正確反映到牌庫頂且抽到重排後的新頂牌、每回合限1次、錯誤陣營呼叫被擋（含用民族祭儀反向驗證）、牌庫不足3張時檢視現有張數、既有能力（立場試探/民族祭儀正確陣營）不被新歸屬檢查誤擋）。回歸：`validate_red_army_faction_abilities.py`、`validate_red_army_special_rules.py`、`validate_faction_action_centered_modal_cleanup.py` PASS；`validate_faction_abilities_phase5.py` 與 `validate_faction_action_guess_result.py` 各有 1 個 FAIL 但經 stash 比對確認為既有失敗（前者是 `華文傳媒` 測試用 ACTION phase 呼叫需要 END phase 的 `buy_card`；後者是 static modal 檢查項），與本次修改無關。
  - proof：`docs/records/faction-ui/RED_FACTION_INSPECT_REORDER_VALIDATION_20260711.{json,md}`。
  - 落差盤點報告已同步更新；A2 剩餘：`民族祭儀` 的①②（明確缺口）與③（待確認）。

- [done] A2（收尾）：`民族祭儀`／`賭徒耳語` 與能力文字的三個偏差修正。
  - root cause：兩能力共用的猜奇偶分支有三處與能力文字不符——①「將1張手牌放進牌庫底」實作成寫死 `hand.pop()` 拿最後一張，玩家沒有選擇；②`民族祭儀` 沒猜中應「獲得2點宣傳**或**2點資金」二選一，實作固定給2點宣傳；③文字只說「展示牌庫頂牌」，實作卻把展示的牌丟進棄牌堆（2026-07-11 使用者確認：看完應放回牌庫頂）。
  - 修正：抽出 `_resolve_guess_ability_with_bottom_card()` helper——手牌多於1張時先開 `guess_ability_bottom_card` 卡牌選擇（只有1張時自動使用，維持一步完成）；展示的頂牌改為放回牌庫頂（`destination: deck_top`）；`民族祭儀` 沒猜中改開 `ethnic_ritual_miss_reward` 選項選擇（2宣傳／2資金），猜中與 `賭徒耳語` 路徑維持一步結算。前端零新元件（重用通用卡選/選項 modal 與既有結果面板），僅更新兩處 `民族祭儀` 提示文字為「沒猜中則獲得 2 點宣傳或 2 點資金（二選一）」。
  - 驗證：更新並擴充 `python3 scripts/validate_faction_action_guess_result.py`（7/7：兩能力命中/未命中、民族祭儀未命中選宣傳/選資金兩路、多張手牌時墊底牌由玩家選且未選的留在手牌、展示牌回到牌庫頂且棄牌堆不變、墊底牌在牌庫底；並順手把該腳本兩個過期的 static 檢查更新到現行 UI 文案——該腳本自此恢復全綠）。回歸：`validate_faction_abilities_phase5.py` 的 `賭徒耳語` 案例 PASS（該腳本僅剩既有的 `華文傳媒` phase 失敗，與本次無關）、`validate_red_faction_inspect_reorder.py` 5/5、`validate_minyun_gender_revolution_nonviolent.py` 7/7。
  - proof：`docs/records/faction-ui/FACTION_ACTION_GUESS_RESULT_VALIDATION.{json,md}`（重新產生，7/7 PASS）。
  - 至此 A2（3個能力字串未解析）全部收尾：非暴力、紅軍派系、民族祭儀（含賭徒耳語連帶修正）。

- [done] S4（第二輪盤點）：開局額外卡應「洗入起始牌庫」，而非放進棄牌堆。
  - root cause：`攬炒策略`（香港+1宣傳家）、`達賴救援`／`東突厥斯坦政府`／`活動家`（各+2宣傳家）、`各界資助`（民運派+1資助者）能力文字都是「洗入起始牌庫」，但 `_apply_setup_abilities` 走 `_add_setup_static_card_to_discard()` 放進棄牌堆；且 `_init_decks()` 先抽完 5 張起手，額外卡要等第一次牌庫耗盡重洗才進循環，整個第一輪牌庫循環（前兩手）都摸不到，開局節奏型能力被實質削弱。
  - 修正：改為 `_add_setup_static_card_to_deck()`（加入牌庫），`_apply_setup_abilities` 有加牌時把已抽的起手牌放回、整副重洗、重抽同樣張數——等同開局就是 11~12 張牌庫再抽起手，起手就可能抽到額外卡；static supply 扣減與供應耗盡保護行為不變；沒加到牌（供應空／無 setup 能力）時不重洗。「宣傳卡 vs 宣傳家」用語問題（達賴救援/東突厥斯坦政府）與本修正無關，仍列第三梯隊待確認。
  - 驗證：新增 `python3 scripts/validate_setup_cards_shuffled_into_deck.py`（6/6：香港/性別革命/民運派額外卡都在牌庫或起手且棄牌堆為空、牌庫總數 11/12 正確、紅軍起始牌庫（含紅軍奧援）不受隊友重洗影響、40 局統計證明起手抽得到也不會永遠抽到、供應耗盡時不加牌不重洗）；同步把既有 `scripts/validate_static_purchase_initial_supply.py` 的兩個「setup 卡在棄牌堆」斷言更新為「在牌庫或起手、棄牌堆為空」（PASS）。
  - proof：`docs/records/faction-ui/SETUP_CARDS_SHUFFLED_INTO_DECK_VALIDATION_20260711.{json,md}`、更新後的 `docs/records/purchase/STATIC_PURCHASE_INITIAL_SUPPLY_VALIDATION.{json,md}`。
  - 落差盤點報告已同步更新對應項目狀態。

- [done] S1（第二輪盤點）：組織棋供應上限完全未實作；紅軍上限依使用者決定採固定 40。
  - root cause：`rules.md` 步驟④明定反共陣營各 22 個組織棋為「可建立組織之最大數量」（紅軍原文為 8×反共人數、有臺灣再+8），但全 `server/game.py` 沒有任何上限檢查，`Player.total_organizations()` 定義後從未被用於任何限制，玩家可無限建立組織，實體桌遊的資源稀缺機制不存在。
  - 決定：紅軍上限**不採規則書公式**，依使用者 2026-07-11 決定改為**固定 40**（常數 `RED_ARMY_ORG_SUPPLY = 40`）；反共陣營維持規則書的 22（`ANTI_COMMUNIST_ORG_SUPPLY = 22`）。
  - 修正：新增 `_org_supply_limit()`／`_has_org_supply()`；供應檢查放進 `can_develop_in_town()`——它是所有建立路徑（一般建立、安全屋、卡牌/奧援/事件/時代建立、UI 可建立高亮清單）的共同漏斗，一處生效；`build_organization` 另補中文明確錯誤訊息（「組織棋已達上限（N），需先瓦解既有組織」）；移動**共享組織**（他人所有、移動後轉為自己所有＝總數+1）時也消耗供應、滿編時擋下；自有組織移動（淨變化0）與瓦解（釋放供應）不受影響。
  - 驗證：新增 `python3 scripts/validate_org_supply_limits.py`（6/6：反共 21→22 可建、滿 22 擋下且訊息明確；紅軍可超過 22 建到 39→40、滿 40 擋下（證明上限是 40 不是 22）；瓦解後供應釋放可再建；`can_develop_in_town` 在滿編時對所有城鎮回 False（UI 清單同步失效）；滿編時接收共享組織被擋、低於上限可接收；滿編時自有組織移動仍可行）。回歸：`validate_enemy_occupancy_rules.py`、`validate_movement_rules.py`、`validate_setup_cards_shuffled_into_deck.py`、`validate_static_purchase_initial_supply.py`、`validate_red_faction_inspect_reorder.py` 全 PASS。
  - proof：`docs/records/rules-audit/ORG_SUPPLY_LIMITS_VALIDATION_20260711.{json,md}`。
  - 落差盤點報告已同步更新對應項目狀態。

- [done] S2（第二輪盤點）＋B3子句：`新疆社會管控` 距離限制零實作；`組織經驗甲`「牆內距離1格」降級子句一併補上。
  - 資料勘誤：第二輪盤點寫「維吾爾慕尼黑」，實際核對 faction JSON 後 **四個維吾爾變體（伊斯坦堡/慕尼黑/華盛頓/阿拉木圖）全部帶有 `新疆社會管控`**（restriction：「無法無視距離建立牆內組織」），本修正對四個變體全部生效。
  - root cause：全案沒有任何程式碼讀取這個限制；所有無視距離建立路徑（`思想家`、`組織經驗甲`、`東洋奧援`III級、事件 ignore_distance、非互動 fallback）都不會檢查。`組織經驗甲` 卡面明印的「無法無視距離建立牆內組織者，本牌於牆內建立組織距離為1格」降級子句也完全沒有實作（第一輪 B3 已追蹤）。
  - 修正：新增 `_player_is_distance_restricted()`／`_faction_restricts_ignore_distance_build()`（僅對牆內城鎮生效，牆外無視距離建立不受影響），比照既有時代關卡 `restrict_ignore_distance_build` 的攔截點逐一掛上：①`_card_build_town_choices`（思想家/組織經驗甲的選城清單；`組織經驗甲` 的降級子句以資料驅動方式表達——`data/action_cards_structured.v1.1.json` 效果加 `inner_fallback_range: 1`，受限玩家仍可選己方組織1格內的牆內城鎮）；②安全屋/支援建立的距離檢查；③`東洋奧援`III級互動清單——「牆內任意」對受限玩家**降級為「己方組織1格內」**（實作裁定：比照 `組織經驗甲` 卡面明印的降級慣例；若之後規則書確認應完全禁用可再調整）；④非互動 `build_anywhere_inner` fallback。
  - 驗證：新增 `python3 scripts/validate_xinjiang_distance_restriction.py`（4/4：能力正確解析且僅限牆內；思想家對受限玩家完全不提供牆內城鎮、對照陣營（哈薩克）仍可拿到1格外牆內城鎮；組織經驗甲對受限玩家只提供1格內牆內城鎮、遠處牆內被排除、對照陣營不受影響；東洋奧援III級清單對受限玩家與1格內清單完全一致、對照陣營明顯更大）。回歸：`validate_org_supply_limits`、`validate_east_asia_support_taxonomy_fix`、`validate_card_effect_audit_p1`、`validate_enemy_occupancy_rules` 全 PASS（`validate_era_effects_runtime` 為既有 FAIL，stash 比對確認與本次無關，已在 P2 validator hygiene 註記）。
  - proof：`docs/records/rules-audit/XINJIANG_DISTANCE_RESTRICTION_VALIDATION_20260711.{json,md}`。
  - 落差盤點報告已同步更新；`組織經驗甲` 剩餘的「棄4點以上卡牌可重複建立」子句仍待處理（B3）。

- [done] B3 剩餘：`行動預告`／`行動募資` 本回合買多張時沒有頂牌選擇權。
  - root cause：`topdeck_purchased_this_turn` 效果自動挑「最近購買且仍在棄牌堆」的一張置頂，玩家無選擇；但 `buy_card` 不限每回合購買張數，買 2 張以上是合法情境，卡面「將本回合購得的**1張**牌置於牌庫頂」隱含玩家選擇。
  - 修正：0 張候選→記 log 不動作（原行為）；恰 1 張→自動置頂（維持一步完成）；2 張以上→開卡牌選擇（`topdeck_purchased_choice`），卡片剩餘效果（+1 資源）以 `remaining_effects` context 在選擇結算後續跑（比照 `optional_trash` 續跑模式）。**連帶修掉一個實作中發現的隱患**：回合結束的「使用行動預告」提示流程（`end_turn_topdeck_action`）原本執行效果時不看回傳值、直接 `_end_turn()`——若效果開出選擇會留下懸空 pending choice 卡住下一位玩家；已改為效果 pending 時延後結束回合，由頂牌選擇結算負責收尾（先頂牌、後補手牌，順序正確）。
  - 驗證：新增 `python3 scripts/validate_topdeck_purchased_choice.py`（4/4：行動階段買2張時跳選擇、選「先買的」而非舊實作固定的「後買的」證明是真選擇、+1資源在選擇後正確續跑；買1張維持一步自動；買0張 no-op 且資源照給；回合結束流程買2張時選完才結束回合、選中的牌因先頂牌後補手牌而進入新手牌、無懸空選擇）。既有 `validate_action_card_end_turn_topdeck_runtime.py` 為既有 FAIL（「未推進到EVENT」的過期 phase 斷言，stash 比對確認早於本次；其使用情境的卡牌行為檢查全數仍過），已屬 P2 validator hygiene 範圍。
  - proof：`docs/records/action-cards/TOPDECK_PURCHASED_CHOICE_VALIDATION_20260711.{json,md}`。
  - 落差盤點報告已同步更新對應項目狀態。

- [done] B3 收尾＋P1 playtest 項目：`組織經驗甲`「棄4點以上卡牌可重複建立」子句與確認流程。
  - root cause：卡面「每從手上棄掉1張購買費用4點以上的牌，可重複上述動作1次」完全沒有實作（結構化效果只有單一 build 步驟）；playtest 亦回報「應先詢問玩家是否要額外花4點以上卡牌」的確認流程缺失（P1 2026-07-06 項目）。
  - 修正：資料驅動——`data/action_cards_structured.v1.1.json` 效果加 `repeat_on_discard_min_cost: 4`；每次建立結算後，若手上有購買費用合計≥4 的牌**且**仍有合法建立城鎮（含組織棋供應上限、新疆社會管控距離限制），開啟明確的確認選項（「不再建立」／「棄1張再建立1次」）；接受後開卡牌選擇（只列合格卡），棄掉後以同一 effect context 重開建立城鎮選擇（`新疆社會管控` 的牆內1格降級自動沿用），循環直到玩家拒絕或無合格卡/城鎮。拒絕或無合格牌時不自動消耗任何東西。前端零改動（重用通用選項/卡牌/城鎮 modal）。
  - 驗證：新增 `python3 scripts/validate_org_exp_a_repeat_build.py`（5/5：完整「建立→棄牌→再建立」循環且只列合格卡（1點的領導不出現）；拒絕時保留手牌且流程正確結束；無合格卡時不跳詢問；兩張合格卡可連續重複兩次後正確收尾；受限陣營（維吾爾）重複建立清單同樣遵守牆內1格降級）。回歸：`validate_xinjiang_distance_restriction`、`validate_org_supply_limits`、`validate_card_effect_audit_p1` 全 PASS。
  - proof：`docs/records/action-cards/ORG_EXP_A_REPEAT_BUILD_VALIDATION_20260711.{json,md}`。
  - 對應的 P1 playtest 項目（「使用組織經驗甲時，應確認是否還要花其他4點以上卡牌來建立組織」）一併完成，見下方 P1 區塊同步標記。

- [done] B1-c：區域門檻奧援卡 II 級門檻由 AND 改為 OR（2026-07-11 使用者裁決）。
  - 背景：7 張區域門檻奧援卡的 II 級條件在 CSV 各是一組兩個地區；舊實作要求同時主導兩個地區（AND）。經使用者裁決為 OR——主導配對中任一地區即達 II 級。
  - 修正：`server/game.py:_support_card_tier` 的 II 級判定由「全部命中」改為「任一命中」。
  - 驗證：`python3 scripts/validate_east_asia_support_taxonomy_fix.py` 擴充「只主導臺灣」「只主導北國」兩個單一地區案例（6/6 PASS）；`validate_support_card_effects_runtime.py` 12/12 回歸 PASS。
  - 同批裁決記錄（見第二輪盤點報告「使用者裁決記錄」）：S4 附帶「宣傳卡＝宣傳家」關閉、東洋奧援 III 級降級裁定獲追認關閉；S5-2 赤鱲角機場、C1 雙倍分神、A4 共同勝利已有明確語意待實作；S5-1（香港抗爭之烈 vs 香港抗暴之戰＋事件後根據地遷移）仍待確認。

- [done] C1：內鬥供應耗盡時以雙倍分神替代（2026-07-11 使用者裁決 C1=B），並修掉 `離間`/`情報網A` 憑空創造內鬥的供應違規。
  - root cause：`rules.md`「放入分神或內鬥：可將內鬥改為雙倍分神」完全未實作；經裁決語意為**供應替代規則**——僅在內鬥供應耗盡時，每張內鬥以 2 張分神替代（分神也不足時有多少放多少、皆空時記 log 不放置）。實作盤查時另發現 `add_internal_conflict` etype（`離間`、`情報網`選項A）**從不扣除 static supply、憑空創造內鬥**，違反專案的 static supply 原則。
  - 修正：新增中央 helper `_take_internal_conflict_cards(count, reason)`（扣內鬥供應；耗盡時扣分神供應×2 替代），四個放置點全部改走它：政工部 topdeck（含 UI 結果顯示實際放置的牌名）、事件 `_gain_event_card`、`走漏風聲`、`add_internal_conflict` etype（連帶補上供應扣除）。
  - 驗證：新增 `python3 scripts/validate_double_distraction_substitution.py`（5/5：正常取牌、替代取牌、部分替代與雙空 log、離間扣供應＋中途耗盡混合替代（內鬥+分神×2）、事件與走漏風聲替代）。同步把 `validate_red_army_faction_abilities.py` 的「供應空→不放」舊斷言改為「供應空→替代放2張分神」＋新增「雙空→不放」案例（全 PASS）；`validate_red_army_special_rules`、`validate_leak_card`、`validate_cost_composition_triggers` 回歸 PASS。
  - proof：`docs/records/rules-audit/DOUBLE_DISTRACTION_SUBSTITUTION_VALIDATION_20260711.{json,md}`、更新後的 `docs/records/event-cards/RED_ARMY_FACTION_ABILITIES_RUNTIME_VALIDATION.{json,md}`。

- [done] A4：共同勝利實作（2026-07-11 使用者裁決語意）。
  - 裁決語意：「在有反共陣營玩家獲得勝利之際，其他反共陣營玩家若已達到所屬陣營勝利條件的 2/3 以上（含），視為共同勝利者。」紅軍獲勝（含第20回合保底）不產生共同勝利者，紅軍也永不為共同勝利者。
  - root cause：舊 `victory.py` 把「2/3」誤實作成「達成條件**數量**的 2/3」——在每陣營只有 1 條條件的現況下永遠等同「達成唯一條件」，真正的共同勝利語意完全不存在。
  - 修正：`victory.py` 新增 `condition_progress()`（達成數量/需求數量，跨條件取最大；`count_and_required` 以組織數比例衡量、必含城鎮不另計——簡化，之後可再調整）與 `co_winners()`；舊「條件數 2/3」公式改為標準的「達成任一條件即獲勝」；`game._check_victory` 勝利時計算並記錄 `co_winners`（含 log），state 增加 `co_winners` 欄位。**注意**：目前僅對 15 個結構化條件陣營有效，46 個 text-only 陣營要等 A1 完成後自動涵蓋；勝利/共同勝利的 UI 顯示屬既有 P1「第20回合勝利宣告」項目的範圍，屆時一併處理。
  - 驗證：新增 `python3 scripts/validate_co_winners.py`（4/4：10/14≈71% 達標為共同勝利者且 state 有曝露、9/14≈64% 不達標、紅軍保底獲勝無共同勝利者、紅軍永不為共同勝利者）。回歸：`validate_org_supply_limits`、`validate_enemy_occupancy_rules`、`validate_red_army_special_rules` PASS。
  - proof：`docs/records/rules-audit/CO_WINNERS_VALIDATION_20260711.{json,md}`。

- [done] S5-2：赤鱲角機場規則實作（2026-07-11 使用者裁決語意）。
  - 裁決語意：「香港可花費 2 次遷移，將位於赤鱲角的香港組織無視距離遷移到任何屬於香港發展空間的牆外城鎮。不可逆向操作。」
  - 實作：`move_organization` 新增 airport 分支——僅限香港陣營移動**自己的**組織、起點為赤臘角（地圖對「赤鱲角」的拼寫）、終點為牆外且屬香港發展空間；花費 2 移動點；不建立反向通道（牆外→赤臘角仍走一般連線規則）；目的地敵方佔領封鎖等既有檢查照常適用；赤臘角原有的道路/鐵路鄰接移動維持 1 點。前端可移動城鎮高亮尚未涵蓋機場航線，歸入 P1 移動 UI 批次一併處理。
  - 驗證：新增 `python3 scripts/validate_chek_lap_kok_airport.py`（7/7：跨洋移動成功且花費2點、移動點不足擋下、反向擋下、非香港陣營（粵）擋下、發展空間外（曼谷）擋下、鄰接移動仍1點、敵佔目的地擋下）。回歸：`validate_movement_rules`、`validate_enemy_occupancy_rules`、`validate_org_supply_limits` PASS。
  - proof：`docs/records/rules-audit/CHEK_LAP_KOK_AIRPORT_VALIDATION_20260711.{json,md}`。
  - S5 剩餘：已於同日由使用者裁決並實作完成，見下一條。

- [done] S5-1：香港根據地遷移兩條特殊規則實作（2026-07-11 使用者裁決）。
  - 裁決：「香港抗爭之烈」＝事件卡**香港抗暴之戰**。兩條規則：①該事件發生並完成結算後（成功或失敗皆算）、進入下一回合之前，香港可**免費**將根據地遷移至臺北/倫敦/卡加利/多倫多（亦可選擇不遷）；②不論事件是否發生，香港隨時（自己的行動階段）可用赤鱲角機場**花費 2 次遷移**把根據地遷到上述四城。
  - 實作：`relocate_hong_kong_base(player_id, to_town)` 新方法＋WS action `relocate_base`；事件結算時開啟免費窗口旗標 `hk_free_base_relocation`（state 有曝露）、新回合事件階段開始時自動關閉；目的地限四個 relocatable 根據地城市、敵佔封鎖；根據地錨定組織隨遷、新根據地的在地能力（如倫敦=國際線）動態生效、錨定不可移動規則在新址延續。**前端 UI（遷移按鈕/免費窗口提示）尚未做**，歸入 P1 UI 批次。
  - 驗證：新增 `python3 scripts/validate_hk_base_relocation.py`（5/5：失敗結算也開窗口且免費遷移不耗移動點、窗口隨新回合關閉、機場路徑花2點且1點被擋、四城限制/敵佔/非己回合/非香港全部擋下、錨定組織與根據地能力隨遷）。回歸：`validate_chek_lap_kok_airport`、`validate_movement_rules`、`validate_event_deck_draw_twenty`、`validate_co_winners` PASS。
  - proof：`docs/records/rules-audit/HK_BASE_RELOCATION_VALIDATION_20260711.{json,md}`。

- [done] 資料修正：刪除 `dian_zhuang`（滇（壯））重複陣營條目（2026-07-11 使用者裁決 B）。
  - 背景：A1 前置確認時發現 `dian_zhuang` 與 `zhuang`（壯）根據地清單、能力完全相同，僅名稱與分組不同、且勝利條件是佔位文字「待補」——判定為建資料時「壯」同時被收進地域類與少數民族兩份清單造成的重複條目；使用者裁決刪除。
  - 修正：自 `data/factions/all_faction.integrated.v2.json` 移除該條目（61→60 個陣營）；`static/app.js` 兩處民族祭儀陣營集合同步移除 `dian_zhuang`。歷史來源檔 `data/factions/rebel_authoritative_rebuilt.v1.json` 保留原樣（未被程式載入，僅作原始紀錄）。A1 的資料轉換自此無阻塞（45 個 text-only 陣營待補結構化勝利條件）。
  - 驗證：Game 正常啟動（60 陣營）；`validate_faction_action_guess_result`、`validate_minyun_gender_revolution_nonviolent`、`validate_co_winners` PASS（`validate_ethnic_ritual_ui_and_engine` 的 FAIL 為需要啟動中伺服器的瀏覽器測試、環境性，引擎部分已另行驗證通過）。

- [done] A1：45 個 text-only 陣營的勝利條件結構化並接入勝利判定（第一輪盤點最大項收尾）。
  - root cause：45 個地域/政治類反賊陣營只有自由文字 `win_condition_text`，全案沒有任何程式讀取，這些陣營永遠無法透過自身條件獲勝（僅剩紅軍第20回合保底）。
  - 資料轉換：`scripts/migrate_win_conditions.py` 一次性轉換（保留在 repo 供重跑/稽核）——45/45 轉換成功：9 個 `count_only`（牆內≥14）、34 個 `count_and_required`（含 `republican` 的牆內 scope 變體；全部必含城鎮已驗證存在於地圖）、2 個特殊案例（`wan`：自訂 `宛地` scope＝主地圖南陽＋未來宛地圖城鎮，附 note；`chaoxian`：新增 `required_any_of` schema 表達「平壤**或**首爾」）。一般形式全部通過**往返檢查**（由結構化資料重建原句逐字比對），零失真；原 `win_condition_text` 保留供對照。
  - 程式擴充：`victory.py` 的 `count_and_required` 支援 `required_any_of`（每組至少一城有組織）；`_count_scope` 新增 `宛地` scope（目前計南陽，宛地圖建模後擴充）。A4 共同勝利進度計算自動涵蓋這些陣營。
  - 驗證：新增 `python3 scripts/validate_text_faction_win_conditions.py`（7/7：60 陣營全有結構化條件；牆內14 的 13→不勝/14→勝；牆外組織不計入牆內 scope；粵的必含城鎮缺一即擋、齊備即勝；朝鮮平壤/首爾兩分支皆勝、皆無則否；宛地外的組織不計入、南陽14勝；text-only 陣營現在也能當共同勝利者）。回歸：`validate_co_winners`、`validate_org_supply_limits`、`validate_hk_base_relocation`、`validate_lobby_family_faction_details`、`validate_minyun_gender_revolution_nonviolent` PASS。
  - proof：`docs/records/rules-audit/TEXT_FACTION_WIN_CONDITIONS_VALIDATION_20260711.{json,md}`。
  - **至此兩輪規則盤點的全部項目（A1-A4、B1、B3、S1-S7、C1-C2 裁決範圍）完成或關閉**；剩餘為第四梯隊保養項（C3 購買區校驗、S6 無限行動、死代碼 JSON 清理、3 支過期驗證腳本）與 P1 UI 批次。
  - 2026-07-15 進度更新：P1 UI 批次（10/10）與 P2 過期驗證腳本（5/5，含挖出並修復事件延後結算真 bug，見 P1 區塊頂部條目）已全部完成；第四梯隊已完成 C3 與死代碼清理（見下兩條），僅剩 C2（歲月靜好難度選項）與 S6（無限行動）待規則書原文。

- [done] C3：購買區組成資料校驗腳本（第四梯隊保養）。
  - 定位：資料一致性校驗＋現行組成行為鎖定；規則書步驟⑧的偏差列**資訊性報告**（不列失敗，避免把刻意的 MVP 選項永久紅牌）。
  - 硬性檢查（8/8 全過）：常設供應量與 CSV 一致（宣傳家/思想家/資助者/資本家 15、分神 30、內鬥 20）；常設區恰為 6 種固定卡；起始牌（追隨者/樂捐者）僅存在 CSV、不進牌庫；structured JSON 卡名恰為 CSV 非起始卡集合；support taxonomy 卡名與 support CSV 一致；`sample_53` 牌庫＝18 奧援＋35 一般卡且無常設/起始/紅軍奧援；`all_cards`＝全 pool。
  - 資訊性偏差報告（記錄於 proof，供之後裁決）：①規則書步驟⑧＝間諜/組織/整肅**全部** 47 張＋隨機 18 奧援＋隨機 35 其它＝100 張，兩種 market_mode 都不是此組成（`sample_53` 為 lobby「53 張核心」刻意 MVP 選項）；②`action_cards_structured.v1.1.json` **沒有張數欄位**，`_initial_purchase_deck` 對每種一般卡 fallback 為 1 份，CSV 張數（批判 8、派遣間諜 5…）不影響牌庫份數；③support CSV 每種奧援兩列各 4 張（合計 8）vs taxonomy 每種 4 張，兩列是「同卡雙資料行」或「各自成卡」待規則書確認；④牌庫用盡的補充實作為重建整份 initial deck（規則書為「從剩餘行動卡任取一疊」，近似）。
  - 驗證 `python3 scripts/validate_purchase_area_composition.py`（8/8）；proof `docs/records/purchase/PURCHASE_AREA_COMPOSITION_VALIDATION.{json,md}`。
  - 2026-07-16/17 後續：偏差 ③（奧援卡張數）與偏差 ②（一般卡張數）已依使用者裁決先後修正並改為硬性檢查——③每種奧援實為兩種印刷變體各 4 張合計 8（見 P1 區塊奧援卡變體條目）；②`action_cards_structured.v1.1.json` 補上 `copies` 欄位（來源 CSV 卡牌張數），`_initial_purchase_deck` 依實體張數展開一般卡池（38 種共 181 張），`sample_53` 的隨機 35 張改為從實體卡池抽出（同名卡可重複，等同實際洗牌），`all_cards` 為完整 64 奧援＋181 一般＝245 張。校驗腳本升至 10/10（新增 `support_taxonomy_copies_match_csv_row_totals`、`structured_general_copies_match_csv` 兩項硬性檢查）。剩餘偏差：①market_mode 組成、④牌庫補充方式。
  - 2026-07-17 連帶修正：`validate_turn_phase_action_gating.py` 用固定 random seed，購買牌庫變大改變了 RNG 消耗順序、換掉開局抽到的事件，剛好抽到大災難（失敗結算開待選擇）擋住 advance 導致 2 項失敗。該段測試本意只驗回合/階段推進形狀，與事件內容無關，改為固定把該輪事件換成無效果的歲月靜好，讓斷言與「事件運氣」脫鉤（13/13，連跑 3 次穩定）。

- [done] 死代碼 JSON 宣告清理：`凝聚共識` conditional_bonus／`武裝集團` conditional_draw（第四梯隊保養）。
  - root cause（第一輪盤點記錄）：兩張卡的 JSON effect 在 pending-choice 步驟後各宣告了一個條件步驟，但兩個 resolve 路徑（`discard_self`、`armed_target_discard`）都**不續跑 remaining_effects**——凝聚共識加成實際走 choice 上的 `grant_propaganda_if_all_non_starter` 旗標、武裝集團抽牌走 `draw_on_success`——JSON 宣告永遠不會執行、只會誤導維護者。
  - 修正：刪除兩段死宣告（凝聚共識 effect 剩 `draw`+`discard_self`；武裝集團剩 `force_discard`）。刪除前後以行為快照證明完全一致（凝聚共識棄 2 非起始→+2 宣傳一次；武裝集團成功迫棄→發動者抽 1）。`conditional_draw`/`conditional_bonus` handler 保留（`點燃熱情` 等其他卡仍使用 conditional_draw）。
  - 驗證 `python3 scripts/validate_dead_effect_cleanup.py`（3/3：兩卡行為鎖定＋JSON 無死宣告）；structured-JSON 相關回歸（event_cards_runtime、purchase composition、離間、誘導虛耗、模仿戰術）全綠。proof `docs/records/action-cards/DEAD_EFFECT_CLEANUP_VALIDATION.{json,md}`。

### 已有完整紀錄的其他模組
- [done] 情報網 target choice map highlight。
  - 提交：`c690f5b fix: highlight intel network dissolve targets on map`。
- [done] 多張行動卡/指令卡 UI 與 runtime regression：`網羅人才`、`地下黨`、`擴大戰果`、`乘勝追擊`、`行動預告`、`行動募資`、武裝系列、`合作談判`、`走漏風聲`、間諜系列、`企業人脈`、`企畫遊說`、`模仿戰術`、`誘導虛耗`、`批判`、`批鬥`。
- [done] pending-choice / modal / UI 系統層：multi-card choice、card choice completion guard、option/town/target/reaction/modal 基礎流程。
- [done] 奧援/支援卡多數 runtime/UI 驗證：英美、歐洲、南洋、印度、東洋、北國、臺灣、天方、紅軍奧援。

## note（不是 active todo）
- 事件卡目前應以「MVP 可 playtest」理解；若 playtest 先於完整化，也可以直接測目前版本，再把發現寫回 P0/P1。
- `search_files` 在此 repo 曾對檔名列舉回傳 0；盤點檔案時可用 Python `Path.rglob()` 交叉確認。
