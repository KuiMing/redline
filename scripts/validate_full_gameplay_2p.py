import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.game import Game, TurnPhase, GamePhase
from server.cards import Card


def main():
    game = Game([('p1', 'host'), ('p2', 'guest')])

    trace = []
    trace.append({
        'step': 'init',
        'turn': game.turn,
        'turn_phase': game.turn_phase,
        'current_player': game.current_player().name,
        'players': [{
            'name': p.name,
            'faction': p.faction_id,
            'orgs': dict(p.organizations),
            'hand': [c.name for c in p.hand],
        } for p in game.players]
    })

    # simulate multiple rounds with real phase transitions, card play, move, and end-turns
    for cycle in range(1, 5):
        # EVENT -> ACTION
        trace.append({'step': f'cycle_{cycle}_advance_to_action_before', 'turn': game.turn, 'turn_phase': game.turn_phase, 'current_player': game.current_player().name})
        game.advance_turn_phase()
        trace.append({'step': f'cycle_{cycle}_advance_to_action_after', 'turn': game.turn, 'turn_phase': game.turn_phase, 'current_player': game.current_player().name})

        # play first card if available
        player = game.current_player()
        hand_before = [c.name for c in player.hand]
        play_result = game.play_card(0) if player.hand else {'skipped': True}
        hand_after = [c.name for c in player.hand]
        trace.append({
            'step': f'cycle_{cycle}_play_card',
            'player': player.name,
            'hand_before': hand_before,
            'hand_after': hand_after,
            'result': play_result,
            'resources': dict(player.resources),
            'moves_left': player.moves_left,
        })

        # attempt one legal move if possible
        move_result = {'skipped': True}
        for from_town in list(player.organizations.keys()):
            town = game.map['towns'].get(from_town, {})
            road = (town.get('road') or [])
            rail = (town.get('rail') or [])
            if road:
                move_result = game.move_organization(from_town, road[0], 'road')
                break
            if rail:
                move_result = game.move_organization(from_town, rail[0], 'rail')
                break
        trace.append({
            'step': f'cycle_{cycle}_move',
            'player': player.name,
            'result': move_result,
            'orgs_after': dict(player.organizations),
            'moves_left_after': player.moves_left,
        })

        # ACTION -> END
        game.advance_turn_phase()
        trace.append({'step': f'cycle_{cycle}_advance_to_end', 'turn': game.turn, 'turn_phase': game.turn_phase, 'current_player': game.current_player().name})

        # END -> next turn / next player
        game.advance_turn_phase()
        trace.append({'step': f'cycle_{cycle}_end_turn', 'turn': game.turn, 'turn_phase': game.turn_phase, 'current_player': game.current_player().name})

    # force a deterministic victory path for end-to-end verification
    winner_player = game.players[0]
    winner_player.organizations = {f'城{i}': 1 for i in range(14)}
    # ensure those towns count for count_only factions by reusing china towns when possible
    china_towns = list(game.board_regions.get('china', {}).get('towns', []))[:14]
    if len(china_towns) == 14:
        winner_player.organizations = {town: 1 for town in china_towns}

    trace.append({
        'step': 'before_forced_victory_check',
        'candidate': winner_player.name,
        'faction': winner_player.faction_id,
        'org_count': sum(winner_player.organizations.values()),
        'turn': game.turn,
        'turn_phase': game.turn_phase,
    })

    game._check_victory()

    trace.append({
        'step': 'after_forced_victory_check',
        'game_phase': game.game_phase,
        'winner': game.winner,
        'turn': game.turn,
        'turn_phase': game.turn_phase,
    })

    out = {
        'trace': trace,
        'final_state': game.state(),
    }

    (BASE / 'FULL_GAMEPLAY_2P_VALIDATION.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = ['# FULL GAMEPLAY 2P VALIDATION', '', '日期：2026-05-03', '']
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
    (BASE / 'FULL_GAMEPLAY_2P_VALIDATION.md').write_text('\n'.join(lines), encoding='utf-8')
    print(BASE / 'FULL_GAMEPLAY_2P_VALIDATION.json')
    print(BASE / 'FULL_GAMEPLAY_2P_VALIDATION.md')

if __name__ == '__main__':
    main()
