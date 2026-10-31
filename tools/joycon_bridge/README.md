# REDLINE Joy-Con bridge

在 Mac 上用 Joy-Con 2（每位玩家各拿一支左或右 Joy-Con）玩 REDLINE 的**本機**輸入橋接：

```
Joy-Con ×N ─▶ Finally the Controller Works ─UDP 127.0.0.1:24800–24803（每埠一支；S2N1 名稱＋S2B1 輸入）─▶ 本 bridge ─WebSocket─▶ 各玩家的瀏覽器
```

每支手把有獨立身份（左右＋FTCW 埠＋名稱指紋，例如 `L24801-3f2a9c1e`）、狀態與擁有者；左 Joy-Con 的按鍵在 bridge 正規化成右 Joy-Con 的邏輯位元。
每個瀏覽器分頁在 🎮 設定面板選一支（claim）；只有恰好一支右 Joy-Con 時沿用舊版的自動綁定。規則與協定見 `docs/joycon_controller.md`「多支獨立 Joy-Con」。

瀏覽器端行為（焦點、按鍵對應、modal 優先權、地圖）見 [`docs/joycon_controller.md`](../../docs/joycon_controller.md)。

## 啟動

1. 保持 **Finally the Controller Works** 開啟並已連上 Joy-Con。
2. 在 repo 根目錄：

   ```bash
   tools/joycon_bridge/run_mac.sh            # 等同 uv run python -m tools.joycon_bridge
   tools/joycon_bridge/run_mac.sh --port 8123
   ```

   不需要全域 `pip`；依賴（fastapi、uvicorn）已在根目錄 `pyproject.toml`，`uv` 會處理。
3. 開 REDLINE 頁面 → 右下角 🎮 → 勾選「啟用搖桿控制」。預設連 `ws://127.0.0.1:8000/ws`。

## 選項

| 選項 | 說明 |
| --- | --- |
| `--port N` | WebSocket/HTTP 連接埠，預設 8000。頁面端的 Bridge 位址要同步修改。 |
| `--bind-host HOST` | WebSocket/HTTP 綁定位址，預設 `127.0.0.1`。Docker 容器內用 `0.0.0.0`（host port 仍只發布到 127.0.0.1）。 |
| `--udp-host HOST` | FTCW 所在主機，預設 `127.0.0.1`。Docker 內用 `host.docker.internal`。 |
| `--udp-port N` | Finally the Controller Works 的第一個 UDP 連接埠，預設 24800；也是舊版「單一右 Joy-Con」預設身份（`R24800-legacy`）所在的埠。 |
| `--udp-port-count K` | 從 `--udp-port` 起連續探測 K 個 FTCW 埠（每埠一支手把），1–8，預設 4（24800–24803）。 |
| `--allow-origin ORIGIN` | 額外允許的網頁 Origin，可重複；也可用環境變數 `REDLINE_JOYCON_ALLOW_ORIGINS`（逗號分隔）。 |
| `--dump-packets` | 印出收到的原始 UDP 封包 hex（前綴 `[udp <埠>]`），用來校正欄位位置。 |
| `--buttons-offset N` / `--stick-offset N` / `--left-stick-offset N` | 覆寫 S2B1 封包欄位位置（u32 buttons、右搖桿、左搖桿）。 |

`/health`（只接受 loopback Host）回傳封包計數、最後封包距今秒數與每支手把的身份／左右／狀態（除錯用）。

## 安全

- **預設只綁 `127.0.0.1`**（`--bind-host` 可覆寫，僅供 Docker 容器內使用；見 `docs/joycon_controller.md`「用 Docker Compose 啟動 Bridge」）。
- WebSocket 會檢查 `Host`（必須是 `127.0.0.1`／`localhost`／`[::1]`，防 DNS rebinding）與 `Origin`。
- **頁面從區網載入時**（例如 `http://192.168.x.x:8100`）瀏覽器的 Origin 是那個區網位址，預設會被拒絕。
  要明確放行：

  ```bash
  tools/joycon_bridge/run_mac.sh --allow-origin http://192.168.1.20:8100
  ```

  頁面端永遠連玩家自己 Mac 的 `ws://127.0.0.1`（不是遠端主機）。
- 封包內容會驗證：magic、長度、NaN/Inf、搖桿範圍（超出 ±1.01 整筆丟棄）。
- UDP 執行緒與 WebSocket 共用狀態都在同一把 lock 內存取；UDP 來源停止超過 1 秒就不再送 frame，瀏覽器端據此判定 stale。

## WebSocket 訊息格式

新版頁面連上 `/ws` 後送 `{"type":"hello","v":2}`，之後收 `roster`、`claim-result` 與只屬於自己那一支的
`{"type":"frame","v":2,"controller":"L24801-…","side":"left","epoch":1,"x":…,"y":…,"buttons":[b0,b1]}`（v2 協定見 `docs/joycon_controller.md`）。
舊版頁面（不送 hello）照舊約 30Hz 收到唯一一支右 Joy-Con 的：

```json
{"x": 0.0, "y": 0.0, "buttons": [b0, b1]}
```

兩種格式的 `x`／`y`／`buttons` 都是**共用邏輯 layout**（左 Joy-Con 已在 bridge 轉成右 Joy-Con 的等價鍵與搖桿）：

- `x`、`y`：該手把的搖桿（右手 rx/ry、左手 lx/ly），−1..1，每軸 deadzone 0.15，**y 向下為正**（畫面座標）。Bridge 會將 FTCW 的「向上為正」Y 軸取負，轉成畫面座標。
- `buttons`：共用邏輯 layout 的兩個 byte（＝右 Joy-Con 的 u32 buttons 低兩個 byte；右手原樣對應，左手由 bridge 轉成等價鍵，未知位元丟棄）。b0：`0x08 A`、`0x04 B`、`0x02 X`、`0x01 Y`、`0x20 SL`、`0x10 SR`、`0x40 R`、`0x80 ZR`；b1：`0x02 +`、`0x04 STICK`、`0x10 HOME`、`0x40 CAPTURE`。只接右 Joy-Con 2 時，實體 Capture 鍵送出的是 `c = 0x0000_4000`（b1 `0x40`，2026-10-10 實錄 `[0, 64]`）；左 Joy-Con 2 的 Capture 與上游 `capture = 0x0000_2000` 一律送成 b1 `0x40`（瀏覽器端仍接受舊版 bridge 送的 b1 `0x20`）。使用者提供的實體 BUTTON AREA 紀錄已確認右 Joy-Con 2 的 A／B／X／Y／SL／SR／R／ZR／`+`／STICK／HOME／Capture 位元與上表一致（例如 SL＝`20 00`，瀏覽器端用於 SL 聚焦選單；ZR＝`80 00`，瀏覽器端用於戰略地圖縮放循環；詳見 `docs/joycon_controller.md`「限制」）。

## 已知限制（務必閱讀）

- **S2B1 預設使用 Finally the Controller Works v0.2.0 的 44-byte 格式。** 按鍵位於 u32 buttons（右手 offset 8、9；左手 offset 9、10）；右手用右搖桿 rx、ry（offset 20、24），左手用左搖桿 lx、ly（offset 12、16）。左手欄位尚未實機確認（見 `TODO.md`）。
  如未來版本變更 wire format，可加 `--dump-packets` 對照封包，並用 `--buttons-offset`／`--stick-offset` 暫時覆寫。
- **https 頁面可能擋 `ws://127.0.0.1`（mixed content）。** 是否擋下取決於瀏覽器（Safari 會擋；Chrome／Firefox 對 loopback 通常放行，但不保證）。
  這一版沒有提供 `wss://` bridge（需要本機憑證）。目前 dev／區網是 http，請用 http 頁面；若頁面是 https 且連不上，設定面板會顯示警語，請改用 http 位址。
