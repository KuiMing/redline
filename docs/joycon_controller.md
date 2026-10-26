# Joy-Con／搖桿控制

左或右 Joy-Con（經 [`tools/joycon_bridge`](../tools/joycon_bridge/README.md)）作為**額外**輸入來源；每位玩家（每個瀏覽器分頁）各拿一支，彼此獨立（見下方「多支獨立 Joy-Con」）。滑鼠、觸控、鍵盤完全不變。下文的按鍵名稱一律是右 Joy-Con 的邏輯鍵；左 Joy-Con 的對照見「按鍵正規化」。

## 多支獨立 Joy-Con（左／右）

每位玩家只拿一支左 Joy-Con 或一支右 Joy-Con；左右**不會**配對成雙手控制器，兩支同側也不會互相覆寫。

- **身份**：bridge 對 Finally the Controller Works（FTCW）的每個 UDP 埠（預設 24800–24803，一個埠一支手把）各自送 `hello`。身份＝左右＋FTCW 埠＋`S2N1` 裝置名稱指紋，例如 `L24801-3f2a9c1e`、`R24800-9b0c11d2`（不是只有 left／right）。左右只由 `S2N1` 名稱判定（`(L)`／`LEFT` → 左，`(R)`／`RIGHT` → 右）；兩者皆有或皆無、或非主埠沒有名稱 → 該埠 fail closed（不建立身份、不轉送、不能 claim）。**舊版相容**：主埠（`--udp-port`，預設 24800）收到輸入卻 1.5 秒都沒有名稱時，採用明確的暫時身份 `R24800-legacy`（視為右 Joy-Con）；之後名稱才到時身份改變，原擁有者不沿用。
- **每支各自的狀態**：左右、原始／正規化 frame、最後收到時間、active／stale、擁有者各自獨立。1 秒沒有封包 → 只有這一支 stale，並清掉它的按鍵與搖桿（不殘留 stuck state）；其他手把不受影響。
- **按鍵正規化（在 bridge 完成）**：左 Joy-Con 的實體輸入先轉成右 Joy-Con 的邏輯位元，瀏覽器的 action routing 只看共用邏輯 layout，桌面與客廳模式沒有兩份左右行為。

  | 左 Joy-Con（封包 offset／位元） | 等同右 Joy-Con |
  | --- | --- |
  | ↑（10／`0x02`）、→（10／`0x04`）、↓（10／`0x01`）、←（10／`0x08`） | X、A、B、Y |
  | 左搖桿（x＝offset 12、y＝offset 16，float32，FTCW 向上為正；每軸 deadzone 0.15） | 右搖桿（offset 20／24） |
  | 按下搖桿（9／`0x08`） | STICK |
  | L（10／`0x40`）、ZL（10／`0x80`） | R、ZR |
  | −（9／`0x01`） | `+` |
  | Capture（9／`0x20`） | Capture（b1 `0x40`）。**不是 HOME** |
  | SR（10／`0x10`）、SL（10／`0x20`） | **SL、SR**（交叉：左 SR＝聚焦選單、左 SL＝上一個區段） |

  右 HOME 沒有左側對應，維持原本不綁定。上游 `capture`（u32 `0x2000`）在右手／舊版預設身份仍當 Capture。逐項對照（Python 與 JS 測試共用）：`scripts/tests/fixtures/joycon_dual_layout.json`。
- **玩家選擇（claim）**：🎮 設定面板「選擇手把」列出 bridge 的所有手把（其他玩家使用中、沒有訊號的不能選）；選一支＝claim，選「不使用手把」＝release。bridge 是唯一權威：每支最多一位擁有者、每位玩家最多一支；claim 別人的、不存在、ID 不合法、沒有訊號的一律拒絕（`claimed`／`unknown-controller`／`invalid-controller`／`not-active`），重複 claim 同一支是冪等，claim 另一支＝切換。沒有 claim 的分頁不會收到任何 frame（狀態「未選擇手把」，輸入與快捷鍵提示都 fail closed）。
- **預設與記憶**：分頁的選擇存在 `sessionStorage`（`redline.controller.claim.v1`，重新整理後重連只會再 claim 同一支）。沒有選擇過的分頁只套用舊版相容預設：bridge 上**恰好只有一支手把、它是右 Joy-Con、有訊號且沒人用**時自動 claim；有兩支以上（或唯一一支是左手）就要手動選。之後加入的第二支手把永遠不會接管第一位玩家。
- **斷線與重連**：手把 stale 時保留擁有者；同一身份（同埠同名）恢復時回到同一位玩家，epoch +1，瀏覽器把第一筆當 baseline（重連時按住的鍵不觸發）。換了埠就是新的、沒人擁有的手把；同一個埠換成另一支裝置（名稱或左右改變）→ 舊身份移除，原擁有者失去它並看到原因。玩家的瀏覽器連線結束即釋放手把。
- **HUD（玩家可見名稱）**：設定面板「我的手把」、「選擇手把」選項、提示膠囊與客廳狀態列只顯示玩家名稱（`Core.controllerLabel`／`bindingBadge`，帶目前 roster）：`左 Joy-Con`／`右 Joy-Con`；同側有多支時依**目前 roster** 給本機顯示序號（依埠號、同埠再依完整 id 排序，與 roster 順序無關），例如 `右 Joy-Con 1`、`右 Joy-Con 2`。**不顯示** FTCW UDP 埠、`S2N1` 名稱（指紋）、endpoint 或 controller id；同側手把增減時序號可能改變。選項的 value、claim、記住的選擇與 bridge 協定仍用完整 id（身份與授權模型不變）。左手玩家另顯示實體鍵對照。客廳輪流大廳用同一規則（`hotseat_core.controllerDisplayNames`，node 測試比對兩者一致）。
- **協定（bridge v2，同一個 `/ws`）**：頁面連上後送 `{"type":"hello","v":2}`；bridge 回 `roster`（`owned`、`controllers:[{id, side, name, endpoint, status, owner:'you'|'other'|null, sideSource}]`，變動時與每秒送一次），只送本分頁擁有那一支的 `{"type":"frame","v":2,controller,side,epoch,x,y,buttons:[b0,b1]}`。client 送 `claim {controller}`、`claim-default`、`release`，bridge 回 `claim-result {request, ok, controller, reason}`；格式不合 → `error bad-message`。瀏覽器端所有訊息都驗證 schema，id 與左右不符、非本分頁擁有的 frame 一律丟棄。**相容**：舊版頁面（不送 hello）0.3 秒後當舊版 client，只拿「唯一一支右 Joy-Con」並收原本的 `{x, y, buttons}`；新版頁面連到舊版 bridge 時，在收到 roster 前把無型別 frame 當唯一一支右 Joy-Con（`右 Joy-Con（舊版 bridge 相容）`）。Host／Origin 檢查不變，`/health` 也只接受 loopback Host。

## 啟用

開始畫面／大廳右下角 🎮 → 勾選「啟用搖桿控制」（遊戲畫面中不顯示 🎮，也不能開啟這個設定／狀態面板）。設定（是否啟用、Bridge 位址）存在 `localStorage`（`redline.controller.v1`）。
未啟用時不會建立任何連線、不會接管焦點；控制器未連線時 UI 正常。位址只接受 `ws(s)://127.0.0.1`、`localhost`、`[::1]`。

連線狀態：未啟用／連線中／已連線／未選擇手把（bridge 已連線但這個分頁沒有手把）／訊號中斷（stale，bridge 回報這支手把 stale 或超過 1.5 秒沒收到 frame）／無法連線（自動以 1→8 秒退避重連，也可按「重新連線」）。

## 預設操作（桌面模式）

產品只保留桌面模式；以 Joy-Con 遊玩也是桌面模式。「客廳大螢幕」顯示模式已移除（見下方「客廳大螢幕模式（已移除）」）。

| 輸入 | 動作 |
| --- | --- |
| 右搖桿 | 方向導航，**只在內容之間**（deadzone 0.5；按住有 380ms 延遲後每 140ms 重複一次）。與客廳模式同一份排除規則（`Core.isDirectionalExcluded`）：六個全域分頁、回合列（結束行動／紅軍能力）、手牌卡內的「資源」「行動」「棄置」、陣營能力發動鈕、購買選擇按鈕、按鍵提示列**永遠不會**取得方向焦點（`.rl-pad-focus` 與瀏覽器原生 focus 皆然）；手牌只以整張卡牌取得焦點。手牌超過手牌區可視張數（1280×720 舞台約 6 張）時，被裁掉的後段手牌仍在焦點集合內（只看是否顯示、有尺寸，不看 overflow 裁切），焦點移過去時手牌區自動水平捲動讓整張卡可見；手牌卡帶 `data-card-index`（伺服器手牌位置），每次狀態推送整列重建後焦點依位置重新綁定（同名手牌不會被綁回第一張），捲動位置也會保留 |
| A | 確認／啟用目前焦點（呼叫既有 click handler）；**焦點在任何卡牌上時一律只開啟置中卡牌預覽**，不執行、不選擇、不購買 |
| B | 返回／取消——只在目前 UI 本身有可見、可用的取消／關閉按鈕時才作用，否則什麼都不做 |
| B（卡牌） | 焦點在購買區卡牌（選擇按鈕不進入焦點集合；卡面以 2px 不透明黃色邊框標示，框內透明）時切換選擇，點擊該卡既有選擇按鈕；按鈕停用（伺服器權威）則不作用。多張選擇照舊（逐張 B） |
| X（手牌） | 焦點在整張手牌時＝以資源使用：點擊該卡既有「資源」按鈕；隱藏或停用則不作用。**一般（非紅軍）奧援**的同一位置是既有「棄置」按鈕：X＝開啟危險確認單（預設焦點「返回」；B 或「返回」取消；右移到「確認」再按 A 才點既有「棄置」，以手牌 key 綁定並在確認當下重驗可見、啟用、標籤未變；伺服器照常驗證）。「棄置」鈕停用／隱藏／不只一顆時 X 不作用（不改走資源）。紅軍奧援的按鈕是「資源」，X 照舊＝資源。判斷只看該卡既有按鈕（`LR.discardControlIndex`：標籤恰好一顆「棄置」），不看卡名。與客廳模式同一個函式（`startDiscard`）與閘門 |
| B（手牌） | 與其他非卡牌焦點相同的返回／取消語意（頁面上沒有可取消的 UI 時不作用）；**不是棄置快捷鍵** |
| Y（手牌） | 焦點在整張手牌時＝以行動使用：點擊該卡既有「行動」按鈕；隱藏或停用則不作用 |
| Y（購買卡） | **先 B 選擇，再按 Y**：焦點卡是有效的已選擇卡（選擇按鈕可見、未停用）且既有「購買所選」可用時，點它開啟既有購買確認單（內容是目前整份選擇；確認、資源檢查與 `buy_cards` 都在既有確認單）。未選擇、選擇按鈕停用／隱藏（例如售完）、合計買不起（按鈕停用）、按鈕隱藏或不存在一律 fail closed；**Y 永遠不會選擇任何卡**、不直接購買。與客廳模式同一個函式與閘門 |
| Y（地圖目標） | 焦點在地圖城鎮目標時＝該目標的既有地圖操作（建立組織／確認移動／瓦解組織，見下方協定 `act`），與客廳模式同一條 iframe `act`＋`req` 確認路徑與閘門：可先用 A 走既有選取，也可直接 Y（iframe 會先走同一個選取）。只有對上 `req` 的 `ok:true` 才算執行（之後上處理中鎖）；沒有操作的目標（例如一般來源）、沒有 iframe、`ok:false`、1 秒逾時一律 fail closed，且不切換說明 |
| R / SR | **選取六個全域區段的唯一方式**，與客廳模式同一個環：指揮中心→戰略地圖→戰況紀錄→我的陣營→事件卡→時代關卡（點既有分頁／開既有說明 modal；在事件卡／時代關卡說明 modal 內按 R／SR 以既有關閉收起並前往下一個區段，其他 modal 一律停用）。必選地圖目標時只回戰略地圖（已在地圖則不動）。切換後焦點放到新區段的內容，不留在分頁上（大廳則為區塊）。環上另有一個**額外焦點（不是第七個頁面）**：導覽列的「Joy-Con 說明」按鈕（時代關卡之後、回合列之前）；R／SR 到達時只聚焦按鈕、不切頁也不開圖，再按 R／SR 離開並繼續循環 |
| Joy-Con 說明按鈕 | 焦點在按鈕上：A 開啟 Joy-Con 功能表原圖（`static/help/joycon-function-table.jpg`，1280×960，保持比例不裁切，小螢幕可捲動）；B 不作用。圖片開著＝modal scope lock：B（或 Esc、×、背景點擊）關閉並把焦點還回按鈕；R／SR、SL、ZR、X、Capture、`+` 都不穿透。滑鼠點按鈕同樣開啟。方向鍵不會落在按鈕上 |
| CAPTURE | 既有「結束行動／結束步驟」，經危險確認單（預設焦點「返回」，向右到「確認」再按 A 才執行；與客廳模式同一張確認單與閘門）；結束行動本身不是方向焦點。實體鍵：只接右 Joy-Con 2 時送出 b1 `0x40`（上游 `c`，2026-10-10 實錄）；上游 `capture`（b1 `0x20`，左 Joy-Con 2／Pro）同樣接受 |
| `+` | 發動唯一一個可見、啟用的既有陣營能力（例如賭徒耳語）；沒有或不只一個時不做事 |
| SL | **全域地圖聚焦選單**（與客廳模式相同，見下方「SL 全域地圖聚焦」）：任何遊戲分頁、不需要 pending choice；依「統治者」或「陣營區域」選 canonical 地圖上的任一城鎮，戰略地圖把它精確置中並放大到固定層級。只改地圖相機與 focus ring／標籤，不建立、移動或瓦解。選單開著時再按 SL＝關閉；其他 modal 內不作用 |
| ZR | **戰略地圖縮放循環**（與客廳模式相同，見下方「ZR 戰略地圖縮放」）：在戰略地圖每按一次放大一級，到最大後再按回到最小（最大地圖範圍）。不需要焦點，第一下就執行；其他分頁、任何 modal（含 SL 聚焦選單）完全不作用，連焦點都不改 |
| X | 非手牌焦點時不作用（回合列不是方向焦點，改用 CAPTURE） |
| Y | 其他焦點時顯示／隱藏操作提示（手牌、購買卡、地圖目標見上；其他卡牌焦點時 X/Y 完全不作用；聚焦選單內不作用） |
| 按住 STICK 2 秒 | **遊戲選單**（見下方「遊戲選單」）；短按 STICK、HOME 桌面模式不綁定 |

### 遊戲選單（按住搖桿按鈕 2 秒）

- 遊戲中，本分頁目前操作的 Joy-Con（hot-seat＝目前行動席位綁定的那一支）按下搖桿並**保持搖桿在中央**持續 2 秒，開啟置中的「遊戲選單」。左右 Joy-Con 的按下搖桿都由 bridge 正規化成邏輯 STICK。
- 累積中搖桿離開中央、放開、按了其他任何鍵、失去資格或情境改變（換手把／重新連線、換分頁 scope、換行動者或 pending choice）→ 立即取消，放開後重新按下才重新累積。從 baseline 起就按住的 STICK 不累積。長按的 STICK 不當成一般按鍵 dispatch。
- 不開啟：開始流程／Joy-Con 配對／自動建房、載入（尚無 state）、交接遮罩、任何 modal／overlay、分頁隱藏、bridge 未連線或未綁定、不是目前行動席位的 Joy-Con；必選地圖目標停在其他分頁時 STICK 維持「先切回戰略地圖」，到地圖上再長按（`Core.gameMenuBlocker`）。
- 選項：**返回遊戲**、**Joy-Con 設定**（既有 Joy-Con 說明按鈕／`openJoyconHelp`）、**重新開始…**（只開第二層確認，明確顯示會離開目前遊戲）。確認層 A＝點既有 `/new-game` 連結；B＝回到遊戲選單（焦點回到「重新開始」）；選單 B＝返回遊戲並還原開啟前的焦點。滑鼠可點每一項，點背景＝返回。
- 搖桿上下導覽（不循環；確認層左右在兩個按鈕間移動），A 執行；其他鍵一律不作用。release gate：開啟時 STICK 仍按住 → 放開前選單不接受任何輸入；換層級時仍按住的 A／B 放開前不作用（同一個按住的 A／B 不會連續觸發兩層）。
- 開啟、導覽、取消都不送遊戲 mutation、不消耗行動、不改地圖。沒有任何立即重新開始的快捷鍵。
- 說明圖（`static/help/joycon-function-table.jpg`，使用者提供的原圖）未修改（原 `alt` 描述它標示「按下搖桿，目前無功能」）；`alt` 文字與 🎮 面板說明已更新為長按開啟遊戲選單。

**必選地圖目標停在其他分頁**（兩種顯示模式相同）：必選地圖目標時其他分頁沒有任何焦點。既有流程在手上還有可排入的建立／瓦解卡（`queueable_card_names`）時刻意不自動切到地圖，讓滑鼠可以繼續排入；控制器則：
- 控制器使用中（`padActive`）出現這類 choice 時，reconcile 以既有分頁切換（與 R／SR 同一條路）自動帶到戰略地圖，**每個 choice 只做一次**（`choice_id`）；之後滑鼠離開地圖不會被再拉回。客廳輪流遮罩期間或不是該席位的 Joy-Con 時不自動切換（`gate.allowsPage`）。
- 仍停在其他分頁時，方向與 A／B／X／Y／R／SR／STICK／`+`／CAPTURE 先切回戰略地圖，**該輸入本身不執行**（第一次輸入也一樣；此時 STICK 不累積遊戲選單長按）。SL 走自己的「切到地圖再開聚焦選單」流程；ZR 在其他分頁照舊完全不作用；未對應的按鍵不做事。
- 切到地圖時 iframe 可能尚未掛載或還在載入：controller 依序補要 snapshot（250ms～4s，共 5 次，有目標的 choice snapshot 到達、鎖解除或離開地圖即停止），iframe 載入完成與地圖狀態變更時也會自己推送；第一份有目標的 snapshot 到達後焦點放到地圖目標（桌面＝地圖城鎮目標，客廳＝地圖清單）。snapshot 只讀，所有建立／移動仍走既有 `act`＋`req` 與 iframe 重驗。
- 只在 page scope、bridge 已連線、遊戲畫面顯示、戰略地圖分頁可用時才切換（`LR.choiceMapRedirect`）；其他一律不動。

第一次有效操作（含 CAPTURE／`+`）只會把焦點放上去，不會執行；預設焦點與區段切換後的落點都是內容（指揮中心先放手牌）。ZR 不在此列：在戰略地圖不需要焦點，第一下就直接執行一次縮放循環（不放焦點、不改焦點）；不在戰略地圖時完全不作用，連焦點都不改。
區段切換時，該區段只要有可取得方向焦點的內容就一定落在內容上；經確認沒有任何這類內容的區段可以維持無焦點，但一定仍可用 R／SR 離開。
搖桿輸入、reconcile 與焦點變更時，若瀏覽器原生 focus 停在上述排除的控制上（例如滑鼠點過分頁），一律放掉；整張卡牌 div 本身無法取得原生 focus。
滑鼠點擊分頁、手牌按鈕、結束行動、購買選擇按鈕等完全不變。遊戲畫面只有一個精簡提示膠囊，位於主導覽列下方、隨機購買卡上方的中央（不遮住導覽、購買卡、購買操作鈕與陣營能力；只是提示，不可點擊）；開始畫面／大廳仍在右下角；專用鍵 fail closed 時，原因（例如「先按 B 選擇這張卡，再按 Y 購買」）會在膠囊前段顯示約 1.8 秒。

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
- `static/controller_ui.js`：bridge client、設定與 HUD、DOM 焦點集合、焦點標示（`.rl-pad-focus`；卡面使用 2px 不透明黃色邊框且框內透明，其他控制項使用高對比外框，不改版面）、`scrollIntoView`。
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
  在地圖狀態改變時推送（已合併）。座標是 iframe 內的 client 座標；目標座標可以遠在畫面外（例如思想家的無視距離候選遍布全圖，SL 聚焦利雅德（zoom 9）後北美目標約 −6 萬 px，再按 ZR 放大到 zoom 10 約 −12 萬 px），
  parent 只拒絕非有限數或超過 `MAP_POINT_LIMIT`（256px 圖磚在 zoom 22 的世界寬度）的值；按鈕外框是視窗內的 DOM rect，維持 ±100000 上限。選用欄位 `act`（客廳模式 Y 用）＝該目標的既有主要操作：
  choice 目標依 pending choice 為 `build`／`dissolve`；move 目標為 `move`；origin 只有可瓦解共享組織時為 `dissolve`。
  與 role／scope 不相容的 `act` 會讓整份 snapshot 作廢。
  選用欄位 `groupMeta: 1`（地圖目標的分組資料版本；SL 全域地圖聚焦改用下方與目標分離的 `browseTowns`）：此時每個目標都帶 `ruler`（1–8 個）、`camp`（0–16 個）字串陣列，由 iframe 取自 canonical
  `/map-data`（`data/map.json` 的 `towns[town].ruler`／`.camp`，即統治者與陣營區域＝發展空間標籤）。iframe 端任一目標的 canonical 資料缺欄位、
  不是陣列、數量不合或含不是 1–16 字字串的名稱時，整份 snapshot 都不帶 `groupMeta` 與分組欄位（不過濾、不截斷、不補值；其餘地圖控制照常）。
  parent 端：版本不是 1、宣告了版本卻缺欄位或 `ruler` 為空、沒宣告版本卻帶欄位、名稱不合或數量超過上限一律整份作廢；重複名稱只算一次（同一份成員資格）。
  選用欄位 `browseMeta: 1`＋`browseTowns:[{town, ruler, camp}]`（SL 全域地圖聚焦的完整 canonical 城鎮清單，與 `targets` 分離）：iframe 由 canonical `/map-data` 帶出**全部**城鎮，
  與 pending choice、地圖目標、回合與地圖篩選無關；任一城鎮的分組資料不合法時整份不帶清單（不宣告 `browseMeta`）。parent 端：版本不是 1、宣告了版本卻缺清單或清單為空、
  沒宣告版本卻帶清單、城鎮重複、超過 400 座或任一城鎮資料不合一律整份作廢。`browseTowns` 不會成為 action target，`targets`／`groupMeta` 也不受它影響。
  選用欄位 `req`：只有回應帶 `req` 的 `snapshot` 指令時才帶（原樣回傳，必須是合法 request id），一般推送沒有。
- parent → iframe：`redline-controller-command`，`cmd` 為 `snapshot`、`focus {town}`、`clearFocus`、`activate {town}`、`button {id}`、`cancel`、`act {town, id, req}`（`id` 只限 `directBuildBtn`／`confirmMoveBtn`／`dissolveBtn`）、`zoom {req}`（ZR 縮放循環，見下方「ZR 戰略地圖縮放」）、`focusTown {town, req}`（SL 全域地圖聚焦：canonical 城鎮置中放大，見下方「SL 全域地圖聚焦」）。**`act`、`zoom` 與 `focusTown` 必須帶合法 `req`**，沒有或不合法的 `req` 在 iframe 端直接丟棄、不執行，它們的 result 也必須帶 `req`；其他指令可選 `req`（正整數 request id）。
- iframe → parent：`redline-controller-result` `{cmd, req, ok, reason, via}`，每個指令處理完都回覆；`req` 原樣回傳（沒帶則為 `null`），`via` 為 iframe 實際走的既有控制（按鈕 id，或取消時的 `cancelDissolveChoiceBtn`／`selection`）。
  地圖執行型指令（兩種顯示模式的 Y 地圖操作；客廳模式另有清單選取、清單取消）、ZR 的 `zoom`、SL 聚焦選單的 `snapshot` 請求與 `focusTown` 都帶 `req`，且同時只有一筆等待確認：**只有對上該 `req` 的 `ok:true`（iframe 執行前已重驗）才算執行**，此時才記錄 250ms 冷卻（SL 聚焦選單的 `snapshot` 請求例外：`ok:true` 只表示可以採用同一個 `req` 的 snapshot，真的開啟選單後才記錄），Y 地圖操作與 `via: cancelDissolveChoiceBtn` 的取消再上處理中鎖（`zoom`、`focusTown` 不是遊戲動作，不上處理中鎖）。沒有 iframe、`ok:false`、1 秒內沒有回覆、過期或對不上的 `req` 一律 fail closed，不記錄冷卻也不上鎖；等待期間其他執行型按鍵被擋下（不重送），回覆或逾時後立即解除。桌面模式的 A／B（`activate`／`button`／`cancel`）不帶 `req`，行為不變。
- `act` 在 iframe 內：(1) 用權威資料重驗 town 是目前目標、其 `act` 對應的既有按鈕等於 `id`（否則 `not-a-target`／`action-mismatch`）；(2) 按鈕尚未作用在該 town 時，走與 A／滑鼠相同的既有 marker click 選取／預備；(3) 再驗一次目標仍在、按鈕可見啟用且作用在該 town，才 `click()` 既有按鈕（否則 `button-unavailable`）。失敗時不點任何按鈕、不送出遊戲動作（最多留下與按 A 相同的選取／預備狀態）。

焦點集合只來自伺服器權威資料，且**每個指令執行當下 iframe 都重新驗證**（parent 的 snapshot 過期或被偽造也不會讓非法目標可 action）：

- pending choice 目標：`supportChoiceHighlight.towns`（伺服器 pending choice 投影），限可見且已知城鎮。
- 移動：目前選取來源的 `legal_organization_moves`（`selectedMoveTargets`），以及可行動的來源城鎮。
- 缺狀態、不是自己的回合、有 pending choice 卻沒有地圖 highlight → 沒有任何目標（fail-closed）。
- 按鈕只限白名單 `directBuildBtn`、`confirmMoveBtn`、`dissolveBtn`、`cancelDissolveChoiceBtn`，且必須存在、可見、未停用。

A 對城鎮走既有 marker `click` 路徑（選取來源／預備移動目的地／選擇 pending choice 候選），對按鈕呼叫既有 `click()`；是否真的移動、建立或瓦解仍由既有確認按鈕與伺服器驗證決定。B 只會：點可見且啟用的「取消瓦解」，或取消目前選取（既有「點地圖其他地方取消」流程）；兩者都沒有就不做事。焦點城鎮以黑底＋黃色雙圈與名稱標籤標示，必要時 `panInside`。

## 客廳大螢幕模式（living-room，已移除）

**2026-10-25 起產品只保留桌面模式，這個顯示模式已無任何入口**：🎮 設定面板不再有「顯示模式」選單，`?display=living-room` 被忽略，
`localStorage` `redline.display.v1` 裡舊的 `living-room`（或任何非 `desktop` 值）在載入時遷移成 `desktop`，`RedlineDisplayMode.set('living-room')` 也只會得到桌面
（`LR.resolveDisplayMode`／`normalizeDisplayMode` 一律回傳 desktop）。舞台縮放的 5% title-safe 分支已刪除。
`controller_living_room.js` 與 `living_room_core.js` 仍保留：桌面 Joy-Con 共用其中的 Capture／`+`、購買卡 Y、一般奧援 X 危險確認、地圖 Y／ZR、
R／SR 區段環、SL 聚焦選單、必選地圖目標重導與閘門。客廳專用的內容區導航、提示列與 `html[data-display="living-room"]` CSS 目前為不會執行的休眠程式碼，
下面保留原說明供日後清理參考。

（以下為移除前的說明）同一 route、同一 DOM、同一套遊戲 action：`html[data-display="living-room"]` 只切換 CSS 版面層並加上搖桿的內容導航與專用快捷鍵。
開啟方式（已移除）：網址加 `?display=living-room`，或 🎮 設定面板「顯示模式」。桌面模式（預設）版面不變，搖桿操作見上表；兩種模式共用同一份方向焦點排除規則、同一個 R／SR 六區段環與同一套 Capture／`+` 流程，客廳模式另外多了內容區兩層導航、按鍵提示列與下列專用鍵。

- **安全區與字級**：舞台等比縮放後再留 5% title-safe（`resizeStage` 乘 0.9）；文字 16–28 設計單位，720p／1080p／4K 只差銳利度。卡牌列使用無捲軸的單列半高卡，完整卡面用 A 預覽（放大到畫面高約 80%）。
- **方向鍵只在內容資料間**：內容區＝常設購買區、隨機購買區、陣營／根據地候選（只有非能力鈕的內容選項時才出現）、手牌、玩家動態（縮小在左下角的對手通知）；戰略地圖分頁是地圖目標清單；其他分頁是該分頁內容。
  方向焦點**永遠不會**落在：手牌卡內的「資源」「行動」「棄置」、結束行動／紅軍能力（回合列）、六個全域分頁、購買選擇按鈕、陣營能力發動鈕、按鍵提示列（`LR.isDirectionalExcluded`＝`Core.isDirectionalExcluded`，與桌面模式同一份）。手牌與購買卡只以整張卡取得焦點；瀏覽器原生 focus 停在這些控制上時，搖桿輸入、reconcile 與焦點變更都會放掉它。
- **六個全域區段只由 R／SR 選取**：指揮中心 → 戰略地圖 → 戰況紀錄 → 我的陣營 → 事件卡 → 時代關卡（依分頁列順序循環；隱藏或停用的分頁跳過；有多個時代關卡時各是一站）。時代關卡之後是額外的「Joy-Con 說明」按鈕焦點（`LR.RING_HELP_KEY`；不是區段，只聚焦、A 才開圖），之後循環回指揮中心；必選地圖目標時不提供。
  分頁＝既有分頁切換；事件卡／時代關卡＝既有開啟說明 modal，在這兩個唯讀說明 modal 內再按 R／SR 會用該 modal 既有的關閉控制收起並前往下一站。其他 modal 一律維持 scope lock（R／SR 不作用）。
  有必選地圖目標時：在戰略地圖 R／SR 停用；在其他分頁 R／SR 只會回到戰略地圖，其他分頁沒有內容區。
- **兩層導航**：區域層用搖桿在內容區之間移動（邊緣距離＋重疊，確定性），A 進入；內容層在區內移動，到邊界停住，不跨區。

| 輸入 | 區域層 | 內容層 |
| --- | --- | --- |
| 搖桿 | 在內容區間移動 | 卡牌列依索引左右（上下換列）、地圖清單上下；到邊界停住 |
| A | 進入區域（還原上次項目） | 卡牌＝查看；內容控制項＝既有 click；地圖清單＝選取／預備（不執行） |
| B | 不做事 | 購買卡＝選擇／取消；手牌不做事（**不棄置**）；地圖清單有既有取消流程時＝取消；其他＝回區域層 |
| X | 不做事 | 手牌＝資源；**一般奧援手牌＝既有「棄置」（危險確認）**；其他不做事 |
| Y | 說明 | 手牌＝行動；**購買卡（先 B 選擇）＝既有「購買所選」**；**地圖目標＝建立組織／確認移動／瓦解組織**；其他＝說明 |
| R／SR | 下一個／上一個全域區段 | 同左 |
| PLUS（+） | **發動既有陣營能力** | 同左 |
| CAPTURE | **既有結束行動／結束步驟（危險確認）** | 同左 |
| STICK（按下搖桿） | **下一個內容區**（直接進入、還原上次項目；只移焦點） | 同左 |
| SL | **全域地圖聚焦選單**（任何分頁皆可開，不需要 pending choice；選任一 canonical 城鎮置中放大，只改地圖相機與焦點） | 同左 |
| ZR | **戰略地圖＝放大一級，到最大後回到最小**（不需要焦點，第一下就執行；必選地圖目標時也可用）；其他分頁完全不作用，連焦點都不改 | 同左（焦點、區域與層級都不變） |

ZR 不再回區域層或回指揮中心：要回區域層用 B（非卡牌項目與地圖清單），換區用按下搖桿，換分頁用 R／SR。

- **專用快捷鍵**（全部只點擊當下可見、啟用、合法的既有控制；按下當下重驗，失效即 fail closed 並在狀態列顯示原因）：
  - CAPTURE：`advanceStepBtn`（結束行動／結束回合／開始行動階段）→ 危險確認單，預設焦點「返回」；連按不會開第二張確認單；確認單開著時按鈕失效或文字改變（換了步驟）就自動關閉不執行。
  - PLUS：`#factionActionButtons` 內的既有發動鈕（例如「發動 賭徒耳語」）或 `redArmyAbilityBtn`，**恰好一個可用**才點擊；沒有或多於一個不做事。點擊後若沒有開啟既有視窗（handler 直接送出伺服器動作）才上處理中鎖。
  - 手牌 X（一般奧援）：該卡第一顆標示「棄置」的既有按鈕 → 危險確認單（預設「返回」；以手牌 key 綁定，確認當下再驗）；按鈕停用／隱藏時 fail closed。紅軍奧援的「資源」與其他卡牌永遠不是棄置（X＝資源）。桌面模式同一套（`runDesktopCardDiscard`）。
  - 購買卡 Y（與桌面模式相同）：**先用 B 選擇焦點卡，再按 Y**。焦點卡是有效的已選擇卡（選擇按鈕可見、未停用，即仍在既有購買選取內）且既有「購買所選」可用時才點它，開啟既有購買確認單（內容是目前整份選擇）；資源檢查、確認與 `buy_cards` 送出都在既有流程。未選擇、選擇按鈕停用／隱藏（例如售完）、資源不足（按鈕停用）、按鈕隱藏或不存在一律 no-op 並顯示原因；不會自動選擇、不建立新購買 action。
  - 地圖 Y（與桌面模式相同）：清單列 `act` 對應的既有按鈕（`directBuildBtn`／`confirmMoveBtn`／`dissolveBtn`），以 iframe `act` 指令＋`req` 確認執行（見上方協定）；沒有 `act` 的列（例如一般來源）不做事。pending choice 目標用 A 選取後焦點**留在該列**（只有換了一份清單——來源 ↔ 目的地或換來源——才回第一列），所以接著按 Y 就是在剛選的城鎮建立／瓦解。
  - STICK：只移焦點，不執行；新焦點視為非使用者指定，300ms 內忽略 A／B／X／Y。沒有內容區時不做事。
  - ZR（與桌面模式相同）：戰略地圖縮放循環，見下方「ZR 戰略地圖縮放」。
- **按鍵提示列**：固定在畫面下緣，**不接受焦點也不接受滑鼠**，只在 bridge 已連線時（未啟用、連線中、無法連線、訊號中斷時整列清空）以「鍵＋標籤」顯示目前可用的專用鍵操作（例如 `Y 購買所選 1 張`、`X ⚠ 棄置 歐洲奧援`、`SL 聚焦選單（289 個城鎮）`、`+ 發動 賭徒耳語`、`Capture ⚠ 結束行動`、`Y 移動 臺北→宜蘭`），來源同樣只限可見、啟用的既有控制（SL 只在最新 snapshot 帶完整 canonical 城鎮清單時出現，與 pending choice 無關；數字只是提示，開啟時仍以 req 綁定的新 snapshot 為準；聚焦選單開著時提示列清空，legend 改為選單按鍵）。「清除」與「卡牌置頂」不再有搖桿入口（滑鼠照常可用；搖桿可用 B 逐張取消勾選；未使用的頂牌權利在結束行動時由伺服器既有流程處理：只有一張候選時自動置頂，多張時開既有選擇視窗）。
- **地圖兩段式清單**：來源（可行動城鎮）→ A → 該來源的伺服器合法目的地（依消耗、道路先於鐵路排序）→ A 只預備移動、Y 直接走既有「確認移動」。pending choice 目標：A 只選取、Y 走既有「建立組織」或「瓦解組織」。清單只來自 iframe 權威 snapshot（選用欄位 `selected`、`pending`、移動目標 `mode`／`cost`、目標 `act`，有給就嚴格驗證），iframe 執行每個指令前仍重驗；沒有 snapshot 或目標時清單為空、A／Y 無作用。滑鼠仍可直接操作地圖。
- **防誤觸**（數值不變：處理中鎖 1500ms、重繪冷卻 300ms、執行冷卻 250ms、地圖確認逾時 1000ms）：送出遊戲動作後到下一份 state（或 1.5 秒）前不再送出 A／B／X／Y／CAPTURE／PLUS 類指令（處理中鎖）；任何**實際執行**（click 既有控制、開啟預覽／確認單／購買確認／說明 modal、B 勾選、iframe 確認成功的地圖操作與 ZR 縮放、成功進入區域，以及客廳模式下 modal 內的 A）之後 250ms 內不接受下一個執行型按鍵（fail-closed 的 no-op 不啟動冷卻；方向、R／SR、STICK、ZR、回區域層與 modal 的 B 不受影響）；重繪、分頁切換或 STICK 造成的焦點換項目後 300ms 內忽略與焦點有關的 A／B／X／Y（CAPTURE／PLUS 與焦點無關，不受此冷卻）；重繪後同 key 留原位、key 消失留同區域同索引、區域空了回同一分頁的預設內容區層，永不跨區域；沒有任何危險控制可取得方向焦點。第一次有效操作（含 CAPTURE／PLUS）只放焦點；戰略地圖上的 ZR 不需要焦點，第一下就執行縮放（不放焦點）。斷線／stale／重連 baseline 沿用上方規則（重連時按住 A＋PLUS＋CAPTURE 也不觸發）。

## 客廳輪流（hot-seat，多位玩家共用一台螢幕）

預設關閉；大廳勾選「客廳輪流（同一台多位玩家）」才啟用（`localStorage` `redline.hotseat.v1`）。未啟用、目前遊戲的本機席位少於兩個、或連線的不是本機席位時完全不介入，單席位桌面／客廳模式不變。

- **席位**：同一瀏覽器、同一房間可保存多個席位，各自 `playerId`、`resumeToken` 與 Joy-Con 綁定。「新增本機玩家」以上方玩家名稱 `/join`（不帶舊 token，一定是新席位）；同一 `player_id` 只更新 token，不覆寫其他席位；新增後**不自動切換**，留在目前席位。本機玩家名稱不可重複。
- **行動代號（P1～P4，Joy-Con 玩家不必打字）**：本機席位的系統預設代號依 **server `/lobby` 的 players 順序**（加入順序；只 append、改名不移位）＝P1、P2、P3、P4，與目前顯示哪一席、本機清單順序、切換席位或重新整理無關（`Core.seatCodename`／`codenameRenames`）。房間最多 4 位真人（AI 紅軍時 3 位），所以不會有 P5；已滿時「新增本機玩家」顯示「作戰室已滿」且不送出。
  - **系統預設 vs 自訂**：「你的行動代號」欄的 HTML 預設值是 `host`；建立／進入作戰室**送出當下**，欄位仍是預設值（或空白）且使用者從未在欄位輸入過，才記為系統預設（`redline.sessions.v1` 的 `name_auto`，隨席位存成 `auto_name`）。使用者輸入過的名稱（即使字面也是 `host`）一律是自訂，永不被覆寫。建房後才勾選客廳輪流時，以建房送出時的紀錄判斷。
  - **新增本機玩家**：沒有在欄位輸入新名稱時，用它將加入的 server lobby 位置的代號（`Core.nextSeatCodename`）；輸入了就用輸入的名稱（自訂）。
  - **寫回伺服器**：客廳輪流啟用、本機至少兩席、尚未開局時，系統預設代號的本機席位若與 server lobby 名稱不同，以既有 `/join`（該席 `player_id`＋它自己的 `resume_token`）改名，寫進伺服器權威 lobby（開局時玩家名稱取自這裡）；成功後才更新本機席位與畫面，失敗 3 秒後再試。只有一席、未啟用客廳輪流、已開局時不改名（單席位與一般流程不變）。
- **大廳列**：每個本機席位一列，顯示玩家名稱（目前連線的席位標「目前」）、已選陣營／根據地、準備狀態與 Joy-Con 綁定狀態，資料只來自 server `/lobby` 公開資料與席位綁定。每列兩行：玩家名稱；下一行左邊是「陣營／準備｜」，右邊是**靠右對齊的緊湊群組**：安全名稱＋狀態燈 → 綁定下拉 → 「切換」（群組內沒有撐開的空白，空白只在陣營／準備與群組之間）。安全名稱＋燈是固定寬度欄 `7.5em`（12px 字＝90 設計像素，靠左起排），所以每列的名稱（或「未綁定 Joy-Con」）左緣對齊成一欄：容得下最長的「右 Joy-Con 4」＋燈（Chrome 實測 89.2 設計像素）與「未綁定 Joy-Con」，較短的名稱只在燈之後留白，不裁切。目前席位不能切換到自己，該位置是同尺寸、不可見、不可點、不可聚焦、對輔助技術隱藏的佔位，所以每列下拉的右緣對齊成一欄。Joy-Con 狀態（`Core.seatJoyStatus`）：**已綁定一律只顯示安全名稱＋對應色燈，不加任何可見狀態文字**——連線正常＝綠；訊號中斷＝琥珀；其他分頁使用中＝紅；未偵測到（不在 bridge 清單）、bridge 未連線、搖桿控制未啟用＝灰色空心。該席目前綁定的下拉選項也不附加狀態註記（其他選項仍註明不可選的原因）。綁定下拉固定為緊湊寬度 `9.25em`（12px 字＝111 設計像素）：容得下最長的安全名稱「右 Joy-Con 4」與「— 未綁定 —」＋原生箭頭（Chrome 實測自然寬 106 設計像素），不再依展開清單裡最長的選項撐寬。未綁定＝「未綁定 Joy-Con」文字。燈是 `role="img"`，`aria-label` 與 `title` 都是完整狀態（例如「右 Joy-Con 2：其他分頁使用中」）；可見名稱對輔助技術隱藏，避免重複朗讀。錯誤永遠不會顯示成綠燈。
- **玩家看到的手把名稱**（`Core.controllerNames`，與上方 HUD 同一規則）：只有左右，例如「左 Joy-Con」「右 Joy-Con」；同側有多支時依**目前 bridge roster** 加本機顯示序號「右 Joy-Con 1」「右 Joy-Con 2」（依埠號、同埠再依完整 id），所以大廳列、🎮 HUD、每個分頁與監聽連線看到的相同；綁定但暫時不在 roster 的手把只顯示左右（例如「右 Joy-Con」＋灰色空心燈，aria／title「右 Joy-Con：未偵測到」）。同側手把增減時序號可能改變。大廳列、下拉選項、提示文字與交接遮罩都**不顯示** FTCW UDP 埠、bridge 回報的名稱（含指紋）或內部 id。
- **大廳綁定**：每列一個下拉，列出 bridge 的每一支手把。選項的 value 是精確 identity（例如 `L24801-…`、`R24800-…`；左右是不同玩家，同側多支依埠＋名稱指紋區分），綁定與 claim 一律用它；選項文字只有上面的玩家名稱。選一支＝綁定或改綁（原本那支釋出），「— 未綁定 —」＝解除。已綁給其他本機席位的手把不可選並註明「已綁給〈玩家〉」；強制送出也會被拒絕（`controller-taken`，store 不變）。綁定存在 `localStorage`，重新整理、bridge 重連、手把暫時 stale 都不改變綁定，也不退化成左右或名稱。
- **大廳的 bridge 連線**：bridge v2 一條 WebSocket 連線最多擁有一支、且只收得到那一支的 frame（bridge 驗證 claim，每支只有一位擁有者，連線結束即釋放）。因此大廳裡：
  - **主連線**（`controller_ui.js`）只 claim **目前席位**綁定的那一支，照既有 focus／modal routing 操作大廳；
  - **監聽連線**（`hotseat_ui.js`）：其他每個已綁定、在 server lobby 內的本機席位各開一條 bridge 連線，送 `hello` 後只 claim 該席的精確 controller id（別的連線正擁有、沒有訊號或不在清單時等待，不搶）。frame 沿用 controller_core 的 `classifyBridgeMessage`／`acceptControllerFrame`／`stepControllerInput`（重連與換手把第一筆只當 baseline），只看 reducer 產生的 A，其他鍵一律丟棄、不路由；
  - 未綁定的 Joy-Con 沒有監聽連線。大廳期間 controller_ui 的單手把自動 claim 暫停，不會搶走綁定流程；開局（或切換席位重新載入）時所有監聽連線關閉。
  - 主連線看到本分頁監聽連線擁有的手把是 `owner:'other'`；大廳列顯示時視為本分頁的（`withLocalOwners`），顯示綠燈，不誤報「其他分頁使用中」。
- **大廳按 A**：任何本機席位、任何時候（不論輪次、是否已選陣營或準備）用**自己已綁定**的 Joy-Con 按 A，都會切到自己的席位：記下 `{active: 該席, unlocked: false}` 後整頁重新載入，`/resume` 以該席自己的 `playerId`／`resumeToken` 重新授權（不只切 DOM 或 playerId）；該席未選陣營時自動開啟它自己的「選擇陣營與根據地」，已選則顯示它的大廳狀態。目前席位自己的 Joy-Con 按 A 不切換；它尚未選陣營且視窗沒開時，A 點既有「選擇陣營與根據地」按鈕，之後方向鍵與 A／B 走既有 modal focus routing，選擇送出時一律是目前席位的 `player_id`。
- **不得代替其他席位**：其他席位的 Joy-Con 除了 A（切到它自己的席位）以外的輸入，都不會操作目前席位（不移焦點、不開視窗、不送出選擇）。未綁定任何本機席位的 Joy-Con（即使被手動選到主連線）一律攔下並顯示「這支 Joy-Con 尚未綁定任何本機席位」，不能切換。目前席位未綁定時（`lobby-bind`），主連線不 claim，任何 Joy-Con 都不能代替它操作，但其他已綁定席位仍可按自己的 A 進入自己的席位。沒有可信大廳狀態時 fail closed（不 claim、不監聽、不切換）。
- 滑鼠「切換」走同一條重新載入路徑。大廳切換**不解鎖遊戲**：開局後第一位行動者仍要交接確認。
- **三個身份分開**：displayed viewer（主頁 WebSocket 以哪一席的 token 連線）、controller owner（bridge 判定本分頁擁有的 Joy-Con 及其綁定席位）、authoritative actor（只讀伺服器 state，優先序：`pending_choice.player_id` → `hk_base_relocation_player_id`（須同時 `hk_free_base_relocation`）→ 選基地的 `pending_base_choices` → `current_player`）。交接只由 actor 驅動，不讀 DOM。除錯：`RedlineHotSeat.getState()`。
- **香港抗暴之戰免費遷移根據地**：窗口開啟時伺服器凍結換人（`current_player` 仍是整輪最後一席），state 以 `hk_base_relocation_player_id` 明確給出要決定的香港玩家（只有 `hk_free_base_relocation` 開啟且唯一找到香港玩家時才有值，否則 `null`；公開資料，每個檢視者相同）。香港席位照一般交接遮罩、以其綁定 Joy-Con 按 A 確認，再以香港 `resumeToken` 重新載入。前端不以陣營猜：旗標關閉時忽略殘留 id；旗標開啟但 id 缺少或不在玩家清單時 fail closed（等待遮罩）。香港不是本機席位時顯示等待遮罩。棄牌等 `pending_choice` 未解決前仍交給該選擇的擁有者；香港「遷移／留在」後窗口關閉，依新 state 交給下一位。
- **交接遮罩**：actor 換人時（含非本回合玩家的 pending choice、選擇解決後交回），在 render 前先以不透明全螢幕遮罩蓋住舞台，舞台與其他頂層節點 `inert`、鍵盤與所有 Joy-Con 輸入都不穿透，顯示「請交給〈玩家／陣營〉」。遮罩沒有關閉鈕。actor 不是本機席位（遠端玩家、AI 紅軍）或沒有權威狀態時顯示「等待〈玩家〉行動」，也不顯示任何席位畫面。遮罩一出現就鎖住：即使權威回到同一席位也要重新確認。
- **AI 紅軍公開行動視窗**：權威 actor 是 AI 紅軍（`state.ai_red_army.player_id`、陣營 `red_army`、`state.current_player` 仍是紅軍）時仍是「等待」遮罩，但遮罩內改顯示置中的「AI 紅軍行動中」公開視窗（`Core.aiPublicView`，1280×720 設計單位、隨 `--stage-scale` 等比縮放）：最新一步在最上面，列出該步 log（卡牌、購買、移動、組織、事件）與資金／宣傳變化。資料來自伺服器 `state.ai_red_army.public_report`（`red_army_ai_runtime` 寫入，每步最多 12 行、保留最近 40 步，換回合重新開始）；英文句型轉成繁體中文，仍含英文者不顯示。視窗開著時 `renderPeerActionNotice` 只消耗 log、不再顯示「玩家動態」。**結束回合的等待確認由伺服器負責**：前端在客廳輪流遊戲連線後送一次 `ai_public_hold`；AI 紅軍要結束回合時伺服器先停在 `current_player`＝紅軍並廣播 `ai_red_army.awaiting_ack`（視窗標題變「回合結束」、出現「知道了」），「知道了」或 A（`ack_ai_red_army`，不受輪到誰限制）或逾時 10 秒（`AI_ACK_TIMEOUT_SECONDS`）後才送出結束回合、換到下一位並進入交接。視窗期間所有 Joy-Con 輸入都不穿透。未送 `ai_public_hold` 的遊戲（一般多人、單席位）不等待。
- **確認**：本分頁改 claim 該席位綁定的 Joy-Con（bridge 權威：每支一位擁有者），接手者用它按 A。其他 Joy-Con 的 frame 本分頁收不到（也會被 `acceptControllerFrame` 丟棄）；B 等其他鍵不是確認。席位尚未綁定時，遮罩列出可綁定的手把（有訊號、不是其他分頁使用中、沒有綁給其他本機席位），選一支後再用它按 A；綁定的手把不在清單或沒有訊號時才可「更換手把」。
- **重新連線**：確認後整頁重新載入，主頁 WebSocket 與戰略地圖 iframe 都以該席位自己的 `resumeToken` 重新授權連線，前一席位的 DOM 全部丟棄；新連線的 viewer-scoped state 確認 actor 就是這一席才解除遮罩。行動中重新整理沿用本分頁的確認紀錄（`sessionStorage` `redline.hotseat.session.v1`）；新分頁或沒有紀錄時一律先遮罩要求確認。
- **顯示時**：只有綁給目前席位的 Joy-Con 能操作（其他手把即使被選取也被攔下）。

## SL 全域地圖聚焦（兩種顯示模式）

`SL` 是隨時可用的戰略地圖導覽器：任何遊戲分頁（指揮中心、戰略地圖、戰況紀錄等 page／map scope）只要沒有其他 modal，按 `SL` 就開啟置中的精簡選單（不新增頂部窄條；客廳模式底部提示列照常可見）。**不需要 pending choice、組織相關卡牌或能力，也不需要焦點**。選單列出 canonical 地圖的**全部城鎮**（不是目前的 action targets），選定城鎮後戰略地圖把它**精確置中並放大到固定層級**。聚焦只改地圖相機與 focus ring／標籤：不選取、不建立、不移動、不瓦解，不消耗行動或資源，也不改任何權威遊戲狀態。

- **候選**＝iframe 從 canonical `/map-data`（`data/map.json`）取得的全部城鎮（snapshot 的 `browseTowns`，見上方協定），與 pending choice、地圖目標、回合、資源、地圖篩選都無關。任一城鎮的 canonical 分組資料缺少或格式不合 → 整份不帶清單，選單 fail closed（`地圖資料不足，無法分組`），不過濾、不截斷、不補值。
- **兩層選單**：
  - 分組層：兩個區段，上下／左右即可選取（每列 4 個），每個選項顯示城鎮數。
    - `統治者`：canonical 地圖資料的 `ruler`。統治者含紅軍的城鎮標示「牆內」（rules.md 牆內定義）。
    - `陣營區域`：canonical 地圖資料的 `camp`（發展空間標籤）。沒有陣營標籤的城鎮不屬於任何陣營區域（仍在統治者分組內）。
    - 只列出至少含 1 座城鎮的項目；城鎮與成員資格都去重。排序：城鎮數多→少，同數依名稱（zh-Hant）；結果確定。
  - 城鎮層（A 打開分組）：第一個選項是「← 分組」（A＝回到分組層並聚焦剛才的分組），其後是該組全部城鎮（名稱 zh-Hant 順序，每列 5 個，可捲動）。預設聚焦開啟選單前的焦點城鎮（在這組時），否則第一座城鎮。目前也是地圖目標（pending choice 候選、移動目的地、可行動來源）的城鎮標「目標」，只是標示。
- **按鍵**（選單是 modal，沿用既有 modal scope lock）：

  | 輸入 | 選單內 |
  | --- | --- |
  | 搖桿／方向 | 只在選項間移動，不穿透背景 |
  | A | 分組＝打開城鎮層；「← 分組」＝回到分組層；城鎮＝關閉選單，必要時用既有分頁切換到戰略地圖（與 R／SR 相同的分頁 click），送 `focusTown` 置中放大（見下） |
  | B／SL／滑鼠 `×` | 關閉並回到開啟前的焦點，不執行任何操作（`×` 保留滑鼠操作，但不是方向焦點） |
  | R／SR、X、Y、`+`、Capture、ZR、STICK、HOME | 不作用（不切區段、不開說明／確認單、不縮放地圖、不送任何地圖操作） |

  其他 modal（危險確認、選擇視窗、卡面預覽等）開著時 SL 不作用。
- **置中放大（`focusTown {town, req}`）**：iframe 以 canonical 資料重驗城鎮，用 Leaflet `setView`（不動畫）把城鎮的**顯示位置**放在容器正中央，層級固定為 `Core.MAP_FOCUS_ZOOM`（9，比 ZR 循環最大層級 10 低一級，與開局根據地視角同級，陣營標籤仍是短標籤、按 ZR 一下才到 10；Leaflet 設了低於 9 的 maxZoom 時取該上限的整數層級，絕不超過）。黑河／海蘭泡／臥龍的 marker 是依層級的像素偏移，iframe 先到目標層級再以該層級的顯示位置置中。剛從其他分頁切回時先 `invalidateSize` 取得目前容器尺寸。驗證城鎮顯示位置在容器中心 ±1px 且層級正確才回 `ok:true`，並畫 focus ring 與城鎮名稱標籤；不走 marker click、不點任何按鈕、不改選取／預備移動／pending choice。未知城鎮（`unknown-town`）、缺座標（`town-position-missing`）、頁面或容器不可見（`map-hidden`）、層級無法同時滿足 Leaflet min／max（`zoom-unavailable`）、驗證不符（`focus-unverified`）→ `ok:false`，不留下 ring。
- **選定後的焦點**：
  - 城鎮剛好是目前的地圖目標 → 綁到既有目標焦點（桌面＝地圖城鎮目標；客廳＝地圖清單的該列），之後 A 選取、Y 建立組織／確認移動／瓦解組織照舊走既有 `act`＋`req` 流程。
  - 其他城鎮 → 只看的瀏覽焦點：不在 action 焦點集合內，A／Y 不對它執行任何操作。桌面模式提示「聚焦 〈城鎮〉（只看）」，方向鍵從地圖中心往該方向找最近的地圖目標；客廳模式停在地圖清單的區域層（狀態欄顯示「聚焦 〈城鎮〉」），A 照常進入清單。ring／標籤保留到下一次導航（方向、R／SR、進入清單、開其他視窗）；地圖目標改變（例如新的 pending choice）時，桌面模式改由既有的地圖預設焦點接手。
  - 焦點在送出 `focusTown` 時就切過去（避免關閉選單後的還原把焦點拉回舊目標而平移相機）；`ok:false`、逾時或沒有 iframe → 放掉瀏覽焦點並提示「地圖無法聚焦這座城鎮」／「地圖沒有回應，請再試一次」。
- **權威與 fail closed**：開啟與選單開著時的刷新都先向 iframe 送帶唯一 `req` 的 `snapshot` 指令，並與其他地圖指令共用「同時只有一筆等待」與 1000ms 逾時。只有**同一個 `req` 先及時回覆 `ok:true`，且同一個 `req` 的 snapshot 也在送出後 1000ms 內送達**才採用：`ok:false`、逾時、snapshot 先於 `ok:true` 或在 1000ms（含）之後才到、`req` 不同或沒有 `req` 的一般推送、不合 schema 一律不採用。等待中的請求一逾時就清掉，晚到的回覆不會再開啟。以下一律不開選單並顯示短原因：iframe 沒有回應或回覆過期（`地圖沒有回應，請再試一次`）、iframe 回覆 `ok:false`（`此操作目前不可用`）、snapshot 不合 schema 或分組資料不足（`地圖資料不足，無法分組`）、遊戲尚未開始、戰略地圖分頁不可用。城鎮在選定時已不在清單（`此範圍已沒有可瀏覽城鎮`）→ 不送 `focusTown`。
- **戰略地圖從未載入**（parent 還沒有 snapshot；iframe 只在戰略地圖可見時由既有流程掛載）：SL 用既有分頁切換到戰略地圖並提示「戰略地圖載入中…載入後自動開啟聚焦選單」；6 秒內第一份含完整城鎮清單的 snapshot 到達、且仍在戰略地圖、沒有其他視窗、bridge 仍連線時，才送出上述的開啟請求。
- **刷新只用 req 綁定的 snapshot**：選單開著時，一般推送（不帶 `req`）本身不改變選單內容，只觸發一次新的 `snapshot` 請求；畫面以那份通過上述檢查的回覆為準（例如「目標」標示更新；打開的分組不在新資料裡就回到分組層）。刷新請求失敗就關閉選單。選單被其他視窗（例如伺服器推來的選擇視窗）蓋過或離開遊戲畫面就自動關閉。
- **停用、清除與斷線**：停用搖桿控制、清除焦點、切換顯示模式、bridge 斷線（含重連中與 stale）時關閉選單並取消等待中的開啟／刷新請求與「載入後開啟」；之後才到的 iframe 回覆不會再開啟。關閉後若沒有可還原的內容（例如必選地圖目標時的指揮中心），焦點不會殘留在隱藏的選項上。
- **防誤觸**（數值不變：1500／300／250／1000ms）：開啟、換層與置中放大都不是遊戲動作，不受處理中鎖限制；地圖確認等待中不送第二筆。**只有真的開啟選單、真的換層，或 iframe 以同一個 `req` 確認 `focusTown` 成功**才記錄一次執行（之後 250ms 內的下一個執行型按鍵被擋，例如開啟後立刻按 A）；fail closed 的開啟或選定不記錄冷卻。選單在游標下刷新後 300ms 內忽略 A。第一次有效操作（含 SL）只放焦點。

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
node --test scripts/tests/js/controller_core.test.js scripts/tests/js/living_room_core.test.js scripts/tests/js/controller_dual.test.js scripts/tests/js/controller_map_adapter.test.js   # 或透過 pytest 包裝
uv run python -m pytest scripts/tests/test_controller_core_js.py scripts/tests/test_living_room_core_js.py scripts/tests/test_joycon_bridge.py scripts/tests/test_joycon_dual_bridge.py scripts/tests/test_sl_global_focus_browser.py scripts/tests/test_propagandist_joycon_browser.py scripts/tests/test_aid_x_discard_joycon_browser.py scripts/tests/test_thinker_sl_focus_joycon_browser.py scripts/tests/test_hand_over_five_joycon_browser.py
uv run python scripts/validate/validate_joycon_controller.py   # 瀏覽器 E2E（mock bridge；含桌面模式 ZR 縮放循環；SL 情境尚待改寫，見下方），截圖到 /tmp/redline-joycon-proof/
uv run python scripts/validate/validate_living_room_controller.py   # （客廳模式已移除，此 E2E 的客廳情境不再適用，待改寫或移除）客廳模式 E2E（固定按鍵序列、三種解析度，含兩種顯示模式的實機 Capture／購買卡 B→Y／地圖 Y 情境、ZR 縮放循環；SL 情境尚待改寫，見下方），截圖到 /private/tmp/redline-living-room-proof/
```

E2E 以 mock WebSocket 取代 bridge 並注入 frame，驗證真實頁面的焦點、A click、B cancel、modal 優先權、斷線重連不誤觸、stale、地圖目標焦點與 fail-closed。注入的按鍵位元取自下方「限制」的實機證據，但 **mock E2E 本身不是實機證據，也不能取代 Mac 實機 Joy-Con 驗證**（見 `TODO.md`）。
SL 全域地圖聚焦的 regression（不啟動伺服器）：
- `scripts/tests/js/controller_map_adapter.test.js`（node:test，以 vm 載入真實 iframe adapter、真實 `townDisplayLatLng` 與 `data/map.json`，Leaflet 換成可驗證的假地圖）：沒有 pending choice 時 snapshot 仍帶全部 canonical 城鎮；`focusTown` 精確置中（含黑河／海蘭泡／臥龍的依層級偏移）、固定層級 9（maxZoom 10 仍是 9）、不超過 maxZoom；不點按鈕、不觸發 marker click、不改遊戲狀態；未知城鎮、容器隱藏、缺座標、缺 `req`、非 parent 來源、min／max 無法滿足一律 fail closed；pending target 路徑（`focus`／`activate`／`act` 只接受合法目標）不變。
- `scripts/tests/test_sl_global_focus_browser.py`（Playwright／Chromium；以 `page.route` 在合成 origin 提供最小 parent 頁與地圖 iframe，載入真實的 controller 腳本；mock bridge）：桌面模式從指揮中心開啟、兩層選單、置中放大、只看的瀏覽焦點上 A 不作用、合法目標城鎮綁到既有目標焦點且 Y 仍走既有建立流程、新的 pending choice 讓瀏覽焦點交回地圖目標、Leaflet maxZoom 低於 9 時取最大整數層級、iframe `ok:false` fail closed、戰略地圖從未載入時先切過去並在載入後自動開啟。
- `controller_core.test.js`／`living_room_core.test.js`：`focusTown` 必須帶 `req`、`mapFocusZoom` 邊界、`browseTowns` schema 整份 fail closed、地圖目標簽章、真實 `data/map.json` 的完整分組、畫面外的目標座標（思想家全圖候選在 SL 的 zoom 9 與之後 ZR 的 zoom 10）不讓 snapshot 作廢。
- `scripts/tests/test_thinker_sl_focus_joycon_browser.py`（真的 uvicorn＋`ENABLE_TEST_ROUTES=true`，`/test/setup-remove-to-purchase` 維吾爾（伊斯坦堡）＋思想家；mock bridge，SL 選單內也只用搖桿與 A）：桌面模式下，思想家 pending choice → SL → 天方 → 利雅德 → `focusTown` ok:true 與放大後的 snapshot → 放開按鍵後，控制器 scope／焦點／snapshot 目標簽章／A、Y 可用命令與同一 choice 直接用搖桿導航到利雅德完全一致；整條 SL 路徑重複 5 次、遊戲 WebSocket（parent 與 iframe）沒有任何 send、伺服器權威 state 不變；之後 A 選取、Y 建立並進入 3 次遷移。SL（zoom 9）後再按 ZR 放大到 zoom 10（北美目標超過舊的 ±10 萬 px 上限）snapshot 仍被採用，A 選取、Y 建立照常。對照組（不開 SL）同樣可完成；非目標城鎮（伊斯坦堡）只建立瀏覽焦點，A／Y 不選取、不送出。

手牌超過可視張數的 regression：
- `scripts/tests/test_hand_over_five_joycon_browser.py`（真的 uvicorn＋`ENABLE_TEST_ROUTES=true`，8 張手牌、第 7／8 張與第 1／2 張同名；桌面模式；mock bridge）：搖桿從第 1 張逐張到第 8 張再逐張回到第 1 張，每一步焦點卡（DOM 位置、`data-card-index`、控制器 sig）正確且整張在手牌區內，第 7、8 張時手牌區確實捲動；焦點在第 7 張時經過 `render()`／地圖 iframe `redline-map-state` 重繪、重繪後立即輸入、A 預覽（預覽中再重繪）與 B 關閉後仍在第 7 張且捲動位置不變；X／Y 點的是實際焦點卡的既有按鈕（第 7 張 index 6、第 6 張資助者 +2 資金、第 5 張不受影響）。不是實體 Joy-Con 驗證。

必選地圖目標停在其他分頁的 regression：
- `living_room_core.test.js`：`choiceMapRedirect` 只在 page scope／已連線／遊戲顯示／地圖可用時切換；自動切換每個 choice 一次且需控制器使用中；SL、ZR、未對應按鍵不切換。
- `scripts/tests/test_propagandist_joycon_browser.py`（Playwright／Chromium；真的 uvicorn＋`ENABLE_TEST_ROUTES=true`，`/test/setup-remove-to-purchase`＋`/test/set-hand`；mock bridge）：兩種顯示模式打出並移除宣傳家 → 建立組織 → 遷移全程只用控制器（trusted pointer 事件為 0），含手上另一張宣傳家（可排入）、單張、滑鼠離開地圖後控制器輸入回到地圖且不執行、ZR 在其他分頁不作用、`/map-data` 延遲 2 秒、控制器尚未使用時由既有按鈕打出後第一個輸入即恢復。

一般奧援手牌 X＝棄置的 regression：

- `scripts/tests/test_aid_x_discard_joycon_browser.py`（同上 harness）：兩種顯示模式下，一般奧援 X → 危險確認單（預設「返回」）、確認單開著時 X／R 不作用、B 與「返回」上的 A 取消都不送出、右移「確認」＋A 才點一次既有「棄置」；B 在奧援手牌不開確認單；一般牌 X＝資源；紅軍奧援 X＝資源（不開確認單）；「棄置」鈕停用／隱藏時 X fail closed；help／legend／提示列不再出現「B 棄置」。

`validate_joycon_controller.py`／`validate_living_room_controller.py` 的 SL 情境（「組織經驗甲」85 個合法建立目標）仍是舊版「只聚焦合法建立目標、選分組即移焦點」的驗證，尚未改寫成全域導覽（見 `TODO.md`）；它們的 ZR 與其他情境不受影響。

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
  這是 SL 全域地圖聚焦 mapping 的依據；與目前的 `BUTTON_BITS` 一致，SL 沿用 b0 `0x20`，沒有新增或重新指派任何位元。ZR 縮放循環同樣沿用既有的 ZR＝b0 `0x80`。
  2026-10-10 的獨立 bridge WebSocket subscriber 也錄到 Y＝`[1, 0]`、實體 Capture＝`[0, 64]`。2026-10-11 另做的 bounded WebSocket capture
  因 FTCW 當時沒有送出任何 frame 而沒有資料，不影響上述紀錄。
- 尚未以實體 Joy-Con 完整驗證 SL 全域地圖聚焦與 ZR 縮放循環的操作流程（目前只有 mock 測試）。
- **左 Joy-Con 與多支手把沒有實機證據**：左手的封包 offset／位元、左搖桿 offset 與 Y 軸方向、`S2N1` 名稱格式、多支同時輸入、斷線與重連行為都只以 fixture 封包與假 FTCW（臨時 UDP 埠）測試；需實機確認的項目列在 `TODO.md`。
- 文字輸入欄位只能聚焦，無法用搖桿輸入文字。
- CAPTURE 接受 b1 `0x40` 與 b1 `0x20` 兩個位元（同一個邏輯鍵，按住時切換位元不會重複觸發）。上游 `Peterksharma/switch2mac`（commit `a8f2e61e85c3e4a43df3e6ed2f1467327df03d72`）`Switch2Protocol.swift` 定義 `capture = 0x0000_2000`、`c = 0x0000_4000`，UDPHub 以 little-endian u32 寫出。2026-10-10 以獨立 subscriber 實錄本機 bridge（只接右 Joy-Con 2）：Y＝`[1, 0]`、實體 Capture 鍵＝`[0, 64]`（b1 `0x40`，即上游 `c`；右 Joy-Con 2 沒有 `capture` 那顆鍵），因此 `0x40` 是主位元；`0x20` 保留給左 Joy-Con 2／Pro 手把的 `capture`（未實測）。兩個位元原本都沒有其他對應，沒有重新指派任何已知按鍵。字面封包回歸測試：`scripts/tests/test_joycon_bridge.py`、`scripts/tests/js/controller_core.test.js`。


## 開始遊戲前流程的 Joy-Con 配對

初始畫面（`static/start_flow_ui.js`＋純邏輯 `start_flow_core.js`）選 Joy-Con 後：

- 頁面啟用搖桿控制並放開主連線的手把，改為每支「有訊號、沒人使用」的手把各開一條只 claim 自己那一支的 bridge 連線（與客廳輪流大廳監聽相同做法）。
- 只認 **SL + SR 同時按住的按下瞬間**（左 Joy-Con 的實體 SR／SL 已在 bridge 正規化為 SL／SR）；每支手把（或重新連線 epoch 改變）的第一筆 frame 只當 baseline，進來就已按住的組合要先放開再按。
- 依成功順序分配 P1、P2、P3、P4；同一支不重複、滿額後不再收（真人紅軍 4 支；AI 紅軍佔一席，上限 3 支，與伺服器 `/create` 驗證相同）。
- 至少一支配對成功，「完成配對」才可按；完成後關閉配對連線（bridge 釋放），主連線 claim P1，建立作戰室後再沿用客廳輪流為 P2～Pn 新增本機席位並依序綁定。
- 配對畫面期間 Joy-Con 只用來配對；「完成配對」以滑鼠／觸控按下。
