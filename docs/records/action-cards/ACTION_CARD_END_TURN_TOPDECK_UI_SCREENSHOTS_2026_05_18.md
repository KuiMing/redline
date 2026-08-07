# 行動預告／行動募資 end-turn UI screenshots

> **本檔已過時**——2026-08-07 使用者要求改版：打出行動預告/行動募資時立刻拿到宣傳/資金，
> 頂牌改為玩家主動觸發的獨立動作（頂牌按鈕），不再是「留在手上、回合結束前跳出
> `end_turn_topdeck_action` 選項讓你決定要不要整張打出」。本檔記錄的流程與截圖僅供歷史參考；
> 新流程的驗證見 `ACTION_CARD_END_TURN_TOPDECK_RUNTIME_VALIDATION.{md,json}` 與
> `TOPDECK_PURCHASED_CHOICE_VALIDATION_20260711.{md,json}`。

Generated at: `2026-05-18`

## Scope

使用真實 Redline UI 驗證 `行動預告` / `行動募資` 的回合結束前使用流程：

1. 玩家在 END / 結束階段，手上仍有對應卡牌，且本回合購得牌位於棄牌堆。
2. 按下「結束回合」後，UI 顯示 `end_turn_topdeck_action` 提示：可選「不使用」或「使用 行動預告 / 行動募資」。
3. 選擇使用後，本回合購得牌先置於牌庫頂。
4. 同一次回合結束補牌後，該購得牌進入玩家新手牌。
5. 戰況紀錄顯示 placed bought card / used card before drawing new hand / End of turn。

## 行動預告

- 起始狀態：`ACTION_ANNOUNCEMENT_END_TURN_01_BEFORE.png`
  - END 結束階段。
  - viewer 手牌含 `行動預告`。
  - 尚未按「結束回合」。
- 提示狀態：`ACTION_ANNOUNCEMENT_END_TURN_02_PROMPT.png`
  - 按「結束回合」後出現 `end_turn_topdeck_action`。
  - 可選「不使用」或「使用 行動預告」。
- 補牌結果：`ACTION_ANNOUNCEMENT_END_TURN_03_REFILL_HAND.png`
  - 使用後進入下一玩家事件階段。
  - viewer 手牌補到 5 張。
  - 第一張為 `剛購買的支援者`，證明本回合購得牌在補牌時進手牌。
- 戰況紀錄：`ACTION_ANNOUNCEMENT_END_TURN_04_LOG.png`
  - 顯示 `viewer placed bought card 剛購買的支援者 on deck top`。
  - 顯示 `viewer used 行動預告 before drawing new hand`。
  - 顯示 `End of turn for viewer`。

## 行動募資

- 起始狀態：`ACTION_FUNDRAISING_END_TURN_01_BEFORE.png`
  - END 結束階段。
  - viewer 手牌含 `行動募資`。
  - 尚未按「結束回合」。
- 提示狀態：`ACTION_FUNDRAISING_END_TURN_02_PROMPT.png`
  - 按「結束回合」後出現 `end_turn_topdeck_action`。
  - 可選「不使用」或「使用 行動募資」。
- 補牌結果：`ACTION_FUNDRAISING_END_TURN_03_REFILL_HAND.png`
  - 使用後進入下一玩家事件階段。
  - viewer 手牌補到 5 張。
  - 第一張為 `剛購買的募資對象`，證明本回合購得牌在補牌時進手牌。
- 戰況紀錄：`ACTION_FUNDRAISING_END_TURN_04_LOG.png`
  - 顯示 `viewer placed bought card 剛購買的募資對象 on deck top`。
  - 顯示 `viewer used 行動募資 before drawing new hand`。
  - 顯示 `End of turn for viewer`。

## Setup note

本次截圖使用 server-side proof endpoint `/test/setup-end-turn-topdeck-proof` 建立合法 MAIN / END 階段 proof state，之後透過真實瀏覽器 UI 與 WebSocket 操作「結束回合」與 modal 選項；非靜態 mock。
