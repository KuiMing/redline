# FULL GAMEPLAY 4P VALIDATION

日期：2026-05-03

## base_selection_resolution
- initial_pending: {'p1': ['東京', '舊金山', '海參崴']}
- remaining_pending: {}
- game_phase_after_selection: main

## init
- turn: 1
- turn_phase: event
- current_player: player1
- base_validation: {'rows': [{'player': 'player1', 'faction': 'manchuria', 'base': '東京', 'orgs': {'東京': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['東京', '海參崴', '舊金山']}, {'player': 'player2', 'faction': 'uyghur_istanbul', 'base': '伊斯坦堡', 'orgs': {'伊斯坦堡': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['伊斯坦堡']}, {'player': 'player3', 'faction': 'tibet_dharamsala', 'base': '達蘭薩拉', 'orgs': {'達蘭薩拉': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['達蘭薩拉']}, {'player': 'player4', 'faction': 'red_army', 'base': '北京', 'orgs': {'北京': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['北京']}], 'unique_bases': True}

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
- faction: manchuria
- hand_before: ['樂捐者', '樂捐者', '追隨者', '追隨者', '樂捐者']
- hand_after: ['樂捐者', '追隨者', '追隨者', '樂捐者']
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
- faction: uyghur_istanbul
- hand_before: ['追隨者', '追隨者', '追隨者', '追隨者', '追隨者']
- hand_after: ['追隨者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_2_move
- player: player2
- move_detail: {'from': '伊斯坦堡', 'to': '伊德利卜', 'mode': 'rail'}
- result: {'success': True}
- orgs_after: {'伊德利卜': 1}
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
- faction: tibet_dharamsala
- hand_before: ['追隨者', '追隨者', '追隨者', '追隨者', '追隨者']
- hand_after: ['追隨者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_3_move
- player: player3
- move_detail: {'from': '達蘭薩拉', 'to': '列城', 'mode': 'road'}
- result: {'success': True}
- orgs_after: {'列城': 1}
- moves_left_after: 2

## cycle_3_advance_to_end
- turn: 1
- turn_phase: end
- current_player: player3

## cycle_3_end_turn
- turn: 1
- turn_phase: event
- current_player: player4

## cycle_4_advance_to_action_before
- turn: 1
- turn_phase: event
- current_player: player4

## cycle_4_advance_to_action_after
- turn: 1
- turn_phase: action
- current_player: player4

## cycle_4_play_card
- player: player4
- faction: red_army
- hand_before: ['追隨者', '樂捐者', '樂捐者', '追隨者', '追隨者']
- hand_after: ['樂捐者', '樂捐者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_4_move
- player: player4
- move_detail: {'from': '北京', 'to': '天津', 'mode': 'rail'}
- result: {'success': True}
- orgs_after: {'天津': 1}
- moves_left_after: 0

## cycle_4_advance_to_end
- turn: 1
- turn_phase: end
- current_player: player4

## cycle_4_end_turn
- turn: 2
- turn_phase: event
- current_player: player1

## cycle_5_advance_to_action_before
- turn: 2
- turn_phase: event
- current_player: player1

## cycle_5_advance_to_action_after
- turn: 2
- turn_phase: action
- current_player: player1

## cycle_5_play_card
- player: player1
- faction: manchuria
- hand_before: ['追隨者', '追隨者', '追隨者', '追隨者', '追隨者']
- hand_after: ['追隨者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_5_move
- player: player1
- move_detail: {'from': '大阪', 'to': '福岡', 'mode': 'rail'}
- result: {'success': True}
- orgs_after: {'福岡': 1}
- moves_left_after: 0

## cycle_5_advance_to_end
- turn: 2
- turn_phase: end
- current_player: player1

## cycle_5_end_turn
- turn: 2
- turn_phase: event
- current_player: player2

## cycle_6_advance_to_action_before
- turn: 2
- turn_phase: event
- current_player: player2

## cycle_6_advance_to_action_after
- turn: 2
- turn_phase: action
- current_player: player2

## cycle_6_play_card
- player: player2
- faction: uyghur_istanbul
- hand_before: ['追隨者', '追隨者', '樂捐者', '樂捐者', '樂捐者']
- hand_after: ['追隨者', '樂捐者', '樂捐者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_6_move
- player: player2
- move_detail: {'from': '伊德利卜', 'to': '伊斯坦堡', 'mode': 'rail'}
- result: {'success': True}
- orgs_after: {'伊斯坦堡': 1}
- moves_left_after: 0

## cycle_6_advance_to_end
- turn: 2
- turn_phase: end
- current_player: player2

## cycle_6_end_turn
- turn: 2
- turn_phase: event
- current_player: player3

## cycle_7_advance_to_action_before
- turn: 2
- turn_phase: event
- current_player: player3

## cycle_7_advance_to_action_after
- turn: 2
- turn_phase: action
- current_player: player3

## cycle_7_play_card
- player: player3
- faction: tibet_dharamsala
- hand_before: ['追隨者', '樂捐者', '樂捐者', '樂捐者', '追隨者']
- hand_after: ['樂捐者', '樂捐者', '樂捐者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_7_move
- player: player3
- move_detail: {'from': '列城', 'to': '吉爾吉特', 'mode': 'road'}
- result: {'success': True}
- orgs_after: {'吉爾吉特': 1}
- moves_left_after: 2

## cycle_7_advance_to_end
- turn: 2
- turn_phase: end
- current_player: player3

## cycle_7_end_turn
- turn: 2
- turn_phase: event
- current_player: player4

## cycle_8_advance_to_action_before
- turn: 2
- turn_phase: event
- current_player: player4

## cycle_8_advance_to_action_after
- turn: 2
- turn_phase: action
- current_player: player4

## cycle_8_play_card
- player: player4
- faction: red_army
- hand_before: ['樂捐者', '追隨者', '追隨者', '追隨者', '追隨者']
- hand_after: ['追隨者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_8_move
- player: player4
- move_detail: {'from': '天津', 'to': '承德', 'mode': 'road'}
- result: {'success': True}
- orgs_after: {'承德': 1}
- moves_left_after: 2

## cycle_8_advance_to_end
- turn: 2
- turn_phase: end
- current_player: player4

## cycle_8_end_turn
- turn: 3
- turn_phase: event
- current_player: player1

## before_forced_victory_check
- candidate: player1
- faction: manchuria
- org_count: 14
- turn: 3
- turn_phase: event

## after_forced_victory_check
- game_phase: finished
- winner: player1
- turn: 3
- turn_phase: event

## final_state
- turn: 3
- turn_phase: event
- game_phase: finished
- current_player: player1
- winner: player1