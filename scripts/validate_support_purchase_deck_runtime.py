import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase


def main():
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
    support_in_deck = sum(1 for c in (g.purchase_deck.draw_pile if has_purchase_deck else []) if getattr(c, 'card_type', None) == 'support')
    purchase_names = [getattr(c, 'name', str(c)) for c in g.purchase_area]

    t.resources = {'money': 99, 'propaganda': 99}
    first_name = getattr(g.purchase_area[0], 'name', '') if g.purchase_area else ''
    buy_result = g.buy_card(0) if g.purchase_area else {'error': 'empty purchase area'}
    area_len_after = len(g.purchase_area)

    payload = {
        'summary': {
            'total': 7,
            'passed': sum([
                has_purchase_deck,
                initial_area_len == 6,
                initial_deck_len == 53,
                support_in_deck == 18,
                '分神' in purchase_names,
                '內鬥' in purchase_names,
                buy_result.get('success') is True and area_len_after == 6,
            ]),
            'failed': 7 - sum([
                has_purchase_deck,
                initial_area_len == 6,
                initial_deck_len == 53,
                support_in_deck == 18,
                '分神' in purchase_names,
                '內鬥' in purchase_names,
                buy_result.get('success') is True and area_len_after == 6,
            ]),
        },
        'has_purchase_deck': has_purchase_deck,
        'initial_area_len': initial_area_len,
        'initial_deck_len': initial_deck_len,
        'support_in_deck': support_in_deck,
        'purchase_names': purchase_names,
        'first_name': first_name,
        'buy_result': buy_result,
        'area_len_after': area_len_after,
    }
    (ROOT / 'SUPPORT_PURCHASE_DECK_RUNTIME_VALIDATION.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'SUPPORT_PURCHASE_DECK_RUNTIME_VALIDATION.md').write_text(
        '# SUPPORT PURCHASE DECK RUNTIME VALIDATION\n\n' +
        '\n'.join(f'- {k}: {json.dumps(v, ensure_ascii=False) if not isinstance(v, (int,bool,str)) else v}' for k, v in payload.items() if k != 'summary') + '\n',
        encoding='utf-8'
    )
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == '__main__':
    main()
