import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'faction-ui'
sys.path.insert(0, str(ROOT))

from server.game import Game, STATIC_PURCHASE_CARD_SUPPLY


def _names(cards):
    return [getattr(c, 'name', str(c)) for c in cards]


def _make_game(faction_id):
    """比照 main.py lobby 正式開局順序：override faction → _init_decks → 重設供應 → 套 setup 能力。"""
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = faction_id
    b.faction_id = 'red_army'
    g._init_decks()
    g.static_purchase_supply = dict(STATIC_PURCHASE_CARD_SUPPLY)
    for p in g.players:
        g._apply_setup_abilities(p)
    return g, a, b


def _zone_counts(player, card_name):
    return {
        'draw': _names(player.deck.draw_pile).count(card_name),
        'hand': _names(player.hand).count(card_name),
        'discard': _names(player.deck.discard_pile).count(card_name),
    }


def case_hong_kong():
    g, a, b = _make_game('hong_kong')
    z = _zone_counts(a, '宣傳家')
    total_cards = len(a.deck.draw_pile) + len(a.hand)
    checks = {
        'one_extra_in_deck_zone': z['draw'] + z['hand'] == 1,
        'none_in_discard': z['discard'] == 0 and not a.deck.discard_pile,
        'hand_still_five': len(a.hand) == 5,
        'deck_total_eleven': total_cards == 11,
        'supply_decremented_once': g.static_purchase_supply['宣傳家'] == STATIC_PURCHASE_CARD_SUPPLY['宣傳家'] - 1,
    }
    return {'name': 'hong_kong_攬炒策略_shuffled_into_deck', 'zones': z, 'checks': checks, 'ok': all(checks.values())}


def case_gender_revolution():
    g, a, b = _make_game('gender_revolution')  # 活動家（abilities_text 路徑）+2 宣傳家
    z = _zone_counts(a, '宣傳家')
    checks = {
        'two_extras_in_deck_zone': z['draw'] + z['hand'] == 2,
        'none_in_discard': not a.deck.discard_pile,
        'hand_still_five': len(a.hand) == 5,
        'deck_total_twelve': len(a.deck.draw_pile) + len(a.hand) == 12,
    }
    return {'name': 'gender_revolution_活動家_shuffled_into_deck', 'zones': z, 'checks': checks, 'ok': all(checks.values())}


def case_minyun():
    g, a, b = _make_game('minyun')  # 各界資助 +1 資助者
    z = _zone_counts(a, '資助者')
    checks = {
        'one_patron_in_deck_zone': z['draw'] + z['hand'] == 1,
        'none_in_discard': not a.deck.discard_pile,
        'supply_decremented_once': g.static_purchase_supply['資助者'] == STATIC_PURCHASE_CARD_SUPPLY['資助者'] - 1,
    }
    return {'name': 'minyun_各界資助_shuffled_into_deck', 'zones': z, 'checks': checks, 'ok': all(checks.values())}


def case_red_army_untouched():
    g, a, b = _make_game('hong_kong')
    red_zone = _names(b.deck.draw_pile) + _names(b.hand)
    checks = {
        'red_support_still_in_deck_zone': red_zone.count('紅軍奧援') == 1,
        'red_deck_total_eleven': len(red_zone) == 11,  # 10 起始 + 紅軍奧援
        'red_discard_empty': not b.deck.discard_pile,
    }
    return {'name': 'red_army_starter_deck_untouched', 'checks': checks, 'ok': all(checks.values())}


def case_opening_hand_reachable():
    # 修正核心：洗入起始牌庫代表「起手就可能抽到」。40 局統計：
    # 性別革命 2/12 張是額外宣傳家，起手 5 張抽到至少 1 張的機率約 68%；
    # 40 局全有或全無的機率皆趨近 0。
    runs = 40
    in_hand_runs = 0
    for _ in range(runs):
        g, a, b = _make_game('gender_revolution')
        if _names(a.hand).count('宣傳家') > 0:
            in_hand_runs += 1
    checks = {
        'sometimes_in_opening_hand': in_hand_runs > 0,
        'not_always_in_opening_hand': in_hand_runs < runs,
    }
    return {'name': 'setup_cards_reachable_in_opening_hand', 'in_hand_runs': in_hand_runs, 'runs': runs, 'checks': checks, 'ok': all(checks.values())}


def case_supply_empty_guard():
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = 'hong_kong'
    b.faction_id = 'red_army'
    g._init_decks()
    g.static_purchase_supply = dict(STATIC_PURCHASE_CARD_SUPPLY)
    g.static_purchase_supply['宣傳家'] = 0
    hand_before = _names(a.hand)
    for p in g.players:
        g._apply_setup_abilities(p)
    z = _zone_counts(a, '宣傳家')
    checks = {
        'no_card_added_when_supply_empty': z['draw'] + z['hand'] + z['discard'] == 0,
        'hand_untouched_without_gain': _names(a.hand) == hand_before,
    }
    return {'name': 'supply_empty_guard_no_reshuffle', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_hong_kong(),
        case_gender_revolution(),
        case_minyun(),
        case_red_army_untouched(),
        case_opening_hand_reachable(),
        case_supply_empty_guard(),
    ]
    summary = {
        'scope': ['攬炒策略', '達賴救援', '東突厥斯坦政府', '活動家', '各界資助'],
        'purpose': (
            'S4 (second-pass audit): setup bonus cards ("洗入起始牌庫") were added to the '
            'DISCARD pile after the opening hand was already drawn, so they missed the entire '
            'first deck cycle. Fixed: _apply_setup_abilities now appends them to the draw '
            'pile, returns the drawn opening hand to the deck, reshuffles, and redraws the '
            'same hand size — equivalent to building an 11-12 card starting deck before the '
            'opening draw. Static-supply decrement behavior unchanged; no-op (and no '
            'reshuffle) when nothing was gained.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'SETUP_CARDS_SHUFFLED_INTO_DECK_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'SETUP_CARDS_SHUFFLED_INTO_DECK_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 開局額外卡洗入起始牌庫驗證（S4）\n\n'
        '可重跑指令：`python3 scripts/validate_setup_cards_shuffled_into_deck.py`\n\n'
        f"- total: {summary['total']}\n"
        f"- passed: {summary['passed']}\n"
        f"- failed: {summary['failed']}\n\n"
        '## Results\n\n'
        + '\n'.join(
            f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: checks={json.dumps(r['checks'], ensure_ascii=False)}"
            for r in results
        )
        + '\n',
        encoding='utf-8',
    )
    print(json.dumps(payload, ensure_ascii=False, default=str))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
