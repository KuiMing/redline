# FACTION ABILITY PHASE3 VALIDATION

- total: 4
- passed: 4
- failed: 0

- PASS nonviolence_play_block: {'error': '非暴力：不能打出武裝類卡牌'}
- PASS nonviolence_buy_block: {'error': '非暴力：不能購買武裝類卡牌'}
- PASS guerrilla_can_choose_red_discard: choice_created=True, choice=red_discard, red_hand=0
- PASS guerrilla_draw_if_red_empty: hand=1
