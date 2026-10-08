# Joy-Con／搖桿控制

右 Joy-Con（或任何能透過 [`tools/joycon_bridge`](../tools/joycon_bridge/README.md) 送出 `{x, y, buttons}` 的搖桿）作為**額外**輸入來源。滑鼠、觸控、鍵盤完全不變。

## 啟用

右下角 🎮 → 勾選「啟用搖桿控制」。設定（是否啟用、Bridge 位址）存在 `localStorage`（`redline.controller.v1`）。
未啟用時不會建立任何連線、不會接管焦點；控制器未連線時 UI 正常。位址只接受 `ws(s)://127.0.0.1`、`localhost`、`[::1]`。

連線狀態：未啟用／連線中／已連線／訊號中斷（stale，超過 1.5 秒沒收到 frame）／無法連線（自動以 1→8 秒退避重連，也可按「重新連線」）。

## 預設操作

| 輸入 | 動作 |
| --- | --- |
| 右搖桿 | 方向導航（deadzone 0.5；按住有 380ms 延遲後每 140ms 重複一次） |
| A | 確認／啟用目前焦點（呼叫既有 click handler）；**焦點在任何卡牌上時一律只開啟置中卡牌預覽**，不執行、不勾選、不購買 |
| B | 返回／取消——只在目前 UI 本身有可見、可用的取消／關閉按鈕時才作用，否則什麼都不做 |
| B（卡牌） | 焦點在購買區卡牌（方向鍵只停在整張卡牌，checkbox 不進入焦點集合、無黃框）時切換勾選，點擊該卡既有 checkbox；勾選框停用（伺服器權威）則不作用 |
| X（手牌） | 焦點在手牌卡時＝以資源使用：點擊該卡既有「資源」按鈕；按鈕不存在（如一般奧援為「棄置」）、隱藏或停用則不作用 |
| Y（手牌） | 焦點在手牌卡時＝以行動使用：點擊該卡既有「行動」按鈕；隱藏或停用則不作用 |
| R / SR | 下一個／上一個主分頁（大廳則為區塊）；modal 與必選地圖目標時停用 |
| X | 把焦點移到回合操作按鈕（只移動焦點，不觸發；手牌卡焦點時見上；其他卡牌焦點時不作用） |
| Y | 顯示／隱藏操作提示（手牌卡焦點時見上；其他卡牌焦點時 X/Y 完全不作用） |
| `+`、HOME、CAPTURE、ZR、STICK、SL | 不綁定（`+` 特意不綁「結束步驟」） |

第一次有效操作只會把焦點放上去，不會執行。畫面右下角只有一個精簡提示膠囊，不增加頂部窄條。

## 輸入安全

- 搖桿有 deadzone；方向在邊緣立即觸發一次，之後依 repeat 節流。
- 按鍵只在 rising edge 觸發一次。
- 斷線、stale、停用、頁面隱藏、視窗失焦：清空所有 held state。
- 每次（重新）連線的**第一筆 frame 只是 baseline**：已按住的按鍵與已推到底的搖桿都不會觸發，必須先放開。因此重連絕不會自動按下按鈕。

## 架構

```
physical input（bridge WebSocket frame）
  → controller_core.js：normalizeFrame / reduceFrame（deadzone、edge、repeat、baseline）
  → logical actions（move / confirm / cancel / nextSection / prevSection / focusTurnBar / toggleHelp）
  → context router：modal ▸ map ▸ page（routeAction / resolveModalScope）
  → controller_ui.js：只呼叫既有元素的 click()；不建構 action payload、不複製遊戲規則
```

- `static/controller_core.js`：純邏輯，可在 node 測試（`scripts/tests/js/controller_core.test.js`）。
- `static/controller_ui.js`：bridge client、設定與 HUD、DOM 焦點集合、焦點標示（`.rl-pad-focus`，4px 高對比外框，不改版面）、`scrollIntoView`。
- `static/controller_map_adapter.js`：戰略地圖 iframe 端。
- `static/living_room_core.js`（純邏輯，node 可測）＋ `static/controller_living_room.js`（DOM 膠合，透過 `RedlineController.attachLayer` 只在客廳模式接手 page／map scope）：見下方「客廳大螢幕模式」。

### Scope 與優先權

1. 有可見 dialog 時（勝利畫面、卡面預覽、事件揭示、行動提示、對手行動通知、購買確認、陣營能力、卡牌選擇／反應選擇、時代關卡、陣營選擇），**導航只限最高優先權的那一個**，背景控制項不在焦點集合內。B 只點該 dialog 自己現有的取消／關閉按鈕（`MODAL_SCOPES.cancel`）；沒有就不做事。
2. 沒有 dialog 且在戰略地圖分頁 → 地圖 context（見下）。
3. 否則為頁面：分頁、回合按鈕與目前分頁中可見、未停用的語意化控制項（`button`、`a[href]`、`input`、`[role=button]`、卡牌）。`disabled`、`aria-disabled`、不可見的控制項不會取得焦點；「重新開始」連結排除。
4. 有必選的地圖目標（pending choice）時，頁面背景鎖定：分頁與回合按鈕不可用，R/SR 停用。

### 地圖 iframe 協定（版本 `v: 1`）

parent 與 iframe 同源；雙方都驗證 `event.origin === location.origin` 與 `event.source`（parent 驗證是該 iframe 的 `contentWindow`，iframe 驗證是 `window.parent`），版本與 schema 不符一律丟棄。

- iframe → parent：`redline-controller-map-snapshot`
  `{scope: 'none'|'choice'|'move', seq, targets:[{town, role:'choice'|'move'|'origin', x, y}], buttons:[{id,label,x,y,w,h}], focusTown, canCancel}`
  在地圖狀態改變時推送（已合併）。座標是 iframe 內的 client 座標。
- parent → iframe：`redline-controller-command`，`cmd` 為 `snapshot`、`focus {town}`、`clearFocus`、`activate {town}`、`button {id}`、`cancel`；可選 `req`（正整數 request id）。
- iframe → parent：`redline-controller-result` `{cmd, req, ok, reason, via}`，每個指令處理完都回覆；`req` 原樣回傳（沒帶則為 `null`），`via` 為 iframe 實際走的既有控制（按鈕 id，或取消時的 `cancelDissolveChoiceBtn`／`selection`）。
  客廳模式的地圖執行型指令（動作列地圖按鈕、清單選取、清單取消）都帶 `req`，且同時只有一筆等待確認：**只有對上該 `req` 的 `ok:true`（iframe 執行前已重驗）才算執行**，此時才記錄 250ms 冷卻，地圖按鈕與 `via: cancelDissolveChoiceBtn` 的取消再上處理中鎖。沒有 iframe、`ok:false`、1 秒內沒有回覆、過期或對不上的 `req` 一律 fail closed，不記錄冷卻也不上鎖；等待期間其他執行型按鍵被擋下（不重送），回覆或逾時後立即解除。桌面模式不帶 `req`，行為不變。

焦點集合只來自伺服器權威資料，且**每個指令執行當下 iframe 都重新驗證**（parent 的 snapshot 過期或被偽造也不會讓非法目標可 action）：

- pending choice 目標：`supportChoiceHighlight.towns`（伺服器 pending choice 投影），限可見且已知城鎮。
- 移動：目前選取來源的 `legal_organization_moves`（`selectedMoveTargets`），以及可行動的來源城鎮。
- 缺狀態、不是自己的回合、有 pending choice 卻沒有地圖 highlight → 沒有任何目標（fail-closed）。
- 按鈕只限白名單 `directBuildBtn`、`confirmMoveBtn`、`dissolveBtn`、`cancelDissolveChoiceBtn`，且必須存在、可見、未停用。

A 對城鎮走既有 marker `click` 路徑（選取來源／預備移動目的地／選擇 pending choice 候選），對按鈕呼叫既有 `click()`；是否真的移動、建立或瓦解仍由既有確認按鈕與伺服器驗證決定。B 只會：點可見且啟用的「取消瓦解」，或取消目前選取（既有「點地圖其他地方取消」流程）；兩者都沒有就不做事。焦點城鎮以黑底＋黃色雙圈與名稱標籤標示，必要時 `panInside`。

## 客廳大螢幕模式（living-room，P0）

同一 route、同一 DOM、同一套遊戲 action：`html[data-display="living-room"]` 只切換 CSS 版面層並加上搖桿的區域導航。
開啟方式：網址加 `?display=living-room`（`?display=desktop` 切回），或 🎮 設定面板「顯示模式」。存於 `localStorage`（`redline.display.v1`），不依螢幕尺寸自動切換。桌面模式（預設）行為、版面與上表完全不變。

- **安全區與字級**：舞台等比縮放後再留 5% title-safe（`resizeStage` 乘 0.9）；文字 16–28 設計單位，720p／1080p／4K 只差銳利度。卡牌列改為單列水平捲動並縮小卡面，卡名以大字標在卡上；完整卡面用 A 預覽（放大到畫面高約 80%）。
- **兩層導航**（指揮中心）：區域層只在可用區域間移動——玩家狀態、常設購買區、隨機購買區、陣營能力（可見時）、手牌、戰略地圖、玩家動態、情境動作列。必選地圖目標時只剩「戰略地圖」與動作列。

| 輸入 | 區域層 | 區域內（內容層） |
| --- | --- | --- |
| 搖桿 | 在區域間移動（邊緣距離＋重疊，確定性） | 卡牌列／動作列依索引左右（上下換列），地圖清單上下；到邊界停住 |
| A | 進入區域（還原上次項目；「戰略地圖」直接切到地圖分頁） | 卡牌＝查看；控制項＝既有 click；動作列＝執行（危險項目先開確認單）；地圖清單＝選取 |
| B | 不做事 | 購買卡＝勾選／取消；手牌＝不做事；其他＝回區域層；地圖清單有既有取消流程時＝取消 |
| X／Y | X＝跳到動作列、Y＝說明 | 手牌 X 資源／Y 行動；購買卡完整 no-op；其他同區域層 |
| R／SR | 下一個／上一個區域 | 同左 |
| PLUS | 跳到動作列（只移焦點、絕不執行；預設落在第一個非危險格） | 同左 |
| ZR | 指揮中心以外的分頁＝回指揮中心 | 回區域層 |

- **情境動作列**：固定在畫面下緣，只鏡射目前可見且啟用的既有控制（`openPurchaseConfirmBtn`、`clearPurchaseSelectionBtn`、`topdeckRightBtn`、`redArmyAbilityBtn`、最近聚焦手牌的「棄置」、`advanceStepBtn`；地圖分頁再加 iframe snapshot 的 `confirmMoveBtn` 等白名單按鈕）。格子不接受滑鼠（原按鈕照常可點），按下當下重驗，失效即 no-op。
- **危險操作確認**：結束步驟／結束行動／結束回合與「棄置」由控制器觸發時開確認單，預設焦點「返回」；按「確認」時再驗原按鈕可用才 `click()`。滑鼠與鍵盤點原按鈕不變。
- **地圖兩段式清單**：來源（可行動城鎮）→ A → 該來源的伺服器合法目的地（依消耗、道路先於鐵路排序）→ A 只預備移動 → PLUS 到動作列「確認移動 甲→乙」→ A。清單只來自 iframe 權威 snapshot（協定新增選用欄位 `selected`、`pending`、移動目標的 `mode`／`cost`，有給就嚴格驗證），iframe 執行每個指令前仍重驗；沒有 snapshot 或目標時清單為空、A 無作用。滑鼠仍可直接操作地圖。
- **防誤觸**：送出遊戲動作後到下一份 state（或 1.5 秒）前不再送出 A／X／Y／B 類指令（處理中鎖）；任何**實際執行**（click 既有控制、開啟預覽／確認單、B 勾選、iframe 確認成功的地圖選取／按鈕／取消、成功進入區域，以及客廳模式下 modal 內的 A）之後 250ms 內不接受下一個執行型按鍵（fail-closed 的 no-op 不啟動冷卻；方向、ZR、PLUS、回區域層與 modal 的 B 不受影響）；重繪造成的焦點換項目後 300ms 內忽略 A／X／Y；重繪後同 key 留原位、key 消失留同區域同索引、區域空了回該區域層，永不跨區域、永不自動落在危險格。斷線／stale／重連 baseline 沿用上方規則。

## 測試

```bash
node --test scripts/tests/js/controller_core.test.js scripts/tests/js/living_room_core.test.js   # 或透過 pytest 包裝
uv run python -m pytest scripts/tests/test_controller_core_js.py scripts/tests/test_living_room_core_js.py scripts/tests/test_joycon_bridge.py
uv run python scripts/validate/validate_joycon_controller.py   # 瀏覽器 E2E（mock bridge），截圖到 /tmp/redline-joycon-proof/
uv run python scripts/validate/validate_living_room_controller.py   # 客廳模式 E2E（固定按鍵序列、三種解析度），截圖到 /tmp/redline-living-room-proof/
```

E2E 以 mock WebSocket 取代 bridge 並注入 frame，驗證真實頁面的焦點、A click、B cancel、modal 優先權、斷線重連不誤觸、stale、地圖目標焦點與 fail-closed。**這不能取代 Mac 實機 Joy-Con 驗證**（見 `TODO.md`）。

## 限制

- https 頁面可能擋 `ws://127.0.0.1`（mixed content），詳見 bridge README；目前只完整支援 http dev／區網頁面。
- S2B1 欄位位置與 `y` 軸方向尚未用實機確認。
- 文字輸入欄位只能聚焦，無法用搖桿輸入文字。
