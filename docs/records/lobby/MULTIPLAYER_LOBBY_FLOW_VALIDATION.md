# MULTIPLAYER LOBBY FLOW VALIDATION

日期：2026-05-09

summary: {'total': 9, 'passed': 9, 'failed': 0}

host screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/lobby/multiplayer_lobby_flow_host.png
ally screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/lobby/multiplayer_lobby_flow_ally.png

## host_created_room
- result: PASS
- detail: {"game_id": "12a053c3-236b-43b7-b7f5-393e3bc2748f", "host_player_id": "750c44ce-ebd4-42c9-bfc9-f2a63287c03e"}

## two_browser_contexts_join_same_lobby
- result: PASS
- detail: {"ally_player_id": "57d2cad0-ceb1-416d-85b6-d16018c948e1", "host_roster": "H\nhost\n房主 / 你｜未準備｜尚未選擇陣營\nA\nally\n玩家｜未準備｜尚未選擇陣營\n+\n等待玩家加入\n分享房間代碼邀請下一位玩家\n+\n空席位\n最多 4 位玩家", "ally_roster": "A\nhost\n房主｜未準備｜尚未選擇陣營\nA\nally\n已進入作戰室；請選擇你的陣營與根據地。\n+\n等待玩家加入\n分享房間代碼邀請下一位玩家\n+\n空席位\n最多 4 位玩家"}

## both_players_show_chosen_factions
- result: PASS
- detail: {"choose_host": {"success": true, "factions": {"750c44ce-ebd4-42c9-bfc9-f2a63287c03e": "red_army"}, "bases": {}}, "choose_ally": {"success": true, "factions": {"750c44ce-ebd4-42c9-bfc9-f2a63287c03e": "red_army", "57d2cad0-ceb1-416d-85b6-d16018c948e1": "taiwan_green"}, "bases": {"57d2cad0-ceb1-416d-85b6-d16018c948e1": "臺北"}}, "host_roster": "H\nhost\n房主 / 你｜未準備｜紅軍\nA\nally\n玩家｜未準備｜臺灣（綠線）｜臺北\n+\n等待玩家加入\n分享房間代碼邀請下一位玩家\n+\n空席位\n最多 4 位玩家", "ally_roster": "H\nhost\n房主｜未準備｜紅軍\nA\nally\n玩家 / 你｜未準備｜臺灣（綠線）｜臺北\n+\n等待玩家加入\n分享房間代碼邀請下一位玩家\n+\n空席位\n最多 4 位玩家"}

## both_players_ready_plain_text
- result: PASS
- detail: {"host_roster": "H\nhost\n房主 / 你｜已準備｜紅軍\nA\nally\n玩家｜已準備｜臺灣（綠線）｜臺北\n+\n等待玩家加入\n分享房間代碼邀請下一位玩家\n+\n空席位\n最多 4 位玩家", "ally_roster": "H\nhost\n房主｜已準備｜紅軍\nA\nally\n玩家 / 你｜已準備｜臺灣（綠線）｜臺北\n+\n等待玩家加入\n分享房間代碼邀請下一位玩家\n+\n空席位\n最多 4 位玩家"}

## non_host_start_button_locked
- result: PASS
- detail: {"disabled": true, "title": "只有房主可以啟動行動", "text": "啟動行動"}

## host_can_start_and_enters_game_shell
- result: PASS
- detail: {"host_start_before": {"disabled": false, "title": "所有玩家已準備，可以啟動行動", "text": "啟動行動"}, "host_body_excerpt": "逆統戰\n逆統戰指揮中心\n結束目前步驟\n指揮中心\n戰略地圖\n戰況紀錄\n常設購買區\n隨機購買區\n手牌"}

## ally_auto_enters_game_shell_after_host_start
- result: PASS
- detail: {"ally_body_excerpt": "逆統戰\n逆統戰指揮中心\n回合 1\n事件階段\n當前玩家 ally\n手牌 5\n資金 0\n宣傳 0\n移動 0\n牌庫模式 53 張卡牌\nhost 組織 1\nally 組織 1\n目前：事件｜下一步：開始購買階段\n開始購買階段\n目前事件\n歲月靜好\n類型：歲月靜好｜狀態：無效果\n任務結果：本次事件無效果\n任務條件：無\n進度：0/0\n成功獎勵：無\n失敗懲罰：無\n指揮中心\n戰略地圖\n戰況紀錄\n常設購買區\n宣傳家\n剩 15\n宣傳 ・ 乙級 ・ 宣傳3\n打出可移除本牌。若移除本牌，可於己方組織1格內建立1個組織，並進行1次組織遷移。\n擅於宣傳的辯士\n資源 宣傳2\n常設購買區\n購買\n思想家\n剩 15\n宣傳 ・ 甲級 ・ 宣傳5\n打出可移除本牌。若移除本牌，可無視距離於己方發展空間建立1個組織，並進行3次組織遷移。\n締造革命理論的智者\n資源 宣傳3\n常設購買區\n購買\n資助者\n剩 15\n資金 ・ 乙級 ・ 資金2+宣傳1\n打出可移除本牌。若移除本牌，獲得2點資金與2點宣傳。\n贊助您事業的中產階級\n資源 資金2\n常設購買區\n購買\n資本家\n剩 15\n資金 ・ 甲級 ・ 資金3+宣傳2\n打出可移除本牌。若移除本牌，獲得3點資金與3點宣傳。\n贊助您事業的企業家\n資源 資金3\n常設購買區\n購買\n分神\n剩 30\n混亂 ・ 乙級 ・ 無\n無效果。打出可移除本牌。\n有其它事情迫使你分散心力\n資源 無\n常設購買區（可視為起始牌）\n購買\n內鬥\n剩 20\n混亂 ・ 丙級 ・ 無\n無效果。\n內部鬥爭令組織效率低落\n資源 無\n常設購買區（可視為起始牌）\n購買\n隨機購買區\n武裝小隊\n剩 5\n武裝 ・ 乙級 ・ 資金3\n選擇1位有組織位在己方組織1格內的玩家，由該玩家選2張手牌棄掉。\n有組織的戰術小隊\n資源 資金1+宣傳1\n隨機購買區\n購買\n謀劃\n剩 5\n指揮 ・ 乙級 ・ 資金1+宣傳1\n抽2張牌。\n深思熟慮後運用計謀\n資源 宣傳2\n隨機購買區\n購買\n組織經驗甲\n剩 3\n組織 ・ 甲級 ・ 資金3+宣傳3\n無視距離於己方發展空間建立1個組織。每從手上棄掉1張購買費用4點以上的牌，可重複上述動作1次。無法無視距離建立牆內組織者，本牌於牆內建立組織距離為1格。\n把遠方的支持者們組織起來\n資源 資金1+宣傳2\n隨機購買區\n購買\n凝聚共識\n剩 5\n指揮 ・ 甲級 ・ 宣傳5\n抽3張牌，再從所有手牌中棄掉任2張牌；若棄掉的牌均非起", "ally_lobby_display": "none", "ally_game_shell_display": "block"}

## battle_log_player_cards_available_after_start
- result: PASS
- detail: {"host_cards": "H\nhost\n玩家戰況\n陣營：紅軍\n根據地：北京\n組織\n1\n資金\n0\n宣傳\n0\n手牌\n5\n棄牌\n0\n移動\n0\n棄牌堆\n無\nA\nally\n當前行動玩家\n當前玩家\n陣營：臺灣（綠線）\n根據地：臺北\n組織\n1\n資金\n0\n宣傳\n0\n手牌\n5\n棄牌\n0\n移動\n0\n棄牌堆\n無", "ally_cards": "H\nhost\n玩家戰況\n陣營：紅軍\n根據地：北京\n組織\n1\n資金\n0\n宣傳\n0\n手牌\n5\n棄牌\n0\n移動\n0\n棄牌堆\n無\nA\nally\n當前行動玩家\n當前玩家\n陣營：臺灣（綠線）\n根據地：臺北\n組織\n1\n資金\n0\n宣傳\n0\n手牌\n5\n棄牌\n0\n移動\n0\n棄牌堆\n無"}

## game_views_include_both_players_and_factions
- result: PASS
- detail: {"host_excerpt": "逆統戰\n逆統戰指揮中心\n回合 1\n事件階段\n當前玩家 ally\n手牌 5\n資金 0\n宣傳 0\n移動 0\n牌庫模式 53 張卡牌\nhost 組織 1\nally 組織 1\n目前：事件｜等待 ally 操作\n開始購買階段\n目前事件\n歲月靜好\n類型：歲月靜好｜狀態：無效果\n任務結果：本次事件無效果\n任務條件：無\n進度：0/0\n成功獎勵：無\n失敗懲罰：無\n指揮中心\n戰略地圖\n戰況紀錄\n戰況總覽\nH\nhost\n玩家戰況\n陣營：紅軍\n根據地：北京\n組織\n1\n資金\n0\n宣傳\n0\n手牌\n5\n棄牌\n0\n移動\n0\n棄牌堆\n無\nA\nally\n當前行動玩家\n當前玩家\n陣營：臺灣（綠線）\n根據地：臺北\n組織\n1\n資金\n0\n宣傳\n0\n手牌\n5\n棄牌\n0\n移動\n0\n棄牌堆\n無\n事件紀錄\n[Turn 1] Event drawn: 歲月靜好 (no-op)", "ally_excerpt": "逆統戰\n逆統戰指揮中心\n回合 1\n事件階段\n當前玩家 ally\n手牌 5\n資金 0\n宣傳 0\n移動 0\n牌庫模式 53 張卡牌\nhost 組織 1\nally 組織 1\n目前：事件｜下一步：開始購買階段\n開始購買階段\n目前事件\n歲月靜好\n類型：歲月靜好｜狀態：無效果\n任務結果：本次事件無效果\n任務條件：無\n進度：0/0\n成功獎勵：無\n失敗懲罰：無\n指揮中心\n戰略地圖\n戰況紀錄\n戰況總覽\nH\nhost\n玩家戰況\n陣營：紅軍\n根據地：北京\n組織\n1\n資金\n0\n宣傳\n0\n手牌\n5\n棄牌\n0\n移動\n0\n棄牌堆\n無\nA\nally\n當前行動玩家\n當前玩家\n陣營：臺灣（綠線）\n根據地：臺北\n組織\n1\n資金\n0\n宣傳\n0\n手牌\n5\n棄牌\n0\n移動\n0\n棄牌堆\n無\n事件紀錄\n[Turn 1] Event drawn: 歲月靜好 (no-op)"}
