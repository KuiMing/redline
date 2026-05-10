# 卡牌用途二選一規則驗證

- total: 4
- passed: 4
- failed: 0

## PASS — resource_mode_grants_printed_resources_without_action_effect
- result: {'success': True}
- resources: {'money': 1, 'propaganda': 2}
- pending_choice: None
- purchase_draw_before: ['候選三', '候選二', '候選一']
- purchase_draw_after: ['候選三', '候選二', '候選一']
- discard: ['地下黨']

## PASS — action_mode_executes_effect_without_printed_resources
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- pending_choice: {'type': 'underground_party', 'player_id': 'p1', 'prompt': '地下黨：從購買區牌庫頂拿取3張牌，任選其中1張加入手牌，其餘移除。', 'cards': ['候選一', '候選二', '候選三']}
- purchase_draw_after: ['底牌']
- discard: ['地下黨']

## PASS — play_card_requires_explicit_resource_or_action_mode
- result: {'error': 'Card play mode must be resource or action'}
- hand: ['領導']
- resources: {'money': 0, 'propaganda': 0}
- draw_pile: ['補牌']

## PASS — unspent_resources_clear_at_end_turn
- resources_after_end_turn: {'money': 0, 'propaganda': 0}
- moves_left_after_end_turn: 0
- turn_phase: event
- current_player: other
