# Action Card Armed Series Runtime Validation

Generated at: `2026-05-18T12:47:27`

Summary: 3 passed / 0 failed / 3 total.

## Scope
- 武裝者：指定 1 格內有組織的對手，目標玩家自選棄 1 張牌。
- 武裝小隊：指定 1 格內有組織的對手，目標玩家自選棄 2 張牌。
- 武裝集團：指定 1 格內有組織的對手，目標玩家自選棄 2 張牌；成功棄牌後，出牌者抽 1 張牌。

## 武裝者 — passed

- Play result: `{'success': True, 'pending_choice': True}`
- Resolve result: `{'success': True, 'discarded_card': 'Enemy1', 'target_player_name': 'P2', 'initiator_player_name': 'P1', 'choice_key': 'armed_target_discard'}`
- Before: P2 hand `['Enemy1', 'Enemy2']`, P2 discard `[]`, P1 hand `['武裝者']`
- Pending: `{'type': 'card_choice', 'choice_key': 'armed_target_discard', 'player_id': 'p2', 'count': None, 'cards': ['Enemy1', 'Enemy2'], 'prompt': '武裝者：從所有手牌中棄掉任1張牌。'}`
- After: P2 hand `['Enemy2']`, P2 discard `['Enemy1']`, P1 hand `[]`, turn_log `{'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': True, 'built_towns': [], 'played_nonstarter_names': ['武裝者'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': [], 'reaction_prompted_player_ids': []}`
- Action log tail: `['[Turn 1] P1 used 武裝者 to ask P2 to choose 1 discard(s)', '[Turn 1] P1 played 武裝者', '[Turn 1] P1 used 武裝者 to force P2 to discard Enemy1']`

## 武裝小隊 — passed

- Play result: `{'success': True, 'pending_choice': True}`
- Resolve result: `{'success': True, 'chosen_cards': ['Enemy1', 'Enemy3'], 'target_player_name': 'P2', 'initiator_player_name': 'P1', 'choice_key': 'armed_target_discard'}`
- Before: P2 hand `['Enemy1', 'Enemy2', 'Enemy3']`, P2 discard `[]`, P1 hand `['武裝小隊']`
- Pending: `{'type': 'multi_card_choice', 'choice_key': 'armed_target_discard', 'player_id': 'p2', 'count': 2, 'cards': ['Enemy1', 'Enemy2', 'Enemy3'], 'prompt': '武裝小隊：從所有手牌中棄掉任2張牌。'}`
- After: P2 hand `['Enemy2']`, P2 discard `['Enemy1', 'Enemy3']`, P1 hand `[]`, turn_log `{'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': True, 'built_towns': [], 'played_nonstarter_names': ['武裝小隊'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': [], 'reaction_prompted_player_ids': []}`
- Action log tail: `['[Turn 1] P1 used 武裝小隊 to ask P2 to choose 2 discard(s)', '[Turn 1] P1 played 武裝小隊', '[Turn 1] P1 used 武裝小隊 to force P2 to discard 2 card(s)']`

## 武裝集團 — passed

- Play result: `{'success': True, 'pending_choice': True}`
- Resolve result: `{'success': True, 'chosen_cards': ['Enemy1', 'Enemy2'], 'target_player_name': 'P2', 'initiator_player_name': 'P1', 'choice_key': 'armed_target_discard'}`
- Before: P2 hand `['Enemy1', 'Enemy2']`, P2 discard `[]`, P1 hand `['武裝集團']`
- Pending: `{'type': 'multi_card_choice', 'choice_key': 'armed_target_discard', 'player_id': 'p2', 'count': 2, 'cards': ['Enemy1', 'Enemy2'], 'prompt': '武裝集團：從所有手牌中棄掉任2張牌。'}`
- After: P2 hand `[]`, P2 discard `['Enemy1', 'Enemy2']`, P1 hand `['RewardDraw']`, turn_log `{'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': True, 'built_towns': [], 'played_nonstarter_names': ['武裝集團'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': [], 'reaction_prompted_player_ids': []}`
- Action log tail: `['[Turn 1] P1 used 武裝集團 to ask P2 to choose 2 discard(s)', '[Turn 1] P1 played 武裝集團', '[Turn 1] P1 used 武裝集團 to force P2 to discard 2 card(s)']`
