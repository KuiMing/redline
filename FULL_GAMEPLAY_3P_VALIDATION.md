# FULL GAMEPLAY 3P VALIDATION

日期：2026-05-03

## base_selection_resolution
- initial_pending: {'p3': ['華盛頓', '紐約', '多倫多', '卡加利', '溫哥華', '舊金山', '洛杉磯']}
- remaining_pending: {}
- game_phase_after_selection: main

## init
- turn: 1
- turn_phase: event
- current_player: player1
- base_validation: {'rows': [{'player': 'player1', 'faction': 'red_army', 'base': '北京', 'orgs': {'北京': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['北京']}, {'player': 'player2', 'faction': 'tibet_dehradun', 'base': '德拉敦', 'orgs': {'德拉敦': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['德拉敦']}, {'player': 'player3', 'faction': 'zhaowu_ganqingning', 'base': '華盛頓', 'orgs': {'華盛頓': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['倫敦', '利雅德', '卡加利', '多倫多', '洛杉磯', '溫哥華', '紐約', '舊金山', '華盛頓', '蘭州']}], 'unique_bases': True}

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
- faction: red_army
- hand_before: ['追隨者', '追隨者', '追隨者', '追隨者', '追隨者']
- hand_after: ['追隨者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_1_move
- player: player1
- move_detail: {'from': '北京', 'to': '天津', 'mode': 'rail'}
- result: {'success': True}
- orgs_after: {'天津': 1}
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
- faction: tibet_dehradun
- hand_before: ['追隨者', '追隨者', '樂捐者', '追隨者', '追隨者']
- hand_after: ['追隨者', '樂捐者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_2_move
- player: player2
- move_detail: {'from': '德拉敦', 'to': '博卡拉', 'mode': 'road'}
- result: {'success': True}
- orgs_after: {'博卡拉': 1}
- moves_left_after: 2

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
- faction: zhaowu_ganqingning
- hand_before: ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者']
- hand_after: ['樂捐者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_3_move
- player: player3
- move_detail: {'from': '華盛頓', 'to': '倫敦', 'mode': 'road'}
- result: {'success': True}
- orgs_after: {'倫敦': 1}
- moves_left_after: 2

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
- faction: red_army
- hand_before: ['樂捐者', '樂捐者', '樂捐者', '追隨者', '追隨者']
- hand_after: ['樂捐者', '樂捐者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_4_move
- player: player1
- move_detail: {'from': '天津', 'to': '承德', 'mode': 'road'}
- result: {'success': True}
- orgs_after: {'承德': 1}
- moves_left_after: 2

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
- faction: tibet_dehradun
- hand_before: ['樂捐者', '追隨者', '追隨者', '樂捐者', '追隨者']
- hand_after: ['追隨者', '追隨者', '樂捐者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_5_move
- player: player2
- move_detail: {'from': '博卡拉', 'to': '加德滿都', 'mode': 'road'}
- result: {'success': True}
- orgs_after: {'加德滿都': 1}
- moves_left_after: 2

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
- faction: zhaowu_ganqingning
- hand_before: ['樂捐者', '樂捐者', '追隨者', '追隨者', '追隨者']
- hand_after: ['樂捐者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_6_move
- player: player3
- move_detail: {'from': '倫敦', 'to': '華盛頓', 'mode': 'road'}
- result: {'success': True}
- orgs_after: {'華盛頓': 1}
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
- faction: red_army
- org_count: 14
- turn: 3
- turn_phase: event

## after_forced_victory_check
- game_phase: main
- winner: None
- turn: 3
- turn_phase: event

## final_state
- turn: 3
- turn_phase: event
- game_phase: main
- current_player: player1
- winner: None