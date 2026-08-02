# INTEL NETWORK MAP CLOSE BROWSER

- PASS 情報網瓦解選項建立 target pending choice 並標記 interaction_kind: `{'pending_choice': {'type': 'target_choice', 'choice_key': 'intel_network_dissolve_target', 'interaction_kind': 'dissolve_organization', 'remaining_builds': None, 'queueable_card_names': [], 'cancellable': False, 'player_id': 'ea79b8c7-e4ec-4a44-8850-953884809396', 'player_name': None, 'prompt': '情報網：選擇 1 個要瓦解的鄰近敵方組織。', 'source_name': '情報網', 'count': None, 'min_count': None, 'mode': None, 'acting_player_id': None, 'acting_player_name': None, 'played_card_name': None, 'region': None, 'free': None, 'ignore_distance': None, 'cards': [], 'options': [], 'towns': [], 'targets': [{'id': 'e69a4e45-1558-401e-b83c-76274a701433::天津', 'label': 'enemyA｜天津', 'player_id': 'e69a4e45-1558-401e-b83c-76274a701433', 'town': '天津', 'requires_self_sacrifice': False}], 'step': None}}`
- PASS 建立 pending choice 後自動隱藏選擇 modal 並切到戰略地圖: `{'modal_hidden': True, 'active_view': 'mapView'}`
- PASS 合法瓦解目標以 💀 標示，且數量與後端投影的候選一致: `{'skull_count': 1, 'target_count': 1}`
- PASS 點擊 💀 標記僅選取目標並啟用確認按鈕，尚未真正瓦解: `{'armed_count': 1, 'still_pending': True}`
- PASS 按下側欄確認按鈕才真正完成瓦解，pending choice 清除: `{'enemyA_orgs': {'香港城': 1, '廣州': 1}}`
