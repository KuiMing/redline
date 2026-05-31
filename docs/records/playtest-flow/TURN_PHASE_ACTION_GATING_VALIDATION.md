# TURN PHASE ACTION GATING VALIDATION

日期：2026-05-31

- passed: True
- passed_count: 7
- failed_count: 0

## Checks
- PASS: game starts first player in event phase after base selection
  - details: {'turn': 1, 'turn_phase': 'TurnPhase.EVENT', 'current_player': 'player1'}
- PASS: event phase blocks action card play
  - details: {'error': 'Not in ACTION phase'}
- PASS: advance from event reaches action for same current player
  - details: {'turn': 1, 'game_phase': <GamePhase.MAIN: 'main'>, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'winner': None, 'current_player': 'player1', 'active_eras': [], 'active_era_details': [], 'era_notification': None, 'current_event': {'id': 'trade_war', 'name': '貿易戰加劇', 'type': 'mission', 'trigger': {'type': 'buy_card', 'count': 1, 'min_cost': 4, 'card_names': ['英美奧援']}, 'success': {'type': 'topdeck_from_discard', 'count': 1}, 'failure': {'type': 'none'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '購買符合條件的卡牌（總費用 4 點以上 / 英美奧援）至少 1 次', 'success_text': '從棄牌堆選 1 張置於牌庫頂', 'failure_text': '無'}, 'event_deck_count': 24, 'red_army_action_count': 0, 'red_army_action_limit': 2, 'event_discard_count': 1, 'event_modifiers': [], 'market_mode': 'sample_53', 'pending_base_choices': {}, 'pending_choice': None, 'faction_action_used': False, 'action_log': ['[Turn 1] Event drawn: 貿易戰加劇', '[Turn 1] player1 played 樂捐者 as resource', '[Turn 1] Event failure: no effect', '[Turn 1] End of turn for player1', '[Turn 1] Event drawn: 全國人大召開'], 'purchase_area': ['宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥', '組織經驗丙', '南洋奧援', '樹立信心', '企畫遊說', '英美奧援'], 'static_purchase_supply': {'宣傳家': 1, '思想家': 1, '資助者': 1, '資本家': 1, '分神': 1, '內鬥': 1}, 'map': {'towns': {'北京': [{'player': 'player1', 'count': 1}], '桂林': [{'player': 'player2', 'count': 1}], '臺北': [{'player': 'player3', 'count': 1}]}, 'shared_access': {}}, 'players': [{'id': 'p1', 'name': 'player1', 'faction': 'red_army', 'base': '北京', 'resources': {'money': 1, 'propaganda': 0}, 'moves_left': 0, 'hand': ['樂捐者', '追隨者', '樂捐者', '追隨者', '追隨者'], 'deck_count': 6, 'discard_count': 0, 'discard_pile': [], 'orgs': {'北京': 1}}, {'id': 'p2', 'name': 'player2', 'faction': 'yao', 'base': '桂林', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '追隨者', '追隨者', '樂捐者', '追隨者'], 'deck_count': 5, 'discard_count': 0, 'discard_pile': [], 'orgs': {'桂林': 1}}, {'id': 'p3', 'name': 'player3', 'faction': 'taiwan_blue', 'base': '臺北', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者'], 'deck_count': 5, 'discard_count': 0, 'discard_pile': [], 'orgs': {'臺北': 1}}]}
- PASS: action phase allows current player card play
  - details: {'success': True}
- PASS: ending turn advances to next player event phase
  - details: {'turn': 1, 'game_phase': <GamePhase.MAIN: 'main'>, 'turn_phase': <TurnPhase.EVENT: 'event'>, 'winner': None, 'current_player': 'player2', 'active_eras': [], 'active_era_details': [], 'era_notification': None, 'current_event': {'id': 'national_people_congress', 'name': '全國人大召開', 'type': 'mission', 'trigger': {'type': 'use_faction_ability', 'count': 1}, 'success': {'type': 'draw', 'count': 1}, 'failure': {'type': 'red_dissolve', 'count': 1, 'scope': '牆內'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '使用或觸發陣營特殊能力至少 1 次', 'success_text': '抽 1 張牌', 'failure_text': '紅軍瓦解 1 個組織'}, 'event_deck_count': 23, 'red_army_action_count': 0, 'red_army_action_limit': 2, 'event_discard_count': 2, 'event_modifiers': [], 'market_mode': 'sample_53', 'pending_base_choices': {}, 'pending_choice': None, 'faction_action_used': False, 'action_log': ['[Turn 1] Event drawn: 貿易戰加劇', '[Turn 1] player1 played 樂捐者 as resource', '[Turn 1] Event failure: no effect', '[Turn 1] End of turn for player1', '[Turn 1] Event drawn: 全國人大召開'], 'purchase_area': ['宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥', '組織經驗丙', '南洋奧援', '樹立信心', '企畫遊說', '英美奧援'], 'static_purchase_supply': {'宣傳家': 1, '思想家': 1, '資助者': 1, '資本家': 1, '分神': 1, '內鬥': 1}, 'map': {'towns': {'北京': [{'player': 'player1', 'count': 1}], '桂林': [{'player': 'player2', 'count': 1}], '臺北': [{'player': 'player3', 'count': 1}]}, 'shared_access': {}}, 'players': [{'id': 'p1', 'name': 'player1', 'faction': 'red_army', 'base': '北京', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '追隨者', '紅軍奧援', '追隨者', '追隨者'], 'deck_count': 1, 'discard_count': 5, 'discard_pile': ['樂捐者', '追隨者', '樂捐者', '追隨者', '追隨者'], 'orgs': {'北京': 1}}, {'id': 'p2', 'name': 'player2', 'faction': 'yao', 'base': '桂林', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '追隨者', '追隨者', '樂捐者', '追隨者'], 'deck_count': 5, 'discard_count': 0, 'discard_pile': [], 'orgs': {'桂林': 1}}, {'id': 'p3', 'name': 'player3', 'faction': 'taiwan_blue', 'base': '臺北', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者'], 'deck_count': 5, 'discard_count': 0, 'discard_pile': [], 'orgs': {'臺北': 1}}]}
- PASS: next player event phase still blocks action until advanced
  - details: {'error': 'Not in ACTION phase'}
- PASS: next player can advance event to action without changing current player
  - details: {'turn': 1, 'game_phase': <GamePhase.MAIN: 'main'>, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'winner': None, 'current_player': 'player2', 'active_eras': [], 'active_era_details': [], 'era_notification': None, 'current_event': {'id': 'national_people_congress', 'name': '全國人大召開', 'type': 'mission', 'trigger': {'type': 'use_faction_ability', 'count': 1}, 'success': {'type': 'draw', 'count': 1}, 'failure': {'type': 'red_dissolve', 'count': 1, 'scope': '牆內'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '使用或觸發陣營特殊能力至少 1 次', 'success_text': '抽 1 張牌', 'failure_text': '紅軍瓦解 1 個組織'}, 'event_deck_count': 23, 'red_army_action_count': 0, 'red_army_action_limit': 2, 'event_discard_count': 2, 'event_modifiers': [], 'market_mode': 'sample_53', 'pending_base_choices': {}, 'pending_choice': None, 'faction_action_used': False, 'action_log': ['[Turn 1] Event drawn: 貿易戰加劇', '[Turn 1] player1 played 樂捐者 as resource', '[Turn 1] Event failure: no effect', '[Turn 1] End of turn for player1', '[Turn 1] Event drawn: 全國人大召開'], 'purchase_area': ['宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥', '組織經驗丙', '南洋奧援', '樹立信心', '企畫遊說', '英美奧援'], 'static_purchase_supply': {'宣傳家': 1, '思想家': 1, '資助者': 1, '資本家': 1, '分神': 1, '內鬥': 1}, 'map': {'towns': {'北京': [{'player': 'player1', 'count': 1}], '桂林': [{'player': 'player2', 'count': 1}], '臺北': [{'player': 'player3', 'count': 1}]}, 'shared_access': {}}, 'players': [{'id': 'p1', 'name': 'player1', 'faction': 'red_army', 'base': '北京', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '追隨者', '紅軍奧援', '追隨者', '追隨者'], 'deck_count': 1, 'discard_count': 5, 'discard_pile': ['樂捐者', '追隨者', '樂捐者', '追隨者', '追隨者'], 'orgs': {'北京': 1}}, {'id': 'p2', 'name': 'player2', 'faction': 'yao', 'base': '桂林', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '追隨者', '追隨者', '樂捐者', '追隨者'], 'deck_count': 5, 'discard_count': 0, 'discard_pile': [], 'orgs': {'桂林': 1}}, {'id': 'p3', 'name': 'player3', 'faction': 'taiwan_blue', 'base': '臺北', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者'], 'deck_count': 5, 'discard_count': 0, 'discard_pile': [], 'orgs': {'臺北': 1}}]}

## Trace
### after_base_selection
- base_choices: [{'player_id': 'p2', 'label': '桂林', 'town': '桂林', 'result': {'success': True}}]
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: player1
- current_event: {'id': 'trade_war', 'name': '貿易戰加劇', 'type': 'mission', 'trigger': {'type': 'buy_card', 'count': 1, 'min_cost': 4, 'card_names': ['英美奧援']}, 'success': {'type': 'topdeck_from_discard', 'count': 1}, 'failure': {'type': 'none'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '購買符合條件的卡牌（總費用 4 點以上 / 英美奧援）至少 1 次', 'success_text': '從棄牌堆選 1 張置於牌庫頂', 'failure_text': '無'}

### event_phase_action_attempt
- card: 樂捐者
- result: {'error': 'Not in ACTION phase'}
- turn_phase: TurnPhase.EVENT
- current_player: player1

### advance_event_to_action
- result: {'success': True}
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player1
- current_event: {'id': 'trade_war', 'name': '貿易戰加劇', 'type': 'mission', 'trigger': {'type': 'buy_card', 'count': 1, 'min_cost': 4, 'card_names': ['英美奧援']}, 'success': {'type': 'topdeck_from_discard', 'count': 1}, 'failure': {'type': 'none'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '購買符合條件的卡牌（總費用 4 點以上 / 英美奧援）至少 1 次', 'success_text': '從棄牌堆選 1 張置於牌庫頂', 'failure_text': '無'}

### action_phase_resource_play
- card: 樂捐者
- result: {'success': True}
- turn_phase: TurnPhase.ACTION
- current_player: player1

### end_turn_to_next_event
- advance_to_end: {'success': True}
- advance_to_next_event: {'success': True}
- turn: 1
- turn_phase: TurnPhase.EVENT
- current_player: player2
- current_event: {'id': 'national_people_congress', 'name': '全國人大召開', 'type': 'mission', 'trigger': {'type': 'use_faction_ability', 'count': 1}, 'success': {'type': 'draw', 'count': 1}, 'failure': {'type': 'red_dissolve', 'count': 1, 'scope': '牆內'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '使用或觸發陣營特殊能力至少 1 次', 'success_text': '抽 1 張牌', 'failure_text': '紅軍瓦解 1 個組織'}

### next_player_event_phase_action_attempt
- card: 追隨者
- result: {'error': 'Not in ACTION phase'}
- turn_phase: TurnPhase.EVENT
- current_player: player2

### next_player_advance_event_to_action
- result: {'success': True}
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player2
