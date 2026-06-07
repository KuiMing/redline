import json
import random
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.game import Game, TurnPhase, GamePhase

RECORD_DIR = BASE / 'docs' / 'records' / 'misc'
OUT_JSON = RECORD_DIR / 'FULL_GAMEPLAY_2P_VALIDATION.json'
OUT_MD = RECORD_DIR / 'FULL_GAMEPLAY_2P_VALIDATION.md'


def china_towns(game, count=None):
    towns = list(game._towns_for_region_alias('china'))
    return towns if count is None else towns[:count]


def resolve_base_selection(game, trace):
    if game.game_phase == GamePhase.BASE_SELECTION:
        initial_pending = json.loads(json.dumps(game.pending_base_choices, ensure_ascii=False))
        for pid, choice_data in list(game.pending_base_choices.items()):
            labels = choice_data.get('labels', [])
            resolved = choice_data.get('resolved', {})
            chosen = None
            for label in labels:
                for town in resolved.get(label, []):
                    result = game.set_base_choice(pid, town, label=label)
                    if result.get('success'):
                        chosen = {'player_id': pid, 'label': label, 'town': town, 'result': result}
                        break
                if chosen:
                    break
            trace.append({'step': 'base_selection_choice', 'choice': chosen})
        trace.append({
            'step': 'base_selection_resolution',
            'initial_pending': initial_pending,
            'remaining_pending': dict(game.pending_base_choices),
            'game_phase_after_selection': game.game_phase,
        })


def resolve_pending_choice_for_validation(game, trace, step):
    """Pick the first legal option so event/support prompts do not stall the smoke test."""
    choice = game.pending_choice
    if not choice:
        return None
    player_id = choice.get('player_id')
    choice_type = choice.get('type')
    if choice_type == 'multi_card_choice':
        min_count = int(choice.get('min_count', choice.get('count', 0)) or 0)
        index = list(range(min_count))
    else:
        index = 0
    result = game.resolve_pending_choice(player_id, index)
    trace.append({
        'step': step,
        'choice_key': choice.get('choice_key'),
        'choice_type': choice_type,
        'player_id': player_id,
        'index': index,
        'result': result,
        'turn': game.turn,
        'turn_phase': game.turn_phase,
        'current_player': game.current_player().name,
    })
    return result


def advance_to_action_for_validation(game, trace, cycle):
    safety = 0
    while game.turn_phase == TurnPhase.EVENT and safety < 6:
        if game.pending_choice:
            resolve_pending_choice_for_validation(game, trace, f'cycle_{cycle}_resolve_event_choice')
            safety += 1
            continue
        result = game.advance_turn_phase()
        trace.append({
            'step': f'cycle_{cycle}_advance_event_step',
            'result': result,
            'turn': game.turn,
            'turn_phase': game.turn_phase,
            'current_player': game.current_player().name,
            'pending_choice': (game.pending_choice or {}).get('choice_key'),
            'event': (game.current_event or {}).get('name'),
            'event_progress': dict(game.event_progress or {}),
        })
        safety += 1
    return game.turn_phase == TurnPhase.ACTION


def force_deterministic_2p_setup(game):
    anti, red = game.players
    anti.name = 'anti'
    anti.faction_id = 'hong_kong'
    anti.base = '香港城'
    anti.organizations = {'香港城': 1}
    red.name = 'red'
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.EVENT
    return anti, red


def validate_bases(game):
    rows = []
    base_names = []
    for p in game.players:
        rows.append({
            'player': p.name,
            'faction': p.faction_id,
            'base': p.base,
            'orgs': dict(p.organizations),
            'single_base_org': list(p.organizations.keys()) == [p.base] and p.organizations.get(p.base) == 1,
            'base_allowed': game.can_faction_develop_in_town(p.faction_id, p.base),
        })
        base_names.append(p.base)
    return {'rows': rows, 'unique_bases': len(base_names) == len(set(base_names))}


def first_connected_move(game, player):
    if player.moves_left <= 0:
        return None, {'skipped': 'no move points available'}
    for from_town in list(player.organizations.keys()):
        if from_town == player.base and player.organizations.get(from_town, 0) <= 1:
            continue
        town = game.map['towns'].get(from_town, {})
        for mode in ('road', 'rail'):
            for target in list(town.get(mode) or []):
                return {'from': from_town, 'to': target, 'mode': mode}, game.move_organization(from_town, target, mode)
    return None, {'skipped': 'no movable non-anchor organization'}


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(20260510)
    game = Game([('p1', 'anti'), ('p2', 'red')])
    trace = []
    resolve_base_selection(game, trace)
    anti, red = force_deterministic_2p_setup(game)

    base_validation = validate_bases(game)
    trace.append({
        'step': 'init',
        'turn': game.turn,
        'turn_phase': game.turn_phase,
        'game_phase': game.game_phase,
        'current_player': game.current_player().name,
        'base_validation': base_validation,
        'players': [{
            'name': p.name,
            'faction': p.faction_id,
            'base': p.base,
            'orgs': dict(p.organizations),
            'hand': [c.name for c in p.hand],
        } for p in game.players],
    })

    for cycle in range(1, 5):
        trace.append({'step': f'cycle_{cycle}_advance_to_action_before', 'turn': game.turn, 'turn_phase': game.turn_phase, 'current_player': game.current_player().name, 'pending_choice': (game.pending_choice or {}).get('choice_key')})
        reached_action = advance_to_action_for_validation(game, trace, cycle)
        trace.append({'step': f'cycle_{cycle}_advance_to_action_after', 'turn': game.turn, 'turn_phase': game.turn_phase, 'current_player': game.current_player().name, 'pending_choice': (game.pending_choice or {}).get('choice_key'), 'reached_action': reached_action})

        player = game.current_player()
        hand_before = [c.name for c in player.hand]
        play_result = game.play_card(0, mode='action') if player.hand else {'skipped': True}
        hand_after = [c.name for c in player.hand]
        trace.append({
            'step': f'cycle_{cycle}_play_card',
            'player': player.name,
            'faction': player.faction_id,
            'hand_before': hand_before,
            'hand_after': hand_after,
            'result': play_result,
            'resources': dict(player.resources),
            'moves_left': player.moves_left,
        })

        move_detail, move_result = first_connected_move(game, player)
        trace.append({
            'step': f'cycle_{cycle}_move',
            'player': player.name,
            'move_detail': move_detail,
            'result': move_result,
            'orgs_after': dict(player.organizations),
            'moves_left_after': player.moves_left,
        })

        game.advance_turn_phase()
        trace.append({'step': f'cycle_{cycle}_advance_to_end', 'turn': game.turn, 'turn_phase': game.turn_phase, 'current_player': game.current_player().name})

        game.advance_turn_phase()
        trace.append({'step': f'cycle_{cycle}_end_turn', 'turn': game.turn, 'turn_phase': game.turn_phase, 'current_player': game.current_player().name})

    china_towns_sample = china_towns(game, 14)
    anti.organizations = {town: 1 for town in china_towns_sample}
    red.organizations = {'北京': 1}
    trace.append({
        'step': 'before_forced_legal_anti_victory_check',
        'candidate': anti.name,
        'faction': anti.faction_id,
        'org_count': sum(anti.organizations.values()),
        'turn': game.turn,
        'turn_phase': game.turn_phase,
    })

    game._check_victory()
    trace.append({
        'step': 'after_forced_legal_anti_victory_check',
        'game_phase': game.game_phase,
        'winner': game.winner,
        'turn': game.turn,
        'turn_phase': game.turn_phase,
    })

    errors = [item for item in trace if isinstance(item.get('result'), dict) and item['result'].get('error')]
    summary = {
        'total_checks': 4,
        'passed': sum([
            game.game_phase == GamePhase.FINISHED,
            game.winner == anti.name,
            base_validation['unique_bases'] and all(row['single_base_org'] and row['base_allowed'] for row in base_validation['rows']),
            len(errors) == 0,
        ]),
        'failed': 4 - sum([
            game.game_phase == GamePhase.FINISHED,
            game.winner == anti.name,
            base_validation['unique_bases'] and all(row['single_base_org'] and row['base_allowed'] for row in base_validation['rows']),
            len(errors) == 0,
        ]),
        'errors': errors,
    }

    out = {'summary': summary, 'trace': trace, 'final_state': game.state()}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = ['# FULL GAMEPLAY 2P VALIDATION', '', '日期：2026-05-09', '', f'summary: {summary}', '']
    for item in trace:
        lines.append(f"## {item['step']}")
        for k, v in item.items():
            if k == 'step':
                continue
            lines.append(f"- {k}: {v}")
        lines.append('')
    lines.append('## final_state')
    lines.append(f"- turn: {out['final_state']['turn']}")
    lines.append(f"- turn_phase: {out['final_state']['turn_phase']}")
    lines.append(f"- game_phase: {out['final_state']['game_phase']}")
    lines.append(f"- current_player: {out['final_state']['current_player']}")
    lines.append(f"- winner: {out['final_state']['winner']}")
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')

    print(json.dumps({'summary': summary, 'json': str(OUT_JSON), 'md': str(OUT_MD)}, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
