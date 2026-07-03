# Elite defection runtime validation

```json
{
  "summary": {
    "total": 3,
    "passed": 3,
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
      "name": "failure_discard_choice_before_red_turn",
      "passed": true,
      "details": {
        "result": {
          "success": true,
          "pending_choice": true
        },
        "current_player": "viewer",
        "event_progress": {
          "count": 0,
          "required": 3,
          "succeeded": false,
          "settled": true,
          "status": "failure"
        },
        "pending_choice": {
          "type": "multi_card_choice",
          "choice_key": "event_discard_self",
          "player_id": "viewer-id",
          "prompt": "紅軍權貴出逃：請選擇 1 張手牌棄掉。",
          "source_name": "紅軍權貴出逃",
          "count": 1,
          "min_count": null,
          "mode": null,
          "acting_player_id": null,
          "acting_player_name": null,
          "played_card_name": null,
          "region": null,
          "free": null,
          "ignore_distance": null,
          "cards": [
            "懲罰棄牌"
          ],
          "options": [],
          "towns": [],
          "targets": [],
          "step": null
        }
      }
    },
    {
      "name": "penalty_discards_non_red_viewer_not_red_army",
      "passed": true,
      "details": {
        "viewer_hand": [],
        "viewer_discard": [
          "懲罰棄牌"
        ],
        "red_hand": [
          "紅軍不應被棄"
        ]
      }
    }
  ]
}
```
