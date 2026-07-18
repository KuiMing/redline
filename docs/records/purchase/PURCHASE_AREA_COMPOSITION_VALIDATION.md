# C3 購買區組成資料校驗

可重跑指令：`python3 scripts/validate_purchase_area_composition.py`

- total: 10 / passed: 10 / failed: 0

## Checks（硬性：資料一致性與現行組成行為）

- PASS static_supply_matches_csv: {"code": {"宣傳家": 15, "思想家": 15, "資助者": 15, "資本家": 15, "分神": 30, "內鬥": 20}, "csv": {"宣傳家": 15, "思想家": 15, "資助者": 15, "資本家": 15, "分神": 30, "內鬥": 20}}
- PASS static_area_is_exactly_the_six_fixed_cards: {"runtime": ["宣傳家", "思想家", "資助者", "資本家", "分神", "內鬥"]}
- PASS starters_are_csv_only: {"csv_starters": ["樂捐者", "追隨者"]}
- PASS structured_json_matches_csv_nonstarters: {"missing_in_json": [], "extra_in_json": []}
- PASS taxonomy_names_match_support_csv: {"taxonomy_only": [], "csv_only": []}
- PASS sample_53_deck_is_18_support_plus_35_general: {"support": 18, "general": 35, "total": 53}
- PASS sample_53_deck_has_no_static_or_starter_cards: {"unexpected": []}
- PASS all_cards_deck_is_the_full_pool: {"total": 245, "expected": 245, "support_pool": 64, "general_pool": 181}
- PASS support_taxonomy_copies_match_csv_row_totals: {"csv_totals": {"英美奧援": 8, "東洋奧援": 8, "南洋奧援": 8, "印度奧援": 8, "天方奧援": 8, "歐洲奧援": 8, "北國奧援": 8, "臺灣奧援": 8}, "taxonomy": {"英美奧援": 8, "東洋奧援": 8, "南洋奧援": 8, "印度奧援": 8, "天方奧援": 8, "歐洲奧援": 8, "北國奧援": 8, "臺灣奧援": 8}}
- PASS structured_general_copies_match_csv: {"mismatched": {}}

## 規則書步驟⑧偏差報告（資訊性，不列失敗）

- **rulebook_step8_expected_deck**: "間諜/組織/整肅全部 47 張 + 隨機 18 張奧援 + 隨機 35 張其它一般卡 = 100 張"
- **deviation_1_market_modes**: "sample_53（lobby「53 張核心」選項）＝18 奧援＋35 一般卡，未保證間諜/組織/整肅全數入庫；all_cards（「全部卡牌」）＝整個 pool。兩種模式都不是規則書步驟⑧的組成——sample_53 為刻意的 MVP 精簡選項。2026-07-18 使用者裁決：先不改；日後若要做規則書 100 張模式（間諜/組織/整肅全數＋隨機18奧援＋隨機35其它），可取代 sample_53 或做成 lobby 第三個選項。"
- **resolved_2026_07_17_general_copies**: "原 deviation_2：structured JSON 已補 copies 欄位（來源 CSV 卡牌張數），_initial_purchase_deck 依實體張數展開一般卡池（181 張），sample_53 的隨機 35 張改為從實體卡池抽出（同名卡可重複，等同實際洗牌）；all_cards 為完整 245 張。"
- **resolved_2026_07_16_support_copies**: {"note": "原 deviation_3：support CSV 每種奧援兩列（各一種實體印刷變體、各印一組不同 II 級地區）各 4 張、合計 8；taxonomy 曾誤記頂層 copies 為 4（只抄一列）。已修正 taxonomy 讓每個 regions[] 項目各自帶 copies:4，頂層加總為 8，且 game.py 的 _support_card_tier 改為只依牌本身的 variant_index 檢查該卡印刷的那組地區，不再把兩種變體地區併查。", "csv_totals": {"英美奧援": 8, "東洋奧援": 8, "南洋奧援": 8, "印度奧援": 8, "天方奧援": 8, "歐洲奧援": 8, "北國奧援": 8, "臺灣奧援": 8, "紅軍奧援": 1}, "taxonomy": {"英美奧援": 8, "東洋奧援": 8, "南洋奧援": 8, "印度奧援": 8, "天方奧援": 8, "歐洲奧援": 8, "北國奧援": 8, "臺灣奧援": 8, "紅軍奧援": 1}}
- **deviation_4_deck_refill**: "規則書「牌庫用盡時從剩餘行動卡任取一疊補上」；實作為重建整份 initial deck（近似，已買走的卡會再次出現）。2026-07-18 使用者裁決：先不改；日後若要做，可把開局未抽進牌庫的卡記成剩卡池、用盡時從中補、剩卡用完即不再補。"
- **mandatory_kind_copies_csv**: {"派遣間諜": 5, "內應間諜": 3, "情報網": 3, "離間": 5, "走漏風聲": 5, "地下黨": 3, "組織經驗丙": 5, "組織經驗乙": 3, "組織經驗甲": 3, "批判": 8, "批鬥": 4}
