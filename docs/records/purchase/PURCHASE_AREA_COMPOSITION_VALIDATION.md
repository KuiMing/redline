# C3 購買區組成資料校驗

可重跑指令：`python3 scripts/validate_purchase_area_composition.py`

- total: 8 / passed: 8 / failed: 0

## Checks（硬性：資料一致性與現行組成行為）

- PASS static_supply_matches_csv: {"code": {"宣傳家": 15, "思想家": 15, "資助者": 15, "資本家": 15, "分神": 30, "內鬥": 20}, "csv": {"宣傳家": 15, "思想家": 15, "資助者": 15, "資本家": 15, "分神": 30, "內鬥": 20}}
- PASS static_area_is_exactly_the_six_fixed_cards: {"runtime": ["宣傳家", "思想家", "資助者", "資本家", "分神", "內鬥"]}
- PASS starters_are_csv_only: {"csv_starters": ["樂捐者", "追隨者"]}
- PASS structured_json_matches_csv_nonstarters: {"missing_in_json": [], "extra_in_json": []}
- PASS taxonomy_names_match_support_csv: {"taxonomy_only": [], "csv_only": []}
- PASS sample_53_deck_is_18_support_plus_35_general: {"support": 18, "general": 35, "total": 53}
- PASS sample_53_deck_has_no_static_or_starter_cards: {"unexpected": []}
- PASS all_cards_deck_is_the_full_pool: {"total": 70, "expected": 70, "support_pool": 32, "general_pool": 38}

## 規則書步驟⑧偏差報告（資訊性，不列失敗）

- **rulebook_step8_expected_deck**: "間諜/組織/整肅全部 47 張 + 隨機 18 張奧援 + 隨機 35 張其它一般卡 = 100 張"
- **deviation_1_market_modes**: "sample_53（lobby「53 張核心」選項）＝18 奧援＋35 一般卡，未保證間諜/組織/整肅全數入庫；all_cards（「全部卡牌」）＝整個 pool。兩種模式都不是規則書步驟⑧的組成——sample_53 為刻意的 MVP 精簡選項。"
- **deviation_2_structured_json_has_no_copies**: "action_cards_structured.v1.1.json 沒有張數欄位，_initial_purchase_deck 對每種一般卡 fallback 為 1 份；CSV 卡牌張數（如 批判 8、派遣間諜 5）目前不影響牌庫內份數。"
- **deviation_2_affected_cards**: {"交通經驗丙": {"csv": 7, "deck_builder": 1}, "交通經驗乙": {"csv": 5, "deck_builder": 1}, "交通經驗甲": {"csv": 3, "deck_builder": 1}, "領導": {"csv": 7, "deck_builder": 1}, "謀劃": {"csv": 5, "deck_builder": 1}, "戰略": {"csv": 3, "deck_builder": 1}, "合作談判": {"csv": 5, "deck_builder": 1}, "高效行動": {"csv": 5, "deck_builder": 1}, "模仿戰術": {"csv": 5, "deck_builder": 1}, "乘勝追擊": {"csv": 5, "deck_builder": 1}, "擴大戰果": {"csv": 5, "deck_builder": 1}, "誘導虛耗": {"csv": 5, "deck_builder": 1}, "點燃熱情": {"csv": 5, "deck_builder": 1}, "樹立信心": {"csv": 5, "deck_builder": 1}, "網羅人才": {"csv": 3, "deck_builder": 1}, "凝聚共識": {"csv": 5, "deck_builder": 1}, "思想建設": {"csv": 5, "deck_builder": 1}, "派遣間諜": {"csv": 5, "deck_builder": 1}, "內應間諜": {"csv": 3, "deck_builder": 1}, "情報網": {"csv": 3, "deck_builder": 1}, "離間": {"csv": 5, "deck_builder": 1}, "走漏風聲": {"csv": 5, "deck_builder": 1}, "地下黨": {"csv": 3, "deck_builder": 1}, "組織經驗丙": {"csv": 5, "deck_builder": 1}, "組織經驗乙": {"csv": 3, "deck_builder": 1}, "組織經驗甲": {"csv": 3, "deck_builder": 1}, "批判": {"csv": 8, "deck_builder": 1}, "批鬥": {"csv": 4, "deck_builder": 1}, "武裝者": {"csv": 8, "deck_builder": 1}, "武裝小隊": {"csv": 5, "deck_builder": 1}, "武裝集團": {"csv": 3, "deck_builder": 1}, "爆料黑幕": {"csv": 4, "deck_builder": 1}, "輿論丕變": {"csv": 6, "deck_builder": 1}, "行動預告": {"csv": 5, "deck_builder": 1}, "企業人脈": {"csv": 5, "deck_builder": 1}, "產業滲透": {"csv": 4, "deck_builder": 1}, "企畫遊說": {"csv": 7, "deck_builder": 1}, "行動募資": {"csv": 4, "deck_builder": 1}}
- **deviation_3_support_copies**: {"note": "support CSV 每種奧援有兩列（不同區域優待組合）各 4 張、合計 8；taxonomy 每種 4 張。兩列是「同卡雙資料行」或「各自成卡」需規則書確認。", "csv_totals": {"英美奧援": 8, "東洋奧援": 8, "南洋奧援": 8, "印度奧援": 8, "天方奧援": 8, "歐洲奧援": 8, "北國奧援": 8, "臺灣奧援": 8, "紅軍奧援": 1}, "taxonomy": {"英美奧援": 4, "東洋奧援": 4, "南洋奧援": 4, "印度奧援": 4, "天方奧援": 4, "歐洲奧援": 4, "北國奧援": 4, "臺灣奧援": 4, "紅軍奧援": 1}}
- **deviation_4_deck_refill**: "規則書「牌庫用盡時從剩餘行動卡任取一疊補上」；實作為重建整份 initial deck（近似）。"
- **mandatory_kind_copies_csv**: {"派遣間諜": 5, "內應間諜": 3, "情報網": 3, "離間": 5, "走漏風聲": 5, "地下黨": 3, "組織經驗丙": 5, "組織經驗乙": 3, "組織經驗甲": 3, "批判": 8, "批鬥": 4}
