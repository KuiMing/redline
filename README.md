# Redline

Redline 是一個以瀏覽器 UI 與 Python WebSocket 伺服器實作的桌遊原型專案。

**不會玩、想知道畫面上要點哪裡？** 請看配有真實截圖的 [`docs/PLAYER_GUIDE.md`](docs/PLAYER_GUIDE.md)（玩家手冊）。

**想讓 LLM 透過 MCP 直接玩這個遊戲？** 請看 [`docs/mcp_server.md`](docs/mcp_server.md)。

**想讓 Agent 不需人工提醒，自動擔任紅軍？** 請看 [`docs/red_army_controller.md`](docs/red_army_controller.md)。

**想用 Claude Code、OpenAI Codex 或其他 Agent 串接 MCP，並接上控制器？** 請看 [`docs/agent_mcp_controller_integration.md`](docs/agent_mcp_controller_integration.md)。

## 啟動遊戲服務

三種方式，依方便程度排列。

### 方式一：Docker Compose（推薦，一次把遊戲跟 MCP 都開好）

```bash
export REDLINE_HOST_PORT=8100
docker compose up --build -d
```

- 遊戲 UI：`http://localhost:8100`
- MCP（給 Agent 用，見下一節）：`http://127.0.0.1:8765/mcp`

就算不需要 Agent，這個做法也沒有壞處——MCP 那個容器預設只綁本機、平常閒置不會影響什麼。
細節見 [`docs/mcp_server.md`](docs/mcp_server.md#4-docker--docker-compose)。

### 方式二：只用 Docker（只要遊戲本體）

```bash
docker build -t redline .
docker run -d --name redline -p 8000:8000 redline
```

`http://localhost:8000`。想讓 Agent 陪玩的話，另外開 MCP（見下方「給 Agent 用的 MCP」）。

### 方式三：直接用 uv 跑（不需要 Docker）

```bash
uv run uvicorn server.main:app --host 0.0.0.0 --port 8000
```

`http://127.0.0.1:8000`；同一區網的其他人可以用 `http://<這台電腦的區網 IP>:8000` 加入，
Lobby 畫面也會顯示這個網址。想讓 Agent 陪玩的話，另外開 MCP（見下方「給 Agent 用的 MCP」）。

以上三種都只能跑單一 worker／單一 container（房間與遊戲狀態存在該 process 的記憶體
中，重開就會消失）。跑 `scripts/validate/validate_*_browser.py` 這類需要 `/test/*` 端點的
驗證腳本時，方式三要另外加 `ENABLE_TEST_ROUTES=true`（不開的話 `/test/*` 一律回傳 404）。

### 給 Agent 用的 MCP

方式一（Docker Compose）已經內建 MCP，開在 `http://127.0.0.1:8765/mcp`，不用另外做什麼。

方式二、三（只有遊戲本體）想讓 Agent 陪玩，另外開：

```bash
uv run python -m mcp_server --transport streamable-http
```

MCP 會開在 `http://127.0.0.1:8080/mcp`。

## 讓 Agent 陪你玩（以紅軍為例）

不限定用哪個 Agent，步驟都一樣：

1. 把你的 Agent 接上 MCP：`http://127.0.0.1:8765/mcp`（或你上面選的其他 port）。怎麼接依
   你用的 Agent 而定——大多數 MCP client 只要給這個網址就好；Claude Code、Codex 的具體做法
   見 [`docs/agent_mcp_controller_integration.md`](docs/agent_mcp_controller_integration.md)。
2. 跟 Agent 說：「讀 `skills/play-redline/SKILL.md` 照做，幫我開一局 REDLINE，你當紅軍」。
   它會給你一個房號，打開遊戲網址、用房號加入、選陣營、按準備，再跟 Agent 說「開始吧」。
   之後每一回合它會自動接手，不用你提醒。

## 資料夾結構

- `server/`
  - 遊戲狀態、規則解析、卡牌效果與 WebSocket/API 伺服器邏輯。
- `mcp_server/`
  - REDLINE MCP server（stdio 或 Streamable HTTP），讓 MCP 相容的 LLM client 透過既有 HTTP/WebSocket API 玩遊戲。見 [`docs/mcp_server.md`](docs/mcp_server.md)。
- `red_army_controller/`
  - 主機端的全自動紅軍控制器；等待真人時不呼叫模型，只在紅軍需要決策時啟動專用 Hermes Agent。
- `static/`
  - 前端 HTML/CSS/JavaScript、地圖 UI、遊戲主畫面與瀏覽器端互動。
- `data/`
  - 遊戲資料檔，例如卡牌、城鎮、陣營與地圖資料。
- `scripts/`
  - 資料產生腳本與其他專案工具。
  - `scripts/validate/`：Browser proof、規則驗證與其他可重跑驗證腳本。
  - `scripts/debug/`：臨時截圖、連線檢查、除錯輔助腳本。
  - `scripts/tests/`：手動 WebSocket / lobby / Playwright 測試腳本。
- `docs/`
  - 設計文件、提交範圍、驗證紀錄與截圖證據。
- `docs/records/`
  - 任務導向的驗證紀錄與 battle-shot / screenshot 證據。新紀錄建議放在這裡，不要再散落到 repo 根目錄。
  - 目前已依主題整理，例如 `leak-card/`、`purchase/`、`layout-ui/`、`faction-ui/`、`safehouse/`、`lobby/`、`map-ui/`。
- `sketches/`
  - UI 草圖或一次性設計探索；正式實作前應整理成 `static/` 或 `docs/`。

## 給接手工程師／Agent 的資料

`docs/records/` 驗證紀錄怎麼找、怎麼讀、新紀錄該放哪裡，請看
[`docs/records/README.md`](docs/records/README.md)；一般玩家或部署者不需要看這份文件。

## 授權與原作聲明

- 本專案自行開發的程式碼採用 MIT License。完整條款請參閱 [`LICENSE-CODE`](LICENSE-CODE)。
- 本專案使用或改編自桌上遊戲《逆統戰：致地與海的革命者》的規則、文字、角色、圖像及其他《逆統戰》原作內容。相關原作內容的權利屬 ESC Taiwan／原著作權人所有，不適用 MIT License。
- 依原權利人向本專案提供的書面說明及[官方二次創作政策](https://reversedfront.tw/download/)，原作相關內容僅限非商用且必須註明出處；商業使用須另行取得原著作權人同意。
- 本專案是獨立製作的非官方二次創作，並非 ESC Taiwan 官方開發、發行、贊助或認可的作品。

完整的授權範圍與權利聲明請參閱 [`LICENSE.md`](LICENSE.md)。
