# 行動卡與奧援卡完整卡面瀏覽器驗證

可重跑：`uv run --with playwright python scripts/validate_playable_card_art_browser.py`

- total: 7 / passed: 7 / failed: 0

- ✅ `all_action_and_support_art_assets_installed` — {"action_count": 46, "support_count": 17, "action_sizes": [[1100, 1350]], "support_sizes": [[1100, 1350]]}
- ✅ `hand_cards_use_complete_action_and_support_faces` — [{"name": "宣傳家", "srcFile": "宣傳家.png", "alt": "宣傳家完整卡面", "natural": [1100, 1350], "faceRect": {"width": 245.25, "height": 306}, "buttons": ["資源", "行動"]}, {"name": "情報網", "srcFile": "情報網.png", "alt": "情報網完整卡面", "natural": [1100, 1350], "faceRect": {"width": 245.25, "height": 306}, "buttons": ["資源", "行動"]}, {"name": "英美奧援", "srcFile": "01_英美奧援_歐洲-天方.png", "alt": "英美奧援完整卡面", "natural": [1100, 1350], "faceRect": {"width": 245.25, "height": 306}, "buttons": ["棄置", "行動"]}]
- ✅ `static_and_random_purchase_areas_use_complete_faces` — {"expected": 11, "cards": 11, "images": 11, "loaded": 11, "failed": 0, "staticCards": 6, "staticCountBadges": 6, "randomCountBadges": 0}
- ✅ `clicking_card_opens_correct_aspect_ratio_art_preview` — {"srcFile": "宣傳家.png", "natural": [1100, 1350], "rect": {"width": 457.875, "height": 562.5}, "ratioDelta": 0.0008148148148148238, "countBadge": false}
- ✅ `main_art_browser_console_has_no_errors` — []
- ✅ `support_variant_one_uses_its_own_printed_face` — {"variantIndex": "1", "srcFile": "02_英美奧援_東洋-臺灣.png", "alt": "英美奧援完整卡面"}
- ✅ `support_art_browser_console_has_no_errors` — []
