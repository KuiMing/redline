# FULL GAMEPLAY 4P VALIDATION

日期：2026-05-03

## base_selection_choice
- choice: {'player_id': 'p1', 'label': '任意牆內', 'town': '三亞', 'result': {'success': True}}

## base_selection_choice
- choice: {'player_id': 'p3', 'label': '潮州', 'town': '潮州', 'result': {'success': True}}

## base_selection_resolution
- initial_pending: {'p1': {'labels': ['任意牆內', '任意南洋', '任意英美城鎮'], 'resolved': {'任意牆內': ['三亞', '上海', '北京', '南京', '南寧', '南昌', '南陽', '合肥', '天津', '太原', '奇臺', '廈門', '廣州', '延安', '徐州', '德宏', '成都', '敦煌', '昆明', '昌吉', '杭州', '桂林', '梅州', '武漢', '海口', '深圳', '湛茂', '溫州', '潮州', '澳門', '濟南', '石家莊', '福州', '蘭州', '西安', '西寧', '西雙版納', '貴陽', '鄭州', '重慶', '銀川', '長沙', '青島'], '任意南洋': ['曼谷', '吉隆坡', '新加坡', '雅加達', '河內', '胡志明市', '仰光'], '任意英美城鎮': ['華盛頓', '紐約', '多倫多', '卡加利', '溫哥華', '舊金山', '洛杉磯']}}, 'p3': {'labels': ['潮州', '任意南洋', '任意英美城鎮'], 'resolved': {'潮州': ['潮州'], '任意南洋': ['曼谷', '吉隆坡', '新加坡', '雅加達', '河內', '胡志明市', '仰光'], '任意英美城鎮': ['華盛頓', '紐約', '多倫多', '卡加利', '溫哥華', '舊金山', '洛杉磯']}}}
- remaining_pending: {}
- game_phase_after_selection: GamePhase.MAIN

## init
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: player1
- base_validation: {'rows': [{'player': 'player1', 'faction': 'republican', 'base': '三亞', 'orgs': {'三亞': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['三亞', '上海', '上粉沙打', '丹東', '九龍城', '仰光', '伊寧', '佳木斯', '倫敦', '元朗', '克孜勒蘇', '克拉瑪依']}, {'player': 'player2', 'faction': 'red_army', 'base': '北京', 'orgs': {'北京': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['北京']}, {'player': 'player3', 'faction': 'chaoshan', 'base': '潮州', 'orgs': {'潮州': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['仰光', '倫敦', '卡加利', '吉隆坡', '多倫多', '新加坡', '曼谷', '河內', '洛杉磯', '溫哥華', '潮州', '紐約']}, {'player': 'player4', 'faction': 'taiwan_green', 'base': '臺北', 'orgs': {'臺北': 1}, 'single_base_org': True, 'base_allowed': True, 'allowed_sample': ['臺北']}], 'unique_bases': True}

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
- faction: republican
- hand_before: ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者']
- hand_after: ['樂捐者', '追隨者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_1_move
- player: player1
- move_detail: None
- result: {'skipped': True}
- orgs_after: {'三亞': 1}
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
- faction: red_army
- hand_before: ['追隨者', '追隨者', '追隨者', '追隨者', '樂捐者']
- hand_after: ['追隨者', '追隨者', '追隨者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_2_move
- player: player2
- move_detail: None
- result: {'skipped': True}
- orgs_after: {'北京': 1}
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
- faction: chaoshan
- hand_before: ['樂捐者', '追隨者', '追隨者', '樂捐者', '追隨者']
- hand_after: ['追隨者', '追隨者', '樂捐者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_3_move
- player: player3
- move_detail: None
- result: {'skipped': True}
- orgs_after: {'潮州': 1}
- moves_left_after: 0

## cycle_3_advance_to_end
- turn: 1
- turn_phase: TurnPhase.END
- current_player: player3

## cycle_3_end_turn
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: player4

## cycle_4_advance_to_action_before
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: player4

## cycle_4_advance_to_action_after
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player4

## cycle_4_play_card
- player: player4
- faction: taiwan_green
- hand_before: ['追隨者', '追隨者', '樂捐者', '追隨者', '樂捐者']
- hand_after: ['追隨者', '樂捐者', '追隨者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_4_move
- player: player4
- move_detail: None
- result: {'skipped': True}
- orgs_after: {'臺北': 1}
- moves_left_after: 0

## cycle_4_advance_to_end
- turn: 1
- turn_phase: TurnPhase.END
- current_player: player4

## cycle_4_end_turn
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: player1

## cycle_5_advance_to_action_before
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: player1

## cycle_5_advance_to_action_after
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player1

## cycle_5_play_card
- player: player1
- faction: republican
- hand_before: ['樂捐者', '追隨者', '追隨者', '樂捐者', '追隨者']
- hand_after: ['追隨者', '追隨者', '樂捐者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_5_move
- player: player1
- move_detail: None
- result: {'skipped': True}
- orgs_after: {'三亞': 1}
- moves_left_after: 0

## cycle_5_advance_to_end
- turn: 2
- turn_phase: TurnPhase.END
- current_player: player1

## cycle_5_end_turn
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: player2

## cycle_6_advance_to_action_before
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: player2

## cycle_6_advance_to_action_after
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player2

## cycle_6_play_card
- player: player2
- faction: red_army
- hand_before: ['樂捐者', '追隨者', '樂捐者', '追隨者', '追隨者']
- hand_after: ['追隨者', '樂捐者', '追隨者', '追隨者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_6_move
- player: player2
- move_detail: None
- result: {'skipped': True}
- orgs_after: {'北京': 1}
- moves_left_after: 0

## cycle_6_advance_to_end
- turn: 2
- turn_phase: TurnPhase.END
- current_player: player2

## cycle_6_end_turn
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: player3

## cycle_7_advance_to_action_before
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: player3

## cycle_7_advance_to_action_after
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player3

## cycle_7_play_card
- player: player3
- faction: chaoshan
- hand_before: ['追隨者', '樂捐者', '追隨者', '追隨者', '樂捐者']
- hand_after: ['樂捐者', '追隨者', '追隨者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_7_move
- player: player3
- move_detail: None
- result: {'skipped': True}
- orgs_after: {'潮州': 1}
- moves_left_after: 0

## cycle_7_advance_to_end
- turn: 2
- turn_phase: TurnPhase.END
- current_player: player3

## cycle_7_end_turn
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: player4

## cycle_8_advance_to_action_before
- turn: 2
- turn_phase: TurnPhase.EVENT
- current_player: player4

## cycle_8_advance_to_action_after
- turn: 2
- turn_phase: TurnPhase.ACTION
- current_player: player4

## cycle_8_play_card
- player: player4
- faction: taiwan_green
- hand_before: ['追隨者', '追隨者', '追隨者', '追隨者', '樂捐者']
- hand_after: ['追隨者', '追隨者', '追隨者', '樂捐者']
- result: {'success': True}
- resources: {'money': 0, 'propaganda': 0}
- moves_left: 0

## cycle_8_move
- player: player4
- move_detail: None
- result: {'skipped': True}
- orgs_after: {'臺北': 1}
- moves_left_after: 0

## cycle_8_advance_to_end
- turn: 2
- turn_phase: TurnPhase.END
- current_player: player4

## cycle_8_end_turn
- turn: 3
- turn_phase: TurnPhase.EVENT
- current_player: player1

## before_forced_victory_check
- candidate: player4
- faction: taiwan_green
- org_count: 14
- forced_red_survival: False
- turn: 3
- turn_phase: TurnPhase.EVENT

## after_forced_victory_check
- did_win: True
- game_phase: GamePhase.FINISHED
- winner: player4
- turn: 3
- turn_phase: TurnPhase.EVENT

## final_state
- turn: 3
- turn_phase: TurnPhase.EVENT
- game_phase: GamePhase.FINISHED
- current_player: player1
- winner: player4