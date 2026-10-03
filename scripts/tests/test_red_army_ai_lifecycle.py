"""TDD coverage for the AI Red Army wake-up hook
(`server/red_army_ai_runtime.maybe_run_red_army_turn`) and its wiring into
`server/main.py`'s `broadcast_game_state()` — the server-side event that
drives the already-committed `red_army_policy` engine, instead of any
client-side poll/interval.

Covers (see the top-level feature report for the full design):
- Red Army's turn is handled automatically once state shows it's
  authoritatively Red Army's turn.
- An AI-owned pending_choice is correctly continued.
- A human's pending choice/reaction window stops the AI; a later state
  update (the human resolving it) correctly wakes it again.
- The AI stops cleanly at game-over (no error, no further action).
- Duplicate-runner prevention: a reentrant wake-up for the same game_id
  while the first run is still in flight is a no-op.
- An injected/simulated runner crash is isolated — it never propagates,
  and the game/room is left in a comprehensible (not silently hung)
  status rather than crashing the caller.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game
from server.game_models import GamePhase
from server.main import broadcast_game_state, manager
from server.red_army_ai_runtime import _RUNNING, maybe_run_red_army_turn
import server.red_army_ai_runtime as red_army_ai_runtime


class _FakeSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, payload):
        self.sent.append(payload)


def _new_ai_red_vs_taiwan_game():
    """Same fixture shape as test_red_army_policy_state_machine.py's
    _new_red_vs_taiwan_game(), but with the AI integration flag set the way
    server/lobby_routes.py's start_game() sets it for a real AI-enabled
    room."""
    game = Game([('p1', 'red'), ('p2', 'other')])
    red, other = game.players
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    other.faction_id = 'taiwan_green'
    other.base = '臺北'
    other.organizations = {'天津': 1}
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.pending_choice = None
    game.ai_red_army_player_id = red.id
    game.ai_red_army_status = {"state": "idle"}
    return game, red, other


@pytest.fixture(autouse=True)
def _clean_running_set(monkeypatch):
    _RUNNING.clear()
    red_army_ai_runtime._DRIVING.clear()
    red_army_ai_runtime._LAST_SUCCESS.clear()
    # Never really wait between AI actions in tests.
    monkeypatch.setattr(red_army_ai_runtime, "AI_ACTION_DELAY_SECONDS", 0.0)
    yield
    _RUNNING.clear()
    red_army_ai_runtime._DRIVING.clear()
    red_army_ai_runtime._LAST_SUCCESS.clear()


# ---------- Red Army's turn is handled automatically ----------

def test_ai_acts_automatically_when_it_is_authoritatively_red_armys_turn():
    game, red, other = _new_ai_red_vs_taiwan_game()
    assert game.current_player().id == red.id  # sanity: it really is Red's turn

    advanced = maybe_run_red_army_turn("game-x", game)

    assert advanced is True
    assert game.ai_red_army_status["state"] == "idle"
    assert game.ai_red_army_status["steps_taken"] > 0


def test_ai_is_a_no_op_when_disabled_for_this_game():
    game, red, other = _new_ai_red_vs_taiwan_game()
    game.ai_red_army_player_id = None

    advanced = maybe_run_red_army_turn("game-x", game)

    assert advanced is False


def test_ai_is_a_no_op_when_it_is_not_actually_red_armys_turn():
    game, red, other = _new_ai_red_vs_taiwan_game()
    # Force it to be the OTHER player's turn instead.
    game.current_player_index = next(i for i, p in enumerate(game.players) if p.id == other.id)

    advanced = maybe_run_red_army_turn("game-x", game)

    assert advanced is False
    assert game.ai_red_army_status["state"] == "idle"
    assert game.ai_red_army_status["steps_taken"] == 0


# ---------- AI-owned pending_choice is continued ----------

def test_ai_owned_pending_choice_is_continued_not_left_hanging():
    game, red, other = _new_ai_red_vs_taiwan_game()
    opened = game._activated_faction_action(red, '國安部')
    assert opened.get('pending_choice') is True
    assert game.pending_choice['player_id'] == red.id

    advanced = maybe_run_red_army_turn("game-x", game)

    assert advanced is True
    assert game.pending_choice is None  # resolved by the AI, not left dangling
    assert other.organizations.get('天津', 0) == 0  # the dissolve actually happened


# ---------- human pending choice/reaction window stops the AI, then wakes on the next update ----------

def test_ai_stops_for_a_humans_pending_choice_and_resumes_once_it_clears():
    game, red, other = _new_ai_red_vs_taiwan_game()
    game._set_pending_town_choice(
        other, 'test_choice_key', [{'town': '臺北'}], 'test prompt', source_name='test',
    )
    assert game.pending_choice['player_id'] == other.id

    first = maybe_run_red_army_turn("game-x", game)

    assert first is False
    assert game.pending_choice is not None
    assert game.pending_choice['player_id'] == other.id  # never resolved on the human's behalf
    assert game.ai_red_army_status["state"] == "idle"

    # The human resolves their own pending choice (simulating a real
    # resolve_pending_choice() call) — this is the state change the next
    # broadcast event should wake the AI up for.
    game.pending_choice = None

    second = maybe_run_red_army_turn("game-x", game)

    assert second is True
    assert game.ai_red_army_status["steps_taken"] > 0


# ---------- stops cleanly at game-over ----------

def test_ai_stops_cleanly_at_game_over_without_acting():
    game, red, other = _new_ai_red_vs_taiwan_game()
    game.game_phase = GamePhase.FINISHED
    game.winner = other.name

    advanced = maybe_run_red_army_turn("game-x", game)

    assert advanced is False
    # Status is untouched (still whatever start_game() initialized it to) —
    # the hook returns before ever calling into the policy for a finished game.
    assert game.ai_red_army_status == {"state": "idle"}


def test_ai_reports_finished_status_if_run_red_army_turn_itself_reports_game_over(monkeypatch):
    # Covers the other path into "game_over": the guard above is a cheap
    # short-circuit, but run_red_army_turn()'s own terminal status must
    # also be handled correctly if ever reached directly.
    game, red, other = _new_ai_red_vs_taiwan_game()

    class _Result:
        status = "game_over"
        steps_taken = 0

    monkeypatch.setattr(red_army_ai_runtime, "run_red_army_turn", lambda g, pid: _Result())

    advanced = maybe_run_red_army_turn("game-x", game)

    assert advanced is False
    assert game.ai_red_army_status["state"] == "finished"


# ---------- duplicate-runner prevention ----------

def test_duplicate_runner_is_prevented_for_a_reentrant_wake_up(monkeypatch):
    game, red, other = _new_ai_red_vs_taiwan_game()
    call_count = {"n": 0}
    real_run = red_army_ai_runtime.run_red_army_turn

    def reentrant_run(g, pid):
        call_count["n"] += 1
        # Simulate a second wake-up event for the exact same game_id firing
        # while this one is still in flight (e.g. two broadcasts racing).
        nested = maybe_run_red_army_turn("game-x", g)
        assert nested is False, "the nested/duplicate call must be a no-op"
        return real_run(g, pid)

    monkeypatch.setattr(red_army_ai_runtime, "run_red_army_turn", reentrant_run)

    advanced = maybe_run_red_army_turn("game-x", game)

    assert advanced is True
    assert call_count["n"] == 1  # the real policy entry point ran exactly once
    assert "game-x" not in _RUNNING  # guard released after completion


# ---------- injected runner error is isolated ----------

def test_injected_runner_crash_is_isolated_and_recorded(monkeypatch):
    game, red, other = _new_ai_red_vs_taiwan_game()

    def boom(g, pid):
        raise RuntimeError("simulated policy crash")

    monkeypatch.setattr(red_army_ai_runtime, "run_red_army_turn", boom)

    advanced = maybe_run_red_army_turn("game-x", game)  # must not raise

    assert advanced is False
    assert game.ai_red_army_status["state"] == "error"
    assert "simulated policy crash" in game.ai_red_army_status["message"]
    assert "game-x" not in _RUNNING  # guard released even after a crash


def test_injected_runner_crash_does_not_leave_the_room_stuck_forever(monkeypatch):
    """After an isolated crash, the hook must be callable again on the very
    next state update (not permanently wedged by the guard)."""
    game, red, other = _new_ai_red_vs_taiwan_game()

    def boom(g, pid):
        raise RuntimeError("simulated transient crash")

    monkeypatch.setattr(red_army_ai_runtime, "run_red_army_turn", boom)
    maybe_run_red_army_turn("game-x", game)
    assert game.ai_red_army_status["state"] == "error"

    monkeypatch.undo()
    advanced = maybe_run_red_army_turn("game-x", game)

    assert advanced is True
    assert game.ai_red_army_status["state"] == "idle"


# ---------- stalled (budget-tripped) status is also surfaced, not silently swallowed ----------

def test_stalled_policy_budget_is_recorded_as_a_comprehensible_status(monkeypatch):
    game, red, other = _new_ai_red_vs_taiwan_game()

    class _Result:
        status = "blocked_retry_exhausted"
        steps_taken = 3

    monkeypatch.setattr(red_army_ai_runtime, "run_red_army_turn", lambda g, pid: _Result())

    advanced = maybe_run_red_army_turn("game-x", game)

    assert advanced is True  # steps_taken > 0: still worth re-broadcasting
    assert game.ai_red_army_status["state"] == "stalled"
    assert game.ai_red_army_status["last_run_status"] == "blocked_retry_exhausted"


# ---------- full integration: the real broadcast_game_state() hook wakes the AI ----------

def test_broadcast_game_state_wakes_the_ai_and_rebroadcasts_the_result():
    """Proves the actual wiring point: server/main.py's broadcast_game_state()
    — the function every state-changing websocket action already funnels
    through — is what wakes the AI, not a client-side poll. A human's
    websocket receives two sends: the state right before the AI acted, then
    the state right after."""
    game, red, other = _new_ai_red_vs_taiwan_game()
    game_id = "broadcast-wakes-ai"
    human_socket = _FakeSocket()
    manager.connections[game_id] = {other.id: [human_socket]}
    try:
        asyncio.run(broadcast_game_state(game_id, game))
    finally:
        manager.connections.pop(game_id, None)

    assert len(human_socket.sent) >= 2
    first_turn = human_socket.sent[0].get("turn")
    last_state = human_socket.sent[-1]
    # The AI actually advanced authoritative state between the two sends —
    # not a mocked/stubbed claim: a real action went through Game's own
    # methods (action_submitter.submit -> Game.*), and current_player
    # reflects that forward progress really happened.
    assert last_state.get("ai_red_army", {}).get("status", {}).get("steps_taken", 0) > 0
    assert first_turn is not None


# ---------- fixed 3s pacing between successful AI actions ----------

class _Result:
    def __init__(self, status, steps_taken=1):
        self.status = status
        self.steps_taken = steps_taken


class _Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def _drive(monkeypatch, game, script, clock=None, game_id="pace-x", broadcast_seconds=0.0):
    """Run drive_red_army_turns against a scripted policy. Each script item is
    "ok" (successful action), "reject" (only a rejected attempt), or a status
    string for a no-submit outcome. Every would-be submission goes through the
    real pre_submit gate; fake sleep advances the fake clock."""
    script = list(script)
    clock = clock or _Clock()
    sleeps, broadcasts, submits = [], [], []

    def fake_run(g, pid, max_successful_actions=None, pre_submit=None):
        item = script.pop(0)
        if item in ("ok", "reject", "final"):
            try:
                if pre_submit:
                    pre_submit()
            except red_army_ai_runtime.SubmitDeferred:
                script.insert(0, item)
                return _Result("submit_deferred", 0)
            if item == "reject":
                return _Result("blocked_retry_exhausted", 1)
            submits.append(clock())
            if item == "final":
                g.game_phase = GamePhase.FINISHED
            return _Result("action_limit")
        return _Result(item, 0)

    monkeypatch.setattr(red_army_ai_runtime, "run_red_army_turn", fake_run)

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        clock.t += seconds

    async def on_advance():
        broadcasts.append(clock())
        clock.t += broadcast_seconds

    game, _, _ = game
    asyncio.run(red_army_ai_runtime.drive_red_army_turns(
        game_id, game, on_advance, delay_seconds=3.0, sleep=fake_sleep, clock=clock,
    ))
    return sleeps, broadcasts, submits


def test_default_action_delay_is_three_seconds():
    import importlib
    fresh = importlib.reload(red_army_ai_runtime)
    try:
        assert fresh.AI_ACTION_DELAY_SECONDS == 3.0
    finally:
        importlib.reload(red_army_ai_runtime)


def test_two_successful_actions_are_at_least_three_seconds_apart(monkeypatch):
    sleeps, broadcasts, submits = _drive(
        monkeypatch, _new_ai_red_vs_taiwan_game(), ["ok", "ok", "waiting_turn"],
    )
    assert sleeps == [3.0]
    assert submits[1] - submits[0] >= 3.0
    assert len(broadcasts) == 2


def test_no_sleep_after_the_last_successful_action(monkeypatch):
    sleeps, broadcasts, submits = _drive(
        monkeypatch, _new_ai_red_vs_taiwan_game(), ["ok", "waiting_turn"],
    )
    assert sleeps == []
    assert len(submits) == 1 and len(broadcasts) == 1


def test_no_delay_when_ai_waits_for_other_player(monkeypatch):
    sleeps, broadcasts, _ = _drive(
        monkeypatch, _new_ai_red_vs_taiwan_game(), ["waiting_other_pending"],
    )
    assert sleeps == [] and broadcasts == []


def test_human_reaction_within_cooldown_waits_only_the_remainder(monkeypatch):
    game = _new_ai_red_vs_taiwan_game()
    clock = _Clock()
    _, _, s1 = _drive(monkeypatch, game, ["ok", "waiting_other_pending"], clock=clock)
    assert red_army_ai_runtime._DRIVING == set()  # driver exited, human reacts
    clock.t += 1.0  # human answered after 1s
    sleeps, _, s2 = _drive(monkeypatch, game, ["ok", "waiting_turn"], clock=clock)
    assert sleeps == [pytest.approx(2.0)]
    assert s2[0] - s1[0] >= 3.0


def test_human_reaction_over_cooldown_does_not_wait(monkeypatch):
    game = _new_ai_red_vs_taiwan_game()
    clock = _Clock()
    _drive(monkeypatch, game, ["ok", "waiting_other_pending"], clock=clock)
    clock.t += 3.5
    sleeps, _, submits = _drive(monkeypatch, game, ["ok", "waiting_turn"], clock=clock)
    assert sleeps == []
    assert len(submits) == 1


def test_rejected_attempt_does_not_reset_or_trigger_cooldown(monkeypatch):
    game = _new_ai_red_vs_taiwan_game()
    clock = _Clock()
    _drive(monkeypatch, game, ["ok", "waiting_other_pending"], clock=clock)
    first = red_army_ai_runtime._LAST_SUCCESS["pace-x"]
    clock.t += 3.5
    sleeps, _, submits = _drive(monkeypatch, game, ["reject"], clock=clock)
    assert sleeps == []
    assert submits == []
    assert red_army_ai_runtime._LAST_SUCCESS["pace-x"] == first


def test_stalled_run_does_not_sleep_or_loop(monkeypatch):
    sleeps, _, _ = _drive(monkeypatch, _new_ai_red_vs_taiwan_game(), ["reject"])
    assert sleeps == []


def test_policy_pre_submit_deferral_submits_nothing():
    from red_army_policy import policy

    game, red, other = _new_ai_red_vs_taiwan_game()
    before = game.state(red.id).get("turn_phase")

    def gate():
        raise policy.SubmitDeferred()

    result = policy.run_red_army_turn(game, red.id, max_successful_actions=1, pre_submit=gate)
    if result.status != "waiting_turn":
        assert result.status == "submit_deferred"
        assert result.steps_taken == 0
        assert game.state(red.id).get("turn_phase") == before


def test_rejected_submission_does_not_count_as_an_action_or_add_delay(monkeypatch):
    """Policy level: a rejected submit retries inside the same run and does
    not consume the success budget, so no pacing boundary appears."""
    from red_army_policy import policy

    game, red, other = _new_ai_red_vs_taiwan_game()
    real_submit = policy.action_submitter.submit
    calls = {"n": 0}

    def flaky_submit(g, pid, action):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"error": "simulated rejection"}
        return real_submit(g, pid, action)

    monkeypatch.setattr(policy.action_submitter, "submit", flaky_submit)
    monkeypatch.setattr(policy.action_submitter, "action_error_message",
                        lambda r: (r or {}).get("error"))

    result = policy.run_red_army_turn(game, red.id, max_successful_actions=1)

    assert result.status == "action_limit"
    assert calls["n"] == 2  # 1 rejected + 1 successful, in a single run
    assert len(result.decisions) == 2


def test_drive_does_not_start_a_second_loop_while_one_is_in_flight(monkeypatch):
    game, red, other = _new_ai_red_vs_taiwan_game()
    red_army_ai_runtime._DRIVING.add("pace-x")
    ran = []
    monkeypatch.setattr(red_army_ai_runtime, "run_red_army_turn", lambda g, pid, **kw: ran.append(1))

    async def on_advance():
        pass

    asyncio.run(red_army_ai_runtime.drive_red_army_turns("pace-x", game, on_advance))
    assert ran == []


def test_cooldown_starts_after_broadcast_completes(monkeypatch):
    clock = _Clock()
    sleeps, broadcasts, submits = _drive(
        monkeypatch, _new_ai_red_vs_taiwan_game(), ["ok", "ok", "waiting_turn"],
        clock=clock, broadcast_seconds=4.0,
    )
    # Broadcast took 4s (> 3s delay) but the next action still waits a full 3s
    # after that broadcast finished.
    assert sleeps == [3.0]
    broadcast_done = broadcasts[0] + 4.0
    assert submits[1] - broadcast_done >= 3.0


def test_final_action_marks_finished_and_clears_pacing_state(monkeypatch):
    game_tuple = _new_ai_red_vs_taiwan_game()
    game = game_tuple[0]
    sleeps, broadcasts, submits = _drive(monkeypatch, game_tuple, ["ok", "final"])
    assert len(submits) == 2
    assert game.game_phase == GamePhase.FINISHED
    assert game.ai_red_army_status["state"] == "finished"
    assert game.ai_red_army_status["last_run_status"] == "game_over"
    assert "pace-x" not in red_army_ai_runtime._LAST_SUCCESS
    assert len(broadcasts) == 2


def test_forget_game_clears_pacing_state():
    red_army_ai_runtime._LAST_SUCCESS["g1"] = 1.0
    red_army_ai_runtime.forget_game("g1")
    assert "g1" not in red_army_ai_runtime._LAST_SUCCESS
