# Static Purchase Initial Supply Validation

Generated: 2026-06-26

Summary: 4/4 passed

## PASS — static_supply_constants_match_raw_card_counts

```json
{
  "rule": "常設購買區總張數以 data/raw/action_cards.csv「卡牌張數」為準。",
  "raw_counts": {
    "宣傳家": 15,
    "思想家": 15,
    "資助者": 15,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20
  },
  "runtime_constants": {
    "宣傳家": 15,
    "思想家": 15,
    "資助者": 15,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20
  }
}
```

## PASS — formal_start_without_setup_static_cards_uses_full_initial_supply

```json
{
  "rule": "沒有起始額外常設牌的正式開局，常設供應應等於原始總張數。",
  "purchase_area_static_slots": [
    "宣傳家",
    "思想家",
    "資助者",
    "資本家",
    "分神",
    "內鬥"
  ],
  "static_purchase_supply": {
    "宣傳家": 15,
    "思想家": 15,
    "資助者": 15,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20
  },
  "expected": {
    "宣傳家": 15,
    "思想家": 15,
    "資助者": 15,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20
  }
}
```

## PASS — formal_start_setup_propagandists_decrement_static_supply_once_after_lobby_override

```json
{
  "rule": "正式 lobby 開局套用陣營/根據地後，起始額外宣傳家要從常設供應扣除，且不可受 Game() 隨機初始陣營二次影響。",
  "static_purchase_supply": {
    "宣傳家": 10,
    "思想家": 15,
    "資助者": 15,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20
  },
  "expected": {
    "宣傳家": 10,
    "思想家": 15,
    "資助者": 15,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20
  },
  "player_discards": {
    "red_army": [],
    "hong_kong": [
      "宣傳家"
    ],
    "tibet_dharamsala": [
      "宣傳家",
      "宣傳家"
    ],
    "uyghur_munich": [
      "宣傳家",
      "宣傳家"
    ]
  }
}
```

## PASS — formal_start_setup_patron_decrements_static_supply

```json
{
  "rule": "各界資助起始額外資助者也消耗常設供應。",
  "static_purchase_supply": {
    "宣傳家": 15,
    "思想家": 15,
    "資助者": 14,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20
  },
  "expected": {
    "宣傳家": 15,
    "思想家": 15,
    "資助者": 14,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20
  },
  "player_discards": {
    "red_army": [],
    "minyun": [
      "資助者"
    ]
  }
}
```
