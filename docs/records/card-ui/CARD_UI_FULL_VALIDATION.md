# CARD UI FULL VALIDATION

日期：2026-05-03

總卡數：40

## 宣傳家 (propaganda)
- effects: optional_trash, build, move
- hand_before: ['可垃圾牌', '宣傳家']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 2}
- moves_before -> after: 3 -> 4
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 2, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 思想家 (propaganda)
- effects: optional_trash, build, move
- hand_before: ['可垃圾牌', '思想家']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 3}
- moves_before -> after: 3 -> 6
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 2, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 資助者 (money)
- effects: optional_trash, gain_resource
- hand_before: ['可垃圾牌', '資助者']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 4, 'propaganda': 2}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 資本家 (money)
- effects: optional_trash, gain_resource
- hand_before: ['可垃圾牌', '資本家']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 6, 'propaganda': 3}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 分神 (disruption)
- effects: optional_trash
- hand_before: ['可垃圾牌', '分神']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 0}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 內鬥 (disruption)
- effects: none
- hand_before: ['內鬥']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 0}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 領導 (command)
- effects: draw
- hand_before: ['領導']
- hand_after: ['抽牌D']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 1}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 謀劃 (command)
- effects: draw
- hand_before: ['謀劃']
- hand_after: ['抽牌D', '抽牌C']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 2}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 戰略 (command)
- effects: draw
- hand_before: ['戰略']
- hand_after: ['抽牌D', '抽牌C', '抽牌B']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 3}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 合作談判 (command)
- effects: shared_draw
- hand_before: ['合作談判']
- hand_after: ['抽牌D']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 1}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 1, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 高效行動 (command)
- effects: draw, discard_self
- hand_before: ['高效行動', '自棄1', '自棄2']
- hand_after: ['自棄1', '自棄2', '抽牌D']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 1, 'propaganda': 1}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 模仿戰術 (command)
- effects: peek_deck, topdeck_to_hand
- hand_before: ['模仿戰術']
- hand_after: ['抽牌D']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 2}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 乘勝追擊 (command)
- effects: gain_from_discard
- hand_before: ['乘勝追擊']
- hand_after: ['可回收牌']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 1, 'propaganda': 0}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 誘導虛耗 (command)
- effects: optional_trash, force_discard
- hand_before: ['可垃圾牌', '誘導虛耗']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 1}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 1, 'orgs': {'香港城': 2}}}

## 點燃熱情 (command)
- effects: draw, conditional_draw
- hand_before: ['點燃熱情']
- hand_after: ['抽牌D', '抽牌C']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 1}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 樹立信心 (command)
- effects: draw, conditional_draw
- hand_before: ['樹立信心']
- hand_after: ['抽牌D', '抽牌C']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 1, 'propaganda': 0}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 網羅人才 (command)
- effects: peek_deck, topdeck_to_hand
- hand_before: ['網羅人才']
- hand_after: ['抽牌D']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 1, 'propaganda': 1}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 凝聚共識 (command)
- effects: draw, discard_self, conditional_bonus
- hand_before: ['凝聚共識', '自棄1', '自棄2']
- hand_after: ['自棄1', '自棄2', '抽牌D']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 5}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 思想建設 (command)
- effects: extend_build_range
- hand_before: ['思想建設']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 1}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 擴大戰果 (command)
- effects: gain_any_from_discard
- hand_before: ['擴大戰果']
- hand_after: ['可回收牌']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 2, 'propaganda': 0}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 交通經驗丙 (transport)
- effects: extra_move
- hand_before: ['交通經驗丙']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 1, 'propaganda': 0}
- moves_before -> after: 3 -> 5
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 交通經驗乙 (transport)
- effects: extra_move
- hand_before: ['交通經驗乙']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 2, 'propaganda': 0}
- moves_before -> after: 3 -> 7
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 交通經驗甲 (transport)
- effects: extra_move
- hand_before: ['交通經驗甲']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 3, 'propaganda': 0}
- moves_before -> after: 3 -> 9
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 組織經驗丙 (organization)
- effects: build
- hand_before: ['組織經驗丙']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 1}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 2, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 組織經驗乙 (organization)
- effects: build, build
- hand_before: ['組織經驗乙']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 2}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 3, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 組織經驗甲 (organization)
- effects: build
- hand_before: ['組織經驗甲']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 1, 'propaganda': 2}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 2, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 批判 (purge)
- effects: trash_from_hand_or_discard
- hand_before: ['非起始牌', '批判']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 1}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 批鬥 (purge)
- effects: trash_from_hand_or_discard
- hand_before: ['非起始牌', '批鬥']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 2}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 爆料黑幕 (propaganda_special)
- effects: cancel_card, conditional_draw
- hand_before: ['爆料黑幕']
- hand_after: ['抽牌D']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 2}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 輿論丕變 (propaganda_special)
- effects: refresh_purchase_area, gain_resource
- hand_before: ['輿論丕變']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: True
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 2}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 行動預告 (propaganda_special)
- effects: topdeck_to_hand, gain_resource
- hand_before: ['行動預告']
- hand_after: ['抽牌D']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 3}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 派遣間諜 (spy)
- effects: dissolve
- hand_before: ['派遣間諜']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 1}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1} -> {}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 1}}} -> {'guest': {'hand': 2, 'orgs': {}}}

## 內應間諜 (spy)
- effects: dissolve
- hand_before: ['內應間諜']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 2}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1} -> {'北京': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 1}}} -> {'guest': {'hand': 2, 'orgs': {}}}

## 情報網 (spy)
- effects: add_internal_conflict, cancel_card
- hand_before: ['情報網']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 1, 'propaganda': 1}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 離間 (spy)
- effects: add_internal_conflict
- hand_before: ['離間']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 2}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 走漏風聲 (spy)
- effects: peek_deck, add_internal_conflict
- hand_before: ['走漏風聲']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 1}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 地下黨 (spy)
- effects: peek_deck, gain_any_from_discard
- hand_before: ['地下黨']
- hand_after: ['可回收牌']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 1, 'propaganda': 2}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 2, 'orgs': {'香港城': 2}}}

## 武裝者 (armed)
- effects: force_discard
- hand_before: ['武裝者']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 0, 'propaganda': 1}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 1, 'orgs': {'香港城': 2}}}

## 武裝小隊 (armed)
- effects: force_discard
- hand_before: ['武裝小隊']
- hand_after: []
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 1, 'propaganda': 1}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 0, 'orgs': {'香港城': 2}}}

## 武裝集團 (armed)
- effects: force_discard, conditional_draw
- hand_before: ['武裝集團']
- hand_after: ['抽牌D']
- hud_changed: True
- log_changed: True
- purchase_changed: False
- error: None
- resources_before -> after: {'money': 0, 'propaganda': 0} -> {'money': 1, 'propaganda': 2}
- moves_before -> after: 3 -> 3
- orgs_before -> after: {'北京': 1, '上海': 1} -> {'北京': 1, '上海': 1}
- opponents_before -> after: {'guest': {'hand': 2, 'orgs': {'香港城': 2}}} -> {'guest': {'hand': 0, 'orgs': {'香港城': 2}}}
