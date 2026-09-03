"""Pure card build/dissolve catalog rules and event-modifier reads (static
action-card catalog and event_modifiers list only, no mutation).

`_card_build_town_choices` / `_card_action_legality` stay in `game.py` as
Game methods (not extracted here) even though their own bodies are pure:
they transitively depend on `can_develop_in_town`/`_has_org_supply`, which
must stay routed through `self._org_supply_limit` rather than the module
composite so that `test_build_entitlement_queue.py`'s monkeypatch of
`Game._org_supply_limit` still takes effect (same reasoning as the
extraction in server/game_build_eligibility_rules.py).
"""


def active_event_modifiers(event_modifiers):
    return [
        modifier for modifier in (event_modifiers or [])
        if int((modifier or {}).get('remaining_turns', 1) or 0) > 0
    ]


def event_modifier_active(event_modifiers, modifier_type):
    return any((m or {}).get('type') == modifier_type for m in active_event_modifiers(event_modifiers))


def card_matches_types(card, card_types):
    if not card_types:
        return True
    return getattr(card, 'card_type', None) in set(card_types or [])


def card_build_effects(action_engine_cards, card):
    card_name = getattr(card, 'name', str(card))
    card_def = (action_engine_cards or {}).get(card_name) or {}
    return [
        effect
        for effect in (card_def.get('effect') or [])
        if isinstance(effect, dict) and effect.get('type') == 'build'
    ]


def card_dissolve_effects(action_engine_cards, card):
    card_name = getattr(card, 'name', str(card))
    card_def = (action_engine_cards or {}).get(card_name) or {}
    found = []

    def collect(value):
        if isinstance(value, dict):
            if value.get('type') == 'dissolve':
                found.append(value)
            for nested in value.values():
                collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)

    collect(card_def.get('effect') or [])
    return found


def card_can_queue_build(action_engine_cards, card):
    return bool(card_build_effects(action_engine_cards, card))
