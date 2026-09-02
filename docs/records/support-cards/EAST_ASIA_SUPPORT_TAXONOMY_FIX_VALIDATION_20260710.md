# 東洋奧援 taxonomy fix validation

可重跑指令：`python3 scripts/validate/validate_east_asia_support_taxonomy_fix.py`

- scope: 東洋奧援
- total: 6
- passed: 6
- failed: 0

## Results

- PASS tier3_own_region: tier=3 region_index=0 matched=[] effect=interactive_build_anywhere_inner checks={"play_card_success": true, "tier_detected": true, "effect_type_matches": true}
- PASS tier2_taiwan_southeast_asia_pair: tier=2 region_index=0 matched=["臺灣", "南洋"] effect=interactive_build_near_inner checks={"play_card_success": true, "tier_detected": true, "effect_type_matches": true}
- PASS tier2_northland_anglo_pair: tier=2 region_index=1 matched=["北國", "英美"] effect=interactive_build_near_inner checks={"play_card_success": true, "tier_detected": true, "effect_type_matches": true}
- PASS tier2_taiwan_only_or_semantics: tier=2 region_index=0 matched=["臺灣"] effect=interactive_build_near_inner checks={"play_card_success": true, "tier_detected": true, "effect_type_matches": true}
- PASS tier2_northland_only_or_semantics: tier=2 region_index=1 matched=["北國"] effect=interactive_build_near_inner checks={"play_card_success": true, "tier_detected": true, "effect_type_matches": true}
- PASS tier1_fallback: tier=1 region_index=0 matched=[] effect=gain_resource checks={"play_card_success": true, "tier_detected": true, "effect_type_matches": true, "propaganda_gained_2": true}
