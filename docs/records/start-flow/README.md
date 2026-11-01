# 開始遊戲前流程 — 證據

分支 `feat/start-game-entry-flow-latest`。截圖由 `scripts/tests/test_start_flow_browser.py` 在真實 Chromium（Playwright）對真實 `uvicorn server.main:app` 產生：

    START_FLOW_PROOF_DIR=docs/records/start-flow uv run --frozen python -m pytest scripts/tests/test_start_flow_browser.py

**Joy-Con 沒有實體硬體。** 配對截圖與測試使用真的 `tools/joycon_bridge`（`ControllerRegistry`＋v2 WebSocket bridge），由測試執行緒以 fixture 的 FTCW S2B1／S2N1 封包模擬四支手把（SL／SR 位元取自 `scripts/tests/fixtures/joycon_dual_layout.json`）。驗證的是協定、配對邏輯與伺服器狀態，不是藍牙／FTCW 實機行為（見 `TODO.md`）。

| 檔案 | 內容 |
| --- | --- |
| 01_entry_three_paths.png | 初始畫面三條路徑，沒有人數選擇 |
| 02_setup_computer.png | 建立設定：難度＋操作方式（電腦，直接可繼續） |
| 03_pairing_waiting.png | Joy-Con 配對中，四支 fixture 手把已監聽，尚未配對、不可完成 |
| 04_pairing_first_paired.png | 第一支配對成功＝P1，「完成配對」啟用 |
| 06_pairing_four_paired.png | 四支依序配對為 P1～P4 |
| 05_guest_join_readonly_settings.png | 以房間代碼加入：略過設定，房主設定唯讀，難度／紅軍控制停用 |
| 09_host_name_and_faction_screen.png | 完成設定後進入既有行動代號畫面（房主設定摘要） |
| 07／08_living_room_*.png | `?display=living-room`：固定 1280×720 舞台等比縮放 |
