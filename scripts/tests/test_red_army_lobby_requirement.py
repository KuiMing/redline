import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server import main


def create_four_player_room(client):
    created = client.post('/create', json={'name': 'Host', 'device_id': 'red-rule-host'}).json()
    game_id = created['game_id']
    player_ids = [created['host_id']]
    for index in range(1, 4):
        joined = client.post('/join', json={
            'game_id': game_id,
            'name': f'Player {index + 1}',
            'device_id': f'red-rule-device-{index}',
        }).json()
        player_ids.append(joined['player_id'])
    return game_id, player_ids


def test_room_without_red_army_cannot_start_even_when_everyone_is_ready():
    client = TestClient(main.app)
    created = client.post('/create', json={'name': 'Host', 'device_id': 'no-red-host'}).json()
    game_id = created['game_id']
    host_id = created['host_id']
    guest = client.post('/join', json={
        'game_id': game_id,
        'name': 'Guest',
        'device_id': 'no-red-guest',
    }).json()
    guest_id = guest['player_id']

    main.lobby_factions[game_id] = {host_id: 'liberals', guest_id: 'hong_kong'}
    main.lobby_ready[game_id] = {host_id: True, guest_id: True}

    result = client.post('/start', json={'game_id': game_id, 'player_id': host_id}).json()

    assert result == {'error': '必須有且只能有一名玩家選擇紅軍，才能啟動行動'}
    assert main.manager.games.get(game_id) is None


def test_last_seat_is_forced_to_choose_red_army_when_room_has_no_red_army():
    client = TestClient(main.app)
    game_id, player_ids = create_four_player_room(client)
    last_player_id = player_ids[-1]
    main.lobby_factions[game_id] = {
        player_ids[0]: 'liberals',
        player_ids[1]: 'hong_kong',
        player_ids[2]: 'taiwan_green',
    }

    lobby_state = client.get(f'/lobby/{game_id}').json()
    rejected = client.post('/choose-faction', json={
        'game_id': game_id,
        'player_id': last_player_id,
        'faction_id': 'mongol',
        'base_name': '烏蘭巴托',
    }).json()
    accepted = client.post('/choose-faction', json={
        'game_id': game_id,
        'player_id': last_player_id,
        'faction_id': 'red_army',
        'base_name': '北京',
    }).json()

    assert lobby_state['required_faction_by_player'] == {last_player_id: 'red_army'}
    assert rejected == {'error': '房間尚無紅軍；最後一個席位只能選擇紅軍'}
    assert accepted['success'] is True
    assert main.lobby_factions[game_id][last_player_id] == 'red_army'
    assert client.get(f'/lobby/{game_id}').json()['required_faction_by_player'] == {}


def test_last_seat_can_choose_another_faction_when_red_army_already_exists():
    client = TestClient(main.app)
    game_id, player_ids = create_four_player_room(client)
    last_player_id = player_ids[-1]
    main.lobby_factions[game_id] = {
        player_ids[0]: 'red_army',
        player_ids[1]: 'hong_kong',
        player_ids[2]: 'taiwan_green',
    }

    lobby_state = client.get(f'/lobby/{game_id}').json()
    accepted = client.post('/choose-faction', json={
        'game_id': game_id,
        'player_id': last_player_id,
        'faction_id': 'mongol',
        'base_name': '烏蘭巴托',
    }).json()

    assert lobby_state['required_faction_by_player'] == {}
    assert accepted['success'] is True
    assert main.lobby_factions[game_id][last_player_id] == 'mongol'
