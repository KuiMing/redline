import importlib.util
from pathlib import Path

module_path = Path(__file__).resolve().parents[1] / 'validate_ui_card_flows.py'
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


class ReadyPage:
    def __init__(self):
        self.clicks = []
        self.waits = []
        self.wait_for_function_calls = []

    def click(self, selector):
        self.clicks.append(selector)

    def wait_for_timeout(self, timeout):
        self.waits.append(timeout)

    def wait_for_function(self, script, timeout=None):
        self.wait_for_function_calls.append({'script': script, 'timeout': timeout})


def test_advance_to_action_waits_for_my_turn_and_advances_until_action_phase():
    page = FakePage(last_game_states=[
        {'turn_phase': 'event'},
        {'turn_phase': 'action'},
    ])

    validator.advance_to_action(page)

    assert page.clicks == ['#advanceStepBtn']
    assert page.evaluate_calls == ['window.lastGameState', 'window.lastGameState']
    assert len(page.wait_for_function_calls) == 3
    assert 'state.players.some' in page.wait_for_function_calls[0]['script']
    assert 'advanceStepBtn' in page.wait_for_function_calls[1]['script']
    assert 'state.turn_phase !== prevPhase' in page.wait_for_function_calls[2]['script']
    assert page.wait_for_function_calls[2]['arg'] == 'event'


def test_mark_ready_clicks_button_and_waits():
    page = ReadyPage()

    validator.mark_ready(page)

    assert page.clicks == ['text=我已準備']
    assert page.waits == [1200]


def test_wait_for_confirmed_faction_and_ready_state_use_latest_lobby_state():
    page = ReadyPage()

    validator.wait_for_confirmed_faction(page, 'player-1')
    validator.wait_for_ready_state(page, 'player-1', True)

    assert len(page.wait_for_function_calls) == 2
    assert 'window.latestLobbyState' in page.wait_for_function_calls[0]['script']
    assert 'state.factions' in page.wait_for_function_calls[0]['script']
    assert 'player-1' in page.wait_for_function_calls[0]['script']
    assert 'state.ready' in page.wait_for_function_calls[1]['script']
    assert '=== true' in page.wait_for_function_calls[1]['script']
