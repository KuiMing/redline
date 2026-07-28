# ENEMY OCCUPANCY RULES VALIDATION

日期：2026-07-28

summary: {'total': 5, 'passed': 5, 'failed': 0}

## cannot_move_into_enemy_occupied_destination — PASS
- result: {'error': 'Cannot move into occupied town'}
- before: {'player_orgs': {'桃園': 1}, 'red_orgs': {'新竹': 1}, 'moves_left': 1}
- after: {'player_orgs': {'桃園': 1}, 'red_orgs': {'新竹': 1}, 'moves_left': 1}
- rule: 敵方組織所在城鎮不可移入。

## propagandist_build_choices_exclude_enemy_occupied_but_include_vacated_new_taipei — PASS
- choices_sample: ['新北']
- red_orgs: {'新竹': 1}
- rule: 宣傳家 range 1：新竹有紅軍組織不可建立；新北目前無紅軍組織且在桃園 1 格內，可建立。

## support_build_rejects_enemy_occupied_town — PASS
- result: {'error': 'Cannot develop in this town'}
- before: {'player_orgs': {'桃園': 1}, 'red_orgs': {'新竹': 1}, 'moves_left': 1}
- after: {'player_orgs': {'桃園': 1}, 'red_orgs': {'新竹': 1}, 'moves_left': 1}

## support_build_allows_vacated_new_taipei — PASS
- result: {'success': True}
- before: {'player_orgs': {'桃園': 1}, 'red_orgs': {'新竹': 1}, 'moves_left': 1}
- after: {'player_orgs': {'桃園': 1, '新北': 1}, 'red_orgs': {'新竹': 1}, 'moves_left': 1}

## direct_build_rejects_second_piece_after_red_moved_out — PASS
- result: {'error': 'Cannot develop in this town'}
- before: {'player_orgs': {'新北': 1}, 'red_orgs': {'新竹': 1}, 'moves_left': 1}
- after: {'player_orgs': {'新北': 1}, 'red_orgs': {'新竹': 1}, 'moves_left': 1}
