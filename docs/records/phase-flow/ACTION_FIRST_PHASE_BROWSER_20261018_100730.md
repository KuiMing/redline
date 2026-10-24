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
          "id": "trade_war",
          "name": "貿易戰加劇",
          "type": "mission",
          "trigger": {
            "type": "buy_card",
            "count": 1,
            "min_cost": 4,
            "card_names": [
              "英美奧援"
            ],
            "each_non_red_player": true
          },
          "success": {
            "type": "topdeck_from_discard",
            "count": 1
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
              "2d4112ab-9e6f-45af-8701-65945771c4a7": {
                "player_id": "2d4112ab-9e6f-45af-8701-65945771c4a7",
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
          "trigger_text": "每位非紅軍玩家各自購買符合條件的卡牌（總費用 4 點以上 / 英美奧援）至少 1 次",
          "success_text": "非紅軍：從棄牌堆選 1 張置於牌庫頂",
          "failure_text": "無",
          "effect_text": "無",
          "player_results": [
            {
              "player_id": "2d4112ab-9e6f-45af-8701-65945771c4a7",
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
    "docs/records/phase-flow/action-first-phase-20261018_100730/01_initial_action_phase_cards_and_buy_enabled.png",
    "docs/records/phase-flow/action-first-phase-20261018_100730/02_play_buy_play_all_inside_one_action_phase.png",
    "docs/records/phase-flow/action-first-phase-20261018_100730/03_after_ending_action_phase_seat_passed.png"
  ]
}
```
