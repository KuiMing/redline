# 新疆社會管控距離限制驗證（S2）

可重跑指令：`python3 scripts/validate_xinjiang_distance_restriction.py`

- total: 4 / passed: 4 / failed: 0

## Results

- PASS ability_resolved_and_scoped_to_inner: checks={"munich_is_restricted": true, "kazakh_not_restricted": true, "restricts_inner": true, "not_restrict_outer": true}
- PASS ideologue_ignore_distance_excludes_inner_for_restricted: checks={"restricted_gets_no_inner_towns": true, "unrestricted_gets_distant_inner": true}
- PASS org_experience_a_inner_fallback_range_1: checks={"effect_has_fallback_clause": true, "inner_offers_limited_to_1_step": true, "distant_inner_excluded": true, "unrestricted_still_ignore_distance": true}
- PASS east_asia_support_tier3_downgraded_to_near_for_restricted: checks={"restricted_anywhere_downgraded_to_near": true, "unrestricted_anywhere_larger_than_near": true}
