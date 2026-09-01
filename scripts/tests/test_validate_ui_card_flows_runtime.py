import importlib.util
from pathlib import Path

module_path = Path(__file__).resolve().parents[1] / 'validate' / 'validate_ui_card_flows.py'
spec = importlib.util.spec_from_file_location('card_ui_validator_runtime', module_path)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)


class FakePage:
    def __init__(self, last_game_states=None):
        self.clicks = []
        self.waits = []
        self.wait_for_function_calls = []
        self.evaluate_calls = []
        self.last_game_states = list(last_game_states or [])

    def click(self, selector):
        self.clicks.append(selector)

    def wait_for_timeout(self, timeout):
        self.waits.append(timeout)

    def wait_for_function(self, script, arg=None, timeout=None):
        self.wait_for_function_calls.append({
            'script': script,
            'arg': arg,
            'timeout': timeout,
        })

    def evaluate(self, script):
        self.evaluate_calls.append(script)
        if script == 'window.lastGameState':
            if self.last_game_states:
                return self.last_game_states.pop(0)
            return {}
        return None


class _FakeLocator:
    def __init__(self, page):
        self.page = page

    def input_value(self):
        return self.page.room_id


class ReadyPage:
    def __init__(self, room_id='room-123', lobby_state=None):
        self.clicks = []
        self.waits = []
        self.wait_for_function_calls = []
        self.evaluate_calls = []
        self.room_id = room_id
        self.lobby_state = lobby_state or {}

    def click(self, selector):
        self.clicks.append(selector)

    def wait_for_timeout(self, timeout):
        self.waits.append(timeout)

    def wait_for_function(self, script, timeout=None):
        self.wait_for_function_calls.append({'script': script, 'timeout': timeout})

    def locator(self, selector):
        return _FakeLocator(self)

    def evaluate(self, script):
        self.evaluate_calls.append(script)
        if 'refreshLobbyState' in script:
            return None
        if f'/lobby/{self.room_id}' in script:
            return self.lobby_state
        return None


def test_advance_to_action_waits_for_my_turn_and_advances_until_action_phase():
    page = FakePage(last_game_states=[
        {'turn_phase': 'event'},
        {'turn_phase': 'action'},
    ])

    validator.advance_to_action(page)

    assert page.clicks == ['#advanceStepBtn']
    assert page.evaluate_calls == ['window.lastGameState', 'window.lastGameState']
    # advance_to_action() calls wait_for_my_turn() + a button-enabled check up front,
    # then (since the first observed phase is still 'event') clicks, waits for the
    # phase to change, and repeats wait_for_my_turn()/the button check once more
    # before the loop observes 'action' and returns — 5 wait_for_function calls total.
    assert len(page.wait_for_function_calls) == 5
    assert 'state.players.some' in page.wait_for_function_calls[0]['script']
    assert 'advanceStepBtn' in page.wait_for_function_calls[1]['script']
    assert 'state.turn_phase !== prevPhase' in page.wait_for_function_calls[2]['script']
    assert page.wait_for_function_calls[2]['arg'] == 'event'
    assert 'state.players.some' in page.wait_for_function_calls[3]['script']
    assert 'advanceStepBtn' in page.wait_for_function_calls[4]['script']


def test_mark_ready_clicks_button_and_waits():
    page = ReadyPage()

    validator.mark_ready(page)

    assert page.clicks == ['text=我已準備']
    assert page.waits == [1200]


def test_wait_for_confirmed_faction_and_ready_state_use_latest_lobby_state():
    lobby_state = {
        'factions': {'player-1': 'taiwan_green'},
        'bases': {'player-1': '臺北'},
        'ready': {'player-1': True},
    }
    page = ReadyPage(room_id='room-123', lobby_state=lobby_state)

    validator.wait_for_confirmed_faction(page, 'player-1')
    validator.wait_for_ready_state(page, 'player-1', True)

    # Both resolve on the very first REST poll (lobby_state already satisfies the
    # target condition), so no wait_for_timeout backoff is ever hit.
    assert page.waits == []
    lobby_fetch_calls = [c for c in page.evaluate_calls if '/lobby/room-123' in c]
    assert len(lobby_fetch_calls) == 2
    refresh_calls = [c for c in page.evaluate_calls if 'refreshLobbyState' in c]
    assert len(refresh_calls) == 2
