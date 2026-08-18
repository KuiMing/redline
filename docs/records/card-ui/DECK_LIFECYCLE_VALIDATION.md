# DECK LIFECYCLE VALIDATION

日期：2026-08-18

summary: {'total': 6, 'passed': 6, 'failed': 0}

## end_turn_discards_hand_resets_and_draws_to_five — PASS
- before: {'hand': ['H1', 'H2', 'H3'], 'draw_pile': ['D1', 'D2', 'D3', 'D4'], 'discard_pile': ['X1', 'X2'], 'hand_count': 3, 'draw_count': 4, 'discard_count': 2, 'total_cards': 9, 'resources': {'money': 7, 'propaganda': 6}, 'moves_left': 0}
- result: {'end_action_phase': {'success': True}}
- after: {'hand': ['H1', 'H2', 'H3', 'D4', 'D3'], 'draw_pile': ['D1', 'D2'], 'discard_pile': ['X1', 'X2'], 'hand_count': 5, 'draw_count': 2, 'discard_count': 2, 'total_cards': 9, 'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'turn_phase': 'action', 'current_player': 'other'}
- rule: 回合結束：棄掉當前手牌、重置資源與移動點為 0、補到 5 張且總牌數守恆。

## draw_reshuffles_discard_when_draw_pile_runs_out — PASS
- before: {'hand': [], 'draw_pile': ['D1', 'D2'], 'discard_pile': ['R1', 'R2', 'R3'], 'hand_count': 0, 'draw_count': 2, 'discard_count': 3, 'total_cards': 5}
- drawn: ['D2', 'D1', 'R1', 'R3']
- after: {'hand': [], 'draw_pile': ['R2'], 'discard_pile': [], 'hand_count': 0, 'draw_count': 1, 'discard_count': 0, 'total_cards': 1}
- rule: 牌庫不足抽牌時，棄牌堆洗回牌庫並繼續抽；不憑空增減牌。

## draw_with_insufficient_total_cards_draws_available_cards_only — PASS
- before: {'hand': [], 'draw_pile': ['Only1', 'Only2'], 'discard_pile': [], 'hand_count': 0, 'draw_count': 2, 'discard_count': 0, 'total_cards': 2}
- drawn: ['Only2', 'Only1']
- after: {'hand': [], 'draw_pile': [], 'discard_pile': [], 'hand_count': 0, 'draw_count': 0, 'discard_count': 0, 'total_cards': 0}
- rule: 牌庫與棄牌堆都不足時，不 crash；能抽幾張就抽幾張。

## ordinary_played_card_moves_from_hand_to_discard — PASS
- before: {'hand': ['追隨者'], 'draw_pile': [], 'discard_pile': [], 'hand_count': 1, 'draw_count': 0, 'discard_count': 0, 'total_cards': 1, 'resources': {'money': 0, 'propaganda': 0}}
- result: {'success': True}
- after: {'hand': [], 'draw_pile': [], 'discard_pile': ['追隨者'], 'hand_count': 0, 'draw_count': 0, 'discard_count': 1, 'total_cards': 1, 'resources': {'money': 0, 'propaganda': 1}}
- rule: 普通打出的卡從手牌離開後進玩家棄牌堆，並保持玩家牌張總數守恆。

## purchased_random_market_card_enters_discard_and_leaves_market — PASS
- before: {'hand': ['追隨者', '追隨者', '樂捐者', '追隨者', '追隨者'], 'draw_pile': ['追隨者', '追隨者', '追隨者', '樂捐者', '樂捐者'], 'discard_pile': [], 'hand_count': 5, 'draw_count': 5, 'discard_count': 0, 'total_cards': 10, 'resources': {'money': 99, 'propaganda': 99}, 'purchase_area_count': 11, 'purchase_area': ['宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥', '東洋奧援', '印度奧援', '領導', '歐洲奧援', '行動募資'], 'buy_index': 6, 'card_to_buy': '東洋奧援'}
- result: {'success': True, 'purchased_cards': ['東洋奧援'], 'payment': {'money': 1, 'propaganda': 2}}
- after: {'hand': ['追隨者', '追隨者', '樂捐者', '追隨者', '追隨者'], 'draw_pile': ['追隨者', '追隨者', '追隨者', '樂捐者', '樂捐者'], 'discard_pile': ['東洋奧援'], 'hand_count': 5, 'draw_count': 5, 'discard_count': 1, 'total_cards': 11, 'resources': {'money': 98, 'propaganda': 97}, 'purchase_area_count': 10, 'purchase_area': ['宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥', '印度奧援', '領導', '歐洲奧援', '行動募資']}
- rule: 購買隨機市場牌後，該牌進玩家棄牌堆，並從購買區移除；補市場由回合結束流程處理。

## end_turn_refills_random_market_to_static_plus_five — PASS
- before_market_count: 10
- result: {'end_action_phase': {'success': True}}
- after_market_count: 11
- after_market: ['宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥', '印度奧援', '領導', '歐洲奧援', '行動募資', '模仿戰術']
- rule: 回合結束時購買區補回常設 6 張 + 隨機 5 張。
