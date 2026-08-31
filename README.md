# Redline

Redline 是一個以瀏覽器 UI 與 Python WebSocket 伺服器實作的桌遊原型專案。

**不會玩、想知道畫面上要點哪裡？** 請看配有真實截圖的 [`docs/PLAYER_GUIDE.md`](docs/PLAYER_GUIDE.md)（玩家手冊）。

## 啟動遊戲服務

在專案根目錄執行：

```bash
cd "$HOME/.openclaw/workspace/redline"
uv run uvicorn server.main:app --host 0.0.0.0 --port 8000
```

`/test/*` 這類會直接改遊戲狀態的測試端點預設是關閉的（正式環境不應該讓人從外部直接改
遊戲狀態）。如果你要跑 `scripts/validate_*_browser.py` 這類 browser-proof 腳本、或任何
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
cd "$HOME/.openclaw/workspace/redline"
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
  - 驗證腳本、資料產生腳本與一次性檢查工具。
  - `scripts/debug/`：臨時截圖、連線檢查、除錯輔助腳本。
  - `scripts/tests/`：手動 WebSocket / lobby / Playwright 測試腳本。
- `docs/`
  - 設計文件、提交範圍、驗證紀錄與截圖證據。
- `docs/records/`
  - 任務導向的驗證紀錄與 battle-shot / screenshot 證據。新紀錄建議放在這裡，不要再散落到 repo 根目錄。
  - 目前已依主題整理，例如 `leak-card/`、`purchase/`、`layout-ui/`、`faction-ui/`、`safehouse/`、`lobby/`、`map-ui/`。
- `sketches/`
  - UI 草圖或一次性設計探索；正式實作前應整理成 `static/` 或 `docs/`。

## 接手前先看哪裡

如果你是下一個接手的人，先讀這幾個地方：

1. `README.md`
   - 看專案結構、紀錄檔規則、目前紀錄放哪裡。
2. `docs/records/<topic>/`
   - 看你現在要接的任務主題，例如 `purchase/`、`safehouse/`、`shared-actions/`、`support-cards/`、`leak-card/`。
3. 對應驗證腳本 `scripts/validate_*.py`
   - 確認該 topic 的紀錄是不是由腳本直接產出，避免人工搬運造成路徑漂移。

## 怎麼看目前做到哪

優先看「最新狀態 / 驗證摘要」類文件：

- `docs/records/purchase/PURCHASE_ALIGNMENT_STATUS_2026_05_10.md`
- `docs/records/leak-card/LEAK_CARD_COMMIT_SCOPE.md`
- `docs/records/shared-actions/HU_SHARED_AND_WIN_VALIDATION.md`
- `docs/records/shared-actions/NEGOTIATION_CARD_VALIDATION.md`
- `docs/records/shared-actions/SHARED_VICTORY_PHASE8_VALIDATION.md`
- `docs/records/shared-actions/VICTORY_RULES_VALIDATION.md`
- `docs/records/card-ui/CARD_UI_VALIDATION_RESULTS.md`
- 各 topic 下面最新的 `*_VALIDATION.md`
- 各 topic 下面的 `*_COMMIT_SCOPE.md`

判讀原則：

- `*_STATUS_*.md`：看目前修到哪、怎麼驗、結論是什麼。
- `*_VALIDATION.md`：看人工可讀摘要。
- `*_VALIDATION.json`：看機器可讀細節與量測值。
- `*_COMMIT_SCOPE.md`：看某次整理 / commit 想包含哪些檔。

## 如果要看更久之前的東西

請照這個順序追：

1. 先看對應 `docs/records/<topic>/`
   - 確認主題資料夾與最新驗證紀錄。
2. 再看該 topic 內的檔案
   - 優先看 `*_STATUS_*.md`、`*_COMMIT_SCOPE.md`、`*_VALIDATION.md`。
3. 如果要追輸出來源或重跑方式，再看對應 `scripts/validate_*.py`
4. 如果還不夠，再看 git 歷史
   - `git log -- docs/records/<topic>/`
   - `git log -- README.md`
   - `git show <commit>`

## 已整理的 records 主題

目前 `docs/records/` 已依主題整理，常見 topic 包含：

- `leak-card/`：走漏風聲規則與 UI 指定目標驗證。
- `purchase/`：購買區、購買牌堆補牌、地下黨、常設 supply / remove-return 驗證。
- `layout-ui/`：手牌、底部黑區、主分頁與 HUD layout 驗證。
- `card-ui/`：卡牌呈現、卡片 HUD、行動卡流程驗證與 card UI battle-shot。
- `support-cards/`：奧援牌與區域支援牌 UI / runtime 驗證。
- `faction-ui/`：陣營選擇、臺灣/香港/蒙古/新疆/西藏等陣營 UI 截圖。
- `rebel/`：反抗者擴充、重建狀態與相關 UI 截圖。
- `shared-actions/`：共享組織、共享拆除、合作談判、共享勝利與勝利條件驗證。
- `safehouse/`：安全屋地圖 highlight / zoom / build range 驗證截圖。
- `lobby/`：多人 lobby、ready sync 與房間 UI 截圖。
- `map-ui/`：Leaflet / strategic map UI 截圖。
- `setup-ui/`：初始基地選擇與 setup 規則 UI 截圖。
- `design/`：設計規格與參考資料。
- `debug-screenshots/`：重跑、console、除錯用畫面證據。
- `misc/`：尚未能明確歸類但需要保留的紀錄。

## 記錄檔整理規則

驗證與截圖檔案請優先放進 `docs/records/<topic>/`：

- 驗證報告：`docs/records/<topic>/*_VALIDATION.md`
- 機器可讀結果：`docs/records/<topic>/*_VALIDATION.json`
- 視覺證據截圖：`docs/records/<topic>/*.png`
- 提交/整理說明：`docs/records/<topic>/*_COMMIT_SCOPE.md`
- 狀態摘要：`docs/records/<topic>/*_STATUS_*.md`

臨時執行輸出不應提交：

- `server.log`
- `__pycache__/`
- Playwright 或手動除錯的中間截圖
- 沒有對應任務說明的 preview / battle-shot 圖片

## 近期已整理進 docs/records 的主題

- `docs/records/leak-card/`
- `docs/records/purchase/`
- `docs/records/safehouse/`
- `docs/records/setup-ui/`
- `docs/records/shared-actions/`
- `docs/records/support-cards/`

例如這批與購買區 / remove-return 相關的驗證，現在由下列腳本直接輸出到 `docs/records/purchase/`：

- `scripts/validate_market_mode_and_removed_supply.py`
- `scripts/validate_purchase_section_alignment.py`
- `scripts/validate_underground_party.py`

共享勝利 / 合作談判 / 勝利條件相關驗證，現在直接輸出到 `docs/records/shared-actions/`：

- `scripts/validate_negotiation_card.py`
- `scripts/validate_hu_shared_and_win.py`
- `scripts/validate_shared_victory_phase8.py`
- `scripts/validate_victory_rules.py`

完整遊戲流程與 era 規則驗證，現在直接輸出到 `docs/records/misc/`：

- `scripts/validate_full_gameplay_2p.py`
- `scripts/validate_full_gameplay_multi.py`
- `scripts/validate_era_rules.py`

卡牌 UI / 類型流程驗證，現在直接輸出到 `docs/records/card-ui/`：

- `scripts/validate_ui_card_flows.py`

重跑驗證時，對應腳本應優先把輸出直接寫進各自的 `docs/records/<topic>/`；repo 根目錄目前不應再承接這些 validation report。

## 授權與原作聲明

- 本專案自行開發的程式碼採用 MIT License。完整條款請參閱 [`LICENSE-CODE`](LICENSE-CODE)。
- 本專案使用或改編自桌上遊戲《逆統戰：致地與海的革命者》的規則、文字、角色、圖像及其他《逆統戰》原作內容。相關原作內容的權利屬 ESC Taiwan／原著作權人所有，不適用 MIT License。
- 依原權利人向本專案提供的書面說明及[官方二次創作政策](https://reversedfront.tw/download/)，原作相關內容僅限非商用且必須註明出處；商業使用須另行取得原著作權人同意。
- 本專案是獨立製作的非官方二次創作，並非 ESC Taiwan 官方開發、發行、贊助或認可的作品。

完整的授權範圍與權利聲明請參閱 [`LICENSE.md`](LICENSE.md)。
