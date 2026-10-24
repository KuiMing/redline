# 客廳輪流模式公開顯示 AI 紅軍行動

記錄日期：2026-10-20
狀態：已完成（2026-10-20）

實作與驗證證據：`AI_RED_ARMY_PUBLIC_ACTION_VALIDATION.md`、`ai-red-army-public-action-20261020/`（桌面與客廳模式 1280×720 截圖、流程與 log 證據）。

## 使用者需求

在客廳輪流模式中，讓現場所有玩家看到 AI 紅軍做了什麼。

## 顯示原則

- AI 紅軍行動結算時，顯示其採取的行動及公開結果。
- 使用置中的公開視窗呈現。
- 公開視窗不與玩家動態重複顯示相同內容。
- 公開視窗顯示的整段期間（包含紅軍回合結束後的等待確認）current player 都必須仍是 red_army；不得先換到下一位玩家，也不能是「伺服器已輪到下一位、只由 UI 停留」。
- 視窗先關閉（「知道了」／Joy-Con A／逾時）之後，才允許推進到下一位玩家與交接；不以「已換人」作為視窗關閉或驗收條件。
- 摘要需涵蓋已公開的卡牌、資源、購買、移動、組織及事件變化。
- 此階段紅軍是當前玩家：即使畫面直接顯示紅軍手牌也沒有關係；先前「不得顯示 AI 隱藏手牌或秘密狀態」的限制對這個畫面不再適用。
- 除了「結束回合前先等公開視窗確認」之外，不得改變、跳過實際規則結算；確認或逾時後必須照原規則推進。
- 等待確認不得無限期阻斷換人流程（有逾時）。

## 驗收證據

實作後需用正式 Browser UI 截圖及流程驗證確認：

1. AI 紅軍行動後，所有玩家可看到明確的行動摘要及結果。
2. 摘要內容正確反映紅軍已執行的行動與資源變化。
3. 相同內容不會同時出現在公開視窗與玩家動態。
4. 視窗顯示的整段期間，權威 current player（伺服器 Game 狀態與 WebSocket state.current_player）都是 red_army；確認或逾時之後伺服器才推進到下一位並出現交接。
5. AI 紅軍的規則結算及下一位玩家流程維持正確。

## 實作說明（2026-10-20，依修正後的需求）

- 前端（客廳輪流）送出 `ai_public_hold` 後，伺服器 `Game.ai_red_army_public_hold = True`。之後 AI 紅軍要執行**結束回合**的 `advance_turn`（行動階段）時，`red_army_ai_runtime` 先不送出，改設 `Game.ai_red_army_ack`（權威狀態，`state.ai_red_army.awaiting_ack = {turn, timeout_seconds}`）並廣播；此時 `current_player` 仍是紅軍。
- 「知道了」／Joy-Con A 送 `ack_ai_red_army`（不受輪到誰限制），或逾時 10 秒（`AI_ACK_TIMEOUT_SECONDS`），runtime 才送出結束回合，伺服器推進到下一位，前端隨即進入交接。
- 沒有啟用 hold（非客廳輪流、一般多人）的遊戲完全不變。
- 驗證：`scripts/validate/validate_hotseat_ai_red_army_public_browser.py`（讀 Game 物件與 WebSocket state 的權威 current player）、`scripts/tests/test_ai_red_army_public_report.py`。
