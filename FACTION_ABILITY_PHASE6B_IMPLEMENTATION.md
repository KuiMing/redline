# FACTION_ABILITY_PHASE6B_IMPLEMENTATION

日期：2026-05-06

## 本輪完成的 phase6b 補強

在 phase6 第一版的基礎上，進一步補上：

### 1. 共用組織名稱對映
`shared_organizations_with` 原始資料中有些是中文名稱，
而 engine 內部使用的是 faction id。

這一輪新增：
- `_canonical_faction_name_to_id(name)`

可把常見中文名稱映射成 faction id，例如：
- 地下教會 → `underground_church`
- 性別革命 → `gender_revolution`
- 客家 → `hakka`
- 潮汕 → `chaoshan`
- 閩 → `min`
- 吳越 → `wuyue`
- 滇 → `dian`
- 粵 → `yue`
- 澳門 → `aomen`
- 綠線臺灣 → `taiwan_green`
- 藍線臺灣 → `taiwan_blue`
- 民國派 → `republican`

### 2. 共用組織計數（第一版）
新增：
- `_shared_org_count(player, town)`

作用：
- 回傳某玩家在指定城鎮可計入的共享組織總數
- 目前是控制 / 勝利條件整合前的第一版輔助函式

## 驗證
新增：
- `scripts/validate_shared_org_count_phase6b.py`

輸出：
- `SHARED_ORG_COUNT_PHASE6B_VALIDATION.json`
- `SHARED_ORG_COUNT_PHASE6B_VALIDATION.md`

### 驗證結果
以：
- `taiwan_green`
- `underground_church`

在 `北京` 的共享組織為例：
- `count_tw = 5`
- `count_church = 5`
- 驗證通過

## 意義
這表示共享組織不只可作為建立據點，
現在也開始有可供後續控制 / 勝利條件整合使用的計數基礎。
