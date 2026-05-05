# FACTION ABILITY PHASE1 VALIDATION

- total: 6
- passed: 6
- failed: 0

- PASS hong_kong_lam_chau_setup: ['宣傳家']
- PASS hong_kong_international_line: {'played_money_card': False, 'played_propaganda_card': True, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': []}
- PASS taiwan_green_end_turn_draw: before=0, after=1
- PASS taiwan_blue_end_turn_draw: before=0, after=1
- PASS mongol_school_restriction: {'error': '盟族學校：只能在蒙古發展空間建立組織'}
- PASS kazakh_first_propaganda_draw: before=1, after=0, log={'played_money_card': False, 'played_propaganda_card': True, 'non_starter_discard': False, 'successful_discard': False, 'built_towns': []}
