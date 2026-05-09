# Market Mode / Removed Supply Smoke Validation

- total: 7
- passed: 7
- failed: 0

| Check | Passed | Actual | Expected |
|---|---|---|---|
| sample_53 draw pile is 48 after 5 random market cards exposed | ✅ | `48` | `48` |
| sample_53 state market mode | ✅ | `"sample_53"` | `"sample_53"` |
| all_cards draw pile exceeds sample_53 after 5 random market cards exposed | ✅ | `64` | `"> 48"` |
| all_cards state market mode | ✅ | `"all_cards"` | `"all_cards"` |
| remove propagandist keeps visible purchase area length | ✅ | `{"before": 11, "after": 11}` | `"equal"` |
| remove propagandist increments static supply | ✅ | `{"before": 1, "after": 2}` | `2` |
| remove propagandist play succeeds | ✅ | `{"success": true}` | `{"success": true}` |
