# Redline

Redline 是一個以瀏覽器 UI 與 Python WebSocket 伺服器實作的桌遊原型專案。

**不會玩、想知道畫面上要點哪裡？** 請看配有真實截圖的 [`docs/PLAYER_GUIDE.md`](docs/PLAYER_GUIDE.md)（玩家手冊）。

## 啟動遊戲服務

在專案根目錄執行：

```bash
uv run uvicorn server.main:app --host 0.0.0.0 --port 8000
```

`/test/*` 這類會直接改遊戲狀態的測試端點預設是關閉的（正式環境不應該讓人從外部直接改
遊戲狀態）。如果你要跑 `scripts/validate/validate_*_browser.py` 這類 browser-proof 腳本、或任何
需要打 `/test/*` 的手動驗證，啟動前要另外加上：

```bash
ENABLE_TEST_ROUTES=true uv run uvicorn server.main:app --host 0.0.0.0 --port 8000
```

沒開這個環境變數的話，`/test/*` 會回傳 404，browser-proof 腳本會整批打不到 setup 端點。

服務啟動後：

- 本機瀏覽器：`http://127.0.0.1:8000`
- 同一個 Wi-Fi／區網的其他玩家：`http://<這台電腦的區網 IP>:8000`
- Lobby 會顯示可分享給其他玩家的區網連線網址。

可用以下方式確認服務是否正常：

```bash
curl -fsS http://127.0.0.1:8000/server-info
```

成功時會回傳區網 IP 與 port，例如：

```json
{"lan_ip":"192.168.x.x","port":8000}
```

前景執行時按 `Ctrl+C` 即可停止服務。請保留單一 Uvicorn worker，因為目前房間與遊戲狀態儲存在該 Python process 的記憶體中。

### 用 Docker 啟動

也可以用 `Dockerfile` build 出 image 再跑：

```bash
docker build -t redline .
docker run -d --name redline -p 8000:8000 redline
```

跟直接跑 `uv run` 一樣只保留單一 worker（同一個限制：房間與遊戲狀態存在單一 process
的記憶體中，不能跑多個 replica）。`/server-info`（因此 lobby 顯示的「區網連線網址」）
會依照瀏覽器實際連線時用的 Host 自動判斷正確的網址，不論是直接跑在主機上、Docker
發布 port、還是之後部署到 Render 這類網域後面的 PaaS，都不需要另外設定。

`static/card-art/` 的卡牌美術（約 78MB）已經是 git 追蹤的既有檔案，`docker build`
會照常包進 image；不需要額外處理。

## 資料夾結構

- `server/`
  - 遊戲狀態、規則解析、卡牌效果與 WebSocket/API 伺服器邏輯。
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
