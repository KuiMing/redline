# MAIN TABS LAYOUT VALIDATION

日期：2026-05-09

summary: {'total': 7, 'passed': 7, 'failed': 0}

screenshot: /Users/benmini/.openclaw/workspace/redline/main_tabs_layout_validation.png

## command_tab_visible
- result: PASS
- detail: {"hand_count": 5, "static_count": 6, "random_count": 5}

## command_tab_card_zones_populated
- result: PASS
- detail: {"hand_count": 5, "static_count": 6, "random_count": 5}

## map_tab_visible
- result: PASS
- detail: {"iframe_count": 1}

## battle_log_tab_visible
- result: PASS
- detail: {"active_tab": "戰況紀錄"}

## player_status_card_count_matches_players
- result: PASS
- detail: {"card_count": 2, "players": ["viewer", "red"]}

## player_status_cards_have_required_fields
- result: PASS
- detail: {"card_texts": ["V\nviewer\n當前行動玩家\n當前玩家\n陣營：西藏（德拉敦）\n根據地：德拉敦\n組織\n1\n資金\n4\n宣傳\n3\n手牌\n5\n移動\n3", "R\nred\n玩家戰況\n陣營：紅軍\n根據地：北京\n組織\n1\n資金\n0\n宣傳\n0\n手牌\n5\n移動\n3"]}

## viewport_1280x720_has_no_body_overflow
- result: PASS
- detail: {"bodyScrollWidth": 1280, "bodyClientWidth": 1280, "bodyScrollHeight": 720, "bodyClientHeight": 720, "hasOverflowX": false, "hasOverflowY": false, "viewport": {"w": 1280, "h": 720}}
