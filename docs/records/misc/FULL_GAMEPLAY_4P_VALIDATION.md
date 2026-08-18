# FULL GAMEPLAY 4P VALIDATION

日期：2026-05-03

## base_selection_choice
- choice: {'player_id': 'p1', 'label': '合肥', 'town': '合肥', 'result': {'success': True}}

## base_selection_choice
- choice: {'player_id': 'p3', 'label': '南寧', 'town': '南寧', 'result': {'success': True}}

## base_selection_resolution
- initial_pending: {'p1': {'labels': ['合肥', '南京', '任意東洋', '任意英美城鎮'], 'resolved': {'合肥': ['合肥'], '南京': ['南京'], '任意東洋': ['東京', '大阪', '福岡', '札幌', '仙臺', '沖繩', '首爾', '釜山'], '任意英美城鎮': ['華盛頓', '紐約', '多倫多', '卡加利', '溫哥華', '舊金山', '洛杉磯']}}, 'p3': {'labels': ['南寧', '昆明', '廣州', '河內', '胡志明市'], 'resolved': {'南寧': ['南寧'], '昆明': ['昆明'], '廣州': ['廣州'], '河內': ['河內'], '胡志明市': ['胡志明市']}}}
- remaining_pending: {}
- game_phase_after_selection: GamePhase.MAIN

## init
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player1
- base_validation: {'rows': [{'player': 'player1', 'faction': 'jianghuai', 'base': '合肥', 'orgs': {'合肥': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['仙臺', '倫敦', '南京', '卡加利', '合肥', '多倫多', '大阪', '札幌', '東京', '沖繩', '洛杉磯', '溫哥華']}, {'player': 'player2', 'faction': 'red_army', 'base': '北京', 'orgs': {'北京': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['北京']}, {'player': 'player3', 'faction': 'zhuang', 'base': '南寧', 'orgs': {'南寧': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['南寧', '廣州', '昆明', '河內', '胡志明市']}, {'player': 'player4', 'faction': 'taiwan_green', 'base': '臺北', 'orgs': {'臺北': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['臺北']}], 'unique_bases': True}

## cycle_1_advance_to_action_before
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player1

## cycle_1_advance_to_action_after
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player2

## cycle_1_play_card
- player: player2
- faction: red_army
- hand_before: ['追隨者', '追隨者', '追隨者', '樂捐者', '追隨者']
- hand_after: ['追隨者', '追隨者', '樂捐者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_1_move
- player: player2
- move_detail: None
- result: {'skipped': True, 'reason': 'no move points'}
- orgs_after: {'北京': 1}
- moves_left_after: 0

## cycle_1_action_phase_done
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player2

## cycle_1_end_turn
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player3

## cycle_2_advance_to_action_before
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player3

## cycle_2_advance_to_action_after
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player4

## cycle_2_play_card
- player: player4
- faction: taiwan_green
- hand_before: ['追隨者', '追隨者', '樂捐者', '追隨者', '樂捐者']
- hand_after: ['追隨者', '樂捐者', '追隨者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_2_move
- player: player4
- move_detail: None
- result: {'skipped': True, 'reason': 'no move points'}
- orgs_after: {'臺北': 1}
- moves_left_after: 0

## cycle_2_action_phase_done
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player4

## cycle_2_end_turn
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player1

## cycle_3_advance_to_action_before
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player1

## cycle_3_advance_to_action_after
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player2

## cycle_3_play_card
- player: player2
- faction: red_army
- hand_before: ['追隨者', '追隨者', '樂捐者', '追隨者', '樂捐者']
- hand_after: ['追隨者', '樂捐者', '追隨者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_3_move
- player: player2
- move_detail: None
- result: {'skipped': True, 'reason': 'no move points'}
- orgs_after: {'北京': 1}
- moves_left_after: 0

## cycle_3_action_phase_done
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player2

## cycle_3_end_turn
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player3

## cycle_4_advance_to_action_before
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player3

## cycle_4_advance_to_action_after
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player4

## cycle_4_play_card
- player: player4
- faction: taiwan_green
- hand_before: ['追隨者', '樂捐者', '追隨者', '樂捐者', '追隨者']
- hand_after: ['樂捐者', '追隨者', '樂捐者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_4_move
- player: player4
- move_detail: None
- result: {'skipped': True, 'reason': 'no move points'}
- orgs_after: {'臺北': 1}
- moves_left_after: 0

## cycle_4_action_phase_done
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player4

## cycle_4_end_turn
- turn: 3
- turn_phase: TurnPhase.ACTION
- current_player: player1

## cycle_5_advance_to_action_before
- turn: 3
- turn_phase: TurnPhase.ACTION
- current_player: player1

## cycle_5_advance_to_action_after
- turn: 3
- turn_phase: TurnPhase.ACTION
- current_player: player2

## cycle_5_play_card
- player: player2
- faction: red_army
- hand_before: ['追隨者', '樂捐者', '追隨者', '樂捐者', '追隨者']
- hand_after: ['樂捐者', '追隨者', '樂捐者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_5_move
- player: player2
- move_detail: None
- result: {'skipped': True, 'reason': 'no move points'}
- orgs_after: {'北京': 1}
- moves_left_after: 0

## cycle_5_action_phase_done
- turn: 3
- turn_phase: TurnPhase.ACTION
- current_player: player2

## cycle_5_end_turn
- turn: 3
- turn_phase: TurnPhase.ACTION
- current_player: player3

## cycle_6_advance_to_action_before
- turn: 3
- turn_phase: TurnPhase.ACTION
- current_player: player3

## cycle_6_advance_to_action_after
- turn: 3
- turn_phase: TurnPhase.ACTION
- current_player: player4

## cycle_6_play_card
- player: player4
- faction: taiwan_green
- hand_before: ['樂捐者', '追隨者', '樂捐者', '追隨者', '追隨者']
- hand_after: ['追隨者', '樂捐者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_6_move
- player: player4
- move_detail: None
- result: {'skipped': True, 'reason': 'no move points'}
- orgs_after: {'臺北': 1}
- moves_left_after: 0

## cycle_6_action_phase_done
- turn: 3
- turn_phase: TurnPhase.ACTION
- current_player: player4

## cycle_6_end_turn
- turn: 4
- turn_phase: TurnPhase.ACTION
- current_player: player1

## cycle_7_advance_to_action_before
- turn: 4
- turn_phase: TurnPhase.ACTION
- current_player: player1

## cycle_7_advance_to_action_after
- turn: 4
- turn_phase: TurnPhase.ACTION
- current_player: player2

## cycle_7_after_advance_to_action_resolve_pending_choices
- resolved: [{'player_id': 'p2', 'choice_type': 'town_choice', 'choice_key': 'event_build_organization', 'index': 0, 'result': {'success': True, 'choice_index': 0, 'town': '吉爾吉特', 'selected': {'town': '吉爾吉特', 'region': 'middle_east'}, 'choice_key': 'event_build_organization'}, 'turn': 4, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player': 'player2'}]

## cycle_7_play_card
- player: player2
- faction: red_army
- hand_before: ['樂捐者', '追隨者', '樂捐者', '追隨者', '追隨者']
- hand_after: ['追隨者', '樂捐者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_7_move
- player: player2
- move_detail: None
- result: {'skipped': True, 'reason': 'no move points'}
- orgs_after: {'北京': 1, '吉爾吉特': 1}
- moves_left_after: 0

## cycle_7_action_phase_done
- turn: 4
- turn_phase: TurnPhase.ACTION
- current_player: player2

## cycle_7_end_turn
- turn: 4
- turn_phase: TurnPhase.ACTION
- current_player: player3

## cycle_8_advance_to_action_before
- turn: 4
- turn_phase: TurnPhase.ACTION
- current_player: player3

## cycle_8_advance_to_action_after
- turn: 4
- turn_phase: TurnPhase.ACTION
- current_player: player4

## cycle_8_play_card
- player: player4
- faction: taiwan_green
- hand_before: ['追隨者', '追隨者', '追隨者', '追隨者']
- hand_after: ['追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_8_move
- player: player4
- move_detail: None
- result: {'skipped': True, 'reason': 'no move points'}
- orgs_after: {'臺北': 1}
- moves_left_after: 0

## cycle_8_action_phase_done
- turn: 4
- turn_phase: TurnPhase.ACTION
- current_player: player4

## cycle_8_end_turn
- turn: 5
- turn_phase: TurnPhase.ACTION
- current_player: player1

## before_forced_victory_check
- candidate: player1
- faction: jianghuai
- org_count: 12
- forced_red_survival: False
- turn: 5
- turn_phase: TurnPhase.ACTION

## after_forced_victory_check
- did_win: True
- game_phase: GamePhase.FINISHED
- winner: player1
- turn: 5
- turn_phase: TurnPhase.ACTION

## final_state
- turn: 5
- turn_phase: TurnPhase.ACTION
- game_phase: GamePhase.FINISHED
- current_player: player1
- winner: player1