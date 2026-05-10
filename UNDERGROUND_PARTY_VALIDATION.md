# 地下黨規則驗證

- total: 3
- passed: 3
- failed: 0

## PASS — structured_effect_uses_purchase_deck_choice_not_discard_gain
- effect_types: ['choose_from_purchase_deck']
- expected: ['choose_from_purchase_deck']
- reason: 地下黨應是購買區牌庫選牌效果，不應殘留 gain_any_from_discard。

## PASS — play_reveals_top_three_purchase_deck_cards_and_not_player_discard
- play_result: {'success': True}
- pending_choice: {'type': 'underground_party', 'player_id': 'p1', 'prompt': '地下黨：從購買區牌庫頂拿取3張牌，任選其中1張加入手牌，其餘移除。', 'cards': ['候選一', '候選二', '候選三']}
- expected_choices: ['候選一', '候選二', '候選三']
- player_hand: []
- player_discard: ['不該取得的棄牌', '地下黨']
- resources: {'money': 1, 'propaganda': 2}
- purchase_draw_remaining: ['底牌']

## PASS — resolve_choice_adds_selected_to_hand_and_returns_unselected_to_purchase_deck_discard
- resolve_result: {'success': True, 'chosen_card': '候選二', 'removed_cards': [{'zone': 'deck_discard', 'name': '候選一'}, {'zone': 'deck_discard', 'name': '候選三'}]}
- player_hand: ['候選二']
- player_discard: ['地下黨']
- purchase_draw_remaining: ['底牌']
- purchase_discard: ['候選一', '候選三']
- removed_zones: ['deck_discard', 'deck_discard']
- pending_choice_after: None
