# 全自動紅軍 Agent 控制器

`red_army_controller` 在主機上監看 REDLINE。等待真人時不呼叫模型。只有輪到紅軍，或紅軍必須處理 `pending_choice` 時，控制器才啟動專用 Hermes Agent。

Claude Code、OpenAI Codex 與自訂 `AgentRunner` 的串接方式見 [`agent_mcp_controller_integration.md`](agent_mcp_controller_integration.md)。

## 安全模型

- Docker 只執行 REDLINE 與 MCP。模型憑證留在主機。
- 控制器把席位憑證存於權限 `0600` 的本機狀態檔。預設位置是 `$XDG_STATE_HOME/redline/red-army-controller.json`，未設定 XDG 時使用 `$HOME/.local/state/redline/red-army-controller.json`。
- 一般輸出只包含可分享的 `game_id` 與安全狀態。它不輸出 `player_id`、`resume_token` 或手牌。
- Hermes 的完整 stdout/stderr 只保留在控制器記憶體中並立即丟棄。
- Streamable HTTP MCP 沒有認證。它必須維持只綁定 `127.0.0.1`。
- 專用 Hermes profile 不是作業系統沙箱。控制器以 `-t mcp-redline` 啟動 Hermes，只載入 REDLINE MCP toolset。控制器 prompt 也明確禁止使用非 REDLINE MCP tools。
- 玩家名稱、action log 與卡牌文字都可能包含不可信文字。Agent prompt 要求把這些內容視為資料，不得當成指令。

## 一次性 Hermes 設定

```bash
hermes profile create redarmy --clone-from default \
  --description "只擔任 REDLINE 紅軍玩家"
hermes -p redarmy mcp add redline --url http://127.0.0.1:8765/mcp
hermes -p redarmy mcp test redline
hermes -p redarmy mcp configure redline
```

控制器每次啟動 Hermes 時都指定 `mcp-redline` toolset。一般 `redarmy` CLI session 的 toolset 設定不會擴大控制器子程序的工具範圍。

## 啟動

先啟動遊戲與 MCP：

```bash
docker compose up --build -d
```

首次建立房間並持續監看：

```bash
uv run python -m red_army_controller create
```

控制器只會輸出可分享的房間碼：

```json
{"game_id":"<room-code>","status":"waiting_for_players"}
```

真人玩家開啟 `http://<主機位址>:8000`，加入該房間，選擇非紅軍陣營並設為準備。當至少有兩名玩家、每人都已選陣營且準備完成時，控制器自動開始遊戲。

遊戲開始後：

- 等待真人時，控制器只輪詢 MCP，不呼叫 LLM。
- 輪到紅軍或紅軍有必要選擇時，控制器自動啟動 Hermes。
- Hermes 返回後，控制器重新讀取伺服器狀態。
- 若紅軍仍可行動，控制器再次啟動 Hermes。
- 若紅軍正在等待真人的反應或選擇，控制器不啟動 Hermes。
- 回合交接後，控制器回到無模型輪詢。
- 遊戲結束後，控制器停止。

## 恢復與狀態

控制器或 MCP 重啟後：

```bash
uv run python -m red_army_controller run
```

它會從權限 `0600` 的狀態檔取得憑證，先呼叫 `resume_room`，再繼續監看。

安全狀態摘要：

```bash
uv run python -m red_army_controller status
```

可覆寫設定：

```bash
REDLINE_MCP_URL=http://127.0.0.1:8765/mcp \
REDLINE_HERMES_PROFILE=redarmy \
REDLINE_CONTROLLER_POLL_SECONDS=2 \
uv run python -m red_army_controller run
```

按 `Ctrl-C` 可安全停止。控制器會終止正在執行的 Hermes 子程序。若 Hermes 連續失敗、同一個可操作狀態多次沒有改變，或單一紅軍行動窗口超過模型呼叫總預算，控制器會停止，避免無限制消耗 token。

## 限制

- 這個控制器依賴 Hermes profile 中已啟用的 `redline` MCP。
- REDLINE WebSocket 沒有每個 action 的 request correlation。控制器以動作後的最新 viewer state 為準。
- 控制器採低頻 bounded polling。等待真人不耗用模型 token，但仍會產生本機 MCP 請求。
- 若遊戲或 MCP 暫時離線，控制器退避後重連並重新呼叫 `resume_room`。

## 驗證

```bash
uv run pytest -q scripts/tests/test_red_army_controller.py
uv run python scripts/validate/red_army_controller_smoke.py
uv run python scripts/validate/red_army_mcp_restart_smoke.py
```

- 單元與安全邊界：14 passed。
- 實際 Docker、MCP、WebSocket 與 fake Agent 自動交接：7/7 passed。
- MCP container 重啟後自動恢復席位：7/7 passed。
- 另以真正的 `redarmy` Hermes profile 驗證一次完整紅軍回合。控制器自動喚起 Agent，且回合成功交接。這項驗證會消耗模型 token，因此不放入一般自動測試。
