# FULL GAMEPLAY 2P VALIDATION

日期：2026-05-03

## init
- turn: 1
- turn_phase: event
- current_player: host
- players: [{'name': 'host', 'faction': 'red_army', 'orgs': {'北京': 1}, 'hand': ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者']}, {'name': 'guest', 'faction': 'uyghur_munich', 'orgs': {'慕尼黑': 1}, 'hand': ['樂捐者', '追隨者', '追隨者', '追隨者', '追隨者']}]

## cycle_1_advance_to_action_before
- turn: 1
- turn_phase: event
- current_player: host

## cycle_1_advance_to_action_after
- turn: 1
- turn_phase: action
- current_player: host

## cycle_1_play_card
- player: host
- hand_before: ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者']
- hand_after: ['樂捐者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_1_move
- player: host
- result: {'success': True}
- orgs_after: {'天津': 1}
- moves_left_after: 0

## cycle_1_advance_to_end
- turn: 1
- turn_phase: end
- current_player: host

## cycle_1_end_turn
- turn: 1
- turn_phase: event
- current_player: guest

## cycle_2_advance_to_action_before
- turn: 1
- turn_phase: event
- current_player: guest

## cycle_2_advance_to_action_after
- turn: 1
- turn_phase: action
- current_player: guest

## cycle_2_play_card
- player: guest
- hand_before: ['樂捐者', '追隨者', '追隨者', '追隨者', '追隨者']
- hand_after: ['追隨者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_2_move
- player: guest
- result: {'success': True}
- orgs_after: {'日內瓦': 1}
- moves_left_after: 0

## cycle_2_advance_to_end
- turn: 1
- turn_phase: end
- current_player: guest

## cycle_2_end_turn
- turn: 2
- turn_phase: event
- current_player: host

## cycle_3_advance_to_action_before
- turn: 2
- turn_phase: event
- current_player: host

## cycle_3_advance_to_action_after
- turn: 2
- turn_phase: action
- current_player: host

## cycle_3_play_card
- player: host
- hand_before: ['追隨者', '樂捐者', '追隨者', '樂捐者', '追隨者']
- hand_after: ['樂捐者', '追隨者', '樂捐者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_3_move
- player: host
- result: {'success': True}
- orgs_after: {'承德': 1}
- moves_left_after: 2

## cycle_3_advance_to_end
- turn: 2
- turn_phase: end
- current_player: host

## cycle_3_end_turn
- turn: 2
- turn_phase: event
- current_player: guest

## cycle_4_advance_to_action_before
- turn: 2
- turn_phase: event
- current_player: guest

## cycle_4_advance_to_action_after
- turn: 2
- turn_phase: action
- current_player: guest

## cycle_4_play_card
- player: guest
- hand_before: ['樂捐者', '追隨者', '樂捐者', '追隨者', '追隨者']
- hand_after: ['追隨者', '樂捐者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_4_move
- player: guest
- result: {'success': True}
- orgs_after: {'巴黎': 1}
- moves_left_after: 0

## cycle_4_advance_to_end
- turn: 2
- turn_phase: end
- current_player: guest

## cycle_4_end_turn
- turn: 3
- turn_phase: event
- current_player: host

## before_forced_victory_check
- candidate: host
- faction: red_army
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
- current_player: host
- winner: None