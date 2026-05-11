# FACTION_ABILITY_PHASE9_SUPPORT_RUNTIME

日期：2026-05-07

## 本輪完成

把 support cards 從 taxonomy 與限制判定，再往前推進到 runtime / purchase_area。

## 已完成

### 1. Game 啟動時建立 support runtime cards
#### server/game.py
新增：
- `_support_card_runtime_type(name)`
- `_make_support_card(support_name)`
- `_initial_purchase_area()`

目前先用最小可驗證方式，把以下 5 張放進初始 `purchase_area`：
- 宣傳家
- 思想家
- 資助者
- 資本家
- 印度奧援

### 2. purchase_area 現在包含 `印度奧援`
#### server/game.py::__init__
- 原本 `purchase_area = []`
- 現在改成：
  - `self.purchase_area = self._initial_purchase_area()`

這代表 support card 已開始真正進到 runtime，而不是只停留在 support JSON / taxonomy 文件層。

### 3. support card cost 接到 buy_card 成本判定
#### server/game.py
擴充：
- `_purchase_area_card_cost_total(card)`
- `_purchase_area_card_cost_money(card)`

現在若 purchase_area 中是 support card，會從 support taxonomy 的 `cost` 解析其費用。

### 4. 印度研究分析室在 runtime purchase_area 生效
因為 `印度奧援` 已進 purchase_area，現在可直接驗證：
- `tibet_dehradun` 能買 `印度奧援`
- `tibet_dehradun` 不能買 `英美奧援`

## 驗證
新增：
- `scripts/validate_support_cards_runtime_purchase_area.py`

輸出：
- `SUPPORT_CARDS_RUNTIME_PURCHASE_AREA_VALIDATION.json`
- `SUPPORT_CARDS_RUNTIME_PURCHASE_AREA_VALIDATION.md`

### 結果
- total: 3
- passed: 3
- failed: 0

### 已驗證內容
1. 初始 `purchase_area` 已包含：`印度奧援`
2. `tibet_dehradun` 可成功購買 `印度奧援`
3. `tibet_dehradun` 被正確禁止購買 `英美奧援`

## 目前限制
- 目前 support runtime integration 仍是 MVP：
  - 先把 `印度奧援` 放進初始 purchase_area 以驗證規則鏈
  - 尚未完整依 rules.md 那套「隨機 18 張奧援卡」混入購買區牌庫
- support card 的 tier / preferred ruler 效果尚未真正結算
- 前端主畫面與奧援卡 UI 顯示尚未做實戰截圖
