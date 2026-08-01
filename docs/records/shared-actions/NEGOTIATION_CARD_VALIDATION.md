# 合作談判規則驗證

- 結果：**4/4 passed**
- 規則：可指定任意其他玩家，包含敵對玩家；行動者與指定者各抽1張，行動者獲得2宣傳。
- Fail closed：缺少、自身或不存在的目標在卡牌／牌庫／資源變動前拒絕。

## Checks
- PASS `enemy_is_a_legal_target_and_only_actor_and_enemy_draw`
- PASS `missing_target_is_rejected_without_mutation`
- PASS `self_target_is_rejected_without_mutation`
- PASS `unknown_target_is_rejected_without_mutation`
