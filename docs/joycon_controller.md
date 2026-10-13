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
| 右搖桿 | 方向導航，**只在內容之間**（deadzone 0.5；按住有 380ms 延遲後每 140ms 重複一次）。與客廳模式同一份排除規則（`Core.isDirectionalExcluded`）：六個全域分頁、回合列（結束行動／紅軍能力）、手牌卡內的「資源」「行動」「棄置」、陣營能力發動鈕、卡牌勾選框、按鍵提示列**永遠不會**取得方向焦點（`.rl-pad-focus` 與瀏覽器原生 focus 皆然）；手牌只以整張卡牌取得焦點 |
| A | 確認／啟用目前焦點（呼叫既有 click handler）；**焦點在任何卡牌上時一律只開啟置中卡牌預覽**，不執行、不勾選、不購買 |
| B | 返回／取消——只在目前 UI 本身有可見、可用的取消／關閉按鈕時才作用，否則什麼都不做 |
| B（卡牌） | 焦點在購買區卡牌（checkbox 不進入焦點集合、無黃框）時切換勾選，點擊該卡既有 checkbox；勾選框停用（伺服器權威）則不作用。多張勾選照舊（逐張 B） |
| X（手牌） | 焦點在整張手牌時＝以資源使用：點擊該卡既有「資源」按鈕；按鈕不存在（如一般奧援為「棄置」）、隱藏或停用則不作用 |
| Y（手牌） | 焦點在整張手牌時＝以行動使用：點擊該卡既有「行動」按鈕；隱藏或停用則不作用 |
| Y（購買卡） | **先 B 勾選，再按 Y**：焦點卡是有效的已勾選卡（勾選框可見、未停用）且既有「購買所選」可用時，點它開啟既有購買確認單（內容是目前整份勾選；確認、資源檢查與 `buy_cards` 都在既有確認單）。未勾選、勾選框停用／隱藏（例如售完）、合計買不起（按鈕停用）、按鈕隱藏或不存在一律 fail closed；**Y 永遠不會勾選任何卡**、不直接購買。與客廳模式同一個函式與閘門 |
| Y（地圖目標） | 焦點在地圖城鎮目標時＝該目標的既有地圖操作（建立組織／確認移動／瓦解組織，見下方協定 `act`），與客廳模式同一條 iframe `act`＋`req` 確認路徑與閘門：可先用 A 走既有選取，也可直接 Y（iframe 會先走同一個選取）。只有對上 `req` 的 `ok:true` 才算執行（之後上處理中鎖）；沒有操作的目標（例如一般來源）、沒有 iframe、`ok:false`、1 秒逾時一律 fail closed，且不切換說明 |
| R / SR | **選取六個全域區段的唯一方式**，與客廳模式同一個環：指揮中心→戰略地圖→戰況紀錄→我的陣營→事件卡→時代關卡（點既有分頁／開既有說明 modal；在事件卡／時代關卡說明 modal 內按 R／SR 以既有關閉收起並前往下一個區段，其他 modal 一律停用）。必選地圖目標時只回戰略地圖（已在地圖則不動）。切換後焦點放到新區段的內容，不留在分頁上（大廳則為區塊） |
| CAPTURE | 既有「結束行動／結束步驟」，經危險確認單（預設焦點「返回」，向右到「確認」再按 A 才執行；與客廳模式同一張確認單與閘門）；結束行動本身不是方向焦點。實體鍵：只接右 Joy-Con 2 時送出 b1 `0x40`（上游 `c`，2026-10-10 實錄）；上游 `capture`（b1 `0x20`，左 Joy-Con 2／Pro）同樣接受 |
| `+` | 發動唯一一個可見、啟用的既有陣營能力（例如賭徒耳語）；沒有或不只一個時不做事 |
| SL | **聚焦選單**（與客廳模式相同，見下方「SL 聚焦選單」）：建立組織的 pending choice 時，依「統治者」或「陣營區域」把焦點移到該範圍內可建立組織的合法地圖城鎮；只移焦點，不建立、移動或瓦解。選單開著時再按 SL＝關閉 |
| ZR | **戰略地圖縮放循環**（與客廳模式相同，見下方「ZR 戰略地圖縮放」）：在戰略地圖每按一次放大一級，到最大後再按回到最小（最大地圖範圍）。不需要焦點，第一下就執行；其他分頁、任何 modal（含 SL 聚焦選單）完全不作用，連焦點都不改 |
| X | 非手牌焦點時不作用（回合列不是方向焦點，改用 CAPTURE） |
| Y | 其他焦點時顯示／隱藏操作提示（手牌、購買卡、地圖目標見上；其他卡牌焦點時 X/Y 完全不作用；聚焦選單內不作用） |
| HOME、STICK | 桌面模式不綁定 |

第一次有效操作（含 CAPTURE／`+`）只會把焦點放上去，不會執行；預設焦點與區段切換後的落點都是內容（指揮中心先放手牌）。ZR 不在此列：在戰略地圖不需要焦點，第一下就直接執行一次縮放循環（不放焦點、不改焦點）；不在戰略地圖時完全不作用，連焦點都不改。
區段切換時，該區段只要有可取得方向焦點的內容就一定落在內容上；經確認沒有任何這類內容的區段可以維持無焦點，但一定仍可用 R／SR 離開。
搖桿輸入、reconcile 與焦點變更時，若瀏覽器原生 focus 停在上述排除的控制上（例如滑鼠點過分頁），一律放掉；整張卡牌 div 本身無法取得原生 focus。
滑鼠點擊分頁、手牌按鈕、結束行動、購買 checkbox 等完全不變。畫面右下角只有一個精簡提示膠囊，不增加頂部窄條；專用鍵 fail closed 時，原因（例如「先按 B 勾選這張卡，再按 Y 購買」）會在膠囊前段顯示約 1.8 秒。

## 輸入安全

- 搖桿有 deadzone；方向在邊緣立即觸發一次，之後依 repeat 節流。
- 按鍵只在 rising edge 觸發一次。
- 斷線、stale、停用、頁面隱藏、視窗失焦：清空所有 held state。
- **只有已連線才處理輸入**：bridge 訊息與公開 `RedlineController.feed()` 走同一個入口（`Core.bridgeInputGate`），只有「已啟用、狀態 connected、目前 socket 開著」才進入按鍵判斷；未啟用、連線中、無法連線時一律丟棄，不會移動焦點或執行任何操作。訊號中斷（stale）時，公開 `feed()` 與非目前 socket 的 frame 一律丟棄；只有目前 bridge socket 送來的 frame 會進入 recover（回到已連線），且這一筆只建立 baseline、不產生任何 action。失聯時焦點與 `padActive` 保留（只是不接受輸入），重連後既有語意不變。
- 每次（重新）連線的**第一筆 frame 只是 baseline**：已按住的按鍵與已推到底的搖桿都不會觸發，必須先放開。因此重連絕不會自動按下按鈕。

## 架構

```
physical input（bridge WebSocket frame）
  → controller_core.js：normalizeFrame / reduceFrame（deadzone、edge、repeat、baseline）
  → logical actions（move / confirm / cancel / nextSection / prevSection / focusTurnBar / toggleHelp / focusMenu / mapZoom；客廳模式另有 factionAbility / endStep / nextZone）
  → context router：modal ▸ map ▸ page（routeAction / resolveModalScope）
  → controller_ui.js：只呼叫既有元素的 click()；不建構 action payload、不複製遊戲規則
```

- `static/controller_core.js`：純邏輯，可在 node 測試（`scripts/tests/js/controller_core.test.js`）。
- `static/controller_ui.js`：bridge client、設定與 HUD、DOM 焦點集合、焦點標示（`.rl-pad-focus`，4px 高對比外框，不改版面）、`scrollIntoView`。
- `static/controller_map_adapter.js`：戰略地圖 iframe 端。
- `static/living_room_core.js`（純邏輯，node 可測：路由、方向焦點排除規則、R／SR 區段環、按鍵提示列、閘門、地圖清單）＋ `static/controller_living_room.js`（DOM 膠合，透過 `RedlineController.attachLayer` 只在客廳模式接手 page／map scope，以及事件卡／時代關卡說明 modal 內的 R／SR）：見下方「客廳大螢幕模式」。

### Scope 與優先權

1. 有可見 dialog 時（危險確認、SL 聚焦選單、勝利畫面、卡面預覽、事件揭示、行動提示、對手行動通知、購買確認、陣營能力、卡牌選擇／反應選擇、時代關卡、陣營選擇），**導航只限最高優先權的那一個**，背景控制項不在焦點集合內。B 只點該 dialog 自己現有的取消／關閉按鈕（`MODAL_SCOPES.cancel`）；沒有就不做事。
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
  選用欄位 `groupMeta: 1`（SL 聚焦選單的分組資料版本）：此時每個目標都帶 `ruler`（1–8 個）、`camp`（0–16 個）字串陣列，由 iframe 取自 canonical
  `/map-data`（`data/map.json` 的 `towns[town].ruler`／`.camp`，即統治者與陣營區域＝發展空間標籤）。iframe 端任一目標的 canonical 資料缺欄位、
  不是陣列、數量不合或含不是 1–16 字字串的名稱時，整份 snapshot 都不帶 `groupMeta` 與分組欄位（不過濾、不截斷、不補值；其餘地圖控制照常）。
  parent 端：版本不是 1、宣告了版本卻缺欄位或 `ruler` 為空、沒宣告版本卻帶欄位、名稱不合或數量超過上限一律整份作廢；重複名稱只算一次（同一份成員資格）。
  選用欄位 `req`：只有回應帶 `req` 的 `snapshot` 指令時才帶（原樣回傳，必須是合法 request id），一般推送沒有。
- parent → iframe：`redline-controller-command`，`cmd` 為 `snapshot`、`focus {town}`、`clearFocus`、`activate {town}`、`button {id}`、`cancel`、`act {town, id, req}`（`id` 只限 `directBuildBtn`／`confirmMoveBtn`／`dissolveBtn`）、`zoom {req}`（ZR 縮放循環，見下方「ZR 戰略地圖縮放」）。**`act` 與 `zoom` 必須帶合法 `req`**，沒有或不合法的 `req` 在 iframe 端直接丟棄、不執行，它們的 result 也必須帶 `req`；其他指令可選 `req`（正整數 request id）。
- iframe → parent：`redline-controller-result` `{cmd, req, ok, reason, via}`，每個指令處理完都回覆；`req` 原樣回傳（沒帶則為 `null`），`via` 為 iframe 實際走的既有控制（按鈕 id，或取消時的 `cancelDissolveChoiceBtn`／`selection`）。
  地圖執行型指令（兩種顯示模式的 Y 地圖操作；客廳模式另有清單選取、清單取消）、ZR 的 `zoom` 與 SL 聚焦選單的 `snapshot` 請求都帶 `req`，且同時只有一筆等待確認：**只有對上該 `req` 的 `ok:true`（iframe 執行前已重驗）才算執行**，此時才記錄 250ms 冷卻（SL 聚焦選單的 `snapshot` 請求例外：`ok:true` 只表示可以採用同一個 `req` 的 snapshot，真的開啟選單或移好焦點後才記錄），Y 地圖操作與 `via: cancelDissolveChoiceBtn` 的取消再上處理中鎖（`zoom` 不是遊戲動作，不上處理中鎖）。沒有 iframe、`ok:false`、1 秒內沒有回覆、過期或對不上的 `req` 一律 fail closed，不記錄冷卻也不上鎖；等待期間其他執行型按鍵被擋下（不重送），回覆或逾時後立即解除。桌面模式的 A／B（`activate`／`button`／`cancel`）不帶 `req`，行為不變。
- `act` 在 iframe 內：(1) 用權威資料重驗 town 是目前目標、其 `act` 對應的既有按鈕等於 `id`（否則 `not-a-target`／`action-mismatch`）；(2) 按鈕尚未作用在該 town 時，走與 A／滑鼠相同的既有 marker click 選取／預備；(3) 再驗一次目標仍在、按鈕可見啟用且作用在該 town，才 `click()` 既有按鈕（否則 `button-unavailable`）。失敗時不點任何按鈕、不送出遊戲動作（最多留下與按 A 相同的選取／預備狀態）。

焦點集合只來自伺服器權威資料，且**每個指令執行當下 iframe 都重新驗證**（parent 的 snapshot 過期或被偽造也不會讓非法目標可 action）：

- pending choice 目標：`supportChoiceHighlight.towns`（伺服器 pending choice 投影），限可見且已知城鎮。
- 移動：目前選取來源的 `legal_organization_moves`（`selectedMoveTargets`），以及可行動的來源城鎮。
- 缺狀態、不是自己的回合、有 pending choice 卻沒有地圖 highlight → 沒有任何目標（fail-closed）。
- 按鈕只限白名單 `directBuildBtn`、`confirmMoveBtn`、`dissolveBtn`、`cancelDissolveChoiceBtn`，且必須存在、可見、未停用。

A 對城鎮走既有 marker `click` 路徑（選取來源／預備移動目的地／選擇 pending choice 候選），對按鈕呼叫既有 `click()`；是否真的移動、建立或瓦解仍由既有確認按鈕與伺服器驗證決定。B 只會：點可見且啟用的「取消瓦解」，或取消目前選取（既有「點地圖其他地方取消」流程）；兩者都沒有就不做事。焦點城鎮以黑底＋黃色雙圈與名稱標籤標示，必要時 `panInside`。

## 客廳大螢幕模式（living-room）

同一 route、同一 DOM、同一套遊戲 action：`html[data-display="living-room"]` 只切換 CSS 版面層並加上搖桿的內容導航與專用快捷鍵。
開啟方式：網址加 `?display=living-room`（`?display=desktop` 切回），或 🎮 設定面板「顯示模式」。存於 `localStorage`（`redline.display.v1`），不依螢幕尺寸自動切換。桌面模式（預設）版面不變，搖桿操作見上表；兩種模式共用同一份方向焦點排除規則、同一個 R／SR 六區段環與同一套 Capture／`+` 流程，客廳模式另外多了內容區兩層導航、按鍵提示列與下列專用鍵。

- **安全區與字級**：舞台等比縮放後再留 5% title-safe（`resizeStage` 乘 0.9）；文字 16–28 設計單位，720p／1080p／4K 只差銳利度。卡牌列改為單列水平捲動並縮小卡面，卡名以大字標在卡上；完整卡面用 A 預覽（放大到畫面高約 80%）。
- **方向鍵只在內容資料間**：內容區＝常設購買區、隨機購買區、陣營／根據地候選（只有非能力鈕的內容選項時才出現）、手牌、玩家動態（縮小在左下角的對手通知）；戰略地圖分頁是地圖目標清單；其他分頁是該分頁內容。
  方向焦點**永遠不會**落在：手牌卡內的「資源」「行動」「棄置」、結束行動／紅軍能力（回合列）、六個全域分頁、購買卡 checkbox、陣營能力發動鈕、按鍵提示列（`LR.isDirectionalExcluded`＝`Core.isDirectionalExcluded`，與桌面模式同一份）。手牌與購買卡只以整張卡取得焦點；瀏覽器原生 focus 停在這些控制上時，搖桿輸入、reconcile 與焦點變更都會放掉它。
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
| Y | 說明 | 手牌＝行動；**購買卡（先 B 勾選）＝既有「購買所選」**；**地圖目標＝建立組織／確認移動／瓦解組織**；其他＝說明 |
| R／SR | 下一個／上一個全域區段 | 同左 |
| PLUS（+） | **發動既有陣營能力** | 同左 |
| CAPTURE | **既有結束行動／結束步驟（危險確認）** | 同左 |
| STICK（按下搖桿） | **下一個內容區**（直接進入、還原上次項目；只移焦點） | 同左 |
| SL | **聚焦選單**（任何分頁皆可開；只有建立組織的 pending choice 才有候選；只移焦點） | 同左 |
| ZR | **戰略地圖＝放大一級，到最大後回到最小**（不需要焦點，第一下就執行；必選地圖目標時也可用）；其他分頁完全不作用，連焦點都不改 | 同左（焦點、區域與層級都不變） |

ZR 不再回區域層或回指揮中心：要回區域層用 B（非卡牌項目與地圖清單），換區用按下搖桿，換分頁用 R／SR。

- **專用快捷鍵**（全部只點擊當下可見、啟用、合法的既有控制；按下當下重驗，失效即 fail closed 並在狀態列顯示原因）：
  - CAPTURE：`advanceStepBtn`（結束行動／結束回合／開始行動階段）→ 危險確認單，預設焦點「返回」；連按不會開第二張確認單；確認單開著時按鈕失效或文字改變（換了步驟）就自動關閉不執行。
  - PLUS：`#factionActionButtons` 內的既有發動鈕（例如「發動 賭徒耳語」）或 `redArmyAbilityBtn`，**恰好一個可用**才點擊；沒有或多於一個不做事。點擊後若沒有開啟既有視窗（handler 直接送出伺服器動作）才上處理中鎖。
  - 手牌 B：該卡第一顆標示「棄置」的既有按鈕（一般奧援）→ 危險確認單（以手牌 key 綁定，確認當下再驗）；紅軍奧援的「資源」與其他卡牌永遠不是棄置。
  - 購買卡 Y（與桌面模式相同）：**先用 B 勾選焦點卡，再按 Y**。焦點卡是有效的已勾選卡（勾選框可見、未停用，即仍在既有購買選取內）且既有「購買所選」可用時才點它，開啟既有購買確認單（內容是目前整份勾選）；資源檢查、確認與 `buy_cards` 送出都在既有流程。未勾選、勾選框停用／隱藏（例如售完）、資源不足（按鈕停用）、按鈕隱藏或不存在一律 no-op 並顯示原因；不會自動勾選、不建立新購買 action。
  - 地圖 Y（與桌面模式相同）：清單列 `act` 對應的既有按鈕（`directBuildBtn`／`confirmMoveBtn`／`dissolveBtn`），以 iframe `act` 指令＋`req` 確認執行（見上方協定）；沒有 `act` 的列（例如一般來源）不做事。pending choice 目標用 A 選取後焦點**留在該列**（只有換了一份清單——來源 ↔ 目的地或換來源——才回第一列），所以接著按 Y 就是在剛選的城鎮建立／瓦解。
  - STICK：只移焦點，不執行；新焦點視為非使用者指定，300ms 內忽略 A／B／X／Y。沒有內容區時不做事。
  - ZR（與桌面模式相同）：戰略地圖縮放循環，見下方「ZR 戰略地圖縮放」。
- **按鍵提示列**：固定在畫面下緣，**不接受焦點也不接受滑鼠**，只在 bridge 已連線時（未啟用、連線中、無法連線、訊號中斷時整列清空）以「鍵＋標籤」顯示目前可用的專用鍵操作（例如 `Y 購買所選 1 張`、`B ⚠ 棄置 歐洲奧援`、`SL 聚焦選單（85 個目標）`、`+ 發動 賭徒耳語`、`Capture ⚠ 結束行動`、`Y 移動 臺北→宜蘭`），來源同樣只限可見、啟用的既有控制（SL 只在最新權威 snapshot 有可分組的合法建立目標時出現，數字只是提示，開啟時仍以 req 綁定的新 snapshot 為準；聚焦選單開著時提示列清空，legend 改為選單按鍵）。「清除」與「卡牌置頂」不再有搖桿入口（滑鼠照常可用；搖桿可用 B 逐張取消勾選；未使用的頂牌權利在結束行動時由伺服器既有流程處理：只有一張候選時自動置頂，多張時開既有選擇視窗）。
- **地圖兩段式清單**：來源（可行動城鎮）→ A → 該來源的伺服器合法目的地（依消耗、道路先於鐵路排序）→ A 只預備移動、Y 直接走既有「確認移動」。pending choice 目標：A 只選取、Y 走既有「建立組織」或「瓦解組織」。清單只來自 iframe 權威 snapshot（選用欄位 `selected`、`pending`、移動目標 `mode`／`cost`、目標 `act`，有給就嚴格驗證），iframe 執行每個指令前仍重驗；沒有 snapshot 或目標時清單為空、A／Y 無作用。滑鼠仍可直接操作地圖。
- **防誤觸**（數值不變：處理中鎖 1500ms、重繪冷卻 300ms、執行冷卻 250ms、地圖確認逾時 1000ms）：送出遊戲動作後到下一份 state（或 1.5 秒）前不再送出 A／B／X／Y／CAPTURE／PLUS 類指令（處理中鎖）；任何**實際執行**（click 既有控制、開啟預覽／確認單／購買確認／說明 modal、B 勾選、iframe 確認成功的地圖操作與 ZR 縮放、成功進入區域，以及客廳模式下 modal 內的 A）之後 250ms 內不接受下一個執行型按鍵（fail-closed 的 no-op 不啟動冷卻；方向、R／SR、STICK、ZR、回區域層與 modal 的 B 不受影響）；重繪、分頁切換或 STICK 造成的焦點換項目後 300ms 內忽略與焦點有關的 A／B／X／Y（CAPTURE／PLUS 與焦點無關，不受此冷卻）；重繪後同 key 留原位、key 消失留同區域同索引、區域空了回同一分頁的預設內容區層，永不跨區域；沒有任何危險控制可取得方向焦點。第一次有效操作（含 CAPTURE／PLUS）只放焦點；戰略地圖上的 ZR 不需要焦點，第一下就執行縮放（不放焦點）。斷線／stale／重連 baseline 沿用上方規則（重連時按住 A＋PLUS＋CAPTURE 也不觸發）。

## SL 聚焦選單（兩種顯示模式）

可建立組織的合法城鎮很多時（例如組織經驗甲「無視距離於己方發展空間建立」一次 85 個），只用方向鍵很難走到目標。按 `SL` 開啟置中的精簡選單（不新增頂部窄條；客廳模式底部提示列照常可見），依範圍把焦點直接移到合法城鎮；實際建立仍只走既有地圖操作：Y → `mapAct` → iframe `act` → `directBuildBtn`，使用唯一的 `req` 並等待對上的 `ok:true`（見上方協定）。

- **候選**＝目前建立組織 pending choice 的合法目標（地圖清單 choice 段，每列 `act`＝`build`），只來自 iframe 權威 snapshot。移動來源、移動目的地、瓦解組織的 pending choice，以及沒有 `build` 的其他 pending choice 一律 fail closed（`目前沒有可聚焦的地圖目標`）。
- **分組**：一層、兩個區段，上下／左右即可選取（每列 4 個）：
  - `統治者`：canonical 地圖資料的 `ruler`。統治者含紅軍的城鎮標示「牆內」（rules.md 牆內定義）。
  - `陣營區域`：canonical 地圖資料的 `camp`（發展空間標籤）。沒有陣營標籤的城鎮不屬於任何陣營區域（仍在統治者分組內）。
  - 每個候選都必須有非空的 `ruler` 與合法的 `camp` 陣列；任一候選缺少或格式不合 → 整份 fail closed（`地圖資料不足，無法分組`），不過濾、不截斷、不補值。
  - 只列出至少含 1 個目前合法目標的項目，顯示匹配城鎮數；城鎮與成員資格都去重。排序：城鎮數多→少，同數依名稱（zh-Hant）；結果確定。
- **按鍵**（選單是 modal，沿用既有 modal scope lock）：

  | 輸入 | 選單內 |
  | --- | --- |
  | 搖桿／方向 | 只在選項間移動，不穿透背景 |
  | A | 選定該範圍：關閉選單，必要時用既有分頁切換到戰略地圖（與 R／SR 相同的分頁 click），焦點移到該範圍內的合法城鎮——**目前焦點城鎮若在該範圍內就保留**，否則取清單順序第一個（城鎮名稱 zh-Hant 順序）。不選取、不建立、不移動、不瓦解 |
  | B／SL／滑鼠 `×` | 關閉並回到開啟前的焦點，不執行任何操作（`×` 保留滑鼠操作，但不是方向焦點） |
  | R／SR、X、Y、`+`、Capture、ZR、STICK、HOME | 不作用（不切區段、不開說明／確認單、不縮放地圖、不送任何地圖操作） |

- **權威與 fail closed**：開啟、選定與選單開著時的刷新都先向 iframe 送帶唯一 `req` 的 `snapshot` 指令，並與其他地圖指令共用「同時只有一筆等待」與 1000ms 逾時。只有**同一個 `req` 先及時回覆 `ok:true`，且同一個 `req` 的 snapshot 也在送出後 1000ms 內送達**才採用：`ok:false`、逾時、snapshot 先於 `ok:true` 或在 1000ms（含）之後才到、`req` 不同或沒有 `req` 的一般推送、不合 schema 一律不採用。等待中的請求一逾時（ack 計時器，或任一按鍵經過閘門時發現）就清掉，晚到的回覆不會再開啟或選定。以下一律不開選單（或不移焦點）並顯示短原因：地圖從未載入（`地圖尚未載入：先用 R 切到戰略地圖`）、iframe 沒有回應或回覆過期（`地圖沒有回應，請再試一次`）、iframe 回覆 `ok:false`（`此操作目前不可用`）、snapshot 不合 schema 或分組資料不足（`地圖資料不足，無法分組`）、沒有合法建立目標（`目前沒有可聚焦的地圖目標`）、遊戲尚未開始、戰略地圖分頁不可用。
- **選定時狀態已改變**：選定時那份新 snapshot 的清單段或 pending choice 的已選城鎮與畫面上的選單不同 → 不移焦點，選單以新資料刷新（`地圖狀態已改變，請重新選擇`）；該範圍已沒有城鎮 → 不移焦點、刷新（`此範圍已沒有合法目標`）；完全沒有合法建立目標或分組資料不足 → 關閉並還原焦點。
- **刷新只用 req 綁定的 snapshot**：選單開著時，一般推送（不帶 `req`）本身不改變選單內容，只觸發一次新的 `snapshot` 請求；畫面以那份通過上述檢查的回覆為準（另一個請求等待中時不另外送，等它的回覆）。刷新請求失敗就關閉選單。選單被其他視窗（例如伺服器推來的選擇視窗）蓋過或離開遊戲畫面就自動關閉。
- **停用、清除與斷線**：停用搖桿控制、清除焦點、切換顯示模式、bridge 斷線（含重連中與 stale）時關閉選單並取消等待中的開啟／選定／刷新請求；之後才到的 iframe 回覆不會再開啟或選定。關閉後若沒有可還原的內容（例如必選地圖目標時的指揮中心），焦點不會殘留在隱藏的選項上。
- **防誤觸**（數值不變：1500／300／250／1000ms）：開啟與選定只移焦點，不受處理中鎖限制；地圖確認等待中不送第二筆。**只有真的開啟選單、或真的把焦點移到合法城鎮**才記錄一次執行（之後 250ms 內的下一個執行型按鍵被擋，例如開啟後立刻按 A）；fail closed 的開啟或選定不記錄冷卻。選單在游標下刷新後 300ms 內忽略 A。第一次有效操作（含 SL）只放焦點。

## ZR 戰略地圖縮放（兩種顯示模式）

實體鍵 ZR＝b0 `0x80`（下方「限制」的實機紀錄 `80 00`）。

- **只在戰略地圖**：目前 scope 是地圖（沒有 modal、分頁＝戰略地圖、地圖 iframe 可見）時，每按一次放大一級；到最大層級後再按一次回到最小層級（最大地圖範圍）：`min → min+1 → … → max → min`，單向循環。兩種顯示模式、區域層與內容層、必選地圖目標時都一樣。
- **不需要焦點**：ZR 與焦點無關，第一下就直接執行一次縮放循環；不放焦點、不改焦點，也不改 `padActive`、區域或層級（之後其他鍵的第一下仍照原規則只放焦點）。
- **其他情境完全 no-op**：指揮中心、戰況紀錄等其他分頁、大廳、任何 modal（含 SL 聚焦選單與危險確認單）、地圖 iframe 隱藏或不在時，ZR 不縮放、不送任何指令，也不放焦點或改變焦點；不切說明、不回區域層、不切分頁。未啟用、連線中、無法連線、stale 時輸入本來就被丟棄（重連或 recover 的第一筆只當 baseline）。
- **層級範圍**：`Core.MAP_ZOOM_CYCLE`（2–10）與 Leaflet `map.getMinZoom()`／`map.getMaxZoom()` 的交集，只取整數層級。戰略地圖沒有設定 minZoom／maxZoom（Leaflet 回傳 0／Infinity），所以目前是 2–10：2＝整個遊戲範圍（溫哥華～奧克蘭）可見的最遠層級，10＝陣營標籤開始顯示的層級（`FACTION_LABEL_MIN_ZOOM`）。之後地圖若設了更窄的 min／max，循環跟著 Leaflet。目前層級高於最大（例如滑鼠縮放到 13）或低於最小時，下一下回到最小；小數層級前進到下一個整數層級。
- **只用 Leaflet API**：iframe 以 `map.setView(目前中心, 下一級, {animate:false})` 縮放，地圖中心不變；不模擬滑鼠滾輪、滑鼠座標或鍵盤事件。不改焦點城鎮、選取的來源、合法目的地、預備移動、pending choice、建立目標或任何遊戲狀態，也不送任何遊戲動作。
- **確認協定**：parent 送 `zoom {req}`（唯一的 request id，與其他地圖指令共用「同時只有一筆等待」與 1000ms 逾時）。iframe 照常驗證來源與 schema；頁面或地圖容器不可見、地圖還沒有視圖、層級無法判定，或縮放後層級／中心驗證不符時回覆 `ok:false`（`map-hidden`／`map-not-ready`／`zoom-unavailable`／`zoom-unverified`）。**只有對上 `req`、1000ms 內的 `ok:true` 才算成功**（記錄成功與 250ms 執行冷卻，不上處理中鎖）；單純送出不算成功。缺 `req`、錯的 `req`、不合 schema、`ok:false`、逾時、逾時後或重複的回覆一律 fail closed，不記錄成功或冷卻；`ok:true` 到達時若已離開戰略地圖、開了 modal、停用／斷線／stale 或 iframe 被隱藏，也視為 `ok:false`。fail closed 時提示「地圖目前無法縮放」或「地圖沒有回應，請再試一次」。
- **防誤觸**：ZR 不受處理中鎖、重繪冷卻與執行冷卻限制（連按時每一下都前進一級），但另一個地圖請求等待確認時不送出（不重送、不覆蓋等待中的請求）；縮放確認成功後記錄的 250ms 執行冷卻只擋下緊接的執行型按鍵（例如立刻按的 A／Y）。

## 測試

```bash
node --test scripts/tests/js/controller_core.test.js scripts/tests/js/living_room_core.test.js   # 或透過 pytest 包裝
uv run python -m pytest scripts/tests/test_controller_core_js.py scripts/tests/test_living_room_core_js.py scripts/tests/test_joycon_bridge.py
uv run python scripts/validate/validate_joycon_controller.py   # 瀏覽器 E2E（mock bridge；含桌面模式 SL 聚焦選單與 ZR 縮放循環），截圖到 /tmp/redline-joycon-proof/
uv run python scripts/validate/validate_living_room_controller.py   # 客廳模式 E2E（固定按鍵序列、三種解析度，含兩種顯示模式的實機 Capture／購買卡 B→Y／地圖 Y 情境、客廳模式 SL 聚焦選單與 ZR 縮放循環），截圖到 /private/tmp/redline-living-room-proof/
```

E2E 以 mock WebSocket 取代 bridge 並注入 frame，驗證真實頁面的焦點、A click、B cancel、modal 優先權、斷線重連不誤觸、stale、地圖目標焦點與 fail-closed。注入的按鍵位元取自下方「限制」的實機證據，但 **mock E2E 本身不是實機證據，也不能取代 Mac 實機 Joy-Con 驗證**（見 `TODO.md`）。
SL 聚焦選單的 E2E 用「組織經驗甲」（85 個合法城鎮、8 個統治者、7 個陣營區域）：分組與城鎮數由驗證端以伺服器 pending choice＋`data/map.json` 獨立計算比對，並驗證：
- 移動來源、移動目的地與瓦解的 pending choice 都 fail closed，而且不開始執行冷卻。
- A 只移焦點：不送 act／activate／button／cancel、不建立。兩種模式都驗證從指揮中心選定後切回戰略地圖，以及保留目前焦點。
- 開啟後 250ms 內的 A 被擋，冷卻過後才選定。
- scope lock 有正向對照：每個綁定鍵先在選單開著時驗證不作用，B 關閉並確認焦點回到原處後，在同一情境再按一次，驗證它確實會執行。
  - 真實情境：方向鍵、R／SR、兩種模式的 ZR（地圖縮放），以及客廳模式的 Y（說明）與 STICK。
  - pending choice 期間遊戲本身會停用結束行動、陣營能力與手牌按鈕：測試暫時啟用，click 在 capture 階段攔下，不送出任何動作。
  - 只在必選鎖之外才會作用的鍵（兩種模式的 X，與桌面模式手牌 Y）：測試暫時解除 parent 的必選鎖旗標。
  - 未綁定的鍵同樣不穿透。
- B／×／SL 從非預設焦點開啟後精確還原。
- 協定整合（攔下 parent 指令、由 iframe 偽造回覆）：`ok:false`、錯的 `req`、不合 schema、snapshot 先於 `ok:true`，以及逾時邊界（約 850ms 採用；`ok:true` 約 900ms 但 snapshot 在 1000ms 之後才到、或兩者都晚到則拒絕）。
- 選定時已選城鎮改變。
- 一般推送只觸發 req 綁定刷新，畫面以那份回覆為準。
- 任一合法目標的 canonical 分組資料不合法。
- 斷線、停用與晚到的回覆。
- 候選在選定瞬間消失、iframe 無回應、沒有目標。
- 選單開著時 Y 不穿透；關閉後 Y 仍走既有 `act`＋`req`＋`ok:true` 建立。

ZR 縮放循環的 E2E（兩種模式）驗證：
- 從最小層級連按走完 `min → … → max → min`，每一下一級、各自唯一的 `req`，中心、焦點城鎮、選取、預備移動與遊戲狀態都不變；不需要焦點，第一下就縮放且不放焦點。
- 邊界：最小 → 下一級、一般層級 → 下一級、最大 → 最小、超出循環 → 最小；Leaflet 設了更窄的 min／max 時跟著 Leaflet。
- 送出到確認前不記錄任何東西、等待中不重送；缺 `req`、錯的 `req`、不合 schema、`ok:false`、逾時、逾時後與重複的回覆 fail closed；iframe 端拒絕缺 `req` 或非 parent 來源的 `zoom`，容器隱藏時回覆 `ok:false`。
- modal、iframe 隱藏或不在、等待中離開地圖或停用、停用、斷線、重連中、stale、重連時按住 ZR、指揮中心與戰況紀錄一律不縮放（客廳模式也不回區域層）。

## 限制

- https 頁面可能擋 `ws://127.0.0.1`（mixed content），詳見 bridge README；目前只完整支援 http dev／區網頁面。
- **按鍵位元的實機證據**（與上方 mock E2E 分開）：使用者提供的完整實體 BUTTON AREA 紀錄（`[b0 b1]`，2026-10-11 交付）明確確認：
  neutral＝`00 00`、A＝`08 00`（b0 `0x08`）、B＝`04 00`（b0 `0x04`）、X＝`02 00`（b0 `0x02`）、Y＝`01 00`（b0 `0x01`）、
  **SL＝`20 00`（b0 `0x20`）**、SR＝`10 00`、R＝`40 00`、ZR＝`80 00`、`+`＝`00 02`、STICK＝`00 04`、HOME＝`00 10`、Capture＝`00 40`。
  原始紀錄（前兩個 byte 即 `[b0 b1]`）：neutral `BUTTON AREA: 00 00 00 e0 00 00 00 00 00 00 00 00`、
  SL `BUTTON AREA: 20 00 00 e0 00 00 00 00 00 00 00 00`。
  這是 SL 聚焦選單 mapping 的依據；與目前的 `BUTTON_BITS` 一致，SL 沿用 b0 `0x20`，沒有新增或重新指派任何位元。ZR 縮放循環同樣沿用既有的 ZR＝b0 `0x80`。
  2026-10-10 的獨立 bridge WebSocket subscriber 也錄到 Y＝`[1, 0]`、實體 Capture＝`[0, 64]`。2026-10-11 另做的 bounded WebSocket capture
  因 FTCW 當時沒有送出任何 frame 而沒有資料，不影響上述紀錄。
- 尚未以實體 Joy-Con 完整驗證 SL 聚焦選單與 ZR 縮放循環的操作流程（目前只有 mock E2E）。
- 文字輸入欄位只能聚焦，無法用搖桿輸入文字。
- CAPTURE 接受 b1 `0x40` 與 b1 `0x20` 兩個位元（同一個邏輯鍵，按住時切換位元不會重複觸發）。上游 `Peterksharma/switch2mac`（commit `a8f2e61e85c3e4a43df3e6ed2f1467327df03d72`）`Switch2Protocol.swift` 定義 `capture = 0x0000_2000`、`c = 0x0000_4000`，UDPHub 以 little-endian u32 寫出。2026-10-10 以獨立 subscriber 實錄本機 bridge（只接右 Joy-Con 2）：Y＝`[1, 0]`、實體 Capture 鍵＝`[0, 64]`（b1 `0x40`，即上游 `c`；右 Joy-Con 2 沒有 `capture` 那顆鍵），因此 `0x40` 是主位元；`0x20` 保留給左 Joy-Con 2／Pro 手把的 `capture`（未實測）。兩個位元原本都沒有其他對應，沒有重新指派任何已知按鍵。字面封包回歸測試：`scripts/tests/test_joycon_bridge.py`、`scripts/tests/js/controller_core.test.js`。
