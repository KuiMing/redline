from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.main import app, manager
from server.game import TurnPhase


def test_red_army_ability_can_be_triggered_during_event_before_purchase_phase_via_button_flow():
    client = TestClient(app)
    setup = client.post('/test/setup-red-army-abilities-proof').json()
    game_id = setup['game_id']
    player_id = setup['player_id']
    game = manager.get_game(game_id)

    game.turn_phase = TurnPhase.EVENT
    red = game.current_player()
    start_hand_count = len(red.hand)

    with client.websocket_connect(f'/ws/{game_id}/{player_id}') as ws:
        initial_state = ws.receive_json()
        assert initial_state['turn_phase'] == 'event'
        assert initial_state['red_army_action_count'] == 0

        ws.send_json({'action': 'faction_action', 'name': '統戰部'})
        resolved_state = ws.receive_json()

    assert resolved_state['turn_phase'] == 'event'
    assert resolved_state['red_army_action_count'] == 1
    assert resolved_state['last_action_result'] == {'name': '統戰部', 'drawn': 1}
    red_state = next(player for player in resolved_state['players'] if player['id'] == player_id)
    assert len(red_state['hand']) == start_hand_count + 1
    assert game.turn_phase == TurnPhase.EVENT


def test_red_army_ability_button_ui_is_not_auto_modal_and_is_available_before_purchase():
    app_js = (ROOT / 'static' / 'app.js').read_text(encoding='utf-8')
    index_html = (ROOT / 'static' / 'index.html').read_text(encoding='utf-8')

    assert 'id="redArmyAbilityBtn"' in index_html
    assert 'onclick="openRedArmyAbilityModal()"' in index_html
    assert "openRedArmyAbilityModal" in app_js
    assert "紅軍能力不再自動彈出" in app_js
    assert "faction === 'red_army' && isMine && (phase === 'event' || phase === 'action')" in app_js
    assert "rawPhase === 'event' || rawPhase === 'action'" in app_js
