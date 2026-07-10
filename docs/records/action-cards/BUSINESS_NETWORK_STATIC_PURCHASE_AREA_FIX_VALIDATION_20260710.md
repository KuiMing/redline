# 企業人脈 static purchase area fix validation

可重跑指令：`python3 scripts/validate_business_network_static_purchase_area.py`

- checks: {"play_card_success": true, "pending_choice_offered": true, "static_purchase_card_offered": true, "total_choices_cover_full_purchase_area": true, "borrow_resolved_without_error": true, "borrowed_chosen_card_matches": true}
- choice_names: ["宣傳家", "思想家", "資助者", "資本家", "分神", "內鬥", "領導", "樹立信心", "地下黨", "擴大戰果", "點燃熱情"]
- picked_static_card: 宣傳家
- borrow_result: {"success": true, "chosen_card": "宣傳家", "purchase_index": 0}
- result: PASS
