# CARD UI VALIDATION PART 1

日期：2026-05-03

## 2 人
- start_result: {'success': True}
- current_player: host
- turn_phase: event -> event
- host hand count: 5 -> 5
- guest hand counts: {'guest2': 5}
- illegal_play: {'guest': 'guest2', 'hand_before': ['追隨者', '追隨者', '追隨者', '樂捐者', '追隨者'], 'state_same': False, 'log_same': True}
- chosen_card: 樂捐者
- host_log_changed: False
- hud_changed: False
- host_state_after_player_count: 2

## 3 人
- start_result: {'success': True}
- current_player: host
- turn_phase: event -> event
- host hand count: 5 -> 5
- guest hand counts: {'guest2': 5, 'guest3': 5}
- illegal_play: {'guest': 'guest2', 'hand_before': ['追隨者', '追隨者', '追隨者', '樂捐者', '樂捐者'], 'state_same': False, 'log_same': True}
- chosen_card: 追隨者
- host_log_changed: False
- hud_changed: False
- host_state_after_player_count: 3

## 4 人
- start_result: {'success': True}
- current_player: host
- turn_phase: event -> event
- host hand count: 5 -> 5
- guest hand counts: {'guest2': 5, 'guest3': 5, 'guest4': 5}
- illegal_play: {'guest': 'guest2', 'hand_before': ['追隨者', '追隨者', '樂捐者', '樂捐者', '追隨者'], 'state_same': False, 'log_same': True}
- chosen_card: 樂捐者
- host_log_changed: False
- hud_changed: False
- host_state_after_player_count: 4
