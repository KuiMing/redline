# HONG_KONG_LAM_CHAU_ABILITY

日期：2026-05-05

## 使用者補充

香港應額外包含能力：
- `攬炒策略`：在遊戲開始時，免費將一張宣傳家洗入牌庫。

## 本輪修正

已將此能力加入：
- `data/factions/all_faction.json`
- `data/factions/all_faction.integrated.v2.json`

加入形式：
```json
{
  "name": "攬炒策略",
  "type": "setup",
  "effect": "在遊戲開始時，免費將一張宣傳家洗入牌庫。"
}
```

## 效果

現在香港城選定後，能力區會顯示：
- 攬炒策略：在遊戲開始時，免費將一張宣傳家洗入牌庫。
- 安全屋：建立牆內組織時，可建立組織距離額外增加1格。

## 驗證

- 截圖：`hong_kong_city_with_lamchau_ui.png`
