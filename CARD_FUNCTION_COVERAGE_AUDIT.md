# CARD FUNCTION COVERAGE AUDIT

日期：2026-05-03

## 結論

目前**不能**聲稱「所有卡牌功能都已可驗證」，因為卡牌資料中的 effect type 與 `server/effect_engine.py` 的可執行覆蓋率仍有明顯缺口。

## Effect type 覆蓋總覽

### 已在 `EffectEngine` 實作
- draw
- discard_self
- gain_resource
- force_discard
- gain_from_discard
- gain_any_from_discard
- peek_deck
- topdeck_to_hand
- extra_move
- extend_build_range

### 尚未在 `EffectEngine` 實作
- add_internal_conflict
- build
- cancel_card
- conditional_bonus
- conditional_draw
- dissolve
- move
- optional_trash
- refresh_purchase_area
- shared_draw
- trash_from_hand_or_discard

## 卡牌覆蓋統計

- IMPLEMENTED_EFFECTS_ONLY: 16
- PARTIAL: 9
- UNIMPLEMENTED_EFFECTS_ONLY: 14
- NO_EFFECT_DECLARED: 1

## 一、已實作 effect-only 卡牌（可進入驗證段）

- 領導 — draw
- 謀劃 — draw
- 戰略 — draw
- 高效行動 — draw, discard_self
- 模仿戰術 — peek_deck, topdeck_to_hand
- 乘勝追擊 — gain_from_discard
- 網羅人才 — peek_deck, topdeck_to_hand
- 思想建設 — extend_build_range
- 擴大戰果 — gain_any_from_discard
- 交通經驗丙 — extra_move
- 交通經驗乙 — extra_move
- 交通經驗甲 — extra_move
- 行動預告 — gain_resource, topdeck_to_hand
- 地下黨 — peek_deck, gain_any_from_discard
- 武裝者 — force_discard
- 武裝小隊 — force_discard

## 二、部分實作卡牌（驗證會失真）

- 資助者 — gain_resource + optional_trash（缺 optional_trash）
- 資本家 — gain_resource + optional_trash（缺 optional_trash）
- 誘導虛耗 — force_discard + optional_trash（缺 optional_trash）
- 點燃熱情 — draw + conditional_draw（缺 conditional_draw）
- 樹立信心 — draw + conditional_draw（缺 conditional_draw）
- 凝聚共識 — draw + discard_self + conditional_bonus（缺 conditional_bonus）
- 輿論丕變 — gain_resource + refresh_purchase_area（缺 refresh_purchase_area）
- 走漏風聲 — peek_deck + add_internal_conflict（缺 add_internal_conflict）
- 武裝集團 — force_discard + conditional_draw（缺 conditional_draw）

## 三、未實作 effect-only 卡牌（目前不可誠實驗證）

- 宣傳家 — optional_trash, build, move
- 思想家 — optional_trash, build, move
- 分神 — optional_trash
- 合作談判 — shared_draw
- 組織經驗丙 — build
- 組織經驗乙 — build, build
- 組織經驗甲 — build
- 批判 — trash_from_hand_or_discard
- 批鬥 — trash_from_hand_or_discard
- 爆料黑幕 — cancel_card, conditional_draw
- 派遣間諜 — dissolve
- 內應間諜 — dissolve
- 情報網 — add_internal_conflict, cancel_card
- 離間 — add_internal_conflict

## 四、無 effect 宣告卡

- 內鬥 — effect: []

## 五、最關鍵缺口（按影響排序）

### P0
1. build
2. move（卡牌 effect 層，不是地圖手動 move）
3. conditional_draw
4. optional_trash
5. shared_draw

### P1
6. cancel_card
7. dissolve
8. trash_from_hand_or_discard
9. add_internal_conflict
10. refresh_purchase_area
11. conditional_bonus

## 六、建議下一步

1. 先補 `build` / `move` / `conditional_draw` / `optional_trash` / `shared_draw`
2. 補完後再做第一輪「已可驗證卡牌」逐張驗證
3. 第二輪再補控制型 / 間諜型效果
4. 最後做「所有卡牌功能驗證完成」聲明

## 七、重要結論

目前最多只能說：

- **部分卡牌功能已可驗證**
- **所有卡牌功能尚未達到可驗證狀態**

不能對外聲稱「全部卡牌功能都驗過且已可玩」。
