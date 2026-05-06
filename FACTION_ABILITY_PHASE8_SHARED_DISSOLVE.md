# FACTION_ABILITY_PHASE8_SHARED_DISSOLVE

日期：2026-05-07

## 本輪完成

把 phase8 最後一塊重要 backend 規則往前補：shared dissolve / shared defense。

## 規則決策
本輪採用的規則是：

### shared 城鎮被瓦解時
- 仍然優先打到「實際擁有該組織的人」
- 不把共享 access 視為憑空複製組織
- 共享只是讓該城鎮可被共享方當成有效起點 / 有效組織 / 有效目標鏈接
- 真正扣掉哪一顆組織，仍由實際 owner 承受

這樣可以保持：
- build / move / victory 的 shared 邏輯一致
- defense ability 也能落在真正該觸發的 owner 身上

## 已完成

### 1. `dissolve_organization()` shared-aware
#### server/game.py
- 以前：
  - 只接受 `defender.organizations[town] > 0`
- 現在：
  - 先找 `target_owner = self._shared_origin_owner(defender, town)`
  - 若 defender 自己沒有，但其共享對象有，仍可找到實際 owner

### 2. 防禦能力改看 `actual owner`
#### server/game.py
- `_can_target_org_with_dissolve(attacker, target_owner, source=...)`
- `盟旗學校` / `殉道者` / `青山里` 都改成以實際被打到的 owner 為準

### 3. dissolve 結果額外帶 metadata
#### server/game.py
成功時會回傳：
- `actual_owner`
- `shared_target`

可供後續 UI / log / debug 使用。

### 4. websocket action 補 `dissolve`
#### server/main.py
- 新增 `action == "dissolve"`
- 允許用 defender name/id + town 呼叫 backend dissolve

## 驗證
新增：
- `scripts/validate_shared_dissolve_phase8.py`

輸出：
- `SHARED_DISSOLVE_PHASE8_VALIDATION.json`
- `SHARED_DISSOLVE_PHASE8_VALIDATION.md`

### 驗證案例 A
- attacker: red_army
- defender: hu
- actual shared owner: taiwan_green
- town: 上海

結果：
- 雖然 defender 傳的是 hu
- 真正被扣掉的是 taiwan_green 在上海的組織
- 驗證通過

### 驗證案例 B
- attacker 無手牌
- defender 傳的是 hu
- actual shared owner: mongol
- town: 上海

結果：
- 仍正確觸發 `盟旗學校`
- 回傳：`盟旗學校：須先棄1張手牌，才可以瓦解蒙古組織`
- 驗證通過

## 結果
- total: 2
- passed: 2
- failed: 0

## 目前尚未完成
- 地圖 / UI 還沒有 shared dissolve 的操作按鈕與高亮
- UI 尚未把 `actual_owner` / `shared_target` 做成玩家可見提示
- 國安部 / 其他直接用 dissolve 的互動前端還沒做專門視覺化驗證
