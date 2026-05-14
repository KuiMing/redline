# FACTION ABILITY PHASE1 VALIDATION

- total: 6
- passed: 6
- failed: 0

- PASS hong_kong_lam_chau_setup: ['宣傳家']
- PASS hong_kong_international_line: {'played_money_card': False, 'played_propaganda_card': True, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['測試金錢牌'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': []}
- PASS taiwan_green_end_turn_draw: before=0, after=1
- PASS taiwan_blue_end_turn_draw: before=0, after=1
- PASS mongol_develop_legality: allow_mongol=True, allow_uncamped=True, block_other=True, result={'success': True}
- PASS kazakh_first_propaganda_draw: before=1, after=1, log={'played_money_card': False, 'played_propaganda_card': True, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': [], 'played_nonstarter_names': ['宣傳測試'], 'combo_reward_triggered': False, 'guerrilla_triggered': False, 'faction_action_used': False, 'india_flag_money_triggered': False, 'purchased_cards_this_turn': [], 'faction_first_propaganda_triggered': True}
