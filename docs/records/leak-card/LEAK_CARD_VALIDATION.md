# LEAK CARD VALIDATION

日期：2026-05-11

summary: {'total': 6, 'passed': 6, 'failed': 0}

## 走漏風聲_explicit_target_discards_top_card_receives_internal_conflict_and_consumes_supply — PASS
- result: {'success': True}
- actor_discard: ['走漏風聲']
- target_a_discard: []
- target_b_draw: ['樂捐者']
- target_b_discard: ['資助者', '內鬥']
- actor_resources: {'money': 0, 'propaganda': 0}
- internal_conflict_supply_before: 1
- internal_conflict_supply_after: 0
- expected_rule: action mode discards chosen target top deck card; if discarded card purchase cost >= 1, move 1 內鬥 from static purchase supply to that same target discard; printed 宣傳1 is resource-mode only.

## 走漏風聲_without_explicit_target_uses_first_other_player_fallback_not_actor_or_all_players — PASS
- result: {'success': True}
- actor_discard: ['走漏風聲']
- target_a_discard: ['追隨者']
- target_b_discard: []
- expected_rule: until UI supplies an explicit target, fallback should affect exactly the first other player; zero-cost/top starter does not add 內鬥.

## 走漏風聲_resource_mode_grants_only_printed_resource_without_deck_attack — PASS
- result: {'success': True}
- actor_resources: {'money': 0, 'propaganda': 1}
- actor_discard: ['走漏風聲']
- target_b_draw: ['資助者']
- target_b_discard: []
- expected_rule: resource mode is exclusive: printed 宣傳1 only, no action effect.

## 走漏風聲_rejects_self_target_without_consuming_card_or_deck — PASS
- result: {'error': '走漏風聲必須指定其他玩家'}
- actor_hand: ['走漏風聲']
- actor_discard: []
- target_b_draw: ['資助者']
- target_b_discard: []
- expected_rule: server-side validation must reject crafted self-target payloads before consuming the played card.

## 走漏風聲_rejects_unknown_target_without_consuming_card_or_deck — PASS
- result: {'error': '走漏風聲必須指定其他玩家'}
- actor_hand: ['走漏風聲']
- actor_discard: []
- target_b_draw: ['資助者']
- target_b_discard: []
- expected_rule: server-side validation must reject unknown explicit targets before consuming the played card.

## 走漏風聲_rejects_empty_string_target_without_consuming_card_or_deck — PASS
- result: {'error': '走漏風聲必須指定其他玩家'}
- actor_hand: ['走漏風聲']
- actor_discard: []
- target_b_draw: ['資助者']
- target_b_discard: []
- expected_rule: server-side validation must reject falsy explicit targets before consuming the played card.
