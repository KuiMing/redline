# FACTION_ABILITY_PHASE4_IMPLEMENTATION

日期：2026-05-06

## 本輪完成的 phase4 engine 實作

這一輪先補了幾個特殊但重要的 faction abilities：

### 1. 華文傳媒（法輪功）
- 可用資金支付宣傳類購買
- 目前在 `buy_card()` 第一版已接線：購買 propaganda 類牌時，會走 money 付款側邏輯

### 2. 各界資助（民運派）
- 開局額外加入 1 張 `資助者`

### 3. 活動家（性別革命）
- 開局額外加入 2 張 `宣傳家`

### 4. 人同此心（性別革命）
- 每回合第 1 次打出含宣傳的牌時，獲得 2 點宣傳

## 主要程式改動

### server/game.py
新增 / 補上：
- `_resolve_ability_text()` 可直接把以下 abilities_text 轉為可執行能力：
  - 華文傳媒
  - 各界資助
  - 民主陣線（先建模，尚未完整 engine 化）
  - 立場試探（先建模，尚未完整 engine 化）
  - 賭徒耳語（先建模，尚未完整 engine 化）
  - 活動家
  - 人同此心
- `_apply_setup_abilities()` 現在支援：
  - 各界資助 → 資助者
  - 活動家 → 2 張宣傳家
- `play_card()` 現在支援：
  - 人同此心 → 第一張 propaganda 給 2 點宣傳
- `buy_card()` 現在支援：
  - 華文傳媒 → 宣傳牌可用 money 支付側邏輯

## 驗證
新增：
- `scripts/validate/validate_faction_abilities_phase4.py`

輸出：
- `FACTION_ABILITY_PHASE4_VALIDATION.json`
- `FACTION_ABILITY_PHASE4_VALIDATION.md`

### 驗證結果
- total: 4
- passed: 4
- failed: 0

已涵蓋：
- 華文傳媒
- 各界資助
- 活動家
- 人同此心

## 仍未完成
- 民主陣線 尚未真正完成「用 2 點任意資源買移除牌」
- 立場試探 尚未真正完成奇偶翻牌行為
- 賭徒耳語 尚未真正完成猜奇偶 / 命中獎勵流程
- 共用組織 / 民族祭儀 / 印度研究分析室 等仍未完成
