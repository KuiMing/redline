# TURN PHASE ACTION GATING VALIDATION

日期：2026-06-01

- passed: True
- passed_count: 14
- failed_count: 0

## Checks
- PASS: game opens first player in ACTION phase with round event drawn
  - details: {'turn': 1, 'turn_phase': 'TurnPhase.ACTION', 'current_player': 'player1', 'current_event': 'tibet_border_conflict'}
- PASS: direct engine base selection immediately exposes current event
  - details: {'current_event': {'id': 'tibet_border_conflict', 'name': '藏印邊境軍事對峙', 'type': 'mission', 'trigger': {'type': 'build_organization', 'count': 1, 'scope': '牆內'}, 'success': {'type': 'move', 'count': 2}, 'failure': {'type': 'none'}, 'effect': {}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '建立組織（牆內）至少 1 次', 'success_text': '非紅軍：獲得 2 次組織遷移', 'failure_text': '無', 'effect_text': '無'}, 'event_deck_count': 19}
- PASS: formal lobby start immediately exposes current event card in ACTION phase
  - details: {'start_result': {'success': True, 'market_mode': 'sample_53'}, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_event': {'id': 'major_disaster', 'name': '重大災難', 'type': 'mission', 'trigger': {'type': 'play_card_with_propaganda', 'count': 1}, 'success': {'type': 'gain_card', 'card': '宣傳家', 'count': 1}, 'failure': {'type': 'discard_self', 'count': 1}, 'effect': {}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '打出購買費用含宣傳的卡牌至少 1 次', 'success_text': '非紅軍：獲得 1 張宣傳家', 'failure_text': '紅軍：選 1 張手牌棄掉', 'effect_text': '無'}, 'event_deck_count': 19}
- PASS: formal 2p lobby keeps turn 1 when first player ends and passes to the other
  - details: {'step': 'first_player_action_phase_end', 'result': {'success': True}, 'turn': 1, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player': 'host', 'current_faction': 'red_army', 'event_before': 'quiet_times', 'event_after': 'quiet_times', 'event_deck_before': 19, 'event_deck_after': 19, 'event_discard_before': 1, 'event_discard_after': 1, 'event_status_after': 'idle'}
- PASS: first player end does not draw or replace event before the round wraps
  - details: {'step': 'first_player_action_phase_end', 'result': {'success': True}, 'turn': 1, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player': 'host', 'current_faction': 'red_army', 'event_before': 'quiet_times', 'event_after': 'quiet_times', 'event_deck_before': 19, 'event_deck_after': 19, 'event_discard_before': 1, 'event_discard_after': 1, 'event_status_after': 'idle'}
- PASS: formal 2p lobby increments to turn 2 only after the full round ends
  - details: {'step': 'second_player_action_phase_end_wraps_round', 'result': {'success': True}, 'turn': 2, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player': 'ally', 'current_faction': 'taiwan_green', 'event_before': 'quiet_times', 'event_after': 'tibet_border_conflict', 'event_deck_before': 19, 'event_deck_after': 18, 'event_discard_before': 1, 'event_discard_after': 2, 'event_status_after': 'active'}
- PASS: new event is drawn only after the full round ends
  - details: {'step': 'second_player_action_phase_end_wraps_round', 'result': {'success': True}, 'turn': 2, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player': 'ally', 'current_faction': 'taiwan_green', 'event_before': 'quiet_times', 'event_after': 'tibet_border_conflict', 'event_deck_before': 19, 'event_deck_after': 18, 'event_discard_before': 1, 'event_discard_after': 2, 'event_status_after': 'active'}
- PASS: action phase allows current player card play
  - details: {'success': True}
- PASS: ending turn passes to next player in ACTION without drawing a new event mid-round
  - details: {'turn': 1, 'game_phase': <GamePhase.MAIN: 'main'>, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'winner': None, 'co_winners': [], 'hk_free_base_relocation': False, 'current_player': 'player2', 'active_eras': [], 'active_era_details': [], 'my_era_stage': None, 'era_notification': None, 'current_event': {'id': 'tibet_border_conflict', 'name': '藏印邊境軍事對峙', 'type': 'mission', 'trigger': {'type': 'build_organization', 'count': 1, 'scope': '牆內'}, 'success': {'type': 'move', 'count': 2}, 'failure': {'type': 'none'}, 'effect': {}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '建立組織（牆內）至少 1 次', 'success_text': '非紅軍：獲得 2 次組織遷移', 'failure_text': '無', 'effect_text': '無'}, 'event_deck_count': 19, 'red_army_action_count': 0, 'red_army_action_limit': 2, 'red_army_base_build_blocks': [], 'pending_topdeck_uses': 0, 'topdeck_candidates_count': 0, 'event_discard_count': 1, 'event_modifiers': [], 'market_mode': 'sample_53', 'pending_base_choices': {}, 'pending_choice': None, 'faction_action_used': False, 'action_log': ['[Turn 1] Event drawn: 藏印邊境軍事對峙', '[Turn 1] player1 played 樂捐者 as resource', '[Turn 1] End of turn for player1', '[Turn 1] player2 played 追隨者 as resource'], 'purchase_area': ['宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥', '臺灣奧援', '行動募資', '歐洲奧援', '合作談判', '武裝者'], 'purchase_area_variants': [None, None, None, None, None, None, {'variant_index': 0, 'support_region': '臺灣', 'tier2_regions': ['東洋', '南洋']}, None, {'variant_index': 1, 'support_region': '歐洲', 'tier2_regions': ['英美', '南洋']}, None, None], 'purchase_area_costs': [{'money': 0, 'propaganda': 3}, {'money': 0, 'propaganda': 5}, {'money': 2, 'propaganda': 1}, {'money': 3, 'propaganda': 2}, {'money': 0, 'propaganda': 0}, {'money': 0, 'propaganda': 0}, {'money': 1, 'propaganda': 2}, {'money': 1, 'propaganda': 3}, {'money': 1, 'propaganda': 2}, {'money': 2, 'propaganda': 2}, {'money': 2, 'propaganda': 0}], 'purchase_area_payments': [{'money': 0, 'propaganda': 3}, {'money': 0, 'propaganda': 5}, {'money': 2, 'propaganda': 1}, {'money': 3, 'propaganda': 2}, {'money': 0, 'propaganda': 0}, {'money': 0, 'propaganda': 0}, {'money': 1, 'propaganda': 2}, {'money': 1, 'propaganda': 3}, {'money': 1, 'propaganda': 2}, {'money': 2, 'propaganda': 2}, {'money': 2, 'propaganda': 0}], 'purchase_area_affordable': [False, False, False, False, True, True, False, False, False, False, False], 'static_purchase_supply': {'宣傳家': 15, '思想家': 15, '資助者': 15, '資本家': 15, '分神': 30, '內鬥': 20}, 'map': {'towns': {'北京': [{'player': 'player1', 'count': 1}], '桂林': [{'player': 'player2', 'count': 1}], '臺北': [{'player': 'player3', 'count': 1}]}, 'shared_access': {}, 'legal_organization_moves': {}}, 'players': [{'id': 'p1', 'name': 'player1', 'faction': 'red_army', 'base': '北京', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者'], 'hand_variants': [None, None, None, None, None], 'hand_action_legality': [{'playable': True}, {'playable': True}, {'playable': True}, {'playable': True}, {'playable': True}], 'deck_count': 5, 'discard_count': 1, 'discard_pile': ['樂捐者'], 'discard_variants': [None], 'organization_counts': {'total': 1, 'inside_wall': 1, 'outside_wall': 0}, 'orgs': {'北京': 1}}, {'id': 'p2', 'name': 'player2', 'faction': 'yao', 'base': '桂林', 'resources': {'money': 0, 'propaganda': 1}, 'moves_left': 0, 'hand': ['追隨者', '追隨者', '追隨者', '樂捐者', '追隨者'], 'hand_variants': [None, None, None, None, None], 'hand_action_legality': [{'playable': True}, {'playable': True}, {'playable': True}, {'playable': True}, {'playable': True}], 'deck_count': 5, 'discard_count': 0, 'discard_pile': [], 'discard_variants': [], 'organization_counts': {'total': 1, 'inside_wall': 1, 'outside_wall': 0}, 'orgs': {'桂林': 1}}, {'id': 'p3', 'name': 'player3', 'faction': 'taiwan_blue', 'base': '臺北', 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'hand': ['追隨者', '樂捐者', '追隨者', '追隨者', '追隨者'], 'hand_variants': [None, None, None, None, None], 'hand_action_legality': [{'playable': True}, {'playable': True}, {'playable': True}, {'playable': True}, {'playable': True}], 'deck_count': 5, 'discard_count': 0, 'discard_pile': [], 'discard_variants': [], 'organization_counts': {'total': 1, 'inside_wall': 0, 'outside_wall': 1}, 'orgs': {'臺北': 1}}]}
- PASS: next player is in ACTION and can play a card
  - details: {'success': True}
- PASS: play and buy freely interleave inside one action phase without advancing
  - details: {'results': [{'success': True}, {'success': True, 'purchased_cards': ['宣傳家'], 'payment': {'money': 0, 'propaganda': 3}}, {'success': True}, {'success': True, 'purchased_cards': ['宣傳家'], 'payment': {'money': 0, 'propaganda': 3}}], 'steps': [{'op': 'play_card', 'card': '樂捐者', 'result': {'success': True}, 'turn_phase': 'TurnPhase.ACTION', 'current_player': 'alpha'}, {'op': 'buy_cards', 'result': {'success': True, 'purchased_cards': ['宣傳家'], 'payment': {'money': 0, 'propaganda': 3}}, 'turn_phase': 'TurnPhase.ACTION', 'current_player': 'alpha'}, {'op': 'play_card', 'card': '樂捐者', 'result': {'success': True}, 'turn_phase': 'TurnPhase.ACTION', 'current_player': 'alpha'}, {'op': 'buy_cards', 'result': {'success': True, 'purchased_cards': ['宣傳家'], 'payment': {'money': 0, 'propaganda': 3}}, 'turn_phase': 'TurnPhase.ACTION', 'current_player': 'alpha'}]}
- PASS: one advance ends the action phase: hand refilled to 5 and seat passed on
  - details: {'result': {'success': True}, 'actor_hand_size': 5, 'current_player': 'bravo', 'turn_phase': <TurnPhase.ACTION: 'action'>}
- PASS: red army support action can be played in event phase before purchase
  - details: {'success': True, 'pending_choice': True, 'card_moved_out_of_play': True}
- PASS: frontend enables only red support action button before purchase
  - details: {'keeps_default_cards_action_phase_guarded': True, 'allows_red_support_event_action': True, 'render_uses_per_mode_disabled_attrs': True, 'click_guard_allows_red_support_exception': True}

## Trace
### after_base_selection
- base_choices: [{'player_id': 'p2', 'label': '桂林', 'town': '桂林', 'result': {'success': True}}]
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player1
- current_event: {'id': 'tibet_border_conflict', 'name': '藏印邊境軍事對峙', 'type': 'mission', 'trigger': {'type': 'build_organization', 'count': 1, 'scope': '牆內'}, 'success': {'type': 'move', 'count': 2}, 'failure': {'type': 'none'}, 'effect': {}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '建立組織（牆內）至少 1 次', 'success_text': '非紅軍：獲得 2 次組織遷移', 'failure_text': '無', 'effect_text': '無'}

### formal_lobby_start_event_state
- game_id: e2494d0e-ca7d-49fd-9fa0-c827beb17c0a
- start_result: {'success': True, 'market_mode': 'sample_53'}
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: ally
- current_event: {'id': 'major_disaster', 'name': '重大災難', 'type': 'mission', 'trigger': {'type': 'play_card_with_propaganda', 'count': 1}, 'success': {'type': 'gain_card', 'card': '宣傳家', 'count': 1}, 'failure': {'type': 'discard_self', 'count': 1}, 'effect': {}, 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'status': 'active', 'result_text': '非紅軍任務進行中', 'trigger_text': '打出購買費用含宣傳的卡牌至少 1 次', 'success_text': '非紅軍：獲得 1 張宣傳家', 'failure_text': '紅軍：選 1 張手牌棄掉', 'effect_text': '無'}
- event_deck_count: 19

### formal_lobby_round_flow
- round_start_player: ally
- round_start_player_index: 1
- flow: [{'step': 'first_player_action_phase_end', 'result': {'success': True}, 'turn': 1, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player': 'host', 'current_faction': 'red_army', 'event_before': 'quiet_times', 'event_after': 'quiet_times', 'event_deck_before': 19, 'event_deck_after': 19, 'event_discard_before': 1, 'event_discard_after': 1, 'event_status_after': 'idle'}, {'step': 'second_player_action_phase_end_wraps_round', 'result': {'success': True}, 'turn': 2, 'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player': 'ally', 'current_faction': 'taiwan_green', 'event_before': 'quiet_times', 'event_after': 'tibet_border_conflict', 'event_deck_before': 19, 'event_deck_after': 18, 'event_discard_before': 1, 'event_discard_after': 2, 'event_status_after': 'active'}]

### action_phase_card_play
- card: 樂捐者
- result: {'success': True}
- turn_phase: TurnPhase.ACTION
- current_player: player1

### end_passes_to_next_player_action
- turn: 1
- turn_phase: TurnPhase.ACTION
- current_player: player2
- current_event: tibet_border_conflict

### next_player_action_play
- card: 追隨者
- result: {'success': True}
- turn_phase: TurnPhase.ACTION
- current_player: player2

### action_phase_allows_free_interleaving_of_play_and_buy
- actor: alpha
- steps: [{'op': 'play_card', 'card': '樂捐者', 'result': {'success': True}, 'turn_phase': 'TurnPhase.ACTION', 'current_player': 'alpha'}, {'op': 'buy_cards', 'result': {'success': True, 'purchased_cards': ['宣傳家'], 'payment': {'money': 0, 'propaganda': 3}}, 'turn_phase': 'TurnPhase.ACTION', 'current_player': 'alpha'}, {'op': 'play_card', 'card': '樂捐者', 'result': {'success': True}, 'turn_phase': 'TurnPhase.ACTION', 'current_player': 'alpha'}, {'op': 'buy_cards', 'result': {'success': True, 'purchased_cards': ['宣傳家'], 'payment': {'money': 0, 'propaganda': 3}}, 'turn_phase': 'TurnPhase.ACTION', 'current_player': 'alpha'}]

### single_advance_ends_action_phase_and_passes_seat
- result: {'success': True}
- turn_phase: TurnPhase.ACTION
- current_player: bravo
- actor_hand_size: 5

### red_support_event_phase_action_before_purchase
- result: {'success': True, 'pending_choice': True, 'card_moved_out_of_play': True}
- turn_phase: TurnPhase.EVENT
- pending_choice: {'type': 'target_choice', 'choice_key': 'red_support_target_player', 'interaction_kind': None, 'remaining_builds': None, 'queueable_card_names': [], 'cancellable': False, 'player_id': 'red', 'player_name': None, 'prompt': '紅軍奧援：請選擇要將本牌放入哪位反共玩家的棄牌堆。', 'source_name': '紅軍奧援', 'count': None, 'min_count': None, 'mode': None, 'acting_player_id': None, 'acting_player_name': None, 'played_card_name': None, 'region': None, 'free': None, 'ignore_distance': None, 'cards': [], 'options': [], 'towns': [], 'targets': [{'id': 'ben', 'label': 'BEN'}], 'step': None}
- hand: []

### frontend_hand_button_red_support_event_exception
- keeps_default_cards_action_phase_guarded: True
- allows_red_support_event_action: True
- render_uses_per_mode_disabled_attrs: True
- click_guard_allows_red_support_exception: True
