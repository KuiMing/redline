# FULL GAMEPLAY 2P VALIDATION

日期：2026-05-09

summary: {'total_checks': 4, 'passed': 3, 'failed': 1, 'errors': [{'step': 'cycle_4_play_card', 'player': 'red', 'faction': 'red_army', 'hand_before': ['紅軍奧援', '追隨者', '樂捐者', '樂捐者', '追隨者'], 'hand_after': ['紅軍奧援', '追隨者', '樂捐者', '樂捐者', '追隨者'], 'result': {'error': 'Please resolve the pending choice first'}, 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0}]}

## base_selection_choice
- choice: {'player_id': 'p1', 'label': '任意牆內城鎮', 'town': '三亞', 'result': {'success': True}}

## base_selection_resolution
- initial_pending: {'p1': {'labels': ['任意牆內城鎮'], 'resolved': {'任意牆內城鎮': ['三亞', '上海', '北京', '南京', '南寧', '南昌', '南陽', '合肥', '天津', '太原', '奇臺', '廈門', '廣州', '延安', '徐州', '德宏', '成都', '敦煌', '昆明', '昌吉', '杭州', '桂林', '梅州', '武漢', '海口', '深圳', '湛茂', '溫州', '潮州', '澳門', '濟南', '石家莊', '福州', '蘭州', '西安', '西寧', '西雙版納', '貴陽', '鄭州', '重慶', '銀川', '長沙', '青島']}}}
- remaining_pending: {}
- game_phase_after_selection: GamePhase.MAIN

## init
- turn: 1
- turn_phase: TurnPhase.EVENT
- game_phase: GamePhase.MAIN
- current_player: anti
- base_validation: {'rows': [{'player': 'anti', 'faction': 'hong_kong', 'base': '香港城', 'orgs': {'香港城': 1}, 'single_base_org': True, 'base_allowed': True}, {'player': 'red', 'faction': 'red_army', 'base': '北京', 'orgs': {'北京': 1}, 'single_base_org': True, 'base_allowed': True}], 'unique_bases': True}
- players: [{'name': 'anti', 'faction': 'hong_kong', 'base': '香港城', 'orgs': {'香港城': 1}, 'hand': ['追隨者', '追隨者', '樂捐者', '追隨者', '追隨者']}, {'name': 'red', 'faction': 'red_army', 'base': '北京', 'orgs': {'北京': 1}, 'hand': ['追隨者', '紅軍奧援', '追隨者', '樂捐者', '樂捐者']}]

## cycle_1_advance_to_action_before
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: anti
- pending_choice: None

## cycle_1_advance_event_step
- result: {'success': True}
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: anti
- pending_choice: None
- event: 貿易戰加劇
- event_progress: {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}

## cycle_1_advance_to_action_after
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: anti
- pending_choice: None
- reached_action: True

## cycle_1_play_card
- player: anti
- faction: hong_kong
- hand_before: ['追隨者', '追隨者', '樂捐者', '追隨者', '追隨者']
- hand_after: ['追隨者', '樂捐者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_1_move
- player: anti
- move_detail: None
- result: {'skipped': 'no move points available'}
- orgs_after: {'香港城': 1}
- moves_left_after: 0

## cycle_1_end_turn
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: red

## cycle_2_advance_to_action_before
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: red
- pending_choice: None

## cycle_2_advance_to_action_after
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: red
- pending_choice: None
- reached_action: True

## cycle_2_play_card
- player: red
- faction: red_army
- hand_before: ['追隨者', '紅軍奧援', '追隨者', '樂捐者', '樂捐者']
- hand_after: ['紅軍奧援', '追隨者', '樂捐者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_2_move
- player: red
- move_detail: None
- result: {'skipped': 'no move points available'}
- orgs_after: {'北京': 1}
- moves_left_after: 0

## cycle_2_end_turn
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: anti

## cycle_3_advance_to_action_before
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: anti
- pending_choice: None

## cycle_3_advance_to_action_after
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: anti
- pending_choice: None
- reached_action: True

## cycle_3_play_card
- player: anti
- faction: hong_kong
- hand_before: ['追隨者', '樂捐者', '追隨者', '追隨者', '樂捐者']
- hand_after: ['樂捐者', '追隨者', '追隨者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_3_move
- player: anti
- move_detail: None
- result: {'skipped': 'no move points available'}
- orgs_after: {'香港城': 1}
- moves_left_after: 0

## cycle_3_end_turn
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: red

## cycle_4_advance_to_action_before
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: red
- pending_choice: event_build_organization

## cycle_4_advance_to_action_after
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: red
- pending_choice: event_build_organization
- reached_action: True

## cycle_4_play_card
- player: red
- faction: red_army
- hand_before: ['紅軍奧援', '追隨者', '樂捐者', '樂捐者', '追隨者']
- hand_after: ['紅軍奧援', '追隨者', '樂捐者', '樂捐者', '追隨者']
- result: {'error': 'Please resolve the pending choice first'}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_4_move
- player: red
- move_detail: None
- result: {'skipped': 'no move points available'}
- orgs_after: {'北京': 1}
- moves_left_after: 0

## cycle_4_end_turn
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: red

## before_forced_legal_anti_victory_check
- candidate: anti
- faction: hong_kong
- org_count: 14
- turn: 2
- turn_phase: TurnPhase.ACTION

## after_forced_legal_anti_victory_check
- game_phase: GamePhase.FINISHED
- winner: anti
- turn: 2
- turn_phase: TurnPhase.ACTION

## final_state
- turn: 2
- turn_phase: TurnPhase.ACTION
- game_phase: GamePhase.FINISHED
- current_player: red
- winner: anti