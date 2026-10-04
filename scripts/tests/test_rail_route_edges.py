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


def test_map_js_highlights_projected_rail_edges_order_independently():
    from pathlib import Path
    logic = (Path(__file__).resolve().parents[2] / "static" / "leaflet_game_map_logic.js").read_text(encoding="utf-8")
    assert "edges: Array.isArray(entry.edges)" in logic
    assert "projectedRailEdges.has([route.source, route.target].sort().join" in logic
    assert "option.edges.forEach(([a, b]) => projectedRailEdges.add([a, b].sort().join" in logic


# ---- real execution of the map's rail highlighting against server-built state ----

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _lit_rail(game, viewer, town):
    if shutil.which('node') is None:
        pytest.skip('node not available')
    state = game.state(viewer.id)
    rails = sorted({tuple(sorted((a, b))) for a, v in game.map['towns'].items() for b in v.get('rail', [])})
    payload = {'state': state, 'viewer': viewer.id, 'town': town, 'rail': rails}
    out = subprocess.run(['node', str(_ROOT / 'scripts/tests/js/rail_highlight_harness.js')], input=json.dumps(payload),
                         capture_output=True, text=True, cwd=_ROOT, check=True)
    return {tuple(e) for e in json.loads(out.stdout)}


def _pair(a, b):
    return tuple(sorted((a, b)))


def test_map_highlights_all_three_segments_fukuoka_to_sendai():
    game, a = _game_at('福岡')
    lit = _lit_rail(game, a, '福岡')
    assert {_pair('福岡', '大阪'), _pair('大阪', '東京'), _pair('東京', '仙臺')} <= lit


def test_enemy_blocked_sole_rail_lights_nothing_for_actionable_origin():
    game, a = _game_at('福岡')
    game.players[1].organizations['大阪'] = 1  # enemy blocks the only rail out of 福岡
    assert game._legal_organization_moves()['福岡']['rail'] == []  # road moves remain, rail is empty
    assert _lit_rail(game, a, '福岡') == set()


def test_zero_moves_left_lights_no_rail():
    game, a = _game_at('福岡')
    a.moves_left = 0
    assert '福岡' not in game._legal_organization_moves()
    assert _lit_rail(game, a, '福岡') == set()


def test_immovable_origin_lights_no_rail():
    game, a = _game_at('福岡')
    game.players[1].organizations['大阪'] = 1
    # 香港城 is the base anchor; whatever the server projects for it, the map lights exactly that
    projected = game._legal_organization_moves().get('香港城', {}).get('rail', [])
    expected = {_pair(x, y) for e in projected for x, y in e['edges']}
    assert _lit_rail(game, a, '香港城') == expected


def test_insufficient_moves_for_wall_crossing_lights_nothing():
    game, a = _game_at('福岡')
    a.moves_left = 1  # wall crossing costs 2
    a.organizations['北京'] = 1
    game.players[1].organizations.pop('北京', None)
    moves = game._legal_organization_moves().get('北京', {})
    expected = {_pair(x, y) for e in moves.get('rail', []) for x, y in e['edges']}
    assert _lit_rail(game, a, '北京') == expected  # exactly the server projection, never direct adjacency


def test_inspection_only_town_keeps_direct_adjacent_rail():
    game, a = _game_at('福岡')
    game.players[1].organizations['東京'] = 1
    lit = _lit_rail(game, a, '東京')  # enemy-owned town: not actionable
    direct = {_pair('東京', n) for n in game.map['towns']['東京']['rail']}
    assert lit == direct and lit


def test_non_current_viewer_gets_inspection_view_not_actionable_projection():
    game, a = _game_at('福岡')
    b = game.players[1]
    lit = _lit_rail(game, b, '福岡')  # b is not the acting player and has no org there
    assert lit == {_pair('福岡', n) for n in game.map['towns']['福岡']['rail']}
