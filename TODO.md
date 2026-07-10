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

- [todo] Playtest UI polish：任何移動選擇／移動後可達城鎮高亮都不應畫大量放射狀直線。
  - 2026-07-04 回報情境：使用 `宣傳家` 後，在 `石家莊` 建立組織；地圖顯示所有可到達城鎮與 `石家莊` 的連線，造成大量放射狀線條。
  - 2026-07-09 補充：這個項目不只適用於 `宣傳家`；只要進入需要移動或顯示可移動城鎮的流程，都應套用同一視覺規則。
  - 期望：只顯示「可以到達的位置」標記/高亮，以及地圖原本就有的鐵路和道路；不要額外畫出從目前城鎮連到所有可達位置的直線。
  - 需檢查：`static/leaflet_game_map_logic.js` 的 movement/build highlight layer 是否把 reachable targets 以 temporary route lines 全部連回 selected town；所有移動來源（卡牌效果、建立組織後移動、一般組織遷移、事件/能力造成的移動）都應保留既有 road/rail layer，移除或限制放射狀可達連線。
  - 回報截圖：`/Users/benmini/.hermes/image_cache/img_4830826f26cd.jpg`。

- [todo] Playtest UI polish：奧援卡卡面需提供各等級詳情入口，並把原本「資源」按鈕改成「詳情」。
  - 2026-07-04 回報想法：奧援卡每一等級的細節仍應能從卡牌上看到；若因字數太多不適合全部放在卡面，可在卡牌上做一個「詳情」按鈕。
  - 2026-07-04 補充：奧援卡其實只能作為行動使用，才可能透過行動效果產生資源；不應保留一般卡牌的「資源」按鈕。
  - 期望：卡牌本體維持簡潔，但提供可點擊的詳情入口，讓玩家查看 I / II / III 級完整效果文字與條件。
  - 期望：把奧援卡原本的「資源」按鈕直接改成「詳情」；按下去顯示卡牌詳情，不執行資源使用。
  - 需檢查：`static/app.js` 支援卡/奧援卡 render、手牌 action/resource button gating、`/card-presentation` 或 support card presentation catalog 是否已有完整 `effect_text` 可供 modal/detail panel 顯示；若資料不足需回查 `data/raw/support_cards.csv`。

- [todo] Playtest UI polish：地圖已建立組織的城鎮／根據地應直接顯示所屬陣營。
  - 2026-07-04 回報想法：已建立組織的根據地和城鎮，應該在地名後面直接顯示是哪個陣營，避免只靠側欄或點選狀態辨識。
  - 期望：例如地名標籤可顯示 `臺北 1（f）`、`臺北 1（臺灣）` 或其他清楚的陣營文字；實際格式待 UI 設計時統一。
  - 期望：城鎮圓圈內的填色也可以使用該陣營代表色，讓地圖一眼看出各城鎮／根據地歸屬。
  - 需檢查：`static/leaflet_game_map_logic.js` 的 city marker/label render 是否可取得 organization owner/faction；同步確認 base marker 與一般城鎮 marker 樣式一致。
  - 回報截圖：`/Users/benmini/.hermes/image_cache/img_e4a4c7db0c4d.jpg`。

- [todo] Playtest UI polish：大量棄牌選擇／展示區需要可捲動。
  - 2026-07-04 回報情境：觸發 `貿易戰加劇` 的成功條件時，因棄牌數量太多，畫面只看得到一部分棄牌。
  - 期望：棄牌卡牌區應提供 scrollbar/slider，可滑動查看所有卡牌，避免卡牌超出視窗或被遮住。
  - 需檢查：事件成功條件結算時的 discard selection/display modal 或 panel；可能在 `static/app.js` 的事件結果／棄牌 UI render，或相關 CSS overflow 設定。

- [todo] Playtest UI/flow bug：紅軍能力「紀委」視窗關閉不應視為動作結束。
  - 2026-07-04 回報情境：紅軍選擇紅軍能力中的 `紀委` 時，如果使用者關閉能力視窗，目前流程似乎不能重新選能力／或被視為已結束選擇。
  - 期望：關閉視窗只代表取消／返回，不代表紅軍能力動作已完成；使用者應可重新選擇能力，或再次打開能力選擇視窗。
  - 需檢查：紅軍能力 selection modal 的 close/cancel handler 是否誤呼叫 end action / resolve ability；特別檢查 `紀委` 分支與其他紅軍能力是否一致。

- [todo] Playtest rule/flow bug：回合結束抽牌應補到 5 張，不應清空手牌後抽 5 張。
  - 2026-07-04 回報規則：每回合最後是抽牌補足到五張牌；如果玩家手上還有手牌，不可以把既有手牌清掉再抽五張。
  - 期望：回合結束／refill hand 時，保留玩家手上的牌；若手牌數少於 5，才從牌庫抽到 5 張；若已經 5 張或更多，則不抽。
  - 需檢查：end turn / discard-refill 流程是否在所有情境都先 discard hand；特別注意事件成功/失敗結算後、紅軍回合、pending choice 完成後的 refill 是否共用同一函式。

- [todo] Playtest rule/flow bug：臺灣綠線 `本土社團` 觸發後應在回合結束手牌補滿流程之外額外多抽 1 張，不能最後仍只有 5 張。
  - 2026-07-06 回報情境：第 9 回合玩家 `f` 為台灣綠線，已在 `昆明` 透過 `思想家` 建立組織；log 顯示 `[Turn 9] f triggered 本土社團 and drew 1 card`，但該回合最後仍只讓玩家抽到 5 張卡。
  - 回報 log：`[Turn 9] End of turn for f`; `[Turn 9] f triggered 本土社團 and drew 1 card`; `[Turn 9] f bought 宣傳家`; `[Turn 9] f built organization in 昆明 via 思想家`; `[Turn 9] f played 思想家`; `[Turn 9] f played 擴大戰果`; `[Turn 9] Event drawn: 歲月靜好 (no-op)`。
  - 期望：依 `本土社團`，若本回合曾在牆內建立組織，行動階段結束時應額外抽 1 張；若一般結束流程是補到 5 張，能力觸發後的結果應可達 6 張（或至少不能被後續補牌/棄牌流程覆蓋回 5 張）。
  - 需檢查：`Game.end_turn()` / refill hand 順序、`on_build_draw_inner` / `本土社團` 觸發點、`turn_log['built_towns']`、行動階段結束與購買/END 階段的抽牌時機是否一致；確認 UI 顯示的手牌數與後端實際手牌一致。

- [todo] Playtest UI/flow polish：移動到可移動城鎮前應跳出確認視窗。
  - 2026-07-05 回報情境：進行組織移動時，玩家點到可移動城鎮後，目前可能直接執行移動，容易誤點。
  - 2026-07-09 補充：當玩家先選定某一組織，接著點選可移動的城鎮時，系統應先出現選項詢問是否要移動到該城鎮。
  - 期望：使用者點到可移動城鎮時，先跳出視窗確認是否要移動到該城鎮；確認後才送出移動，取消則保留在移動選擇狀態。
  - 需檢查：`static/leaflet_game_map_logic.js` / `static/app.js` 的 movement highlight click handler、sidebar move action、WebSocket `move` action 送出點；需避免影響事件/卡牌 pending choice 的選點流程。

- [todo] Playtest rule/flow bug：移動路線需同時檢查翻牆成本與城鎮適用陣營。
  - 2026-07-05 回報情境：玩家剛剛從 `東沙` 移動到 `觀塘`，看起來好像只花 1 次移動。
  - 2026-07-05 補充：當時玩家陣營是 `台灣綠線`，理應不能從 `東沙` 移動到 `觀塘`；移動路線視覺化與功能都應注意該城鎮／路線的適用陣營。
  - 期望：依 `rules.md`「組織遷移」規則，牆外 ↔ 牆內屬於翻牆，需花費 2 次移動，且僅移動 1 格；若路線或目的城鎮不適用目前陣營，前端不應高亮為可移動，後端也應拒絕移動。
  - 需檢查：`Game.move_organization()` / route cost 計算 / map route metadata 是否正確判斷 `東沙` 到 `觀塘` 為翻牆與台灣綠線不可用路線；同時檢查前端可移動城鎮高亮、路線視覺化與剩餘移動點顯示是否使用相同 faction-aware cost/eligibility。

- [todo] Playtest UI polish：顯示目前還有幾個城鎮可以建立組織。
  - 2026-07-05 回報想法：玩家應能直接看到目前還有幾個城鎮可以建立，避免只能靠地圖高亮逐一判斷。
  - 期望：在建立組織相關 UI 中顯示可建立城鎮數量；若受陣營適用城鎮、牆內/牆外、敵方佔領、事件/卡牌限制影響，數字應跟實際可點擊/可建立名單一致。
  - 需檢查：`static/leaflet_game_map_logic.js` 建立高亮資料、`static/app.js` sidebar/action prompt 顯示、後端 build eligibility/state projection 是否能提供一致的可建立城鎮 count。

- [todo] Playtest card rule bug：`誘導虛耗` 只能移除剛打出的 `誘導虛耗` 本身，不能移除其他卡牌。
  - 2026-07-05 回報情境：使用 `誘導虛耗` 後，UI 顯示「你可以移除剛打出的這張牌，或移除 1 張手牌」，並列出手牌中的 `天方奧援`、`內鬥`、`追隨者`、`樂捐者` 等可移除選項。
  - 期望：依卡牌規則，`誘導虛耗` 的可移除對象應只限於剛打出的 `誘導虛耗` 這張牌；不應允許移除其他手牌，也不應在選擇視窗列出其他手牌作為可移除選項。
  - 需檢查：`誘導虛耗` action effect 的 optional trash / pending choice 建立邏輯、`pending_choice.cards` 來源、`static/app.js` 的 card-choice modal 呈現；確認 runtime 後端也拒絕移除非 `誘導虛耗` 的卡。
  - 回報截圖：`/Users/benmini/.hermes/image_cache/img_fe2d5d612086.jpg`。

- [todo] Playtest card ownership bug：非紅軍陣營打出 `紅軍奧援` 後，卡牌應回到紅軍棄牌堆。
  - 2026-07-06 回報情境：非紅軍陣營打出 `紅軍奧援` 後，此卡沒有回到紅軍的棄牌堆。
  - 期望：`紅軍奧援` 屬於紅軍專屬卡；即使因借用／取得／特殊流程由非紅軍玩家打出，結算後也應回到紅軍玩家的棄牌堆，而不是留在非紅軍玩家棄牌堆、消失、或進入錯誤區域。
  - 需檢查：`play_card()` / played-card discard destination、紅軍奧援 ownership/original owner metadata、借用卡牌規則、`_make_support_card('紅軍奧援')` 或起始牌庫歸屬、UI 棄牌堆投影是否使用實際 card owner 而非 acting player。

- [todo] Playtest card/flow bug：使用 `模仿戰術` 後沒有跳出可使用卡牌的選擇。
  - 2026-07-06 回報情境：玩家使用 `模仿戰術` 後，似乎沒有跳出可讓玩家選擇／使用的卡牌清單。
  - 期望：打出 `模仿戰術` 後，若依規則應可選擇某些可模仿／可使用的卡牌，UI 應顯示對應選擇視窗或明確提示沒有合法目標；不能沒有回饋或讓玩家以為流程卡住。
  - 需檢查：`模仿戰術` card effect 定義、pending choice 建立邏輯、可模仿卡牌來源與合法性篩選、`static/app.js` choice/card modal render，以及無合法目標時的 log/提示與 phase gating。

- [todo] Playtest card rule bug：紅軍使用 `離間` 時，`內鬥` 應只放到對方牌堆，不應放到紅軍自己的牌堆。
  - 2026-07-06 回報情境：紅軍使用 `離間` 後，效果似乎把 `內鬥` 放到了紅軍自己的牌堆。
  - 期望：`離間` 應只將 `內鬥` 放到指定對方／目標玩家的牌堆；紅軍自己不應成為此效果的放置目標。
  - 需檢查：`離間` card effect 定義、target player selection、`add_internal_conflict` / static supply 消耗、紅軍作為 actor 時的 target/recipient 判定，以及 UI/log 是否正確顯示內鬥進入哪位玩家牌堆。

- [todo] Playtest card/flow polish：使用 `組織經驗甲` 時，應確認是否還要花其他 4 點以上卡牌來建立組織。
  - 2026-07-06 回報情境：玩家使用 `組織經驗甲` 時，目前流程似乎沒有先詢問玩家是否要額外花其他 4 點以上的卡牌來建立組織。
  - 期望：`組織經驗甲` 若提供「可再花其他 4 點以上卡牌建立組織」的選項，UI 應跳出確認／選卡流程；玩家可選擇不做，不能直接跳過或自動執行。
  - 需檢查：`組織經驗甲` card effect 定義、4 點以上卡牌判定是否使用總購買成本、optional build pending choice / card-choice modal、取消/不使用時是否正確繼續流程。

- [todo] Playtest card rule bug：`點燃熱情` 在本回合曾打出宣傳費用卡牌時應抽 2 張，但實際只拿到 1 張。
  - 2026-07-06 回報情境：Turn 19 使用 `點燃熱情`，且該回合曾經打出過有宣傳費用的卡牌；log 顯示 `[Turn 19] f played 點燃熱情`、`[Turn 19] f chose 點燃熱情 via 地下黨`，但最終只有拿到 1 張卡牌。
  - 期望：若本回合曾打出有宣傳費用的卡牌，`點燃熱情` 應多抽 1 張，也就是總共抽 2 張；透過 `地下黨` 選擇／取得後使用時也應套用同一條件。
  - 需檢查：`點燃熱情` card effect 條件判定、turn log/旗標是否正確記錄「本回合曾打出有宣傳費用的卡牌」、`地下黨` 觸發或選牌後是否保留/套用 acting card context，以及抽牌數與 UI 手牌顯示是否一致。

- [todo] Playtest card/flow bug：紅軍使用 `北國奧援` 觸發先瓦解己方組織、再瓦解敵方組織時，關閉/離開視窗後無法繼續瓦解。
  - 2026-07-06 回報情境：紅軍使用 `北國奧援`，觸發「可以瓦解自己組織，再瓦解敵方組織」的流程；按了離開或關閉後，就無法再瓦解組織，畫面無法動彈，即使按 `瓦解目前城鎮組織` 也無法完成。
  - 期望：關閉/離開選擇視窗不應清除或破壞後續 target pending choice；玩家應可回到地圖繼續選擇合法己方/敵方組織並完成兩步瓦解，或可明確取消整個效果且不卡住階段。
  - 需檢查：`北國奧援` support tier effect 的兩段式 dissolve pending choice、choice modal close handler、map highlight preservation、`瓦解目前城鎮組織` sidebar action、pending_choice state machine，以及與先前 `情報網` 關閉後仍可地圖瓦解修正是否可共用同一 target-choice close behavior。

- [todo] Playtest victory/flow bug：到第 20 回合時沒有直接宣告勝利者。
  - 2026-07-06 回報情境：遊戲看起來已到第 20 回合，但系統沒有直接宣告勝利者是誰。
  - 期望：依 `rules.md` 勝利條件，第 20 回合結束前無人勝利則紅軍勝利；到達應結算時點時，UI/後端應明確進入 finished 狀態並宣告勝利者，不應讓遊戲繼續停在未結算狀態。
  - 需檢查：`VictoryChecker` / `Game.end_turn()` / round-turn advancement、Turn 20 結束階段判定時機、事件獎懲與勝利判定順序、`winner` state projection、UI 勝利提示/finished modal，以及是否 off-by-one（第 20 回合開始 vs 第 20 回合結束）。

- [todo] Playtest UI polish：Lobby 房間代碼複製功能保留一個即可，移除最上方重複複製入口。
  - 2026-07-09 回報情境：Lobby 畫面同時在最上方房間代碼橫幅與下方「建立 / 加入房間代碼」輸入列各有一個 `複製` 按鈕，功能重複。
  - 期望：複製功能保留一個就好；最上面的房間代碼橫幅複製入口可以移除，避免 UI 重複與視覺干擾。
  - 需檢查：`static/index.html` lobby room banner / room-code input row、`static/app.js` 的 `copyRoomId()` 綁定與 lobby room banner 顯示邏輯；確認移除上方入口後仍能從保留的複製按鈕成功複製房間代碼。
  - 回報截圖：`/Users/benmini/.hermes/image_cache/img_3c6a990786b4.jpg`。

- [todo] 下一步建議：開 LAN 桌測／端到端 playtest，記錄實際遊戲中出現的 UI polish 或規則落差，再回寫成具體 P0/P1 項目。
  - 目前事件／時代 scope 已可 playtest；不要再以 speculative implementation 延伸 P0，除非 playtest 或規則文本指出具體 bug。
  - 事件面板 polish 待 playtest 後再決定是否需要展開/收合、詳細文字、或事件歷史紀錄。
  - 目前面板位置：右上紅框區，`.event-card-panel` 為 `width: 300px; height: 200px; max-height: 200px; top: 0; right: 24px`。
  - 現有 proof：`docs/records/event-cards/EVENT_CARD_LAYOUT_REDFRAME_300X200_PROOF_2026_05_23.md` 與同名截圖。

### P2：repo hygiene / validator hygiene
- [todo] 維持 root record-like count = 0。
  - 新增 validation reports、proof markdown、screenshots 時，直接放到 `docs/records/<topic>/`。
  - 若新增 validator，確認輸出路徑不是 repo root，且失敗時 exit non-zero。

- [todo] `scripts/validate_event_cards_runtime.py` 已長期失效（stale），需更新至現行事件生命週期後恢復可跑。
  - 2026-07-11 發現：`test_hong_kong_success_static_supply` 起穩定失敗；用 git worktree 往回跑 20+ 個 commit（含 `8191639` 之前）全部 FAIL，證明壞掉已久、沒有人在跑。
  - root cause：2026-05-31 事件卡生命週期改為「任務條件達成先 `success_pending`，等全體玩家 ACTION 結束才結算」（TODO 已記錄的刻意設計），但腳本裡的 `settle_round_event()` helper 還停留在舊設計（`advance_turn_phase()` 一次就期待 `settled=True`）；單人 advance 後實際狀態是 `success_pending`＋輪到下一位玩家，不是結算完成。屬於驗證腳本過期，不是 runtime bug。
  - 需修：把 `settle_round_event()` 改成推進到整輪結束（所有玩家含紅軍完成 ACTION）再斷言 `settled`；逐一檢查該檔 20+ 個 test 是否還有其他依賴舊生命週期的斷言。修好前，該腳本的 FAIL 不應被當成 regression 訊號（例如 S3 修正時已另建 `validate_event_deck_draw_twenty.py` 獨立驗證）。

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

### 已有完整紀錄的其他模組
- [done] 情報網 target choice map highlight。
  - 提交：`c690f5b fix: highlight intel network dissolve targets on map`。
- [done] 多張行動卡/指令卡 UI 與 runtime regression：`網羅人才`、`地下黨`、`擴大戰果`、`乘勝追擊`、`行動預告`、`行動募資`、武裝系列、`合作談判`、`走漏風聲`、間諜系列、`企業人脈`、`企畫遊說`、`模仿戰術`、`誘導虛耗`、`批判`、`批鬥`。
- [done] pending-choice / modal / UI 系統層：multi-card choice、card choice completion guard、option/town/target/reaction/modal 基礎流程。
- [done] 奧援/支援卡多數 runtime/UI 驗證：英美、歐洲、南洋、印度、東洋、北國、臺灣、天方、紅軍奧援。

## note（不是 active todo）
- 事件卡目前應以「MVP 可 playtest」理解；若 playtest 先於完整化，也可以直接測目前版本，再把發現寫回 P0/P1。
- `search_files` 在此 repo 曾對檔名列舉回傳 0；盤點檔案時可用 Python `Path.rglob()` 交叉確認。
