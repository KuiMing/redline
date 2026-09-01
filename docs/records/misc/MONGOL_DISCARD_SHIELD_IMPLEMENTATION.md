# MONGOL_DISCARD_SHIELD_IMPLEMENTATION

日期：2026-05-05

## 本輪完成

已開始把蒙古的核心防瓦解能力真正接進 engine：

- `盟旗學校` / `【盟族學校】其他玩家須先棄1張手牌，才可以用手牌或陣營能力瓦解您的組織。`

## 實作內容

### server/game.py
新增：
- `_can_target_org_with_dissolve(attacker, defender, source="card")`
- `dissolve_organization(attacker, defender, town, source="card")`

### 規則行為
若目標玩家具有 `盟旗學校`：
- 攻擊者若手牌為空 → 瓦解失敗
- 攻擊者若有手牌 → 先棄 1 張手牌，才允許瓦解繼續

### server/effect_engine.py
- `dissolve` 類效果現在改走 `game.dissolve_organization(...)`
- 不再直接繞過能力檢查去扣組織

## 驗證
新增：
- `scripts/validate/validate_mongol_discard_shield.py`

輸出：
- `MONGOL_DISCARD_SHIELD_VALIDATION.json`
- `MONGOL_DISCARD_SHIELD_VALIDATION.md`

### 驗證結果
#### success case
- 攻擊者有 1 張手牌
- 先棄掉該手牌
- 瓦解成功
- 蒙古組織被移除

#### fail case
- 攻擊者沒有手牌
- 回傳錯誤：
  - `盟旗學校：須先棄1張手牌，才可以瓦解蒙古組織`
- 蒙古組織保留

## 目前範圍
這一輪已接上：
- `dissolve` 類卡效入口

尚未完整覆蓋的潛在入口：
- 若之後新增其他直接瓦解組織的 faction ability / API 入口，也要統一改走這個防護邏輯
