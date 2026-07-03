# Action-first phase browser validation

```json
{
  "summary": {
    "total": 6,
    "passed": 6,
    "failed": 0
  },
  "checks": [
    {
      "name": "starts_in_action_phase",
      "passed": true
    },
    {
      "name": "current_event_visible_at_action_start",
      "passed": true,
      "details": {
        "current_event": {
          "id": "belt_road_middle_east",
          "name": "一帶一路 天方",
          "type": "auto",
          "trigger": {},
          "success": {},
          "failure": {},
          "effect": {
            "type": "build_organization_in_region",
            "count": 1,
            "player_faction": "red_army",
            "region": "middle_east",
            "free": true,
            "ignore_distance": true
          },
          "progress": {
            "count": 0,
            "required": 0,
            "succeeded": false,
            "settled": false,
            "status": "auto_pending",
            "auto_target_player_id": "fd5fc47c-41c0-4ba7-a937-824bd96c86f3",
            "auto_target_player_name": "host",
            "auto_target_faction": "red_army"
          },
          "status": "auto_pending",
          "result_text": "等待 host 回合發動紅軍事件效果",
          "trigger_text": "無",
          "success_text": "無",
          "failure_text": "無",
          "effect_text": "紅軍：在天方免費建立 1 個組織"
        },
        "event_panel": {
          "visible": true,
          "text": "目前事件\n一帶一路 天方\n類型：自動｜狀態：等待指定玩家回合發動\n事件結果：等待 host 回合發動紅軍事件效果\n自動效果：紅軍：在天方免費建立 1 個組織"
        }
      }
    },
    {
      "name": "hand_actions_enabled_initially",
      "passed": true
    },
    {
      "name": "purchase_disabled_before_purchase_phase",
      "passed": true
    },
    {
      "name": "advance_enters_purchase_phase",
      "passed": true
    },
    {
      "name": "purchase_phase_disables_hand_enables_buy",
      "passed": true
    }
  ],
  "screenshots": [
    "docs/records/phase-flow/action-first-phase-20260703_094551/01_initial_action_phase_cards_enabled_buy_disabled.png",
    "docs/records/phase-flow/action-first-phase-20260703_094551/02_purchase_phase_hand_disabled_buy_enabled.png"
  ]
}
```
