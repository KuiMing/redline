# FULL GAMEPLAY 2P VALIDATION

日期：2026-05-09

summary: {'total_checks': 4, 'passed': 4, 'failed': 0, 'errors': []}

## base_selection_choice
- choice: {'player_id': 'p1', 'label': '任意牆內城鎮', 'town': '深圳', 'result': {'success': True}}

## base_selection_resolution
- initial_pending: {'p1': {'labels': ['任意牆內城鎮'], 'resolved': {'任意牆內城鎮': ['北京', '深圳', '廣州', '湛茂', '梅州', '潮州', '桂林', '南寧', '海口', '三亞', '廈門', '福州', '溫州', '杭州', '上海', '南京', '合肥', '武漢', '南昌', '長沙', '南陽', '鄭州', '徐州', '濟南', '青島', '天津', '石家莊', '太原', '延安', '西安', '銀川', '蘭州', '敦煌', '西寧', '重慶', '成都', '貴陽', '昆明', '德宏', '西雙版納']}}}
- remaining_pending: {}
- game_phase_after_selection: main

## init
- turn: 1
- turn_phase: event
- game_phase: main
- current_player: anti
- base_validation: {'rows': [{'player': 'anti', 'faction': 'hong_kong', 'base': '香港城', 'orgs': {'香港城': 1}, 'single_base_org': True, 'base_allowed': True}, {'player': 'red', 'faction': 'red_army', 'base': '北京', 'orgs': {'北京': 1}, 'single_base_org': True, 'base_allowed': True}], 'unique_bases': True}
- players: [{'name': 'anti', 'faction': 'hong_kong', 'base': '香港城', 'orgs': {'香港城': 1}, 'hand': ['追隨者', '追隨者', '樂捐者', '追隨者', '追隨者']}, {'name': 'red', 'faction': 'red_army', 'base': '北京', 'orgs': {'北京': 1}, 'hand': ['追隨者', '樂捐者', '追隨者', '追隨者', '樂捐者']}]

## cycle_1_advance_to_action_before
- turn: 1
- turn_phase: event
- current_player: anti

## cycle_1_advance_to_action_after
- turn: 1
- turn_phase: action
- current_player: anti

## cycle_1_play_card
- player: anti
- faction: hong_kong
- hand_before: ['追隨者', '追隨者', '樂捐者', '追隨者', '追隨者']
- hand_after: ['追隨者', '樂捐者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_1_move
- player: anti
- move_detail: None
- result: {'skipped': 'no movable non-anchor organization'}
- orgs_after: {'香港城': 1}
- moves_left_after: 3

## cycle_1_advance_to_end
- turn: 1
- turn_phase: end
- current_player: anti

## cycle_1_end_turn
- turn: 1
- turn_phase: event
- current_player: red

## cycle_2_advance_to_action_before
- turn: 1
- turn_phase: event
- current_player: red

## cycle_2_advance_to_action_after
- turn: 1
- turn_phase: action
- current_player: red

## cycle_2_play_card
- player: red
- faction: red_army
- hand_before: ['追隨者', '樂捐者', '追隨者', '追隨者', '樂捐者']
- hand_after: ['樂捐者', '追隨者', '追隨者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_2_move
- player: red
- move_detail: None
- result: {'skipped': 'no movable non-anchor organization'}
- orgs_after: {'北京': 1}
- moves_left_after: 3

## cycle_2_advance_to_end
- turn: 1
- turn_phase: end
- current_player: red

## cycle_2_end_turn
- turn: 2
- turn_phase: event
- current_player: anti

## cycle_3_advance_to_action_before
- turn: 2
- turn_phase: event
- current_player: anti

## cycle_3_advance_to_action_after
- turn: 2
- turn_phase: action
- current_player: anti

## cycle_3_play_card
- player: anti
- faction: hong_kong
- hand_before: ['樂捐者', '樂捐者', '追隨者', '追隨者', '追隨者']
- hand_after: ['樂捐者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_3_move
- player: anti
- move_detail: None
- result: {'skipped': 'no movable non-anchor organization'}
- orgs_after: {'香港城': 1}
- moves_left_after: 3

## cycle_3_advance_to_end
- turn: 2
- turn_phase: end
- current_player: anti

## cycle_3_end_turn
- turn: 2
- turn_phase: event
- current_player: red

## cycle_4_advance_to_action_before
- turn: 2
- turn_phase: event
- current_player: red

## cycle_4_advance_to_action_after
- turn: 2
- turn_phase: action
- current_player: red

## cycle_4_play_card
- player: red
- faction: red_army
- hand_before: ['追隨者', '追隨者', '追隨者', '樂捐者', '追隨者']
- hand_after: ['追隨者', '追隨者', '樂捐者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_4_move
- player: red
- move_detail: None
- result: {'skipped': 'no movable non-anchor organization'}
- orgs_after: {'北京': 1}
- moves_left_after: 3

## cycle_4_advance_to_end
- turn: 2
- turn_phase: end
- current_player: red

## cycle_4_end_turn
- turn: 3
- turn_phase: event
- current_player: anti

## before_forced_legal_anti_victory_check
- candidate: anti
- faction: hong_kong
- org_count: 14
- turn: 3
- turn_phase: event

## after_forced_legal_anti_victory_check
- game_phase: finished
- winner: anti
- turn: 3
- turn_phase: event

## final_state
- turn: 3
- turn_phase: event
- game_phase: finished
- current_player: anti
- winner: anti