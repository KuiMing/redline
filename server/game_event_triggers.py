"""Pure event trigger-matching / condition-checking rules (catalog and
player-state reads only, no mutation).

`_track_event_progress` and `_track_event_purchase` mutate
`self.event_progress` / `self.event_notification` after calling these —
those stay in `game.py`, out of scope here.
"""

from server.game_map_rules import towns_for_region_alias
from server.game_market_cost_rules import card_purchase_cost


def event_trigger_matches_scope(map_data, towns_by_ruler, trigger, town=None):
    scope = trigger.get('scope')
    if not scope:
        return True
    if scope == '牆內':
        return town is None or town in set(towns_for_region_alias(map_data, towns_by_ruler, 'china'))
    return True


def event_trigger_actor_allowed(player):
    if player is None:
        return True
    return getattr(player, 'faction_id', None) != 'red_army'


def event_purchase_trigger_matches(structured_cards, support_taxonomy, trigger, card, original_cost=None):
    if (trigger or {}).get('type') != 'buy_card':
        return False
    card_name = getattr(card, 'name', str(card))
    if card_name in set(trigger.get('card_names') or []):
        return True
    min_cost = trigger.get('min_cost')
    if min_cost is not None:
        cost = original_cost or card_purchase_cost(structured_cards, support_taxonomy, card)
        total = int((cost or {}).get('money', 0) or 0) + int((cost or {}).get('propaganda', 0) or 0)
        if total >= int(min_cost or 0):
            return True
    return False


def event_state_condition_met(map_data, towns_by_ruler, trigger, player):
    condition = (trigger or {}).get('condition')
    if condition == 'own_organization_in_scope':
        scope = (trigger or {}).get('scope')
        required = int((trigger or {}).get('count', 1) or 1)
        if scope == '牆內':
            allowed = set(towns_for_region_alias(map_data, towns_by_ruler, 'china'))
        else:
            allowed = set(map_data.get('towns', {}) or {})
        count = sum(
            int(n or 0)
            for town, n in (getattr(player, 'organizations', {}) or {}).items()
            if town in allowed and int(n or 0) > 0
        )
        return count >= required, count
    return False, 0
