#!/usr/bin/env python3
import json
from pathlib import Path

from server.cards import Card
from server.game import Game, TurnPhase

BASE = Path(__file__).resolve().parent.parent
OUT_DIR = BASE / 'docs' / 'records' / 'event-cards'
OUT_JSON = OUT_DIR / 'EAST_TURKESTAN_FAILURE_TARGETS.json'
OUT_MD = OUT_DIR / 'EAST_TURKESTAN_FAILURE_TARGETS.md'


def make_game(hand_counts=(3, 3, 3), current_index=1):
    game = Game([('p1', 'f'), ('p2', 'g'), ('p3', 'r')])
    fixtures = [
        ('hong_kong', '香港城'),
        ('taiwan_blue', '臺北'),
        ('red_army', '北京'),
    ]
    for player, (faction, base), hand_count in zip(game.players, fixtures, hand_counts):
        player.faction_id = faction
        player.base = base
        player.organizations = {base: 1}
        player.hand = [Card(f'{player.name}手牌{i + 1}', 'starter', {}) for i in range(hand_count)]
        player.deck.draw_pile = []
        player.deck.discard_pile = []
    game.current_player_index = current_index
    game.round_start_player_index = 0
    game.turn = 1
    game.current_event = game._event_by_name('東突厥集中營')
    game.event_progress = {
        'count': 0,
        'required': 1,
        'succeeded': False,
        'settled': False,
        'status': 'active',
    }
    game.turn_phase = TurnPhase.END
    game.action_log = []
    return game


def settle(game):
    before = {
        player.name: {
            'faction': player.faction_id,
            'hand': [card.name for card in player.hand],
            'discard': [card.name for card in player.deck.discard_pile],
        }
        for player in game.players
    }
    result = game._settle_current_event()
    after = {
        player.name: {
            'faction': player.faction_id,
            'hand': [card.name for card in player.hand],
            'discard': [card.name for card in player.deck.discard_pile],
        }
        for player in game.players
    }
    return {
        'result': result,
        'before': before,
        'after': after,
        'log': list(game.action_log),
        'event_progress': dict(game.event_progress),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target_case = settle(make_game(hand_counts=(3, 3, 3)))
    empty_case = settle(make_game(hand_counts=(0, 0, 3)))

    non_red_names = ['f', 'g']
    red_name = 'r'
    target_assertions = {
        name: {
            'hand_delta': len(target_case['before'][name]['hand']) - len(target_case['after'][name]['hand']),
            'discard_delta': len(target_case['after'][name]['discard']) - len(target_case['before'][name]['discard']),
        }
        for name in non_red_names + [red_name]
    }
    checks = [
        target_assertions['f']['hand_delta'] == 1,
        target_assertions['g']['hand_delta'] == 1,
        target_assertions['r']['hand_delta'] == 0,
        any('f discarded 1 random hand card(s)' in entry and 'g discarded 1 random hand card(s)' in entry for entry in target_case['log']),
        any('no eligible non-red player hand cards to discard' in entry for entry in empty_case['log']),
        target_case['event_progress']['status'] == 'failure',
    ]
    report = {
        'scenario': '東突厥集中營 mission failure random discard targets non-red players',
        'passed': all(checks),
        'checks': checks,
        'target_case': target_case,
        'empty_hand_case': empty_case,
        'target_assertions': target_assertions,
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    OUT_MD.write_text(
        '# 東突厥集中營 failure target validation\n\n'
        f"- passed: `{report['passed']}`\n"
        f"- non-red f hand delta: `{target_assertions['f']['hand_delta']}`\n"
        f"- non-red g hand delta: `{target_assertions['g']['hand_delta']}`\n"
        f"- red r hand delta: `{target_assertions['r']['hand_delta']}`\n"
        f"- target log: `{target_case['log']}`\n"
        f"- empty-hand log: `{empty_case['log']}`\n",
        encoding='utf-8',
    )
    print(json.dumps({'passed': report['passed'], 'json': str(OUT_JSON), 'md': str(OUT_MD)}, ensure_ascii=False))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
