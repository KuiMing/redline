# Redline TODO

最後更新：2026-10-20

本文件只保留尚未完成的工作。已完成內容請查閱 Git history、`CHANGELOG.md` 與 `docs/records/`。

## 待辦

- **指揮中心「陣營能力」位置調整**（需求記錄：`docs/records/ui-layout/faction-ability-location-request-20261020.md`）：
  - 將目前位於常設購買區下方的橫向「陣營能力」區塊移至畫面右上角，放在「隨機購買區」最右邊。
  - 保留完整能力說明及能力操作按鈕；不得遮住五張隨機購買卡、購買操作、右側控制項或回合控制。
  - 保持固定 `1280 × 720` 舞台等比例縮放；不要改成傳統 Reflow RWD。
  - 不改變隨機購買卡數量、購買規則、焦點狀態或 Joy-Con 操作。
  - 完成時需提供正式 Browser UI screenshot proof，確認右上角位置、間距、可讀性與無遮擋。

- **Mac 實機 Joy-Con 驗證**（右 Joy-Con 按鍵位元已有實機紀錄；左 Joy-Con 與多支獨立手把只有 fixture／假 FTCW 測試，尚未接真實硬體）：
  - 左 Joy-Con 2 的 S2B1 封包：用 `tools/joycon_bridge/run_mac.sh --dump-packets` 確認按鍵位元（offset 9：`0x01` −、`0x08` 按下搖桿、`0x20` Capture；offset 10：`0x01` ↓、`0x02` ↑、`0x04` →、`0x08` ←、`0x10` SR、`0x20` SL、`0x40` L、`0x80` ZL）、左搖桿 offset（x＝12、y＝16，float32 LE）與 Y 軸方向（目前假設 FTCW 向上為正），以及 deadzone 0.15 是否足以消除靜止漂移。
  - 右 Joy-Con 2 搖桿 offset（20／24）與 Y 軸方向的實機確認（按鍵位元已有實機紀錄）。
  - `S2N1` 裝置名稱：實際字串是否含 `(L)`／`(R)`（或 LEFT／RIGHT）、是否每次 `hello` 都會送、是否早於第一筆 S2B1（主埠超過 1.5 秒沒有名稱會改用 `R24800-legacy`，名稱晚到會換身份）、不同的同側 Joy-Con 名稱是否相同。
  - FTCW 多支手把：是否一個 UDP 埠一支（24800–24803）、回覆是否從同一個埠送出；左＋右、兩支同側同時輸入時各自的封包與按鍵是否互不影響。
  - 斷線與重連：關掉／重新連上單一 Joy-Con 時，只有該支在 1 秒後 stale；重連後是否回到同一個 FTCW 埠與名稱（決定 claim 是否保留），以及重連時按住的鍵不會觸發。
  - 確認 Finally the Controller Works 在搖桿靜止時仍持續送封包（否則 1 秒後該支會 stale，閒置後第一次按鍵只會重新建立 baseline）。
  - 用實體 Joy-Con（左、右各一位玩家）走過：大廳、購買、手牌、modal／pending choice、地圖移動與瓦解取消，以及 SL 聚焦選單（開啟、選範圍、B／SL 返回、選定後 Y 建立；兩種顯示模式）與 ZR 戰略地圖縮放循環（第一下就縮放、最大後回到最小、其他分頁不作用；兩種顯示模式）。
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
