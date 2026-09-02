# 奧援卡「單一變體地區判定」與「棄置」驗證

可重跑指令：`python3 scripts/validate/validate_support_card_variant_and_discard.py`

- total: 6 / passed: 6 / failed: 0
- screenshot: /Users/benmini/.openclaw/workspace/redline/docs/records/support-cards/support_card_variant_and_discard.png

## Results
- ✅ `variant0_matches_own_pair` — {"variant_index": 0, "orgs": {"伊斯坦堡": 1}, "expected_tier": 2, "actual_tier": 2}
- ✅ `variant0_ignores_other_variant_pair` — {"variant_index": 0, "orgs": {"東京": 1}, "expected_tier": 1, "actual_tier": 1}
- ✅ `variant1_matches_own_pair` — {"variant_index": 1, "orgs": {"東京": 1}, "expected_tier": 2, "actual_tier": 2}
- ✅ `variant1_ignores_other_variant_pair` — {"variant_index": 1, "orgs": {"伊斯坦堡": 1}, "expected_tier": 1, "actual_tier": 1}
- ✅ `card_face_shows_only_this_cards_own_printed_variant_regions` — {"face_text": "III級（英美主導）：獲得3點資金。\nII級（東洋/臺灣其一主導）：獲得2點資金。\nI級（皆未主導）：獲得1點資金。"}
- ✅ `discard_button_removes_card_from_hand_with_no_resource_gain` — {"before_hand": ["英美奧援"], "after_hand": [], "after_discard": ["英美奧援"], "before_resources": {"money": 0, "propaganda": 0}, "after_resources": {"money": 0, "propaganda": 0}}
