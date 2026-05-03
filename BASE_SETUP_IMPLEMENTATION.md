# BASE_SETUP_IMPLEMENTATION

日期：2026-05-03

## 本輪已完成

已將 `server/game.py` 的開局根據地建立流程，從測試期硬塞邏輯改成依 faction `bases` 資料建立。

## 主要變更

### 舊邏輯
- `Game._seed_starting_positions()`
- 使用 `preferred` + `fallback_cycle`
- 每個玩家直接取得 2 個起始城鎮
- `base = assigned[0]`

### 新邏輯
- `Game._assign_starting_bases()`
- 根據 faction `bases` 欄位決定開局根據地
- 每個玩家開局只建立 **1 個** 根據地組織
- 紅軍最後建立根據地

## 目前處理方式

### 1. 固定唯一根據地
- 直接使用唯一 fixed base
- 例：紅軍 → 北京，維吾爾伊斯坦堡 → 伊斯坦堡

### 2. 多候選固定根據地
- 目前採用 deterministic 規則：選第一個尚未被占用、且存在於地圖中的候選城鎮
- 不再 fallback 到與 faction 無關的任意城鎮

### 3. flex / 特殊根據地
- 目前對 `任意牆內 / 任意英美城鎮 / 任意南洋 / 任意東洋` 做 deterministic pool 選擇
- 香港先以 `香港城` 作為開局根據地初始化（遷移規則仍待後續產品化）

## 與規則相比的狀態

### 已修正
- 不再給每個玩家兩個起始城鎮
- 根據地建立不再靠 `fallback_cycle`
- `Player.base` 現在與 faction `bases` 正式對齊

### 尚未完全產品化
- 多候選根據地目前仍是 deterministic 自動選擇，不是玩家互動選擇
- `flex_base` faction 仍未有 UI 選擇流程
- 香港根據地遷移規則尚未做成完整互動流程

## 驗證結果

重新執行 `FULL_GAMEPLAY_2P_VALIDATION` 後：
- 開局已不再是雙城鎮硬塞
- 範例驗證中：
  - host（red_army）→ 北京
  - guest（uyghur_munich）→ 慕尼黑
- 2 人完整流程仍可跑通到 victory / finished
