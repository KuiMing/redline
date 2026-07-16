# 奧援卡「資源」按鈕改「詳情」驗證

可重跑指令：`python3 scripts/validate_support_card_detail_button.py`

- total: 7 / passed: 7 / failed: 0
- screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/action-cards/support_card_detail_button.png

## Results
- ✅ `support_card_shows_detail_and_discard_not_labeled_resource` — {"buttons": [{"text": "詳情", "mode": "detail", "disabled": false}, {"text": "棄置", "mode": "resource", "disabled": false}, {"text": "行動", "mode": "action", "disabled": false}]}
- ✅ `detail_button_is_never_disabled` — {"detail_disabled": false}
- ✅ `clicking_detail_does_not_consume_or_play_the_card` — {"before_hand": ["臺灣奧援"], "after_hand": ["臺灣奧援"]}
- ✅ `clicking_detail_flashes_the_card_for_feedback` — {"flash_applied": true}
- ✅ `card_face_already_shows_all_three_tier_effect_lines` — {"face_text": "III級（臺灣主導）：瓦解己方組織1格內的1個對手組織，並在該城鎮建立1個組織\nII級（東洋/南洋其一主導）：瓦解己方組織1格內的1個對手組織。\nI級（皆未主導）：獲得1點宣傳。"}
- ✅ `red_army_support_card_also_shows_detail_and_discard_not_labeled_resource` — {"buttons": [{"text": "詳情", "mode": "detail", "disabled": false}, {"text": "棄置", "mode": "resource", "disabled": false}, {"text": "行動", "mode": "action", "disabled": false}]}
- ✅ `non_support_card_keeps_the_resource_button` — {"buttons": [{"text": "資源", "mode": "resource", "disabled": false}, {"text": "行動", "mode": "action", "disabled": false}]}
