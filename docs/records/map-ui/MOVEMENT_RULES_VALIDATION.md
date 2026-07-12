# MOVEMENT RULES VALIDATION

日期：2026-07-12

summary: {'total': 13, 'passed': 13, 'failed': 0}

## movement_rejected_outside_action_phase — PASS
- result: {'error': 'Not in ACTION phase'}
- before: {'orgs': {'香港城': 1}, 'moves_left': 3, 'base': '香港城'}
- after: {'orgs': {'香港城': 1}, 'moves_left': 3, 'base': '香港城'}

## initial_zero_move_points_cannot_move — PASS
- result: {'error': 'Not enough move points'}
- before: {'orgs': {'澳門': 1}, 'moves_left': 0, 'base': '香港城'}
- after: {'orgs': {'澳門': 1}, 'moves_left': 0, 'base': '香港城'}
- rule: 一開始沒有移動點；必須靠卡牌或效果取得移動點後才能移動。

## road_adjacent_move_costs_one_and_moves_org — PASS
- result: {'success': True}
- before: {'orgs': {'澳門': 1}, 'moves_left': 1, 'base': '香港城'}
- after: {'orgs': {'香港城': 1}, 'moves_left': 0, 'base': '香港城'}

## rail_adjacent_move_costs_one_move_count_and_moves_org — PASS
- result: {'success': True}
- before: {'orgs': {'北京': 1}, 'moves_left': 1, 'base': '香港城'}
- after: {'orgs': {'天津': 1}, 'moves_left': 0, 'base': '香港城'}

## rail_three_step_move_costs_one_move_count_and_moves_org — PASS
- result: {'success': True}
- before: {'orgs': {'新北': 1}, 'moves_left': 1, 'base': '香港城'}
- after: {'orgs': {'苗栗': 1}, 'moves_left': 0, 'base': '香港城'}
- rule: rules.md：鐵路一次最多 3 格；新北→桃園→新竹→苗栗 consumes 1 move count.

## rail_four_step_move_rejected_without_spending_points — PASS
- result: {'error': 'No rail connection'}
- before: {'orgs': {'新北': 1}, 'moves_left': 1, 'base': '香港城'}
- after: {'orgs': {'新北': 1}, 'moves_left': 1, 'base': '香港城'}
- rule: 新北→彰化 requires 4 rail edges, exceeding the 3-step rail limit.

## rail_three_step_cannot_pass_enemy_organization — PASS
- result: {'error': 'No rail connection'}
- before: {'orgs': {'新北': 1}, 'moves_left': 1, 'base': '香港城'}
- after: {'orgs': {'新北': 1}, 'moves_left': 1, 'base': '香港城'}
- enemy_org: {'新竹': 1}
- rule: 可跨越己方組織，但不可跨越敵方。

## rail_move_rejected_when_no_move_count_left — PASS
- result: {'error': '目的城鎮不適用你的陣營，無法遷入'}
- before: {'orgs': {'北京': 1}, 'moves_left': 0, 'base': '香港城'}
- after: {'orgs': {'北京': 1}, 'moves_left': 0, 'base': '香港城'}

## non_adjacent_move_rejected_without_spending_points — PASS
- result: {'error': 'No road connection'}
- before: {'orgs': {'香港城': 2}, 'moves_left': 3, 'base': '香港城'}
- after: {'orgs': {'香港城': 2}, 'moves_left': 3, 'base': '香港城'}

## invalid_move_mode_rejected_without_state_change — PASS
- result: {'error': 'Invalid move mode'}
- before: {'orgs': {'香港城': 2}, 'moves_left': 3, 'base': '香港城'}
- after: {'orgs': {'香港城': 2}, 'moves_left': 3, 'base': '香港城'}

## invalid_origin_rejected_without_state_change — PASS
- result: {'error': 'Invalid town'}
- before: {'orgs': {'香港城': 1}, 'moves_left': 3, 'base': '香港城'}
- after: {'orgs': {'香港城': 1}, 'moves_left': 3, 'base': '香港城'}

## base_anchor_organization_cannot_leave_base — PASS
- rule: RULES.md: 根據地的組織棋在遊戲過程中不得離開根據地底座。
- result: {'error': 'Base anchor organization cannot move'}
- before: {'orgs': {'香港城': 1}, 'moves_left': 3, 'base': '香港城'}
- after: {'orgs': {'香港城': 1}, 'moves_left': 3, 'base': '香港城'}

## extra_organization_on_base_can_move_but_anchor_remains — PASS
- rule: 只有根據地底座上的保底組織不可離開；同城額外組織仍可正常遷移。
- result: {'success': True}
- before: {'orgs': {'香港城': 2}, 'moves_left': 3, 'base': '香港城'}
- after: {'orgs': {'香港城': 1, '澳門': 1}, 'moves_left': 2, 'base': '香港城'}
