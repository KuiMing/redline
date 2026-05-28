# Redline TODO

最後更新：2026-05-28

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

- [todo] 修正 structured event data 與 raw card text 不一致的事件。
  - 2026-05-24 整理：目前應分三層追蹤，不要把「MVP 可 playtest」等同「所有 raw event/era 已完整實作」。
    1. `raw 13 張事件卡`：目前 runtime deck 的主要對齊目標；13 張事件卡 raw/structured 對齊已於 2026-05-24 完成。
    2. `structured MVP adaptation`：`公知世代的終結`、`臺灣綏靖派反對介入` 目前在 structured data 裡是 event-like MVP adaptation，但 raw 檔屬於時代關卡，需 canonical 決策後再決定是否保留此 adaptation 或改成 era-stage mechanics。
    3. `raw 8 張時代關卡`：尚未完整納入 runtime；若要宣稱完整 event/era，需另開 P0 設計 runtime primitive、持續效果與 UI proof。
  - raw 13 張事件卡盤點：
    - 已修正並有針對性 validator/proof：`貿易戰加劇`、`紅軍權貴出逃`、`烏魯木齊七五事件`、`上海合作組織`、`一帶一路 南洋`、`一帶一路 天方`。
    - 2026-05-24 已逐張重審且 raw/structured 對齊：`全國人大召開`、`香港抗暴之戰`、`重大災難`、`藏印邊境軍事對峙`、`東突厥集中營`、`北京政爭`。
    - 明確待修 raw/structured mismatch：目前無；`一帶一路 南洋`、`一帶一路 天方` 已於 2026-05-24 修正。
  - raw 8 張時代關卡盤點：
    - 2026-05-26：已決定 8 張 raw 時代關卡 canonical scope 為 **era-stage mechanics**，不是事件牌堆卡；8 張皆保留在 `data/era_structured.v1.1.json`，並已補上雙方效果宣告：`red_suppression`（紅軍壓制）與 `revolution_counterattack`（革命反撲）。
    - 已新增 `scripts/validate_era_canonical_scope.py`，驗證 raw 8 張皆由 structured era-stage 表示、raw bracketed era rows 未進 event deck、靜態常設牌效果明確標記 consume static supply；紀錄：`docs/records/event-cards/ERA_CANONICAL_SCOPE_AUDIT_2026_05_26.{md,json}`。
    - 2026-05-26：已完成第一批不需新 UI 的 era effect runtime：`add_static_cards_to_discard` 會透過 static supply 加入棄牌堆（目前 `蒙古`/`臺灣` 內鬥、`滿洲` 分神皆受供應量上限保護）、`draw` immediate 會在時代啟動時立即抽牌（`哈薩克` 抽 2）、`reduce_purchase_cost` 會由 active era modifier 套用到購買成本（`香港` 武裝類卡牌 -2 資金）。新增 validator / proof：`scripts/validate_era_effects_runtime.py`、`docs/records/event-cards/ERA_EFFECTS_RUNTIME_VALIDATION.{md,json}`。
    - 2026-05-26：已完成第二批跳過香港 UI 的 no-new-UI / gameplay-hook era runtime：`hand_card_resource_bonus`（蒙古宣傳類手牌作資源時 +1 宣傳）、`gain_resource_on_play_card`（維吾爾打出武裝類卡牌 +2 宣傳）、`gain_resource_on_build_in_region`（臺灣在臺灣城鎮建組織 +1 宣傳）、`build_count_draw_bonus`（反賊同回合建立第 3 個組織後抽 1 張、每回合一次）、`restrict_ignore_distance_build`（哈薩克啟動後對牆內城鎮不再允許無視距離建組織）。已擴充 `scripts/validate_era_effects_runtime.py` 與 `docs/records/event-cards/ERA_EFFECTS_RUNTIME_VALIDATION.{md,json}` 至 10 項 runtime checks。
    - 2026-05-26：已完成第一個互動型 era runtime：藏國紅軍壓制 `red_discard_to_build_near_target`。啟動後紅軍先用既有 pending card choice 棄 1 張手牌，再重用既有 pending town choice / map highlight / 側欄建立組織架構，在藏國玩家藏國組織 1 格內免費建立 1 個紅軍組織；validator/proof 擴充至 11 項 runtime checks。
    - 2026-05-27：已完成維吾爾互動型 era runtime：紅軍打出武裝類卡牌後，先沿用既有武裝牌目標棄牌 pending choice；棄牌完成後接續 `era_red_bonus_dissolve_target`，重用既有 target choice / map highlight 架構，讓紅軍選擇 1 個自身組織 1 格內的維吾爾組織瓦解。`scripts/validate_era_effects_runtime.py` 擴充至 12 項 runtime checks；proof records：`docs/records/event-cards/UYGHUR_ERA_RED_DISSOLVE_MAP_UI_PROOF_2026_05_27.{md,json}` 與同名 PNG。
    - 2026-05-27：已完成滿洲互動型 era runtime：革命反撲 `inspect_deck_top_and_reorder` 會檢視滿洲玩家牌庫頂 7 張，重用既有 multi-card pending choice modal 依點選順序選 2 張置頂；紅軍壓制 `分神` 仍遵守 static supply，只能消耗既有常設供應。`scripts/validate_era_effects_runtime.py` 擴充至 13 項 runtime checks；proof records：`docs/records/event-cards/MANCHURIA_ERA_REORDER_UI_PROOF_2026_05_27.{md,json}` 與 `MANCHURIA_ERA_REORDER_CHOICE_UI_2026_05_27.png`。
    - 2026-05-27：已完成香港紅軍壓制 `bonus_discard_on_red_card` runtime 與正式 browser UI proof：紅軍打出間諜類卡牌並完成原本間諜瓦解 pending choice 後，接續重用既有 card choice / multi-card choice 架構，要求香港玩家棄 1 張手牌；香港革命反撲武裝購買 -2 資金仍維持。`scripts/validate_era_effects_runtime.py` 擴充至 14 項 runtime checks；runtime proof records：`docs/records/event-cards/ERA_EFFECTS_RUNTIME_VALIDATION.{md,json}`；UI proof records：`docs/records/event-cards/HONG_KONG_ERA_RED_DISCARD_UI_PROOF_2026_05_27.{md,json}` 與兩張同名前綴 PNG。
    - 2026-05-27：已補齊時代關卡達成大彈窗的官方說明文字 fallback：`era_notification` 會合併 structured era payload，測試端點也改用同一 payload；香港達成彈窗不再顯示 `（暫缺）`。`scripts/validate_era_effects_runtime.py` 新增 notification 文案完整性檢查；proof records：`docs/records/event-cards/HONG_KONG_ERA_NOTIFICATION_UI_PROOF_2026_05_27.{md,json,png}`。
    - 2026-05-27：已依要求補齊香港以外 7 張時代關卡達成通知正式 browser UI 截圖，並新增通用 `/test/setup-era-notification-proof` proof endpoint；proof records：`docs/records/event-cards/ERA_NOTIFICATION_ALL_NON_HONG_KONG_UI_PROOF_2026_05_27.{md,json}` 與 `ERA_NOTIFICATION_{MONGOLIA,TIBET,KAZAKH,UYGHUR,MANCHURIA,REBELS,TAIWAN}_UI_PROOF_2026_05_27.png`。
    - 2026-05-27：已收斂事件牌堆 canonical scope：移除 `公知世代的終結`、`臺灣綏靖派反對介入` 兩張 event-like MVP adaptation；這兩張只保留在 `data/era_structured.v1.1.json` 作為 era-stage mechanics。事件 runtime deck 回到 raw 13 張事件列共 25 張，時代關卡不進事件牌堆；`scripts/validate_event_card_canonical_scope.py` 與 `EVENT_CARD_CANONICAL_SCOPE_AUDIT_2026_05_27.{md,json}` 已更新。
    - 2026-05-28：藏國紅軍壓制已由「棄 1 張→建 1 個」修正為「可棄任意張→同數建立」：紅軍使用既有 multi-card pending choice 選 1～可建城鎮數張手牌，棄牌後依序重用既有 `era_red_build_near_target` town choice / Strategic Map sidebar 建立同數組織；validator 擴充至 15 項 runtime checks，並補正式 browser UI proof：`docs/records/event-cards/TIBET_ERA_RED_MULTI_DISCARD_BUILD_UI_PROOF_2026_05_28.{md,json}` 與 `TIBET_ERA_RED_MULTI_{DISCARD_MODAL,BUILD_MAP}_UI_2026_05_28.png`。
    - 仍待 runtime 落地：其餘需要新互動或更細 gameplay hook 的時代效果尚未接完。
  - 建議下一步順序：raw 13 張事件卡 deck 對齊已完成；8 張時代關卡已完成 canonical/data declaration；第一批 no-new-UI era runtime 已完成；接著分批實作需要 pending choice / map highlight / play-card hook 的剩餘 era effects。
  - 2026-05-23：已修正 `貿易戰加劇`：structured trigger 改為購買 `英美奧援` 或總費用 4 點以上卡牌，success 改為從棄牌堆選 1 張置頂；新增 runtime primitive `buy_card` / `topdeck_from_discard` 與 validator proof。
  - 2026-05-24：已修正 `紅軍權貴出逃`：structured success 改為 `trash_from_hand_or_discard`，成功後可從手牌或棄牌堆選 1 張移除；新增 runtime validator 與正式 browser UI proof。
  - 2026-05-24：已修正 `烏魯木齊七五事件`：structured trigger 改為回合結束時牆內有己方組織，success 改為在己方組織 1 格內免費建 1 個；新增 end-turn state / nearby build runtime validator 與正式 browser UI proof。
  - 2026-05-24：已修正 `上海合作組織`：structured effect 改為 `scoped_card_range`，限定紅軍 `armed` / `spy` 卡對北國城鎮組織距離為 5 格；runtime validator 已覆蓋 structured 對齊、自動 modifier、武裝卡 5 格北國可用且非北國不放行、間諜 target choice 僅列北國目標。
  - 2026-05-24：已修正 `一帶一路 南洋` / `一帶一路 天方`：structured effect 改為 `build_organization_in_region`，限定紅軍在 `southeast_asia` / `middle_east` 區域免費無視距離建立 1 個組織；新增 runtime validator 與正式 Strategic Map UI proof。
  - 2026-05-24：已完成剩餘 6 張事件卡 raw/structured 逐張對齊審核：`全國人大召開`、`香港抗暴之戰`、`重大災難`、`藏印邊境軍事對峙`、`東突厥集中營`、`北京政爭`；新增 runtime validator 覆蓋全國人大成功/失敗、藏印邊境成功、東突厥成功/失敗，審核紀錄在 `docs/records/event-cards/EVENT_CARD_REMAINING_SIX_RAW_ALIGNMENT_AUDIT_2026_05_24.{md,json}`。
  - 2026-05-24：已套用規則釐清：事件卡 mission「任務條件」只由非紅軍陣營行動推進；紅軍行動／抽牌／購買／建組織／移動不會完成 mission trigger。自動型紅軍事件（如 `一帶一路`、`上海合作組織`）仍依各自 event effect 處理。
  - 2026-05-24：已讓紅軍也能從事件面板明確看到非紅軍任務結果；mission 結算後 payload/UI 顯示 `非紅軍任務成功` 或 `非紅軍任務失敗，紅軍效果生效`，並補紅軍視角正式 browser UI proof。
  - 已知差異：
    - `貿易戰加劇` raw 是購買英美奧援或 4 點以上卡牌，成功從棄牌堆選 1 張置頂；2026-05-23 已修正並補 runtime validator。
    - `紅軍權貴出逃` raw 成功是從手牌或棄牌移除 1 張；2026-05-24 已修正為 `trash_from_hand_or_discard` 並補 runtime/UI proof。
    - `烏魯木齊七五事件` raw trigger 是回合結束時牆內有組織，成功是在己方組織 1 格內免費建 1 個；2026-05-24 已修正為 `end_turn_state` + `build_organization_near_own` 並補 runtime/UI proof。
    - `上海合作組織` raw 是紅軍對北國城鎮組織使用武裝/間諜距離增加為 5 格；2026-05-24 已修正為 scoped `armed`/`spy` range modifier 並補 runtime validator。
    - `一帶一路 南洋` / `一帶一路 天方` raw 是紅軍免費在指定區域無視距離建立 1 個組織；2026-05-24 已由 generic `ignore_distance` 修正為區域限定免費建組織。
  - 驗收：更新 `data/events_structured.v1.1.json` 與 effect vocabulary；新增/更新 validator 證明 raw text 與 structured effect 對齊。

- [done] 補齊缺少的 trigger/effect runtime primitives。
  - 2026-05-26：已確認並補強事件卡 runtime primitives：購買事件 trigger（指定卡名／總費用門檻）、回合結束狀態 trigger、從棄牌堆選牌置頂、從手牌／棄牌移除、卡種／區域／距離限定 modifier 均有 deterministic runtime 覆蓋；本次另補 `duration` / `remaining_turns` 持續回合 modifier runtime，事件 modifier 會依回合結束倒數並支援跨回合持續。
  - 驗證紀錄：`docs/records/event-cards/EVENT_CARDS_RUNTIME_VALIDATION.{json,md}`（35 passed，含 `test_event_modifier_duration_ticks_across_turns` 與 `test_event_runtime_primitive_inventory_is_covered`）。

- [todo] 補事件卡玩家選擇 UI / map proof。
  - 範圍：`discard_self`、`red_dissolve`、`build_organization`、從棄牌堆選牌、從手牌/棄牌移除、區域建組織等需要玩家指定目標的效果。
  - 2026-05-24：已補 `貿易戰加劇` 從棄牌堆選牌置頂的正式 browser UI proof；確認既有 pending card choice modal 可顯示 `event_topdeck_from_discard` 並 resolve，截圖與 state/log proof 在 `docs/records/event-cards/TRADE_WAR_UI_PROOF_2026_05_24.{md,json}`。
  - 2026-05-24：已補 `紅軍權貴出逃` 從手牌或棄牌堆選 1 張移除的正式 browser UI proof；確認既有 pending card choice modal 可顯示手牌/棄牌堆來源標籤並 resolve。
  - 2026-05-24：已補 `烏魯木齊七五事件` 在己方組織 1 格內免費建組織的正式 browser UI proof；確認既有 pending town choice modal 顯示 `天津` / `石家莊`，resolve 後 `viewer 組織 2` 且事件面板為成功 1/1。
  - 2026-05-24：已讓 `event_build_organization` 的 `town_choice` 重用既有 pending choice / map highlight 架構，在 modal 提示可切到戰略地圖查看城鎮位置，並於地圖用橘色外框標出 `天津` / `石家莊` 可建組織城鎮；proof records：`docs/records/event-cards/URUMQI_BUILD_CHOICE_MAP_HIGHLIGHT_UI_PROOF_2026_05_24.{md,json}`。
  - 2026-05-24：已補乾淨版烏魯木齊地圖 proof：proof endpoint 改用非立場試探陣營，且 pending choice 期間會隱藏陣營能力 overlay，避免 `立場試探` 混入正式 UI 證據；另補一張 active `戰略地圖` tab 且地圖區域可見的正式 UI 截圖；proof records：`docs/records/event-cards/URUMQI_BUILD_CHOICE_MAP_HIGHLIGHT_UI_PROOF_CLEAN_2026_05_24.{md,json}`。
  - 2026-05-24：已把 `event_build_organization` town choice 改為沿用正式 `戰略地圖` 側欄建組織操作；pending choice 自動切到地圖並用既有 map highlight 標示可建城鎮，玩家選取城鎮後按「在目前城鎮建立組織（事件卡）」完成 resolve，不再使用 choice modal 兩段式確認；正式 browser UI 截圖與 state proof 在 `docs/records/event-cards/URUMQI_BUILD_DIRECT_MAP_SIDEBAR_UI_2026_05_24.png`、`URUMQI_BUILD_DIRECT_MAP_SIDEBAR_UI_PROOF_2026_05_24.{md,json}`。
  - 2026-05-24：已補 `一帶一路 南洋` / `一帶一路 天方` 區域限定免費建組織正式 Strategic Map UI proof；確認兩張事件都重用 `event_build_organization` pending choice / map highlight，且 pending choice 分別帶 `region=southeast_asia` / `region=middle_east`、`free=true`、`ignore_distance=true`。proof records：`docs/records/event-cards/BELT_ROAD_SOUTHEAST_MAP_BUILD_UI_PROOF_2026_05_24.{md,json}`、`BELT_ROAD_MIDDLE_EAST_MAP_BUILD_UI_PROOF_2026_05_24.{md,json}`。
  - 2026-05-26：已補藏國時代關卡 `era_red_build_near_target` 正式 Strategic Map UI proof；確認時代關卡 pending town choice 重用既有 map highlight / 側欄建立組織流程，proof records：`docs/records/event-cards/TIBET_ERA_RED_BUILD_MAP_UI_PROOF_2026_05_26.{md,json}` 與同名 PNG。
  - 2026-05-27：已補維吾爾時代關卡 `era_red_bonus_dissolve_target` 正式 Strategic Map UI proof；確認紅軍打出武裝牌後的追加瓦解 target choice 重用既有 target choice / map highlight 架構，proof records：`docs/records/event-cards/UYGHUR_ERA_RED_DISSOLVE_MAP_UI_PROOF_2026_05_27.{md,json}` 與同名 PNG。
  - 2026-05-27：已補滿洲時代關卡 `era_inspect_deck_top_and_reorder` 正式 modal UI proof；確認檢視牌庫頂 7 張、選 2 張置頂重用既有 multi-card pending choice modal，並以 `確認置頂 2 張` 完成 resolve。proof records：`docs/records/event-cards/MANCHURIA_ERA_REORDER_UI_PROOF_2026_05_27.{md,json}` 與 `MANCHURIA_ERA_REORDER_CHOICE_UI_2026_05_27.png`。
  - 2026-05-24：已補 `全國人大召開` 失敗後 `event_red_dissolve` 的正式 map-highlight UI proof；紅軍目標選擇 modal 會列出其他玩家牆內組織，並重用既有 `support-targets` 地圖高亮流程在戰略地圖標出 `viewer｜北京`。proof records：`docs/records/event-cards/NATIONAL_PEOPLE_CONGRESS_RED_DISSOLVE_MAP_HIGHLIGHT_UI_PROOF_2026_05_24.{md,json}` 與同名 PNG。
  - 原則：只重用既有 pending choice modal / target choice map highlight 架構；不要重做情報網 highlight。
  - 驗收：每一種互動型 effect 至少有一個正式 browser UI proof，截圖與紀錄放 `docs/records/event-cards/`。

- [done] 事件卡完整化總驗證。
  - 2026-05-27：事件牌堆 canonical scope、event/era validators、compileall、diff check、root record-like count 已完成；事件牌堆不再包含 raw 時代關卡 adaptation。
  - 必跑：事件卡 runtime validator、`python3 -m compileall -q server scripts static`、`git diff --check`、root record-like count 檢查。
  - 若有 UI 變更：補正式 browser UI screenshot proof。
  - 若要 LAN playtest：重啟 server 綁 `0.0.0.0:8000` 並確認 `TCP *:8000 (LISTEN)`。

### P1：事件卡 MVP 後 UI polish / playtest feedback
- [todo] Playtest 後再決定事件面板是否需要展開/收合、詳細文字、或事件歷史紀錄。
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
  - 驗證紀錄：`docs/records/lobby/`。
- [done] 常設購買區可購買性、常設牌不混入隨機購買區、手牌資源/行動按鈕 listener 修正。
- [done] 紅軍奧援起始牌庫歸屬修正。
  - 2026-05-25：已修正 `紅軍奧援` 不應進隨機奧援購買樣本，而應作為紅軍起始牌庫專屬卡；Lobby 選定紅軍後會重建起始牌庫，確保實際選紅軍玩家擁有 1 張 `紅軍奧援`，非紅軍與購買牌庫不含該卡。驗證紀錄：`docs/records/support-cards/SUPPORT_PURCHASE_DECK_RUNTIME_VALIDATION.{md,json}`。
- [done] 紅軍陣營能力 runtime / UI 說明補齊。
  - 2026-05-25：已實作紅軍能力 `統戰部`、`政工部`、`國安部`、`中紀委` runtime 與前端按鈕；紅軍能力彈窗文字說明區已列出四項效果說明。驗證紀錄與正式 browser UI proof：`docs/records/event-cards/RED_ARMY_FACTION_ABILITIES_RUNTIME_VALIDATION.{md,json}`、`RED_ARMY_FACTION_ABILITIES_HELP_UI_PROOF_2026_05_25.{md,json}`、`RED_ARMY_FACTION_ABILITIES_HELP_UI_2026_05_25.png`。
  - 2026-05-25：已修正 `政工部` 從錯誤的 `內宣` 改為將常設牌 `內鬥` 放到目標玩家牌庫頂，並遵守 static supply（供應歸零時不憑空新增）。補 runtime validator 與正式 browser UI proof：`docs/records/event-cards/RED_ARMY_POLITICAL_WORK_INTERNAL_CONFLICT_UI_PROOF_2026_05_25.{md,json}`、`RED_ARMY_POLITICAL_WORK_INTERNAL_CONFLICT_HELP_UI_2026_05_25.png`、`RED_ARMY_POLITICAL_WORK_INTERNAL_CONFLICT_RESULT_UI_2026_05_25.png`。
  - 2026-05-25：已補紅軍特殊規則 runtime：4 種紅軍能力視同行動卡可被既有取消反應牌取消；同一玩家同回合成功瓦解紅軍根據地 2 次後根據地消失且不可重建；紅軍組織移動不得離開紅軍發展空間。驗證紀錄：`docs/records/event-cards/RED_ARMY_SPECIAL_RULES_RUNTIME_VALIDATION.{md,json}`。
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
