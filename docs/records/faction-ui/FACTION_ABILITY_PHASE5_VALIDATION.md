# FACTION ABILITY PHASE5 VALIDATION

- total: 4
- passed: 4
- failed: 0

- PASS democracy_frontline: result={'success': True}, discard=1
- PASS political_probe: result={'success': True, 'result': {'name': '立場試探', 'revealed_card': '奇數牌', 'cost_total': 1, 'destination': 'hand'}}, hand=1
- PASS huawen_media_spend_money: result={'success': True}, resources={'money': 0, 'propaganda': 0}
- PASS gambler_whisper: result={'success': True, 'result': {'name': '賭徒耳語', 'revealed_card': '奇數牌', 'cost_total': 1, 'guess': 'odd', 'hit': True, 'bottom_card': '墊牌', 'destination': 'deck_top', 'reward': {'money': 3, 'propaganda': 3}}}, resources={'money': 3, 'propaganda': 3}
