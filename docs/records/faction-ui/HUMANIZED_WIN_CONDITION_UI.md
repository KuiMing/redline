# HUMANIZED_WIN_CONDITION_UI

日期：2026-05-05

## 本輪修正

根據使用者回饋，faction detail panel 中的獲勝條件不應直接顯示 JSON 結構，
而應轉成玩家能直接閱讀的自然語句。

## 修改內容

### static/app.js
新增：
- `humanizeWinCondition(w)`

目前已支援的結構化勝利條件類型：
- `count_only`
  - 轉為：`回合結束時在牆內擁有至少 14 個有效組織。`
- `count_and_required`
  - 轉為：`回合結束時在牆內與牆外擁有至少 X 個有效組織，且必須包含 A、B、C。`
- `default_survival`
  - 直接使用文字
- `taiwan_override`
  - 直接使用文字

### renderFactionDetails()
- `win_conditions` 現在改為先經過 `humanizeWinCondition()` 再渲染
- 不再直接 fallback 成 JSON 字串

## 驗證

### 維吾爾（慕尼黑）
- 原本會顯示 raw object / JSON 風格內容
- 現在顯示：
  - `回合結束時在牆內擁有至少 14 個有效組織。`
- 截圖：`uyghur_humanized_win_ui.png`
