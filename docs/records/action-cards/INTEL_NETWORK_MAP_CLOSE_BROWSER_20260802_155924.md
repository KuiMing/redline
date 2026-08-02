# INTEL NETWORK MAP CLOSE BROWSER

- PASS 情報網瓦解選項建立 target pending choice 並標記 interaction_kind: `{'pending_choice': {'type': 'target_choice', 'choice_key': 'intel_network_dissolve_target', 'interaction_kind': 'dissolve_organization', 'remaining_builds': None, 'queueable_card_names': [], 'cancellable': False, 'player_id': '8cb8e3f2-0d84-435c-96bb-a8158abe3e01', 'player_name': None, 'prompt': '情報網：選擇 1 個要瓦解的鄰近敵方組織。', 'source_name': '情報網', 'count': None, 'min_count': None, 'mode': None, 'acting_player_id': None, 'acting_player_name': None, 'played_card_name': None, 'region': None, 'free': None, 'ignore_distance': None, 'cards': [], 'options': [], 'towns': [], 'targets': [{'id': '9e23895b-4f04-4a24-881c-80b6767c7b57::天津', 'label': 'enemyA｜天津', 'player_id': '9e23895b-4f04-4a24-881c-80b6767c7b57', 'town': '天津', 'requires_self_sacrifice': False}], 'step': None}}`
- PASS 建立 pending choice 後自動隱藏選擇 modal 並切到戰略地圖: `{'modal_hidden': True, 'active_view': 'mapView'}`
- PASS 合法瓦解目標以 💀 標示，且數量與後端投影的候選一致: `{'skull_count': 1, 'target_count': 1}`
- PASS 點擊 💀 標記單一步驟完成瓦解，pending choice 清除: `{'enemyA_orgs': {'香港城': 1, '廣州': 1}}`
