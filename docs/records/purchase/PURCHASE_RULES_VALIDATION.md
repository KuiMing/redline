# Purchase Rules Validation

Generated: 2026-06-26

Summary: 4/4 passed

## PASS — static_purchase_card_can_be_bought_and_decrements_supply

```json
{
  "rule": "常設購買區的卡可被購買；購買後扣費、進玩家棄牌堆、常設庫存 -1，常設 slot 不消失。",
  "result": {
    "success": true
  },
  "resources_after": {
    "money": 0,
    "propaganda": 0
  },
  "supply_before": 15,
  "supply_after": 14,
  "area_before": [
    "宣傳家",
    "思想家",
    "資助者",
    "資本家",
    "分神",
    "內鬥",
    "高效行動",
    "組織經驗乙",
    "樹立信心",
    "離間",
    "武裝小隊"
  ],
  "area_after": [
    "宣傳家",
    "思想家",
    "資助者",
    "資本家",
    "分神",
    "內鬥",
    "高效行動",
    "組織經驗乙",
    "樹立信心",
    "離間",
    "武裝小隊"
  ],
  "discard_before": [],
  "discard_after": [
    "宣傳家"
  ]
}
```

## PASS — static_purchase_card_cannot_be_bought_when_supply_empty

```json
{
  "rule": "常設庫存為 0 時不可購買，且不扣費、不加牌。",
  "result": {
    "error": "Static purchase card is out of supply"
  },
  "resources_before": {
    "money": 0,
    "propaganda": 3
  },
  "resources_after": {
    "money": 0,
    "propaganda": 3
  },
  "discard_before": [],
  "discard_after": []
}
```

## PASS — support_card_purchase_deducts_taxonomy_cost

```json
{
  "rule": "奧援卡購買費用依 taxonomy：1 資金 + 2 宣傳；購買後進玩家棄牌堆並移出購買區。",
  "result": {
    "success": true
  },
  "resources_after": {
    "money": 0,
    "propaganda": 0
  },
  "area_len_before": 7,
  "area_len_after": 6,
  "discard_before": [],
  "discard_after": [
    "英美奧援"
  ]
}
```

## PASS — support_card_purchase_requires_taxonomy_cost

```json
{
  "rule": "資源不足時不可購買奧援卡，且狀態不可改變。",
  "result": {
    "error": "Not enough resources"
  },
  "resources_before": {
    "money": 1,
    "propaganda": 1
  },
  "resources_after": {
    "money": 1,
    "propaganda": 1
  },
  "area_before": [
    "宣傳家",
    "思想家",
    "資助者",
    "資本家",
    "分神",
    "內鬥",
    "英美奧援"
  ],
  "area_after": [
    "宣傳家",
    "思想家",
    "資助者",
    "資本家",
    "分神",
    "內鬥",
    "英美奧援"
  ],
  "discard_before": [],
  "discard_after": []
}
```
