# SETUP RULES VALIDATION

日期：2026-05-09

summary: {'total': 8, 'passed': 8, 'failed': 0}

screenshot: /Users/benmini/.openclaw/workspace/redline/setup_rules_validation.png

## start_endpoint_accepts_ready_setup
- result: PASS
- detail: {"success": true, "market_mode": "sample_53"}

## setup_enters_main_event_phase
- result: PASS
- detail: {"game_phase": "main", "turn_phase": "event", "turn": 1, "winner": null}

## starting_player_is_first_non_red
- result: PASS
- detail: {"current_player": "ally", "expected": "ally"}

## host_faction_and_base_initialized
- result: PASS
- detail: {"player": {"id": "5a3983a3-a5f9-42a9-951c-e569bdf36cc4", "name": "host", "faction": "red_army", "base": "北京", "resources": {"money": 0, "propaganda": 0}, "moves_left": 3, "hand": ["追隨者", "追隨者", "追隨者", "追隨者", "樂捐者"], "deck_count": 5, "discard_count": 0, "orgs": {"北京": 1}}, "expected": {"faction": "red_army", "base": "北京"}}

## ally_faction_and_base_initialized
- result: PASS
- detail: {"player": {"id": "97a27080-aa17-4357-9d88-565250c80918", "name": "ally", "faction": "taiwan_green", "base": "臺北", "resources": {"money": 0, "propaganda": 0}, "moves_left": 3, "hand": ["追隨者", "樂捐者", "追隨者", "追隨者", "樂捐者"], "deck_count": 5, "discard_count": 0, "orgs": {"臺北": 1}}, "expected": {"faction": "taiwan_green", "base": "臺北"}}

## host_starter_hand_resources_and_moves
- result: PASS
- detail: {"player": {"id": "5a3983a3-a5f9-42a9-951c-e569bdf36cc4", "name": "host", "faction": "red_army", "base": "北京", "resources": {"money": 0, "propaganda": 0}, "moves_left": 3, "hand": ["追隨者", "追隨者", "追隨者", "追隨者", "樂捐者"], "deck_count": 5, "discard_count": 0, "orgs": {"北京": 1}}}

## ally_starter_hand_resources_and_moves
- result: PASS
- detail: {"player": {"id": "97a27080-aa17-4357-9d88-565250c80918", "name": "ally", "faction": "taiwan_green", "base": "臺北", "resources": {"money": 0, "propaganda": 0}, "moves_left": 3, "hand": ["追隨者", "樂捐者", "追隨者", "追隨者", "樂捐者"], "deck_count": 5, "discard_count": 0, "orgs": {"臺北": 1}}}

## purchase_area_setup_matches_rules
- result: PASS
- detail: {"purchase_area_count": 11, "purchase_area": ["宣傳家", "思想家", "資助者", "資本家", "分神", "內鬥", "爆料黑幕", "組織經驗丙", "武裝者", "紅軍奧援", "領導"], "static_supply": {"宣傳家": 1, "思想家": 1, "資助者": 1, "資本家": 1, "分神": 1, "內鬥": 1}}
