# Redline TODO

最後更新：2026-08-01

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

### P1：使用者回報牌庫感覺越來越少——已完成徹底稽核
- [done] 使用者貼出實際對局 action log（dfa 玩家，回合10→12），觀察到 Turn 11 結束牌庫用盡、棄牌堆僅7張重洗，緊接著 Turn 12 又用盡、棄牌堆僅剩4張重洗；懷疑與『網羅人才』有關，且提到「上一次也觀察到類似現象」，要求本輪深入調查（2026-08-04 使用者回報並要求深入調查，非僅記錄）。
  - **已完成的徹底稽核**：逐一排查 `_execute_support_card()` 與東洋奧援/臺灣奧援的建立流程（`interactive_build_anywhere_inner`/`interactive_build_near_inner`/`interactive_dissolve_and_build`）——只呼叫 `_place_organization`，不碰 `player.hand`/`player.deck`，無洩漏；所有 `draw_pile =`/`discard_pile =` 重新賦值（非 `.remove()`，共11處）全部只存在於 `setup_test_card_scenario`（`game.py:4283`，掛在 `/test/setup-card-scenario` debug endpoint，正常遊戲流程不會呼叫到）；`recruit_talent` 候選清單 (`effect_engine.py` 的 `cards = list(player.deck.draw_pile)`) 確認是真正的淺拷貝，不會被其他地方的操作牽連修改；`Deck._reshuffle()` 完整搬移棄牌堆進牌庫，不篩選不遺失；`draw_to_five()`/`discard_hand()` 也都無過濾；另外逐一追過 `trash_from_hand_or_discard`、`optional_trash`、`armed_target_discard`、`org_exp_repeat_discard`、`draw_then_discard_choice`、`bait_exhaustion_target_discard`、`red_army_ccdi_discard_draw`、`discard_self`、`guess_ability_bottom_card`、`topdeck_purchased_choice`、`event_topdeck_from_discard`、`era_inspect_deck_top_and_reorder` 等所有「從自己牌庫/棄牌堆/手牌選1張」的 `card_choice`/`multi_card_choice`，全部都是1:1對應，沒有第二個「銷毀未選中候選」的同類型 bug。
  - **結論**：本輪徹底稽核沒有找到本次會話已修的『網羅人才』銷毀牌庫 bug（commit `d40bed4`，即上方「紅軍使用網羅人才時有時只顯示棄牌堆」項目）以外的任何額外卡牌洩漏路徑。使用者貼的 log 高度吻合舊 bug 的行為模式（回合11→12密集用了2次網羅人才、2次臺灣奧援瓦解補位），很可能是在該修正**之前**打的。建議使用者用目前版本重測幾回合；如果還發生，請回報「手牌+牌庫+棄牌堆總張數」而非只看牌庫剩幾張（牌庫/棄牌堆本來就會正常來回循環，只看其中一堆的張數容易誤判是流失）。
  - **順帶發現（不在本輪修，列入待查）**：`build_organization`/`build_organization_with_support`/`dissolve_organization`/`relocate_hong_kong_base`/`move_organization` 這5個函式完全沒有 `pending_choice` 守門檢查，與 `play_card()`/`advance_turn_phase()` 不一致——理論上能在開著選擇視窗（例如網羅人才候選還沒選完）時插入這些動作。逐行確認過這5個函式都只動 `organizations`/`moves_left`/`resources`，不碰 `hand`/`deck`，所以**不會**造成卡牌流失，只是既有架構不一致，值得之後補上同樣的守門判斷。

### P1：抽牌類效果的紀錄應該寫出實際抽到哪些牌（含紅軍奧援）
- [done] 使用者需求：抽牌類卡牌效果的 action log 應該寫出「因為使用了什麼卡牌，抽中了哪些卡牌」，而不是只有「抽了1張牌」這種不具名的紀錄，方便之後直接從 log 診斷牌庫相關回報（2026-08-04 使用者提出）。
  - 實作：`server/game.py` 的 `_draw_player_cards()` 新增 `trigger_name` 參數，抽到牌時一律記一行「{player} 因{trigger_name/來源}抽到：{卡名...}」；紅軍奧援（`play_card()` 特判區塊）、`_execute_support_card()` 的 `red_support_draw_and_pass`/`draw`/`draw_then_discard`、商貿組織／民族調和／星星之火等陣營能力都已傳入具體的觸發卡名/能力名稱。`server/effect_engine.py` 的 `_draw()` 同步新增 `game`/`card_name` 選填參數並補上同樣格式的 log，涵蓋一般行動卡的 `draw`/`conditional_draw`/`shared_draw` 效果型別（例如樹立信心、領導這類最常見的抽牌卡）。時代效果（`source='era'`）沒有具體卡名時，退回「因時代關卡效果抽到」的通用說法；其餘未特別傳入觸發名稱的呼叫點仍會記「抽到：{卡名}」，至少卡名本身一律可見。
  - 新增 `test_red_army_aid_draw_is_logged_with_the_specific_card_name`／`test_standard_draw_effect_card_logs_the_specific_drawn_card_name`（`scripts/tests/test_action_card_regressions.py`），分別驗證紅軍奧援特判路徑與一般 `effect_engine.py` 的 `draw` 效果路徑都會記錄具體抽到的卡名。完整 pytest 239/241（2個既有無關 FakePage API drift 失敗），確認沒有既有測試斷言舊的「抽了N張牌」無具名格式而被打壞。

### P1：紅軍以外玩家組織建立後可遷移至任意城鎮
- [todo] 使用者回報：紅軍以外的玩家，組織建立完成後，似乎可以遷移到任意城鎮，不受道路／鐵路相鄰關係限制。（2026-08-04 使用者回報，先記錄，尚未調查）

### P2：玩家在軍火庫城鎮擁有組織可減免武裝類卡牌購買費用
- [todo] 使用者回報規則：玩家在軍火庫城鎮每擁有1個組織，該陣營購買每張武裝類卡牌所需支付的費用減少1點資金（至多可藉軍火庫減少3點資金）。（2026-08-04 使用者回報，先記錄，尚未確認現有實作是否已涵蓋此規則）

### P1：宣布勝利時機應該等整輪（含紅軍）都行動完才公布
- [todo] 使用者提出：宣布勝利也應該要等這一輪所有玩家（包含紅軍）都行動完才公布，因為紅軍有可能在同一輪稍後行動，把其他玩家的組織瓦解掉，改變原本的勝負結果。（2026-08-03 使用者提出，先記錄，尚未稽核）
  - 初步檢查：`_check_victory()` 呼叫點在 `_end_turn()` 約5147行（每位玩家自己回合結束就檢查，一但判定就直接 `return`、不再推進 `current_player_index`／補牌，等同立刻中止整輪剩餘玩家的行動）與約5194行（第20回合保底判定，本來就在整輪wrap的區塊內）。紅軍座位由 `_assign_factions()` 隨機洗牌決定、不保證排在整輪最後（`random.shuffle`），所以確實存在「非紅玩家一回合結束就判定勝利、紅軍當輪還沒行動」的情況，與使用者描述的疑慮相符。
  - **2026-08-04 使用者裁決**：與上方『時代關卡觸發時機』一起評估後暫緩不動——原因與風險同上（牽動20幾條已個別稽核過的勝利條件，且不確定 canonical 規則書是否規定整輪結束才判定），維持現狀記錄待之後深入稽核。

### P1：事件卡『北京政爭』用網羅人才選到樹立信心應算任務成功；另網羅人才選完似乎沒有立即洗牌
- [todo] 使用者playtest回報兩點，先記錄，尚未稽核：(1) 事件卡『北京政爭』，使用網羅人才、選到樹立信心，應該要算成功達成任務才對。(2) 同一回合內第二次使用網羅人才時，可選的候選卡牌只有一張——代表第一次使用網羅人才時，並沒有馬上直接把牌庫洗牌（卡面：「...而後將牌庫洗牌」）。（2026-08-03 使用者回報）
  - **(2) 已釐清，非bug**：`_resolve_card_choice()` 的 `recruit_talent` 分支在選完後會立刻同步呼叫 `random.shuffle(player.deck.draw_pile)`，沒有任何延遲；`Deck._reshuffle()` 也是立即、完整地把棄牌堆搬進牌庫，不篩選、不遺失。同一回合第二次候選只剩1張，最可能只是牌庫在那個當下本來就只剩很少張（小牌庫循環的正常現象），不是洗牌沒生效。
  - **(1) 仍是待修的真缺口，但比原本想的更大**：稽核 `_track_event_progress()` 發現，`'draw'` 這個事件觸發類型目前**只有** `_draw_player_cards()`（`server/game.py:518`，紅軍奧援／各奧援卡／時代效果等呼叫的抽牌路徑）會呼叫 `_track_event_progress('draw', ...)`；一般透過 `effect_engine.py` 的 `draw`/`conditional_draw`/`shared_draw` 效果型別（也就是絕大多數一般行動卡的抽牌，例如樹立信心、領導、點燃熱情）都走 `effect_engine.py` 自己的 `_draw()`，完全沒有呼叫 `_track_event_progress`。也就是說：**不管是直接打出樹立信心，還是透過網羅人才把樹立信心加入手牌，目前都不會讓『北京政爭』這類 `trigger:{"type":"draw"}` 的事件任務推進**——網羅人才只是剛好也不算數的其中一種途徑，不是唯一漏掉的。全部門檢查過 `data/events_structured.v1.1.json`，只有『北京政爭』與2張『全國人大召開』（副本）用到 `draw` 型別（後兩張是拿來當 success 條件，trigger 是另一種），影響範圍不大。
  - **本輪決策（2026-08-04）**：使用者要求先不修這項，只記錄調查發現；不在這輪動 `_track_event_progress`/`effect_engine.py` 的抽牌事件追蹤邏輯。之後要修的話，方向是讓 `effect_engine.py` 的 `_draw()`（連同 `game.py:_draw_player_cards()`）都統一呼叫 `_track_event_progress('draw', ...)`，並重跑涉及『北京政爭』／『全國人大召開』的既有 event regression 確認沒有讓這兩張的判定變得太容易觸發。

### P1：時代關卡觸發時機應該等整輪（含紅軍）都行動完才判定
- [done] 使用者提出：時代關卡的觸發判定不應該在某位玩家自己回合一開始就檢查，而應該要等這一輪所有陣營（包含紅軍）都輪完該回合的行動後才算數——因為紅軍在同一輪稍後可能還會有行動（例如瓦解組織），可能讓原本符合的條件在紅軍行動後不再成立，若太早判定觸發就可能誤判。（2026-08-03 使用者提出，先記錄，尚未深入稽核）
  - 初步檢查：`_check_era_trigger()`（`server/game.py:6207`）目前在 `advance_turn_phase()` 的 `TurnPhase.EVENT` 分支（約行 5094，也就是每位玩家自己回合開始、進入行動階段之前）與 `_end_turn()` 尾聲（約行 5186）都會呼叫，屬於「每個玩家自己回合開始/結束時各檢查一次」的逐回合判定，不是等整輪（所有玩家皆行動完）才判定一次。
  - 值得注意的既有先例：事件卡的「任務結算」已經有類似的整輪延後機制（`_is_final_non_red_turn_before_round_wrap()`／`_should_defer_event_settlement_until_after_refill()`），會特意延後到「這一輪最後一位非紅軍玩家結算完」才處理，正是為了避免在紅軍行動之前就提早判定。時代關卡觸發目前似乎沒有套用類似的延後邏輯。
  - 待確認：(1) 這是否真的是canonical規則書規定的時機（「整輪結束才判定」），或只是使用者對「感覺應該公平一點」的直覺；(2) 若要修，是否所有時代關卡都要延後到整輪結束，還是只有「紅軍行動可能影響判定結果」的那些關卡（例如牆內組織數、與紅軍相關的勝負條件）才需要；(3) 延後判定與現有「一次性啟動」佇列（`_pending_era_activations`／`_continue_era_activation_queue()`）如何共存，避免同一輪內因為延後而漏判或重複判定；(4) 需要找到或建立可以重現「紅軍行動改變結果」情境的 regression（例如某玩家回合一開始就達成關卡條件，接著紅軍瓦解掉關鍵組織，驗證關卡不應該仍判定為已達成）。
  - **2026-08-04 使用者裁決**：連同下面『宣布勝利時機』一起評估過風險後，暫緩不動。`_check_era_trigger()` 同時驅動 `_continue_era_activation_queue()`（已在跑的互動式時代啟動流程，不能整批延後、否則會卡住既有 pending choice 鏈），`_check_victory()` 牽動全陣營20幾條已個別稽核過的勝利條件（見下方「P1：全陣營時代關卡與勝利條件scope稽核」106項`[done]`）。這是本輪調查裡影響範圍最大、風險最高的一項，貿然把判定時機整套搬到整輪結束有牽一髮動全身的風險，且不確定 canonical 規則書是否真的規定「整輪結束才判定」——維持現狀，待之後另外找時間深入稽核（可能需要先去對照 canonical 規則書原文，或採用「只延後新觸發的偵測、不影響既有佇列續跑」的局部方案）。
  - **2026-08-04 實作（採用上方裁決提到的『只延後偵測、不影響佇列續跑』局部方案；本次只動時代觸發，勝利判定時機仍不碰）**：
    - 根因：`_check_era_trigger()`（`server/game.py`）把兩件事綁在一起——(1)「觸發偵測」：掃 `structured_eras`、以 `_evaluate_era_trigger()` 判定新達標的時代並 append 進 `_pending_era_activations`；(2)「佇列續跑」：`_continue_era_activation_queue()` 逐一啟動已入列的時代、遇到互動式 pending choice 就暫停、下次再續。原本這個合體函式在 `advance_turn_phase()` 的 `TurnPhase.EVENT` 分支（每位玩家自己回合開始）與 `_end_turn()` 尾聲（`current_player_index` 推進之前、每位玩家自己回合結束）各呼叫一次，屬逐回合偵測；只要某位非紅玩家自己回合的當下快照符合條件就會判定達標，即使紅軍當輪稍後才行動、可能把撐住條件的組織瓦解掉。
    - 修法：把「偵測」與「續跑」拆開。新增 `_detect_era_triggers()`（`server/game.py`）只做掃描 append，不啟動；`_check_era_trigger()` 保留為「偵測＋續跑」的合體入口，僅供 `/test/*` 情境設定端點與 era validators／tests（`server/main.py:933`／`:998`、`scripts/validate_era_*`、`scripts/tests/test_era_*`）強制立即檢查用，正常對局流程不再逐回合呼叫它。兩處對局呼叫點改為只呼叫 `_continue_era_activation_queue()`（`advance_turn_phase()` 每位玩家回合開始、`_end_turn()` 每位玩家回合結束都照跑，確保已入列的互動式時代啟動不會被卡住）；偵測改為只在 `_end_turn()` 整輪 wrap 區塊（`if self.current_player_index == round_start_player_index:`，該點是整輪最後一位玩家回合結束、`current_player_index` 剛好繞回起點的當下，代表含紅軍在內每位玩家本輪都已行動）呼叫 `_detect_era_triggers()` 後再 `_continue_era_activation_queue()`。紅軍座位由 `_assign_factions()` 隨機洗牌決定，但 wrap 判定本身與座位順序無關、由構造保證正確；偵測仍排在 `era_engine.tick()` 之後，避免同一邊界新啟動的持續時間被立刻消耗。**沒有為「不涉及紅軍的時代」特例保留逐回合觸發**——依使用者需求採全面整輪邊界判定。
    - 為何必須拆偵測／續跑：若把整個 `_check_era_trigger()` 一律延後到 wrap，會讓已入列、正等玩家解 pending choice 的互動式時代啟動鏈（例如 tibet／manchuria 的紅軍棄牌換建立）在非 wrap 回合停止續跑、既有 pending choice 永遠推不動。續跑必須每回合／每次解 choice 都照跑，只有「偵測」該延後。
    - 新增回歸（`scripts/tests/test_era_lifecycle.py`）：`test_era_detection_deferred_to_round_wrap_so_red_army_can_still_invalidate_it`（非紅玩家自己回合已達 7 個牆內組織，但整輪 wrap 前紅軍瓦解掉 1 個使其掉回 6，斷言時代整輪結束後仍不啟動）、`test_era_activates_at_round_wrap_when_condition_survives_red_army_turn`（同條件在紅軍行動後仍成立，斷言時代在整輪 wrap 邊界才啟動、非紅玩家自己回合中途不啟動）、`test_queued_interactive_era_keeps_draining_without_a_new_round_wrap`（預先把互動式時代塞進 `_pending_era_activations`，在非 wrap 回合驗證續跑仍會啟動它並跨多個動作解完 pending choice，不需再等下一次整輪 wrap）。另修正兩支原本把逐回合舊時機當預期的既有測試 `test_timed_era_is_not_consumed_on_activation_boundary_or_reactivated_after_expiry`／`test_expired_one_time_era_is_achieved_but_not_active_in_viewer_public_state`：改為讓紅軍（整輪最後一位）回合結束觸發整輪 wrap 才啟動時代（只更正過時的時機預期，未削弱其對「持續時間不被啟動邊界消耗／到期後不再啟動」的實質覆蓋）。同理修正 `server/main.py` 的 `/test/setup-era-notification-proof?via_lifecycle` 端點：改從紅軍座位推進整輪 wrap 才啟動時代，否則 `validate_my_era_stage_view` 的 lifecycle 佐證會因為只走非紅玩家自己回合而抓不到啟動。
    - 驗證：era 相關 focused 全綠——`test_era_lifecycle.py` 11/11（含新增3支）、`test_era_trigger.py`、`validate_era_rules` 5/5、`validate_era_effects_runtime` 15/15、`validate_era_canonical_scope` 8/8；瀏覽器佐證 `validate_my_era_stage_view` 9/9、`validate_dissolve_map_first_interaction` 9/9。完整 pytest 242 passed／2 failed（僅既有無關 FakePage API drift：`test_advance_to_action_waits_for_my_turn_and_advances_until_action_phase`、`test_wait_for_confirmed_faction_and_ready_state_use_latest_lobby_state`；baseline 239→242 恰為新增3支測試），其餘既有時代／勝利相關測試零回歸。勝利判定時機（`_check_victory()`，見上方『宣布勝利時機』項）本輪依範圍限制完全未動。

### P1：連續使用建立組織效果時，後續建立候選城鎮沒有反映玩家移動後的位置
- [todo] 使用者playtest回報：先打出`宣傳家`（效果含 `build range:1` 與 `move count:1`）與`組織經驗丙`（效果含 `build range:1`），到地圖頁面後先在桃園建立第一個組織，接著移動到彰化，再要建立第二個組織時，預期候選城鎮應該考慮彰化附近（因為已經移動過去），但實際看到的候選仍是臺北附近的城鎮。（2026-08-03 使用者回報，先記錄，尚未深入稽核／未重現）
  - 初步分析（未完整驗證）：`_card_build_town_choices()`（`server/game.py`）計算候選城鎮的依據是呼叫當下 `_organization_towns_for_player(player)` 的即時結果，理論上不是寫死城鎮；但當多張牌各自的 `build` 效果被合併進同一個連續建立佇列（`_queued_card_build_choices`／`_activate_next_queued_card_build`）時，第二張卡的候選清單似乎是在「上一次建立解決的當下」就計算好並固定下來，而不是等到玩家真正要解決這一次建立時才重新即時投影；若玩家在兩次建立之間額外做了移動，這次移動不會反映到已經算好、等待解決的候選清單裡。需要確認：(1) 候選清單究竟是在佇列批次「啟動」當下算一次、還是在每次真正呈現給玩家時都重新算；(2) 這兩張卡的建立額度是否真的合併進同一個 `card_build_organization` session（而非各自獨立的 `support_interaction` 之類）；(3) 用 `/test/setup-build-queue-proof` 或類似 fixture 重現「建立→移動→建立」序列，直接比對第二次候選清單是否含彰化鄰近城鎮。
  - 後續需要：先寫一支重現腳本（打兩張牌進入連續建立、解決第一次建立、呼叫正常移動 API 把組織移到遠處、再檢查第二次候選清單的城鎮組成），確認是否真的過期；若確認，修法方向是讓候選城鎮清單在「即將呈現給玩家解決」的那一刻才重新投影，而不是在佇列批次啟動當下就固定。

### P1：`臺灣奧援`瓦解紅軍根據地後應該可以直接補上自己的組織（待確認是否為既有規則限制）
- [done] 使用者playtest回報：臺灣陣營在天津有組織（與北京相鄰），且在臺灣地區擁有最多組織（研判可達成較高級別），認為理應可以用`臺灣奧援`瓦解北京的組織並建立自己的組織。（2026-08-03 使用者回報，先記錄，尚未確認是否為bug）
  - 初步檢查：`_can_replace_dissolved_org_with_own()`（`server/game.py:2701`）明確擋下「目標玩家是紅軍、且目標城鎮就是該玩家的根據地」這個組合——瓦解紅軍根據地本身是允許的（沿用既有 2 次命中才移除的耐久規則），但「瓦解＋直接補上自己的組織」這個 `interactive_dissolve_and_build`（臺灣奧援 III 級效果）明確排除紅軍根據地城鎮。天津—北京確實相鄰（rail），距離不是問題；卡在的是這條紅軍根據地保護規則。
  - **2026-08-04 使用者裁決：放寬限制，允許補位**。移除 `_can_replace_dissolved_org_with_own()` 裡「目標玩家是紅軍且目標城鎮是其根據地」的排除條件，讓紅軍根據地與紅軍其他組織城鎮走同一套判斷。既有「2次命中才真正移除」的耐久規則完全不受影響——這個函式只是「預先篩選要不要把這個目標顯示成候選」用的模擬，真正的把關在 `_resolve_support_interaction_result()` 呼叫 `dissolve_organization()` 之後對 `_can_player_build_in_town()` 的即時複查（`game.py` 約3013-3015行）：如果這次只是根據地的第1次命中、組織其實還在，那個即時複查會正確擋下建立，不受這次放寬影響。
  - 新增 `test_taiwan_support_tier3_can_replace_red_army_base_after_second_dissolve_hit`（模擬本回合已經先對根據地命中1次，這次臺灣奧援瓦解是第2次命中，正確移除根據地組織後補上自己的組織）與 `test_taiwan_support_tier3_cannot_replace_red_army_base_on_first_dissolve_hit`（驗證只中1次時，即使候選階段放行，真正解決時仍會被即時複查正確擋下，耐久規則不受影響）。`scripts/tests/test_action_card_regressions.py` 全數106項通過；`scripts/validate_base_dissolve_browser.py`（涵蓋非紅軍根據地保護、紅軍根據地2次命中等既有案例）9/9 通過；完整 pytest 239/241（2個既有無關 FakePage API drift 失敗）。

### P1：`紅軍奧援`不論哪一方打出，應該都要能抽1張牌
- [done] 使用者提出疑問：`紅軍奧援`（起始牌，卡面「提供資源：1資金+1宣傳。卡牌效果：抽1張牌。若您為紅軍，打出後將本牌放進任一反共陣營玩家棄牌堆；若您為反共陣營玩家，打出後將本牌放進紅軍棄牌堆。」）不管是紅軍還是反共陣營玩家打出，都應該可以抽到那 1 張牌才對；懷疑目前實作可能有一方（或某種取得/打出方式）漏抽。（2026-08-03 使用者提出，先記錄，尚未深入稽核）
  - 初步快速檢查（未完整稽核，僅供下一次接手起點）：`server/game.py` 的 `play_card()` 對卡名字面等於「紅軍奧援」、`mode=="action"` 有獨立的特判區塊（約行 4816 起），會呼叫 `self._draw_player_cards(player, 1)`，且判斷式沒有限定陣營——用 `red_army` 與 `liberals` 兩種陣營各跑一次最小重現腳本，兩者在 `mode='action'` 下都確實抽到了牌，尚未直接重現使用者觀察到的漏抽。
  - 已知這個特判區塊會在 `effective_type == 'support'` 的一般奧援卡通用派送（`_execute_support_card()`，內有另一份 `red_support_draw_and_pass` 效果邏輯，行約 3171）之前就 `return`，導致「紅軍奧援」實際上永遠不會走到通用奧援卡派送——`_execute_support_card()` 裡的那份 `red_support_draw_and_pass` 目前疑似死代碼，需確認是否真的有任何呼叫路徑（例如經由企業人脈/模仿戰術借用、或紅軍在 EVENT 階段的 prep-action 特殊時機 `is_red_support_prep_action`）會繞過 `play_card()` 的特判、改走 `_execute_support_card()`，而該路徑是否也正確抽牌。
  - **2026-08-04 深入稽核結論：沒有程式錯誤，行為已經對稱**。逐一追過 `mode='action'`（特判區塊，任何陣營都抽）、`mode='resource'`（support卡在資源模式本來就不觸發卡牌效果，這是所有支援卡的共同規則，不是紅軍奧援獨有）、EVENT階段紅軍 prep-action（`is_red_support_prep_action` 只放寬 phase 檢查，實際執行仍走同一個特判區塊）、模仿戰術借用（借來的牌一樣透過同一個 `play_card()` mode='action' 路徑打出）——所有實際可達的路徑都會正確抽牌，紅軍與反共陣營玩家沒有差異。`_execute_support_card()` 裡的 `red_support_draw_and_pass` 確認是死代碼（唯一呼叫點在 `effective_type=='support'` 分支，但紅軍奧援的特判永遠先 `return`，不可能落到那裡）——先保留不清，之後想清理再處理，不影響正確性。
  - **本輪動作**：只釐清結論，不改任何程式碼。
  - 後續需要：(1) 確認使用者實際觀察到漏抽的具體情境（哪個陣營、用什麼方式取得/打出這張卡、mode='action' 還是 'resource'、是否透過反應/借用/模仿等間接管道）；(2) 稽核 `mode='resource'` 分支是否也該抽牌（卡面「卡牌效果：抽1張牌」比對規則書判斷是否只在打出「效果」而非「資源」時才抽）；(3) 確認 `_execute_support_card()` 裡的 `red_support_draw_and_pass` 是否為死代碼，若是則整併或刪除避免維護混淆；(4) 補齊涵蓋紅軍／各反共陣營、直接打出／借用／模仿取得、action／resource 兩種 mode 的 regression。

### P1：紅軍使用`網羅人才`時有時只顯示棄牌堆，漏掉己方牌庫
- [done] canonical卡面規則為：一般玩家從己方牌庫任選1張加入手牌；若為紅軍，則應在效果結算當下同時看到己方牌庫與己方棄牌堆中的所有可選卡牌，並從兩區聯集任選1張。playtest發現紅軍有時只能看到棄牌堆，牌庫中的卡牌未出現在候選。後續需稽核 `choose_from_own_deck`的candidate generation、牌庫／棄牌堆zone metadata、抽牌堆洗牌／重建時機及viewer-scoped projection；涵蓋牌庫與棄牌堆皆有牌、其中一區為空、重名卡、選中後從正確來源移除、其餘牌庫洗牌、非紅軍不得看到棄牌候選，以及正式WebSocket UI選單同時呈現兩區完整卡牌。（2026-08-02 playtest回報）
  - 根因（比候選投影嚴重得多）：`server/game.py` 的 `_resolve_card_choice()` 在 `choice_key == 'recruit_talent'` 分支裡，有一段從實作第一天（2026-05-11 commit `695872e`）就存在的迴圈——`for card in list(source_cards): if card is chosen_card: continue; ... player.deck.draw_pile.remove(card); ... player.deck.discard_pile.remove(card)`——把候選清單裡「除了被選中那張以外」的每一張牌都從牌庫／棄牌堆直接刪除。卡面規則其實是「任選 1 張加入手牌，而後將牌庫洗牌」，沒被選中的候選牌應該原地保留，只是牌庫最後會被洗牌；這段迴圈等同每次使用網羅人才就銷毀玩家整副牌庫（只留被選中的那 1 張）。playtest 回報的「紅軍再次使用時只顯示棄牌堆」正是這個副作用：上一次使用就已經把牌庫清空了，第二次自然只剩之後累積的棄牌堆有候選，不是候選投影或畫面顯示的問題。連既有測試 `test_red_army_recruit_talent_can_select_from_own_deck_or_discard` 都把這個被刪除的錯誤行為當成預期結果寫進斷言（`'DeckChoiceA' not in names(p.deck.draw_pile)`），從一開始就沒被抓到。
  - 修法：整段刪除迴圈，只保留「把被選中的那張從其所在區域移除、加入手牌」的邏輯（原本就在迴圈後面，邏輯本身正確，只是被前面那段迴圈連帶波及）；`server/effect_engine.py` 的 `choose_from_own_deck` 也一併移除了現在已無用的 `source_cards` 參數傳遞。
  - 測試修正：改寫了把錯誤行為當預期的 `test_red_army_recruit_talent_can_select_from_own_deck_or_discard`（改斷言沒被選中的候選牌留在牌庫）與 `test_recruit_talent_selects_any_card_from_own_deck_not_topdeck_only`（補上牌庫其餘候選牌仍在的斷言，原本完全沒檢查這點）；新增 `test_recruit_talent_does_not_destroy_the_rest_of_the_deck_it_only_moves_the_chosen_card`（直接比對修正前後牌庫總量）與 `test_red_army_recruit_talent_still_shows_deck_candidates_on_a_second_use`（直接重現 playtest 描述的症狀：連續使用兩張網羅人才，第二次候選仍要看得到牌庫剩下的牌）。四支全過；完整 pytest 235/237（2 個既有無關 FakePage API drift 失敗）。
  - 未做：沒有另外建立正式 WebSocket UI 瀏覽器 proof——這是純後端資料邏輯錯誤（銷毀牌庫資料本身），不涉及任何畫面渲染或候選投影程式碼，既有 4 支後端 regression（含直接重現症狀的跨次使用測試）已足以證明修正；若之後仍想要正式 UI 截圖佐證，可用 `/test/setup-card-scenario` 搭配紅軍陣營與網羅人才手牌另外補建。

### P2：連續建立組織時保留地圖鏡頭，不在每次建立後zoom out
- [done] 玩家累積多張可建立組織的卡牌並在戰略地圖連續建立時，每成功建立一個組織後應暫時保留使用者當下的Leaflet `center`與`zoom`，只更新組織marker、合法候選與剩餘建立數，不要重新 `fitBounds`、reset view或zoom out；因為下一個目標很可能就在相鄰城鎮。後續需區分「首次進入建立流程可自動定位」與「同一pending build queue內後續重繪必須保留viewport」，並涵蓋候選重算、相鄰／遠距下一目標、最後一次建立、iframe重新render、桌面／行動版及正式Leaflet UI proof。（2026-08-02 playtest建議）
  - 根因：`static/leaflet_game_map_logic.js` 的 `applySupportChoiceHighlight()` 用 `supportChoiceHighlightKey()` 算出的 key 是否改變來決定要不要重新 `fitBounds`／`setView`。原本這把 key 包含 `towns`／`prompt`（甚至一度包含 `sourceName`）；但同一個連續建立 session 內，伺服器每次成功建立後都會重新投影候選城鎮、把 `prompt` 改成「尚可建立 N 個」——實測進一步發現，玩家疊加打出多張不同建立卡（如先組織經驗丙、再組織經驗乙）時，伺服器會把兩者的建立額度合併進同一個連續 session，但目前作用中的那一批額度用完、換下一批接手時 `source_name` 會從第一張牌換成第二張牌（仍是同一個 session、同一個 `choiceKey`）。這些欄位只要被算進 key，每次成功建立都會被誤判成「新的 session」而重新搶鏡頭。
  - 修法：`supportChoiceHighlightKey()` 只保留 `mode`／`actionKind`／`choiceKey` 三個在整個連續 session 內保證不變的欄位；`towns`／`prompt`／`sourceName`／`focusTown` 全部排除。session 真正結束時 payload 會變成 `null`（`applyGameStateToMap()` 偵測到 `pending_choice.choice_key` 不在 `INITIAL_VIEW_MAP_CHOICE_KEYS` 時清空 highlight），下一個 session 開始時 key 自然與 `null` 不同、正確重新聚焦一次；同一 session 內後續每次重繪只更新 marker／候選／剩餘數，鏡頭原地不動。此 key 同時驅動瓦解流程的地圖高亮，因此連續多目標瓦解（北國奧援 III 級等）現在也一併受惠，不會在每輪之間重新搶鏡頭。
  - 新增 `scripts/validate_build_queue_preserves_map_viewport.py`（5/5）：用 `/test/setup-build-queue-proof` 疊加組織經驗丙＋組織經驗乙進入 3 次連續建立的 session，先確認進入 session 時自動聚焦一次，接著手動把鏡頭平移到與候選完全無關的座標（模擬玩家自行調整視角），再依序完成 3 次建立（透過與正式地圖點擊建立候選 marker 相同的 `selectTownForCurrentMapAction(town, {autoFocus:false})` 路徑，而非既有 `validate_build_entitlement_queue_browser.py` 為了測試方便使用的 `{autoFocus:true}`），斷言三次建立過程中鏡頭全程維持在玩家手動設定的位置，不會被沖回自動聚焦時的位置。
  - 回歸：`validate_build_entitlement_queue_browser.py`／`validate_action_card_build_choices_runtime.py`／`validate_org_exp_a_repeat_build.py`／`validate_belt_road_red_turn_build_gating.py`／`validate_dissolve_map_first_interaction.py`／`validate_beiguo_two_stage_dissolve.py`／`validate_intel_network_map_close_browser.py`／`validate_base_dissolve_browser.py` 全數重跑通過（`validate_action_card_build_choices_browser.py` 有一個與本次改動無關、在改動前的 baseline 上也會重現的既有 flake：隨機事件卡的放大檢視圖片短暫攔截點擊，Playwright 自動重試後仍可能逾時，屬既有環境問題，未列入本次回歸範圍）。

### P1：全陣營時代關卡與勝利條件scope稽核
- [done] 使用者指出牆內scope問題不應只檢查臺灣後，已逐條對照8張canonical時代卡、60個runtime陣營勝利條件與正式WebSocket/UI。發現香港、蒙古、藏國、維吾爾、滿洲5張時代卡的structured trigger未正規化為 `region: china`；其中蒙古／藏國／滿洲會實際漏觸發牆內達標，香港／維吾爾則只是靠region alias碰巧等價。現已將7張count-only牆內時代（香港10、蒙古4、藏國7、維吾爾7、滿洲10、反賊4、臺灣7）全部正規化為同一canonical helper，哈薩克保留北國7＋牆內3；不改各卡觸發後的效果地區。勝利條件方面修正紅軍臺灣14特殊勝利缺少「場上有臺灣玩家」gate，並讓所有勝利scope每城最多計1個有效組織，非法同城疊放不再灌高進度；牆內、牆內外、必須城鎮、required_any_of、共享組織、共同勝利與13/14邊界均已涵蓋。宛的全宛地14仍因宛擴充地圖未建模而保持fail-closed，只將南陽計為1個有效城鎮，不虛構可達成。新增全時代16項、全勝利27項matrix；focused 61/61、完整可收集pytest 228 passed、canonical era trigger 8/8、text faction victory 7/7、shared victory 3/3、正式Chromium/WebSocket跨陣營proof 31/31且console 0。證據位於 `docs/records/rules-audit/canonical-scopes/`。（2026-08-02 完成）

### P2：建模宛擴充地圖，使宛的全宛地14個有效組織勝利條件可達成
- [todo] `all_faction.integrated.v2.json`的宛勝利條件為「主地圖南陽＋宛擴充地圖城鎮共14個有效組織」，但目前正式地圖尚未包含宛擴充城鎮。runtime現採fail-closed：全圖其他組織不計、南陽每城最多只計1，非法將14個組織疊在南陽也不會勝利。後續必須先取得／確認宛地圖canonical城鎮、道路／鐵路、統治者、發展限制與視覺拓撲，再加入正式Leaflet及勝利scope；不得以暫時把全圖組織或南陽疊放當作替代。（2026-08-02 全勝利條件稽核）

### P1：臺灣時代關卡牆內組織判定與玩家戰況拆分
- [done] 已確認root cause是canonical卡面寫「臺灣在牆內擁有至少7個有效組織」，但 `era_structured.v1.1.json`誤編成 `region: taiwan`；現已修正為 `region: china`。牆內SSOT為canonical `map.json`城鎮 `ruler`清單包含`紅軍`，與組織擁有者陣營及Leaflet runtime「當前控制者」無關。新增 `_is_inside_wall_town()`與 `_player_organization_scope_counts()`共用helper：時代／勝利條件以含合法共享組織的有效視角計數，玩家戰況則拆分實際擁有組織並投影 `organization_counts`，正式UI顯示 `組織總數`及`牆內 X／牆外 Y`，且X＋Y恆等於總數。新增臺灣地區8個不達成、牆內6／7邊界、任意陣營擁有者、共享有效組織、state總數守恆共6項focused matrix；focused＋era lifecycle 14/14、map相鄰16/16、完整可收集pytest 185 passed、era規則5/5、效果runtime15/15、canonical scope 0 failures、正式Chromium/WebSocket UI proof 11/11且console 0。證據位於 `docs/records/era-cards/inside-wall-counts/`，原playtest截圖保留於同級era-cards records。（2026-08-02 完成）

### P1：`產業滲透`首次取消後，後續回合似乎不再發動
- [done] 更正playtest重現：目前觀察到的是 `產業滲透`第一次成功取消對手的卡牌能力後，到了下一回合，對手再次使用卡牌能力時似乎不會再出現取消詢問；尚不能據此斷定同一回合內只有第一次可取消。後續需先依canonical卡面確認效果持續期限，再稽核首次取消時是否錯誤永久消耗／移除了reaction entitlement，而不是只結束當次反應；建立跨回合「首次取消→下一回合再次出牌」為主的regression，並另外確認當次選擇不取消、同回合連續出牌、資源模式、不同玩家、效果正確到期與正式WebSocket UI反應流程。（2026-08-02 playtest更正）
  - **修正（推翻本項前一版錯誤結論）**：先前在此項下記錄「稽核後未發現程式缺陷，現象成因是卡片被消耗」——這個結論錯了，且遺漏了使用者事後明確澄清的規則：只要 `情報網`／`爆料黑幕`／`產業滲透` 還在手上，對手「每一次」符合取消條件的行動都應該跳出取消詢問，不是「這回合已經問過這個人一次，之後同一回合就不再問」。舊行為（`reaction_prompted_player_ids`，2026-05-17 commit `2aa6b0d` "prompt cancel reactions on first action" 引入）才是真正的程式缺陷——它把「同一回合只問一次」誤當成卡面規則。
  - 修正內容（`server/game.py`）：完全移除 `reaction_prompted_player_ids`（`_new_turn_log()`／`_reaction_prompt_candidates()`／`_set_pending_reaction_choice()` 三處）；`_reaction_prompt_candidates()` 不再排除「這回合已問過」的玩家，每次出牌都重新從頭計算合法候選。同時修正一個連帶發現、原本就存在的相關缺陷：3 人以上對局中，若持有反應卡的第一位候選人選擇不取消，該次出牌會直接結算，其餘同樣持有反應卡的候選人永遠沒有機會反應——`_set_pending_reaction_choice()`／`_resolve_reaction_choice()` 新增 `remaining_candidates` 鏈：選擇「不取消」（index 0）時，若還有其他候選人，改為對下一位候選人重新建立 `pending_choice`（同一次出牌繼續問下去），直到所有候選人都放棄才真正讓行動結算；只有選擇「取消」才會讓整個反應鏈立即結束（行動已死，沒有再問下去的意義）。既有 `schedule_reaction_timeout`（`server/main.py`，10 秒逾時自動視為不取消）不需改動，逾時仍呼叫 `resolve_pending_choice(reacting_player_id, 0)`，會自然沿著新的鏈往下一位候選人推進。
  - 測試修正：`scripts/tests/test_action_card_regressions.py` 原有 `test_first_other_player_action_prompts_cancel_reaction_once_with_all_available_cards` 斷言「同一回合第二張牌不再跳出詢問」——這其實是把錯誤行為寫進了測試，已重寫為 `test_every_other_player_action_prompts_cancel_reaction_while_reactor_holds_eligible_cards`（斷言第二張牌一樣會重新詢問，且能再次成功取消）；新增 `test_reaction_candidate_who_declines_lets_the_next_eligible_reactor_react_to_the_same_card`（3 人局，驗證第一位候選人放棄後第二位候選人接著被問）；`test_reaction_prompted_player_ids_only_suppresses_within_the_same_turn_not_forever`（上一輪治標分析時新增，前提已被推翻）改寫為 `test_reaction_prompt_no_longer_throttled_by_any_per_turn_bookkeeping`，直接斷言 `turn_log` 不再有這個欄位、同一回合連續兩次出牌各自完整觸發詢問。上一輪新增的兩支跨回合 regression（`test_產業滲透_reaction_prompt_reappears_on_a_later_turn_after_being_used`／`test_爆料黑幕_reaction_prompt_reappears_on_a_later_turn_after_being_used`）在移除 `reaction_prompted_player_ids` 後依然成立、不須修改（它們驗證的是「換了新副本後下一輪還能再問」，這件事本來就是對的，只是上一輪誤把「同一回合内只問一次」也當成正確設計附帶驗證，這部分已一併移除／修正）。
  - 驗證：`test_action_card_regressions.py` 反應相關測試 11/11；完整 pytest 233/235（2 個既有無關 FakePage API drift 失敗）；`validate_intel_network_no_reaction_option_own_turn.py`／`validate_support_no_reaction_phase_gating.py`／`validate_cancellable_choice.py`（皆牽涉 `reaction_choice` 流程）重跑全綠，確認舊有的「奧援卡不觸發取消反應」「情報網己方回合不誤觸反應選項」「可取消 pending choice 的中紀委/政工部/國安部」等既有行為都未被本次改動波及。
  - 未做：正式 WebSocket UI 層面尚未另外建立「同一回合連續出牌各自跳出詢問」「3 人局候選人接力」的雙玩家瀏覽器 proof（本次以直接呼叫 `play_card`／`resolve_pending_choice` 等生產方法覆蓋核心狀態機；`reaction_choice` 的 WS 廣播/逾時/隱私範圍已有既有 `test_reaction_timeout_and_privacy.py` 覆蓋，但未疊加「連續出牌」與「多候選人接力」兩個維度）。

### P2：瓦解組織效果應直接導向地圖並以💀標示合法目標
- [done] 使用 `北國奧援`、`臺灣奧援`或其他需要選擇組織進行瓦解的卡牌／效果時，建立authoritative pending target後應自動切換至正式戰略地圖，並只在後端判定可合法瓦解的組織marker上直接顯示 `💀`；玩家應可在地圖上點選該組織完成瓦解，不必先在指揮中心或通用choice modal尋找目標。（2026-08-02 playtest建議）
  - 統一 interaction_kind：`server/game.py` 的 `state()` 序列化新增 `pending_is_dissolve` 判定（choice_key 屬於 `intel_network_dissolve_target`／`event_red_dissolve`／`era_red_bonus_dissolve_target`／`red_army_state_security_target`，或 `support_interaction`／`card_dissolve_interaction` 且 step=='target' 且 effect_type 屬於 `interactive_dissolve_many_near`／`interactive_dissolve_and_build`／`interactive_dissolve_self_and_enemy`），統一輸出 `interaction_kind: 'dissolve_organization'`（與既有建立組織的 `'build_organization'` 對稱）；明確排除 `support_interaction` 的 `force_discard_near`（同樣 step=='target' 但選的是玩家而非要瓦解的組織）。
  - 前端：`app.js` 的 `renderChoiceModal()` 新增 `isMapDissolveChoice` 分支（緊接既有 `isMapBuildChoice` 之後），偵測到 `interaction_kind==='dissolve_organization'` 就隱藏 choice modal、自動 `setActiveGameView('map')`、把候選目標包成 `support-targets` payload（`actionKind:'dissolve'`）同步給地圖；移除了原本「modal＋地圖提示外框」混合模式的舊邏輯（`targetChoicesWithMapHighlight`／`shouldHighlightTargetChoices`），因為 6 個瓦解 choice_key 現在全部改走新分支，舊邏輯變成死碼。
  - 地圖：`leaflet_game_map_logic.js` 新增 `isDissolveSupportChoiceHighlight()` 與 `renderSupportChoiceHighlights()` 的 dissolve 分支——後端投影的每個合法目標城鎮上疊一個半透明紅色熱區（放大點擊範圍）＋💀 divIcon（`leaflet_game_map.html` 新增 `.dissolve-target-badge` 樣式），點擊任一個直接呼叫既有 `sendDissolveAction(null, townName)`（沿用既有 `supportTargetChoiceForTown()` 比對 town→index 解析出正確的 `resolve_choice` index，無需改動解析/送出邏輯本身）完成瓦解，不需要先選取再按側欄按鈕。
  - 候選正確性（敵我／距離／地區／根據地保護／自我犧牲／連續瓦解／無合法目標）完全沿用既有後端候選投影函式（`_interactive_support_dissolve_targets` 等），本次未變動，只是把「怎麼呈現／怎麼點選」換成地圖優先；紅軍根據地兩次命中才移除的耐久規則（P1「根據地瓦解」）在地圖新流程下驗證仍正確運作（`validate_base_dissolve_browser.py` 9/9 含此案例）。
  - 回歸修正：`validate_beiguo_two_stage_dissolve.py`（北國奧援 I 級兩段式瓦解：sacrifice_town 步驟仍走 modal，target 步驟改驗證自動切地圖＋💀＋一鍵解決）、`validate_intel_network_map_close_browser.py`（原測「關閉 modal 後用地圖側欄按鈕完成」的路徑已不存在，改測「建立 pending choice 即自動切地圖、💀 數量與後端候選一致、一鍵完成」）、`validate_base_dissolve_browser.py`（移除已點不到的手動關閉 modal 步驟，其餘斷言〔含非紅軍根據地保護、紅軍根據地兩次命中〕不變仍全過）皆已改寫並全綠；`test_action_card_regressions.py` 等既有 pytest（222/224，2 個既有 FakePage API drift 失敗與本次無關）與其餘瓦解相關 validator（`shared_dissolve_ui_phase8`、`support_region_leadership_browser`、`intel_network_no_reaction_option_own_turn`）皆無退化。
  - 新增 `python3 scripts/validate_dissolve_map_first_interaction.py`（6/6，連跑 3 次穩定）補齊跨來源覆蓋：內應間諜（`card_dissolve_interaction`，單步、距離過濾使 3 座敵方城鎮只有 1 座在範圍內顯示 💀）、北國奧援 III 級（`support_interaction`，連續瓦解 2 個，兩輪 💀 數量正確更新、結算後停留在地圖）。proof `docs/records/action-cards/DISSOLVE_MAP_FIRST_INTERACTION_VALIDATION.{json,md}` + `dissolve_map_first_spy_card.png`／`dissolve_map_first_multi_target.png`。
  - [done] 追加：使用者回饋單擊 💀 立即瓦解對新手太危險（容易只是想點點看就誤觸不可逆動作），改為「選取→確認」兩步驟（2026-08-02）——`renderSupportChoiceHighlights()` 的 dissolve 分支點擊行為從直接呼叫 `sendDissolveAction` 改為 `selectTownForCurrentMapAction(townName)`（與既有建立組織候選城鎮的選取模式一致），選中目標的 💀 以 `.dissolve-target-badge-armed` 樣式（金色描邊＋脈動動畫）標示；`renderMovementHighlights()` 內在 `selectedTown` 賦值後補一次 `renderSupportChoiceHighlights()`，修正原本 `renderMap()`→`renderSupportChoiceHighlights()` 早於 `selectedTown` 更新導致 armed 樣式延遲一輪才刷新的問題。真正執行瓦解改為沿用既有側欄 `#dissolveBtn`（`refreshDirectBuildUi()` 已有的 `supportTargetChoiceForTown(selectedTown)` 分支，本次僅把按鈕文字/提示改得更明確：「確認瓦解此組織」＋「確認瓦解 X 的組織？…按上方按鈕才會真正執行」），未新增任何按鈕或狀態變數。三支相關 validator（`validate_dissolve_map_first_interaction.py` 9/9、`validate_beiguo_two_stage_dissolve.py` 6/6、`validate_intel_network_map_close_browser.py`）已改寫斷言為「點 💀 → 斷言僅選取未變動盤面 → 點 `#dissolveBtn` → 斷言真正完成瓦解」；`validate_base_dissolve_browser.py`（本就走 select+按鈕流程，未受影響）重跑仍 9/9；pytest 229/231（2 個既有無關 FakePage API drift 失敗）。

### P1：多張建立組織卡可累積後在地圖一次結算
- [done] 已將原本只允許多張 `宣傳家` 的特判改為通用 build-entitlement FIFO；所有具印刷 `build` effect 的行動卡（`宣傳家`、`思想家`、`組織經驗甲／乙／丙`）都可在既有 `card_build_organization` 尚未結算時繼續以行動打出。queue entry 保留各卡自己的 range、ignore-distance、後續移動／repeat／其餘 effects與結算順序；每次建立後重新計算合法城鎮與組織棋供應，無合法目標或供應耗盡時安全跳過未能使用的 entitlement。state以 viewer-scoped `queueable_card_names`控制正式手牌按鈕，`remaining_builds`計入 active effect、同卡尚未執行的 build effects與後續queued cards；指揮中心會在仍有可加入的建立牌時留在手牌區，最後一張加入後才自動切正式Leaflet地圖集中建立。新增5卡admission matrix、異質 `丙＋乙=3` FIFO、範圍差異、候選重算、供應耗盡、甲repeat continuation、後續移動與非建立牌阻擋共12項；focused pytest 12/12、action/build affected pytest 119/119、逐檔完整可收集pytest 175 passed、單卡建立runtime 5/5、action card recomposition 46/46、正式 Chromium／WebSocket／Leaflet UI proof 10/10且console 0。人工截圖確認第二張卡行動按鈕可用、地圖顯示尚可建立3個及中性候選、最後3次建立與兩卡棄牌紀錄。證據位於 `docs/records/action-cards/build-entitlement-queue/`。（2026-08-01 完成）

### P1：所有奧援卡的事件任務進度稽核
- [done] 已確認 `東突厥集中營` canonical任務條件為「打出至少1張購買費用有宣傳的卡牌」，8種一般奧援卡的印刷購買費用皆為 `1資金＋2宣傳`，因此全部應計入；`紅軍奧援`是無購買費用的起始牌，不計入。root cause是需要後續選擇的互動奧援在 `play_card()`建立 pending choice後提早 return，跳過位於其後的事件進度hook。現改為合法奧援通過目標preflight後、pending return前依原始印刷購買費用記錄事件進度；無合法目標退回卡牌時不計，北國奧援於初始步驟取消時連同卡牌、turn flags、事件進度與事件通知一起transactional rollback。新增8種一般奧援matrix、臺灣奧援II級pending、no-target、北國取消與紅軍奧援負例共12項；affected pytest 133/133、事件runtime 35/35、奧援runtime 12/12、北國7/7、南洋2/2、正式臺灣奧援UI proof 8/8且console 0。證據位於 `docs/records/event-cards/support-event-progress/`。（2026-08-01 完成）

### P1：`合作談判`可指定敵對玩家
- [done] `合作談判`的正式玩家選單由server state中的所有其他玩家產生，不依陣營、camp、友好／敵對關係或距離過濾；四人UI實測候選同時列出香港 Ally、紅軍 Enemy、臺灣 Observer，且不列行動者自己。後端 `play_card()`在卡牌移出手牌與任何抽牌／資源mutation前fail closed：必須提供存在且不是自己的 `target_player_id`，缺少、自身或不存在目標皆以繁中錯誤拒絕並保持手牌、牌庫、棄牌、資源、pending與log完全不變。合法指定紅軍Enemy時只讓Actor與Enemy各抽1張，Ally／Observer不抽，Actor另得2宣傳；action log明確記錄實際指定者。新增敵對成功與3種非法目標matrix共4項，focused negotiation pytest 5/5、逐檔完整可收集pytest 179 passed、規則runtime 4/4、正式四人Chromium/WebSocket UI proof 11/11且console 0。證據位於 `docs/records/shared-actions/NEGOTIATION_CARD_VALIDATION.{json,md}`、`NEGOTIATION_ENEMY_TARGET_UI_VALIDATION.{json,md}`與兩張正式截圖。（2026-08-01 完成）

### P1：根據地瓦解與紅軍根據地失效規則
- [done] 一般陣營根據地已從所有瓦解候選投影排除，中央 `dissolve_organization()`亦 fail closed；紅軍北京根據地保留為唯一例外。同一玩家同一回合第一次成功只記 `1/2`並保留組織，第二次才移除組織、保留北京根據地位置，並以當回合 `turn_log`封鎖紅軍在北京的所有建立來源；不同玩家、不同回合命中不合併，下一回合可重建。建立封鎖集中於 `_place_organization()`，移動既有組織明確豁免；自我犧牲不可選自己的根據地，legacy effect先確認合法敵方目標才支付犧牲，避免直接 mutation繞過。focused pytest 7/7、affected runtime pytest 121/121、完整可收集 pytest 152 passed（另2個未修改舊 UI validator FakePage測試因 API drift失敗）、紅軍 runtime 6/6、一城一組織 11/11、北國兩階段 7/7、奧援 runtime 12/12、正式 Leaflet/WebSocket UI proof 9/9且 console 0。證據位於 `docs/records/base-dissolve/`。（2026-08-01 完成）

### P1：奧援卡 II／III 級的「最多組織」門檻
- [done] 已將所有 8 種一般奧援卡、每種 2 個印刷 variant 的 II／III 級判定由「指定地區至少有 1 個己方組織」改為「指定地區組織數並列全場最多且大於 0」；平手視為共同最多，全員 0 不算。III 級先比較該卡自身奧援地區，II 級仍只檢查該實體卡印刷的兩個指定地區並維持 OR 語義；`matched_rulers`只回傳真正領先的地區。區域計數統一經實體組織城鎮與共用關係計算，依 `rules.md`讓共用組織對每個共享玩家各計 1，但同一玩家不重複計算同一實體。另修正市場購買／借用 copy 遺失 `variant_index`，確保 variant 1 經購買、棄牌、洗牌與抽回後仍使用原卡面及 II 級指定地區，普通卡不新增 variant metadata。新增 8 卡 × 2 variants matrix，涵蓋有 1 但落後、並列最多、自身地區 III 級、零組織、OR、共用組織及 variant 生命週期；focused pytest 6/6、affected pytest 121/121、奧援 runtime 12/12、東洋互動 6/6、南洋 2/2、北國 7/7、一城一組織 11/11、正式 UI proof 9/9。UI 證據位於 `docs/records/support-region-leadership/`。（2026-08-01 完成）

### P2：`上海合作組織`卡面說明文字被右側裁切
- [done] 已確認裁切存在於 runtime 原始 PNG，而非瀏覽器 DOM／CSS。重新以 canonical 事件文字與既有插圖排版 `上海合作組織`完整卡面，將無標點長句改為 22 字安全寬度硬換行；任務文字現完整留在白色內容框內，右側安全區無深色文字像素。新增專用 validator，覆蓋 1350×1100 資產、runtime 綁定、右側安全區、放大卡比例、視窗邊界、狀態列及 console error，正式 UI proof 10/10 passed。（2026-08-01 完成）

### P2：遊戲區域寬度與卡牌邊界裁切
- [done] 指揮中心三欄由 `312 / 460 / 460px`調整為 `284 / 474 / 474px`：常設購買區縮窄，隨機購買區與手牌區各加寬，兩張 220px 卡牌加 12px gap 可完整落在 panel 內容寬度內，`purchaseRandom`與 `hand`均由 `client/scroll 442/452`修正為 `456/456`。另修正 1280×720 固定舞台在 1024 viewport 以中心縮放後整體右偏 128px 的問題，改由 `resizeStage()`計算縮放後 left/top 並以左上為 transform origin；移除已過時的窄視窗事件卡左移 workaround。新增 1280×720 與 1024×768 正式 browser geometry／截圖 proof，覆蓋欄寬、卡牌與按鈕邊界、zone/document overflow、viewport containment、卡面載入及 console，20/20 passed；證據位於 `docs/records/game-area-width/`。（2026-08-01 完成）

### P2：所有玩家可見英文提示全面中文化
- [done] 已建立共用 `static/player_messages_zh_tw.js` 翻譯邊界，接入 lobby REST error、WebSocket error、原生 dialog、行動提示、pending choice/modal 與正式戰略地圖；未知英文操作錯誤使用繁中安全 fallback，內部 key／protocol identifier 不直接作 UI fallback。後端 125 條固定 error inventory 全數具專用翻譯或受控規則；`Target player has no organization within range`正式顯示為「目標玩家在範圍內沒有組織。」。另將地圖工具列及 road/rail/shared-dissolve 等殘留英文中文化，錯誤提示改為 5 秒 sticky 並避開事件卡縮圖；action log 與地圖動態提示補 HTML escape。靜態 regression 24/24、正式 browser proof 10/10、相鄰 backend tests 115/115 通過，證據位於 `docs/records/player-message-localization/`。（2026-08-01 完成）

### P0：一城一組織 invariant 與共用組織語義
- [done] 全場每個城鎮最多 1 個實體組織；香港／粵／澳門共用同一枚組織，不是同城疊放例外。
  - 2026-07-28：`rules.md` 補上共用組織的建立起點、移動、瓦解、計數與所有權轉移語義；建立、卡牌／事件／時代效果、移動、根據地選擇及香港根據地遷移均統一檢查實體佔位。
  - 紅軍根據地耐久改用同一行動玩家同回合兩次成功瓦解的命中計數，地圖上仍只有 1 枚組織。
  - runtime：`validate_one_organization_per_town.py` 11/11、事件卡 35/35、時代效果 15/15、移動 13/13、敵佔規則 5/5、相關 pytest 95/95；正式 UI：`validate_one_organization_per_town_ui.py` 7/7，proof 位於 `docs/records/map-ui/ONE_ORGANIZATION_PER_TOWN_UI_VALIDATION.{json,md}` 與 `one_organization_per_town_ui.png`。
  - 地圖標籤不再顯示永遠為 1 的組織數；遠視角只顯示城鎮名，zoom 10 起附陣營名稱，組織存在與陣營仍由實心色表示。

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
- [done] Playtest rule/flow bug：陣營在部分應合法城鎮無法建立組織（紅軍：`廣州`、`金門`；臺灣：`金門`）。
  - 2026-07-29 回報情境：紅軍嘗試在 `廣州` 建立組織時，UI／系統似乎未提供或拒絕建立；後續也發現紅軍與臺灣似乎都無法在 `金門` 建立組織。
  - 期望：`廣州` 應允許紅軍建立，`金門` 應同時允許紅軍與臺灣建立；符合一般距離、佔位與效果限制時，前端候選高亮與後端建立驗證都應允許。
  - 需檢查：兩座城鎮資料中的陣營適用設定（尤其 `金門` 的紅軍／臺灣適用範圍）、`can_faction_develop_in_town`／`can_develop_in_town`、後端 legal build projection，以及地圖建立候選清單是否錯誤排除合法陣營。
  - 2026-07-29 root cause：陣營標籤與後端陣營合法性均正確；問題是道路／鐵路鄰接資料非對稱（例如 `金門→廈門` 有邊、`廈門→金門` 無反向邊，`廣州→桂林／南寧` 同理），一格建立從缺反向邊的一側出發時會被距離投影排除。全圖掃描另見 12 條 road、21 條 rail 非對稱與 `台東／臺東` 異體字幽靈連線。
  - 2026-07-29 已修正：以 Leaflet 原有 185 條無向 road／286 條無向 rail 為視覺基準，補齊 canonical `map.json` 缺少的反向 adjacency 並統一 `台東→臺東`；改造前後無向 edge set 完全相同，沒有新增或刪除任何視覺連線。紅軍 `桂林／南寧→廣州`、紅軍與臺灣 `廈門→金門` 的陣營、1 格距離及實際建造候選矩陣均通過。
  - 地圖單一來源：正式、embed 與 standalone Leaflet 已移除內嵌 `MAP_DATA`／`GEO_COORDS`，統一讀取 `/map-data` 與 `/map-geo-coordinates`。`movement_rules` 明確拆成道路 1 格、鐵路 3 格、一般移動成本 1、翻牆 1 格／成本 2；後端鐵路 range 與移動成本改讀 canonical schema。
  - 驗證：`test_map_data_single_source.py` 5/5、`validate_map_single_source_browser.py` 8/8（269 城鎮、185 road、286 rail、兩個 canonical API、standalone 選單無重複、console 0 error）、`validate_movement_rules.py` 13/13；正式 UI、可建數、金門標籤、陣營顯示回歸全綠。

- [done] Playtest UI：點選棄牌堆中的卡牌時，應可查看該卡牌的完整卡牌圖片。
  - 2026-07-29 回報情境：「戰況紀錄」的玩家資訊卡目前以文字籤列出棄牌堆卡名，但無法從這裡查看卡牌圖片。
  - 期望：棄牌堆中的每張卡牌／卡名都可點選，點擊後開啟該卡牌的完整卡面圖片預覽；應沿用既有卡牌預覽互動與文字 fallback，不改變棄牌堆內容或遊戲狀態。
  - 需檢查：`static/app.js` 戰況總覽棄牌堆 render、棄牌卡名 click handler、既有完整卡面 preview overlay，以及卡名到 `static/card-art/` 圖片資產的映射。
  - 回報截圖：`/Users/benmini/.hermes/cache/images/img_3e2ea2cf475f.jpg`。
  - 2026-07-29 已修正：後端投影 `discard_variants`；卡名改為可點擊按鈕並沿用 `selectCardDetail()`／完整卡面 modal。正式 browser proof 2/2 中的棄牌預覽項通過，包含北國奧援 variant 0 精確卡面。

- [done] Playtest card interaction bug：先打出 `臺灣奧援`，再打出 `點燃熱情`，應可抽 2 張牌。
  - 2026-07-29 回報情境：玩家先打出 `臺灣奧援`，接著打出 `點燃熱情`，目前似乎沒有正確套用可抽 2 張牌的結果。
  - 期望：系統應辨識本回合先前已打出的 `臺灣奧援`，使後續 `點燃熱情` 依卡牌互動效果抽 2 張牌；實際手牌、牌庫與戰況紀錄應同步反映。
  - 需檢查：`點燃熱情` 的抽牌數判定、`臺灣奧援` 的本回合已打出／牌色／類型紀錄、出牌順序追蹤，以及抽牌與棄牌堆結算時機。
  - 2026-07-29 已修正：購買費用 trigger 改依 `_card_purchase_cost()`，不再排除 support 卡；費用旗標在互動奧援提前返回前即記錄，且 `點燃熱情` 仍使用打出自己前的旗標快照。focused regression PASS。

- [done] Playtest UI/flow：建立組織流程應顯示目前還可建立幾個組織。
  - 2026-07-29 回報情境：玩家可能一口氣使用多張 `宣傳家`，再集中處理建立組織；目前畫面缺少「剩餘可建立組織數」提示，容易不知道還有幾次建立待處理。
  - 期望：建立組織選點流程除了顯示可建立城鎮數，也要清楚顯示本批／目前尚可建立的組織數量，並在每次成功建立後即時遞減，直到所有累積建立效果處理完畢。
  - 需檢查：多張 `宣傳家` 的效果累積與 pending-choice queue、剩餘建立次數的後端狀態投影、`static/app.js`／戰略地圖的建立提示，以及連續建立後的流程推進與計數同步。
  - 2026-07-29 已修正：建立 choice 投影 `interaction_kind=build_organization`／`remaining_builds`；允許未結算建立時繼續打出宣傳家並累積 entitlement；每次建立後重新計算候選、遞減次數，且每張宣傳家各自給 1 移動。focused regression 驗證連打 2 張、連建 2 次、移動累積為 2。

- [done] Playtest UI/flow：使用 `東洋奧援` 建立組織時，應直接在戰略地圖顯示合法城鎮，而不是跳出城鎮選單。
  - 2026-07-29 回報情境：`東洋奧援` 進入建立組織選擇時，目前以選單列出城鎮。
  - 期望：系統應自動切換／聚焦戰略地圖，直接高亮所有可建立組織的合法城鎮，讓玩家在地圖上點選；提示應顯示可建立城鎮數與該效果剩餘建立數，不再出現重複的城鎮選單。
  - 需檢查：`東洋奧援` 各級效果的 pending choice 類型與建立數量、support-card build choice 的前端 routing、戰略地圖 legal target projection／高亮，以及選點完成後的連續建立流程。
  - 2026-07-29 已修正：`support_interaction` 的 town step 以 semantic build payload 導向戰略地圖，不顯示重複選單；正式 browser proof 驗證後端 34 個候選與 34 個中性 marker 一致，並顯示「尚可建立組織：1 個」。

- [done] Playtest UI/flow：使用 `北國奧援` 時，在尚未選擇／結算目標前可取消使用。
  - 2026-07-29 回報情境：玩家進入該奧援卡的使用／目標選擇流程後，目前似乎無法取消並返回。
  - 期望：效果尚未實際結算前應提供明確的「取消使用」入口；取消後不消耗卡牌、不執行效果、不留下 pending choice，並讓玩家回到可重新選擇行動的狀態。
  - 需檢查：`北國奧援` 各級效果的 pending-choice 建立與結算時點、support card 出牌是否過早移出手牌、choice cancellable policy、前端取消按鈕，以及取消後的卡牌／行動／階段狀態還原。
  - 2026-07-29 已修正：初始選擇可交易式取消，還原卡牌位置、購買費用旗標與 pending；第一個目標結算後取消即關閉。同步修正 III 級 `count:2` 連續瓦解。unit 7/7 與 browser `BEIGUO_TWO_STAGE_DISSOLVE_VALIDATION` 7/7。

- [done] Playtest deck lifecycle investigation：紅軍結束回合時棄牌堆似乎會被直接清空，且可能沒有正確洗回牌庫。
  - 2026-07-29 回報情境：紅軍只要結束回合，畫面上的紅軍棄牌堆就直接變空；同時懷疑這些牌沒有經過洗牌進入新的抽牌堆。
  - 期望：結束回合不應無條件清空棄牌堆；棄牌應持續保留，只有抽牌堆需要補充時才依規則將棄牌堆洗牌後轉成新的抽牌堆，且所有卡牌總數與區域歸屬必須守恆。
  - 需檢查：紅軍 `_end_turn`／補牌流程、`Deck.draw()` 的棄牌重洗邏輯、紅軍專屬牌與借用卡的棄牌目的地、state 序列化的 discard projection，以及 UI 是否只是錯誤隱藏而非後端真的清空。
  - 2026-07-30 釐清：判斷是否洗牌的關鍵不是棄牌堆張數，而是「本次補到 5 張的過程是否耗盡牌庫」。正式 UI 確定性重現：手牌 4／牌庫 1／棄牌 1 時，結束回合後棄牌仍為 1；手牌 4／牌庫 0／棄牌 1 時，該棄牌依規則洗成新牌庫並立刻被抽入手牌，棄牌顯示為 0。兩情境卡牌總數與身分均守恆。
  - 可觀察性修正：只有確實發生洗牌時，action log 新增「牌庫用盡，將棄牌堆 N 張牌洗成新牌庫」；未洗牌時不顯示。正式 browser proof `RED_END_TURN_SINGLE_DISCARD_VALIDATION` 2/2，兩情境皆由可見「結束回合」按鈕操作、console 0 error。
  - 2026-07-31 新回報：`host` 打出 1 張樂捐者後，10 張棄牌在回合結束補牌時洗回；`紅軍權貴出逃`失敗再選擇棄 1 張，但下一輪 `上海合作組織`開始時 UI 顯示手牌 3／牌庫 8／棄牌 2，兩張皆為樂捐者。這與 action log 的單次 chosen discard 不一致。
  - 精確重現初期未失敗：同樣的手牌 0／牌庫 3／棄牌 10、延後結算紅軍權貴出逃、選擇樂捐者、紅軍回合結束、下一輪上海合作組織路徑本身只產生手牌 4／牌庫 8／棄牌 1；藉此排除事件重複結算。
  - 2026-07-31 root cause／修正：第二張其實由 `hostda` 隨後打出的 `天方奧援`造成。當紅軍一格內沒有合法、有手牌的目標時，interactive flow 回傳無目標，但 `_execute_support_card()` 又錯誤進入舊 fallback，忽略距離、任取其他玩家並靜默 `pop(0)`；因此把 host 手牌第一張樂捐者移入棄牌堆且沒有明確 log。已刪除任意玩家 fallback；無合法目標時不棄任何牌並記錄 no-target。合法目標的正常互動選擇／隨機棄牌保持不變。天方奧援 regression 3/3、完整正式 UI deck lifecycle 3/3、backend focused 14/14，console 0 error。
  - 2026-07-31 同型錯誤擴大稽核／修正：所有 interactive-only 奧援無合法目標時統一 fail closed，並交易式把奧援卡放回原手牌位置、還原本回合費用旗標；移除 `build_anywhere_inner`、`build_near_inner`、`dissolve_many_near`、`dissolve_self_and_enemy`、`dissolve_and_build` 的舊自動 fallback。`EffectEngine.force_discard`／`dissolve` 未指定明確玩家時不再退回所有對手。`派遣間諜`／`內應間諜`改為移出手牌前先確認至少一個合法目標，避免回錯誤後卡牌從所有 zone 消失。resolver 結算時重新驗證東洋建立、北國／臺灣瓦解、天方棄牌的距離；臺灣奧援 III 僅列出能完整「瓦解並同城建立」的目標，禁止只做前半段。武裝牌不再允許空手目標；誘導虛耗不再列出空手玩家。backend 136/136、support runtime 12/12、current playtest UI 2/2、deck lifecycle UI 3/3。

#### 2026-07-29 本批修正順序（source-backed triage）
1. **牌堆生命週期／卡牌守恆（P0，M）**：先用紅軍回合結束的真實路徑確認「抽牌堆未空時棄牌保留、抽牌堆空時才洗回」與總卡數守恆；這是最可能造成卡牌永久遺失的項目，先排除資料破壞，再處理其他卡牌互動。
2. **`臺灣奧援` → `點燃熱情` 抽 2（P1，S）**：已定位 `play_card()` 明確把 support 排除於購買費用含宣傳／資金的回合旗標之外，但卡面條件只寫「其它購買費用有宣傳的牌」；修正共用費用判定並補 action-card regression。
3. **合法建立城鎮（P1，M）**：`map.json` 已確認 `廣州` 含紅軍標籤、`金門` 含紅軍與臺灣標籤，故不能只改資料；需以實際建立來源重現並修正 backend legal projection／距離／佔位判定，避免 UI 與後端分歧。
4. **棄牌堆卡牌圖片預覽（P2，S）**：既有 `selectCardDetail()`／`cardPreviewModal` 可直接重用，將文字籤改成可點擊卡牌元素並補 browser proof；與規則狀態無依賴，可作為前面後端修正後的快速 UI 項目。
5. **`東洋奧援` 改走地圖選點（P1，S～M）**：後端 `support_interaction` 已提供 `towns`，前端目前只把一般 card/event build town choice 導向地圖；擴充共用 routing，並與第 3 項共用合法候選驗證。
6. **顯示／支援累積剩餘建立數（P1，L）**：不只是文案；現行單一 `pending_choice` 會阻止連打多張 `宣傳家`，需先定義並實作建立效果 queue／remaining count，再投影到地圖提示。依賴第 3、5 項的共用合法建立流程。
7. **`北國奧援` 可取消使用（P1，L）**：卡片目前可能在建立 pending choice 時已移出手牌，取消需要交易式 rollback（卡牌、已完成步驟、pending、行動狀態）；最後處理以避免和 support 地圖流程重做互相衝突。

- [done] Playtest UI：紅軍抽到 `一帶一路 南洋` 時，戰略地圖應自動對準南洋區域。
  - 2026-07-29 回報情境：抽到 `一帶一路 南洋`，輪到紅軍回合並進入「免費在南洋無視距離建立 1 個組織」的自動事件選點流程時，地圖沒有自動對準南洋。
  - root cause：事件 build highlight 先依 11 個南洋候選執行 `fitBounds`，但地圖 iframe 隨後收到第一份 WebSocket state 時，`focusOwnBaseOnFirstState()` 又把視角覆寫回觀看者根據地北京；同一 highlight key 後續不會重複自動對焦，因此候選外框存在、視角卻停在北京。
  - 2026-07-29 已修正：集中定義會接管地圖視角的 map-choice keys；第一份 state 若已有地圖 pending choice，就將該候選視角視為初始視角並略過根據地自動聚焦。一般無 pending choice 的開局仍維持聚焦自己的根據地。同步更新地圖 JS cache bust。
  - 驗證：新增 `uv run --with playwright python scripts/validate_belt_road_nanyang_map_focus.py`（7/7）：紅軍 ACTION 的 `event_build_organization` 候選為 11 個南洋城鎮、UI 自動切到戰略地圖、中心由北京改至南洋、11 個合法候選全部在 viewport 內、提示數量一致、非行動玩家仍保留自己的根據地初始視角、console 0 error。回歸：`validate_map_label_zoom_and_base_view.py` 6/6、`validate_buildable_town_count.py` 4/4、`validate_event_card_zoom_preview.py` 11/11、JS/Python syntax 與 `git diff --check` PASS。
  - proof：`docs/records/event-cards/BELT_ROAD_NANYANG_MAP_FOCUS_VALIDATION.{json,md}`、`BELT_ROAD_NANYANG_MAP_FOCUS.png`。

- [done] Playtest UI：修復金門城鎮標籤被廈門標籤遮住。
  - 2026-07-28 root cause：金門（118.319, 24.432）與廈門（118.0894, 24.4798）地理位置接近；兩個 Leaflet permanent tooltip 原本都固定置於 marker 上方。在 zoom 5／6／7 實測重疊面積分別為 604.5／367.5／170.5 px²，且資料渲染順序較後的廈門蓋在金門上方，造成金門名稱看似消失。
  - 修正：新增 `townLabelOptions()`，只將金門 tooltip 固定放到 marker 下方並加入獨立 class；其他城鎮維持上方標籤。zoom 動態樣式同步套用相同方向與 offset，不修改金門／廈門座標或道路資料；更新地圖 JS cache bust。
  - 驗證：新增 `uv run --with playwright python scripts/validate_kinmen_map_label.py`（6/6）：zoom 5／6／7 金門與廈門標籤皆存在、金門使用 bottom placement、三個 zoom 重疊面積均為 0、標籤完整位於地圖內、browser console 0 error。回歸：`validate_map_label_zoom_and_base_view.py` 6/6、`validate_map_faction_display.py` 6/6、`validate_map_selection_highlight.py` 7/7。
  - 驗證保養：兩支既有 map validator 補上關閉回合開始事件卡 Zoom-in，避免事件遮罩攔截「戰略地圖」Tab 點擊。
  - proof：`docs/records/map-ui/KINMEN_LABEL_VALIDATION_2026_07_28.{json,md}`、`KINMEN_LABEL_UI_2026_07_28.png`。

- [done] Playtest UI：縮小右上角固定事件卡，避免遮住戰略地圖工具列。
  - 2026-07-28 回報：原固定事件卡使用完整 `270×220` 遊戲尺寸，底緣進入戰略地圖區並遮住 `Fit All`／`Focus Asia`／`Export View`。
  - 修正：固定縮圖改為 `180×147`（維持 1350:1100 原比例）、圓角同步縮小；完整 `1350×1100` 卡面、回合開始置中 Zoom-in、點擊縮圖重開、Escape／點擊任意處關閉及純文字載入失敗備援全部保留。固定 1280×720 舞台在窄視窗會向右溢出，另於 `max-width:1100px` 將縮圖拉回可視範圍。
  - 驗證：`uv run --with playwright python scripts/validate_event_card_zoom_preview.py` 11/11；1280×720 實測縮圖 `180×147`、底緣 y=147，地圖 toolbar 頂緣 y=226，零重疊；1024×768 實測縮圖完整位於 viewport 且與 toolbar 零重疊；瀏覽器 console 0 error，縮圖仍可重開完整卡面。
  - proof：`docs/records/event-cards/EVENT_CARD_ZOOM_PREVIEW_VALIDATION.{json,md}`、`EVENT_CARD_COMPACT_MAP_1280_2026_07_28.png`、`EVENT_CARD_COMPACT_MAP_1024_2026_07_28.png`、`EVENT_CARD_ZOOM_PREVIEW_OPEN_2026_07_28.png`。

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

- [done] Playtest UI polish：臺灣北部地圖標籤過密互相重疊蓋字＋玩家名陣營色＋開局根據地視角。
  - 2026-07-13 桌測參考截圖：`docs/records/misc/taiwan-map-label-overlap-reference.jpg`——北臺灣城鎮密集區（臺北/新北/桃園/基隆/宜蘭），加上陣營標籤後「臺北 1（臺灣（綠線））」變長，跟鄰近城鎮標籤互相覆蓋，臺北的字被新北/基隆壓住讀不到。2026-07-18 實測確認問題仍在（zoom 9 下臺北長標籤與新北相疊）。
  - 2026-07-18 使用者裁決採 **zoom 門檻方案**並追加兩項需求，已全部實作：
    - ① 標籤 zoom 門檻：`labelTextForTown()` 只在 `zoom >= FACTION_LABEL_MIN_ZOOM`（=10）時附陣營文字，遠視角只顯示「臺北 1」（陣營資訊由圓圈陣營填色承擔）。實測 zoom 9 長標籤仍與新北相疊、zoom 10 才完全散開，故門檻取 10 而非 9。`updateDynamicStyles` 補 `setTooltipContent` 讓 labelMode 'on' 時 zoom 變動也會刷新標籤文字。
    - ② 玩家名稱字色＝陣營色：`app.js` 新增 `FACTION_CATEGORY_COLOR`／`FACTION_NAME_COLOR_OVERRIDE`／`factionNameColor()`（與地圖 iframe 的 palette／override 同值），套用於戰況總覽玩家卡名稱與 HUD「當前玩家」名字；地圖側欄「當前行動玩家」同步上色（`updateStatusPanel`）。
    - ③ 開局視角：地圖 iframe 收到第一份遊戲狀態時，以觀看者自己的根據地為中心 `setView(zoom 9)`（`focusOwnBaseOnFirstState`，用 `mapPlayerId` 找 viewer 的 base），取代原本每場都要自己從整個亞洲視角 zoom in。
  - 驗證：新增 `python3 scripts/validate_map_label_zoom_and_base_view.py`（6/6，連跑 3 次穩定：開局視角以臺北為中心 zoom 9、地圖側欄當前玩家名為陣營色、zoom 9 標籤無陣營文字、zoom 10 有、戰況總覽兩位玩家名各為紅軍紅/綠線綠、HUD 當前玩家名陣營色）；proof `docs/records/map-ui/MAP_LABEL_ZOOM_AND_BASE_VIEW_VALIDATION.{json,md}` + `map_label_far_zoom.png`／`map_label_near_zoom.png`。既有 `validate_map_faction_display.py`（6/6）／`validate_map_selection_highlight.py`（7/7）需回歸確認。
  - 2026-07-18 後續（使用者提供原版桌遊陣營色）：香港紫、蒙古深藍、藏國綠、哈薩克青綠、維吾爾淺藍、滿洲金黃——六色依原版校正（`leaflet_game_map_logic.js` 的 `palette` 與 `app.js` 的 `FACTION_CATEGORY_COLOR` 同步改：香港 #a855f7、蒙古 #2563eb、藏國 #15803d（初版 #16a34a，使用者要求再深一階）；綠線同步調淺為 #4ade80（原 #22c55e，使用者要求，拉開與藏國深綠的距離）、哈薩克 #14b8a6、維吾爾 #93c5fd、滿洲 #eab308）。藏國改綠後與臺灣綠線（#22c55e）同色系，取深一階綠做區隔；`palette` 同時是地區統治者的城鎮底色，一併生效（原版本就是地區色＝陣營色）。地圖驗證回歸全綠（label_zoom 6/6、faction_display 6/6、selection_highlight 7/7）。

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

- [done] 每回合事件卡 Zoom-in 與右上角重開（2026-07-26 使用者需求）。
  - 回合首次收到新的 `current_event` 時，以現有純文字資料自動顯示置中的放大事件卡；同一回合關閉後，後續 state 更新不會反覆重開。
  - 點擊放大卡或遮罩任意位置均可關閉，`Escape` 也可關閉；右上角既有 `.event-card-panel` 改為可點擊／鍵盤操作，隨時重新放大本回合事件。
  - 暫不接入設計審稿目錄中的圖片卡面；放大層確認沒有圖片節點或 card-art 綁定。
  - 驗證：`validate_event_card_zoom_preview.py` 9/9、`validate_event_cards_runtime.py` 35/35、`validate_event_effect_text_browser.py` 2/2；proof 位於 `docs/records/event-cards/EVENT_CARD_ZOOM_PREVIEW_VALIDATION.{json,md}` 與兩張正式 UI 截圖。

- [done] Playtest UI/rule polish：城鎮只能有一個組織，不需統計或顯示城鎮組織數量。
  - 2026-07-28：一城一組織 invariant 完成後，地圖標籤已移除永遠為 1 的數字；本批再移除 popup 的「當前組織總數：N」與側欄「有組織（N）」顯示，改為「組織狀態：有／無組織」並保留控制者／陣營資訊。
  - 驗證：`validate_one_organization_per_town_ui.py` 7/7、`validate_legal_movement_ui.py` 11/11。

- [done] Playtest UI polish：右上角事件卡面板太大，遮住地圖操作按鈕。
  - 回報情境：完整事件卡固定顯示於地圖右上角時，卡片覆蓋 `Fit All`、`Focus Asia`、`Export View` 等地圖按鈕所在區域，妨礙操作與辨識。
  - 期望：縮小事件卡、調整面板位置或提供不遮擋地圖控制列的收合方式；仍需保留點擊卡片重新放大查看完整內容的入口。
  - 需檢查：不同視窗寬度／地圖尺寸下 `.event-card-panel` 與地圖右上控制列的碰撞，並確保調整後卡面可辨識、按鈕可完整點擊。
  - 回報截圖：`/Users/benmini/.hermes/image_cache/img_e04e233354e6.jpg`。

- [done] Playtest UI/rule polish：移動組織時，只顯示該組織實際可合法到達的城鎮。
  - 2026-07-28：`move_organization()` 的所有前置檢查抽成無副作用 `_validate_organization_move()`；實際執行與 viewer-scoped `map.legal_organization_moves` 共用同一來源，完整涵蓋 phase、移動點、道路／鐵路、翻牆成本、陣營發展空間、佔位、根據地錨定、共享組織供應、紅軍限制、赤臘角機場及 ignore-distance。
  - 前端 `movementOptionsForTown()` 只消費後端投影，缺少投影即 fail closed，不再自行 BFS 或複製規則；非當前玩家不收到可操作投影。
  - 驗證：`validate_legal_movement_projection.py` 8/8、`validate_movement_rules.py` 13/13、`validate_wall_crossing_movement.py` 6/6、`validate_enemy_occupancy_rules.py` 5/5。

- [done] Playtest 地圖／操作 UI polish：區分候選城鎮與既有組織，並整理移動／建立操作按鈕。
  - 2026-07-28：移動、建立與效果目標候選統一改成不屬於任何陣營的淺灰中性色外框；候選樣式沿用底層 marker 的 `fillColor/fillOpacity`，不再覆蓋既有組織的陣營實心色，並新增中性色候選圖例。
  - 「在目前城鎮建立組織」移到「確認移動」上方；「取消」改為「取消目的地（保留起點）」，取消後提示仍保留原起點與合法候選。
  - 驗證：`validate_map_selection_highlight.py` 7/7、`validate_buildable_town_count.py` 4/4、`validate_legal_movement_ui.py` 11/11；proof：`docs/records/map-ui/legal_movement_ui.png`。

- [done] Playtest 移動選取 UI polish：進入移動選取後聚焦合法路徑，並支援點擊地圖空白處取消。
  - 2026-07-28：移動選取期間只允許合法目的地或另一個己方／共享組織作為新起點；其他不合法城鎮維持一般視覺且點擊不改變選取，事件／支援目標選擇仍優先處理，未與既有模式衝突。
  - 實際點擊地圖空白處會清除起點、pending 目的地、候選高亮與側欄選取資訊；「取消目的地」則只退回已選起點，兩種取消語意明確區分。
  - 驗證：`validate_legal_movement_ui.py` 11/11（含 Playwright 實際點擊海面退出、非法城鎮不可互動）、`validate_move_confirmation.py` 8/8、`validate_map_selection_highlight.py` 7/7。

- [done] Playtest 地圖 UI bug：金門城鎮標示消失。
  - 回報情境：臺灣海峽局部地圖中可見金門位置的橘色城鎮圓圈，但圓圈上方／周邊沒有顯示「金門」名稱標籤；同畫面的廈門仍正常顯示名稱與狀態。
  - 期望：金門 marker 在一般地圖、移動選取與建立組織候選狀態下，都應持續顯示可辨識的城鎮名稱標籤，且不可被候選樣式、縮放層級或標籤避讓邏輯隱藏。
  - 需檢查：金門資料是否缺少 label/name、marker 與 tooltip 是否建立但被 CSS／pane z-index／碰撞避讓隱藏，以及移動／建立候選樣式重繪時是否漏掉永久標籤。
  - 回報截圖：`/Users/benmini/.hermes/image_cache/img_aa186a54b9c9.jpg`。

- [done] Playtest 個人資訊 UI polish：「我的陣營」與「我的時代關卡」改為頁內 Tab 內容，不再跳出 modal。
  - 回報情境：目前點選頂部的「我的陣營」或「我的時代關卡」會開啟覆蓋遊戲畫面的彈出視窗；這兩項本身已位於主功能 Tab 列，互動卻不像「指揮中心／戰略地圖／戰況紀錄」那樣在下方內容區切換，體驗不一致。
  - 期望：點擊後直接在 Tab 下方的主內容區渲染個人陣營與時代關卡資訊，不需另開 modal，也不需遮罩背景或額外關閉操作；切換其他 Tab 即可離開。
  - 實作方向：不強制使用 `<iframe>`。優先評估沿用現有 Tab router／content panel，以原生 DOM component 在同一頁渲染，避免 iframe 的尺寸同步、重複樣式、焦點與狀態傳遞成本；若現有架構確實適合再採 iframe。
  - 需保留：完整卡面或純文字 fallback、目前達成狀態／剩餘回合、紅軍無個人時代關卡提示、陣營能力與限制內容，以及圖片載入失敗時的備援。
  - 需檢查：Tab active 樣式、頁內捲動與響應式高度、事件卡面板重疊、從 modal 遷移後的鍵盤操作，以及既有 `openMyFactionModal()`／時代關卡 modal 邏輯如何去除或重用，避免留下雙重入口。
  - 2026-07-28 已完成：依使用者後續要求，移除獨立「我的時代關卡」Tab／View，將時代關卡合併到「我的陣營」右欄；左欄保留陣營四區，右欄顯示 viewer-scoped 時代狀態與已核准完整卡面。圖片載入失敗切換完整純文字四區，紅軍顯示無個人關卡提示，切換其他 Tab 即離開。
  - 驗證：`validate_my_faction_modal.py` 7/7、`validate_my_era_stage_view.py` 9/9、`validate_event_card_zoom_preview.py` 11/11；正式 proof：`docs/records/playtest-flow/my_faction_tab{,_hong_kong}.png`、`docs/records/event-cards/my_era_stage_tab_{pending,active,red_army}.png`。
  - 回報截圖：`/Users/benmini/.hermes/image_cache/img_431cc7fcb20e.jpg`。

- [done] Playtest bug：臺灣已在牆內擁有 7 個有效組織，仍未觸發時代關卡。
  - 回報情境：「我的時代關卡」顯示 `[臺灣重建敵後工作] 臺灣在牆內擁有至少 7 個有效組織`，玩家盤面已達 7 個牆內有效組織，但狀態仍為「尚未達成」。
  - 根因：action-first 回合流程不再停留於舊 `EVENT` phase，但 `_check_era_trigger()` 仍只掛在舊事件階段分支，因此正常 ACTION→END→下一玩家流程不會檢查時代關卡；臺灣 trigger 資料與牆內計數本身正常。
  - 2026-07-28 已修正：每位玩家正式結束回合時，在既有時代效果 tick 後檢查新時代關卡，讓新啟動的 2 回合效果不會在啟動當下先被扣 1；新增永久 `activated` 履歷，時代效果結束後不會因條件仍成立而重複啟動，個人關卡 UI 也能區分「尚未達成」與「已達成、效果已結束」。
  - 互動排程：新增時代啟動 queue；同一邊界若藏國、滿洲等多個互動關卡同時達成，會依序完成每一條 pending-choice chain，全部完成後才恢復同邊界的 auto event，避免互相覆蓋。啟動採 at-most-once 排程，非預期部分失敗不會重試並重複套用效果。
  - 驗證：`uv run pytest -q scripts/tests/test_era_lifecycle.py` 8/8（6/7 個不同合法臺灣城鎮、完整 2 回合、到期不重觸發、多關卡 queue、藏國／滿洲＋auto event、舊 EraEngine 相容、部分失敗不重複）；`validate_era_rules.py` 5/5、`validate_era_effects_runtime.py` 15/15、`validate_event_cards_runtime.py` 35/35、`validate_event_outcome_timing_audit.py` 28/28、`validate_turn_phase_action_gating.py` 13/13。
  - 正式 UI proof：`uv run --with playwright python scripts/validate_my_era_stage_view.py` 10/10；以 7 個不同合法臺灣城鎮經正式 `advance_turn_phase()` 生命週期啟動，畫面顯示「條件已達成｜剩餘 2 回合」與完整卡面。紀錄：`docs/records/event-cards/MY_ERA_STAGE_VIEW_VALIDATION.{json,md}`、`taiwan_era_stage_lifecycle_active.png`。
  - 回報截圖：`/Users/benmini/.hermes/image_cache/img_5cebd29ce2a5.jpg`、`/Users/benmini/.hermes/image_cache/img_d1a835432b8c.jpg`。

### 2026-07-27 實作規劃（由簡易到困難；依賴優先於表面改字）

1. **DONE｜S｜縮小／重定位右上事件卡**：已縮小且不遮擋地圖 toolbar，保留點擊 Zoom-in 與 responsive 行為。
2. **DONE｜S｜修金門標籤**：金門／廈門使用個別 tooltip direction/offset，已完成一般／移動／建立與多 zoom 驗證。
3. **DONE｜S｜整理側欄按鈕與取消文字**：「建立組織」已移到「確認移動」上方；取消明確標示「取消目的地（保留起點）」並保留合法候選上下文。
4. **DONE｜S–M｜候選 marker 視覺修正**：移動、建立與效果候選採中性色外框／透明填色，不覆蓋既有組織的陣營實心色；browser proof 11/11。
5. **DONE｜M–L｜個人資訊合併為「我的陣營」單一頁內 Tab**：已保留單一 `myFaction` View，移除獨立時代關卡 Tab／View；左欄渲染陣營四區，右欄渲染 viewer-scoped 時代狀態、完整圖片卡面、純文字載入失敗備援與紅軍無關卡提示。
6. **DONE｜M–L（P0）｜修臺灣時代關卡不觸發**：已在正常 action-first lifecycle 加入可靠 era trigger 檢查點，並完成多關卡 pending-choice queue、auto event 延後、一次性啟動履歷、到期後 UI 狀態與完整 runtime/browser 回歸。
7. **DONE｜M–L｜後端投影合法移動目的地**：`move_organization()` 已抽出共用 `_validate_organization_move()`，viewer state 提供 `legal_organization_moves`，前端只消費後端結果且伺服器保留最終檢查。
8. **DONE｜M–L｜聚焦起點／合法目的地＋空白點擊退出**：移動狀態只允許合法目的地或其他己方／共享組織成為新起點；統一 `exitMovementSelection()` 完整清理，事件／支援 choice 仍優先處理。
9. **DONE｜L–XL｜建立「全場每城最多一個組織」核心 invariant**：所有 placement/move/根據地遷移路徑已集中 occupancy 判定，共享組織採單一實體語意；核心 11/11、正式 UI 7/7。
10. **DONE｜S（依賴第 9 項）｜移除單城組織數 UI**：已移除 popup、側欄及城鎮標籤的單城組織數，只保留有無組織、控制者／陣營與全局統計。

- 批次 A–G 已完成；本輪追加後端合法移動投影與地圖狀態機正式 E2E（projection 8/8、UI 11/11）。
- 排序說明保留作歷史紀錄：第 10 項確實在第 9 項 invariant 完成後才落地，未以隱藏 UI 掩蓋資料錯誤。

- [done] A→G 批次已依序實作、驗證並回寫本節；後續工作回到下方實際 active todo，不再擴張 speculative scope。

### P1.5：2026-07-18 自動桌測（20 回合完整局）發現
- 執行方式：`scripts/auto_playthrough_20260718.py` 用 Playwright 同控紅軍/綠線兩頁，逐動作截圖（340 張，`playthrough_screens/`，已 gitignore）＋ JSONL 行動紀錄；紅軍 vs 綠線玩滿 20 回合，紅軍第 21 回合結算獲勝（組織 10 vs 5），全程驅動零卡死。
- [done] 地圖側欄「當前行動玩家」名字染錯色：本日稍早的名字上色改動誤用 `currentPlayerFaction()`（回傳**觀看者**陣營，非當前行動玩家陣營），對手回合時名字會被染成觀看者的顏色（紅軍視角看 GREEN 變紅字）。已修正為以當前行動玩家自身陣營查色；`validate_map_label_zoom_and_base_view.py` 加強為兩個玩家頁面同驗（viewer≠current 那頁必抓得到舊 bug），6/6 連跑 3 次穩定。
- [done] 遊戲結束沒有任何勝利畫面：`state.winner` 前端從未渲染——第 21 回合分出勝負後 HUD 仍顯示「購買階段／當前玩家」，玩家完全不知道遊戲已結束、誰贏了。
  - 2026-07-19 已實作：新增 `#victoryModal` 結束畫面（`renderVictoryModal()`，`state.winner` 出現即顯示）——標題以贏家陣營色顯示「X 獲勝」、副標「陣營｜第 N 回合結算」、共同勝利者（有才顯示）、全玩家最終戰況表（名字染各自陣營色、贏家列金框＋🏆）；「檢視最終盤面」可縮小成頂部徽章、點徽章重開。winner 值為 `red_army` 時解析到紅軍玩家顯示其名字。新增 test-only `POST /test/setup-victory-proof` 供 UI proof。
- [done] 建房者的「行動代號」輸入被無聲忽略：`createRoom()` POST `/create` 不帶名字、伺服器寫死 `'host'`，只有加入者的名字生效。
  - 2026-07-19 已修正：前端 `/create` 帶上輸入框的名字，伺服器採用（空值才 fallback `host`）。
  - 兩項驗證：新增 `python3 scripts/validate_victory_screen_and_creator_name.py`（5/5，連跑 3 次穩定：建房者輸入名生效、綠線贏家 modal 名字染綠、陣營/回合/戰況表正確、縮小徽章與重開、`red_army` 贏家解析為紅軍玩家染紅）；proof `docs/records/playtest-flow/VICTORY_SCREEN_AND_CREATOR_NAME_VALIDATION.{json,md}` + `victory_screen.png`。回歸（map label zoom、detail button、faction display 等走 lobby 建房流程的驗證）全綠。
- 觀察（非 bug）：簡單策略下購買集中在常設區第一格（40 次購買有 30 次宣傳家），隨機購買區的卡幾乎沒被買——之後若要更深入的自動桌測，驅動策略可改成優先買隨機區。
- 2026-07-19 二輪：驅動參數化（`--preset 2p/4p`、`--turns`、`--buy-strategy first/random-first`、`--label`，commit `1a096de`）後跑 **4 人局**（紅軍/綠線/香港/西藏德拉敦，random-first 購買）：完整 20 回合、紅軍第 21 回合結算勝（組織 4/3/1/4）、691 張截圖（`playthrough_screens/4p_run1/`）。購買覆蓋大幅變廣（80 次購買含 21 張奧援卡與 15+ 種行動卡）；反應時機（`cancel_other_player_action`）被觸發 8 次，並以引擎層重現確認「反應視窗開著時 advance 會被伺服器正確回絕」——驅動記到的 8 個「advance disabled」issue 全是驅動搶拍雜訊，非遊戲 bug。本輪無新遊戲問題。

- [done] 區網連線資訊顯示（2026-07-19 使用者需求）：開房的人要能把 IP:port 告訴其他玩家。
  - 實作：新增 `GET /server-info`（UDP connect 技巧偵測區網 IP、port 取自連線的伺服器 socket；偵測失敗回 null）；lobby ROOM CONTROL 新增「區網連線網址（給其他玩家）」欄位＋複製按鈕（`loadLanInfo()`/`copyLanUrl()`，頁面載入即顯示），附提示「其他玩家在同一個 Wi-Fi／區網下，用瀏覽器打開這個網址，再貼上房間代碼加入」。
  - 驗證：新增 `python3 scripts/validate_lan_info_display.py`（3/3，連跑 3 次穩定：endpoint 回傳非 127 的 IPv4＋port 8000、lobby 顯示 `http://IP:port`、複製按鈕回報已複製）；proof `docs/records/playtest-flow/LAN_INFO_DISPLAY_VALIDATION.{json,md}` + `lan_info_display.png`。
  - 注意：伺服器需以 `--host 0.0.0.0` 啟動區網才連得到（現行啟動指令即是）。

- [done] 遊戲畫面「我的陣營」按鈕（2026-07-19 使用者需求）：桌測時常需要查自己陣營的能力/限制/獲勝條件，之前只有 lobby 選陣營時看得到，進遊戲後就查不到了。
  - 實作：`#gameTabs` 新增「我的陣營」按鈕（`openMyFactionModal()`），彈窗顯示陣營名（陣營色標題）＋根據地／能力／規則與限制／獲勝條件四區塊；資料萃取邏輯與 lobby 的 `renderFactionDetails()` 相同（能力排除 setup/restriction 型並入規則區、根據地專屬能力併入能力區），另外處理了 lobby 版本沒遇過的情況：family variant（如維吾爾/西藏子系）只存在 `variant_details` 內、抓不到頂層 `factionOptionById` 時的 fallback 查找。
  - 驗證：新增 `python3 scripts/validate_my_faction_modal.py`（5/5，連跑 3 次穩定：按鈕在遊戲畫面可見、點開後標題染陣營色且四區塊皆有內容、根據地區塊顯示實際根據地、關閉按鈕可收起、換一個資料結構不同的陣營〔香港〕同樣正確渲染）；proof `docs/records/playtest-flow/MY_FACTION_MODAL_VALIDATION.{json,md}` + `my_faction_modal.png`／`my_faction_modal_hong_kong.png`。

- [done] 遊戲畫面「我的時代關卡」入口（2026-07-26 使用者需求）：讓玩家在關卡達成前後都能隨時查看自己的時代關卡，不再只有達成當下的全桌通知。
  - 實作：`#gameTabs` 在「戰況紀錄」右側依序新增「我的陣營」與「我的時代關卡」按鈕（不再用 `margin-left:auto` 推到事件卡所在的最右側）及文字 modal；後端依 WebSocket viewer 的陣營大類只投影 `my_era_stage`，內容包含簡述、觸發條件、紅軍壓制、革命反撲、效果期限與目前是否達成／剩餘回合。紅軍沒有個人時代關卡，入口會明確說明，不會誤配其他陣營資料。
  - 驗證：`uv run --with playwright python scripts/validate_my_era_stage_view.py`（7/7：入口可見、兩個個人資訊按鈕緊鄰戰況紀錄且不與事件卡重疊、相鄰「我的陣營」入口回歸、臺灣未達成關卡全文、關閉、蒙古已達成與剩餘回合、紅軍無個人關卡提示）；proof `docs/records/event-cards/MY_ERA_STAGE_VIEW_VALIDATION.{json,md}` + `my_era_stage_entry_position.png`／`my_era_stage_pending.png`／`my_era_stage_active.png`。

### P2：repo hygiene / validator hygiene
- [todo] 維持 root record-like count = 0。
  - 2026-07-28：將既有 root `North.md` 移至 `docs/records/map-data/NORTH_RULER_TOWNS.md`；root 再次只保留權威專案文件。
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
  - 2026-07-18 追加清償：`scripts/tests/test_action_card_regressions.py` 長期有 24 個測試失敗（回歸訊號完全失效）。逐群排查後**全數為過期測試、無新 runtime bug**——各群對應的刻意設計變更：①建組織改互動式選城鎮（宣傳家/思想家/組織經驗甲乙丙 5 個，測試補 `resolve_build_town` helper）；②奧援卡資源模式=無效果棄置（2026-06-07 `457d3a2`，紅軍奧援兩個資源模式測試改寫為現行語意）；③II 級 OR 裁決＋單卡變體裁決（臺灣/北國奧援 3 個，改用 `variant_index` 指定印刷變體）；④企業人脈可借整個購買區（2026-07-10 `19fc9bd`，4 個，並發現借牌現在是「選定即視同打出」、無資源/行動二段選擇）；⑤情報網自回合選單移除無效的取消選項（`5f50a20`，2 個）；⑥離間=每位其他玩家各 1 張內鬥、至多 3 位（`7bc0d6b`，改 4 人局斷言）；⑦action-first 回合模型（end_turn topdeck 2 個，EVENT→下一位玩家 ACTION）；⑧立場試探屬自由派非 fujian（3 個）；⑨誘導虛耗 optional_trash=移出遊戲非棄牌；⑩點燃熱情費用組成條件使借用情境抽 2。另修 2 個測試環境問題：`make_game`/直接建構的 Game 補 `pin_noop_event`（開局隨機事件〔如一帶一路 auto build〕會污染單元測試）、企業人脈測試改釘死購買區（隨機區出現需目標的武裝/間諜卡會令自動打出失敗）。**87/87 連續 8 次全綠**。
  - 2026-07-18 一併修復 2 支壞掉腳本：`validate_support_cards_runtime_purchase_area.py`（buy_card 需 END 階段的同款過期假設，3/3）與 `validate_playtest_feedback_2026_06_07.py`（宣傳家互動建造後把含 Card 物件的原始 pending_choice 塞進 json.dumps 直接 crash；改為 resolve 建造選擇＋用 state() 序列化，並補 END 階段與事件釘定，5/5）。兩支皆連跑 3 次穩定。

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
  - 2026-07-16/17 後續：偏差 ③（奧援卡張數）與偏差 ②（一般卡張數）已依使用者裁決先後修正並改為硬性檢查——③每種奧援實為兩種印刷變體各 4 張合計 8（見 P1 區塊奧援卡變體條目）；②`action_cards_structured.v1.1.json` 補上 `copies` 欄位（來源 CSV 卡牌張數），`_initial_purchase_deck` 依實體張數展開一般卡池（38 種共 181 張），`sample_53` 的隨機 35 張改為從實體卡池抽出（同名卡可重複，等同實際洗牌），`all_cards` 為完整 64 奧援＋181 一般＝245 張。校驗腳本升至 10/10（新增 `support_taxonomy_copies_match_csv_row_totals`、`structured_general_copies_match_csv` 兩項硬性檢查）。剩餘偏差：①market_mode 組成、④牌庫補充方式（見下一行 2026-07-18 裁決）。
  - 2026-07-18 使用者裁決：偏差①與④**先不改、供日後參考**。①規則書步驟⑧的官方標準牌庫＝「所有間諜/組織/整肅類 47 張保證入庫＋隨機 18 奧援＋隨機 35 其它」共 100 張，介於現有兩模式之間（53 張核心＝純隨機 18+35 不保證間諜/組織/整肅；全部卡牌＝245 張整池）；若日後要做，可取代「53 張核心」或做成 lobby 第三個選項。④規則書的牌庫用盡補充＝「從剩餘行動卡任取一疊補上」，數位化做法是把開局沒被抽進牌庫的卡記成剩卡池、用盡時從中補、剩卡也用完就不再補（符合實體張數上限，已買走的卡不會憑空再現）；現行實作為重建整份初始牌庫的近似版。兩項偏差持續記錄在 C3 校驗的資訊性報告（`docs/records/purchase/PURCHASE_AREA_COMPOSITION_VALIDATION.md`）。
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
