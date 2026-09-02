# 回合結束補牌（保留手牌補到5）＋本土社團額外抽驗證

可重跑指令：`python3 scripts/validate/validate_end_turn_hand_refill.py`

- total: 4 / passed: 4 / failed: 0

## Results

- PASS keep_hand_and_top_up_to_five: checks={"hand_size_five": true, "existing_cards_kept": true, "kept_cards_not_discarded": true, "drew_only_three": true}
- PASS five_or_more_cards_no_draw_no_discard: checks={"six_cards_kept": true, "no_extra_draw": true}
- PASS local_society_extra_draw_reaches_six: checks={"ends_with_six_cards": true, "ability_logged": true}
- PASS no_inner_build_no_extra_draw: checks={"exactly_five": true}
