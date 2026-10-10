# REDLINE Joy-Con bridge

在 Mac 上用右 Joy-Con 2 玩 REDLINE 的**本機**輸入橋接：

```
Joy-Con ─▶ Finally the Controller Works ─UDP 127.0.0.1:24800 (S2B1)─▶ 本 bridge ─WebSocket─▶ 瀏覽器中的 REDLINE
```

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
| `--udp-port N` | Finally the Controller Works 的 UDP 連接埠，預設 24800。 |
| `--allow-origin ORIGIN` | 額外允許的網頁 Origin，可重複。 |
| `--dump-packets` | 印出收到的原始 UDP 封包 hex，用來校正欄位位置。 |
| `--buttons-offset N` / `--stick-offset N` | 覆寫 S2B1 封包欄位位置。 |

`/health` 回傳封包計數與最後封包距今秒數（除錯用）。

## 安全

- **只綁 `127.0.0.1`**（程式內固定，沒有 `--host` 選項）。
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

約 30Hz、每筆：

```json
{"x": 0.0, "y": 0.0, "buttons": [b0, b1]}
```

- `x`、`y`：右搖桿，−1..1，**y 向下為正**（畫面座標）。若上下相反，請在 `bridge.py` 的 `parse_packet` 對 `y` 取負。
- `buttons`：兩個 byte。b0：`0x08 A`、`0x04 B`、`0x02 X`、`0x01 Y`、`0x20 SL`、`0x10 SR`、`0x40 R`、`0x80 ZR`；b1：`0x02 +`、`0x04 STICK`、`0x10 HOME`、`0x20 CAPTURE`（上游 `Switch2Protocol.swift` 的 `capture = 0x0000_2000`，以 little-endian u32 寫出，落在 b1 的 `0x20`）。

## 已知限制（務必閱讀）

- **S2B1 預設使用 Finally the Controller Works v0.2.0 的 44-byte 格式。** 按鍵位於 u32 buttons（低兩個 byte offset 8、9）；REDLINE 使用右搖桿 rx、ry（offset 20、24）。
  如未來版本變更 wire format，可加 `--dump-packets` 對照封包，並用 `--buttons-offset`／`--stick-offset` 暫時覆寫。
- **https 頁面可能擋 `ws://127.0.0.1`（mixed content）。** 是否擋下取決於瀏覽器（Safari 會擋；Chrome／Firefox 對 loopback 通常放行，但不保證）。
  這一版沒有提供 `wss://` bridge（需要本機憑證）。目前 dev／區網是 http，請用 http 頁面；若頁面是 https 且連不上，設定面板會顯示警語，請改用 http 位址。
