# FACTION_ABILITY_PHASE2_IMPLEMENTATION

日期：2026-05-05

## 本輪完成的 phase2 engine 實作

這一輪先補上高頻模板能力的第一批：

### 1. 商貿組織
- 每回合第 1 次打出有資金的牌時，抽 1 張牌
- 已接線到 `play_card()` 階段觸發

### 2. 展現實力
- 當一回合內打出至少 3 張不同名稱的非起始牌時，獲得 3 點資金
- 目前先固定給 3 點資金作為第一版可執行實作

### 3. 殉道者 / 青山里
- 己方牆內組織被他人成功瓦解時，抽 1 張牌
- 已接線到 `dissolve_organization()`

### 4. 基金會 / 共合會
- 每回合第 1 次打出有資金的牌時，獲得 2 點資金
- 已接線到 `play_card()`

## 補強內容

### server/game.py
新增 / 補上：
- `_resolve_ability_text()`
  - 可把 `abilities_text` 解析成可執行模板能力
- `turn_log['played_nonstarter_names']`
- `turn_log['combo_reward_triggered']`
- `play_card()` 現在會處理：
