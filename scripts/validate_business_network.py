import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.main import app, manager
from server.cards import Card


def main():
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

    static_cards = game._static_purchase_cards()
    game.purchase_area = static_cards + [
        Card('合作談判', 'command', {'propaganda': 1}),
        Card('交通經驗乙', 'transport', {'money': 2}),
        Card('模仿戰術', 'command', {'propaganda': 2}),
        Card('資本家', 'money', {'money': 3}),
        Card('填充D', 'command', {}),
    ]

    result = {
        'game_id': game_id,
        'player_id': player_id,
        'initial_purchase_area': [getattr(c, 'name', str(c)) for c in game.purchase_area],
    }

    with client.websocket_connect(f'/ws/{game_id}/{player_id}') as ws:
        initial_state = ws.receive_json()
        result['initial_state_hand'] = initial_state['players'][0]['hand']

        ws.send_json({'action': 'play_card', 'index': 0, 'mode': 'action'})
        pending_state = ws.receive_json()
        result['pending_choice'] = pending_state.get('pending_choice')
        result['hand_after_play'] = pending_state['players'][0]['hand']
        result['action_log_after_play'] = pending_state['action_log'][-3:]

        ws.send_json({'action': 'resolve_choice', 'index': 2})
        resolved_state = ws.receive_json()
        result['resolved_hand'] = resolved_state['players'][0]['hand']
        result['resolved_pending_choice'] = resolved_state.get('pending_choice')
        result['resolved_action_log'] = resolved_state['action_log'][-5:]
        result['purchase_area_after_resolve'] = resolved_state['purchase_area']

    out_path = Path('docs/records/card-ui/business-network-validation.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
