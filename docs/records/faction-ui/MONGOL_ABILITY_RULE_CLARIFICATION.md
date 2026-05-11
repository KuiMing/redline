# MONGOL_ABILITY_RULE_CLARIFICATION

日期：2026-05-05

## 使用者澄清

蒙古的能力描述是：
- 其他玩家須先棄 1 張手牌，才可以用手牌或陣營能力瓦解您的組織。

而蒙古的發展合法性應為：
- 可以在 **蒙古的發展空間** 建立組織
- 也可以在 **沒有特別標示陣營的城鎮** 建立組織
- 不能在其他已標示不同陣營 camp 的城鎮建立組織

## 本輪修正

### server/game.py
- 移除先前錯誤加入的額外 build restriction
- 恢復以既有 camp legality 規則處理蒙古：
  - `蒙古 camp` 可建
  - `無 camp` 可建
  - `其他 camp` 不可建

### scripts/validate_faction_abilities_phase1.py
- 把原本錯誤的 `mongol_school_restriction` 測試改成：
  - `mongol_develop_legality`
- 驗證以下三件事：
  1. 蒙古 camp 可建
  2. 無 camp 城鎮可建
  3. 其他 camp 城鎮不可建

## 驗證結果
- phase1 驗證維持：6 / 6 passed
- 蒙古檢查結果：
  - `allow_mongol=True`
  - `allow_uncamped=True`
  - `block_other=True`
  - `result={'success': True}`
