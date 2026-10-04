# Elite defection runtime validation

```json
{
  "summary": {
    "total": 4,
    "passed": 4,
    "failed": 0
  },
  "checks": [
    {
      "name": "event_visible_at_action_start",
      "passed": true,
      "details": {
        "turn_phase": "action",
        "event": "紅軍權貴出逃"
      }
    },
    {
      "name": "viewer_turn_end_refills_but_does_not_settle",
      "passed": true,
      "details": {
        "result": {
          "success": true
        },
        "current_player": "red",
        "viewer_hand": [
          "補牌5",
          "補牌4",
          "補牌3",
          "補牌2",
          "補牌1"
        ],
        "event_progress": {
          "count": 0,
          "required": 1,
          "succeeded": false,
          "settled": true,
          "status": "failure",
          "completed_player_ids": [],
          "player_progress": {
            "viewer-id": {
              "player_id": "viewer-id",
              "player_name": "viewer",
              "count": 0,
              "required": 3,
              "met": false,
              "result": "failure"
            }
          },
          "settlement_started": true,
          "settlement_queue": [],
          "qualified_player_ids": []
        }
      }
    },
    {
      "name": "failure_discard_choice_after_red_turn_end",
      "passed": true,
      "details": {
        "result": {
          "success": true,
          "pending_choice": true
        },
        "current_player": "red",
        "viewer_hand_after_refill": [
          "補牌5",
          "補牌4",
          "補牌3",
          "補牌2",
          "補牌1"
        ],
        "event_progress": {
          "count": 0,
          "required": 1,
          "succeeded": false,
          "settled": true,
          "status": "failure",
          "completed_player_ids": [],
          "player_progress": {
            "viewer-id": {
              "player_id": "viewer-id",
              "player_name": "viewer",
              "count": 0,
              "required": 3,
              "met": false,
              "result": "failure"
            }
          },
          "settlement_started": true,
          "settlement_queue": [],
          "qualified_player_ids": []
        },
        "pending_choice": {
          "choice_id": "1f7c6164f0bb4c3b812bb271a0cecc44",
          "type": "multi_card_choice",
          "choice_key": "event_discard_self",
          "interaction_kind": null,
          "remaining_builds": null,
          "queueable_card_names": [],
          "cancellable": false,
          "player_id": "viewer-id",
          "player_name": null,
          "prompt": "紅軍權貴出逃：請選擇 1 張手牌棄掉。",
          "source_name": "紅軍權貴出逃",
          "count": 1,
          "min_count": null,
          "selected_count": null,
          "total_count": null,
          "remaining_count": null,
          "mode": null,
          "acting_player_id": null,
          "acting_player_name": null,
          "played_card_name": null,
          "target_player_id": null,
          "target_player_name": null,
          "region": null,
          "free": null,
          "ignore_distance": null,
          "cards": [
            "補牌5",
            "補牌4",
            "補牌3",
            "補牌2",
            "補牌1"
          ],
          "options": [],
          "towns": [],
          "targets": [],
          "step": null
        },
        "log": [
          "[Turn 1] Event drawn: 紅軍權貴出逃",
          "[Turn 1] End of turn for viewer",
          "[Turn 1] End of turn for red",
          "[Turn 1] 事件結算（整輪結束）：紅軍權貴出逃｜成功：無｜失敗：viewer",
          "[Turn 1] Event failure: viewer must discard 1 hand card(s)"
        ]
      }
    },
    {
      "name": "penalty_discards_refilled_non_red_viewer_not_red_army",
      "passed": true,
      "details": {
        "viewer_hand": [
          "補牌4",
          "補牌3",
          "補牌2",
          "補牌1"
        ],
        "viewer_discard": [
          "補牌5"
        ],
        "red_hand": [
          "紅軍不應被棄"
        ]
      }
    }
  ]
}
```
