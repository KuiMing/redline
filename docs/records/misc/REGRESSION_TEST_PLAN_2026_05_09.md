# REGRESSION_TEST_PLAN_2026_05_09

日期：2026-05-09

## 目的

把既有 `scripts/validate_*.py` 與驗證產物整理成新版前端與規則實作可重跑的回歸測試流程。

本計畫依 `rules.md` / `RULES.md`、既有驗證腳本、以及近期 UI 改版狀態整理。

## 現況判斷

前人留下的測試腳本可用，但不能全部原封不動視為完整規則驗收。

### 可保留直接重跑

- `scripts/validate_all_action_cards.py`
- `scripts/validate_support_purchase_deck_runtime.py`
- `scripts/validate_support_card_effects_runtime.py`
- `scripts/validate_india_research_room.py`
- `scripts/validate_india_research_room_support_taxonomy.py`
- `scripts/validate_shared_*.py`
- `scripts/validate_faction_picker_combinations.py`

### 需要修正後再當主回歸

- `scripts/validate_full_gameplay_2p.py`
- `scripts/validate_full_gameplay_multi.py`
- `scripts/validate_card_type_ui_flows.py`
- `scripts/validate_all_cards_ui_batch.py`

### 需要新增

- 規則級 setup 驗證
- 規則級 turn flow 驗證
- 規則級 movement 驗證
- 規則級 victory 驗證
- event / era 驗證
- 最新主畫面 tabs / stage / 戰況紀錄玩家卡片 UI 驗證

## P0：本輪立即接回

### 1. 修正 2P 完整流程驗證

目標檔案：

- `scripts/validate_full_gameplay_2p.py`

要求：

- 處理 `GamePhase.BASE_SELECTION`。
- 驗證根據地唯一且合法。
- 不再讓 `game_phase: setup` / `winner: None` 被視為成功結尾。
- forced victory 改成合法勝利路徑：非紅軍在牆內 14 組織。
- 報告增加 summary。

### 2. 新增勝利條件規則驗證

目標檔案：

- `scripts/validate_victory_rules.py`

要求：

- 紅軍第 20 回合後 survival win。
- 紅軍臺灣 14 有效組織提前勝利。
- 反共牆內 14 有效組織勝利。
- shared organization 可計入反共勝利。
- 不滿足條件時不得勝利。

### 3. 新增新版主 UI 回歸

目標檔案：

- `scripts/validate_main_tabs_layout.py`

要求：

- Playwright 進入測試狀態。
- 驗證「指揮中心」「戰略地圖」「戰況紀錄」三個 Tab 可切換。
- 驗證 `#playerStatusOverview .player-status-card` 數量等於玩家數。
- 驗證玩家卡片包含玩家名稱、陣營、根據地、組織、資金、宣傳、手牌、移動、當前玩家標籤。
- 驗證 1280×720 無 body overflow。
- 產出主驗證截圖。

## P1：下一輪補

### setup rules

新增：

- `scripts/validate_setup_rules.py`

驗證：

- 至少一名紅軍。
- 起始玩家不是紅軍。
- 紅軍組織上限 = 反共玩家數 × 8，若有臺灣 +8。
- 反共組織上限 22。
- 起始牌庫 7 追隨者 + 3 樂捐者，抽 5。
- 事件牌庫 20。
- 常設購買區 6 張 + 隨機購買區 5 張。
- 根據地選擇順序與合法性。

### turn flow rules

新增：

- `scripts/validate_turn_flow_rules.py`

驗證：

- EVENT → ACTION → END → 下一玩家 EVENT。
- END 時補手牌至 5。
- END 時補滿購買區，不是買完立刻補。
- 一輪後 turn +1。
- 起始玩家指示物傳遞規則。

### movement rules

新增：

- `scripts/validate_movement_rules.py`

驗證：

- road 一般 1 格。
- rail 是否一次 3 格，需依規則語義確認。
- 翻牆消耗 2 次移動。
- 可跨越己方組織。
- 不可跨越敵方組織。
- shared organization 移動歸屬。

## P2：後續補強

### event / era rules

新增：

- `scripts/validate_event_era_rules.py`

驗證：

- 事件牌庫抽牌。
- 歲月靜好。
- 自動執行事件。
- 時代關卡觸發與 duration tick。

### card rule expectations

新增：

- `scripts/validate_card_rule_expectations.py`

把 `validate_all_action_cards.py` 從「可執行 smoke」升級到「每張卡明確 expected result」。

## 建議標準回歸順序

1. 後端規則 smoke：
   - `python3 scripts/validate_victory_rules.py`
   - `python3 scripts/validate_full_gameplay_2p.py`
   - `python3 scripts/validate_full_gameplay_multi.py`
   - `python3 scripts/validate_all_action_cards.py`

2. 專項規則回歸：
   - `python3 scripts/validate_support_purchase_deck_runtime.py`
   - `python3 scripts/validate_support_card_effects_runtime.py`
   - `python3 scripts/validate_india_research_room_support_taxonomy.py`
   - `python3 scripts/validate_shared_move_phase8.py`
   - `python3 scripts/validate_shared_dissolve_phase8.py`
   - `python3 scripts/validate_shared_victory_phase8.py`

3. UI 回歸：
   - 先啟動 server：`python3 -m uvicorn server.main:app --host 127.0.0.1 --port 8000`
   - `python3 scripts/validate_main_tabs_layout.py`
   - `python3 scripts/validate_card_type_ui_flows.py`
   - `python3 scripts/validate_all_cards_ui_batch.py --start 0 --end 10` 等 batch

4. 視覺驗證：
   - 檢查 Playwright 截圖。
   - 重要畫面送 Telegram 或附在驗證報告。
