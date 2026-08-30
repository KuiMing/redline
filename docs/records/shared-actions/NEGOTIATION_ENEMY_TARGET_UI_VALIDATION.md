# 合作談判敵對玩家正式UI驗證

- 結果：**11/11 passed**
- 四人正式UI：候選包含 Ally、Enemy、Observer，不包含行動者自己。
- 實際指定 Enemy：Actor與Enemy各抽1張，其他兩人不抽；Actor獲得2宣傳。

## Checks
- PASS `negotiation_action_button_is_available`
- PASS `formal_target_modal_is_for_negotiation`
- PASS `all_three_other_players_are_candidates`
- PASS `actor_is_not_a_candidate`
- PASS `enemy_candidate_is_visible_and_enabled`
- PASS `actor_and_enemy_each_draw_exactly_one`
- PASS `ally_and_observer_do_not_draw`
- PASS `actor_gains_two_propaganda_only`
- PASS `negotiation_commits_to_discard_and_clears_pending`
- PASS `formal_traditional_chinese_log_names_actor_enemy_and_negotiation`
- PASS `browser_console_has_no_errors`

## Screenshots
- `docs/records/shared-actions/negotiation-enemy-target-choice.png`
- `docs/records/shared-actions/negotiation-enemy-target-result.png`
