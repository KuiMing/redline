# Next session start prompt（P1 UI 批次 + P2 驗證腳本保養，2026-07-12 版）

> **2026-07-15 狀態更新：本檔的三批工作已全部完成，不需再派工。** ①P1 UI 批次 10/10（放射線、Lobby 複製、地圖陣營顯示＋選取高亮、移動確認、可建數量、棄牌捲動、模仿戰術、中紀委可取消機制、北國奧援兩段瓦解）；②P2 過期驗證腳本 5/5 修綠（過程中挖出並修復「事件延後結算撞整輪繞回」真 bug，commit `ac77e74`）；③第四梯隊已完成 C3 購買區校驗（`a1788a4`）與死代碼 JSON 清理（`4eab237`）。**僅剩 C2（歲月靜好難度選項）與 S6（無限行動處理規則）——兩者都需要完整規則書原文才能動工**，且 C3 的偏差報告（`docs/records/purchase/PURCHASE_AREA_COMPOSITION_VALIDATION.md`）列了 4 個規則書步驟⑧偏差待使用者裁決。權威追蹤見 `TODO.md`。

> 本檔取代 `docs/records/NEXT_SESSION_START_20260711.md`。該檔的「第二批：規則落差修正」與 P1 的後端規則項目（C 組）已於 2026-07-12 **全部完成**（commits `51f1dd7`／`4179f4c`／`7bc0d6b`／`7e2119f`／`543c9f7`／`6075b70`／`cff1c28` 等）。剩餘工作只有：①P1 前端 UI 批次、②P2 過期驗證腳本修復、③第四梯隊保養項。

把下面這段貼到新 session 即可：

```text
請到 `/Users/benmini/.openclaw/workspace/redline`。這次工作分三批，請依序完成，不要交錯進行。後端規則層已全部修完，這次的重點是前端 UI；改前端時不要動 server/ 的規則邏輯（有問題先回報，不要自行改規則）。

===== 全程 git 紀律（必守）=====
- 開工前先 `git status --short`。repo 裡有大量既有的無關 dirty/untracked 檔案（docs/records/ 下的 event-cards、purchase、phase-flow 瀏覽器紀錄、playtest-flow/TURN_PHASE_ACTION_GATING_VALIDATION.{json,md} 等），不屬於你的工作範圍，絕不能混進 commit。
- **禁止使用 `git add -A`、`git add .`、`git add *` 等整包全加的指令**；一律先用 `git diff HEAD -- <檔案>` 確認每個檔案的 diff 只含本次修正，再明確列出檔名 `git add <file1> <file2> ...`。
- commit 用 staged-only 方式（選擇性 stage 後直接 `git commit -m "..."`）；若用 `git commit -- <路徑>`，注意它會把該路徑「工作目錄當下的完整內容」重新 stage，commit 前務必確認該檔工作目錄 diff 就是你要的內容。
- 每完成 1 項（或邏輯相關的幾項）就單獨 commit 一次，不要累積。
- commit 後用 `git show --stat` + `git status --short` 確認只有預期檔案入庫、無關檔案原封不動。

===== 第一批：P1 Playtest UI 批次 =====

權威追蹤來源是 `TODO.md` 的「P1：LAN / end-to-end playtest feedback」區塊（每項有回報情境、期望、需檢查位置）；前三項另有規劃書 `docs/records/playtest-feedback/PLAN_P1_UI_FIXES_20260709.md`（含程式碼位置與建議做法）。每項完成都要：root cause、修正摘要、驗證指令與 browser proof（放 `docs/records/...`），並把 `TODO.md` 對應項目改 [done]。

0. 【先做】放射狀直線修正收尾：這個修正的程式碼「已經在 working tree 但未 commit」——`static/leaflet_game_map.html`、`static/leaflet_game_map_logic.js` 是 modified，proof（docs/records/map-ui/MAP_NO_RADIAL_LINES_20260709_065808.*）與 `scripts/validate_map_no_radial_lines.py` 是 untracked。請先看懂該 diff、重跑驗證腳本確認仍通過，然後把這 5+ 個檔案明確列名 commit。若驗證不過才需要修。
1. 移動確認視窗：選定組織後點可移動城鎮，先跳確認視窗；確認才送 move，取消要保留選擇狀態（不可影響事件/卡牌 pending choice 的選點流程）。
2. Lobby 房間代碼複製保留一個，移除最上方橫幅的重複複製入口（static/index.html + app.js copyRoomId 綁定）。
3. 移動高亮／成本需 faction-aware + cost-aware：後端已改為「翻牆花2點且僅能1格、目的城鎮須適用移動者陣營、赤臘角機場航線（香港限定，赤臘角→臺北/倫敦/卡加利/多倫多，花2點）」；前端可移動城鎮高亮、路線視覺化、剩餘移動點顯示要跟後端一致（不適用的城鎮不可高亮、跨牆/機場要顯示成本2）。後端行為見 scripts/validate_wall_crossing_movement.py 與 TODO.md 對應條目。
4. 地圖已建立組織的城鎮／根據地直接顯示所屬陣營（地名標籤 + 圓圈填色用陣營代表色；base marker 與一般城鎮樣式一致）。
5. 顯示「目前還有幾個城鎮可以建立組織」，數字要跟實際可點擊/可建立名單一致。
6. 奧援卡卡面：把「資源」按鈕改成「詳情」，點開顯示 I/II/III 級完整效果文字（奧援卡只能當行動用，不應有資源按鈕）。effect_text 資料不足時回查 data/raw/support_cards.csv。
7. 大量棄牌選擇／展示區可捲動（貿易戰加劇情境；modal/panel overflow）。
8. 紅軍能力「紀委」視窗關閉 ≠ 動作結束：關閉只是取消/返回，玩家應可重新開啟能力選擇；檢查其他紅軍能力分支是否一致。
9. 北國奧援兩段式瓦解：關閉/離開選擇視窗後應仍可從地圖繼續選目標完成兩步瓦解（或明確取消整個效果），不可卡住階段；可參考先前 `情報網` 關閉後仍可地圖瓦解的既有 close behavior。
10. 模仿戰術：打出後沒有跳出可選卡牌清單。後端 imitate/topdeck 流程已存在，優先懷疑前端 choice modal 接線；若無合法目標也要有明確提示，不能沒回饋。
11. 香港根據地遷移 UI：後端已有 WS action `relocate_base` 與免費窗口旗標 `hk_free_base_relocation`（state 有曝露）。需要：①側欄「遷移根據地」按鈕（機場路徑：花2次遷移，隨時可用）；②「香港抗暴之戰」結算後、下一回合前的免費遷移提示（旗標為 true 時顯示，目的地限 臺北/倫敦/卡加利/多倫多）。
12. 勝利宣告畫面：後端已在第20輪翻頁瞬間宣告（state 有 `winner` 與 `co_winners`）；前端要有 finished modal 顯示勝利者與共同勝利者，不能讓遊戲畫面停在原地沒有回饋。

===== 第二批：P2 過期驗證腳本修復 =====

這些腳本在「修正之前」就已經 FAIL（已用 git stash 基準比對確認非近期修正造成），是腳本假設過期，不是遊戲邏輯錯誤。修復方向是更新腳本情境假設，讓它們重新反映現行正確行為；若修的過程發現真正的邏輯 bug，先回報再動 server/。
1. scripts/validate_turn_phase_action_gating.py（目前 5/15；另外注意 docs/records/playtest-flow/TURN_PHASE_ACTION_GATING_VALIDATION.{json,md} 是它的舊輸出、目前是 dirty 狀態，修好重跑後一起 commit）。
2. scripts/validate_event_cards_runtime.py（settle_round_event helper 早於「整輪結算」改動）。
3. scripts/validate_era_effects_runtime.py。
4. scripts/validate_action_card_end_turn_topdeck_runtime.py（phase 推進假設過期）。
5. scripts/validate_faction_abilities_phase5.py 的 華文傳媒 案例。

===== 第三批（做得完再做）：第四梯隊保養 =====
- C3：購買區組成資料校驗腳本（data/raw CSV vs 程式購買區組成）。
- C2：歲月靜好「至多抽除5張」難度選項（需先回查規則書原文再實作）。
- S6：無限行動處理規則（需先回查完整規則書，整理成疑問回報，不要自行假設）。
- `凝聚共識`/`武裝集團` 的死代碼 JSON 條件步驟清理。

執行規範：
- 每項都要有 root cause、修正摘要、驗證指令與 proof（比照 TODO.md 現有條目風格）；UI 項目要有 browser proof（截圖或自動化紀錄）。
- 完成一項就更新 TODO.md；做不完全部沒關係，做到哪裡就把「已完成/進行中/待處理」確實記錄到 TODO.md，方便下一個人接手。

備註：`TODO.md` 全程是權威追蹤來源；`docs/records/playtest-feedback/PLAN_P1_UI_FIXES_20260709.md` 是第一批前三項的細部依據；兩份 rules-audit 盤點報告（20260710 / SECOND_PASS_20260711）已全部完成、僅供背景查閱，不要重做裡面的項目。
```
