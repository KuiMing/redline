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
    # Current model: the game opens directly in the first player's ACTION phase with the
    # round's event already drawn — there is no per-player resting EVENT phase.
    assert_true(checks, 'game opens first player in ACTION phase with round event drawn', game.turn == 1 and game.turn_phase == TurnPhase.ACTION and bool(state_after_setup.get('current_event')), {
        'turn': game.turn,
        'turn_phase': str(game.turn_phase),
        'current_player': game.current_player().name,
        'current_event': (state_after_setup.get('current_event') or {}).get('id'),
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
    assert_true(checks, 'formal lobby start immediately exposes current event card in ACTION phase', bool(lobby_state.get('current_event')) and lobby_state.get('turn_phase') == 'action', {
        'start_result': lobby_setup['start_result'],
        'turn_phase': lobby_state.get('turn_phase'),
        'current_event': lobby_state.get('current_event'),
        'event_deck_count': lobby_state.get('event_deck_count'),
    })

    lobby_start_player = lobby_state.get('current_player')
    lobby_round_start_index = getattr(lobby_game, 'round_start_player_index', None)
    lobby_turn_flow = []
    # 這段只驗「回合/階段推進」的形狀，跟抽到哪張事件無關；固定種子下，其它初始化
    # （如購買牌庫大小）一變動就會改變 RNG 消耗順序、換掉開局事件——若剛好抽到
    # 結算會開待選擇的任務事件（如大災難失敗懲罰），advance 會被待選擇擋住，讓
    # 這段測試因為「事件運氣」而非「階段推進」失敗。改為固定換成無效果的歲月靜好，
    # 讓回合流程的斷言與事件內容脫鉤（2026-07-17）。
    lobby_game.current_event = dict(lobby_game._event_by_name('歲月靜好'))
    lobby_game.event_progress = {'count': 0, 'required': 0, 'succeeded': True, 'settled': True, 'status': 'idle'}
    # Current model: each player's turn is ACTION -> END (2 advances), and the round's event
    # is drawn only when the round wraps back to the starting player.
    for step in ['first_action_to_end', 'first_end_to_second_action', 'second_action_to_end', 'second_end_to_next_round']:
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
        'step': 'formal_lobby_round_flow',
        'round_start_player': lobby_start_player,
        'round_start_player_index': lobby_round_start_index,
        'flow': lobby_turn_flow,
    })
    passed_to_second = lobby_turn_flow[1]   # first player's END -> second player's ACTION
    round_wrap_state = lobby_turn_flow[3]   # second player's END -> next round (turn 2)
    assert_true(checks, 'formal 2p lobby keeps turn 1 when first player ends and passes to the other',
        passed_to_second.get('turn') == 1 and passed_to_second.get('turn_phase') == 'action' and passed_to_second.get('current_player') != lobby_start_player,
        passed_to_second,
    )
    assert_true(checks, 'first player end does not draw or replace event before the round wraps',
        passed_to_second.get('event_before') == passed_to_second.get('event_after')
        and passed_to_second.get('event_deck_before') == passed_to_second.get('event_deck_after')
        and passed_to_second.get('event_discard_before') == passed_to_second.get('event_discard_after'),
        passed_to_second,
    )
    assert_true(checks, 'formal 2p lobby increments to turn 2 only after the full round ends',
        round_wrap_state.get('turn') == 2 and round_wrap_state.get('turn_phase') == 'action' and round_wrap_state.get('current_player') == lobby_start_player,
        round_wrap_state,
    )
    assert_true(checks, 'new event is drawn only after the full round ends',
        round_wrap_state.get('event_deck_after') == round_wrap_state.get('event_deck_before') - 1
        and round_wrap_state.get('event_discard_after') == round_wrap_state.get('event_discard_before') + 1,
        round_wrap_state,
    )

    # ACTION phase allows the current player (player1) to play a card.
    idx, card_name = first_current_player_action_card(game)
    action_play_result = game.play_card(idx, mode='resource') if idx is not None else {'skipped': True}
    trace.append({
        'step': 'action_phase_card_play',
        'card': card_name,
        'result': action_play_result,
        'turn_phase': str(game.turn_phase),
        'current_player': game.current_player().name,
    })
    assert_true(checks, 'action phase allows current player card play', isinstance(action_play_result, dict) and action_play_result.get('success'), action_play_result)

    # ACTION -> END; the END (purchase) phase blocks action-card play.
    game.advance_turn_phase()
    end_idx, end_card = first_current_player_action_card(game)
    end_play_result = game.play_card(end_idx, mode='action') if end_idx is not None else {'skipped': True}
    trace.append({
        'step': 'end_phase_action_attempt',
        'card': end_card,
        'result': end_play_result,
        'turn_phase': str(game.turn_phase),
        'current_player': game.current_player().name,
    })
    assert_true(checks, 'end (purchase) phase blocks action card play',
        game.turn_phase == TurnPhase.END and isinstance(end_play_result, dict) and end_play_result.get('error') == 'Not in ACTION phase',
        end_play_result)

    # END -> next player's ACTION; still turn 1 and the same round event (no mid-round draw).
    state_before_pass = game.state()
    game.advance_turn_phase()
    state_next = game.state()
    trace.append({
        'step': 'end_passes_to_next_player_action',
        'turn': state_next['turn'],
        'turn_phase': state_next['turn_phase'],
        'current_player': state_next['current_player'],
        'current_event': (state_next.get('current_event') or {}).get('id'),
    })
    assert_true(checks, 'ending turn passes to next player in ACTION without drawing a new event mid-round',
        state_next['turn_phase'] == 'action'
        and state_next['current_player'] == 'player2'
        and state_next['turn'] == 1
        and (state_next.get('current_event') or {}).get('id') == (state_before_pass.get('current_event') or {}).get('id')
        and state_next.get('event_deck_count') == state_before_pass.get('event_deck_count')
        and state_next.get('event_discard_count') == state_before_pass.get('event_discard_count'),
        state_next,
    )

    # The next player is likewise in ACTION and can play a card.
    next_idx, next_card = first_current_player_action_card(game)
    next_play = game.play_card(next_idx, mode='resource') if next_idx is not None else {'skipped': True}
    trace.append({
        'step': 'next_player_action_play',
        'card': next_card,
        'result': next_play,
        'turn_phase': str(game.turn_phase),
        'current_player': game.current_player().name,
    })
    assert_true(checks, 'next player is in ACTION and can play a card', isinstance(next_play, dict) and next_play.get('success'), next_play)

    red_support_game = Game([('red', '紅軍'), ('ben', 'BEN')], market_mode='all_cards')
    red_player = red_support_game.players[0]
    ben_player = red_support_game.players[1]
    red_player.faction_id = 'red_army'
    red_player.base = '北京'
    red_player.organizations = {'北京': 1}
    red_player.hand = [red_support_game._make_support_card('紅軍奧援')]
    red_player.deck.draw_pile = []
    red_player.deck.discard_pile = []
    ben_player.faction_id = 'taiwan_green'
    ben_player.base = '臺北'
    ben_player.organizations = {'臺北': 1}
    red_support_game.current_player_index = 0
    red_support_game.turn_phase = TurnPhase.EVENT
    red_support_action_result = red_support_game.play_card(0, mode='action')
    red_support_state = red_support_game.state()
    trace.append({
        'step': 'red_support_event_phase_action_before_purchase',
        'result': red_support_action_result,
        'turn_phase': red_support_state.get('turn_phase'),
        'pending_choice': red_support_state.get('pending_choice'),
        'hand': red_support_state.get('players', [{}])[0].get('hand'),
    })
    assert_true(checks, 'red army support action can be played in event phase before purchase',
        isinstance(red_support_action_result, dict)
        and red_support_action_result.get('success')
        and red_support_action_result.get('pending_choice')
        and red_support_state.get('turn_phase') == 'event',
        red_support_action_result,
    )

    frontend_source = (BASE / 'static' / 'app.js').read_text(encoding='utf-8')
    frontend_hand_button_guards = {
        'keeps_default_cards_action_phase_guarded': "rawPhase === 'action'" in frontend_source,
        'allows_red_support_event_action': "cardName === '紅軍奧援'" in frontend_source and "mode === 'action'" in frontend_source and "rawPhase === 'event'" in frontend_source,
        'render_uses_per_mode_disabled_attrs': "resourceDisabledAttr" in frontend_source and "actionDisabledAttr" in frontend_source,
        'click_guard_allows_red_support_exception': "isRedSupportPrepAction" in frontend_source,
    }
    trace.append({
        'step': 'frontend_hand_button_red_support_event_exception',
        **frontend_hand_button_guards,
    })
    assert_true(checks, 'frontend enables only red support action button before purchase', all(frontend_hand_button_guards.values()), frontend_hand_button_guards)

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
        '日期：2026-06-01',
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
