import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase, STATIC_PURCHASE_CARD_NAMES
from server.cards import Card

CARD = '企業人脈'


def _new_game():
    g = Game([('p1', 'player'), ('p2', 'red')])
    player, red = g.players
    player.id = 'p1'
    red.id = 'p2'
    player.faction_id = 'liberals'
    red.faction_id = 'red_army'
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    player.hand = [Card(CARD, 'money', {'money': 1})]
    player.resources = {'money': 4, 'propaganda': 0}
    return g, player, red


def main():
    g, player, red = _new_game()

    static_names = {getattr(c, 'name', str(c)) for c in g._static_purchase_cards()}
    assert static_names == set(STATIC_PURCHASE_CARD_NAMES), f'unexpected static card set: {static_names}'

    before_hand = len(player.hand)
    result = g.play_card(0, mode='action')

    choices = (getattr(g, 'pending_choice', None) or {}).get('cards', [])
    choice_zones = [c.get('zone_label') for c in choices]
    choice_names = [c.get('name') for c in choices]
    static_offered = any(name in STATIC_PURCHASE_CARD_NAMES for name in choice_names)

    static_index = next(
        (i for i, name in enumerate(choice_names) if name in STATIC_PURCHASE_CARD_NAMES),
        None,
    )
    picked_name = choice_names[static_index] if static_index is not None else None
    borrow_result = None
    if static_index is not None:
        # Resolving borrows the chosen card and immediately plays it (card text:
        # "使用後將該牌放回購買區" — borrow, use once this turn, then it returns to
        # the purchase area), so it is not expected to remain sitting in hand.
        borrow_result = g.resolve_pending_choice(player.id, static_index)

    checks = {
        'play_card_success': result.get('success') is True,
        'pending_choice_offered': bool(choices),
        'static_purchase_card_offered': static_offered,
        'total_choices_cover_full_purchase_area': len(choices) == len(getattr(g, 'purchase_area', []) or []),
        'borrow_resolved_without_error': bool(borrow_result) and not borrow_result.get('error'),
        'borrowed_chosen_card_matches': bool(borrow_result) and borrow_result.get('chosen_card') == picked_name,
    }

    payload = {
        'summary': {
            'scope': [CARD],
            'purpose': (
                '企業人脈 card text ("將購買區面朝上的任1張牌暫時移出購買區") does not restrict the '
                'borrowable pool to the random-market slots. Prior to this fix, '
                'use_purchase_area_card had prefer_random_market=true, which excluded the 6 '
                'static purchase-area cards (宣傳家/思想家/資助者/資本家/分神/內鬥). This proof shows '
                'a static card is now offered and can be borrowed.'
            ),
            'static_card_names': sorted(STATIC_PURCHASE_CARD_NAMES),
            'passed': int(all(checks.values())),
            'failed': int(not all(checks.values())),
        },
        'before_hand_count': before_hand,
        'play_card_result': result,
        'choice_zone_labels': choice_zones,
        'choice_names': choice_names,
        'picked_static_card': picked_name,
        'borrow_result': borrow_result,
        'checks': checks,
        'ok': all(checks.values()),
    }

    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'BUSINESS_NETWORK_STATIC_PURCHASE_AREA_FIX_VALIDATION_20260710.json'
    md_path = RECORD_DIR / 'BUSINESS_NETWORK_STATIC_PURCHASE_AREA_FIX_VALIDATION_20260710.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 企業人脈 static purchase area fix validation\n\n'
        '可重跑指令：`python3 scripts/validate_business_network_static_purchase_area.py`\n\n'
        f"- checks: {json.dumps(checks, ensure_ascii=False)}\n"
        f"- choice_names: {json.dumps(choice_names, ensure_ascii=False)}\n"
        f"- picked_static_card: {picked_name}\n"
        f"- borrow_result: {json.dumps(borrow_result, ensure_ascii=False)}\n"
        f"- result: {'PASS' if payload['ok'] else 'FAIL'}\n",
        encoding='utf-8',
    )
    print(json.dumps(payload, ensure_ascii=False))
    if not payload['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
