# 規劃書：P1 Playtest UI 三項修正（2026-07-09）

來源：`docs/records/playtest-feedback/NEXT_SESSION_START.md` 的啟動 prompt，對應 `TODO.md`「P1：LAN / end-to-end playtest feedback」區塊中三個 `[todo]` 項目：

1. 地圖移動/可達城鎮高亮不要畫大量放射狀直線（TODO.md 現行行號約 61-66，標題「任何移動選擇／移動後可達城鎮高亮都不應畫大量放射狀直線」）。
2. 選定組織後點可移動城鎮應先跳出移動確認視窗（TODO.md 現行行號約 103-107，標題「移動到可移動城鎮前應跳出確認視窗」）。
3. Lobby 房間代碼複製功能保留一個，移除最上方重複入口（TODO.md 現行行號約 161-165）。

範圍邊界：只處理這三項。P1 區塊其他 `[todo]`（`誘導虛耗`、`紅軍奧援`、`模仿戰術`、`離間`、`組織經驗甲`、`點燃熱情`、`北國奧援`、第 20 回合勝利判定、本土社團多抽、棄牌捲動、事件卡陣營顯示、奧援卡詳情按鈕等）本次不動，避免範圍蔓延。

---

## 0. 開始前必讀：目前 repo 髒狀態（務必先處理，不要跳過）

執行者開工前務必先跑 `git status --short` 並對照下列說明，這不是泛泛提醒，而是目前 repo 的實際狀態記錄：

- `TODO.md` 同時有 **staged（M）** 與 **unstaged（M）** 兩層變更。Staged 的那層是較舊版本，把項目 1 標成 `[done]` 且描述只提到「宣傳家」；unstaged 的那層才是現在的 `TODO.md`（我方才讀取的內容），把項目 1 重新標成 `[todo]` 並補充「不只限於宣傳家」的範圍說明，同時新增了項目 2 的補充句與整個項目 3。**請以 unstaged／目前工作目錄的 `TODO.md` 內容為準**（也就是本規劃書引用的版本）。
- `static/leaflet_game_map_logic.js`、`static/leaflet_game_map.html` 已經有 **staged** 的修改：`renderMovementHighlights()` 裡兩段畫放射狀 `L.polyline` 的程式碼已經被移除，且 HTML 的 script cache-busting query 已改成 `?v=map-no-radial-lines-20260709`。也就是說，**項目 1 的核心程式碼修正很可能已經做好了，只是還沒 commit**，且看起來也沒有把對應的 `[done]` 狀態同步進目前的 `TODO.md`（目前 `TODO.md` 又把它改回 `[todo]`）。
- `docs/records/map-ui/MAP_NO_RADIAL_LINES_20260709_065808.{json,md,png}` 與 `scripts/validate/validate_map_no_radial_lines.py` 也已經 staged（新檔案），是對應上述修正的驗證產物。
- 另外還混著明顯無關的既有 dirty 檔案：`docs/records/playtest-flow/TURN_PHASE_ACTION_GATING_VALIDATION.{json,md}`、`docs/records/support-cards/SUPPORT_CARD_EFFECTS_RUNTIME_VALIDATION.json`（unstaged M），以及一大批 untracked 的 `docs/records/event-cards/`、`docs/records/phase-flow/`、`docs/records/purchase/` 底下的紀錄檔案與資料夾，還有 `docs/records/playtest-feedback/NEXT_SESSION_START.md` 本身也是 untracked。這些都**不屬於本次三項任務**，commit 時不能被夾帶進去。

建議的第一步操作（不會遺失任何工作內容）：

```bash
git status --short
git diff --cached -- TODO.md static/leaflet_game_map_logic.js static/leaflet_game_map.html
git restore --staged .        # 只是把 index 攤平回 working tree，不會丟棄任何內容
git status --short            # 確認全部變成 unstaged / untracked，方便後面逐項重新 stage
```

`git restore --staged .` 只清空暫存區、不改動工作目錄檔案，是安全、可逆的操作；目的是避免「舊版已 staged 內容」與「新版工作目錄內容」疊在一起造成誤判。之後所有工作都在 unstaged 狀態下進行，每項修完再各自 `git add` 對應檔案。

---

## 1. 地圖移動/可達城鎮高亮不要畫放射狀直線

### 已確認的現況（供執行者直接查證，不需要重新從頭找）

- 畫放射狀線的邏輯在 `static/leaflet_game_map_logic.js` 的 `renderMovementHighlights(townName, options)`（目前約在 480 行起）。可達道路目標迴圈（約 526-534 行）與可達鐵路目標迴圈（約 536-544 行）原本各自呼叫一次 `L.polyline([[origin...]], [[target...]], {...}).addTo(highlightLayer)`，把選定城鎮到「每一個」可達城鎮都畫一條亮線 → 這就是回報截圖裡「大量放射狀直線」的成因。
- **`renderMovementHighlights()` 是全遊戲唯一一個負責畫移動/建立高亮的共用函式**，呼叫點包括：`selectTownForCurrentMapAction`（一般點選城鎮）、`finalizeMoveSelection`（移動完成後重新高亮）、`applyGameStateToMap` 內的狀態刷新（約 815、957 行）、以及三個測試用 hook（`__selectTownForTest`、`__moveFromToForTest`、`__dissolveFromSharedForTest`，約 1003-1050 行）。因為所有「移動」或「顯示可移動城鎮」的流程最終都會走這個函式，**目前 staged 的修法（直接刪掉那兩段 `L.polyline`）在架構上本來就不是宣傳家專屬修法**，理論上已滿足「不只限於宣傳家」的需求。
- 建立組織用的安全屋可建立目標（約 546-561 行，`buildHighlightLayer`）本來就只用 `L.circleMarker`（圓圈），沒有畫線，不受影響。
- 地圖底圖的道路/鐵路連線（`renderMap()` 內約 760-770 行的 `L.polyline`，畫在 `roadLayer`/`railLayer`）是常駐地圖圖層，**必須保留**，不要跟高亮用的暫時亮線搞混。
- 全檔案搜尋 `L.polyline` 目前應該只剩這一處常駐道路/鐵路繪製；如果修完之後 grep 出現其他新的動態 `L.polyline`，代表有新的放射線來源要一併處理。

### 執行者要做的事

1. 依第 0 節先攤平 git 狀態，重新檢視 `static/leaflet_game_map_logic.js`／`static/leaflet_game_map.html` 目前 diff 是否就是「移除那兩段 `L.polyline`」且沒有夾帶其他非預期改動；若乾淨就沿用，不用重寫。
2. `grep -n "L.polyline" static/leaflet_game_map_logic.js`，確認除了 `renderMap()` 裡畫常駐道路/鐵路那一處以外，沒有其他地方還在動態畫放射線（含未來可能新增的建立/瓦解/事件效果高亮路徑）。
3. 現有 `scripts/validate/validate_map_no_radial_lines.py` 只用 `__selectTownForTest('臺北')` 測了單一情境（單一玩家、單一城鎮，沒有特別驗證同時有道路+鐵路多個可達目標、也沒有模擬「先建立組織再自動重新高亮」這種宣傳家報告情境）。請擴充同一支腳本（或在裡面新增第二個情境函式），至少涵蓋：
   - 一個同時有道路與鐵路多個可達目標的城鎮（重現原始截圖那種「多目標」情境）。
   - 呼叫 `window.__moveFromToForTest(from, to)` 完成一次實際移動後，`finalizeMoveSelection` 觸發的重新高亮（對應「移動後可達城鎮高亮」）同樣沒有新增亮線。
   - 斷言邏輯沿用現有寫法：比對 `L.Polyline` 圖層總數 selecting 前後不變、且不存在 `color==='#ffd166'/weight===6` 或 `color==='#67e8f9'/weight===7` 這兩種舊放射線特徵值。
4. 重新產生驗證證據（新時間戳的 json/md/png，放 `docs/records/map-ui/`）；舊的 `MAP_NO_RADIAL_LINES_20260709_065808.*` 可以保留當作既有佐證，不必刪除，但不要只沿用舊證據交差。
5. `node --check static/leaflet_game_map_logic.js` 確認語法正確。
6. 更新 `TODO.md` 對應項目為 `[done]`，內容需包含：root cause（`renderMovementHighlights()` 對每個可達目標多畫一條 `L.polyline`）、修正摘要（明確寫「移除放射線繪製；因高亮邏輯是單一共用函式，修正涵蓋所有移動/建立高亮進入點，不限宣傳家」）、驗證指令、證據路徑（含新舊 proof 路徑）。

---

## 2. 選定組織後點可移動城鎮應先跳出確認視窗

### 已確認的現況

- 實際觸發移動的地方在 `static/leaflet_game_map_logic.js` 的 `renderMap()` 內，城鎮 marker 的 `marker.on('click', () => {...})`（目前約 791-806 行）。邏輯是：
  ```js
  const moveOption = moveOptionForTown(t.name);
  if (selectedTown && moveOption) {
    const result = sendMoveAction(selectedTown, t.name, moveOption.mode);
    ...
    return;
  }
  ```
  **目前一點可達城鎮就立刻送出移動，完全沒有確認步驟** —— 這正是回報「容易誤點」的原因。同一個 handler 後面（約 799-803 行）還有一個「快速點擊安全屋可建立目標」的分支，也是點了就直接送出 `build`；這個分支**不在本次三項任務範圍內**，先不要動，除非之後使用者另外要求。
- `sendMoveAction(fromTown, toTown, mode)`（約 587-599 行）是實際送出 WebSocket `{action:'move', from, to, mode}` 的地方，維持不變即可，改動應該發生在「呼叫它之前」要不要先跳確認。
- 這個 repo 已經有一個現成、風格一致的「選取 → 側欄出現確認用按鈕 → 使用者再按一次才真的執行」模式，用在建立組織／瓦解組織上：`static/leaflet_game_map.html` 約 120-125 行的 `#directBuildBtn` / `#dissolveBtn` + `static/leaflet_game_map_logic.js` 的 `refreshDirectBuildUi()`（約 671-725 行）。**建議直接沿用這個既有模式**，而不是另外發明一套 modal 系統，理由：風格一致、不需要新增彈窗元件、也不會牽動 `static/app.js` 那邊的 modal/pending_choice 邏輯（TODO 項目裡也特別提醒「需避免影響事件/卡牌 pending choice 的選點流程」）。

### 建議設計（給執行者的具體落地方式，細節可依實作彈性調整，但需求本身不能少）

1. 新增前端狀態 `pendingMoveTarget`（例如 `{ from, to, mode }`），marker click handler 命中 `moveOption` 時，**不要**直接呼叫 `sendMoveAction`，改成設定 `pendingMoveTarget` 並呼叫一個新函式（例如 `refreshMoveConfirmUi()`）刷新 UI；**不要**清除 `selectedTown`、也不要重跑 `resetMoveSelection()` / `renderMovementHighlights(null)`。
2. 在 `static/leaflet_game_map.html` 側欄（可放在 `#directBuildBtn`/`#dissolveBtn` 附近的同一張 `.card` 內）新增兩個元素，例如：`#confirmMoveBtn`（預設 disabled，文字如「確認移動」）、`#cancelMoveBtn`（文字「取消」）、以及一個提示區（可比照 `#directBuildHint` 命名 `#confirmMoveHint`）。
3. `refreshMoveConfirmUi()`：當 `pendingMoveTarget` 存在時，enable 兩顆按鈕、提示文字寫明「確認移動 {from} → {to}（{mode}）」；`pendingMoveTarget` 為空時兩顆按鈕 disabled、提示回到預設文字。
4. `#confirmMoveBtn` 的 click handler：呼叫 `sendMoveAction(pendingMoveTarget.from, pendingMoveTarget.to, pendingMoveTarget.mode)`，成功後清空 `pendingMoveTarget` 並刷新 UI。
5. `#cancelMoveBtn` 的 click handler：**只清空 `pendingMoveTarget`** 並刷新 UI；`selectedTown`、目前的可達城鎮高亮（`selectedMoveTargets` 等）必須維持原狀 —— 這是 TODO 明確要求的「取消要保留選擇狀態」，也是最容易做錯的地方，請特別檢查取消後使用者是否還能直接點另一個可達城鎮或原城鎮重新操作，不需要重新選取起點。
6. 不要影響同一個 click handler 裡其他分支：`selectTownForCurrentMapAction`（一般選城鎮）、既有的安全屋快速建立分支、事件/卡牌 pending choice 相關的 `supportChoiceTownNearLatLng` 等點選流程都應維持原行為。
7. 測試 hook：`window.__moveFromToForTest`（約 1026 行）目前直接呼叫 `sendMoveAction`，繞過了 marker click handler，可以保留當作「跳過確認、直接測試移動結果」的既有 low-level hook，不用改。但因為它繞過真正的使用者互動路徑，**無法用來驗證這次要修的確認流程**。請新增一個新的測試 hook（例如 `window.__clickMoveTargetForTest(townName)`），內容等同「模擬使用者點擊某個可達城鎮 marker」，實際觸發 marker 的 click handler，讓瀏覽器驗證腳本可以斷言：點擊後 `pendingMove` 不變、`window.__lastMoveRequest` 不變（代表還沒送出）、確認按鈕出現且可點；點確認後才真的送出；另外開一輪點取消，斷言 `selectedTown`/高亮不變且沒有送出 move。
8. 撰寫新驗證腳本（例如 `scripts/validate/validate_move_confirmation.py`，可參考 `scripts/validate/validate_map_no_radial_lines.py` 的 Playwright 寫法），至少覆蓋：
   - 點選可達城鎮後，尚未送出 `move`（可用 `mapWs.send` 的 spy 或觀察 `pendingMove`/`window.__lastMoveRequest` 狀態）。
   - 按下確認後才送出 `move`，且 payload 的 `from/to/mode` 正確。
   - 按下取消後，`selectedTown` 與高亮狀態不變，且沒有送出任何 `move`。
   - 截圖存證放 `docs/records/map-ui/`（或視覺較相關可放 `docs/records/playtest-feedback/`，兩者皆可，統一放一處即可）。
9. 更新 `TODO.md` 對應項目為 `[done]`：root cause（marker click 直接送出 move，沒有確認步驟）、修正摘要、驗證指令、proof 路徑。

---

## 3. Lobby 房間代碼複製功能保留一個

### 已確認的現況

- `static/index.html` 目前有兩處複製入口：
  - 最上方橫幅（約 35-39 行）：`#lobbyRoomBannerCode`（本身是可點擊的 `<button>`，onclick 也是 `copyRoomId()`，title 是「點擊複製房間代碼」）+ `#copyRoomBannerBtn`（明確標「複製」的按鈕，onclick 同樣是 `copyRoomId()`）。
  - 下方「建立/加入房間代碼」輸入列（約 65-66 行）：`#roomId` 輸入框 + `#copyRoomBtn`（「複製」按鈕，onclick 也是 `copyRoomId()`）。
- `copyRoomId()`（`static/app.js` 約 286 行起）、`currentRoomCode()`（約 216 行）、`selectRoomCodeForManualCopy()`（約 243 行）都是共用邏輯，會優先用 `#roomId` 這個 input 的值/焦點，只有在 input 不存在時才 fallback 用 `bannerCode`。也就是說**只要 `#roomId` 存在，移除橫幅上的複製按鈕不會影響複製功能本身**。
- 確認過 `static/style.css` 的 `#lobby.room-active` 規則（約 176-182 行）只會把 `.lobby-brand`/`.lobby-briefing` 往下推，**不會隱藏**下方輸入列；也就是說即使房間已建立、橫幅顯示出來時，下方 `#roomId` + `#copyRoomBtn` 仍然同時存在畫面上，保留它當唯一複製入口是安全的，不會出現「橫幅顯示時反而找不到複製按鈕」的情況。

### 執行者要做的事

1. 移除 `static/index.html` 橫幅裡明確標示「複製」的按鈕 `#copyRoomBannerBtn`。
2. 保留 `#lobbyRoomBannerCode` 作為房間代碼的**純顯示**用途（讓玩家仍能一眼看到代碼），但要把它從「可點擊複製」改成單純顯示：移除 `onclick="copyRoomId()"`，同時把 `static/app.js` 的 `syncLobbyRoomCode()`（約 220-233 行）裡 `bannerCode.title = ... '點擊複製房間代碼 ...'` 的提示文字一併改掉（例如改成單純顯示房間代碼、不再暗示可點擊複製），避免留下「看起來還能點擊複製」的視覺誤導。是否要連元素標籤都從 `<button>` 改成 `<span>` 由執行者依風格判斷，但功能上（拿掉 onclick、拿掉點擊複製提示）是必須做的部分。
   - 這裡有一個小判斷：如果覺得「保留橫幅顯示但拿掉複製功能」不夠乾脆，也可以考慮乾脆整段橫幅拿掉；但 TODO 原文是「移除最上方**重複複製入口**」，字面上只要求移除複製功能重複，沒有要求拿掉整個房間代碼顯示橫幅，因此預設建議做法是保留顯示、拿掉複製，除非使用者/回報者後續明確要整個橫幅都拿掉。
3. `static/app.js` 的 `selectRoomCodeForManualCopy()`（約 243-262 行）已經是先看 `#roomId`、找不到才 fallback `bannerCode`，這段不需要改（保留 fallback 邏輯本身無害，即使 bannerCode 之後改成非按鈕元素也還能被選取複製文字）。
4. `static/style.css` 檢查 `.lobby-room-banner-copy`（約 169 行起）等只服務被刪按鈕的規則是否變成死樣式，需要的話一併清掉；`.lobby-room-banner-code` 相關樣式視覺上維持即可，若原本有 `cursor:pointer` 之類暗示可點擊的樣式，因為元素不再可點擊，也應該一併拿掉。
5. 撰寫/擴充瀏覽器驗證（例如新增 `scripts/validate/validate_lobby_single_copy_button.py`）：載入 lobby、建立或帶入一個房間代碼、斷言畫面上只剩一個可用的複製按鈕（`#copyRoomBtn`）、點擊後透過既有的 `window.__lastRoomCopyResult` 確認複製成功、並確認橫幅上原本的複製按鈕已經不存在。截圖存證放 `docs/records/`（可放 `docs/records/playtest-feedback/` 或新開一個 lobby-ui 目錄，統一放一處）。
6. 更新 `TODO.md` 對應項目為 `[done]`：root cause（橫幅與輸入列各自綁定同一份 `copyRoomId()`，形成重複入口）、修正摘要、驗證指令、proof 路徑。

---

## 執行順序建議

依 `NEXT_SESSION_START.md` 給的優先順序 1 → 2 → 3 進行；但因為項目 1 的程式碼修正大機率已經做完（只差重新驗證與 TODO 同步），建議流程是：

1. 先做第 0 節的 git 攤平與盤點。
2. 項目 1：驗證/補強既有修正 → 產生新 proof → 更新 TODO。
3. 項目 2：實作確認/取消流程 → 新增測試 hook 與驗證腳本 → 更新 TODO。
4. 項目 3：移除重複複製入口 → 驗證 → 更新 TODO。
5. 全部完成後，`git status --short` 檢查一次，**只 `git add`** 這三項牽涉到的檔案（`static/leaflet_game_map_logic.js`、`static/leaflet_game_map.html`、`static/index.html`、`static/app.js`、`static/style.css`、新增的 `scripts/validate_*.py`、對應 `docs/records/...` 證據檔、以及 `TODO.md` 這三個項目的 hunk），確認沒有夾帶第 0 節列出的無關 dirty/untracked 檔案，再一次性 commit。commit message 建議依三項內容摘要（例如列點寫清楚三項各自的修正），並如既有慣例附上驗證指令與 proof 路徑於 `TODO.md`，不需要在 commit message 裡重複整段。

## 驗收檢查清單（給執行者收尾自我檢查用）

- [ ] `git status --short` 顯示的 staged 內容只包含這三項相關檔案，無 `docs/records/event-cards|phase-flow|purchase` 等既有無關項目。
- [ ] 項目 1：`node --check static/leaflet_game_map_logic.js` 通過；擴充後的 `validate_map_no_radial_lines.py` 涵蓋多目標與「移動後重新高亮」情境並 PASS；grep 全檔沒有非預期新增的動態 `L.polyline`。
- [ ] 項目 2：確認流程送出前不觸發 WebSocket `move`；確認後才送出且 payload 正確；取消後 `selectedTown`/高亮完全不變；不影響事件/卡牌 pending choice 選點路徑；新驗證腳本 PASS。
- [ ] 項目 3：畫面上只剩一個可用「複製」按鈕；複製功能仍可用（`window.__lastRoomCopyResult` 驗證）；橫幅代碼顯示仍在，但不再暗示可點擊複製；新驗證腳本 PASS。
- [ ] `TODO.md` 三個項目都改成 `[done]`，各自補上 root cause、修正摘要、驗證指令、proof 路徑。
- [ ] 只有一個（或依需要拆分的）commit，內容乾淨對應這三項。
