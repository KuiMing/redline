# 網羅人才 UI Screenshot Proof — 2026-05-18

## Scope

驗證 Action 卡 `網羅人才` 的真實 UI 流程，包含一般版本與紅軍特例：

- 一般版本：從己方牌庫任選 1 張牌加入手牌，然後洗牌。
- 紅軍特例：從己方牌庫或棄牌堆任選 1 張牌加入手牌，然後洗牌。
- UI contract：打出後出現 `card_choice` / `recruit_talent` 選牌 modal，解析後清掉 pending choice，選中牌進入手牌，`網羅人才` 進入棄牌堆。

## General setup

Fixture endpoint：`POST /test/setup-recruit-talent-proof`

一般版本固定狀態：

- viewer faction/base：`tibet_dehradun` / `德拉敦`
- turn phase：`action`
- viewer resources：`資金 4` / `宣傳 4`
- viewer hand：`網羅人才`
- viewer deck draw pile：`宣傳家` / `合作談判` / `走漏風聲`
- viewer discard pile：`棄牌見證`

## General screenshot evidence

1. `ACTION_CARD_RECRUIT_TALENT_UI_2026_05_18_01_START.png`
   - 顯示 action phase、viewer hand count 1、資金 4 / 宣傳 4。
   - 手牌區只有 `網羅人才`，且有 `資源` / `行動` 按鈕。

2. `ACTION_CARD_RECRUIT_TALENT_UI_2026_05_18_02_CHOICE_MODAL.png`
   - 打出 `網羅人才` 後顯示 `卡牌選擇` modal。
   - modal key 顯示 `recruit_talent`。
   - prompt 顯示：`網羅人才：從己方牌庫任選1張加入手牌，而後將牌庫洗牌。`
   - 候選卡列出 `宣傳家` / `合作談判` / `走漏風聲`。

3. `ACTION_CARD_RECRUIT_TALENT_UI_2026_05_18_03_AFTER_HAND.png`
   - 選 `合作談判` 後 modal 關閉。
   - 上方狀態顯示 hand count 1。
   - 手牌區顯示 `合作談判`。

4. `ACTION_CARD_RECRUIT_TALENT_UI_2026_05_18_04_LOG.png`
   - 戰況總覽中 viewer discard pile 顯示 `棄牌見證` / `網羅人才`。
   - 事件紀錄包含：
     - `[Turn 1] viewer may recruit 1 card from deck`
     - `[Turn 1] viewer played 網羅人才`
     - `[Turn 1] viewer recruited 合作談判 from deck`

## Red Army setup

紅軍特例 fixture payload：

```json
{"faction_id":"red_army","deck_names":["宣傳家","走漏風聲"],"discard_names":["合作談判"]}
```

固定狀態：

- viewer faction/base：`red_army` / `北京`
- turn phase：`action`
- viewer resources：`資金 4` / `宣傳 4`
- viewer hand：`網羅人才`
- viewer deck draw pile：`宣傳家` / `走漏風聲`
- viewer discard pile：`合作談判`

## Red Army screenshot evidence

1. `ACTION_CARD_RECRUIT_TALENT_RED_ARMY_UI_2026_05_18_01_START.png`
   - 顯示 action phase、viewer hand count 1、資金 4 / 宣傳 4。
   - 手牌區只有 `網羅人才`。
   - console state 驗證 viewer faction/base 為 `red_army` / `北京`。

2. `ACTION_CARD_RECRUIT_TALENT_RED_ARMY_UI_2026_05_18_02_CHOICE_MODAL.png`
   - 打出 `網羅人才` 後顯示 `卡牌選擇` modal。
   - modal key 顯示 `recruit_talent`。
   - 候選卡同時包含牌庫的 `宣傳家` / `走漏風聲` 與棄牌堆的 `合作談判`。

3. `ACTION_CARD_RECRUIT_TALENT_RED_ARMY_UI_2026_05_18_03_AFTER_HAND.png`
   - 選棄牌堆來源的 `合作談判` 後 modal 關閉。
   - 手牌區顯示 `合作談判`。

4. `ACTION_CARD_RECRUIT_TALENT_RED_ARMY_UI_2026_05_18_04_LOG.png`
   - 戰況總覽明確顯示 viewer：`陣營：紅軍`、`根據地：北京`。
   - viewer discard pile 只剩 `網羅人才`，表示 `合作談判` 已從棄牌堆移入手牌。
   - 事件紀錄包含：
     - `[Turn 1] UI proof setup: viewer has 網羅人才; deck/discard choices include 宣傳家 / 走漏風聲 / 合作談判.`
     - `[Turn 1] viewer may recruit 1 card from deck`
     - `[Turn 1] viewer played 網羅人才`
     - `[Turn 1] viewer recruited 合作談判 from deck`

## Structured browser state evidence

一般版本選 `合作談判` 後 browser console 驗證：

```text
pending_choice: null
hand: ['合作談判']
draw_pile: []
discard_pile: ['棄牌見證', '網羅人才']
action_log last entries:
- [Turn 1] UI proof setup: viewer has 網羅人才; deck choices include 宣傳家 / 合作談判 / 走漏風聲.
- [Turn 1] viewer may recruit 1 card from deck
- [Turn 1] viewer played 網羅人才
- [Turn 1] viewer recruited 合作談判 from deck
```

紅軍版本選棄牌堆 `合作談判` 後 browser console 驗證：

```text
pending_choice: null
faction: red_army
base: 北京
hand: ['合作談判']
draw_pile: []
discard_pile: ['網羅人才']
action_log last entries:
- [Turn 1] UI proof setup: viewer has 網羅人才; deck/discard choices include 宣傳家 / 走漏風聲 / 合作談判.
- [Turn 1] viewer may recruit 1 card from deck
- [Turn 1] viewer played 網羅人才
- [Turn 1] viewer recruited 合作談判 from deck
```

## Verification commands

```bash
python3 -m compileall -q server/main.py
python3 -m pytest -q scripts/tests/test_action_card_regressions.py -k 'recruit_talent or recruit'
python3 -m compileall -q server scripts static
python3 - <<'PY'
from pathlib import Path
import struct
patterns = [
    'ACTION_CARD_RECRUIT_TALENT_UI_2026_05_18_*.png',
    'ACTION_CARD_RECRUIT_TALENT_RED_ARMY_UI_2026_05_18_*.png',
]
for pattern in patterns:
    files = sorted(Path('docs/records/action-cards').glob(pattern))
    assert len(files) == 4, (pattern, files)
    for p in files:
        data = p.read_bytes()
        assert data.startswith(b'\x89PNG\r\n\x1a\n'), p
        w, h = struct.unpack('>II', data[16:24])
        assert w > 0 and h > 0, p
        print(f'{p.name}: {w}x{h}, {p.stat().st_size} bytes')
PY
git diff --check
```
