# EXPAND_SEMANTIC_BASE_OPTIONS

日期：2026-05-05

## 本輪修正

根據使用者回饋，像：
- `任意英美城鎮`
- `任意南洋`
- `任意東洋`

這種語義型根據地，不應停在抽象類別按鈕，
而應在第三層繼續展開成具體城市清單。

## 修改內容

### server/main.py
新增：
- `semantic_base_pool(option_name)`
- `faction_base_resolved(by_id, faction_id)`

作用：
- 把 `任意英美城鎮` 解析成：
  - 華盛頓 / 紐約 / 多倫多 / 卡加利 / 溫哥華 / 舊金山 / 洛杉磯 / 倫敦
- 把 `任意南洋` / `任意南洋城鎮` / `任意東洋` 也轉成具體城鎮列表
- `/factions` 現在除了 `base_options` 之外，也會回傳 `base_resolved`

### static/app.js
- 新增 `pendingFactionBaseGroup`
- 第三層 base 選擇現在支援兩段：
  1. 先選根據地類別
  2. 若該類別對應多個具體城鎮，展開城鎮列表
- 加入 `← 返回根據地類別`
- 只有選到具體城鎮後，才算完成 base choice

## 驗證

### 反賊 → 粵 → 任意英美城鎮
- 先出現根據地類別：
  - 廣州
  - 任意南洋
  - 任意英美城鎮
- 點 `任意英美城鎮` 後，展開：
  - 華盛頓
  - 紐約
  - 多倫多
  - 卡加利
  - 溫哥華
  - 舊金山
  - 洛杉磯
  - 倫敦
- 選完具體城鎮（示例：倫敦）後，才顯示 detail panel 與確認按鈕
- 截圖：`rebel_yue_anglo_expanded_ui.png`
