# RESOLVE_ABILITY_REFS_FOR_UI

日期：2026-05-05

## 問題

有些 faction 的能力在資料中是以：
- `{"ref": "combo_three_unique"}`

這種 reference 形式存在。

因此 UI 若只直接渲染 faction 本身的 `abilities`，
就可能出現：
- 沒有能力描述
- 或只有空白 / 不完整資訊

## 本輪修正

### server/main.py
在 `/factions` 中新增：
- `ability_templates = data.get("ability_templates", {})`
- `resolve_ui_faction(faction)`

作用：
- 將 faction 內 `abilities` 中的 `ref` 先展開成完整能力描述
- 若有 `name_override`，則覆蓋模板名稱
- 讓前端直接拿到可顯示的完整能力資料

## 效果

像滿洲原本：
- `{"ref": "combo_three_unique"}`

現在會先被展開成：
- `展現實力：在己方行動階段打出至少3張不同名稱的非起始牌，獲得3點宣傳或3點資金。`

## 驗證

### 滿洲
- 修正前：能力區可能為空
- 修正後：選完根據地後會顯示完整能力描述
- 截圖：`manchuria_ability_fixed_ui.png`
