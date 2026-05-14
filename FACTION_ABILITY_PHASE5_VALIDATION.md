# FACTION ABILITY PHASE5 VALIDATION

- total: 4
- passed: 3
- failed: 1

- PASS democracy_frontline: result={'success': True}, discard=1
- PASS political_probe: result={'success': True}, hand=1
- PASS huawen_media_spend_money: result={'success': True}, resources={'money': 0, 'propaganda': 0}
- FAIL gambler_whisper: result={'error': 'Guess required'}, resources={'money': 0, 'propaganda': 0}
