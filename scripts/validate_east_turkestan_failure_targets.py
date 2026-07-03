#!/usr/bin/env python3
import json
from pathlib import Path

from server.cards import Card
from server.game import Game, TurnPhase

BASE = Path(__file__).resolve().parent.parent
OUT_DIR = BASE / 'docs' / 'records' / 'event-cards'
OUT_JSON = OUT_DIR / 'EAST_TURKESTAN_FAILURE_TARGETS.json'
OUT_MD = OUT_DIR / 'EAST_TURKESTAN_FAILURE_TARGETS.md'


def make_game(hand_counts=(3, 0, 3), draw_counts=(0, 5, 0), current_index=1):
    game = Game([('p1', 'f'), ('p2', 'g'), ('p3', 'r')])
    fixtures = [
        ('hong_kong', '香港城'),
        ('taiwan_blue', '臺北'),
        ('red_army', '北京'),
    ]
    for player, (faction, base), hand_count, draw_count in zip(game.players, fixtures, hand_counts, draw_counts):
        player.faction_id = faction
        player.base = base
        player.organizations = {base: 1}
        player.hand = [Card(f'{player.name}手牌{i + 1}', 'starter', {}) for i in range(hand_count)]
        player.deck.draw_pile = [Card(f'{player.name}補牌{i + 1}', 'starter', {}) for i in range(draw_count)]
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


def snapshot(game):
    return {
        player.name: {
            'faction': player.faction_id,
            'hand': [card.name for card in player.hand],
            'draw': [card.name for card in player.deck.draw_pile],
            'discard': [card.name for card in player.deck.discard_pile],
        }
        for player in game.players
    }


def settle_via_phase_button(game):
    before = snapshot(game)
    result = game.advance_turn_phase()
    after = snapshot(game)
    return {
        'result': result,
        'before': before,
        'after': after,
        'log': list(game.action_log),
        'event_progress': dict(game.event_progress),
        'current_player': game.current_player().name,
        'turn_phase': str(game.turn_phase),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    refill_case = settle_via_phase_button(make_game(hand_counts=(3, 0, 3), draw_counts=(0, 5, 0)))
    empty_case = settle_via_phase_button(make_game(hand_counts=(0, 0, 3), draw_counts=(0, 0, 0)))

    target_assertions = {
        'f_hand_delta': len(refill_case['before']['f']['hand']) - len(refill_case['after']['f']['hand']),
        'g_hand_after_refill_and_penalty': len(refill_case['after']['g']['hand']),
        'g_discard_delta': len(refill_case['after']['g']['discard']) - len(refill_case['before']['g']['discard']),
        'r_hand_delta': len(refill_case['before']['r']['hand']) - len(refill_case['after']['r']['hand']),
    }
    checks = [
        # Existing non-red player with hand loses 1 card.
        target_assertions['f_hand_delta'] == 1,
        # Final non-red actor had no hand before end turn, refilled to 5, then lost 1.
        target_assertions['g_hand_after_refill_and_penalty'] == 4,
        target_assertions['g_discard_delta'] == 1,
        # Red Army is never targeted by this default mission-failure discard.
        target_assertions['r_hand_delta'] == 0,
        any('f discarded 1 random hand card(s)' in entry and 'g discarded 1 random hand card(s)' in entry for entry in refill_case['log']),
        any('no eligible non-red player hand cards to discard' in entry for entry in empty_case['log']),
        refill_case['event_progress']['status'] == 'failure',
        refill_case['current_player'] == 'r',
    ]
    report = {
        'scenario': '東突厥集中營 failure resolves after final non-red refill, then random-discards non-red players',
        'passed': all(checks),
        'checks': checks,
        'refill_case': refill_case,
        'empty_hand_case': empty_case,
        'target_assertions': target_assertions,
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    OUT_MD.write_text(
        '# 東突厥集中營 failure target/timing validation\n\n'
        f"- passed: `{report['passed']}`\n"
        f"- f hand delta: `{target_assertions['f_hand_delta']}`\n"
        f"- g hand after refill + penalty: `{target_assertions['g_hand_after_refill_and_penalty']}`\n"
        f"- g discard delta: `{target_assertions['g_discard_delta']}`\n"
        f"- red r hand delta: `{target_assertions['r_hand_delta']}`\n"
        f"- refill-case log: `{refill_case['log']}`\n"
        f"- empty-hand log: `{empty_case['log']}`\n",
        encoding='utf-8',
    )
    print(json.dumps({'passed': report['passed'], 'json': str(OUT_JSON), 'md': str(OUT_MD)}, ensure_ascii=False))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
