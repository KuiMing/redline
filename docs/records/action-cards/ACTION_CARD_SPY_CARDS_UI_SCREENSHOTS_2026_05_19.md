# 派遣間諜／內應間諜 UI proof（2026-05-19）

## 範圍
- `派遣間諜`：兩段式互動，先瓦解己方組織，再選該組織 1 格內敵方組織瓦解。
- `內應間諜`：不犧牲己方組織，直接選己方組織 1 格內敵方組織瓦解。

## 測試場景
- Fixture：`POST /test/setup-spy-proof`
- 派遣間諜預設場景：
  - viewer 手牌：`派遣間諜`
  - viewer 組織：`北京`、`上海`
  - enemy 組織：`天津`、`杭州`、`香港城`
- 內應間諜預設場景：
  - viewer 手牌：`內應間諜`
  - viewer 組織：`北京`
  - enemy 組織：`天津`、`香港城`

## 派遣間諜 proof

### 1. 起始狀態
- 截圖：`ACTION_CARD_SPY_CARDS_UI_2026_05_19_01_FIELD_AGENT_START.png`
- 證明：第 1 回合行動階段，viewer 手牌 1 張為 `派遣間諜`，viewer 組織 2，enemy 組織 3。

### 2. 第一段：選己方犧牲組織
- 截圖：`ACTION_CARD_SPY_CARDS_UI_2026_05_19_02_FIELD_AGENT_SACRIFICE_MODAL.png`
- Modal prompt：`派遣間諜：先選擇 1 個要瓦解的己方組織。`
- 可選項：
  - `北京｜北京（可瓦解鄰近敵方組織）`
  - `上海｜上海（可瓦解鄰近敵方組織）`

### 3. 第二段：選被犧牲組織 1 格內敵方目標
- 截圖：`ACTION_CARD_SPY_CARDS_UI_2026_05_19_03_FIELD_AGENT_TARGET_MODAL.png`
- 選擇 `上海` 後，viewer 組織數從 2 降為 1。
- Modal prompt：`派遣間諜：選擇 上海 1 格內的 1 個敵方組織瓦解。`
- 可選目標只剩：`enemy｜杭州`。

### 4. 完成後狀態
- 截圖：`ACTION_CARD_SPY_CARDS_UI_2026_05_19_04_FIELD_AGENT_AFTER.png`
- 證明：viewer 組織 1，enemy 組織 2；代表己方 `上海` 與敵方 `杭州` 已瓦解。

### 5. 戰況紀錄
- 截圖：`ACTION_CARD_SPY_CARDS_UI_2026_05_19_05_FIELD_AGENT_LOG.png`
- Log 證據：
  - `[Turn 1] viewer played 派遣間諜`
  - `[Turn 1] viewer dissolved 1 own organization at 上海 for 派遣間諜`
  - `[Turn 1] viewer dissolved 1 organization from enemy at 杭州`

## 內應間諜 proof

### 1. 起始狀態
- 截圖：`ACTION_CARD_SPY_CARDS_UI_2026_05_19_06_EMBEDDED_AGENT_START.png`
- 證明：第 1 回合行動階段，viewer 手牌 1 張為 `內應間諜`，viewer 組織 1，enemy 組織 2。

### 2. 目標選擇 modal
- 截圖：`ACTION_CARD_SPY_CARDS_UI_2026_05_19_07_EMBEDDED_AGENT_TARGET_MODAL.png`
- Modal prompt：`內應間諜：選擇 1 個要瓦解的鄰近敵方組織。`
- 沒有己方犧牲步驟。
- 可選目標只列出：`enemy｜天津`。

### 3. 完成後狀態
- 截圖：`ACTION_CARD_SPY_CARDS_UI_2026_05_19_08_EMBEDDED_AGENT_AFTER.png`
- 證明：viewer 組織仍為 1，enemy 組織降為 1；代表沒有犧牲己方組織，敵方 `天津` 已瓦解。

### 4. 戰況紀錄
- 截圖：`ACTION_CARD_SPY_CARDS_UI_2026_05_19_09_EMBEDDED_AGENT_LOG.png`
- Log 證據：
  - `[Turn 1] viewer played 內應間諜`
  - `[Turn 1] viewer dissolved 1 organization from enemy at 天津`
- 沒有 `own organization` / 己方犧牲紀錄。

## 回歸測試
- `scripts/tests/test_action_card_regressions.py`
  - `test_field_agent_requires_target_org_within_one_step_of_sacrificed_org`
  - `test_field_agent_prompts_sacrifice_then_target_org_like_north_support`
  - `test_embedded_agent_requires_target_org_within_one_step_of_own_org`
  - `test_embedded_agent_prompts_exact_in_range_target_org_without_self_sacrifice`

## 驗證指令
```bash
python3 -m pytest -q scripts/tests/test_action_card_regressions.py -k 'field_agent or embedded_agent or support'
python3 -m compileall -q server scripts static
git diff --check
```
