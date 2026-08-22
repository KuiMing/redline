# VICTORY RULES VALIDATION

日期：2026-05-09

summary: {'total': 6, 'passed': 6, 'failed': 0}

## red_survival_after_turn_20
- result: PASS
- detail: {"phase": "finished", "winner": "red_army", "turn": 21}

## kazakh_completed_condition_precedes_red_survival
- result: PASS
- detail: {"phase": "finished", "winner": "Ben", "turn": 21, "organization_count": 19, "required_locations": ["阿勒泰", "塔城", "伊寧"], "has_required_locations": true}

## red_taiwan_14_orgs_early_win
- result: PASS
- detail: {"phase": "finished", "winner": "red_army", "red_orgs": {"南投": 1, "嘉義": 1, "基隆": 1, "宜蘭": 1, "屏東": 1, "彰化": 1, "新北": 1, "新竹": 1, "東沙": 1, "桃園": 1, "澎湖": 1, "臺中": 1, "臺北": 1, "臺南": 1}}

## non_red_china_14_orgs_win
- result: PASS
- detail: {"phase": "finished", "winner": "anti", "anti_org_count": 14}

## shared_orgs_count_for_non_red_victory
- result: PASS
- detail: {"shared_count": 14, "phase": "finished", "winner": "Taiwan", "tw_orgs": {"三亞": 1, "上海": 1, "上粉沙打": 1, "丹東": 1, "九龍城": 1, "伊寧": 1, "佳木斯": 1, "元朗": 1}, "hu_orgs": {"克孜勒蘇": 1, "克拉瑪依": 1, "包頭": 1, "北京": 1, "南京": 1, "南寧": 1}}

## no_win_when_below_threshold
- result: PASS
- detail: {"phase": "main", "winner": null, "anti_org_count": 13, "turn": 20}
