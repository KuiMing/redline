# FULL GAMEPLAY 3P VALIDATION

日期：2026-05-03

## init
- turn: 1
- turn_phase: event
- current_player: player1
- base_validation: {'rows': [{'player': 'player1', 'faction': 'qi', 'base': '東京', 'orgs': {'東京': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['仙臺', '倫敦', '卡加利', '多倫多', '大阪', '札幌', '東京', '沖繩', '洛杉磯', '溫哥華', '濟南', '福岡']}, {'player': 'player2', 'faction': 'ye_lang_qian', 'base': '貴陽', 'orgs': {'貴陽': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['貴陽']}, {'player': 'player3', 'faction': 'red_army', 'base': '北京', 'orgs': {'北京': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['北京']}], 'unique_bases': True}

## cycle_1_advance_to_action_before
- turn: 1
- turn_phase: event
- current_player: player1

## cycle_1_advance_to_action_after
- turn: 1
- turn_phase: action
- current_player: player1

## cycle_1_play_card
- player: player1
- faction: qi
- hand_before: ['追隨者', '追隨者', '追隨者', '樂捐者', '樂捐者']
- hand_after: ['追隨者', '追隨者', '樂捐者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_1_move
- player: player1
- move_detail: {'from': '東京', 'to': '大阪', 'mode': 'rail'}
- result: {'success': True}
- orgs_after: {'大阪': 1}
- moves_left_after: 0

## cycle_1_advance_to_end
- turn: 1
- turn_phase: end
- current_player: player1

## cycle_1_end_turn
- turn: 1
- turn_phase: event
- current_player: player2

## cycle_2_advance_to_action_before
- turn: 1
- turn_phase: event
- current_player: player2

## cycle_2_advance_to_action_after
- turn: 1
- turn_phase: action
- current_player: player2

## cycle_2_play_card
- player: player2
- faction: ye_lang_qian
- hand_before: ['樂捐者', '追隨者', '樂捐者', '追隨者', '追隨者']
- hand_after: ['追隨者', '樂捐者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_2_move
- player: player2
- move_detail: {'from': '貴陽', 'to': '重慶', 'mode': 'rail'}
- result: {'success': True}
- orgs_after: {'重慶': 1}
- moves_left_after: 0

## cycle_2_advance_to_end
- turn: 1
- turn_phase: end
- current_player: player2

## cycle_2_end_turn
- turn: 1
- turn_phase: event
- current_player: player3

## cycle_3_advance_to_action_before
- turn: 1
- turn_phase: event
- current_player: player3

## cycle_3_advance_to_action_after
- turn: 1
- turn_phase: action
- current_player: player3

## cycle_3_play_card
- player: player3
- faction: red_army
- hand_before: ['樂捐者', '樂捐者', '追隨者', '樂捐者', '追隨者']
- hand_after: ['樂捐者', '追隨者', '樂捐者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_3_move
- player: player3
- move_detail: {'from': '北京', 'to': '天津', 'mode': 'rail'}
- result: {'success': True}
- orgs_after: {'天津': 1}
- moves_left_after: 0

## cycle_3_advance_to_end
- turn: 1
- turn_phase: end
- current_player: player3

## cycle_3_end_turn
- turn: 2
- turn_phase: event
- current_player: player1

## cycle_4_advance_to_action_before
- turn: 2
- turn_phase: event
- current_player: player1

## cycle_4_advance_to_action_after
- turn: 2
- turn_phase: action
- current_player: player1

## cycle_4_play_card
- player: player1
- faction: qi
- hand_before: ['追隨者', '追隨者', '樂捐者', '追隨者', '追隨者']
- hand_after: ['追隨者', '樂捐者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_4_move
- player: player1
- move_detail: {'from': '大阪', 'to': '福岡', 'mode': 'rail'}
- result: {'success': True}
- orgs_after: {'福岡': 1}
- moves_left_after: 0

## cycle_4_advance_to_end
- turn: 2
- turn_phase: end
- current_player: player1

## cycle_4_end_turn
- turn: 2
- turn_phase: event
- current_player: player2

## cycle_5_advance_to_action_before
- turn: 2
- turn_phase: event
- current_player: player2

## cycle_5_advance_to_action_after
- turn: 2
- turn_phase: action
- current_player: player2

## cycle_5_play_card
- player: player2
- faction: ye_lang_qian
- hand_before: ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者']
- hand_after: ['樂捐者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_5_move
- player: player2
- move_detail: {'from': '重慶', 'to': '成都', 'mode': 'rail'}
- result: {'success': True}
- orgs_after: {'成都': 1}
- moves_left_after: 0

## cycle_5_advance_to_end
- turn: 2
- turn_phase: end
- current_player: player2

## cycle_5_end_turn
- turn: 2
- turn_phase: event
- current_player: player3

## cycle_6_advance_to_action_before
- turn: 2
- turn_phase: event
- current_player: player3

## cycle_6_advance_to_action_after
- turn: 2
- turn_phase: action
- current_player: player3

## cycle_6_play_card
- player: player3
- faction: red_army
- hand_before: ['追隨者', '追隨者', '追隨者', '追隨者', '追隨者']
- hand_after: ['追隨者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_6_move
- player: player3
- move_detail: {'from': '天津', 'to': '承德', 'mode': 'road'}
- result: {'success': True}
- orgs_after: {'承德': 1}
- moves_left_after: 2

## cycle_6_advance_to_end
- turn: 2
- turn_phase: end
- current_player: player3

## cycle_6_end_turn
- turn: 3
- turn_phase: event
- current_player: player1

## before_forced_victory_check
- candidate: player1
- faction: qi
- org_count: 14
- turn: 3
- turn_phase: event

## after_forced_victory_check
- game_phase: setup
- winner: None
- turn: 3
- turn_phase: event

## final_state
- turn: 3
- turn_phase: event
- game_phase: setup
- current_player: player1
- winner: None