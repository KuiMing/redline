# CARD REMAINING EFFECTS IMPLEMENTATION

日期：2026-05-03

## 本輪補上的剩餘 effect type

已在 `server/effect_engine.py` 補上：

- add_internal_conflict
- cancel_card
- conditional_bonus
- dissolve
- refresh_purchase_area
- trash_from_hand_or_discard

## 目前 effect type 覆蓋狀態

結論：

- `action_cards_structured.v1.1.json` 中出現的 effect type
- 已全部在 `server/effect_engine.py` 具備可執行分支

也就是說：

> **卡牌 effect type 覆蓋缺口已清零**

## 本輪採用的 MVP 語義

### add_internal_conflict
- 目前行為：將 `內鬥` 卡加入玩家 discard pile。

### cancel_card
- 目前行為：設置 `turn_log.canceled_propaganda_card = True`，供後續 `conditional_draw` 使用。

### conditional_bonus
- 目前支援 `non_starter_discard`，條件成立時給資源獎勵。

### dissolve
- 目前行為：
  - 若要求 self sacrifice，先移除自己一個組織
  - 再從第一個可用對手城鎮移除一個組織

### refresh_purchase_area
- 目前行為：從目前玩家牌庫抽 3 張到 `game.purchase_area`

### trash_from_hand_or_discard
- 目前行為：
  - 優先 trash 非 starter hand card
  - 再找 discard pile 中非 starter card
  - 若都沒有，再退化為移除 hand/discard 中任一張
  - 會更新 `turn_log.non_starter_discard`

## 本輪快速驗證結果

### add_internal_conflict
- discard pile 成功新增：`內鬥 x3`

### cancel_card + conditional_draw
- `canceled_propaganda_card` flag 成功設置
- 條件抽牌成功生效

### conditional_bonus
- 在 `non_starter_discard=True` 下，propaganda bonus 成功生效

### dissolve
- 自我犧牲 + 對手組織移除成功生效

### refresh_purchase_area
- `purchase_area` 成功刷新為 3 張新牌

### trash_from_hand_or_discard
- 成功優先移除非 starter card
- `non_starter_discard` flag 成功設置

## 目前狀態

到這一步為止：

- effect type 層面：**已全覆蓋**
- 但仍未等於：**所有卡牌已逐張完整驗證**

下一步應進入：

1. 逐張卡牌驗證
2. 逐張記錄：資源 / 手牌 / 棄牌 / 對手影響 / 狀態旗標 / UI 對應結果
