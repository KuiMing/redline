# Static Purchase UI Browser Validation

Generated: 20260702_050652

Summary: 3/3 passed

## PASS — formal_start_host_ui_static_counts_not_one

```json
{
  "actual": {
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
  "url": "http://127.0.0.1:8768/?game_id=8039e280-0b9f-47f1-ac25-4a275a1ee519&player_id=2ad2f46c-1723-43ba-9e19-9f57970b0252&v=static-ui-browser-20260702_050652",
  "state_static_purchase_supply": {
    "宣傳家": 10,
    "思想家": 15,
    "資助者": 15,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20
  },
  "screenshot": "docs/records/purchase/static-purchase-ui-20260702_050652/01_host_formal_start_static_counts.png"
}
```

## PASS — formal_start_current_player_ui_static_counts_not_one

```json
{
  "actual": {
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
  "url": "http://127.0.0.1:8768/?game_id=8039e280-0b9f-47f1-ac25-4a275a1ee519&player_id=16c78c2c-079a-4e55-a3b8-c99702270f54&v=static-ui-browser-20260702_050652",
  "state_static_purchase_supply": {
    "宣傳家": 10,
    "思想家": 15,
    "資助者": 15,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20
  },
  "screenshot": "docs/records/purchase/static-purchase-ui-20260702_050652/02_hk_formal_start_static_counts.png"
}
```

## PASS — after_buy_ui_static_count_decrements_and_card_stays

```json
{
  "actual": {
    "宣傳家": 9,
    "思想家": 15,
    "資助者": 15,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20
  },
  "expected": {
    "宣傳家": 9,
    "思想家": 15,
    "資助者": 15,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20
  },
  "state_static_purchase_supply": {
    "宣傳家": 9,
    "思想家": 15,
    "資助者": 15,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20
  },
  "hk_resources": {
    "money": 0,
    "propaganda": 0
  },
  "hk_discard_tail": [
    "宣傳家",
    "追隨者",
    "追隨者",
    "追隨者",
    "宣傳家"
  ],
  "action_log_tail": [
    "[Turn 1] hk played 追隨者 as resource",
    "[Turn 1] hk played 追隨者 as resource",
    "[Turn 1] hk played 追隨者 as resource",
    "[Turn 1] hk bought 宣傳家"
  ],
  "screenshot": "docs/records/purchase/static-purchase-ui-20260702_050652/03_after_buy_propagandist_static_count_decrements.png"
}
```
