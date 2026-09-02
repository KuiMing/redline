# `/server-info` 改用請求本身的 Host，取代 UDP 猜測法

## 使用者回報

啟動 Dockerized 版本後，lobby 顯示的「區網連線網址（給其他玩家）」是
`http://172.17.0.2:8000`——Docker 橋接網路裡 container 自己的內部 IP，不是主機在
區網上真正的位址（`http://192.168.10.192:8000`），其他玩家完全連不到。使用者也
指出以後部署到 Render 這類 PaaS 時必定是網域開頭，同一套猜測法完全不適用。

## 根因

`server/main.py` 的 `/server-info` 端點原本用 UDP connect 技巧（不實際發包，只取
路由後的本機位址）自行猜測「本機的區網 IP」。這個技巧問到的是**執行這段程式碼的
那個網路命名空間**的路由結果——直接跑在主機上時剛好等於主機的區網 IP，但在 Docker
容器裡，路由查到的是容器自己的橋接網路 IP，跟主機的區網 IP是兩回事；部署到 Render
這類網域後面時，猜 IP 更是完全沒有意義。

## 修法

改成優先直接採用這次 HTTP 請求本身的 Host（反向代理常見的
`X-Forwarded-Host`／`X-Forwarded-Proto` 優先，其次 `request.headers['host']`）
組出完整網址——這在直接跑主機、Docker 發布 port、或掛在 Render 網域後面都是對的，
因為這就是瀏覽器實際用來連過來的位址。只有 Host 明顯是 loopback
（`127.0.0.1`／`localhost`，例如開發者在主機本地直接開瀏覽器檢查）且沒有反向代理
標頭時，才退回舊的 UDP 探測法（這種情境下 Host header 本身沒有意義，但探測法在
裸機環境還是能正確測到區網 IP）。新增 `base_url` 欄位（完整網址字串，如
`https://redline-abcd.onrender.com`，預設 port 不附加），前端 `loadLanInfo()`
改成優先使用它；舊的 `lan_ip`／`port` 欄位保留相容。

## 驗證

程式化測試四種情境（`curl` 帶自訂 `Host`／`X-Forwarded-*` 標頭）：

| 情境 | 結果 |
|---|---|
| 其他玩家透過主機真正的區網 IP 連線 | `base_url: "http://192.168.10.192:8000"` ✅ |
| 掛在 Render 網域後面（無明講 port） | `base_url: "https://redline-abcd.onrender.com"`（正確不附加 :8000）✅ |
| 反向代理帶明確非預設 port | `base_url: "https://play.example.com:9443"` ✅ |
| 直接用 127.0.0.1 連到容器本身 | 退回容器內部橋接 IP（Docker 網路命名空間的既有限制，非程式碼可解——實際使用情境是透過真正的區網 IP 連線，見上） |

真實瀏覽器（Playwright + Chromium）：對啟動中的 Docker container 用
`http://192.168.10.192:8000/` 開房，lobby 的「區網連線網址」欄位正確顯示
`http://192.168.10.192:8000`（`docker_lan_url_lobby.png`）。

`scripts/validate/validate_lan_info_display.py`（既有裸機情境的驗證腳本，未改動、行為不變）
與完整 pytest 366/366 皆通過。
