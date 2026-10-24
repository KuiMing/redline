# Action-first phase browser validation

```json
{
  "summary": {
    "total": 6,
    "passed": 5,
    "failed": 1
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
      "name": "other_players_auto_event_stays_hidden_at_action_start",
      "passed": false,
      "details": {
        "current_event": {
          "id": "tibet_border_conflict",
          "name": "藏印邊境軍事對峙",
          "type": "mission",
          "trigger": {
            "type": "build_organization",
            "count": 1,
            "scope": "牆內",
            "each_non_red_player": true
          },
          "success": {
            "type": "move",
            "count": 2
          },
          "failure": {
            "type": "none"
          },
          "effect": {},
          "progress": {
            "count": 0,
            "required": 1,
            "succeeded": false,
            "settled": false,
            "status": "active",
            "completed_player_ids": [],
            "player_progress": {
              "f72c65fb-a35a-4846-acb5-6f4ed8b7d942": {
                "player_id": "f72c65fb-a35a-4846-acb5-6f4ed8b7d942",
                "player_name": "hk",
                "count": 0,
                "required": 1,
                "met": false,
                "result": null
              }
            }
          },
          "status": "active",
          "result_text": "非紅軍任務進行中：每位玩家個別判定，整輪結束時結算",
          "trigger_text": "每位非紅軍玩家各自建立組織（牆內）至少 1 次",
          "success_text": "非紅軍：獲得 2 次組織遷移",
          "failure_text": "無",
          "effect_text": "無",
          "player_results": [
            {
              "player_id": "f72c65fb-a35a-4846-acb5-6f4ed8b7d942",
              "player_name": "hk",
              "count": 0,
              "required": 1,
              "met": false,
              "result": null
            }
          ]
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
    "docs/records/phase-flow/action-first-phase-20261018_100650/01_initial_action_phase_cards_and_buy_enabled.png",
    "docs/records/phase-flow/action-first-phase-20261018_100650/02_play_buy_play_all_inside_one_action_phase.png",
    "docs/records/phase-flow/action-first-phase-20261018_100650/03_after_ending_action_phase_seat_passed.png"
  ]
}
```
