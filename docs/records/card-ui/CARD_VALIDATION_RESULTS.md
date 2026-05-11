# CARD VALIDATION RESULTS

日期：2026-05-03

總卡數：40

## 總結

- 已完成 40 張 action card 的第二輪可執行驗證。
- 本輪已修正第一輪驗證腳本中對出牌索引的錯誤假設，重新驗證後：
  - 40/40 張卡 `play_success`
  - 40/40 張卡 `card_left_hand`
- 也就是說，在目前的 MVP 規則語義下，40 張 action card 已全部通過第二輪基礎可執行驗證。
- 本報表仍屬於「可執行驗證」結果，不等於最終規則完稿驗收；若規則語義後續更精細，仍可能需要再做規則級驗收。

## 宣傳家 (propaganda)
- effects: optional_trash, build, move
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 2
- hand before → after: 2 → 0
- moves_left before → after: 3 → 4
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 2, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '宣傳家']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': True, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 trashed 可垃圾牌', '[Turn 1] player1 built organization in 北京 via card effect', '[Turn 1] player1 played 宣傳家']

## 思想家 (propaganda)
- effects: optional_trash, build, move
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 3
- hand before → after: 2 → 0
- moves_left before → after: 3 → 6
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 2, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '思想家']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': True, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 trashed 可垃圾牌', '[Turn 1] player1 built organization in 北京 via card effect', '[Turn 1] player1 played 思想家']

## 資助者 (money)
- effects: optional_trash, gain_resource
- checks: play_success, card_left_hand
- resources delta: money 4, propaganda 2
- hand before → after: 2 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '資助者']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': True, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 trashed 可垃圾牌', '[Turn 1] player1 played 資助者']

## 資本家 (money)
- effects: optional_trash, gain_resource
- checks: play_success, card_left_hand
- resources delta: money 6, propaganda 3
- hand before → after: 2 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '資本家']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': True, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 trashed 可垃圾牌', '[Turn 1] player1 played 資本家']

## 分神 (disruption)
- effects: optional_trash
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 2 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '分神']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 trashed 可垃圾牌', '[Turn 1] player1 played 分神']

## 內鬥 (disruption)
- effects: none
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '內鬥']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 內鬥']

## 領導 (command)
- effects: draw
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 1
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '領導']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 領導']

## 謀劃 (command)
- effects: draw
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 2
- hand before → after: 1 → 2
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '謀劃']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 謀劃']

## 戰略 (command)
- effects: draw
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 3
- hand before → after: 1 → 3
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '戰略']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 戰略']

## 合作談判 (command)
- effects: shared_draw
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 1
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '合作談判']
- purchase_area after: []
- other_hands before → after: {'player2': 1} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 合作談判']

## 高效行動 (command)
- effects: draw, discard_self
- checks: play_success, card_left_hand
- resources delta: money 1, propaganda 1
- hand before → after: 3 → 3
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '抽牌B', '抽牌C', '高效行動']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 高效行動']

## 模仿戰術 (command)
- effects: peek_deck, topdeck_to_hand
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 2
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '模仿戰術']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 模仿戰術']

## 乘勝追擊 (command)
- effects: gain_from_discard
- checks: play_success, card_left_hand
- resources delta: money 1, propaganda 0
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['乘勝追擊']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 乘勝追擊']

## 誘導虛耗 (command)
- effects: optional_trash, force_discard
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 1
- hand before → after: 2 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '誘導虛耗']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 1}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 trashed 可垃圾牌', '[Turn 1] player1 played 誘導虛耗']

## 點燃熱情 (command)
- effects: draw, conditional_draw
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 1
- hand before → after: 1 → 2
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '點燃熱情']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': True, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 點燃熱情']

## 樹立信心 (command)
- effects: draw, conditional_draw
- checks: play_success, card_left_hand
- resources delta: money 1, propaganda 0
- hand before → after: 1 → 2
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '樹立信心']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': True, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 樹立信心']

## 網羅人才 (command)
- effects: peek_deck, topdeck_to_hand
- checks: play_success, card_left_hand
- resources delta: money 1, propaganda 1
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '網羅人才']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 網羅人才']

## 凝聚共識 (command)
- effects: draw, discard_self, conditional_bonus
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 5
- hand before → after: 3 → 3
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '抽牌B', '抽牌C', '凝聚共識']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': True, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 凝聚共識']

## 思想建設 (command)
- effects: extend_build_range
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 1
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '思想建設']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 思想建設']

## 擴大戰果 (command)
- effects: gain_any_from_discard
- checks: play_success, card_left_hand
- resources delta: money 2, propaganda 0
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['擴大戰果']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 擴大戰果']

## 交通經驗丙 (transport)
- effects: extra_move
- checks: play_success, card_left_hand
- resources delta: money 1, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 5
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '交通經驗丙']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 交通經驗丙']

## 交通經驗乙 (transport)
- effects: extra_move
- checks: play_success, card_left_hand
- resources delta: money 2, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 7
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '交通經驗乙']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 交通經驗乙']

## 交通經驗甲 (transport)
- effects: extra_move
- checks: play_success, card_left_hand
- resources delta: money 3, propaganda 0
- hand before → after: 1 → 0
- moves_left before → after: 3 → 9
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '交通經驗甲']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 交通經驗甲']

## 組織經驗丙 (organization)
- effects: build
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 1
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 2, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '組織經驗丙']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 built organization in 北京 via card effect', '[Turn 1] player1 played 組織經驗丙']

## 組織經驗乙 (organization)
- effects: build, build
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 2
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 3, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '組織經驗乙']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 built organization in 北京 via card effect', '[Turn 1] player1 built organization in 北京 via card effect', '[Turn 1] player1 played 組織經驗乙']

## 組織經驗甲 (organization)
- effects: build
- checks: play_success, card_left_hand
- resources delta: money 1, propaganda 2
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 2, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '組織經驗甲']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 built organization in 北京 via card effect', '[Turn 1] player1 played 組織經驗甲']

## 批判 (purge)
- effects: trash_from_hand_or_discard
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 1
- hand before → after: 2 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['追隨者', '棄牌區非起始牌', '批判']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': True, 'successful_discard': False}
- log tail: ['[Turn 1] player1 trashed 非起始牌', '[Turn 1] player1 played 批判']

## 批鬥 (purge)
- effects: trash_from_hand_or_discard
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 2
- hand before → after: 2 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['追隨者', '批鬥']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': True, 'successful_discard': False}
- log tail: ['[Turn 1] player1 trashed 非起始牌', '[Turn 1] player1 trashed 棄牌區非起始牌', '[Turn 1] player1 played 批鬥']

## 爆料黑幕 (propaganda_special)
- effects: cancel_card, conditional_draw
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 2
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '爆料黑幕']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'canceled_propaganda_card': True}
- log tail: ['[Turn 1] player1 triggered cancel-card effect', '[Turn 1] player1 played 爆料黑幕']

## 輿論丕變 (propaganda_special)
- effects: refresh_purchase_area, gain_resource
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 2
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '輿論丕變']
- purchase_area after: ['市場4', '市場3', '市場2']
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 輿論丕變']

## 行動預告 (propaganda_special)
- effects: topdeck_to_hand, gain_resource
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 3
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '行動預告']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 行動預告']

## 派遣間諜 (spy)
- effects: dissolve
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 1
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1} → {}
- discard after: ['棄牌A', '棄牌B', '派遣間諜']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 dissolved 1 organization from player2 at 香港城', '[Turn 1] player1 played 派遣間諜']

## 內應間諜 (spy)
- effects: dissolve
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 2
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1} → {'北京': 1}
- discard after: ['棄牌A', '棄牌B', '內應間諜']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 dissolved 1 organization from player2 at 香港城', '[Turn 1] player1 played 內應間諜']

## 情報網 (spy)
- effects: add_internal_conflict, cancel_card
- checks: play_success, card_left_hand
- resources delta: money 1, propaganda 1
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '內鬥', '情報網']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False, 'canceled_propaganda_card': True}
- log tail: ['[Turn 1] player1 gained 1 內鬥 card(s)', '[Turn 1] player1 triggered cancel-card effect', '[Turn 1] player1 played 情報網']

## 離間 (spy)
- effects: add_internal_conflict
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 2
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '內鬥', '內鬥', '內鬥', '離間']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 gained 3 內鬥 card(s)', '[Turn 1] player1 played 離間']

## 走漏風聲 (spy)
- effects: peek_deck, add_internal_conflict
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 1
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '內鬥', '走漏風聲']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 gained 1 內鬥 card(s)', '[Turn 1] player1 played 走漏風聲']

## 地下黨 (spy)
- effects: peek_deck, gain_any_from_discard
- checks: play_success, card_left_hand
- resources delta: money 1, propaganda 2
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['地下黨']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 2}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 地下黨']

## 武裝者 (armed)
- effects: force_discard
- checks: play_success, card_left_hand
- resources delta: money 0, propaganda 1
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '武裝者']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 1}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 武裝者']

## 武裝小隊 (armed)
- effects: force_discard
- checks: play_success, card_left_hand
- resources delta: money 1, propaganda 1
- hand before → after: 1 → 0
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '武裝小隊']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 0}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': False}
- log tail: ['[Turn 1] player1 played 武裝小隊']

## 武裝集團 (armed)
- effects: force_discard, conditional_draw
- checks: play_success, card_left_hand
- resources delta: money 1, propaganda 2
- hand before → after: 1 → 1
- moves_left before → after: 3 → 3
- orgs before → after: {'北京': 1, '上海': 1} → {'北京': 1, '上海': 1}
- discard after: ['棄牌A', '棄牌B', '武裝集團']
- purchase_area after: []
- other_hands before → after: {'player2': 2} → {'player2': 0}
- turn_log after: {'played_money_card': False, 'played_propaganda_card': False, 'non_starter_discard': False, 'successful_discard': True}
- log tail: ['[Turn 1] player1 played 武裝集團']
