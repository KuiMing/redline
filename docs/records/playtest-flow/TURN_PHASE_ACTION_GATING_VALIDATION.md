# TURN PHASE ACTION GATING VALIDATION

日期：2026-06-01

- passed: True
- passed_count: 15
- failed_count: 0

## Checks
- PASS: game starts first player in event phase after base selection
  - details: {'turn': 1, 'turn_phase': 'TurnPhase.EVENT', 'current_player': 'player1'}
- PASS: direct engine base selection immediately exposes current event
  - details: {'current_event': {'id': 'trade_war', 'name': '貿易戰加劇', 'type': 'mission', 'trigger': {'type': 'buy_card', 'count': 1, 'min_cost': 4, 'card_names': ['英美奧援']}, 'success': {'type': 'topdeck_from_discard', 'count': 1}, 'failure': {'type': 'none'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '購買符合條件的卡牌（總費用 4 點以上 / 英美奧援）至少 1 次', 'success_text': '從棄牌堆選 1 張置於牌庫頂', 'failure_text': '無'}, 'event_deck_count': 24}
- PASS: formal lobby start immediately exposes current event card
  - details: {'start_result': {'success': True, 'market_mode': 'sample_53'}, 'turn_phase': <TurnPhase.EVENT: 'event'>, 'current_event': {'id': 'tibet_border_conflict', 'name': '藏印邊境軍事對峙', 'type': 'mission', 'trigger': {'type': 'build_organization', 'count': 1, 'scope': '牆內'}, 'success': {'type': 'move', 'count': 2}, 'failure': {'type': 'none'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '建立組織（牆內）至少 1 次', 'success_text': '獲得 2 次組織遷移', 'failure_text': '無'}, 'event_deck_count': 24}
- PASS: formal 2p lobby keeps turn 1 when Ben ends and passes to Red Army
  - details: {'step': 'ben_end_to_red_event', 'result': {'success': True}, 'turn': 1, 'turn_phase': <TurnPhase.EVENT: 'event'>, 'current_player': 'host', 'current_faction': 'red_army', 'event_before': 'tibet_border_conflict', 'event_after': 'tibet_border_conflict', 'event_deck_before': 24, 'event_deck_after': 24, 'event_discard_before': 1, 'event_discard_after': 1, 'event_status_after': 'active'}
- PASS: Ben end does not draw or replace event before Red Army also ends
  - details: {'step': 'ben_end_to_red_event', 'result': {'success': True}, 'turn': 1, 'turn_phase': <TurnPhase.EVENT: 'event'>, 'current_player': 'host', 'current_faction': 'red_army', 'event_before': 'tibet_border_conflict', 'event_after': 'tibet_border_conflict', 'event_deck_before': 24, 'event_deck_after': 24, 'event_discard_before': 1, 'event_discard_after': 1, 'event_status_after': 'active'}
- PASS: formal 2p lobby increments to turn 2 only after Red Army ends
  - details: {'step': 'red_end_to_next_round', 'result': {'success': True}, 'turn': 2, 'turn_phase': <TurnPhase.EVENT: 'event'>, 'current_player': 'ally', 'current_faction': 'taiwan_green', 'event_before': 'tibet_border_conflict', 'event_after': 'quiet_times', 'event_deck_before': 24, 'event_deck_after': 23, 'event_discard_before': 1, 'event_discard_after': 2, 'event_status_after': 'idle'}
- PASS: new event is drawn only after the full round ends
  - details: {'step': 'red_end_to_next_round', 'result': {'success': True}, 'turn': 2, 'turn_phase': <TurnPhase.EVENT: 'event'>, 'current_player': 'ally', 'current_faction': 'taiwan_green', 'event_before': 'tibet_border_conflict', 'event_after': 'quiet_times', 'event_deck_before': 24, 'event_deck_after': 23, 'event_discard_before': 1, 'event_discard_after': 2, 'event_status_after': 'idle'}
- PASS: event phase blocks action card play
  - details: {'error': 'Not in ACTION phase'}
- PASS: advance from event reaches action for same current player
  - details: {'turn': 1, 'game_phase': <GamePhase.MAIN: 'main'>, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'winner': None, 'current_player': 'player1', 'active_eras': [], 'active_era_details': [], 'era_notification': None, 'current_event': {'id': 'trade_war', 'name': '貿易戰加劇', 'type': 'mission', 'trigger': {'type': 'buy_card', 'count': 1, 'min_cost': 4, 'card_names': ['英美奧援']}, 'success': {'type': 'topdeck_from_discard', 'count': 1}, 'failure': {'type': 'none'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '購買符合條件的卡牌（總費用 4 點以上 / 英美奧援）至少 1 次', 'success_text': '從棄牌堆選 1 張置於牌庫頂', 'failure_text': '無'}, 'event_deck_count': 24, 'red_army_action_count': 0, 'red_army_action_limit': 2, 'event_discard_count': 1, 'event_modifiers': [], 'market_mode': 'sample_53', 'pending_base_choices': {}, 'pending_choice': None, 'faction_action_used': False, 'action_log': ['[Turn 1] Event drawn: 貿易戰加劇', '[Turn 1] player1 played 樂捐者 as resource', '[Turn 1] End of turn for player1'], 'purchase_area': ['宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥', '組織經驗丙', '南洋奧援', '樹立信心', '企畫遊說', '英美奧援'], 'static_purchase_supply': {'宣傳家': 10, '思想家': 10, '資助者': 10, '資本家': 10, '分神': 10, '內鬥': 10}, 'map': {'towns': {'北京': [{'player': 'player1', 'count': 1}], '桂林': [{'player': 'player2', 'count': 1}], '臺北': [{'player': 'player3', 'count': 1}]}, 'shared_access': {}}, 'players': [{'id': 'p1', 'name': 'player1', 'faction': 'red_army', 'base': '北京', 'resources': {'money': 1, 'propaganda': 0}, 'moves_left': 0, 'hand': ['樂捐者', '追隨者', '樂捐者', '追隨者', '追隨者'], 'deck_count': 6, 'discard_count': 0, 'discard_pile': [], 'orgs': {'北京': 1}}, {'id': 'p2', 'name': 'player2', 'faction': 'yao', 'base': '桂林', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '追隨者', '追隨者', '樂捐者', '追隨者'], 'deck_count': 5, 'discard_count': 0, 'discard_pile': [], 'orgs': {'桂林': 1}}, {'id': 'p3', 'name': 'player3', 'faction': 'taiwan_blue', 'base': '臺北', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者'], 'deck_count': 5, 'discard_count': 0, 'discard_pile': [], 'orgs': {'臺北': 1}}]}
- PASS: action phase allows current player card play
  - details: {'success': True}
- PASS: ending turn advances to next player event phase without drawing a new event
  - details: {'turn': 1, 'game_phase': <GamePhase.MAIN: 'main'>, 'turn_phase': <TurnPhase.EVENT: 'event'>, 'winner': None, 'current_player': 'player2', 'active_eras': [], 'active_era_details': [], 'era_notification': None, 'current_event': {'id': 'trade_war', 'name': '貿易戰加劇', 'type': 'mission', 'trigger': {'type': 'buy_card', 'count': 1, 'min_cost': 4, 'card_names': ['英美奧援']}, 'success': {'type': 'topdeck_from_discard', 'count': 1}, 'failure': {'type': 'none'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '購買符合條件的卡牌（總費用 4 點以上 / 英美奧援）至少 1 次', 'success_text': '從棄牌堆選 1 張置於牌庫頂', 'failure_text': '無'}, 'event_deck_count': 24, 'red_army_action_count': 0, 'red_army_action_limit': 2, 'event_discard_count': 1, 'event_modifiers': [], 'market_mode': 'sample_53', 'pending_base_choices': {}, 'pending_choice': None, 'faction_action_used': False, 'action_log': ['[Turn 1] Event drawn: 貿易戰加劇', '[Turn 1] player1 played 樂捐者 as resource', '[Turn 1] End of turn for player1'], 'purchase_area': ['宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥', '組織經驗丙', '南洋奧援', '樹立信心', '企畫遊說', '英美奧援'], 'static_purchase_supply': {'宣傳家': 10, '思想家': 10, '資助者': 10, '資本家': 10, '分神': 10, '內鬥': 10}, 'map': {'towns': {'北京': [{'player': 'player1', 'count': 1}], '桂林': [{'player': 'player2', 'count': 1}], '臺北': [{'player': 'player3', 'count': 1}]}, 'shared_access': {}}, 'players': [{'id': 'p1', 'name': 'player1', 'faction': 'red_army', 'base': '北京', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '追隨者', '紅軍奧援', '追隨者', '追隨者'], 'deck_count': 1, 'discard_count': 5, 'discard_pile': ['樂捐者', '追隨者', '樂捐者', '追隨者', '追隨者'], 'orgs': {'北京': 1}}, {'id': 'p2', 'name': 'player2', 'faction': 'yao', 'base': '桂林', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '追隨者', '追隨者', '樂捐者', '追隨者'], 'deck_count': 5, 'discard_count': 0, 'discard_pile': [], 'orgs': {'桂林': 1}}, {'id': 'p3', 'name': 'player3', 'faction': 'taiwan_blue', 'base': '臺北', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者'], 'deck_count': 5, 'discard_count': 0, 'discard_pile': [], 'orgs': {'臺北': 1}}]}
- PASS: next player event phase still blocks action until advanced
  - details: {'error': 'Not in ACTION phase'}
- PASS: next player can advance event to action without changing current player
  - details: {'turn': 1, 'game_phase': <GamePhase.MAIN: 'main'>, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'winner': None, 'current_player': 'player2', 'active_eras': [], 'active_era_details': [], 'era_notification': None, 'current_event': {'id': 'trade_war', 'name': '貿易戰加劇', 'type': 'mission', 'trigger': {'type': 'buy_card', 'count': 1, 'min_cost': 4, 'card_names': ['英美奧援']}, 'success': {'type': 'topdeck_from_discard', 'count': 1}, 'failure': {'type': 'none'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '購買符合條件的卡牌（總費用 4 點以上 / 英美奧援）至少 1 次', 'success_text': '從棄牌堆選 1 張置於牌庫頂', 'failure_text': '無'}, 'event_deck_count': 24, 'red_army_action_count': 0, 'red_army_action_limit': 2, 'event_discard_count': 1, 'event_modifiers': [], 'market_mode': 'sample_53', 'pending_base_choices': {}, 'pending_choice': None, 'faction_action_used': False, 'action_log': ['[Turn 1] Event drawn: 貿易戰加劇', '[Turn 1] player1 played 樂捐者 as resource', '[Turn 1] End of turn for player1'], 'purchase_area': ['宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥', '組織經驗丙', '南洋奧援', '樹立信心', '企畫遊說', '英美奧援'], 'static_purchase_supply': {'宣傳家': 10, '思想家': 10, '資助者': 10, '資本家': 10, '分神': 10, '內鬥': 10}, 'map': {'towns': {'北京': [{'player': 'player1', 'count': 1}], '桂林': [{'player': 'player2', 'count': 1}], '臺北': [{'player': 'player3', 'count': 1}]}, 'shared_access': {}}, 'players': [{'id': 'p1', 'name': 'player1', 'faction': 'red_army', 'base': '北京', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '追隨者', '紅軍奧援', '追隨者', '追隨者'], 'deck_count': 1, 'discard_count': 5, 'discard_pile': ['樂捐者', '追隨者', '樂捐者', '追隨者', '追隨者'], 'orgs': {'北京': 1}}, {'id': 'p2', 'name': 'player2', 'faction': 'yao', 'base': '桂林', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '追隨者', '追隨者', '樂捐者', '追隨者'], 'deck_count': 5, 'discard_count': 0, 'discard_pile': [], 'orgs': {'桂林': 1}}, {'id': 'p3', 'name': 'player3', 'faction': 'taiwan_blue', 'base': '臺北', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者'], 'deck_count': 5, 'discard_count': 0, 'discard_pile': [], 'orgs': {'臺北': 1}}]}
- PASS: red army support action can be played in event phase before purchase
  - details: {'success': True, 'pending_choice': True, 'card_moved_out_of_play': True}
- PASS: frontend enables only red support action button before purchase
  - details: {'keeps_default_cards_action_phase_guarded': True, 'allows_red_support_event_action': True, 'render_uses_per_mode_disabled_attrs': True, 'click_guard_allows_red_support_exception': True}

## Trace
### after_base_selection
- base_choices: [{'player_id': 'p2', 'label': '桂林', 'town': '桂林', 'result': {'success': True}}]
- turn: 1
- turn_phase: event
- current_player: player1
- current_event: {'id': 'trade_war', 'name': '貿易戰加劇', 'type': 'mission', 'trigger': {'type': 'buy_card', 'count': 1, 'min_cost': 4, 'card_names': ['英美奧援']}, 'success': {'type': 'topdeck_from_discard', 'count': 1}, 'failure': {'type': 'none'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '購買符合條件的卡牌（總費用 4 點以上 / 英美奧援）至少 1 次', 'success_text': '從棄牌堆選 1 張置於牌庫頂', 'failure_text': '無'}

### formal_lobby_start_event_state
- game_id: 1093e74c-87b2-4378-a2b4-b87b7337f30e
- start_result: {'success': True, 'market_mode': 'sample_53'}
- turn: 1
- turn_phase: event
- current_player: ally
- current_event: {'id': 'tibet_border_conflict', 'name': '藏印邊境軍事對峙', 'type': 'mission', 'trigger': {'type': 'build_organization', 'count': 1, 'scope': '牆內'}, 'success': {'type': 'move', 'count': 2}, 'failure': {'type': 'none'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '建立組織（牆內）至少 1 次', 'success_text': '獲得 2 次組織遷移', 'failure_text': '無'}
- event_deck_count: 24

### formal_lobby_round_flow_after_ben_turn
- round_start_player: ally
- round_start_player_index: 1
- flow: [{'step': 'ben_event_to_action', 'result': {'success': True}, 'turn': 1, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player': 'ally', 'current_faction': 'taiwan_green', 'event_before': 'tibet_border_conflict', 'event_after': 'tibet_border_conflict', 'event_deck_before': 24, 'event_deck_after': 24, 'event_discard_before': 1, 'event_discard_after': 1, 'event_status_after': 'active'}, {'step': 'ben_action_to_end', 'result': {'success': True}, 'turn': 1, 'turn_phase': <TurnPhase.END: 'end'>, 'current_player': 'ally', 'current_faction': 'taiwan_green', 'event_before': 'tibet_border_conflict', 'event_after': 'tibet_border_conflict', 'event_deck_before': 24, 'event_deck_after': 24, 'event_discard_before': 1, 'event_discard_after': 1, 'event_status_after': 'active'}, {'step': 'ben_end_to_red_event', 'result': {'success': True}, 'turn': 1, 'turn_phase': <TurnPhase.EVENT: 'event'>, 'current_player': 'host', 'current_faction': 'red_army', 'event_before': 'tibet_border_conflict', 'event_after': 'tibet_border_conflict', 'event_deck_before': 24, 'event_deck_after': 24, 'event_discard_before': 1, 'event_discard_after': 1, 'event_status_after': 'active'}, {'step': 'red_event_to_action', 'result': {'success': True}, 'turn': 1, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player': 'host', 'current_faction': 'red_army', 'event_before': 'tibet_border_conflict', 'event_after': 'tibet_border_conflict', 'event_deck_before': 24, 'event_deck_after': 24, 'event_discard_before': 1, 'event_discard_after': 1, 'event_status_after': 'active'}, {'step': 'red_action_to_end', 'result': {'success': True}, 'turn': 1, 'turn_phase': <TurnPhase.END: 'end'>, 'current_player': 'host', 'current_faction': 'red_army', 'event_before': 'tibet_border_conflict', 'event_after': 'tibet_border_conflict', 'event_deck_before': 24, 'event_deck_after': 24, 'event_discard_before': 1, 'event_discard_after': 1, 'event_status_after': 'failure'}, {'step': 'red_end_to_next_round', 'result': {'success': True}, 'turn': 2, 'turn_phase': <TurnPhase.EVENT: 'event'>, 'current_player': 'ally', 'current_faction': 'taiwan_green', 'event_before': 'tibet_border_conflict', 'event_after': 'quiet_times', 'event_deck_before': 24, 'event_deck_after': 23, 'event_discard_before': 1, 'event_discard_after': 2, 'event_status_after': 'idle'}]

### event_phase_action_attempt
- card: 樂捐者
- result: {'error': 'Not in ACTION phase'}
- turn_phase: event
- current_player: player1

### advance_event_to_action
- result: {'success': True}
- turn: 1
- turn_phase: action
- current_player: player1
- current_event: {'id': 'trade_war', 'name': '貿易戰加劇', 'type': 'mission', 'trigger': {'type': 'buy_card', 'count': 1, 'min_cost': 4, 'card_names': ['英美奧援']}, 'success': {'type': 'topdeck_from_discard', 'count': 1}, 'failure': {'type': 'none'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '購買符合條件的卡牌（總費用 4 點以上 / 英美奧援）至少 1 次', 'success_text': '從棄牌堆選 1 張置於牌庫頂', 'failure_text': '無'}

### action_phase_resource_play
- card: 樂捐者
- result: {'success': True}
- turn_phase: action
- current_player: player1

### end_turn_to_next_event
- advance_to_end: {'success': True}
- advance_to_next_event: {'success': True}
- turn: 1
- turn_phase: event
- current_player: player2
- current_event: {'id': 'trade_war', 'name': '貿易戰加劇', 'type': 'mission', 'trigger': {'type': 'buy_card', 'count': 1, 'min_cost': 4, 'card_names': ['英美奧援']}, 'success': {'type': 'topdeck_from_discard', 'count': 1}, 'failure': {'type': 'none'}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '購買符合條件的卡牌（總費用 4 點以上 / 英美奧援）至少 1 次', 'success_text': '從棄牌堆選 1 張置於牌庫頂', 'failure_text': '無'}

### next_player_event_phase_action_attempt
- card: 追隨者
- result: {'error': 'Not in ACTION phase'}
- turn_phase: event
- current_player: player2

### next_player_advance_event_to_action
- result: {'success': True}
- turn: 1
- turn_phase: action
- current_player: player2

### red_support_event_phase_action_before_purchase
- result: {'success': True, 'pending_choice': True, 'card_moved_out_of_play': True}
- turn_phase: event
- pending_choice: {'type': 'target_choice', 'choice_key': 'red_support_target_player', 'player_id': 'red', 'prompt': '紅軍奧援：請選擇要將本牌放入哪位反共玩家的棄牌堆。', 'source_name': '紅軍奧援', 'count': None, 'min_count': None, 'mode': 'action', 'acting_player_id': None, 'acting_player_name': None, 'played_card_name': None, 'region': None, 'free': None, 'ignore_distance': None, 'cards': [], 'options': [], 'towns': [], 'targets': [{'id': 'ben', 'label': 'BEN'}], 'step': None}
- hand: []

### frontend_hand_button_red_support_event_exception
- keeps_default_cards_action_phase_guarded: True
- allows_red_support_event_action: True
- render_uses_per_mode_disabled_attrs: True
- click_guard_allows_red_support_exception: True
