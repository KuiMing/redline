# LEGAL MOVEMENT PROJECTION VALIDATION

日期：2026-07-28

結果：8/8 PASS

## PASS — current_player_receives_backend_legal_moves_without_mutation

- detail: `{"new_taipei": {"road": {"基隆": 1}, "rail": {"基隆": 1, "桃園": 1, "新竹": 1, "苗栗": 1, "宜蘭": 1}}, "state_unchanged": true}`

## PASS — other_viewer_receives_no_actionable_projection

- detail: `{}`

## PASS — base_anchor_is_not_a_movable_origin

- detail: `{"origins": ["新北"]}`

## PASS — every_projected_move_matches_the_shared_validator_and_cost

- detail: `{"projected_count": 6, "all_consistent": true}`

## PASS — projection_is_exactly_bidirectionally_equivalent_to_shared_validator

- detail: `{"actual_count": 6, "expected_count": 6, "missing": [], "extra": []}`

## PASS — zero_move_points_projects_no_destinations

- detail: `{}`

## PASS — occupied_destination_is_absent_from_projection

- detail: `{"road": {"基隆": 1}, "rail": {"基隆": 1, "桃園": 1, "新竹": 1, "宜蘭": 1}}`

## PASS — faction_inapplicable_destination_is_absent_from_projection

- detail: `{"road": {"基隆": 1}, "rail": {"基隆": 1, "桃園": 1, "新竹": 1, "苗栗": 1, "宜蘭": 1}}`
