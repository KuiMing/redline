# 奧援卡區域最多組織門檻 UI Validation

- 結果：**9/9 passed**
- 正式端點：`http://127.0.0.1:8000`
- Fixture：玩家巴黎 1；對手日內瓦＋慕尼黑 2；英美奧援 variant 0（II：歐洲／天方）。
- 預期：玩家在歐洲有組織但不是最多，故只結算 I 級並獲得 1 資金。

## Checks
- PASS `fixture_actor_has_one_europe_organization`
- PASS `fixture_enemy_has_two_europe_organizations`
- PASS `authoritative_setup_downgrades_presence_to_tier_one`
- PASS `formal_card_face_uses_variant_zero_regions`
- PASS `formal_action_resolves_tier_one_money_gain`
- PASS `support_card_moves_from_hand_to_discard`
- PASS `formal_action_log_records_tier_one`
- PASS `formal_action_log_does_not_claim_tier_two`
- PASS `browser_console_has_no_errors`

## Screenshots
- `docs/records/support-region-leadership/support-region-leadership-before.png`
- `docs/records/support-region-leadership/support-region-leadership-tier1-after.png`
