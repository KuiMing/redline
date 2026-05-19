# Market Mode / Removed Supply Smoke Validation

- total: 7
- passed: 7
- failed: 0

| Check | Passed | Actual | Expected |
|---|---|---|---|
| sample_53 draw pile matches 53-card sampled market deck minus 5 exposed market cards | ✅ | `48` | `48` |
| sample_53 state market mode | ✅ | `"sample_53"` | `"sample_53"` |
| all_cards draw pile exceeds sample_53 sampled market deck after 5 exposed cards | ✅ | `68` | `"> 48"` |
| all_cards state market mode | ✅ | `"all_cards"` | `"all_cards"` |
| remove propagandist keeps visible purchase area length | ✅ | `{"before": 11, "after": 11}` | `"equal"` |
| remove propagandist increments static supply | ✅ | `{"before": 1, "after": 2}` | `2` |
| remove propagandist play succeeds | ✅ | `{"success": true, "pending_choice": true, "resolved_pending_choice": {"success": true, "chosen_card": "宣傳家", "zone": "current_card", "zone_label": "剛打出的牌", "removed_card": {"zone": "static_supply", "name": "宣傳家", "count": 2}, "removed_current_card": true, "pending_choice": true}}` | `{"success": true}` |
