# 民運派／性別革命 非暴力 fix validation

可重跑指令：`python3 scripts/validate_minyun_gender_revolution_nonviolent.py`

- total: 7
- passed: 7
- failed: 0

## Results

- PASS minyun_has_非暴力_ability: checks={"ability_resolved": true}
- PASS minyun_blocked_from_playing_armed_card: checks={"play_blocked": true, "card_still_in_hand": true}
- PASS minyun_blocked_from_buying_armed_card: checks={"buy_blocked": true}
- PASS gender_revolution_has_非暴力_ability: checks={"ability_resolved": true}
- PASS gender_revolution_blocked_from_playing_armed_card: checks={"play_blocked": true, "card_still_in_hand": true}
- PASS gender_revolution_blocked_from_buying_armed_card: checks={"buy_blocked": true}
- PASS unrelated_faction_liberals_not_blocked: checks={"play_succeeded": true, "no_nonviolent_ability": true}
