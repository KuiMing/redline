# 紅軍結束回合：單張棄牌洗牌驗證

- 結果：2/2 passed
- 規則：只有補牌過程耗盡牌庫時，才將棄牌堆洗成新牌庫。

## sufficient
- PASS：True
- Before：`{'hand': ['保留手牌1', '保留手牌2', '保留手牌3', '保留手牌4'], 'deck_count': 1, 'discard_count': 1, 'discard_pile': ['棄牌唯一一張']}`
- After：`{'hand': ['保留手牌1', '保留手牌2', '保留手牌3', '保留手牌4', '牌庫保留牌'], 'deck_count': 0, 'discard_count': 1, 'discard_pile': ['棄牌唯一一張']}`
- Screenshot：`/Users/benmini/.openclaw/workspace/redline/docs/records/deck-lifecycle/RED_END_TURN_SINGLE_DISCARD_SUFFICIENT.png`

## exhausted
- PASS：True
- Before：`{'hand': ['保留手牌1', '保留手牌2', '保留手牌3', '保留手牌4'], 'deck_count': 0, 'discard_count': 1, 'discard_pile': ['棄牌唯一一張']}`
- After：`{'hand': ['保留手牌1', '保留手牌2', '保留手牌3', '保留手牌4', '棄牌唯一一張'], 'deck_count': 0, 'discard_count': 0, 'discard_pile': []}`
- Screenshot：`/Users/benmini/.openclaw/workspace/redline/docs/records/deck-lifecycle/RED_END_TURN_SINGLE_DISCARD_EXHAUSTED.png`
