import json
import random
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.game import Game, TurnPhase
from server.main import create_room, join_game, choose_faction, set_ready, start_game, manager

RECORD_DIR = BASE / 'docs' / 'records' / 'playtest-flow'


def assert_true(checks, name, passed, details=None):
    checks.append({
        'name': name,
        'passed': bool(passed),
        'details': details or {},
    })


def choose_all_bases(game):
    choices = []
    for pid, choice_data in list(game.pending_base_choices.items()):
        selected = None
        labels = choice_data.get('labels') or []
        resolved = choice_data.get('resolved') or {}
        for label in labels:
            for town in resolved.get(label, []) or []:
                result = game.set_base_choice(pid, town, label=label)
                if result.get('success'):
                    selected = {'player_id': pid, 'label': label, 'town': town, 'result': result}
                    break
            if selected:
                break
        choices.append(selected)
    return choices


def first_current_player_action_card(game):
    player = game.current_player()
    for idx, card in enumerate(player.hand):
        name = getattr(card, 'name', str(card))
        if name:
            return idx, name
    return None, None


def setup_formal_lobby_game():
    create = create_room()
    game_id = create['game_id']
    host_id = create['host_id']
    join = join_game({'game_id': game_id, 'name': 'ally'})
    ally_id = join['player_id']
    choose_faction({'game_id': game_id, 'player_id': host_id, 'faction_id': 'red_army'})
    choose_faction({'game_id': game_id, 'player_id': ally_id, 'faction_id': 'taiwan_green', 'base_name': '臺北'})
    set_ready({'game_id': game_id, 'player_id': host_id, 'ready': True})
    set_ready({'game_id': game_id, 'player_id': ally_id, 'ready': True})
    start = start_game({'game_id': game_id, 'player_id': host_id, 'market_mode': 'sample_53'})
    return {
        'game_id': game_id,
        'host_id': host_id,
        'ally_id': ally_id,
        'start_result': start,
        'game': manager.games.get(game_id),
    }


def run_validation():
    random.seed(20260531)
    game = Game([('p1', 'player1'), ('p2', 'player2'), ('p3', 'player3')])
    trace = []
    checks = []

    base_choices = choose_all_bases(game)
    state_after_setup = game.state()
    trace.append({
        'step': 'after_base_selection',
        'base_choices': base_choices,
        'turn': state_after_setup['turn'],
        'turn_phase': state_after_setup['turn_phase'],
        'current_player': state_after_setup['current_player'],
        'current_event': state_after_setup.get('current_event'),
    })
    assert_true(checks, 'game starts first player in event phase after base selection', game.turn == 1 and game.turn_phase == TurnPhase.EVENT, {
        'turn': game.turn,
        'turn_phase': str(game.turn_phase),
        'current_player': game.current_player().name,
    })
    assert_true(checks, 'direct engine base selection immediately exposes current event', bool(state_after_setup.get('current_event')), {
        'current_event': state_after_setup.get('current_event'),
        'event_deck_count': state_after_setup.get('event_deck_count'),
    })

    lobby_setup = setup_formal_lobby_game()
    lobby_game = lobby_setup['game']
    lobby_state = lobby_game.state() if lobby_game else {}
    trace.append({
        'step': 'formal_lobby_start_event_state',
        'game_id': lobby_setup['game_id'],
        'start_result': lobby_setup['start_result'],
        'turn': lobby_state.get('turn'),
        'turn_phase': lobby_state.get('turn_phase'),
        'current_player': lobby_state.get('current_player'),
        'current_event': lobby_state.get('current_event'),
        'event_deck_count': lobby_state.get('event_deck_count'),
    })
    assert_true(checks, 'formal lobby start immediately exposes current event card', bool(lobby_state.get('current_event')) and lobby_state.get('turn_phase') == 'event', {
        'start_result': lobby_setup['start_result'],
        'turn_phase': lobby_state.get('turn_phase'),
        'current_event': lobby_state.get('current_event'),
        'event_deck_count': lobby_state.get('event_deck_count'),
    })

    lobby_start_player = lobby_state.get('current_player')
    lobby_round_start_index = getattr(lobby_game, 'round_start_player_index', None)
    lobby_turn_flow = []
    for step in ['ben_event_to_action', 'ben_action_to_end', 'ben_end_to_red_event', 'red_event_to_action', 'red_action_to_end', 'red_end_to_next_round']:
        before_state = lobby_game.state()
        advance_result = lobby_game.advance_turn_phase()
        step_state = lobby_game.state()
        lobby_turn_flow.append({
            'step': step,
            'result': advance_result,
            'turn': step_state.get('turn'),
            'turn_phase': step_state.get('turn_phase'),
            'current_player': step_state.get('current_player'),
            'current_faction': getattr(lobby_game.current_player(), 'faction_id', None),
            'event_before': (before_state.get('current_event') or {}).get('id'),
            'event_after': (step_state.get('current_event') or {}).get('id'),
            'event_deck_before': before_state.get('event_deck_count'),
            'event_deck_after': step_state.get('event_deck_count'),
            'event_discard_before': before_state.get('event_discard_count'),
            'event_discard_after': step_state.get('event_discard_count'),
            'event_status_after': ((step_state.get('current_event') or {}).get('progress') or {}).get('status'),
        })
    trace.append({
        'step': 'formal_lobby_round_flow_after_ben_turn',
        'round_start_player': lobby_start_player,
        'round_start_player_index': lobby_round_start_index,
        'flow': lobby_turn_flow,
    })
    ben_end_state = lobby_turn_flow[2]
    red_end_state = lobby_turn_flow[5]
    assert_true(checks, 'formal 2p lobby keeps turn 1 when Ben ends and passes to Red Army',
        ben_end_state.get('turn') == 1 and ben_end_state.get('turn_phase') == 'event' and ben_end_state.get('current_faction') == 'red_army',
        ben_end_state,
    )
    assert_true(checks, 'Ben end does not draw or replace event before Red Army also ends',
        ben_end_state.get('event_before') == ben_end_state.get('event_after')
        and ben_end_state.get('event_deck_before') == ben_end_state.get('event_deck_after')
        and ben_end_state.get('event_discard_before') == ben_end_state.get('event_discard_after'),
        ben_end_state,
    )
    assert_true(checks, 'formal 2p lobby increments to turn 2 only after Red Army ends',
        red_end_state.get('turn') == 2 and red_end_state.get('turn_phase') == 'event' and red_end_state.get('current_player') == lobby_start_player,
        red_end_state,
    )
    assert_true(checks, 'new event is drawn only after the full round ends',
        red_end_state.get('event_before') != red_end_state.get('event_after')
        and red_end_state.get('event_deck_after') == red_end_state.get('event_deck_before') - 1
        and red_end_state.get('event_discard_after') == red_end_state.get('event_discard_before') + 1,
        red_end_state,
    )

    idx, card_name = first_current_player_action_card(game)
    event_play_result = game.play_card(idx, mode='action') if idx is not None else {'skipped': True}
    trace.append({
        'step': 'event_phase_action_attempt',
        'card': card_name,
        'result': event_play_result,
        'turn_phase': game.turn_phase,
        'current_player': game.current_player().name,
    })
    assert_true(checks, 'event phase blocks action card play', isinstance(event_play_result, dict) and event_play_result.get('error') == 'Not in ACTION phase', event_play_result)

    advance_to_action = game.advance_turn_phase()
    state_action = game.state()
    trace.append({
        'step': 'advance_event_to_action',
        'result': advance_to_action,
        'turn': state_action['turn'],
        'turn_phase': state_action['turn_phase'],
        'current_player': state_action['current_player'],
        'current_event': state_action.get('current_event'),
    })
    assert_true(checks, 'advance from event reaches action for same current player', state_action['turn_phase'] == 'action' and state_action['current_player'] == 'player1', state_action)

    idx, card_name = first_current_player_action_card(game)
    action_play_result = game.play_card(idx, mode='resource') if idx is not None else {'skipped': True}
    trace.append({
        'step': 'action_phase_resource_play',
        'card': card_name,
        'result': action_play_result,
        'turn_phase': game.turn_phase,
        'current_player': game.current_player().name,
    })
    assert_true(checks, 'action phase allows current player card play', isinstance(action_play_result, dict) and action_play_result.get('success'), action_play_result)

    to_end = game.advance_turn_phase()
    to_next_event = game.advance_turn_phase()
    state_next_event = game.state()
    trace.append({
        'step': 'end_turn_to_next_event',
        'advance_to_end': to_end,
        'advance_to_next_event': to_next_event,
        'turn': state_next_event['turn'],
        'turn_phase': state_next_event['turn_phase'],
        'current_player': state_next_event['current_player'],
        'current_event': state_next_event.get('current_event'),
    })
    assert_true(checks, 'ending turn advances to next player event phase without drawing a new event',
        state_next_event['turn_phase'] == 'event'
        and state_next_event['current_player'] == 'player2'
        and (state_next_event.get('current_event') or {}).get('id') == (state_action.get('current_event') or {}).get('id')
        and state_next_event.get('event_deck_count') == state_action.get('event_deck_count')
        and state_next_event.get('event_discard_count') == state_action.get('event_discard_count'),
        state_next_event,
    )

    next_idx, next_card = first_current_player_action_card(game)
    next_event_play = game.play_card(next_idx, mode='action') if next_idx is not None else {'skipped': True}
    trace.append({
        'step': 'next_player_event_phase_action_attempt',
        'card': next_card,
        'result': next_event_play,
        'turn_phase': game.turn_phase,
        'current_player': game.current_player().name,
    })
    assert_true(checks, 'next player event phase still blocks action until advanced', isinstance(next_event_play, dict) and next_event_play.get('error') == 'Not in ACTION phase', next_event_play)

    next_to_action = game.advance_turn_phase()
    state_next_action = game.state()
    trace.append({
        'step': 'next_player_advance_event_to_action',
        'result': next_to_action,
        'turn': state_next_action['turn'],
        'turn_phase': state_next_action['turn_phase'],
        'current_player': state_next_action['current_player'],
    })
    assert_true(checks, 'next player can advance event to action without changing current player', state_next_action['turn_phase'] == 'action' and state_next_action['current_player'] == 'player2', state_next_action)

    result = {
        'summary': {
            'passed': all(item['passed'] for item in checks),
            'passed_count': sum(1 for item in checks if item['passed']),
            'failed_count': sum(1 for item in checks if not item['passed']),
        },
        'checks': checks,
        'trace': trace,
        'final_state': game.state(),
    }
    return result


def write_outputs(result):
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'TURN_PHASE_ACTION_GATING_VALIDATION.json'
    md_path = RECORD_DIR / 'TURN_PHASE_ACTION_GATING_VALIDATION.md'
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = [
        '# TURN PHASE ACTION GATING VALIDATION',
        '',
        '日期：2026-05-31',
        '',
        f"- passed: {result['summary']['passed']}",
        f"- passed_count: {result['summary']['passed_count']}",
        f"- failed_count: {result['summary']['failed_count']}",
        '',
        '## Checks',
    ]
    for check in result['checks']:
        marker = 'PASS' if check['passed'] else 'FAIL'
        lines.append(f"- {marker}: {check['name']}")
        if check.get('details'):
            lines.append(f"  - details: {check['details']}")
    lines.extend(['', '## Trace'])
    for item in result['trace']:
        lines.append(f"### {item['step']}")
        for key, value in item.items():
            if key == 'step':
                continue
            lines.append(f"- {key}: {value}")
        lines.append('')
    md_path.write_text('\n'.join(lines), encoding='utf-8')
    return json_path, md_path


def main():
    result = run_validation()
    json_path, md_path = write_outputs(result)
    print(json.dumps({
        'passed': result['summary']['passed'],
        'passed_count': result['summary']['passed_count'],
        'failed_count': result['summary']['failed_count'],
        'json_path': str(json_path.relative_to(BASE)),
        'md_path': str(md_path.relative_to(BASE)),
    }, ensure_ascii=False))
    if not result['summary']['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
