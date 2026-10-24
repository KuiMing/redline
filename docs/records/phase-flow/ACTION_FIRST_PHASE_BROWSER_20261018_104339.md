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
      "passed": true,
      "details": {
        "meta": "目前：行動｜下一步：結束行動",
        "advance_text": "結束行動",
        "turn_phase": "action"
      }
    },
    {
      "name": "non_reveal_event_stays_hidden_at_action_start",
      "passed": true,
      "details": {
        "current_event": {
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
            "auto_target_player_id": "d8584154-bad9-46d8-83d0-a8e4d1767af2",
            "auto_target_player_name": "host",
            "auto_target_faction": "red_army"
          },
          "status": "auto_pending",
          "result_text": "等待 host 回合發動紅軍事件效果",
          "trigger_text": "無",
          "success_text": "無",
          "failure_text": "無",
          "effect_text": "紅軍：在南洋免費建立 1 個組織"
        },
        "event_panel": {
          "visible": false,
          "text": ""
        }
      }
    },
    {
      "name": "hand_actions_enabled_initially",
      "passed": true
    },
    {
      "name": "purchase_enabled_in_action_phase_without_advancing",
      "passed": true
    },
    {
      "name": "play_then_buy_then_play_again_inside_one_action_phase",
      "passed": true,
      "details": {
        "turn_phase_after_play": "action",
        "turn_phase_after_buy": "action",
        "turn_phase_after_second_play": "action",
        "hand_enabled_after_buy": true,
        "buy_still_enabled": true,
        "notice_text": ""
      }
    },
    {
      "name": "single_advance_ends_action_phase_and_passes_seat",
      "passed": true,
      "details": {
        "before_player": "hk",
        "after": {
          "current_player": "host",
          "turn_phase": "action"
        }
      }
    }
  ],
  "screenshots": [
    "docs/records/phase-flow/action-first-phase-20261018_104339/01_initial_action_phase_cards_and_buy_enabled.png",
    "docs/records/phase-flow/action-first-phase-20261018_104339/02_play_buy_play_all_inside_one_action_phase.png",
    "docs/records/phase-flow/action-first-phase-20261018_104339/03_after_ending_action_phase_seat_passed.png"
  ]
}
```
