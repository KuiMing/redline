# 模仿戰術目標選擇驗證

可重跑指令：`python3 scripts/validate_imitate_tactics.py`

- total: 5 / passed: 5 / failed: 0

## Results

- PASS single_opponent_still_prompts_a_choice: checks={"pending_choice_opened": true, "choice_key_is_imitate": true, "single_opponent_still_listed": true}
- PASS multi_opponent_lists_every_player_with_a_card: checks={"both_opponents_listed": true}
- PASS discard_only_opponent_is_a_valid_target: checks={"discard_only_opponent_included": true, "fully_empty_opponent_excluded": true}
- PASS no_legal_target_does_not_get_stuck: checks={"no_pending_choice": true, "nothing_imitated_to_hand": true}
- PASS resolving_imitates_card_to_hand_and_marks_return: checks={"resolve_ok": true, "imitated_card_reported": true, "card_in_my_hand": true, "marked_to_return_to_owner": true, "removed_from_owner_deck": true, "pending_cleared": true}
