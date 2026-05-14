# SUPPORT PURCHASE DECK RUNTIME VALIDATION

Summary: 8/8 passed

- checks: {"has_purchase_deck": true, "initial_area_has_static_plus_five_random": true, "purchase_deck_has_48_cards_after_market_draw": true, "support_total_in_market_and_deck_is_18": true, "static_area_contains_disruption_cards": true, "static_buy_succeeds_and_decrements_supply_without_removing_slot": true, "random_buy_succeeds_and_removes_slot": true, "end_turn_refills_market_to_static_plus_five_random": true}
- initial_area_len: 11
- initial_deck_len: 48
- support_total: 18
- purchase_names: ["宣傳家", "思想家", "資助者", "資本家", "分神", "內鬥", "組織經驗甲", "凝聚共識", "離間", "批鬥", "樹立信心"]
- static_supply_before: {"宣傳家": 1, "思想家": 1, "資助者": 1, "資本家": 1, "分神": 1, "內鬥": 1}
- static_supply_after: {"宣傳家": 0, "思想家": 1, "資助者": 1, "資本家": 1, "分神": 1, "內鬥": 1}
- static_buy_result: {"success": true}
- random_slot_before: 組織經驗甲
- random_buy_result: {"success": true}
- area_len_after_static_buy: 11
- area_len_after_random_buy: 10
- area_len_after_refill: 11
