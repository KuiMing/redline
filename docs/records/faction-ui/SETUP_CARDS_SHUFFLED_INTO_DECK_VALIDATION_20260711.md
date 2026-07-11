# 開局額外卡洗入起始牌庫驗證（S4）

可重跑指令：`python3 scripts/validate_setup_cards_shuffled_into_deck.py`

- total: 6
- passed: 6
- failed: 0

## Results

- PASS hong_kong_攬炒策略_shuffled_into_deck: checks={"one_extra_in_deck_zone": true, "none_in_discard": true, "hand_still_five": true, "deck_total_eleven": true, "supply_decremented_once": true}
- PASS gender_revolution_活動家_shuffled_into_deck: checks={"two_extras_in_deck_zone": true, "none_in_discard": true, "hand_still_five": true, "deck_total_twelve": true}
- PASS minyun_各界資助_shuffled_into_deck: checks={"one_patron_in_deck_zone": true, "none_in_discard": true, "supply_decremented_once": true}
- PASS red_army_starter_deck_untouched: checks={"red_support_still_in_deck_zone": true, "red_deck_total_eleven": true, "red_discard_empty": true}
- PASS setup_cards_reachable_in_opening_hand: checks={"sometimes_in_opening_hand": true, "not_always_in_opening_hand": true}
- PASS supply_empty_guard_no_reshuffle: checks={"no_card_added_when_supply_empty": true, "hand_untouched_without_gain": true}
