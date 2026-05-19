# LOBBY READY SYNC VALIDATION

日期：2026-05-09

summary: {'total': 6, 'passed': 6, 'failed': 0}

screenshot: /Users/benmini/.openclaw/workspace/redline/lobby_ready_sync_validation.png

## host_start_button_locked_until_ready
- result: PASS
- detail: {"exists": true, "disabled": true, "text": "啟動行動", "title": "至少需要 2 位玩家"}

## ready_toggle_visible_in_lobby
- result: PASS
- detail: {"exists": true, "text": "我已準備", "disabled": true}

## lobby_roster_auto_syncs_joined_players
- result: PASS
- detail: {"roster_text": "H\nhost\n房主 / 你｜未準備｜尚未選擇陣營\nA\nally\n玩家｜未準備｜尚未選擇陣營\n+\n等待玩家加入\n分享房間代碼邀請下一位玩家\n+\n空席位\n最多 4 位玩家", "second_player_id": "cc7d4139-8eae-4e8f-862b-2e33317e7608"}

## lobby_state_exposes_ready_map
- result: PASS
- detail: {"lobby_state_keys": ["bases", "count", "factions", "host_id", "market_mode", "players", "ready", "started"]}

## backend_rejects_start_before_all_ready
- result: PASS
- detail: {"error": "All players must be ready before start"}

## host_start_button_unlocks_when_all_players_ready
- result: PASS
- detail: {"start_button": {"disabled": false, "title": "所有玩家已準備，可以啟動行動", "text": "啟動行動"}, "roster_text": "H\nhost\n房主 / 你｜已準備｜紅軍\nA\nally\n玩家｜已準備｜臺灣（綠線）\n+\n等待玩家加入\n分享房間代碼邀請下一位玩家\n+\n空席位\n最多 4 位玩家"}
