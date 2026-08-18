# 行動階段與購買階段合併（出牌／購買可自由交錯）

日期：2026-08-18

## 使用者回報

「出牌 → 結束行動 → 購買 → 無法再出牌」。玩家一旦按下「開始購買階段」，就再也不能打出手牌；
反過來在行動階段又完全不能購買，等於被迫把一個回合切成兩段不可逆的操作。

## 根因

`server/game.py` 把「出牌」與「購買」實作成兩個循序且不可逆的 `TurnPhase`：

- `TurnPhase.ACTION`：`play_card` / `build_organization` / 移動可用，`buy_cards` 直接回傳
  `{"error": "Not in PURCHASE phase"}`。
- `TurnPhase.END`：`buy_cards` 才放行，但 `play_card` 被 `!= TurnPhase.ACTION` 閘門擋下。

`advance_turn_phase()` 需要按兩次才能結束一個回合（`ACTION -> END`、`END -> _end_turn`），
中間那次 advance 是不可逆的。這其實偏離了 `rules.md:91-129`——文件從頭到尾只描述一個連續的
行動階段，從未獨立命名「購買階段」。

## 修法

不是「兩個 phase 都放寬」，而是把 `ACTION` 分支摺疊進 `END` 分支的既有邏輯：

1. `advance_turn_phase()` 原本 `TurnPhase.END` 分支整段（事件結算時機／頂牌流程／香港根據地遷移／
   `_end_turn()`）**逐字**抽成新方法 `Game._finish_action_phase()`，一行都沒有改動或重排。
2. `advance_turn_phase()` 的 `EVENT` 分支完全不動；其餘情況（`ACTION` 與防禦性的 `END` 重入）
   一律 `self.turn_phase = TurnPhase.END` 後立刻呼叫 `_finish_action_phase()` 並回傳其結果。
   於是「結束行動階段」變成唯一一次不可逆的動作。
3. `buy_cards()` 是**唯一**放寬的閘門：`turn_phase not in (ACTION, END)` 才拒絕，錯誤字串沿用既有的
   `"Not in ACTION phase"`（`static/player_messages_zh_tw.js` 已有中文對應）。
4. `play_card` / `_validate_organization_move` / `build_organization` 的 `!= TurnPhase.ACTION` 閘門
   **維持不變**：`TurnPhase.END` 仍是一個真的會停留的狀態——香港「香港抗暴之戰」事件觸發的免費
   根據地遷移等待窗口就停在這裡（此時 `_end_turn(advance_player=False)` 已跑過、手牌已補到 5 張），
   那個閘門是唯一擋住玩家用剛補到的新手牌繼續出牌的機制。
5. 前端 `static/app.js`：advance 按鈕文字 `行動 -> 結束行動階段`；購買勾選面板與購買區卡片改成
   `action`／`end` 皆可購買；手牌出牌的判斷邏輯**完全不動**（只更新過時文案），保留
   `scripts/validate_turn_phase_action_gating.py` 與 `test_red_army_ability_timing_ws.py` 的逐字字串比對。
6. `server/main.py` 三個 `/test/*` 端點的 advance 次數同步收斂（少一次 advance 才會落在同一個座位）。

## 驗證結果

### 引擎／單元測試

- `pytest scripts/tests`（排除 4 個需要真實 ws/lobby 的檔案）：**366 passed**。
- `scripts/tests/test_hong_kong_base_relocation.py`：**10 passed**，且只改前置設定（拿掉手動
  `game.turn_phase = TurnPhase.END`），**沒有動任何斷言**——這是 `_finish_action_phase()` 抽取是否
  忠實原邏輯的準繩。
- `scripts/validate_turn_phase_action_gating.py`：**14/14**，其中新增的正面驗證確認同一位玩家不呼叫
  `advance_turn_phase()` 就能「出牌 → 購買 → 出牌 → 購買」全部成功，`turn_phase` 全程 `ACTION`、
  `current_player` 不變；單次 advance 後手牌補到 5 張並換人。
- 全部非瀏覽器 validator 與改動前（HEAD）逐一比對：沒有任何一支從通過變成失敗；
  `validate_deck_lifecycle`（3/6 → 6/6）、`validate_faction_abilities_phase3`、
  `validate_india_research_room(_support_taxonomy)`、`validate_action_card_recomposition` 反而由失敗轉為通過
  ——它們本來就是被 `"Not in PURCHASE phase"` 擋住的購買測試。

### 真實瀏覽器（Playwright + Chromium）

`scripts/validate_action_phase_interleave_browser.py` — **8/8 通過**，對應使用者原始回報的確切流程：

| # | 驗收項目 | 結果 |
|---|---|---|
| 1 | 行動階段一開始 `#advanceStepBtn` 就顯示「結束行動階段」，購買區已可勾選（不必先按 advance） | PASS |
| 2 | 打出手牌（資源模式）→ 資源增加、`turn_phase` 仍是 `action` | PASS |
| 3 | 勾選並購買一張卡 → 購買成功、`turn_phase` 仍是 `action` | PASS |
| 4 | **購買後再打出一張手牌**（修正前必定失敗的步驟）→ 成功、沒有「目前是購買階段」錯誤訊息 | PASS |
| 5 | 再購買一次 → 成功 | PASS |
| 6 | 陣營主動能力入口在整個合併行動階段都可用 | PASS |
| 7 | 按一次「結束行動階段」→ 手牌補到 5 張、換下一位玩家、`turn_phase` 回到 `action` | PASS |
| 8 | 全程 console error 數為 0 | PASS |

截圖：`docs/records/turn-flow/action-phase-interleave-20260818_215703/`
（`01`…`07`，JSON 報告見 `ACTION_PHASE_INTERLEAVE_BROWSER_20260818_215703.json`）

其他瀏覽器驗證：`validate_action_first_phase_browser.py` 6/6、`validate_purchase_affordance_browser.py` 3/3、
`validate_faction_ability_triggers_browser.py` 7/7、`validate_hong_kong_base_relocation_browser.py` 23/23
（香港根據地遷移等待窗口在真實 UI 上與修正前完全一致）、`validate_elite_defection_failure_browser.py` 2/2。
