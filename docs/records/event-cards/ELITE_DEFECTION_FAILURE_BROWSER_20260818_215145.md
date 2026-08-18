# Elite defection failure browser validation

```json
{
  "summary": {
    "total": 2,
    "passed": 2,
    "failed": 0
  },
  "checks": [
    {
      "name": "elite_defection_event_visible_at_action_start",
      "passed": true,
      "details": {
        "turn_phase": "action",
        "event": {
          "id": "elite_defection",
          "name": "紅軍權貴出逃",
          "type": "mission",
          "trigger": {
            "type": "move_organization",
            "count": 3
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
            "required": 3,
            "succeeded": false,
            "settled": false,
            "status": "active"
          },
          "status": "active",
          "result_text": "非紅軍任務進行中",
          "trigger_text": "進行組織遷移至少 3 次",
          "success_text": "非紅軍：從手牌或棄牌堆移除 1 張牌",
          "failure_text": "紅軍：選 1 張手牌棄掉",
          "effect_text": "無"
        },
        "panel_text": "任務進度 0/3\n點擊放大查看",
        "advance_text": "結束行動階段"
      }
    },
    {
      "name": "failure_discard_choice_triggers_before_red_turn",
      "passed": true,
      "details": {
        "current_player": "red",
        "turn_phase": "action",
        "current_event": {
          "id": "elite_defection",
          "name": "紅軍權貴出逃",
          "type": "mission",
          "trigger": {
            "type": "move_organization",
            "count": 3
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
            "required": 3,
            "succeeded": false,
            "settled": true,
            "status": "failure",
            "settlement_target_player_id": "2d24a1b4-7154-4fcd-9380-2439726f4fe7"
          },
          "status": "failure",
          "result_text": "非紅軍任務失敗，紅軍效果生效",
          "trigger_text": "進行組織遷移至少 3 次",
          "success_text": "非紅軍：從手牌或棄牌堆移除 1 張牌",
          "failure_text": "紅軍：選 1 張手牌棄掉",
          "effect_text": "無"
        },
        "pending_choice": {
          "type": "multi_card_choice",
          "choice_key": "event_discard_self",
          "interaction_kind": null,
          "remaining_builds": null,
          "queueable_card_names": [],
          "cancellable": false,
          "player_id": "2d24a1b4-7154-4fcd-9380-2439726f4fe7",
          "player_name": null,
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
            "合作談判",
            "追隨者",
            "樂捐者",
            "追隨者",
            "追隨者"
          ],
          "options": [],
          "towns": [],
          "targets": [],
          "step": null
        }
      }
    }
  ],
  "screenshots": [
    "docs/records/event-cards/elite-defection-failure-20260818_215145/01_initial_elite_defection_event_visible.png",
    "docs/records/event-cards/elite-defection-failure-20260818_215145/02_failure_discard_choice_before_red_turn.png"
  ]
}
```
