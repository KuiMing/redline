# FACTION_ABILITY_PHASE5_IMPLEMENTATION

日期：2026-05-06

## 本輪完成的 phase5 engine 實作

這一輪補上了幾個先前只做建模、尚未真正落地的特殊能力：

### 1. 民主陣線（民運派）
- 可用 2 點任意資源購買已移除牌
- 目前第一版實作為：消耗 2 點總資源，加入 1 張「已移除牌」代理卡到棄牌堆

### 2. 立場試探（自由派）
- 展示牌庫頂牌
- 若購買費用為奇數 → 加入手牌
- 若為偶數 → 放入棄牌堆

### 3. 賭徒耳語（澳門）
- 將 1 張手牌放進牌庫底
- 展示牌庫頂牌
- 第一版以「猜奇數」流程實作
- 猜中時獲得 3 點資金與 3 點宣傳

### 4. 華文傳媒（法輪功）補強
- 先前 phase4 已接第一版
- 這一輪改成更接近規則：購買 propaganda 類牌時，實際消耗 money 資源

## 主要程式改動

### server/game.py
新增 / 補上：
- `_resource_total()`
- `_purchase_area_card_cost_total()`
- `_purchase_area_card_cost_money()`
- `_top_card_cost_total()`
- `_activated_faction_action(player, action_name)`

### 目前已接的 activated faction actions
- `民主陣線`
- `立場試探`
- `賭徒耳語`

### buy_card()
- `華文傳媒` 現在改為真正以 money 支付 propaganda 類牌成本

### server/main.py
- websocket 新增：
  - `action = 'faction_action'`
- 會轉去 `game._activated_faction_action(...)`

## 驗證
新增：
- `scripts/validate_faction_abilities_phase5.py`

輸出：
- `FACTION_ABILITY_PHASE5_VALIDATION.json`
- `FACTION_ABILITY_PHASE5_VALIDATION.md`

### 驗證結果
- total: 4
- passed: 4
- failed: 0

已涵蓋：
- 民主陣線
- 立場試探
- 華文傳媒（支付側）
- 賭徒耳語

## 仍未完成
- 共用組織
- 民族祭儀
- 印度研究分析室
- 非暴力更深層的持有 / 得牌限制
- 其他特殊地圖 / 根據地遷移規則
