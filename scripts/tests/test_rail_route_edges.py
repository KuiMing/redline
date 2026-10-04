"""Rail multi-hop movement projects the full authoritative edge chain."""

from server.game import Game
from server.game_build_eligibility_rules import rail_reachable_within_three, rail_route_edges


def _game_at(town):
    game = Game([('p1', 'a'), ('p2', 'b')])
    a, b = game.players
    a.faction_id = 'hong_kong'
    a.base = '香港城'
    a.organizations = {'香港城': 1, town: 1}
    b.faction_id = 'red_army'
    b.base = '北京'
    b.organizations = {'北京': 1}
    game.current_player_index = 0
    a.moves_left = 5
    return game, a


def _edges(game, a, src, dst):
    return rail_route_edges(game.map, game.towns_by_ruler, game.faction_by_id, game.players, a, src, dst)


def _norm(edges):
    return {frozenset(e) for e in edges}


def test_fukuoka_to_sendai_projects_all_three_segments():
    game, a = _game_at('福岡')
    assert _edges(game, a, '福岡', '仙臺') == [['福岡', '大阪'], ['大阪', '東京'], ['東京', '仙臺']]
    moves = game._legal_organization_moves()['福岡']['rail']
    sendai = next(m for m in moves if m['town'] == '仙臺')
    assert _norm(sendai['edges']) == {frozenset(p) for p in [('福岡', '大阪'), ('大阪', '東京'), ('東京', '仙臺')]}
    # state projection carries the same data
    state = game.state(a.id)
    assert state['map']['legal_organization_moves']['福岡']['rail'] == moves


def test_every_projected_rail_destination_has_edges_matching_authority():
    game, a = _game_at('福岡')
    for entry in game._legal_organization_moves()['福岡']['rail']:
        assert entry['edges']
        assert rail_reachable_within_three(game.map, game.towns_by_ruler, game.faction_by_id, game.players, a, '福岡', entry['town'])
        # chain is contiguous from origin to destination, within range
        assert entry['edges'][0][0] == '福岡' and entry['edges'][-1][1] == entry['town']
        assert len(entry['edges']) <= 3


def test_out_of_range_has_no_edges():
    game, a = _game_at('福岡')
    # 札幌 is 4 rail hops from 福岡
    assert _edges(game, a, '福岡', '札幌') == []
    towns = {m['town'] for m in game._legal_organization_moves()['福岡']['rail']}
    assert '札幌' not in towns


def test_blocked_intermediate_town_yields_no_route():
    game, a = _game_at('福岡')
    game.players[1].organizations['東京'] = 1  # enemy org blocks the middle
    assert _edges(game, a, '福岡', '仙臺') == []
    towns = {m['town'] for m in game._legal_organization_moves().get('福岡', {}).get('rail', [])}
    assert '仙臺' not in towns


def test_edges_only_include_shortest_paths_for_diamond():
    game, a = _game_at('福岡')
    game.map = {**game.map, 'towns': {k: dict(v) for k, v in game.map['towns'].items()}}
    t = game.map['towns']
    for n in ('X', 'Y', 'Z', 'W'):
        t[n] = {'rail': [], 'road': []}
    t['X']['rail'] = ['Y', 'Z']; t['Y']['rail'] = ['X', 'W']; t['Z']['rail'] = ['X', 'W']; t['W']['rail'] = ['Y', 'Z']
    edges = _edges(game, a, 'X', 'W')
    assert _norm(edges) == {frozenset(p) for p in [('X', 'Y'), ('X', 'Z'), ('Y', 'W'), ('Z', 'W')]}
    # a longer detour inside range must not be added for a nearer destination
    t['W']['rail'].append('V'); t['V'] = {'rail': ['W', 'X'], 'road': []}; t['X']['rail'].append('V')
    assert _norm(_edges(game, a, 'X', 'Y')) == {frozenset(('X', 'Y'))}


# ---- real execution of the map's route highlighting against server-built state ----

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _lit(game, viewer, town, preview=None, pending=None):
    """Run the real refreshRouteHighlights() in node; return (lit rail, lit road) edge sets."""
    if shutil.which('node') is None:
        pytest.skip('node not available')
    towns = game.map['towns']
    edges = lambda kind: sorted({tuple(sorted((a, b))) for a, v in towns.items() for b in v.get(kind, [])})
    payload = {'state': game.state(viewer.id), 'viewer': viewer.id, 'town': town,
               'rail': edges('rail'), 'road': edges('road'), 'preview': preview, 'pending': pending}
    out = subprocess.run(['node', str(_ROOT / 'scripts/tests/js/rail_highlight_harness.js')], input=json.dumps(payload),
                         capture_output=True, text=True, cwd=_ROOT, check=True)
    data = json.loads(out.stdout)
    return {tuple(e) for e in data['rail']}, {tuple(e) for e in data['road']}


def _pair(a, b):
    return tuple(sorted((a, b)))


def _direct(game, town, kind):
    return {_pair(town, n) for n in game.map['towns'][town].get(kind, [])}


def _target(game, town, to, mode='rail'):
    return {'to': to, 'mode': mode}


@pytest.mark.parametrize('town', ['廣州', '格爾木', '福岡', '東京', '大阪'])
def test_selecting_own_org_town_lights_only_direct_roads_and_rails(town):
    game, a = _game_at(town)
    rail, road = _lit(game, a, town)
    assert rail == _direct(game, town, 'rail')
    assert road == _direct(game, town, 'road')
    # no remote segment between two other towns is lit
    assert all(town in e for e in rail | road)


def test_actionable_origin_with_rails_never_lights_union_of_destinations():
    game, a = _game_at('廣州')
    rail, _ = _lit(game, a, '廣州')
    union = {_pair(x, y) for e in game._legal_organization_moves()['廣州']['rail'] for x, y in e['edges']}
    assert rail == _direct(game, '廣州', 'rail')
    assert union - rail  # multi-hop remote segments exist in the union but stay dark


@pytest.mark.parametrize('kw', ['preview', 'pending'])
def test_specific_rail_destination_lights_full_path_only(kw):
    game, a = _game_at('福岡')
    tgt = {'to': '仙臺', 'mode': 'rail'}
    if kw == 'pending':
        tgt = {'from': '福岡', **tgt, 'cost': 1}
    rail, road = _lit(game, a, '福岡', **{kw: tgt})
    assert rail == {_pair('福岡', '大阪'), _pair('大阪', '東京'), _pair('東京', '仙臺')}
    assert road == set()


def test_cancelling_destination_restores_direct_adjacency():
    game, a = _game_at('福岡')
    rail, road = _lit(game, a, '福岡')
    assert rail == _direct(game, '福岡', 'rail') and road == _direct(game, '福岡', 'road')


def test_road_mode_target_keeps_direct_adjacency():
    game, a = _game_at('福岡')
    rail, road = _lit(game, a, '福岡', preview={'to': '仙臺', 'mode': 'road'})
    assert rail == _direct(game, '福岡', 'rail')


def test_target_not_in_server_projection_is_not_highlighted_as_route():
    game, a = _game_at('福岡')
    # 札幌 is out of range: not a legal destination, so the display must not invent a path
    rail, _ = _lit(game, a, '福岡', preview={'to': '札幌', 'mode': 'rail'})
    assert rail == _direct(game, '福岡', 'rail')


def test_enemy_blocked_destination_not_projected_and_not_clickable():
    game, a = _game_at('福岡')
    game.players[1].organizations['東京'] = 1
    towns = {m['town'] for m in game._legal_organization_moves()['福岡']['rail']}
    assert '仙臺' not in towns
    rail, _ = _lit(game, a, '福岡', preview={'to': '仙臺', 'mode': 'rail'})
    assert rail == _direct(game, '福岡', 'rail')  # adjacency only, no full path


def test_zero_moves_left_has_no_legal_targets_but_shows_adjacency():
    game, a = _game_at('福岡')
    a.moves_left = 0
    assert '福岡' not in game._legal_organization_moves()
    rail, _ = _lit(game, a, '福岡', preview={'to': '仙臺', 'mode': 'rail'})
    assert rail == _direct(game, '福岡', 'rail')


def test_immovable_base_projects_no_rail_destination_path():
    game, a = _game_at('福岡')
    projected = {m['town'] for m in game._legal_organization_moves().get('香港城', {}).get('rail', [])}
    rail, _ = _lit(game, a, '香港城', preview={'to': '福岡', 'mode': 'rail'})
    if '福岡' not in projected:
        assert rail == _direct(game, '香港城', 'rail')


def test_wall_crossing_with_insufficient_moves_projects_no_far_path():
    game, a = _game_at('福岡')
    a.moves_left = 1
    a.organizations['北京'] = 1
    game.players[1].organizations.pop('北京', None)
    projected = game._legal_organization_moves().get('北京', {}).get('rail', [])
    far = next((e for e in projected if len(e['edges']) > 1), None)
    assert far is None or far['cost'] <= a.moves_left


def test_inspection_only_town_shows_direct_adjacency_even_with_target():
    game, a = _game_at('福岡')
    game.players[1].organizations['東京'] = 1
    rail, road = _lit(game, a, '東京', preview={'to': '仙臺', 'mode': 'rail'})
    assert rail == _direct(game, '東京', 'rail') and road == _direct(game, '東京', 'road')


def test_non_current_viewer_gets_inspection_view():
    game, a = _game_at('福岡')
    rail, _ = _lit(game, game.players[1], '福岡', preview={'to': '仙臺', 'mode': 'rail'})
    assert rail == _direct(game, '福岡', 'rail')


def test_route_key_order_independent():
    game, a = _game_at('福岡')
    state = game.state(a.id)
    for e in state['map']['legal_organization_moves']['福岡']['rail']:
        if e['town'] == '仙臺':
            e['edges'] = [list(reversed(x)) for x in e['edges']]
    # reversed edge orientation still lights the same undirected segments
    game.state = lambda _id, s=state: s
    rail, _ = _lit(game, a, '福岡', preview={'to': '仙臺', 'mode': 'rail'})
    assert rail == {_pair('福岡', '大阪'), _pair('大阪', '東京'), _pair('東京', '仙臺')}


def test_sources_never_unions_remote_edges():
    from pathlib import Path as P
    logic = (P(__file__).resolve().parents[2] / 'static' / 'leaflet_game_map_logic.js').read_text(encoding='utf-8')
    assert 'projectedRailEdges' not in logic
