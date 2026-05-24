# Redline TODO

最後更新：2026-05-23

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
  - 盤點結論：raw 檔共有 13 張事件列、8 張時代關卡列；目前 structured data 有 20 rows（15 base + 5 副本），runtime event deck 依 base structured rows 與 raw 張數建立為 27 張。
  - canonical scope 建議：目前 MVP 應明確視為「15 張 structured base rows 進 runtime event deck」；若要宣稱完整 raw event/era，需先決定 8 張 raw 時代關卡是以 era-stage mechanics 還是 event-deck cards 納入。
  - 已知缺口：8 張時代關卡中有 6 張完全未 structured；`[反賊]公知世代的終結`、`[臺灣]綏靖派反對介入對岸` 目前只是 event-like MVP adaptation，仍需 canonical 決策。

- [todo] 修正 structured event data 與 raw card text 不一致的事件。
  - 2026-05-23：已修正 `貿易戰加劇`：structured trigger 改為購買 `英美奧援` 或總費用 4 點以上卡牌，success 改為從棄牌堆選 1 張置頂；新增 runtime primitive `buy_card` / `topdeck_from_discard` 與 validator proof。
  - 2026-05-24：已修正 `紅軍權貴出逃`：structured success 改為 `trash_from_hand_or_discard`，成功後可從手牌或棄牌堆選 1 張移除；新增 runtime validator 與正式 browser UI proof。
  - 優先比對並修正：`烏魯木齊七五事件`、`上海合作組織`、`一帶一路 南洋`、`一帶一路 天方`。
  - 已知差異：
    - `貿易戰加劇` raw 是購買英美奧援或 4 點以上卡牌，成功從棄牌堆選 1 張置頂；2026-05-23 已修正並補 runtime validator。
    - `紅軍權貴出逃` raw 成功是從手牌或棄牌移除 1 張；2026-05-24 已修正為 `trash_from_hand_or_discard` 並補 runtime/UI proof。
    - `烏魯木齊七五事件` raw trigger 是回合結束時牆內有組織，成功是在己方組織 1 格內免費建 1 個；目前 structured 是 `build_organization` trigger + generic build choice。
    - `上海合作組織` raw 是紅軍對北國城鎮組織使用武裝/間諜距離增加為 5 格；目前是 generic `ignore_distance`。
    - `一帶一路 南洋` / `一帶一路 天方` raw 是紅軍免費在指定區域無視距離建立 1 個組織；目前是 generic `ignore_distance`。
  - 驗收：更新 `data/events_structured.v1.1.json` 與 effect vocabulary；新增/更新 validator 證明 raw text 與 structured effect 對齊。

- [todo] 補齊缺少的 trigger/effect runtime primitives。
  - 可能需要新增：購買事件 trigger（指定卡類/費用門檻）、回合結束狀態 trigger、從棄牌堆選牌置頂、從手牌/棄牌移除、區域限定免費建組織、卡種/區域/距離限定 modifier、持續回合 modifier。
  - 驗收：`scripts/validate_event_cards_runtime.py` 擴充到逐張事件或逐 effect primitive 覆蓋；所有新增效果都有 deterministic runtime assertions。

- [todo] 補事件卡玩家選擇 UI / map proof。
  - 範圍：`discard_self`、`red_dissolve`、`build_organization`、從棄牌堆選牌、從手牌/棄牌移除、區域建組織等需要玩家指定目標的效果。
  - 2026-05-24：已補 `貿易戰加劇` 從棄牌堆選牌置頂的正式 browser UI proof；確認既有 pending card choice modal 可顯示 `event_topdeck_from_discard` 並 resolve，截圖與 state/log proof 在 `docs/records/event-cards/TRADE_WAR_UI_PROOF_2026_05_24.{md,json}`。
  - 2026-05-24：已補 `紅軍權貴出逃` 從手牌或棄牌堆選 1 張移除的正式 browser UI proof；確認既有 pending card choice modal 可顯示手牌/棄牌堆來源標籤並 resolve。
  - 原則：只重用既有 pending choice modal / target choice map highlight 架構；不要重做情報網 highlight。
  - 驗收：每一種互動型 effect 至少有一個正式 browser UI proof，截圖與紀錄放 `docs/records/event-cards/`。

- [todo] 事件卡完整化總驗證。
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
