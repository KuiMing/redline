# FULL GAMEPLAY 3P VALIDATION

日期：2026-05-03

## base_selection_choice
- choice: {'player_id': 'p1', 'label': '青島', 'town': '青島', 'result': {'success': True}}

## base_selection_choice
- choice: {'player_id': 'p2', 'label': '任意牆內', 'town': '三亞', 'result': {'success': True}}

## base_selection_resolution
- initial_pending: {'p1': {'labels': ['青島', '濟南', '任意東洋', '任意英美城鎮'], 'resolved': {'青島': ['青島'], '濟南': ['濟南'], '任意東洋': ['東京', '大阪', '福岡', '札幌', '仙臺', '沖繩', '首爾', '釜山'], '任意英美城鎮': ['華盛頓', '紐約', '多倫多', '卡加利', '溫哥華', '舊金山', '洛杉磯']}}, 'p2': {'labels': ['任意牆內', '任意英美城鎮'], 'resolved': {'任意牆內': ['三亞', '上海', '北京', '南京', '南寧', '南昌', '南陽', '合肥', '天津', '太原', '奇臺', '廈門', '廣州', '延安', '徐州', '德宏', '成都', '敦煌', '昆明', '昌吉', '杭州', '桂林', '梅州', '武漢', '海口', '深圳', '湛茂', '溫州', '潮州', '澳門', '濟南', '石家莊', '福州', '蘭州', '西安', '西寧', '西雙版納', '貴陽', '鄭州', '重慶', '銀川', '長沙', '青島'], '任意英美城鎮': ['華盛頓', '紐約', '多倫多', '卡加利', '溫哥華', '舊金山', '洛杉磯']}}}
- remaining_pending: {}
- game_phase_after_selection: GamePhase.MAIN

## init
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: player1
- base_validation: {'rows': [{'player': 'player1', 'faction': 'qi', 'base': '青島', 'orgs': {'青島': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['仙臺', '倫敦', '卡加利', '多倫多', '大阪', '札幌', '東京', '沖繩', '洛杉磯', '溫哥華', '濟南', '福岡']}, {'player': 'player2', 'faction': 'reform_opening', 'base': '三亞', 'orgs': {'三亞': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['三亞', '上海', '上粉沙打', '丹東', '九龍城', '伊寧', '佳木斯', '倫敦', '元朗', '克孜勒蘇', '克拉瑪依', '包頭']}, {'player': 'player3', 'faction': 'red_army', 'base': '北京', 'orgs': {'北京': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['北京']}], 'unique_bases': True}

## cycle_1_advance_to_action_before
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: player1

## cycle_1_advance_to_action_after
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player1

## cycle_1_play_card
- player: player1
- faction: qi
- hand_before: ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者']
- hand_after: ['樂捐者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_1_move
- player: player1
- move_detail: None
- result: {'skipped': True}
- orgs_after: {'青島': 1}
- moves_left_after: 0

## cycle_1_advance_to_end
- turn: 1
- turn_phase: TurnPhase.END
- current_player: player1

## cycle_1_end_turn
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: player2

## cycle_2_advance_to_action_before
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: player2

## cycle_2_advance_to_action_after
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player2

## cycle_2_play_card
- player: player2
- faction: reform_opening
- hand_before: ['追隨者', '追隨者', '追隨者', '追隨者', '追隨者']
- hand_after: ['追隨者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_2_move
- player: player2
- move_detail: None
- result: {'skipped': True}
- orgs_after: {'三亞': 1}
- moves_left_after: 0

## cycle_2_advance_to_end
- turn: 1
- turn_phase: TurnPhase.END
- current_player: player2

## cycle_2_end_turn
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: player3

## cycle_3_advance_to_action_before
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: player3

## cycle_3_advance_to_action_after
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player3

## cycle_3_play_card
- player: player3
- faction: red_army
- hand_before: ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者']
- hand_after: ['樂捐者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_3_move
- player: player3
- move_detail: None
- result: {'skipped': True}
- orgs_after: {'北京': 1}
- moves_left_after: 0

## cycle_3_advance_to_end
- turn: 1
- turn_phase: TurnPhase.END
- current_player: player3

## cycle_3_end_turn
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: player1

## cycle_4_advance_to_action_before
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: player1

## cycle_4_advance_to_action_after
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player1

## cycle_4_play_card
- player: player1
- faction: qi
- hand_before: ['追隨者', '樂捐者', '追隨者', '追隨者', '樂捐者']
- hand_after: ['樂捐者', '追隨者', '追隨者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_4_move
- player: player1
- move_detail: None
- result: {'skipped': True}
- orgs_after: {'青島': 1}
- moves_left_after: 0

## cycle_4_advance_to_end
- turn: 2
- turn_phase: TurnPhase.END
- current_player: player1

## cycle_4_end_turn
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: player2

## cycle_5_advance_to_action_before
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: player2

## cycle_5_advance_to_action_after
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player2

## cycle_5_play_card
- player: player2
- faction: reform_opening
- hand_before: ['追隨者', '追隨者', '樂捐者', '樂捐者', '樂捐者']
- hand_after: ['追隨者', '樂捐者', '樂捐者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_5_move
- player: player2
- move_detail: None
- result: {'skipped': True}
- orgs_after: {'三亞': 1}
- moves_left_after: 0

## cycle_5_advance_to_end
- turn: 2
- turn_phase: TurnPhase.END
- current_player: player2

## cycle_5_end_turn
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: player3

## cycle_6_advance_to_action_before
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: player3

## cycle_6_advance_to_action_after
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player3

## cycle_6_play_card
- player: player3
- faction: red_army
- hand_before: ['樂捐者', '追隨者', '追隨者', '追隨者', '樂捐者']
- hand_after: ['追隨者', '追隨者', '追隨者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_6_move
- player: player3
- move_detail: None
- result: {'skipped': True}
- orgs_after: {'北京': 1}
- moves_left_after: 0

## cycle_6_advance_to_end
- turn: 2
- turn_phase: TurnPhase.END
- current_player: player3

## cycle_6_end_turn
- turn: 3
- turn_phase: TurnPhase.EVENT
- current_player: player1

## before_forced_victory_check
- candidate: player3
- faction: red_army
- org_count: 1
- forced_red_survival: True
- turn: 21
- turn_phase: TurnPhase.EVENT

## after_forced_victory_check
- did_win: True
- game_phase: GamePhase.FINISHED
- winner: red_army
- turn: 21
- turn_phase: TurnPhase.EVENT

## final_state
- turn: 21
- turn_phase: TurnPhase.EVENT
- game_phase: GamePhase.FINISHED
- current_player: player1
- winner: red_army