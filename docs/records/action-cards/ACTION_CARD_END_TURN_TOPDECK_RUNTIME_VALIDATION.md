# Action Card Topdeck-Right Runtime Validation

Generated at: `2026-08-07T23:18:04`

Summary: 5 passed / 0 failed / 5 total.

## Scope (2026-08-07 改版)
- 打出 `行動預告`/`行動募資` 時立刻拿到宣傳/資金（本回合可花用），頂牌變成玩家主動觸發的獨立動作。
- 買牌前點頂牌：回傳錯誤、不消耗權利。買牌後點頂牌：候選牌只有 1 張時自動置頂；2+ 張時開選擇視窗。
- 同一回合打出多張，各自累積成獨立的頂牌權利，可分次使用；沒用完的權利在按下「結束回合」時自動逐一跳出選擇，選完才真正結束回合。
- 完全沒有候選牌時，剩餘權利在回合結束時直接作廢，不會卡住回合推進。

## play_announce_action_grants_propaganda_and_banks_right — passed

- failures: `[]`
- before: `{'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player_index': 0, 'hand': ['行動預告'], 'draw_pile': ['紅軍奧援', '追隨者', '追隨者', '追隨者', '追隨者', '追隨者'], 'discard_pile': [], 'resources': {'money': 0, 'propaganda': 0}, 'pending_topdeck_uses': 0, 'pending_choice': None, 'action_log_tail': []}`
- after: `{'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player_index': 0, 'hand': [], 'draw_pile': ['紅軍奧援', '追隨者', '追隨者', '追隨者', '追隨者', '追隨者'], 'discard_pile': ['行動預告'], 'resources': {'money': 0, 'propaganda': 1}, 'pending_topdeck_uses': 1, 'pending_choice': None, 'action_log_tail': ['[Turn 1] P1 打出 行動預告，獲得 1 次頂牌權利（可在購買後、回合結束前使用）', '[Turn 1] P1 played 行動預告']}`

## manual_use_with_single_candidate_auto_placed — passed

- failures: `[]`
- before: `{'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player_index': 0, 'hand': [], 'draw_pile': ['追隨者', '樂捐者', '追隨者', '追隨者', '樂捐者'], 'discard_pile': ['PurchasedCard'], 'resources': {'money': 1, 'propaganda': 0}, 'pending_topdeck_uses': 1, 'pending_choice': None, 'action_log_tail': ['[Turn 1] P1 打出 行動募資，獲得 1 次頂牌權利（可在購買後、回合結束前使用）', '[Turn 1] P1 played 行動募資']}`
- after: `{'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player_index': 0, 'hand': [], 'draw_pile': ['追隨者', '樂捐者', '追隨者', '追隨者', '樂捐者', 'PurchasedCard'], 'discard_pile': [], 'resources': {'money': 1, 'propaganda': 0}, 'pending_topdeck_uses': 0, 'pending_choice': None, 'action_log_tail': ['[Turn 1] P1 打出 行動募資，獲得 1 次頂牌權利（可在購買後、回合結束前使用）', '[Turn 1] P1 played 行動募資', '[Turn 1] P1 使用頂牌權利，將 PurchasedCard 置於牌庫頂']}`

## manual_use_before_any_purchase_errors_without_losing_right — passed

- failures: `[]`
- before: `{'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player_index': 0, 'hand': [], 'draw_pile': ['樂捐者', '追隨者', '樂捐者', '追隨者', '追隨者'], 'discard_pile': ['行動預告'], 'resources': {'money': 0, 'propaganda': 1}, 'pending_topdeck_uses': 1, 'pending_choice': None, 'action_log_tail': ['[Turn 1] P1 打出 行動預告，獲得 1 次頂牌權利（可在購買後、回合結束前使用）', '[Turn 1] P1 played 行動預告']}`
- after: `{'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player_index': 0, 'hand': [], 'draw_pile': ['樂捐者', '追隨者', '樂捐者', '追隨者', '追隨者'], 'discard_pile': ['行動預告'], 'resources': {'money': 0, 'propaganda': 1}, 'pending_topdeck_uses': 1, 'pending_choice': None, 'action_log_tail': ['[Turn 1] P1 打出 行動預告，獲得 1 次頂牌權利（可在購買後、回合結束前使用）', '[Turn 1] P1 played 行動預告']}`

## end_turn_auto_drains_two_stacked_rights_before_advancing — passed

- failures: `[]`
- after_plays: `{'turn_phase': <TurnPhase.END: 'end'>, 'current_player_index': 0, 'hand': [], 'draw_pile': ['Bottom1', 'Bottom2', 'Bottom3', 'Bottom4', 'Bottom5', 'Bottom6', 'Bottom7'], 'discard_pile': ['第一張買的牌', '第二張買的牌', '第三張買的牌'], 'resources': {'money': 0, 'propaganda': 2}, 'pending_topdeck_uses': 2, 'pending_choice': None, 'action_log_tail': ['[Turn 1] P1 打出 行動預告，獲得 1 次頂牌權利（可在購買後、回合結束前使用）', '[Turn 1] P1 played 行動預告', '[Turn 1] P1 打出 行動預告，獲得 1 次頂牌權利（可在購買後、回合結束前使用）', '[Turn 1] P1 played 行動預告']}`
- first_prompted: `{'turn_phase': <TurnPhase.END: 'end'>, 'current_player_index': 0, 'hand': [], 'draw_pile': ['Bottom1', 'Bottom2', 'Bottom3', 'Bottom4', 'Bottom5', 'Bottom6', 'Bottom7'], 'discard_pile': ['第一張買的牌', '第二張買的牌', '第三張買的牌'], 'resources': {'money': 0, 'propaganda': 2}, 'pending_topdeck_uses': 1, 'pending_choice': {'type': 'card_choice', 'choice_key': 'topdeck_purchased_choice', 'player_id': 'p1', 'prompt': '行動預告／行動募資：選擇 1 張本回合購得的牌置於牌庫頂。', 'cards': ['第一張買的牌', '第二張買的牌', '第三張買的牌']}, 'action_log_tail': ['[Turn 1] P1 打出 行動預告，獲得 1 次頂牌權利（可在購買後、回合結束前使用）', '[Turn 1] P1 played 行動預告', '[Turn 1] P1 打出 行動預告，獲得 1 次頂牌權利（可在購買後、回合結束前使用）', '[Turn 1] P1 played 行動預告', '[Turn 1] P1 may resolve remaining 行動預告/行動募資 topdeck rights before drawing new hand']}`
- first_resolve: `{'success': True, 'topdecked_card': '第一張買的牌', 'pending_choice': True}`
- second_prompted: `{'turn_phase': <TurnPhase.END: 'end'>, 'current_player_index': 0, 'hand': [], 'draw_pile': ['Bottom1', 'Bottom2', 'Bottom3', 'Bottom4', 'Bottom5', 'Bottom6', 'Bottom7', '第一張買的牌'], 'discard_pile': ['第二張買的牌', '第三張買的牌'], 'resources': {'money': 0, 'propaganda': 2}, 'pending_topdeck_uses': 0, 'pending_choice': {'type': 'card_choice', 'choice_key': 'topdeck_purchased_choice', 'player_id': 'p1', 'prompt': '行動預告／行動募資：選擇 1 張本回合購得的牌置於牌庫頂。', 'cards': ['第二張買的牌', '第三張買的牌']}, 'action_log_tail': ['[Turn 1] P1 打出 行動預告，獲得 1 次頂牌權利（可在購買後、回合結束前使用）', '[Turn 1] P1 played 行動預告', '[Turn 1] P1 打出 行動預告，獲得 1 次頂牌權利（可在購買後、回合結束前使用）', '[Turn 1] P1 played 行動預告', '[Turn 1] P1 may resolve remaining 行動預告/行動募資 topdeck rights before drawing new hand', '[Turn 1] P1 placed bought card 第一張買的牌 on deck top via 行動預告／行動募資', '[Turn 1] P1 may resolve remaining 行動預告/行動募資 topdeck rights before drawing new hand']}`
- after: `{'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player_index': 1, 'hand': ['第二張買的牌', '第一張買的牌', 'Bottom7', 'Bottom6', 'Bottom5'], 'draw_pile': ['Bottom1', 'Bottom2', 'Bottom3', 'Bottom4'], 'discard_pile': ['第三張買的牌'], 'resources': {'money': 0, 'propaganda': 0}, 'pending_topdeck_uses': 0, 'pending_choice': None, 'action_log_tail': ['[Turn 1] P1 played 行動預告', '[Turn 1] P1 打出 行動預告，獲得 1 次頂牌權利（可在購買後、回合結束前使用）', '[Turn 1] P1 played 行動預告', '[Turn 1] P1 may resolve remaining 行動預告/行動募資 topdeck rights before drawing new hand', '[Turn 1] P1 placed bought card 第一張買的牌 on deck top via 行動預告／行動募資', '[Turn 1] P1 may resolve remaining 行動預告/行動募資 topdeck rights before drawing new hand', '[Turn 1] P1 placed bought card 第二張買的牌 on deck top via 行動預告／行動募資', '[Turn 1] End of turn for P1']}`

## end_turn_drops_unused_right_with_no_candidates — passed

- failures: `[]`
- before: `{'turn_phase': <TurnPhase.END: 'end'>, 'current_player_index': 0, 'hand': [], 'draw_pile': ['Bottom1', 'Bottom2', 'Bottom3', 'Bottom4', 'Bottom5', 'Bottom6', 'Bottom7'], 'discard_pile': ['行動募資'], 'resources': {'money': 1, 'propaganda': 0}, 'pending_topdeck_uses': 1, 'pending_choice': None, 'action_log_tail': ['[Turn 1] P1 打出 行動募資，獲得 1 次頂牌權利（可在購買後、回合結束前使用）', '[Turn 1] P1 played 行動募資']}`
- after: `{'turn_phase': <TurnPhase.ACTION: 'action'>, 'current_player_index': 1, 'hand': ['Bottom7', 'Bottom6', 'Bottom5', 'Bottom4', 'Bottom3'], 'draw_pile': ['Bottom1', 'Bottom2'], 'discard_pile': ['行動募資'], 'resources': {'money': 0, 'propaganda': 0}, 'pending_topdeck_uses': 0, 'pending_choice': None, 'action_log_tail': ['[Turn 1] P1 打出 行動募資，獲得 1 次頂牌權利（可在購買後、回合結束前使用）', '[Turn 1] P1 played 行動募資', '[Turn 1] P1 有 1 次頂牌權利本回合沒有可頂的牌，作廢', '[Turn 1] End of turn for P1']}`
