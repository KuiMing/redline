"""Pure era display/notification rules (catalog reads only, no Game
mutation).

Era *activation* (`_detect_era_triggers`, `_continue_era_activation_queue`,
`_apply_era_activation_effects`, and everything that creates/resolves a
pending_choice for an interactive era) stays in `game.py` — those mutate
turn_log/pending_choice/player state, unlike everything here.

`_evaluate_era_trigger` / `_player_region_org_count` /
`_player_requirement_org_count` also stay in `game.py`: they depend on
`Game._player_organization_scope_counts` / `Game._organization_towns_for_player`,
which weren't verified pure in this pass — left for a future slice rather
than guessed at.
"""

from server.game_catalog import EVENT_CARD_COUNTS_PATH, load_json


def era_card_entry(era_name):
    if not EVENT_CARD_COUNTS_PATH.exists():
        return None
    try:
        rows = load_json(EVENT_CARD_COUNTS_PATH)
    except Exception:
        return None
    for row in rows:
        if isinstance(row, list) and row and row[0] == era_name:
            return row
    return None


def era_notification_payload(era):
    era_name = era.get("name", "未知時代")
    row = era_card_entry(era_name)
    summary_text = None
    trigger_text = None
    success_text = None
    fail_text = None
    if row and len(row) >= 5:
        summary_text = row[1] or None
        trigger_text = row[2] or None
        success_text = row[3] or None
        fail_text = row[4] or None
    trigger = era.get("trigger") or {}
    if not trigger_text and trigger.get("type") == "count_only":
        trigger_text = f"在指定區域擁有至少 {trigger.get('count', 0)} 個有效組織。"
    duration = era.get("duration", {})
    if duration.get("type") == "turns":
        duration_text = f"持續 {duration.get('value', 0)} 回合"
    elif duration.get("type") == "permanent":
        duration_text = "持續至遊戲結束"
    else:
        duration_text = "持續時間未明"
    return {
        "id": era.get("id"),
        "name": era_name,
        "summary_text": summary_text or "（時代關卡簡述暫缺）",
        "trigger_text": trigger_text or "（條件資料暫缺）",
        "success_text": success_text or "（紅軍壓制效果暫缺）",
        "fail_text": fail_text or "（革命反撲效果暫缺）",
        "duration_text": duration_text,
        "remaining": None,
        "minimized": False,
    }


def player_matches_era_trigger(faction_by_id, player, trigger):
    faction_id = trigger.get("faction_id")
    if faction_id and player.faction_id != faction_id:
        return False
    camp = trigger.get("camp")
    if camp:
        faction = faction_by_id.get(player.faction_id, {})
        if faction.get("camp") != camp and player.faction_id != camp:
            return False
    return True


def era_stage_for_player(structured_eras, faction_by_id, activated_eras, player, active_era_details=None):
    if not player or player.faction_id == "red_army":
        return None
    active_era_details = active_era_details or []
    for era in structured_eras:
        trigger = era.get("trigger") or {}
        if not player_matches_era_trigger(faction_by_id, player, trigger):
            continue
        payload = era_notification_payload(era)
        active = next(
            (item for item in active_era_details if item.get("id") == era.get("id")),
            None,
        )
        payload["active"] = active is not None
        payload["achieved"] = era.get("id") in set(activated_eras)
        if active:
            payload["remaining"] = active.get("remaining")
            payload["duration"] = active.get("duration")
        return payload
    return None
