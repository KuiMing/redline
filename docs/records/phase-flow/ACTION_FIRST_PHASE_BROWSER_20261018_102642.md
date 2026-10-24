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
          "id": "elite_defection",
          "name": "紅軍權貴出逃",
          "type": "mission",
          "trigger": {
            "type": "move_organization",
            "count": 3,
            "each_non_red_player": true
          },
          "success": {
            "type": "trash_from_hand_or_discard",
            "count": 1
          },
          "failure": {
            "type": "discard_self",
            "count": 1
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
              "32e7bb53-bbca-4380-a594-c2626e492f75": {
                "player_id": "32e7bb53-bbca-4380-a594-c2626e492f75",
                "player_name": "hk",
                "count": 0,
                "required": 3,
                "met": false,
                "result": null
              }
            }
          },
          "status": "active",
          "result_text": "非紅軍任務進行中：每位玩家個別判定，整輪結束時結算",
          "trigger_text": "每位非紅軍玩家各自進行組織遷移至少 3 次",
          "success_text": "非紅軍：從手牌或棄牌堆移除 1 張牌",
          "failure_text": "紅軍：選 1 張手牌棄掉",
          "effect_text": "無",
          "player_results": [
            {
              "player_id": "32e7bb53-bbca-4380-a594-c2626e492f75",
              "player_name": "hk",
              "count": 0,
              "required": 3,
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
    "docs/records/phase-flow/action-first-phase-20261018_102642/01_initial_action_phase_cards_and_buy_enabled.png",
    "docs/records/phase-flow/action-first-phase-20261018_102642/02_play_buy_play_all_inside_one_action_phase.png",
    "docs/records/phase-flow/action-first-phase-20261018_102642/03_after_ending_action_phase_seat_passed.png"
  ]
}
```
