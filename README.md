# Redline

Redline 是一個以瀏覽器 UI 與 Python WebSocket 伺服器實作的桌遊原型專案。

## 資料夾結構

- `server/`
  - 遊戲狀態、規則解析、卡牌效果與 WebSocket/API 伺服器邏輯。
- `static/`
  - 前端 HTML/CSS/JavaScript、地圖 UI、遊戲主畫面與瀏覽器端互動。
- `data/`
  - 遊戲資料檔，例如卡牌、城鎮、陣營與地圖資料。
- `scripts/`
  - 驗證腳本、資料產生腳本與一次性檢查工具。
- `docs/`
  - 設計文件、提交範圍、驗證紀錄與截圖證據。
- `docs/records/`
  - 任務導向的驗證紀錄與 battle-shot / screenshot 證據。新紀錄建議放在這裡，不要再散落到 repo 根目錄。
  - 目前已依主題整理，例如 `leak-card/`、`purchase/`、`layout-ui/`、`faction-ui/`、`safehouse/`、`lobby/`、`map-ui/`。
- `sketches/`
  - UI 草圖或一次性設計探索；正式實作前應整理成 `static/` 或 `docs/`。

## 紀錄檔整理規則

驗證與截圖檔案請優先放進 `docs/records/<topic>/`：

- 驗證報告：`docs/records/<topic>/*_VALIDATION.md`
- 機器可讀結果：`docs/records/<topic>/*_VALIDATION.json`
- 視覺證據截圖：`docs/records/<topic>/*.png`
- 提交/整理說明：`docs/records/<topic>/*_COMMIT_SCOPE.md`

臨時執行輸出不應提交：

- `server.log`
- `__pycache__/`
- Playwright 或手動除錯的中間截圖
- 沒有對應任務說明的 preview / battle-shot 圖片

## 走漏風聲驗證紀錄

本次 `走漏風聲` 相關紀錄已整理到：

- `docs/records/leak-card/LEAK_CARD_COMMIT_SCOPE.md`
- `docs/records/leak-card/LEAK_CARD_VALIDATION.md`
- `docs/records/leak-card/LEAK_CARD_VALIDATION.json`
- `docs/records/leak-card/LEAK_CARD_TARGET_UI_VALIDATION.md`
- `docs/records/leak-card/LEAK_CARD_TARGET_UI_VALIDATION.json`
- `docs/records/leak-card/leak_card_target_modal.png`

重跑驗證：

```bash
python3 scripts/validate_leak_card.py
python3 scripts/validate_leak_card_target_ui.py
```

以上腳本會自動把輸出寫入 `docs/records/leak-card/`。
