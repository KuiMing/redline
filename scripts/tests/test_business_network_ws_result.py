from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.main import app, manager
from server.cards import Card


def test_business_network_resolve_choice_websocket_broadcasts_last_action_result_and_effect():
    client = TestClient(app)
    setup = client.post(
        '/test/setup-hand-preview',
        json={
            'faction_id': 'tibet_dehradun',
            'base': '德拉敦',
            'resources': {'money': 0, 'propaganda': 0},
            'hand_names': ['企業人脈'],
        },
    ).json()

    game_id = setup['game_id']
    player_id = setup['player_id']
    game = manager.get_game(game_id)
    game.purchase_area = game._static_purchase_cards() + [
        Card('合作談判', 'command', {'propaganda': 1}),
        Card('交通經驗乙', 'transport', {'money': 2}),
        Card('模仿戰術', 'command', {'propaganda': 2}),
    ]

    with client.websocket_connect(f'/ws/{game_id}/{player_id}') as ws:
        ws.receive_json()
        ws.send_json({'action': 'play_card', 'index': 0, 'mode': 'action'})
        pending_state = ws.receive_json()
        assert pending_state['pending_choice']['choice_key'] == 'use_purchase_area_card'
        choice_index = next(
            index
            for index, entry in enumerate(pending_state['pending_choice']['cards'])
            if entry.get('name') == '交通經驗乙'
        )

        ws.send_json({'action': 'resolve_choice', 'index': choice_index})
        resolved_state = ws.receive_json()

    me = next(player for player in resolved_state['players'] if player['id'] == player_id)
    assert me['moves_left'] == 4
    assert resolved_state.get('last_action_result') == {
        'success': True,
        'chosen_card': '交通經驗乙',
        'purchase_index': 7,
        'zone_label': '購買區槽位 8',
    }
    assert resolved_state['pending_choice'] is None
