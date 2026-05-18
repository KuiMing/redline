# 乘勝追擊 UI screenshots（2026-05-18）

目的：用真實 Redline UI 證明 `乘勝追擊` 的 pending card-choice flow 與解析後狀態：打出後從己方棄牌堆列出費用 3 點以下候選牌，選擇 `宣傳家` 後加入手牌，未選牌與 `乘勝追擊` 留在棄牌堆／進入棄牌堆，並寫入戰況紀錄。

## Fixture

- Endpoint：`POST /test/setup-press-advantage-proof`
- 玩家：`viewer`（紅軍，北京） vs `enemy`（香港，香港城）
- 起始手牌：`乘勝追擊`
- 起始棄牌堆：`宣傳家`、`合作談判`、`走漏風聲`
- 預期候選：`宣傳家`、`走漏風聲`
  - `合作談判` 總購買費用為資金 2 + 宣傳 2 = 4，因此不列入 3 點以下候選。

## Screenshots

1. `ACTION_CARD_PRESS_ADVANTAGE_UI_2026_05_18_01_START.png`
   - 起始 command view：回合 1、行動階段、viewer 手牌 1，手牌可見 `乘勝追擊`。

2. `ACTION_CARD_PRESS_ADVANTAGE_UI_2026_05_18_02_CHOICE_MODAL.png`
   - 打出 `乘勝追擊` 後的 `卡牌選擇` modal。
   - Modal 顯示說明：`從己方棄牌堆任選1張費用3點以下的牌加入手牌。`
   - 候選牌包含 `宣傳家` 與 `走漏風聲`，不包含費用 4 的 `合作談判`。

3. `ACTION_CARD_PRESS_ADVANTAGE_UI_2026_05_18_03_AFTER_HAND.png`
   - 選擇 `宣傳家` 解析後回到 command view。
   - viewer 手牌 1，手牌內容變為 `宣傳家`，modal 已關閉。

4. `ACTION_CARD_PRESS_ADVANTAGE_UI_2026_05_18_04_LOG.png`
   - 戰況紀錄 view。
   - viewer 狀態：手牌 1、棄牌 3。
   - viewer 棄牌堆：`合作談判`、`走漏風聲`、`乘勝追擊`。
   - 事件紀錄包含：
     - `viewer may gain 1 eligible card from discard`
     - `viewer played 乘勝追擊`
     - `viewer gained 宣傳家 from discard via 乘勝追擊`

## Browser state evidence

Live UI state after resolving:

```json
{
  "hand": ["宣傳家"],
  "discard": ["合作談判", "走漏風聲", "乘勝追擊"],
  "pending_choice": null,
  "log": [
    "[Turn 1] UI proof setup: viewer has 乘勝追擊; discard pile contains 宣傳家 / 合作談判 / 走漏風聲.",
    "[Turn 1] viewer may gain 1 eligible card from discard",
    "[Turn 1] viewer played 乘勝追擊",
    "[Turn 1] viewer gained 宣傳家 from discard via 乘勝追擊"
  ]
}
```

## Verification

- `python3 scripts/validate_action_card_press_advantage_runtime.py`
- `python3 -m pytest -q scripts/tests/test_action_card_regressions.py -k 'press_advantage'`
- `python3 -m compileall -q server scripts static`
