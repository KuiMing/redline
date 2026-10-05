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
| A | 確認／啟用目前焦點（呼叫既有 click handler） |
| B | 返回／取消——只在目前 UI 本身有可見、可用的取消／關閉按鈕時才作用，否則什麼都不做 |
| R / SR | 下一個／上一個主分頁（大廳則為區塊）；modal 與必選地圖目標時停用 |
| X | 把焦點移到回合操作按鈕（只移動焦點，不觸發） |
| Y | 顯示／隱藏操作提示 |
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
- parent → iframe：`redline-controller-command`，`cmd` 為 `snapshot`、`focus {town}`、`clearFocus`、`activate {town}`、`button {id}`、`cancel`。

焦點集合只來自伺服器權威資料，且**每個指令執行當下 iframe 都重新驗證**（parent 的 snapshot 過期或被偽造也不會讓非法目標可 action）：

- pending choice 目標：`supportChoiceHighlight.towns`（伺服器 pending choice 投影），限可見且已知城鎮。
- 移動：目前選取來源的 `legal_organization_moves`（`selectedMoveTargets`），以及可行動的來源城鎮。
- 缺狀態、不是自己的回合、有 pending choice 卻沒有地圖 highlight → 沒有任何目標（fail-closed）。
- 按鈕只限白名單 `directBuildBtn`、`confirmMoveBtn`、`dissolveBtn`、`cancelDissolveChoiceBtn`，且必須存在、可見、未停用。

A 對城鎮走既有 marker `click` 路徑（選取來源／預備移動目的地／選擇 pending choice 候選），對按鈕呼叫既有 `click()`；是否真的移動、建立或瓦解仍由既有確認按鈕與伺服器驗證決定。B 只會：點可見且啟用的「取消瓦解」，或取消目前選取（既有「點地圖其他地方取消」流程）；兩者都沒有就不做事。焦點城鎮以黑底＋黃色雙圈與名稱標籤標示，必要時 `panInside`。

## 測試

```bash
node --test scripts/tests/js/controller_core.test.js          # 或透過 pytest 包裝
uv run python -m pytest scripts/tests/test_controller_core_js.py scripts/tests/test_joycon_bridge.py
uv run python scripts/validate/validate_joycon_controller.py   # 瀏覽器 E2E（mock bridge），截圖到 /tmp/redline-joycon-proof/
```

E2E 以 mock WebSocket 取代 bridge 並注入 frame，驗證真實頁面的焦點、A click、B cancel、modal 優先權、斷線重連不誤觸、stale、地圖目標焦點與 fail-closed。**這不能取代 Mac 實機 Joy-Con 驗證**（見 `TODO.md`）。

## 限制

- https 頁面可能擋 `ws://127.0.0.1`（mixed content），詳見 bridge README；目前只完整支援 http dev／區網頁面。
- S2B1 欄位位置與 `y` 軸方向尚未用實機確認。
- 文字輸入欄位只能聚焦，無法用搖桿輸入文字。
