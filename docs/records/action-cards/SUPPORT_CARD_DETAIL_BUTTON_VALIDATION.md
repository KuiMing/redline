# 奧援卡手牌按鈕（棄置／行動）驗證

可重跑指令：`python3 scripts/validate_support_card_detail_button.py`

- total: 6 / passed: 6 / failed: 0
- screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/action-cards/support_card_detail_button.png

## Results
- ✅ `support_card_shows_discard_and_action_only` — {"buttons": [{"text": "棄置", "mode": "resource", "disabled": false}, {"text": "行動", "mode": "action", "disabled": false}]}
- ✅ `card_face_shows_all_three_tier_effect_lines` — {"face_text": "III級（臺灣主導）：瓦解己方組織1格內的1個對手組織，並在該城鎮建立1個組織II級（東洋/南洋其一主導）：瓦解己方組織1格內的1個對手組織。I級（皆未主導）：獲得1點宣傳。"}
- ✅ `card_face_art_is_loaded_and_contained` — {"naturalW": 1100, "naturalH": 1350, "imageW": 218, "imageH": 272, "faceW": 218, "faceH": 272, "contained": true}
- ✅ `discard_button_discards_with_no_resource_gain` — {"before_hand": ["臺灣奧援"], "after_hand": [], "after_discard": ["臺灣奧援"], "before_resources": {"money": 0, "propaganda": 0}, "after_resources": {"money": 0, "propaganda": 0}}
- ✅ `red_army_support_card_shows_resource_and_action` — {"buttons": [{"text": "資源", "mode": "resource", "disabled": false}, {"text": "行動", "mode": "action", "disabled": false}]}
- ✅ `non_support_card_keeps_the_resource_button` — {"buttons": [{"text": "資源", "mode": "resource", "disabled": false}, {"text": "行動", "mode": "action", "disabled": false}]}
