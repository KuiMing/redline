# 粵/澳門 <-> 香港 共用組織修正驗證

可重跑指令：`python3 scripts/validate_yue_aomen_hongkong_shared_org.py`

- scope: yue, aomen, hong_kong
- total: 5
- passed: 5
- failed: 0

## Results

- PASS yue_sees_hong_kong_org_in_廣州: expect_shared=True shared_org_count=2 origin_owner_faction=hong_kong
- PASS aomen_sees_hong_kong_org_in_深圳: expect_shared=True shared_org_count=2 origin_owner_faction=hong_kong
- PASS hong_kong_sees_yue_org_in_廣州: expect_shared=True shared_org_count=2 origin_owner_faction=yue
- PASS hong_kong_sees_aomen_org_in_深圳: expect_shared=True shared_org_count=2 origin_owner_faction=aomen
- PASS liberals_sees_hong_kong_org_in_廣州: expect_shared=False shared_org_count=0 origin_owner_faction=None
