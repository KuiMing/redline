# Era Canonical Scope Audit

Generated: 2026-05-26
Status: passed

## Summary

- raw_era_rows: 8
- structured_era_rows: 8
- raw_era_rows_represented_as_era_stage: 8
- raw_bracketed_era_rows_in_event_deck: 0
- legacy_event_like_adaptations_still_present: {"[反賊]公知世代的終結": true, "[臺灣]綏靖派反對介入對岸": true}
- structured_effect_rows: 8
- failures: []

## Canonical decision

- Scope: The 8 raw era-stage rows are canonical era-stage mechanics, not event-deck cards.
- Reason: Raw source labels these rows under 時代關卡名稱 and current UI/runtime already has EraEngine plus era achievement modal/pinned HUD.
- Next runtime step: Apply the declared red_suppression and revolution_counterattack effects through EraEngine with deterministic validators and focused UI proof.

## Card-by-card

### [香港]香港人被自殺

- canonical_decision: era_stage_mechanic_not_event_deck_card
- runtime_status: structured_effects_declared
- trigger: [香港抗爭遍地開花]香港在牆內擁有至少10個有效組織
- 紅軍壓制: [新型態的血腥鎮壓]紅軍每次對香港使用間諜類卡牌時，可再隨機棄掉香港1張手牌。持續2回合。
- 革命反撲: [沉冤待雪香港報仇]香港購買每張武裝類卡牌之費用額外減少2點資金。持續2回合。
- structured_id: hong_kong
- red_suppression_effect: `bonus_discard_on_red_card`
- revolution_counterattack_effect: `reduce_purchase_cost`

### [蒙古]莫日根事件爆發

- canonical_decision: era_stage_mechanic_not_event_deck_card
- runtime_status: structured_effects_declared
- trigger: [牧民維權團體成形]蒙古在牆內擁有至少4個有效組織
- 紅軍壓制: [知識分子互相猜疑]將3張內鬥放進蒙古棄牌堆。
- 革命反撲: [南蒙古人世代覺醒]蒙古當回合手牌中的每張宣傳類卡牌 用於購買時可額外提供1點宣傳。
- structured_id: mongolia
- red_suppression_effect: `add_static_cards_to_discard`
- revolution_counterattack_effect: `hand_card_resource_bonus`

### [藏國]藏國騷亂

- canonical_decision: era_stage_mechanic_not_event_deck_card
- runtime_status: structured_effects_declared
- trigger: [藏人完成示威準備]藏國在牆內擁有至少7個有效組織
- 紅軍壓制: [青藏鐵路運兵鎮壓]紅軍當回合可棄掉任意張數手牌，無視距離在藏國有效組織１格內建立與張數同數量的組織。
- 革命反撲: [心向法王達賴喇嘛]藏國當回合手牌中的每張宣傳類卡牌 用於購買時可額外提供1點宣傳。
- structured_id: tibet
- red_suppression_effect: `red_discard_to_build_near_target`
- revolution_counterattack_effect: `hand_card_resource_bonus`

### [哈薩克]伊塔事件

- canonical_decision: era_stage_mechanic_not_event_deck_card
- runtime_status: structured_effects_declared
- trigger: [三玉茲與三區革命]哈薩克在北國擁有至少7個有效組織，在牆內擁有至少3個有效組織
- 紅軍壓制: [紅軍提防哈薩克人]哈薩克此後無法再無視距離建立牆內組織。
- 革命反撲: [出逃同胞加入隊伍]當回合哈薩克立即額外抽2張牌。
- structured_id: kazakh
- red_suppression_effect: `restrict_ignore_distance_build`
- revolution_counterattack_effect: `draw`

### [維吾爾]莎車大屠殺

- canonical_decision: era_stage_mechanic_not_event_deck_card
- runtime_status: structured_effects_declared
- trigger: [突厥戰士踏遍七城]維吾爾在牆內擁有至少7個有效組織
- 紅軍壓制: [武力清剿叛軍基地]紅軍每次對維吾爾使用武裝類卡牌時，可再瓦解己方組織1格內的1個維吾爾組織。持續2回合。
- 革命反撲: [壯士去兮弔民伐罪]維吾爾每打出1張武裝類卡牌，獲得2點宣傳。持續2回合。
- structured_id: uyghur
- red_suppression_effect: `bonus_dissolve_on_red_card_near_self`
- revolution_counterattack_effect: `gain_resource_on_play_card`

### [滿洲]滿洲地方派系凝聚

- canonical_decision: era_stage_mechanic_not_event_deck_card
- runtime_status: structured_effects_declared
- trigger: [山海關外故國甦生]滿洲在牆內擁有至少10個有效組織
- 紅軍壓制: [試圖清洗地方勢力]將5張分神放進滿洲棄牌堆。
- 革命反撲: [行政資源固守地盤]滿洲當回合可檢視己方牌庫頂7張牌，將其中2張牌移到牌庫最頂，其餘順序不變。
- structured_id: manchuria
- red_suppression_effect: `add_static_cards_to_discard`
- revolution_counterattack_effect: `inspect_deck_top_and_reorder`

### [反賊]公知世代的終結

- canonical_decision: era_stage_mechanic_not_event_deck_card
- runtime_status: structured_effects_declared
- trigger: [寒冬將至新芽始生]反賊在牆內擁有至少4個有效組織
- 紅軍壓制: [互聯網管控全面化]反賊此後無法再無視距離建立牆內組織。
- 革命反撲: [反賊結社潛入地下]反賊在回合中建立至少3個組織，則當回合可再抽1張牌。持續至遊戲結束。
- structured_id: rebels
- red_suppression_effect: `restrict_ignore_distance_build`
- revolution_counterattack_effect: `build_count_draw_bonus`

### [臺灣]綏靖派反對介入對岸

- canonical_decision: era_stage_mechanic_not_event_deck_card
- runtime_status: structured_effects_declared
- trigger: [臺灣重建敵後工作]臺灣在牆內擁有至少7個有效組織
- 紅軍壓制: [鼓吹停止挑釁紅軍]將3張內鬥放進臺灣棄牌堆
- 革命反撲: [打擊國內綏靖主義]每當臺灣在臺灣城鎮建立至少1個組織時，獲得1點宣傳。持續2回合。
- structured_id: taiwan
- red_suppression_effect: `add_static_cards_to_discard`
- revolution_counterattack_effect: `gain_resource_on_build_in_region`
