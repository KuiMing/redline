# BASE_SPECIFIC_ABILITY_UI

日期：2026-05-05

## 問題

像香港這種 faction，能力不只在 faction 本體上，
也可能掛在特定根據地條目內：
- `bases[].abilities`

因此若 UI 只顯示 faction-level `abilities`，
就會漏掉像「香港城」這種根據地專屬能力。

## 本輪修正

### static/app.js
在 `renderFactionDetails()` 中：
- 依 `pendingFactionBaseChoice` 找出當前選中的 `bases[]` 條目
- 將該 base 的 `abilities` 一起併入最終顯示的能力列表

## 效果

### 香港城
- 現在選到 `香港城` 後
- 能力區會正確顯示：
  - `安全屋：建立牆內組織時，可建立組織距離額外增加1格。`

## 驗證

- 截圖：`hong_kong_city_selection_with_ability.png`
