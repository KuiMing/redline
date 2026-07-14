# Action Card End-Turn Topdeck Runtime Validation

Generated at: `2026-07-14T10:20:42`

Summary: 3 passed / 0 failed / 3 total.

## Scope
- 回合 END 階段進入真正結束回合前，若玩家手上有 `行動預告` / `行動募資` 且本回合購得的牌仍在棄牌堆，先提示可使用。
- 選擇使用後，該行動卡把本回合購得牌置頂；同一次 end-turn 補牌會把該購得牌抽入手牌。
- 玩家也可以選擇不使用，購得牌維持在棄牌堆。

## 行動預告_end_turn_use — passed

- Prompt result: `{'success': True, 'pending_choice': True}`
- Resolve result: `{'success': True, 'choice_index': 1, 'chosen_card': '行動預告'}`
- Before: `{'turn_phase': <TurnPhase.END: 'end'>, 'current_player': 'P1', 'hand': ['行動預告', 'Filler'], 'draw_pile': ['Bottom1', 'Bottom2', 'Bottom3', 'Bottom4', 'Bottom5'], 'discard_pile': ['PurchasedCard'], 'turn_log': {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': [], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'red_army_action_count': 0, 'red_army_targeted_actions': {}, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': ['PurchasedCard'], 'reaction_prompted_player_ids': [], 'red_army_base_dissolves': {}}, 'pending_choice': None, 'action_log_tail': ['[Turn 1] Event drawn: 一帶一路 南洋 (auto deferred)']}`
- Prompted: `{'type': 'option_choice', 'choice_key': 'end_turn_topdeck_action', 'player_id': 'p1', 'prompt': '回合結束前：你本回合有購得的牌，可使用行動預告／行動募資將其中 1 張置於牌庫頂，接著補牌時抽上手。', 'options': [{'label': '不使用', 'action': 'skip'}, {'label': '使用 行動預告', 'action': 'use', 'card_name': '行動預告', 'hand_index': 0}]}`
- After: `{'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player': 'P1', 'hand': ['Filler', 'PurchasedCard', 'Bottom5', 'Bottom4', 'Bottom3'], 'draw_pile': ['Bottom1', 'Bottom2'], 'discard_pile': ['行動預告'], 'turn_log': {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': [], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'red_army_action_count': 0, 'red_army_targeted_actions': {}, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': [], 'reaction_prompted_player_ids': [], 'red_army_base_dissolves': {}}, 'pending_choice': None, 'action_log_tail': ['[Turn 1] Event drawn: 一帶一路 南洋 (auto deferred)', '[Turn 1] P1 may use 行動預告/行動募資 before drawing new hand', '[Turn 1] P1 placed bought card PurchasedCard on deck top', '[Turn 1] P1 used 行動預告 before drawing new hand', '[Turn 1] End of turn for P1']}`

## 行動募資_end_turn_use — passed

- Prompt result: `{'success': True, 'pending_choice': True}`
- Resolve result: `{'success': True, 'choice_index': 1, 'chosen_card': '行動募資'}`
- Before: `{'turn_phase': <TurnPhase.END: 'end'>, 'current_player': 'P1', 'hand': ['行動募資', 'Filler'], 'draw_pile': ['Bottom1', 'Bottom2', 'Bottom3', 'Bottom4', 'Bottom5'], 'discard_pile': ['PurchasedCard'], 'turn_log': {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': [], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'red_army_action_count': 0, 'red_army_targeted_actions': {}, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': ['PurchasedCard'], 'reaction_prompted_player_ids': [], 'red_army_base_dissolves': {}}, 'pending_choice': None, 'action_log_tail': []}`
- Prompted: `{'type': 'option_choice', 'choice_key': 'end_turn_topdeck_action', 'player_id': 'p1', 'prompt': '回合結束前：你本回合有購得的牌，可使用行動預告／行動募資將其中 1 張置於牌庫頂，接著補牌時抽上手。', 'options': [{'label': '不使用', 'action': 'skip'}, {'label': '使用 行動募資', 'action': 'use', 'card_name': '行動募資', 'hand_index': 0}]}`
- After: `{'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player': 'P1', 'hand': ['Filler', 'PurchasedCard', 'Bottom5', 'Bottom4', 'Bottom3'], 'draw_pile': ['Bottom1', 'Bottom2'], 'discard_pile': ['行動募資'], 'turn_log': {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': [], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'red_army_action_count': 0, 'red_army_targeted_actions': {}, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': [], 'reaction_prompted_player_ids': [], 'red_army_base_dissolves': {}}, 'pending_choice': None, 'action_log_tail': ['[Turn 1] P1 may use 行動預告/行動募資 before drawing new hand', '[Turn 1] P1 placed bought card PurchasedCard on deck top', '[Turn 1] P1 used 行動募資 before drawing new hand', '[Turn 1] End of turn for P1', '[Turn 1] Event drawn: 全國人大召開']}`

## skip_end_turn_prompt — passed

- Prompt result: `{'success': True, 'pending_choice': True}`
- Resolve result: `{'success': True, 'choice_index': 0, 'skipped': True}`
- Before: `{'turn_phase': <TurnPhase.END: 'end'>, 'current_player': 'P1', 'hand': ['行動募資'], 'draw_pile': ['Draw1', 'Draw2', 'Draw3', 'Draw4', 'Draw5'], 'discard_pile': ['PurchasedCard'], 'turn_log': {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': [], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'red_army_action_count': 0, 'red_army_targeted_actions': {}, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': ['PurchasedCard'], 'reaction_prompted_player_ids': [], 'red_army_base_dissolves': {}}, 'pending_choice': None, 'action_log_tail': []}`
- Prompted: `{'type': 'option_choice', 'choice_key': 'end_turn_topdeck_action', 'player_id': 'p1', 'prompt': '回合結束前：你本回合有購得的牌，可使用行動預告／行動募資將其中 1 張置於牌庫頂，接著補牌時抽上手。', 'options': [{'label': '不使用', 'action': 'skip'}, {'label': '使用 行動募資', 'action': 'use', 'card_name': '行動募資', 'hand_index': 0}]}`
- After: `{'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player': 'P1', 'hand': ['行動募資', 'Draw5', 'Draw4', 'Draw3', 'Draw2'], 'draw_pile': ['Draw1'], 'discard_pile': ['PurchasedCard'], 'turn_log': {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': [], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'red_army_action_count': 0, 'red_army_targeted_actions': {}, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': [], 'reaction_prompted_player_ids': [], 'red_army_base_dissolves': {}}, 'pending_choice': None, 'action_log_tail': ['[Turn 1] P1 may use 行動預告/行動募資 before drawing new hand', '[Turn 1] P1 skipped end-turn action topdeck prompt', '[Turn 1] End of turn for P1', '[Turn 1] Event drawn: 一帶一路 南洋 (auto deferred)']}`
