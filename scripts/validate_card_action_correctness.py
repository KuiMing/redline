import json
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase

OUT_JSON = BASE / 'CARD_ACTION_CORRECTNESS_VALIDATION.json'
OUT_MD = BASE / 'CARD_ACTION_CORRECTNESS_VALIDATION.md'


def make_game_with_card(card):
    game = Game([('p1', 'actor'), ('p2', 'red')])
    actor = game.players[0]
    other = game.players[1]
    actor.name = 'actor'
    actor.faction_id = 'red_army'
    actor.base = '北京'
    actor.organizations = {'北京': 1}
    actor.resources = {'money': 0, 'propaganda': 0}
    actor.moves_left = 0
    actor.hand = [card]
    actor.deck.draw_pile = []
    actor.deck.discard_pile = []

    other.name = 'other'
    other.faction_id = 'hong_kong'
    other.base = '香港城'
    other.organizations = {'香港城': 1}

    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.static_purchase_supply = {name: 1 for name in ['宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥']}
    return game, actor


def card_from_structured(game, name):
    for row in game.structured_cards:
        if row.get('name') == name:
            return Card(row['name'], row['type'], row.get('resources', {}))
    raise KeyError(name)


def discard_names(player):
    return [getattr(c, 'name', str(c)) for c in player.deck.discard_pile]


def check(name, passed, details):
    return {'name': name, 'passed': bool(passed), 'details': details}


def run_checks():
    checks = []

    starter_cases = [
        ('追隨者', Card('追隨者', 'propaganda', {'propaganda': 1}), {'money': 0, 'propaganda': 1}),
        ('樂捐者', Card('樂捐者', 'money', {'money': 1}), {'money': 1, 'propaganda': 0}),
    ]
    for name, card, expected_resources in starter_cases:
        game, player = make_game_with_card(card)
        before = {'resources': dict(player.resources), 'hand_count': len(player.hand), 'moves_left': player.moves_left, 'discard': discard_names(player)}
        result = game.play_card(0, mode='resource')
        after = {'resources': dict(player.resources), 'hand_count': len(player.hand), 'moves_left': player.moves_left, 'discard': discard_names(player)}
        checks.append(check(
            f'{name}_grants_intrinsic_resource_and_discards_played_card',
            result.get('success') is True
            and after['resources'] == expected_resources
            and after['hand_count'] == 0
            and after['moves_left'] == before['moves_left']
            and after['discard'].count(name) == 1,
            {'result': result, 'before': before, 'after': after, 'expected_resources': expected_resources},
        ))

    static_expectations = {
        '宣傳家': {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 1, 'orgs': {'北京': 2}, 'supply_delta': 1},
        '思想家': {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 3, 'orgs': {'北京': 2}, 'supply_delta': 1},
        '資助者': {'resources': {'money': 2, 'propaganda': 2}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply_delta': 1},
        '資本家': {'resources': {'money': 3, 'propaganda': 3}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply_delta': 1},
        '分神': {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply_delta': 1},
        '內鬥': {'resources': {'money': 0, 'propaganda': 0}, 'moves_left': 0, 'orgs': {'北京': 1}, 'supply_delta': 0},
    }

    seed_game = Game([('seed1', 'seed'), ('seed2', 'red')])
    for name, expected in static_expectations.items():
        game, player = make_game_with_card(card_from_structured(seed_game, name))
        supply_before = game.static_purchase_supply.get(name, 0)
        before = {
            'resources': dict(player.resources),
            'moves_left': player.moves_left,
            'orgs': dict(player.organizations),
            'supply': supply_before,
            'discard': discard_names(player),
        }
        result = game.play_card(0, mode='action')
        supply_after = game.static_purchase_supply.get(name, 0)
        after = {
            'resources': dict(player.resources),
            'moves_left': player.moves_left,
            'orgs': dict(player.organizations),
            'supply': supply_after,
            'discard': discard_names(player),
        }
        should_return_to_supply = expected['supply_delta'] == 1
        checks.append(check(
            f'{name}_effect_and_removed_card_destination',
            result.get('success') is True
            and after['resources'] == expected['resources']
            and after['moves_left'] == expected['moves_left']
            and after['orgs'] == expected['orgs']
            and supply_after == supply_before + expected['supply_delta']
            and (name not in after['discard'] if should_return_to_supply else after['discard'].count(name) == 1),
            {
                'result': result,
                'before': before,
                'after': after,
                'expected': expected,
                'rule': '被移除的卡牌直接回到購買區；常設卡移除後對應庫存 +1。內鬥沒有移除效果，正常進棄牌堆。',
            },
        ))

    return checks


def write_outputs(checks):
    summary = {
        'total': len(checks),
        'passed': sum(1 for c in checks if c['passed']),
        'failed': sum(1 for c in checks if not c['passed']),
    }
    out = {'date': date.today().isoformat(), 'summary': summary, 'checks': checks}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = ['# CARD ACTION CORRECTNESS VALIDATION', '', f"日期：{out['date']}", '', f"summary: {summary}", '']
    for item in checks:
        status = 'PASS' if item['passed'] else 'FAIL'
        lines.append(f"## {item['name']} — {status}")
        for k, v in item['details'].items():
            lines.append(f"- {k}: {v}")
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    return out


def main():
    out = write_outputs(run_checks())
    print(json.dumps({'summary': out['summary'], 'json': str(OUT_JSON), 'md': str(OUT_MD)}, ensure_ascii=False))
    if out['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
