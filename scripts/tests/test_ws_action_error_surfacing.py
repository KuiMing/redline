"""Regression coverage for server/main.py's `_ws_action_error_message()`.

Bug: a Red Army ability that is legitimately unavailable right now (e.g. 國安部
with no valid dissolve target) makes `Game._activated_faction_action()` return
`{'success': False, 'result': {..., 'message': '...'}}` rather than an
`'error'` string. The WS dispatcher in `websocket_endpoint()` only ever
checked for `'error'`, so this shape was silently broadcast as if the action
had succeeded and the server's own explanatory message never reached the
client (browser or MCP). Caught live playing a real game over MCP on
2026-09-25.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.main import _ws_action_error_message, app, manager


def test_unavailable_ability_result_is_treated_as_an_error():
    assert _ws_action_error_message(
        {"success": False, "result": {"name": "國安部", "unavailable": True, "message": "沒有可以瓦解的組織"}}
    ) == "沒有可以瓦解的組織"


def test_unavailable_ability_result_without_message_still_reports_an_error():
    assert _ws_action_error_message({"success": False, "result": {"name": "國安部"}}) == "Action unavailable"


def test_explicit_error_string_still_takes_priority():
    assert _ws_action_error_message({"error": "boom", "success": False}) == "boom"


def test_successful_result_has_no_error():
    assert _ws_action_error_message({"success": True, "result": {"name": "統戰部", "drawn": 1}}) is None
    assert _ws_action_error_message(None) is None
    assert _ws_action_error_message("not a dict") is None


def test_state_security_with_no_target_surfaces_as_a_ws_error_not_a_silent_success():
    client = TestClient(app)
    setup = client.post("/test/setup-red-army-abilities-proof", json={"empty_actions": True}).json()
    game_id = setup["game_id"]
    player_id = setup["player_id"]
    game = manager.get_game(game_id)
    start_action_count = game._red_army_action_count()

    with client.websocket_connect(f"/ws/{game_id}/{player_id}") as ws:
        ws.receive_json()  # initial state
        ws.send_json({"action": "faction_action", "name": "國安部"})
        resolved_state = ws.receive_json()

    assert resolved_state.get("error")
    assert "沒有可以瓦解的組織" in resolved_state["error"]
    assert game._red_army_action_count() == start_action_count
