# Joy-Con／搖桿控制

右 Joy-Con（或任何能透過 [`tools/joycon_bridge`](../tools/joycon_bridge/README.md) 送出 `{x, y, buttons}` 的搖桿）作為**額外**輸入來源。滑鼠、觸控、鍵盤完全不變。

## 啟用

右下角 🎮 → 勾選「啟用搖桿控制」。設定（是否啟用、Bridge 位址）存在 `localStorage`（`redline.controller.v1`）。
未啟用時不會建立任何連線、不會接管焦點；控制器未連線時 UI 正常。位址只接受 `ws(s)://127.0.0.1`、`localhost`、`[::1]`。

連線狀態：未啟用／連線中／已連線／訊號中斷（stale，超過 1.5 秒沒收到 frame）／無法連線（自動以 1→8 秒退避重連，也可按「重新連線」）。

## 預設操作（桌面模式）

客廳大螢幕模式另有一套內容導航與專用快捷鍵，見下方「客廳大螢幕模式」。

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
| `+`、HOME、CAPTURE、ZR、STICK、SL | 桌面模式不綁定（`+` 特意不綁「結束步驟」） |

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
  → logical actions（move / confirm / cancel / nextSection / prevSection / focusTurnBar / toggleHelp；客廳模式另有 factionAbility / endStep / nextZone / zoneBack）
  → context router：modal ▸ map ▸ page（routeAction / resolveModalScope）
  → controller_ui.js：只呼叫既有元素的 click()；不建構 action payload、不複製遊戲規則
```

- `static/controller_core.js`：純邏輯，可在 node 測試（`scripts/tests/js/controller_core.test.js`）。
- `static/controller_ui.js`：bridge client、設定與 HUD、DOM 焦點集合、焦點標示（`.rl-pad-focus`，4px 高對比外框，不改版面）、`scrollIntoView`。
- `static/controller_map_adapter.js`：戰略地圖 iframe 端。
- `static/living_room_core.js`（純邏輯，node 可測：路由、方向焦點排除規則、R／SR 區段環、按鍵提示列、閘門、地圖清單）＋ `static/controller_living_room.js`（DOM 膠合，透過 `RedlineController.attachLayer` 只在客廳模式接手 page／map scope，以及事件卡／時代關卡說明 modal 內的 R／SR）：見下方「客廳大螢幕模式」。

### Scope 與優先權

1. 有可見 dialog 時（勝利畫面、卡面預覽、事件揭示、行動提示、對手行動通知、購買確認、陣營能力、卡牌選擇／反應選擇、時代關卡、陣營選擇），**導航只限最高優先權的那一個**，背景控制項不在焦點集合內。B 只點該 dialog 自己現有的取消／關閉按鈕（`MODAL_SCOPES.cancel`）；沒有就不做事。
2. 沒有 dialog 且在戰略地圖分頁 → 地圖 context（見下）。
3. 否則為頁面：分頁、回合按鈕與目前分頁中可見、未停用的語意化控制項（`button`、`a[href]`、`input`、`[role=button]`、卡牌）。`disabled`、`aria-disabled`、不可見的控制項不會取得焦點；「重新開始」連結排除。
4. 有必選的地圖目標（pending choice）時，頁面背景鎖定：分頁與回合按鈕不可用，R/SR 停用。

### 地圖 iframe 協定（版本 `v: 1`）

parent 與 iframe 同源；雙方都驗證 `event.origin === location.origin` 與 `event.source`（parent 驗證是該 iframe 的 `contentWindow`，iframe 驗證是 `window.parent`），版本與 schema 不符一律丟棄。

- iframe → parent：`redline-controller-map-snapshot`
  `{scope: 'none'|'choice'|'move', seq, targets:[{town, role:'choice'|'move'|'origin', x, y, act?}], buttons:[{id,label,x,y,w,h}], focusTown, canCancel}`
  在地圖狀態改變時推送（已合併）。座標是 iframe 內的 client 座標。選用欄位 `act`（客廳模式 Y 用）＝該目標的既有主要操作：
  choice 目標依 pending choice 為 `build`／`dissolve`；move 目標為 `move`；origin 只有可瓦解共享組織時為 `dissolve`。
  與 role／scope 不相容的 `act` 會讓整份 snapshot 作廢。
- parent → iframe：`redline-controller-command`，`cmd` 為 `snapshot`、`focus {town}`、`clearFocus`、`activate {town}`、`button {id}`、`cancel`、`act {town, id}`（`id` 只限 `directBuildBtn`／`confirmMoveBtn`／`dissolveBtn`）；可選 `req`（正整數 request id）。
- iframe → parent：`redline-controller-result` `{cmd, req, ok, reason, via}`，每個指令處理完都回覆；`req` 原樣回傳（沒帶則為 `null`），`via` 為 iframe 實際走的既有控制（按鈕 id，或取消時的 `cancelDissolveChoiceBtn`／`selection`）。
  客廳模式的地圖執行型指令（Y 地圖操作、清單選取、清單取消）都帶 `req`，且同時只有一筆等待確認：**只有對上該 `req` 的 `ok:true`（iframe 執行前已重驗）才算執行**，此時才記錄 250ms 冷卻，Y 地圖操作與 `via: cancelDissolveChoiceBtn` 的取消再上處理中鎖。沒有 iframe、`ok:false`、1 秒內沒有回覆、過期或對不上的 `req` 一律 fail closed，不記錄冷卻也不上鎖；等待期間其他執行型按鍵被擋下（不重送），回覆或逾時後立即解除。桌面模式不帶 `req`，行為不變。
- `act` 在 iframe 內：(1) 用權威資料重驗 town 是目前目標、其 `act` 對應的既有按鈕等於 `id`（否則 `not-a-target`／`action-mismatch`）；(2) 按鈕尚未作用在該 town 時，走與 A／滑鼠相同的既有 marker click 選取／預備；(3) 再驗一次目標仍在、按鈕可見啟用且作用在該 town，才 `click()` 既有按鈕（否則 `button-unavailable`）。失敗時不點任何按鈕、不送出遊戲動作（最多留下與按 A 相同的選取／預備狀態）。

焦點集合只來自伺服器權威資料，且**每個指令執行當下 iframe 都重新驗證**（parent 的 snapshot 過期或被偽造也不會讓非法目標可 action）：

- pending choice 目標：`supportChoiceHighlight.towns`（伺服器 pending choice 投影），限可見且已知城鎮。
- 移動：目前選取來源的 `legal_organization_moves`（`selectedMoveTargets`），以及可行動的來源城鎮。
- 缺狀態、不是自己的回合、有 pending choice 卻沒有地圖 highlight → 沒有任何目標（fail-closed）。
- 按鈕只限白名單 `directBuildBtn`、`confirmMoveBtn`、`dissolveBtn`、`cancelDissolveChoiceBtn`，且必須存在、可見、未停用。

A 對城鎮走既有 marker `click` 路徑（選取來源／預備移動目的地／選擇 pending choice 候選），對按鈕呼叫既有 `click()`；是否真的移動、建立或瓦解仍由既有確認按鈕與伺服器驗證決定。B 只會：點可見且啟用的「取消瓦解」，或取消目前選取（既有「點地圖其他地方取消」流程）；兩者都沒有就不做事。焦點城鎮以黑底＋黃色雙圈與名稱標籤標示，必要時 `panInside`。

## 客廳大螢幕模式（living-room）

同一 route、同一 DOM、同一套遊戲 action：`html[data-display="living-room"]` 只切換 CSS 版面層並加上搖桿的內容導航與專用快捷鍵。
開啟方式：網址加 `?display=living-room`（`?display=desktop` 切回），或 🎮 設定面板「顯示模式」。存於 `localStorage`（`redline.display.v1`），不依螢幕尺寸自動切換。桌面模式（預設）行為、版面與上表完全不變。

- **安全區與字級**：舞台等比縮放後再留 5% title-safe（`resizeStage` 乘 0.9）；文字 16–28 設計單位，720p／1080p／4K 只差銳利度。卡牌列改為單列水平捲動並縮小卡面，卡名以大字標在卡上；完整卡面用 A 預覽（放大到畫面高約 80%）。
- **方向鍵只在內容資料間**：內容區＝常設購買區、隨機購買區、陣營／根據地候選（只有非能力鈕的內容選項時才出現）、手牌、玩家動態（縮小在左下角的對手通知）；戰略地圖分頁是地圖目標清單；其他分頁是該分頁內容。
  方向焦點**永遠不會**落在：手牌卡內的「資源」「行動」「棄置」、結束行動／紅軍能力（回合列）、六個全域分頁、購買卡 checkbox、陣營能力發動鈕、按鍵提示列（`LR.isDirectionalExcluded`）。手牌與購買卡只以整張卡取得焦點。
- **六個全域區段只由 R／SR 選取**：指揮中心 → 戰略地圖 → 戰況紀錄 → 我的陣營 → 事件卡 → 時代關卡（依分頁列順序循環；隱藏或停用的分頁跳過；有多個時代關卡時各是一站）。
  分頁＝既有分頁切換；事件卡／時代關卡＝既有開啟說明 modal，在這兩個唯讀說明 modal 內再按 R／SR 會用該 modal 既有的關閉控制收起並前往下一站。其他 modal 一律維持 scope lock（R／SR 不作用）。
  有必選地圖目標時：在戰略地圖 R／SR 停用；在其他分頁 R／SR 只會回到戰略地圖，其他分頁沒有內容區。
- **兩層導航**：區域層用搖桿在內容區之間移動（邊緣距離＋重疊，確定性），A 進入；內容層在區內移動，到邊界停住，不跨區。

| 輸入 | 區域層 | 內容層 |
| --- | --- | --- |
| 搖桿 | 在內容區間移動 | 卡牌列依索引左右（上下換列）、地圖清單上下；到邊界停住 |
| A | 進入區域（還原上次項目） | 卡牌＝查看；內容控制項＝既有 click；地圖清單＝選取／預備（不執行） |
| B | 不做事 | 購買卡＝勾選／取消；**一般奧援手牌＝既有「棄置」（危險確認）**，其他手牌不做事；地圖清單有既有取消流程時＝取消；其他＝回區域層 |
| X | 不做事 | 手牌＝資源；其他不做事 |
| Y | 說明 | 手牌＝行動；**購買卡＝既有「購買所選」**；**地圖目標＝建立組織／確認移動／瓦解組織**；其他＝說明 |
| R／SR | 下一個／上一個全域區段 | 同左 |
| PLUS（+） | **發動既有陣營能力** | 同左 |
| CAPTURE | **既有結束行動／結束步驟（危險確認）** | 同左 |
| STICK（按下搖桿） | **下一個內容區**（直接進入、還原上次項目；只移焦點） | 同左 |
| ZR | 指揮中心以外的分頁＝回指揮中心 | 回區域層 |

- **專用快捷鍵**（全部只點擊當下可見、啟用、合法的既有控制；按下當下重驗，失效即 fail closed 並在狀態列顯示原因）：
  - CAPTURE：`advanceStepBtn`（結束行動／結束回合／開始行動階段）→ 危險確認單，預設焦點「返回」；連按不會開第二張確認單；確認單開著時按鈕失效或文字改變（換了步驟）就自動關閉不執行。
  - PLUS：`#factionActionButtons` 內的既有發動鈕（例如「發動 賭徒耳語」）或 `redArmyAbilityBtn`，**恰好一個可用**才點擊；沒有或多於一個不做事。點擊後若沒有開啟既有視窗（handler 直接送出伺服器動作）才上處理中鎖。
  - 手牌 B：該卡第一顆標示「棄置」的既有按鈕（一般奧援）→ 危險確認單（以手牌 key 綁定，確認當下再驗）；紅軍奧援的「資源」與其他卡牌永遠不是棄置。
  - 購買卡 Y：焦點卡**已勾選**（在既有購買選取內）且既有「購買所選」可用時才點它，開啟既有購買確認單；資源檢查、確認與 `buy_cards` 送出都在既有流程。未勾選、資源不足（按鈕停用）、按鈕隱藏或不存在一律 no-op；不會自動勾選、不建立新購買 action。
  - 地圖 Y：清單列 `act` 對應的既有按鈕（`directBuildBtn`／`confirmMoveBtn`／`dissolveBtn`），以 iframe `act` 指令＋`req` 確認執行（見上方協定）；沒有 `act` 的列（例如一般來源）不做事。
  - STICK：只移焦點，不執行；新焦點視為非使用者指定，300ms 內忽略 A／B／X／Y。沒有內容區時不做事。
- **按鍵提示列**：固定在畫面下緣，**不接受焦點也不接受滑鼠**，只以「鍵＋標籤」顯示目前可用的專用鍵操作（例如 `Y 購買所選 1 張`、`B ⚠ 棄置 歐洲奧援`、`+ 發動 賭徒耳語`、`Capture ⚠ 結束行動`、`Y 移動 臺北→宜蘭`），來源同樣只限可見、啟用的既有控制。「清除」與「卡牌置頂」不再有搖桿入口（滑鼠照常可用；搖桿可用 B 逐張取消勾選；未使用的頂牌權利在結束行動時由伺服器既有流程處理：只有一張候選時自動置頂，多張時開既有選擇視窗）。
- **地圖兩段式清單**：來源（可行動城鎮）→ A → 該來源的伺服器合法目的地（依消耗、道路先於鐵路排序）→ A 只預備移動、Y 直接走既有「確認移動」。pending choice 目標：A 只選取、Y 走既有「建立組織」或「瓦解組織」。清單只來自 iframe 權威 snapshot（選用欄位 `selected`、`pending`、移動目標 `mode`／`cost`、目標 `act`，有給就嚴格驗證），iframe 執行每個指令前仍重驗；沒有 snapshot 或目標時清單為空、A／Y 無作用。滑鼠仍可直接操作地圖。
- **防誤觸**（數值不變：處理中鎖 1500ms、重繪冷卻 300ms、執行冷卻 250ms、地圖確認逾時 1000ms）：送出遊戲動作後到下一份 state（或 1.5 秒）前不再送出 A／B／X／Y／CAPTURE／PLUS 類指令（處理中鎖）；任何**實際執行**（click 既有控制、開啟預覽／確認單／購買確認／說明 modal、B 勾選、iframe 確認成功的地圖操作、成功進入區域，以及客廳模式下 modal 內的 A）之後 250ms 內不接受下一個執行型按鍵（fail-closed 的 no-op 不啟動冷卻；方向、R／SR、STICK、ZR、回區域層與 modal 的 B 不受影響）；重繪、分頁切換或 STICK 造成的焦點換項目後 300ms 內忽略與焦點有關的 A／B／X／Y（CAPTURE／PLUS 與焦點無關，不受此冷卻）；重繪後同 key 留原位、key 消失留同區域同索引、區域空了回同一分頁的預設內容區層，永不跨區域；沒有任何危險控制可取得方向焦點。第一次有效操作（含 CAPTURE／PLUS）只放焦點。斷線／stale／重連 baseline 沿用上方規則（重連時按住 A＋PLUS＋CAPTURE 也不觸發）。

## 測試

```bash
node --test scripts/tests/js/controller_core.test.js scripts/tests/js/living_room_core.test.js   # 或透過 pytest 包裝
uv run python -m pytest scripts/tests/test_controller_core_js.py scripts/tests/test_living_room_core_js.py scripts/tests/test_joycon_bridge.py
uv run python scripts/validate/validate_joycon_controller.py   # 瀏覽器 E2E（mock bridge），截圖到 /tmp/redline-joycon-proof/
uv run python scripts/validate/validate_living_room_controller.py   # 客廳模式 E2E（固定按鍵序列、六個情境、三種解析度），截圖到 /private/tmp/redline-living-room-proof/
```

E2E 以 mock WebSocket 取代 bridge 並注入 frame，驗證真實頁面的焦點、A click、B cancel、modal 優先權、斷線重連不誤觸、stale、地圖目標焦點與 fail-closed。**這不能取代 Mac 實機 Joy-Con 驗證**（見 `TODO.md`）。

## 限制

- https 頁面可能擋 `ws://127.0.0.1`（mixed content），詳見 bridge README；目前只完整支援 http dev／區網頁面。
- S2B1 欄位位置與 `y` 軸方向尚未用實機確認。
- 文字輸入欄位只能聚焦，無法用搖桿輸入文字。
- CAPTURE 位元：`static/controller_core.js` 解碼為 b1 `0x20`，但 `tools/joycon_bridge/README.md` 寫 `0x40`；尚未用實機確認哪一個正確，程式維持 `0x20`。Capture 實體鍵通常在左 Joy-Con，只接右 Joy-Con 時可能沒有這顆鍵（滑鼠仍可結束行動）。
