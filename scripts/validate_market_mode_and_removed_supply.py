import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase, GamePhase
from server.cards import Card

OUT_JSON = ROOT / 'MARKET_MODE_AND_REMOVED_SUPPLY_VALIDATION.json'
OUT_MD = ROOT / 'MARKET_MODE_AND_REMOVED_SUPPLY_VALIDATION.md'


def make_game(mode: str):
    game = Game([('p1', 'viewer'), ('p2', 'red')], market_mode=mode)
    viewer = game.players[0]
    red = game.players[1]
    viewer.faction_id = 'tibet_dehradun'
    viewer.base = '德拉敦'
    viewer.organizations = {'德拉敦': 1}
    viewer.resources = {'money': 0, 'propaganda': 0}
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    return game, viewer, red


def make_card(game: Game, name: str):
    card_def = next(c for c in game.structured_cards if c.get('name') == name)
    return Card(card_def['name'], card_def['type'], card_def.get('resources', {}))


def validate():
    checks = []

    game53, _, _ = make_game('sample_53')
    checks.append({
        'name': 'sample_53 draw pile is 48 after 5 random market cards exposed',
        'passed': len(game53.purchase_deck.draw_pile) == 48,
        'actual': len(game53.purchase_deck.draw_pile),
        'expected': 48,
    })
    checks.append({
        'name': 'sample_53 state market mode',
        'passed': game53.state().get('market_mode') == 'sample_53',
        'actual': game53.state().get('market_mode'),
        'expected': 'sample_53',
    })

    game_all, _, _ = make_game('all_cards')
    all_count = len(game_all.purchase_deck.draw_pile)
    checks.append({
        'name': 'all_cards draw pile exceeds sample_53 after 5 random market cards exposed',
        'passed': all_count > 48,
        'actual': all_count,
        'expected': '> 48',
    })
    checks.append({
        'name': 'all_cards state market mode',
        'passed': game_all.state().get('market_mode') == 'all_cards',
        'actual': game_all.state().get('market_mode'),
        'expected': 'all_cards',
    })

    remove_game, viewer, _ = make_game('sample_53')
    viewer.hand = [make_card(remove_game, '宣傳家')]
    while len(remove_game.purchase_area) < 11:
        drawn = remove_game._draw_purchase_cards(1)
        if not drawn:
            break
        remove_game.purchase_area.extend(drawn)
    before_len = len(remove_game.purchase_area)
    before_supply = dict(remove_game.static_purchase_supply)
    result = remove_game.play_card(0, mode='action')
    after_len = len(remove_game.purchase_area)
    after_supply = dict(remove_game.static_purchase_supply)
    checks.append({
        'name': 'remove propagandist keeps visible purchase area length',
        'passed': before_len == after_len,
        'actual': {'before': before_len, 'after': after_len},
        'expected': 'equal',
    })
    checks.append({
        'name': 'remove propagandist increments static supply',
        'passed': after_supply.get('宣傳家') == before_supply.get('宣傳家', 0) + 1,
        'actual': {'before': before_supply.get('宣傳家'), 'after': after_supply.get('宣傳家')},
        'expected': before_supply.get('宣傳家', 0) + 1,
    })
    checks.append({
        'name': 'remove propagandist play succeeds',
        'passed': result.get('success') is True,
        'actual': result,
        'expected': {'success': True},
    })

    payload = {
        'summary': {
            'total': len(checks),
            'passed': sum(1 for c in checks if c['passed']),
            'failed': sum(1 for c in checks if not c['passed']),
        },
        'checks': checks,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    lines = [
        '# Market Mode / Removed Supply Smoke Validation',
        '',
        f"- total: {payload['summary']['total']}",
        f"- passed: {payload['summary']['passed']}",
        f"- failed: {payload['summary']['failed']}",
        '',
        '| Check | Passed | Actual | Expected |',
        '|---|---|---|---|',
    ]
    for c in checks:
        lines.append(f"| {c['name']} | {'✅' if c['passed'] else '❌'} | `{json.dumps(c['actual'], ensure_ascii=False)}` | `{json.dumps(c['expected'], ensure_ascii=False)}` |")
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return payload


if __name__ == '__main__':
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
