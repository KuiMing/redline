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
          "id": "quiet_times",
          "name": "歲月靜好",
          "type": "idle",
          "trigger": {},
          "success": {},
          "failure": {},
          "effect": {},
          "progress": {
            "count": 0,
            "required": 0,
            "succeeded": true,
            "settled": true,
            "status": "idle"
          },
          "status": "idle",
          "result_text": "本次事件無效果",
          "trigger_text": "無",
          "success_text": "無",
          "failure_text": "無",
          "effect_text": "無"
        },
        "event_panel": {
          "visible": true,
          "text": "目前事件\n歲月靜好\n類型：歲月靜好｜狀態：無效果\n事件結果：本次事件無效果"
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
    "docs/records/phase-flow/action-first-phase-20260703_070802/01_initial_action_phase_cards_enabled_buy_disabled.png",
    "docs/records/phase-flow/action-first-phase-20260703_070802/02_purchase_phase_hand_disabled_buy_enabled.png"
  ]
}
```
