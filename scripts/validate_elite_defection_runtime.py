#!/usr/bin/env python3
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.cards import Card  # noqa: E402
from server.game import Game, GamePhase, TurnPhase  # noqa: E402

RECORD_DIR = ROOT / 'docs' / 'records' / 'event-cards'
JSON_OUT = RECORD_DIR / 'ELITE_DEFECTION_RUNTIME_VALIDATION.json'
MD_OUT = RECORD_DIR / 'ELITE_DEFECTION_RUNTIME_VALIDATION.md'


def assert_ok(result, label):
    assert result.get('success'), f'{label}: {result}'
    return result


def setup_game():
    game = Game([('viewer-id', 'viewer'), ('red-id', 'red')], market_mode='all_cards')
    viewer = game.players[0]
    red = game.players[1]
    viewer.faction_id = 'liberals'
    red.faction_id = 'red_army'
    viewer.base = '臺北'
    red.base = '北京'
    viewer.organizations = {'臺北': 1}
    red.organizations = {'北京': 1}
    viewer.hand = []
    viewer.deck.draw_pile = [Card(f'補牌{i + 1}', 'command', {}) for i in range(5)]
    viewer.deck.discard_pile = []
    red.hand = [Card('紅軍不應被棄', 'command', {})]
    red.deck.draw_pile = []
    red.deck.discard_pile = []
    game.pending_base_choices = []
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.round_start_player_index = 0
    game.turn_phase = TurnPhase.EVENT
    event = game._event_by_name('紅軍權貴出逃')
    assert event, 'missing 紅軍權貴出逃'
    game.event_deck.draw_pile = [event]
    game.event_deck.discard_pile = []
    game.current_event = None
    game.event_progress = None
    game.event_notification = None
    game.pending_choice = None
    game.action_log = []
    return game, viewer, red


def names(cards):
    return [c.name for c in cards]


def main():
    game, viewer, red = setup_game()
    checks = []

    assert_ok(game.advance_turn_phase(), 'draw event')
    assert_ok(game.advance_turn_phase(), 'enter action')
    checks.append({
        'name': 'event_visible_at_action_start',
        'passed': game.turn_phase == TurnPhase.ACTION and game.current_event and game.current_event.get('name') == '紅軍權貴出逃',
        'details': {'turn_phase': game.turn_phase.value, 'event': game.current_event.get('name') if game.current_event else None},
    })

    assert_ok(game.advance_turn_phase(), 'enter purchase')
    result = assert_ok(game.advance_turn_phase(), 'refill then settle failure before red turn')
    choice = game.state().get('pending_choice') or {}
    checks.append({
        'name': 'failure_discard_choice_after_refill_before_red_action',
        'passed': (
            bool(result.get('pending_choice'))
            and game.current_player_index == 1
            and choice.get('choice_key') == 'event_discard_self'
            and choice.get('player_id') == viewer.id
            and len(choice.get('cards') or []) == 5
        ),
        'details': {
            'result': result,
            'current_player': game.current_player().name,
            'viewer_hand_after_refill': names(viewer.hand),
            'event_progress': game.event_progress,
            'pending_choice': choice,
            'log': list(game.action_log),
        },
    })

    assert_ok(game.resolve_pending_choice(viewer.id, [0]), 'resolve discard')
    checks.append({
        'name': 'penalty_discards_refilled_non_red_viewer_not_red_army',
        'passed': len(viewer.hand) == 4 and len(viewer.deck.discard_pile) == 1 and names(red.hand) == ['紅軍不應被棄'],
        'details': {'viewer_hand': names(viewer.hand), 'viewer_discard': names(viewer.deck.discard_pile), 'red_hand': names(red.hand)},
    })

    summary = {'total': len(checks), 'passed': sum(1 for c in checks if c['passed']), 'failed': sum(1 for c in checks if not c['passed'])}
    payload = {'summary': summary, 'checks': checks}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    MD_OUT.write_text('# Elite defection runtime validation\n\n```json\n' + json.dumps(payload, ensure_ascii=False, indent=2) + '\n```\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
