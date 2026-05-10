import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase


def names(cards):
    return [getattr(c, 'name', str(c)) for c in cards]


def main():
    random.seed(20260510)
    g = Game([('p1', 'Tibet'), ('p2', 'Red')])
    t, r = g.players
    t.faction_id = 'tibet_dehradun'
    t.base = '德拉敦'
    t.organizations = {'德拉敦': 1}
    r.faction_id = 'red_army'
    r.base = '北京'
    r.organizations = {'北京': 1}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0

    has_purchase_deck = hasattr(g, 'purchase_deck') and g.purchase_deck is not None
    initial_area_len = len(g.purchase_area)
    initial_deck_len = len(g.purchase_deck.draw_pile) if has_purchase_deck else -1
    purchase_names = names(g.purchase_area)
    support_total = sum(
        1 for c in (g.purchase_area + (g.purchase_deck.draw_pile if has_purchase_deck else []))
        if getattr(c, 'card_type', None) == 'support'
    )

    t.resources = {'money': 99, 'propaganda': 99}
    static_supply_before = dict(g.static_purchase_supply)
    static_buy_result = g.buy_card(0) if g.purchase_area else {'error': 'empty purchase area'}
    static_supply_after = dict(g.static_purchase_supply)
    area_len_after_static_buy = len(g.purchase_area)

    random_slot_before = getattr(g.purchase_area[6], 'name', None) if len(g.purchase_area) > 6 else None
    resources_before_random_buy = dict(t.resources)
    random_buy_result = g.buy_card(6) if len(g.purchase_area) > 6 else {'error': 'no random slot'}
    area_len_after_random_buy = len(g.purchase_area)

    g.turn_phase = TurnPhase.END
    g.advance_turn_phase()
    area_len_after_refill = len(g.purchase_area)

    checks = {
        'has_purchase_deck': has_purchase_deck,
        'initial_area_has_static_plus_five_random': initial_area_len == 11,
        'purchase_deck_has_48_cards_after_market_draw': initial_deck_len == 48,
        'support_total_in_market_and_deck_is_18': support_total == 18,
        'static_area_contains_disruption_cards': '分神' in purchase_names and '內鬥' in purchase_names,
        'static_buy_succeeds_and_decrements_supply_without_removing_slot': (
            static_buy_result.get('success') is True
            and static_supply_after.get('宣傳家') == static_supply_before.get('宣傳家') - 1
            and area_len_after_static_buy == initial_area_len
        ),
        'random_buy_succeeds_and_removes_slot': (
            random_buy_result.get('success') is True
            and area_len_after_random_buy == area_len_after_static_buy - 1
            and random_slot_before in names(t.deck.discard_pile)
            and t.resources['money'] <= resources_before_random_buy['money']
            and t.resources['propaganda'] <= resources_before_random_buy['propaganda']
        ),
        'end_turn_refills_market_to_static_plus_five_random': area_len_after_refill == 11,
    }
    passed = sum(1 for ok in checks.values() if ok)
    payload = {
        'summary': {'total': len(checks), 'passed': passed, 'failed': len(checks) - passed},
        'checks': checks,
        'initial_area_len': initial_area_len,
        'initial_deck_len': initial_deck_len,
        'support_total': support_total,
        'purchase_names': purchase_names,
        'static_supply_before': static_supply_before,
        'static_supply_after': static_supply_after,
        'static_buy_result': static_buy_result,
        'random_slot_before': random_slot_before,
        'random_buy_result': random_buy_result,
        'area_len_after_static_buy': area_len_after_static_buy,
        'area_len_after_random_buy': area_len_after_random_buy,
        'area_len_after_refill': area_len_after_refill,
    }
    (ROOT / 'SUPPORT_PURCHASE_DECK_RUNTIME_VALIDATION.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'SUPPORT_PURCHASE_DECK_RUNTIME_VALIDATION.md').write_text(
        '# SUPPORT PURCHASE DECK RUNTIME VALIDATION\n\n'
        f"Summary: {passed}/{len(checks)} passed\n\n" +
        '\n'.join(f'- {k}: {json.dumps(v, ensure_ascii=False) if not isinstance(v, (int,bool,str)) else v}' for k, v in payload.items() if k != 'summary') + '\n',
        encoding='utf-8'
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload['summary']['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
