# Redline TODO

最後更新：2026-10-05

本文件只保留尚未完成的工作。已完成內容請查閱 Git history、`CHANGELOG.md` 與 `docs/records/`。

## 待辦

- **Mac 實機 Joy-Con 驗證**（Joy-Con／搖桿控制第一版已完成並通過 mock E2E，但尚未接真實硬體）：
  - 用 `tools/joycon_bridge/run_mac.sh --dump-packets` 確認 S2B1 封包欄位位置（目前 buttons offset 4、float32 x/y offset 8 是假設）與 `y` 軸方向。
  - 確認 Finally the Controller Works 在搖桿靜止時仍持續送封包（否則 1.5 秒後會 stale，閒置後第一次按鍵只會重新建立 baseline）。
  - 用實體 Joy-Con 走過：大廳、購買、手牌、modal／pending choice、地圖移動與瓦解取消，以及 SL 聚焦選單（開啟、選範圍、B／SL 返回、選定後 Y 建立；兩種顯示模式）。
  - 確認 https 頁面連 `ws://127.0.0.1` 在實際使用的瀏覽器是否被 mixed content 擋下；如需支援 https，另開 wss bridge 工作。

## 工作規則
- 開始新工作前先讀本文件，並執行 `git status --short --branch` 與 `git log --oneline -5`。
- 同一時間只保留一個 `in_progress`。
- 完成項目後，從本文件移除。
- 歷史證據放在 `docs/records/<topic>/`，不要放在 repository root；維持 repository root 的 record-like 檔案數量為 0。
- 新增 validator 時，確認輸出路徑不是 repository root，且失敗時回傳非零 exit code。
- UI 變更必須使用正式 Browser UI screenshot proof。
- 事件卡與常設牌互動時，遵守 static supply。`宣傳家`、`思想家`、`資助者`、`資本家`、`分神`、`內鬥` 等固定購買牌不可憑空新增。

## 接手注意事項
- 不要重做情報網 target-choice map highlight。事件卡需要目標選擇時，重用既有 pending choice 與 map highlight 架構。
- 事件卡 validator 與 proof records 放在 `docs/records/event-cards/`。
- 處理奧援卡前，先確認卡名與級別。不要用北國奧援 I 級規則推測 II 級。
