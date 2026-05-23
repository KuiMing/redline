# Event Cards Runtime Validation

Status: passed (14 passed)

- test_idle_noop: passed — {'event': '歲月靜好', 'status': 'idle', 'phase_after_second_advance': <TurnPhase.ACTION: 'action'>}
- test_hong_kong_success_static_supply: passed — {'event': '香港抗暴之戰', 'progress': {'count': 1, 'required': 1, 'succeeded': True, 'settled': True, 'status': 'success'}, 'discard': ['宣傳家', '資助者'], 'static_supply': 0}
- test_hong_kong_failure_discard_choice: passed — {'event': '香港抗暴之戰', 'choice_key': 'event_discard_self', 'discard': ['追隨者']}
- test_major_disaster_success: passed — {'event': '重大災難', 'progress': {'count': 1, 'required': 1, 'succeeded': True, 'settled': True, 'status': 'success'}, 'discard': ['宣傳家', '宣傳家']}
- test_draw_trigger_succeeds: passed — {'event': '北京政爭', 'progress': {'count': 1, 'required': 1, 'succeeded': True, 'settled': True, 'status': 'success'}, 'hand_count': 7}
- test_trade_war_purchase_trigger_topdecks_from_discard: passed — {'event': '貿易戰加劇', 'choice_key': 'event_topdeck_from_discard', 'deck_top': '四點行動', 'discard': ['舊棄牌']}
- test_trade_war_purchase_trigger_ignores_low_cost_non_anglo_support: passed — {'event': '貿易戰加劇', 'progress': {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}, 'pending_choice': None}
- test_trade_war_purchase_trigger_accepts_anglo_support_by_name: passed — {'event': '貿易戰加劇', 'triggered_by': '英美奧援', 'choice_key': 'event_topdeck_from_discard'}
- test_auto_event_modifier: passed — {'event': '上海合作組織', 'modifiers': [{'type': 'ignore_distance', 'duration': 1, 'event_id': 'shanghai_cooperation_org'}], 'status': 'auto'}
- test_event_deck_uses_declared_counts_without_structured_duplicate_overcount: passed — {'全國人大召開': 2, '重大災難': 2, 'total': 27}
- test_trade_war_structured_matches_raw_rule: passed — {'event': '貿易戰加劇', 'trigger': {'type': 'buy_card', 'count': 1, 'min_cost': 4, 'card_names': ['英美奧援']}, 'success': {'type': 'topdeck_from_discard', 'count': 1}}
- test_event_modifiers_are_consumed_by_runtime_rules: passed — {'reduce_cost_buy': ['資助者'], 'restrict_build_error': 'Current event restricts building organizations', 'ignore_distance_move': {'success': True}}
- test_pending_choice_blocks_phase_advance_until_resolved: passed — {'event': '香港抗暴之戰', 'blocked_error': 'Resolve pending choice before advancing phase', 'phase_after_resolve': <TurnPhase.END: 'end'>}
- test_event_deck_reshuffle: passed — {'event': '歲月靜好', 'discard_count': 1}
