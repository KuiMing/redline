import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server import main


def test_resume_restores_existing_player_identity_and_rejects_wrong_device():
    client = TestClient(main.app)
    created = client.post('/create', json={'name': 'Ben', 'device_id': 'device-a'}).json()
    game_id = created['game_id']
    player_id = created['host_id']
    token = created['resume_token']

    resumed = client.post('/resume', json={
        'game_id': game_id,
        'player_id': player_id,
        'device_id': 'device-a',
        'resume_token': token,
    }).json()
    assert resumed['success'] is True
    assert resumed['player_id'] == player_id
    assert resumed['name'] == 'Ben'
    assert resumed['started'] is False

    rejected = client.post('/resume', json={
        'game_id': game_id,
        'player_id': player_id,
        'device_id': 'device-b',
        'resume_token': 'wrong-token',
    }).json()
    assert rejected == {'error': 'Resume authentication failed'}


def test_join_with_saved_credentials_reuses_seat_without_resetting_lobby_choices():
    client = TestClient(main.app)
    created = client.post('/create', json={'name': 'Host', 'device_id': 'host-device'}).json()
    game_id = created['game_id']
    joined = client.post('/join', json={
        'game_id': game_id,
        'name': 'Alice',
        'device_id': 'alice-device',
    }).json()
    player_id = joined['player_id']

    main.lobby_factions[game_id][player_id] = 'liberals'
    main.lobby_bases[game_id][player_id] = '臺北'
    main.lobby_ready[game_id][player_id] = True
    before_count = len(main.lobby[game_id])

    resumed = client.post('/join', json={
        'game_id': game_id,
        'name': 'Alice',
        'player_id': player_id,
        'device_id': 'alice-device',
        'resume_token': joined['resume_token'],
    }).json()

    assert resumed['resumed'] is True
    assert resumed['player_id'] == player_id
    assert len(main.lobby[game_id]) == before_count
    assert main.lobby_factions[game_id][player_id] == 'liberals'
    assert main.lobby_bases[game_id][player_id] == '臺北'
    assert main.lobby_ready[game_id][player_id] is True


def test_resume_reports_started_game_without_rebuilding_player_state():
    client = TestClient(main.app)
    created = client.post('/create', json={'name': 'Host', 'device_id': 'host-started-device'}).json()
    game_id = created['game_id']
    host_id = created['host_id']
    joined = client.post('/join', json={
        'game_id': game_id,
        'name': 'Guest',
        'device_id': 'guest-started-device',
    }).json()
    guest_id = joined['player_id']

    main.lobby_factions[game_id] = {host_id: 'red_army', guest_id: 'liberals'}
    main.lobby_bases[game_id] = {host_id: '北京', guest_id: '臺北'}
    main.lobby_ready[game_id] = {host_id: True, guest_id: True}
    started = client.post('/start', json={'game_id': game_id, 'player_id': host_id}).json()
    assert started['success'] is True

    game = main.manager.games[game_id]
    guest = next(player for player in game.players if player.id == guest_id)
    guest.resources = {'money': 7, 'propaganda': 4}

    resumed = client.post('/resume', json={
        'game_id': game_id,
        'player_id': guest_id,
        'device_id': 'guest-started-device',
        'resume_token': joined['resume_token'],
    }).json()
    assert resumed['started'] is True
    assert resumed['faction_id'] == 'liberals'
    assert resumed['base'] == '臺北'
    assert next(player for player in game.players if player.id == guest_id).resources == {
        'money': 7,
        'propaganda': 4,
    }
