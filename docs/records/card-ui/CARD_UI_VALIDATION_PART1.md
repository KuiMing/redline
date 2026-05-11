# CARD UI VALIDATION PART 1

日期：2026-05-03

## 2 人
- start_result: {'success': True}
- current_player: host
- turn_phase: event -> action
- host hand count: 5 -> 4
- guest hand counts: {'guest2': 5}
- illegal_play: {'guest': 'guest2', 'hand_before': ['追隨者', '追隨者', '追隨者', '樂捐者', '追隨者'], 'error_before': None, 'error_after': 'Not your turn', 'log_same': True}
- chosen_card: 追隨者
- host_log_changed: True
- hud_changed: True
- hud_before: TURN 1 | PHASE action | ACTIVE HOST | HAND 5 | MONEY 0 | PROP 0 | MOVES 3 | HOST: 2 | GUEST2: 2 |
- hud_after: TURN 1 | PHASE action | ACTIVE HOST | HAND 4 | MONEY 0 | PROP 0 | MOVES 3 | HOST: 2 | GUEST2: 2 |
- host_state_after_player_count: 2

## 3 人
- start_result: {'success': True}
- current_player: host
- turn_phase: event -> action
- host hand count: 5 -> 4
- guest hand counts: {'guest2': 5, 'guest3': 5}
- illegal_play: {'guest': 'guest2', 'hand_before': ['樂捐者', '樂捐者', '追隨者', '追隨者', '追隨者'], 'error_before': None, 'error_after': 'Not your turn', 'log_same': True}
- chosen_card: 追隨者
- host_log_changed: True
- hud_changed: True
- hud_before: TURN 1 | PHASE action | ACTIVE HOST | HAND 5 | MONEY 0 | PROP 0 | MOVES 3 | HOST: 2 | GUEST2: 2 | GUEST3: 0 |
- hud_after: TURN 1 | PHASE action | ACTIVE HOST | HAND 4 | MONEY 0 | PROP 0 | MOVES 3 | HOST: 2 | GUEST2: 2 | GUEST3: 0 |
- host_state_after_player_count: 3

## 4 人
- start_result: {'success': True}
- current_player: host
- turn_phase: event -> action
- host hand count: 5 -> 4
- guest hand counts: {'guest2': 5, 'guest3': 5, 'guest4': 5}
- illegal_play: {'guest': 'guest2', 'hand_before': ['追隨者', '追隨者', '樂捐者', '追隨者', '追隨者'], 'error_before': None, 'error_after': 'Not your turn', 'log_same': True}
- chosen_card: 樂捐者
- host_log_changed: True
- hud_changed: True
- hud_before: TURN 1 | PHASE action | ACTIVE HOST | HAND 5 | MONEY 0 | PROP 0 | MOVES 3 | HOST: 2 | GUEST2: 0 | GUEST3: 2 | GUEST4: 2 |
- hud_after: TURN 1 | PHASE action | ACTIVE HOST | HAND 4 | MONEY 0 | PROP 0 | MOVES 3 | HOST: 2 | GUEST2: 0 | GUEST3: 2 | GUEST4: 2 |
- host_state_after_player_count: 4
