# Redline

Redline 是一個以瀏覽器 UI 與 Python WebSocket 伺服器實作的不對稱政治策略桌遊。專案支援鍵盤、滑鼠、Joy-Con，以及透過 MCP 接入的 LLM 玩家。

**不會玩、想知道畫面上要點哪裡？** 請看配有真實截圖的 [`docs/PLAYER_GUIDE.md`](docs/PLAYER_GUIDE.md)（玩家手冊）。

**想讓 LLM 透過 MCP 直接玩這個遊戲？** 請看 [`docs/mcp_server.md`](docs/mcp_server.md)。

**想讓 Agent 不需人工提醒，自動擔任紅軍？** 請看 [`docs/red_army_controller.md`](docs/red_army_controller.md)。

**想用 Claude Code、OpenAI Codex 或其他 Agent 串接 MCP，並接上控制器？** 請看 [`docs/agent_mcp_controller_integration.md`](docs/agent_mcp_controller_integration.md)。

## 啟動遊戲服務

以下三種方式，依方便程度排列。Apple Silicon Mac 也可以試用[不需安裝任何工具的測試版 App](#macos-測試版-appdmg未簽署)。

### 方式一：Docker Compose（推薦，一次啟動遊戲、MCP 與 Joy-Con Bridge）

```bash
docker compose up --build -d
```

- 遊戲 UI：`http://localhost:8100`
- MCP（給 Agent 用，見下一節）：`http://127.0.0.1:8765/mcp`
- Joy-Con Bridge：`ws://127.0.0.1:8000/ws`（macOS 需先開 FTCW，見 [`docs/joycon_controller.md`](docs/joycon_controller.md#用-docker-compose-啟動-bridge-macos)）
- 遊戲 host port 預設 8100（8000 留給 Bridge）；用 `REDLINE_HOST_PORT` 修改。

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

### Joy-Con／搖桿（選用）

在 macOS 上使用 Joy-Con 時，藍牙連線與 FTCW 必須在 host 執行。Docker Compose 會啟動 Joy-Con Bridge container；Bridge 透過 `host.docker.internal` 接收 FTCW UDP 資料，並預設只在 `127.0.0.1:8000` 發布 WebSocket。

每位玩家可各使用一支左或右 Joy-Con。建立遊戲時選擇 **Joy-Con**，畫面會顯示電腦連線說明；依序以 `SL + SR` 配對後，配對順序會決定 P1、P2、P3、P4。遊戲內仍可從頁面右下角 🎮 查看或調整控制器。

遊戲內導覽列的 **遊戲選單** 按鈕（滑鼠點擊，或 Joy-Con 以 R／SR 聚焦後按 A；也可長按搖桿按鈕 2 秒）可開啟選單，其中 `Joy-Con 功能表` 顯示目前操作提示，`配樂音量` 以 −／＋ 調整遊戲配樂（範圍 0%～100%，預設 30%，每次 10%，會記在瀏覽器）。配樂從開始畫面延續到大廳與遊戲畫面，且需先有一次點擊、按鍵或觸控操作（瀏覽器 autoplay 限制）。

遊戲結束後，按 Joy-Con **Y** 或鍵盤 **Y** 可重新查看最後勝利圖片。此操作只重新顯示圖片，不會再次執行結算、獎勵或音效。

完整設定、控制方式與故障排除請參閱 [`docs/joycon_controller.md`](docs/joycon_controller.md) 與 [`tools/joycon_bridge/README.md`](tools/joycon_bridge/README.md)。

### macOS 測試版 App（DMG，未簽署）

`REDLINE.app` 內含遊戲伺服器、所有遊戲資源與 Joy-Con Bridge，雙擊就能玩，不需要安裝 Python、uv 或 Docker。

> [!WARNING]
> 這是**未簽署、未經 Apple 公證**的測試版（只有 arm64 核心要求的 ad-hoc 簽章），僅支援 Apple Silicon。macOS 無法驗證來源，請只使用你信任的人建置的版本。

**下載**：到 GitHub Actions 的 [macOS DMG workflow](../../actions/workflows/macos-dmg.yml)，開啟一次成功的執行，下載名為 `REDLINE-<version>-macOS-arm64-run<run id>.<attempt>-<commit>` 的 artifact 並解壓縮（需登入 GitHub，保留 14 天；目前不發布 GitHub Release）。名稱中的 run id、attempt 與 commit 可對應到實際的建置。可用同目錄的 `.sha256` 以 `shasum -a 256 -c` 檢查。維護者可用 **Run workflow** 手動觸發建置。

**第一次開啟（Gatekeeper）**：

1. 打開 DMG，把 `REDLINE.app` 拖到 Applications，再雙擊開啟。
2. macOS 顯示無法驗證時按「完成」，不要移到垃圾桶。
3. 到「系統設定」>「隱私權與安全性」，往下找到 REDLINE，按「強制打開」並確認。之後就能直接開啟。

**Joy-Con**：App 已內含 Bridge，但藍牙連線仍需另外安裝並先開啟 **Finally the Controller Works（FTCW）**，App 不會內附它；不用 Joy-Con 就不需要安裝。如果 `127.0.0.1:8000` 已經有 Joy-Con Bridge（例如 Docker Compose 啟動的），App 會直接沿用它，關閉時也不會停止它；如果 8000 被其他程式佔用，App 會改用其他埠並自動更新頁面設定。

**行為與限制**：

- 只綁 `127.0.0.1`，同一區網的其他裝置連不進來，因此 Lobby 顯示的區網網址在這個模式下無法使用。需要區網連線時，請從終端機以 `REDLINE_APP_BIND_HOST=0.0.0.0 /Applications/REDLINE.app/Contents/MacOS/REDLINE` 啟動（遊戲伺服器沒有存取驗證，請只在信任的網路使用）。
- 遊戲伺服器拒絕不是 `127.0.0.1:<實際埠>`／`localhost:<實際埠>` 的 `Host`，也拒絕其他網站的 `Origin`（HTTP 與 WebSocket 都是），防止你瀏覽的網頁連進本機遊戲；沒有 `Origin` 的本機工具不受影響。這個防護只在 App 中啟用，Docker 與 `uv run` 的行為不變。開放區網時 `Host` 只接受實際埠上的 IP 位址（IPv4、加方括號的 IPv6）或 loopback 名稱，不接受網域名稱，`Origin` 仍須同源。
- 遊戲優先使用 18100–18109 埠，都被佔用時改用系統分配的埠。同時只能開一個 REDLINE；再開一次會切換到已開啟的視窗。
- 瀏覽器儲存（localStorage）綁連接埠。換埠時，只有配樂音量、Joy-Con 控制器設定與顯示模式會由 `~/Library/Application Support/REDLINE/settings.json` 帶過去，**不是全部的 localStorage**；關閉 App 前約 2 秒內的變更可能來不及存。重連憑證、席位與裝置 id 刻意不搬移也不寫入該檔，因為房間在關閉 App 時就消失了。
- 房間與對局狀態存在記憶體中，關閉 App 就會消失。
- 戰略地圖的 Leaflet、底圖與部分字型從網路載入，離線時地圖可能無法完整顯示。
- 無法啟動時會顯示錯誤視窗；診斷記錄在 `~/Library/Logs/REDLINE/`（`launcher.log`、`server.log`、`bridge.log`）。
- `/test/*` 端點在 App 中一律關閉，即使設定了 `ENABLE_TEST_ROUTES` 也一樣。

**自行建置**（需要 Apple Silicon macOS、Xcode Command Line Tools 與 [uv](https://docs.astral.sh/uv/)）：

```bash
packaging/macos/build.sh
build/macos/venv/bin/python packaging/macos/smoke_test.py --dmg dist/REDLINE-*-macOS-arm64.dmg --gui
```

輸出 `dist/REDLINE.app` 與 `dist/REDLINE-<version>-macOS-arm64.dmg`。`build.sh` 要求 uv 0.11.8 與 uv 管理的 CPython 3.11.15，版本不符會直接失敗。打包相依（PyInstaller、pywebview）在 `pyproject.toml` 的 `macos-app` 群組，Docker 與一般 `uv run` 都不會安裝。

`smoke_test.py` 需要 18100 與 18870 埠空著，也不能有其他 REDLINE 正在執行，否則直接失敗。`--gui` 會短暫開啟真實視窗，並用 `open -n` 啟動 App 複本再以 application quit 結束，全部自動關閉；測試資料放在暫存目錄，不會留在你的家目錄。

App 與 DMG 都附有 `THIRD-PARTY-NOTICES.txt`（由 `packaging/macos/generate_third_party_notices.py` 產生）。相依變更時 `build.sh` 會因內容不一致而失敗；審閱新授權後，更新腳本內的 `REVIEWED` 清單，再以 `--write` 重新產生。

## 開始遊戲

1. 在「開始遊戲」選擇真人紅軍、AI 紅軍，或使用房間代碼加入現有遊戲。
2. 建立遊戲時選擇遊戲模式：
   - 簡單模式：`53 張精簡牌組`，由 `18 張奧援卡與 35 張隨機一般卡` 組成。
   - 一般模式：`245 張完整牌組`。
3. 選擇「電腦」或「Joy-Con」。選擇 Joy-Con 時，先依畫面說明完成電腦連線與玩家配對。
4. 完成玩家與陣營設定後開始遊戲。

遊戲介面固定使用 `1280 × 720` 舞台並等比例縮放。非 16:9 顯示區域會保留黑邊，不會裁切或拉伸畫面。

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
- `tools/`
  - `tools/joycon_bridge/`：本機 Joy-Con WebSocket bridge。
  - `tools/macos_app/`：macOS App 的 launcher（子行程管理、視窗、smoke 模式）。
- `packaging/macos/`
  - macOS App／DMG 的 PyInstaller 設定、建置腳本與 smoke 測試。
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
