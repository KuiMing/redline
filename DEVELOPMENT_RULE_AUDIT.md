# DEVELOPMENT_RULE_AUDIT

日期：2026-05-03

## 你補充的規則

- 所有陣營都只能在有標示自己陣營的城鎮發展組織。
- 如果城鎮沒有標示任何陣營，則除了紅軍以外的陣營都能在該城鎮發展組織。
- 紅軍只能在陣營清單有 `紅軍` 的城鎮發展組織。

## 本輪已落實到程式的地方

### `server/game.py`
新增：
- `_camp_token_for_faction_id()`
- `_camp_token_for_player()`
- `can_faction_develop_in_town(faction_id, town)`
- `can_develop_in_town(player, town)`

### 規則邏輯

#### 非紅軍
可在：
1. `camp` 包含自己陣營 token 的城鎮
2. `camp` 為空的城鎮

#### 紅軍
只可在：
1. `camp` 明確包含 `紅軍` 的城鎮

不可因 `camp` 為空而發展。

## 已接上的流程

### 1. 根據地初始化
- `_assign_starting_bases()` 現在會用 `can_faction_develop_in_town()` 檢查候選根據地是否合法
- 並額外保留固定根據地，避免被 flex/candidate faction 搶走

### 2. 一般 build
- `build_organization()` 現在會檢查 `can_develop_in_town()`
- 不合法時回：`Cannot develop in this town`

### 3. 卡牌 build effect
- `EffectEngine` 的 `build` 現在只會在合法城鎮發展

## 驗證結果

### 紅軍
- `can_develop_in_town(red, 空白 camp 城鎮)` → False
- `can_develop_in_town(red, camp 含紅軍城鎮)` → True
- `can_develop_in_town(red, 非紅軍 camp 城鎮)` → False

### 非紅軍
- `can_develop_in_town(non_red, 空白 camp 城鎮)` → True
- `can_develop_in_town(non_red, 自身合法根據地)` → True

## 重要補充

為了讓單一正式根據地初始化仍正確：
- 固定唯一根據地（例如紅軍北京）現在會先被 reserve
- flex/candidate faction 不會先搶走其他 faction 的固定根據地

## 回歸驗證

已重新跑：
- `FULL_GAMEPLAY_2P_VALIDATION`
- `FULL_GAMEPLAY_3P_VALIDATION`
- `FULL_GAMEPLAY_4P_VALIDATION`

目前在這條新規則下，2 / 3 / 4 人完整流程驗證仍可跑通。
