# CARD ACTION CORRECTNESS VALIDATION

日期：2026-05-14

summary: {'total': 8, 'passed': 8, 'failed': 0}

## 追隨者_grants_intrinsic_resource_and_discards_played_card — PASS
- result: {'success': True}
- before: {'resources': {'money': 0, 'propaganda': 0}, 'hand_count': 1, 'moves_left': 0, 'discard': []}
- after: {'resources': {'money': 0, 'propaganda': 1}, 'hand_count': 0, 'moves_left': 0, 'discard': ['追隨者']}
- expected_resources: {'money': 0, 'propaganda': 1}

## 樂捐者_grants_intrinsic_resource_and_discards_played_card — PASS
- result: {'success': True}
- before: {'resources': {'money': 0, 'propaganda': 0}, 'hand_count': 1, 'moves_left': 0, 'discard': []}
- after: {'resources': {'money': 1, 'propaganda': 0}, 'hand_count': 0, 'moves_left': 0, 'discard': ['樂捐者']}
- expected_resources: {'money': 1, 'propaganda': 0}

## 宣傳家_effect_and_removed_card_destination — PASS
- result: {'success': True}
- before: {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply': 1, 'discard': []}
- after: {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 1, 'orgs': {'北京': 2}, 'supply': 2, 'discard': []}
- expected: {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 1, 'orgs': {'北京': 2}, 'supply_delta': 1}
- rule: 被移除的卡牌直接回到購買區；常設卡移除後對應庫存 +1。內鬥沒有移除效果，正常進棄牌堆。

## 思想家_effect_and_removed_card_destination — PASS
- result: {'success': True}
- before: {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply': 1, 'discard': []}
- after: {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 3, 'orgs': {'北京': 2}, 'supply': 2, 'discard': []}
- expected: {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 3, 'orgs': {'北京': 2}, 'supply_delta': 1}
- rule: 被移除的卡牌直接回到購買區；常設卡移除後對應庫存 +1。內鬥沒有移除效果，正常進棄牌堆。

## 資助者_effect_and_removed_card_destination — PASS
- result: {'success': True}
- before: {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply': 1, 'discard': []}
- after: {'resources': {'money': 2, 'propaganda': 2}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply': 2, 'discard': []}
- expected: {'resources': {'money': 2, 'propaganda': 2}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply_delta': 1}
- rule: 被移除的卡牌直接回到購買區；常設卡移除後對應庫存 +1。內鬥沒有移除效果，正常進棄牌堆。

## 資本家_effect_and_removed_card_destination — PASS
- result: {'success': True}
- before: {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply': 1, 'discard': []}
- after: {'resources': {'money': 3, 'propaganda': 3}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply': 2, 'discard': []}
- expected: {'resources': {'money': 3, 'propaganda': 3}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply_delta': 1}
- rule: 被移除的卡牌直接回到購買區；常設卡移除後對應庫存 +1。內鬥沒有移除效果，正常進棄牌堆。

## 分神_effect_and_removed_card_destination — PASS
- result: {'success': True}
- before: {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply': 1, 'discard': []}
- after: {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply': 2, 'discard': []}
- expected: {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply_delta': 1}
- rule: 被移除的卡牌直接回到購買區；常設卡移除後對應庫存 +1。內鬥沒有移除效果，正常進棄牌堆。

## 內鬥_effect_and_removed_card_destination — PASS
- result: {'success': True}
- before: {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply': 1, 'discard': []}
- after: {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply': 1, 'discard': ['內鬥']}
- expected: {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply_delta': 0}
- rule: 被移除的卡牌直接回到購買區；常設卡移除後對應庫存 +1。內鬥沒有移除效果，正常進棄牌堆。
