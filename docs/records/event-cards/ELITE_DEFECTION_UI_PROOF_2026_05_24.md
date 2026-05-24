# 紅軍權貴出逃 UI Proof — 2026-05-24

## 目標
驗證 `紅軍權貴出逃` 成功後，正式 browser UI 會重用既有 pending card choice modal，讓玩家從「手牌或棄牌堆」選 1 張牌移除。

## Scenario
- Setup endpoint: `POST /test/setup-elite-defection-event-proof`
- Formal UI URL: `http://127.0.0.1:8000/?game_id=b0624f68-3576-4937-8ac7-34e87ddd59d4&player_id=e3b064b0-1faa-4d55-bb94-1be8a4092307`
- Event: `紅軍權貴出逃`
- Trigger: organization movement 3 times
- Moves performed via the live browser/websocket UI action path:
  1. `桃園` → `新竹` via rail
  2. `基隆` → `新北` via road
  3. `臺中` → `南投` via road

## Pending choice proof
Screenshot: `ELITE_DEFECTION_UI_PENDING_CHOICE_2026_05_24.png`

Observed in formal browser UI:
- Event panel: `紅軍權貴出逃`
- Event status/progress in DOM snapshot: `成功已結算`, `進度：3/3`
- Modal title: `卡牌選擇` / `紅軍權貴出逃`
- Prompt: `紅軍權貴出逃：請從己方手牌或棄牌堆中移除 1 張牌。`
- Options include:
  - `手牌｜手牌移除目標`
  - `手牌｜手牌保留`
  - `棄牌堆｜棄牌移除目標`

## Resolved proof
Screenshot: `ELITE_DEFECTION_UI_RESOLVED_2026_05_24.png`

After choosing `棄牌堆｜棄牌移除目標`:
- Card-choice modal is closed.
- Event panel shows `紅軍權貴出逃` with status `成功已結算`.
- Event progress shows `3/3`.
- `pending_choice` is `null`.
- Viewer discard pile is empty.
- Browser state/action log confirms:
  - 3 organization moves were recorded.
  - `棄牌移除目標 returned to purchase deck discard`.
  - `viewer trashed 棄牌移除目標 from 棄牌堆 via 紅軍權貴出逃`.

## Artifacts
- `docs/records/event-cards/ELITE_DEFECTION_UI_PENDING_CHOICE_2026_05_24.png`
- `docs/records/event-cards/ELITE_DEFECTION_UI_RESOLVED_2026_05_24.png`
- `docs/records/event-cards/ELITE_DEFECTION_UI_PROOF_2026_05_24.json`
