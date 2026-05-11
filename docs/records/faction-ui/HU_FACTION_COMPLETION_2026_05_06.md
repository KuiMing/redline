# HU_FACTION_COMPLETION_2026_05_06

日期：2026-05-06

## 背景
使用者補充了反賊陣營「滬」的權威規則：
- 【商貿組織】當您每回合第1次打出購買費用含資金的牌時，抽1張牌。
- 遊戲過程中可與綠線臺灣共用組織。
- 勝利條件：回合結束時在牆內與牆外共擁有至少13個有效組織，其中必須包含上海。

## 本輪完成

### 1. 補齊滬 faction runtime 結構
#### data/factions/all_faction.integrated.v2.json
#### data/factions/all_faction.json
- 為 `hu` 補上：
  - `shared_organizations_with: ["綠線臺灣"]`
  - 結構化 `win_conditions`
  - `tags: ["engine", "money", "draw", "shared_org"]`
- 保留原本卡面權威文字：
  - `abilities_text`
  - `special_rules`
  - `win_condition_text`

### 2. 補齊綠線臺灣 reciprocal shared list
#### data/factions/all_faction.integrated.v2.json
#### data/factions/all_faction.json
- `taiwan_green.shared_organizations_with` 追加：
  - `滬`

### 3. 補齊 runtime 中文名稱映射
#### server/game.py
- `_canonical_faction_name_to_id()` 新增：
  - `滬 -> hu`

### 4. 修正 victory 對「牆內與牆外」的 shared counting 範圍
#### server/victory.py
- `_count_scope()` 原本只會掃 `player.organizations.keys()`
- 這會漏掉「只存在於共享對象那邊」的必要城市
- 現在改成掃整局 `all_org_towns`

這讓像 `hu` 這種：
- 自己主體組織在牆外
- 但靠綠線臺灣共享到 `上海`
的情境，可以正確計入勝利條件。

## 驗證
新增：
- `scripts/validate_hu_shared_and_win.py`

輸出：
- `HU_SHARED_AND_WIN_VALIDATION.json`
- `HU_SHARED_AND_WIN_VALIDATION.md`

### 驗證案例
- `taiwan_green` 在上海有 1 組織、北京有 2 組織
- `hu` 在紐約有 10 組織

### 期望
- `hu` 可共享 `taiwan_green`
- `hu` 對上海具有 shared access
- `hu` 在上海的 shared count = 1
- `hu` 達成 13 組織且包含上海，勝利成立

### 結果
- total: 4
- passed: 4
- failed: 0
