import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game

MAP_PATH = ROOT / 'data' / 'map.json'
GEO_PATH = ROOT / 'data' / 'map_geo_coordinates.v1.json'
STATIC_MAP_FILES = [
    ROOT / 'static' / 'leaflet_game_map_logic.js',
    ROOT / 'static' / 'leaflet_embed_logic.js',
    ROOT / 'static' / 'leaflet_full_map.html',
]


def test_leaflet_maps_do_not_embed_topology_or_geo_snapshots():
    for path in STATIC_MAP_FILES:
        text = path.read_text(encoding='utf-8')
        assert 'const MAP_DATA =' not in text, path
        assert 'const GEO_COORDS =' not in text, path
    loader = (ROOT / 'static' / 'map_data_loader.js').read_text(encoding='utf-8')
    assert "fetchJson('/map-data')" in loader
    assert "fetchJson('/map-geo-coordinates')" in loader


def test_map_topology_has_only_existing_bidirectional_edges():
    data = json.loads(MAP_PATH.read_text(encoding='utf-8'))
    towns = data['towns']
    failures = []
    for source, entry in towns.items():
        for mode in ('road', 'rail'):
            for target in entry.get(mode, []):
                if target not in towns:
                    failures.append(f'{source}.{mode}->{target}: target missing')
                elif source not in towns[target].get(mode, []):
                    failures.append(f'{source}.{mode}->{target}: reverse edge missing')
    assert failures == []

    expected_visual_topology = {
        'road': (185, '5101788c6717ae8c80d810d8be04c53e1343bf0b40020f3e9f330a1980cc489c'),
        'rail': (286, 'bf412de9e39568b38edfa211d37deb21ad5e8925b5aae29c25eac38c8116d9b1'),
    }
    for mode, expected in expected_visual_topology.items():
        edges = sorted({
            '::'.join(sorted((source, target)))
            for source, entry in towns.items()
            for target in entry.get(mode, [])
        })
        digest = hashlib.sha256('\n'.join(edges).encode()).hexdigest()
        assert (len(edges), digest) == expected


def test_geo_coordinates_cover_exactly_the_canonical_town_set():
    map_data = json.loads(MAP_PATH.read_text(encoding='utf-8'))
    geo = json.loads(GEO_PATH.read_text(encoding='utf-8'))
    assert set(geo) == set(map_data['towns'])
    assert all(isinstance(coords, list) and len(coords) == 2 for coords in geo.values())


def test_movement_rule_schema_distinguishes_range_from_move_cost():
    data = json.loads(MAP_PATH.read_text(encoding='utf-8'))
    assert data['movement_rules'] == {
        'road_range': 1,
        'rail_range': 3,
        'move_cost': 1,
        'wall_crossing_range': 1,
        'wall_crossing_cost': 2,
    }


def test_reported_guangzhou_and_kinmen_build_routes_are_reachable_in_one_step():
    game = Game([('red_army', 'Red'), ('taiwan_green', 'Taiwan')])
    red, taiwan = game.players
    red.faction_id = 'red_army'
    taiwan.faction_id = 'taiwan_green'
    taiwan.organizations = {}

    matrix = [
        (red, '桂林', '廣州'),
        (red, '南寧', '廣州'),
        (red, '廈門', '金門'),
        (taiwan, '廈門', '金門'),
    ]
    for player, origin, target in matrix:
        red.organizations = {}
        taiwan.organizations = {}
        player.organizations = {origin: 1}
        assert game.can_faction_develop_in_town(player.faction_id, target)
        assert target in game._towns_within_steps([origin], 1)
        assert target in [entry['town'] for entry in game._card_build_town_choices(player, {'range': 1})]
