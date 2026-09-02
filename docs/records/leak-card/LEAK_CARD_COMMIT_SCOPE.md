# 走漏風聲提交範圍建議

日期：2026-05-11

## 最小應提交檔案

- `data/action_cards_structured.v1.1.json`
  - 將 `走漏風聲` 效果改成 `leak_top_deck`，避免沿用舊的 `peek_deck + add_internal_conflict`。
- `server/effect_engine.py`
  - 實作 `leak_top_deck`：指定目標玩家棄牌庫頂牌；若該牌購買費用 >= 1，從常設購買區扣 1 張 `內鬥` 並放到目標棄牌堆；供應為 0 時不新增。
- `server/game.py`
  - 在消耗手牌前擋下惡意或錯誤 payload：`走漏風聲` 不可指定自己或不存在的玩家。
- `static/app.js`
  - `走漏風聲` 行動模式開啟目標玩家 modal。
  - 點目標後送出 `target_player_id`。
  - 修正手牌 inline onclick 字串 escaping，避免中文字/引號造成 attribute 壞掉。
- `scripts/validate/validate_leak_card.py`
  - 後端規則驗證。
- `scripts/validate/validate_leak_card_target_ui.py`
  - UI modal 與 payload 驗證。
- `docs/records/leak-card/LEAK_CARD_VALIDATION.json`
- `docs/records/leak-card/LEAK_CARD_VALIDATION.md`
- `docs/records/leak-card/LEAK_CARD_TARGET_UI_VALIDATION.json`
- `docs/records/leak-card/LEAK_CARD_TARGET_UI_VALIDATION.md`
- `docs/records/leak-card/leak_card_target_modal.png`
  - 視覺證據截圖。
- `README.md`
  - 說明專案資料夾結構與紀錄檔歸檔規則。
- `docs/records/README.md`
  - 說明 `docs/records/` 的命名與整理慣例。

## 不應混入本次走漏風聲 commit 的 tracked 變更

這些是其他任務/地圖/UI 對齊相關，建議另開 commit 或先保留未 staged：

- `PURCHASE_SECTION_ALIGNMENT_VALIDATION.json`
- `PURCHASE_SECTION_ALIGNMENT_VALIDATION.md`
- `data/map.json`
- `map.json`（目前是 deleted，需特別小心）
- `scripts/validate/validate_purchase_section_alignment.py`
- `static/leaflet_embed_logic.js`
- `static/leaflet_full_map.html`
- `static/leaflet_game_map_logic.js`
- `static/style.css`

## 可刪或應忽略的暫存 artifacts

建議不要 commit：

- `server.log`
- `scripts/__pycache__/`
- `server/__pycache__/`
- 大量中間截圖，例如：
  - `safehouse_*.png`
  - `hong_kong_*.png`
  - `taiwan_*.png`
  - `*_preview*.png`
  - `*_validation.png`（除本次 `leak_card_target_modal.png` 外）
  - `rerun_after_user_code_change_*.png`

## 需人工判斷是否屬於其他功能的未追蹤檔

這些看起來可能是其他功能/資料重建成果，不建議直接刪：

- `data/map.json`
- `data/town_coordinates.v1.json`
- `data/factions/rebel_authoritative_rebuilt.v1.json`
- `data/factions/rebel_expansion_authoritative.v1.json`
- `static/map-module.js`
- `static/map_test.html`
- `scripts/generate_era_structured.py`
- `scripts/generate_town_coordinates.py`
- `scripts/validate/validate_ui_card_flows.py`
- `test_*.py`
- `sketches/`
- 各類 `*_VALIDATION.json/md`、`*_BATTLESHOT.json`、`*_PREVIEW.json`

## 已跑驗證

```bash
python3 -m py_compile server/game.py server/effect_engine.py scripts/validate/validate_leak_card.py scripts/validate/validate_leak_card_target_ui.py
node --check static/app.js
python3 scripts/validate/validate_leak_card.py
python3 scripts/validate/validate_leak_card_target_ui.py
```

結果：全部通過。

## 建議 staging 指令

```bash
git add \
  data/action_cards_structured.v1.1.json \
  server/game.py \
  server/effect_engine.py \
  static/app.js \
  scripts/validate/validate_leak_card.py \
  scripts/validate/validate_leak_card_target_ui.py \
  README.md \
  docs/records/README.md \
  docs/records/leak-card/LEAK_CARD_VALIDATION.json \
  docs/records/leak-card/LEAK_CARD_VALIDATION.md \
  docs/records/leak-card/LEAK_CARD_TARGET_UI_VALIDATION.json \
  docs/records/leak-card/LEAK_CARD_TARGET_UI_VALIDATION.md \
  docs/records/leak-card/leak_card_target_modal.png \
  docs/records/leak-card/LEAK_CARD_COMMIT_SCOPE.md
```

建議 commit message：

```bash
git commit -m "[verified] implement leak card target selection"
```
