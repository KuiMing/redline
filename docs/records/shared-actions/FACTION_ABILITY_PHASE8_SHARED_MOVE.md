# FACTION_ABILITY_PHASE8_SHARED_MOVE

日期：2026-05-06

## 本輪完成

把共用組織從 shared-aware UI，再往前推到 backend `move_organization()` 規則整合。

## 已完成

### 1. shared origin owner helper
#### server/game.py
- 新增 `_shared_origin_owner(player, town)`
- 用來判斷：
  - 若自己在該 town 有組織，回傳自己
  - 否則若共享對象在該 town 有組織，回傳共享對象 player
  - 否則回傳 `None`

### 2. `_town_has_shared_org_access()` 改走 shared origin owner
#### server/game.py
- 不再重複自己掃一次 shared access
- 直接用 `_shared_origin_owner(...) is not None`

### 3. `build_organization_with_support()` 現在可接受 shared origin
#### server/game.py
- 以前要求 `player.organizations.get(origin_town, 0) > 0`
- 現在改成：
  - `origin_owner = self._shared_origin_owner(player, origin_town)`
- 所以如果起點是共享對象的組織，也可作為 supported build 起點

### 4. `move_organization()` backend shared-aware
#### server/game.py
- 以前要求 current player 自己在 `from_town` 有組織
- 現在改成：
  - `origin_owner = self._shared_origin_owner(player, from_town)`
- 若是 shared origin：
  - 從共享對象的 `from_town` 扣掉 1
  - 在當前玩家的 `to_town` 增加 1
  - moves_left 仍消耗當前玩家的移動點

### 5. 日誌區分 shared move
#### server/game.py
- own move：
  - `moved 1 organization from A to B via road/rail`
- shared move：
  - `moved 1 shared organization from Other:A to B via road/rail`

## 驗證
新增：
- `scripts/validate/validate_shared_move_phase8.py`

輸出：
- `SHARED_MOVE_PHASE8_VALIDATION.json`
- `SHARED_MOVE_PHASE8_VALIDATION.md`

### 驗證案例
- 玩家：香港
- 共享對象：粵
- 粵在 `廣州` 有 1 組織
- 香港自己在 `廣州` 沒有組織
- 香港發動 `move_organization('廣州', '深圳', 'rail')`

### 結果
- success: true
- 粵 `廣州` 組織被扣掉
- 香港 `深圳` 組織 +1
- 驗證通過

## 目前仍未完成
- dissolve 是否允許 shared-origin / shared-defense 進一步整合
- 前端 move error / hint 與 shared backend 規則完全一致化
- 真瀏覽器截圖驗證
