# FULL GAMEPLAY 2P VALIDATION

日期：2026-05-09

summary: {'total_checks': 4, 'passed': 4, 'failed': 0, 'errors': []}

## init
- turn: 1
- turn_phase: TurnPhase.EVENT
- game_phase: GamePhase.MAIN
- current_player: anti
- base_validation: {'rows': [{'player': 'anti', 'faction': 'hong_kong', 'base': '香港城', 'orgs': {'香港城': 1}, 'single_base_org': True, 'base_allowed': True}, {'player': 'red', 'faction': 'red_army', 'base': '北京', 'orgs': {'北京': 1}, 'single_base_org': True, 'base_allowed': True}], 'unique_bases': True}
- players: [{'name': 'anti', 'faction': 'hong_kong', 'base': '香港城', 'orgs': {'香港城': 1}, 'hand': ['追隨者', '樂捐者', '樂捐者', '追隨者', '樂捐者']}, {'name': 'red', 'faction': 'red_army', 'base': '北京', 'orgs': {'北京': 1}, 'hand': ['樂捐者', '樂捐者', '追隨者', '追隨者', '追隨者']}]

## cycle_1_advance_to_action_before
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: anti

## cycle_1_advance_to_action_after
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: anti

## cycle_1_play_card
- player: anti
- faction: hong_kong
- hand_before: ['追隨者', '樂捐者', '樂捐者', '追隨者', '樂捐者']
- hand_after: ['樂捐者', '樂捐者', '追隨者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_1_move
- player: anti
- move_detail: {'from': '香港城', 'to': '澳門', 'mode': 'road'}
- result: {'success': True}
- orgs_after: {'澳門': 1}
- moves_left_after: 2

## cycle_1_advance_to_end
- turn: 1
- turn_phase: TurnPhase.END
- current_player: anti

## cycle_1_end_turn
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: red

## cycle_2_advance_to_action_before
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: red

## cycle_2_advance_to_action_after
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: red

## cycle_2_play_card
- player: red
- faction: red_army
- hand_before: ['樂捐者', '樂捐者', '追隨者', '追隨者', '追隨者']
- hand_after: ['樂捐者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_2_move
- player: red
- move_detail: {'from': '北京', 'to': '天津', 'mode': 'rail'}
- result: {'success': True}
- orgs_after: {'天津': 1}
- moves_left_after: 0

## cycle_2_advance_to_end
- turn: 1
- turn_phase: TurnPhase.END
- current_player: red

## cycle_2_end_turn
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: anti

## cycle_3_advance_to_action_before
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: anti

## cycle_3_advance_to_action_after
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: anti

## cycle_3_play_card
- player: anti
- faction: hong_kong
- hand_before: ['追隨者', '追隨者', '追隨者', '追隨者', '追隨者']
- hand_after: ['追隨者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_3_move
- player: anti
- move_detail: {'from': '澳門', 'to': '赤臘角', 'mode': 'road'}
- result: {'success': True}
- orgs_after: {'赤臘角': 1}
- moves_left_after: 2

## cycle_3_advance_to_end
- turn: 2
- turn_phase: TurnPhase.END
- current_player: anti

## cycle_3_end_turn
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: red

## cycle_4_advance_to_action_before
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: red

## cycle_4_advance_to_action_after
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: red

## cycle_4_play_card
- player: red
- faction: red_army
- hand_before: ['樂捐者', '追隨者', '追隨者', '追隨者', '追隨者']
- hand_after: ['追隨者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 3

## cycle_4_move
- player: red
- move_detail: {'from': '天津', 'to': '承德', 'mode': 'road'}
- result: {'success': True}
- orgs_after: {'承德': 1}
- moves_left_after: 2

## cycle_4_advance_to_end
- turn: 2
- turn_phase: TurnPhase.END
- current_player: red

## cycle_4_end_turn
- turn: 3
- turn_phase: TurnPhase.EVENT
- current_player: anti

## before_forced_legal_anti_victory_check
- candidate: anti
- faction: hong_kong
- org_count: 14
- turn: 3
- turn_phase: TurnPhase.EVENT

## after_forced_legal_anti_victory_check
- game_phase: GamePhase.FINISHED
- winner: anti
- turn: 3
- turn_phase: TurnPhase.EVENT

## final_state
- turn: 3
- turn_phase: TurnPhase.EVENT
- game_phase: GamePhase.FINISHED
- current_player: anti
- winner: anti