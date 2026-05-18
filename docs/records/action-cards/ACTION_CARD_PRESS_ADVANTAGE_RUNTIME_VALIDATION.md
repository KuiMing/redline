# Action Card Press Advantage Runtime Validation

Generated at: `2026-05-18T14:23:01`

Summary: 1 passed / 0 failed / 1 total.

## Scope
- 乘勝追擊：從己方棄牌堆任選 1 張總費用 3 點以下的牌加入手牌。
- 總費用以資金費用 + 宣傳費用計算；本驗證同時放入總費用 3、2 的 eligible 卡，以及總費用 4 的 ineligible 卡。
- 驗證 pending choice 候選清單、選牌解析後的手牌／棄牌堆、以及 action log。

## 乘勝追擊 — passed

- Play result: `{'success': True, 'pending_choice': True}`
- Resolve result: `{'success': True, 'chosen_card': '走漏風聲'}`
- Before: hand `['乘勝追擊']`, discard `['宣傳家', '合作談判', '走漏風聲']`
- Pending: `{'type': 'card_choice', 'choice_key': 'gain_from_discard', 'player_id': 'p1', 'source_name': '乘勝追擊', 'max_cost': 3, 'cards': ['宣傳家', '走漏風聲'], 'prompt': '從己方棄牌堆任選1張費用3點以下的牌加入手牌。'}`, discard `['宣傳家', '合作談判', '走漏風聲', '乘勝追擊']`
- After: hand `['走漏風聲']`, discard `['宣傳家', '合作談判', '乘勝追擊']`
- Action log tail: `['[Turn 1] P1 may gain 1 eligible card from discard', '[Turn 1] P1 played 乘勝追擊', '[Turn 1] P1 gained 走漏風聲 from discard via 乘勝追擊']`
