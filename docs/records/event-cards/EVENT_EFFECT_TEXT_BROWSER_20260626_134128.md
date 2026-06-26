# Event Effect Text Browser Validation

Generated: 20260626_134128

Summary: 2/2 passed

## PASS — auto_event_shows_red_army_effect_text

```json
{
  "text": "一帶一路 南洋\n類型：自動｜狀態：等待指定玩家回合發動\n事件結果：等待 紅軍 回合發動紅軍事件效果\n自動效果：紅軍：在南洋免費建立 1 個組織",
  "event": {
    "id": "belt_road_southeast",
    "name": "一帶一路 南洋",
    "type": "auto",
    "trigger": {},
    "success": {},
    "failure": {},
    "effect": {
      "type": "build_organization_in_region",
      "count": 1,
      "player_faction": "red_army",
      "region": "southeast_asia",
      "free": true,
      "ignore_distance": true
    },
    "progress": {
      "count": 0,
      "required": 0,
      "succeeded": false,
      "settled": false,
      "status": "auto_pending",
      "auto_target_player_id": "d400809b-0b9d-4c59-96c5-a2bb9f6492ca",
      "auto_target_player_name": "紅軍",
      "auto_target_faction": "red_army"
    },
    "status": "auto_pending",
    "result_text": "等待 紅軍 回合發動紅軍事件效果",
    "trigger_text": "無",
    "success_text": "無",
    "failure_text": "無",
    "effect_text": "紅軍：在南洋免費建立 1 個組織"
  },
  "screenshot": "docs/records/event-cards/event-effect-text-browser-20260626_134128/01_auto_event_red_army_effect_text.png"
}
```

## PASS — mission_failure_labels_red_army_effect_text

```json
{
  "text": "全國人大召開\n類型：任務｜狀態：失敗已結算\n事件結果：非紅軍任務失敗，紅軍效果生效\n任務條件：使用或觸發陣營特殊能力至少 1 次\n進度：0/1\n成功獎勵：非紅軍：抽 1 張牌\n失敗／紅軍效果：紅軍：瓦解 1 個組織（牆內）",
  "event": {
    "id": "national_people_congress",
    "name": "全國人大召開",
    "type": "mission",
    "trigger": {
      "type": "use_faction_ability",
      "count": 1
    },
    "success": {
      "type": "draw",
      "count": 1
    },
    "failure": {
      "type": "red_dissolve",
      "count": 1,
      "scope": "牆內"
    },
    "effect": {},
    "progress": {
      "count": 0,
      "required": 1,
      "succeeded": false,
      "settled": true,
      "status": "failure"
    },
    "status": "failure",
    "result_text": "非紅軍任務失敗，紅軍效果生效",
    "trigger_text": "使用或觸發陣營特殊能力至少 1 次",
    "success_text": "非紅軍：抽 1 張牌",
    "failure_text": "紅軍：瓦解 1 個組織（牆內）",
    "effect_text": "無"
  },
  "screenshot": "docs/records/event-cards/event-effect-text-browser-20260626_134128/02_mission_failure_red_army_effect_text.png"
}
```
