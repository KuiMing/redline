# CARD VALIDATION RESULTS

日期：2026-05-03

總卡數：44

## 宣傳家 (propaganda)
- effects: optional_trash, build, move
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 2 → 2
- moves_left before → after: 3 → 4
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 2, '上海': 1}
- discard after: ['棄牌A', '棄牌B']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': True, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['宣傳家'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': [], 'faction_first_propaganda_triggered': True}
- log tail: ['[Turn 1] player1 built organization in 北京 via card effect', '[Turn 1] player1 triggered 星星之火 and drew 1 card', '[Turn 1] player1 played 宣傳家']

## 思想家 (propaganda)
- effects: optional_trash, build, move
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 2 → 1
- moves_left before → after: 3 → 6
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 2, '上海': 1}
- discard after: ['棄牌A', '棄牌B']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': True, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['思想家'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 removed 思想家 and it returned to static_supply', '[Turn 1] player1 built organization in 北京 via card effect', '[Turn 1] player1 played 思想家']

## 資助者 (money)
- effects: optional_trash, gain_resource
- checks: play_success, card_left_hand
- resources delta: money 2, propaganda 2
- hand before → after: 2 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': True, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['資助者'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] 資助者 returned to static purchase supply', '[Turn 1] player1 removed 資助者 and it returned to static_supply', '[Turn 1] player1 played 資助者']

## 資本家 (money)
- effects: optional_trash, gain_resource
- checks: play_success, card_left_hand
- resources delta: money 3, propaganda 3
- hand before → after: 2 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': True, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['資本家'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] 資本家 returned to static purchase supply', '[Turn 1] player1 removed 資本家 and it returned to static_supply', '[Turn 1] player1 played 資本家']

## 分神 (disruption)
- effects: optional_trash
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 2 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['分神'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] 分神 returned to static purchase supply', '[Turn 1] player1 removed 分神 and it returned to static_supply', '[Turn 1] player1 played 分神']

## 內鬥 (disruption)
- effects: none
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '內鬥']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['內鬥'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 內鬥']

## 領導 (command)
- effects: draw
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '領導']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['領導'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 領導']

## 謀劃 (command)
- effects: draw
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 2
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '謀劃']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['謀劃'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 謀劃']

## 戰略 (command)
- effects: draw
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 3
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '戰略']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['戰略'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 戰略']

## 合作談判 (command)
- effects: shared_draw, gain_resource
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 2
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '合作談判']
- purchase_area after: []
- other_hands before → after: {'player2': 1} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['合作談判'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 合作談判']

## 高效行動 (command)
- effects: draw, discard_self
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 3 → 3
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '抽牌B', '抽牌C', '高效行動']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['高效行動'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 高效行動']

## 模仿戰術 (command)
- effects: imitate_topdeck
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '模仿戰術']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['模仿戰術'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ["[Turn 1] player1 imitated player2's top card 對手抽牌B", '[Turn 1] player1 played 模仿戰術']

## 乘勝追擊 (command)
- effects: gain_from_discard
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['乘勝追擊']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['乘勝追擊'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 乘勝追擊']

## 誘導虛耗 (command)
- effects: draw, optional_trash, force_discard
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 2 → 2
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 1}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['誘導虛耗'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] 誘導虛耗 returned to purchase deck discard', '[Turn 1] player1 removed 誘導虛耗 and it returned to deck_discard', '[Turn 1] player1 played 誘導虛耗']

## 點燃熱情 (command)
- effects: draw, conditional_draw
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 2
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '點燃熱情']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': True, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['點燃熱情'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 點燃熱情']

## 樹立信心 (command)
- effects: draw, conditional_draw
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 2
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '樹立信心']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': True, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['樹立信心'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 樹立信心']

## 網羅人才 (command)
- effects: choose_from_own_deck
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '網羅人才']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['網羅人才'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 may recruit 1 card from deck', '[Turn 1] player1 played 網羅人才']

## 凝聚共識 (command)
- effects: draw, discard_self, conditional_bonus
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 2
- hand before → after: 3 → 3
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '抽牌B', '抽牌C', '凝聚共識']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': True, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['凝聚共識'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 凝聚共識']

## 思想建設 (command)
- effects: draw, extend_build_range
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '思想建設']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['思想建設'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 思想建設']

## 擴大戰果 (command)
- effects: gain_any_from_discard
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['擴大戰果']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['擴大戰果'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 擴大戰果']

## 交通經驗丙 (transport)
- effects: extra_move
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 5
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '交通經驗丙']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['交通經驗丙'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 交通經驗丙']

## 交通經驗乙 (transport)
- effects: extra_move
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 7
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '交通經驗乙']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['交通經驗乙'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 交通經驗乙']

## 交通經驗甲 (transport)
- effects: extra_move
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 9
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '交通經驗甲']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['交通經驗甲'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 交通經驗甲']

## 組織經驗丙 (organization)
- effects: build
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 2, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '組織經驗丙']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['組織經驗丙'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 built organization in 北京 via card effect', '[Turn 1] player1 played 組織經驗丙']

## 組織經驗乙 (organization)
- effects: build, build
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 3, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '組織經驗乙']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['組織經驗乙'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 built organization in 北京 via card effect', '[Turn 1] player1 built organization in 北京 via card effect', '[Turn 1] player1 played 組織經驗乙']

## 組織經驗甲 (organization)
- effects: build
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 2, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '組織經驗甲']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['組織經驗甲'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 built organization in 北京 via card effect', '[Turn 1] player1 played 組織經驗甲']

## 批判 (purge)
- effects: trash_from_hand_or_discard
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 2 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['追隨者', '棄牌區非起始牌', '批判']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': True, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['批判'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 trashed 非起始牌', '[Turn 1] player1 played 批判']

## 批鬥 (purge)
- effects: trash_from_hand_or_discard
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 2 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['追隨者', '批鬥']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': True, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['批鬥'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 trashed 非起始牌', '[Turn 1] player1 trashed 棄牌區非起始牌', '[Turn 1] player1 played 批鬥']

## 爆料黑幕 (propaganda_special)
- effects: cancel_card, conditional_draw
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '爆料黑幕']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['爆料黑幕'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': [], 'canceled_propaganda_card': True}
- log tail: ['[Turn 1] player1 triggered cancel-card effect', '[Turn 1] player1 played 爆料黑幕']

## 輿論丕變 (propaganda_special)
- effects: refresh_purchase_area, gain_resource
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 1
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '輿論丕變']
- purchase_area after: ['市場4', '市場3', '市場2']
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['輿論丕變'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 輿論丕變']

## 行動預告 (propaganda_special)
- effects: topdeck_purchased_this_turn, gain_resource
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 1
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '行動預告']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['行動預告'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 行動預告']

## 派遣間諜 (spy)
- effects: dissolve
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1} → {}
- discard after: ['棄牌A', '棄牌B', '派遣間諜']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['派遣間諜'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 dissolved 1 organization from player2 at 香港城', '[Turn 1] player1 played 派遣間諜']

## 內應間諜 (spy)
- effects: dissolve
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1} → {'北京': 1}
- discard after: ['棄牌A', '棄牌B', '內應間諜']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['內應間諜'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 dissolved 1 organization from player2 at 香港城', '[Turn 1] player1 played 內應間諜']

## 情報網 (spy)
- effects: choose_one
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '內鬥', '情報網']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['情報網'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 gained 1 內鬥 card(s)', '[Turn 1] player1 played 情報網']

## 離間 (spy)
- effects: add_internal_conflict
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '內鬥', '內鬥', '內鬥', '離間']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['離間'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 gained 3 內鬥 card(s)', '[Turn 1] player1 played 離間']

## 走漏風聲 (spy)
- effects: leak_top_deck
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '走漏風聲']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['走漏風聲'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 used 走漏風聲 on player2: discarded 對手抽牌B', '[Turn 1] player1 played 走漏風聲']

## 地下黨 (spy)
- effects: choose_from_purchase_deck
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '地下黨']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['地下黨'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 revealed 3 cards for 地下黨', '[Turn 1] player1 played 地下黨']

## 武裝者 (armed)
- effects: force_discard
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '武裝者']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 1}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['武裝者'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 武裝者']

## 武裝小隊 (armed)
- effects: force_discard
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '武裝小隊']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 0}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['武裝小隊'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 武裝小隊']

## 武裝集團 (armed)
- effects: force_discard, conditional_draw
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '武裝集團']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 0}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': True, 'built_towns': [], 'played_nonstarter_names': ['武裝集團'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 武裝集團']

## 企業人脈 (money)
- effects: use_purchase_area_card
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '企業人脈']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': True, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['企業人脈'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 企業人脈']

## 產業滲透 (money)
- effects: cancel_card, conditional_draw
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '產業滲透']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': True, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['產業滲透'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': [], 'canceled_propaganda_card': True}
- log tail: ['[Turn 1] player1 triggered cancel-card effect', '[Turn 1] player1 played 產業滲透']

## 企畫遊說 (money)
- effects: reveal_topdeck_cost_gain
- checks: play_success, card_left_hand
- resources delta: money 2, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '企畫遊說']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': True, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['企畫遊說'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 revealed 抽牌D for 企畫遊說', '[Turn 1] player1 played 企畫遊說']

## 行動募資 (money)
- effects: topdeck_purchased_this_turn, gain_resource
- checks: play_success, card_left_hand
- resources delta: money 1, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '行動募資']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': True, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['行動募資'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- log tail: ['[Turn 1] player1 played 行動募資']
