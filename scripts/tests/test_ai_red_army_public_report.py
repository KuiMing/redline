"""AI 紅軍公開行動摘要（客廳輪流的置中公開視窗資料來源）。

契約：
- 內容是該步新增的 log（取公開投影）與資金、宣傳；紅軍仍是 current player 時就顯示，不要求隱藏任何資訊。
- 只有啟用 AI 紅軍的遊戲才輸出 state()["ai_red_army"]["public_report"]；其他遊戲 state 不變。
- 純顯示資料：不改變 AI 的行動結果，也不影響規則結算。
- 換回合時重新開始；步驟數與每步行數有上限。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game
from server.game_models import GamePhase
from server.red_army_ai_runtime import _RUNNING, maybe_run_red_army_turn
import server.red_army_ai_runtime as runtime


def _ai_game():
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
def _clean(monkeypatch):
    _RUNNING.clear()
    runtime._DRIVING.clear()
    runtime._LAST_SUCCESS.clear()
    monkeypatch.setattr(runtime, "AI_ACTION_DELAY_SECONDS", 0.0)
    yield
    _RUNNING.clear()
    runtime._DRIVING.clear()
    runtime._LAST_SUCCESS.clear()


def test_ai_step_records_public_lines_resources_and_turn():
    game, red, other = _ai_game()
    turn = game.turn

    # 第一步只是換階段（沒有公開變化，不留項目）；之後的步驟才有公開 log
    for _ in range(3):
        assert maybe_run_red_army_turn("g", game, max_actions=1) is True

    report = game.state(other.id)["ai_red_army"]["public_report"]
    assert report["turn"] == turn
    assert report["actor_name"] == red.name
    assert report["steps"][0]["seq"] == 1
    step = report["steps"][-1]
    assert step["lines"], "AI 的一步行動至少會留下一行公開 log"
    assert all(line.startswith(f"[Turn {turn}]") for line in step["lines"])
    assert set(step["resources"]) == {"money", "propaganda"}
    assert step["resources"] == {"money": red.resources.get("money", 0), "propaganda": red.resources.get("propaganda", 0)}
    assert set(step["delta"]) == {"money", "propaganda"}


def test_report_has_only_the_documented_fields():
    game, red, other = _ai_game()
    for _ in range(3):
        maybe_run_red_army_turn("g", game, max_actions=1)
    report = game.state(other.id)["ai_red_army"]["public_report"]
    assert set(report) == {"turn", "actor_name", "next_seq", "steps"}
    for step in report["steps"]:
        assert set(step) == {"seq", "lines", "resources", "delta"}


def test_public_report_only_exists_for_ai_games():
    game, red, other = _ai_game()
    for _ in range(3):
        maybe_run_red_army_turn("g", game, max_actions=1)
    assert "public_report" in game.state(other.id)["ai_red_army"]

    plain = Game([('p1', 'red'), ('p2', 'other')])
    assert plain.state('p1')["ai_red_army"] == {"enabled": False, "player_id": None, "status": {"state": "idle"}}

    game.ai_red_army_player_id = None
    assert "public_report" not in game.state(other.id)["ai_red_army"]


def test_steps_accumulate_within_a_turn_and_reset_on_a_new_turn():
    game, red, other = _ai_game()
    for _ in range(4):
        maybe_run_red_army_turn("g", game, max_actions=1)
    report = game.ai_red_army_public_report
    turn = report["turn"]
    assert [s["seq"] for s in report["steps"]][:2] == [1, 2]

    # 同一個 report 在另一個回合重新開始
    game.turn = turn + 1
    game.current_player_index = next(i for i, p in enumerate(game.players) if p.id == red.id)
    seq0 = game._log_seq
    game.log(f"{red.name} played 追隨者 as resource")
    runtime._record_public_report(game, red.id, game.turn, seq0, {"money": 0, "propaganda": 0})
    fresh = game.ai_red_army_public_report
    assert fresh["turn"] == turn + 1 and [s["seq"] for s in fresh["steps"]] == [1]


def test_report_limits_steps_and_lines(monkeypatch):
    game, red, other = _ai_game()
    for index in range(runtime._PUBLIC_REPORT_MAX_STEPS + 5):
        seq0 = game._log_seq
        for n in range(runtime._PUBLIC_REPORT_MAX_LINES + 4):
            game.log(f"{red.name} played 測試 as resource {index}-{n}")
        runtime._record_public_report(game, red.id, game.turn, seq0, {"money": 0, "propaganda": 0})
    report = game.ai_red_army_public_report
    assert len(report["steps"]) == runtime._PUBLIC_REPORT_MAX_STEPS
    assert all(len(step["lines"]) <= runtime._PUBLIC_REPORT_MAX_LINES for step in report["steps"])


def test_display_layer_failure_never_changes_the_rules_outcome(monkeypatch):
    broken, red, other = _ai_game()
    monkeypatch.setattr(Game, "public_action_log_since", lambda self, seq: (_ for _ in ()).throw(RuntimeError("boom")))

    # 摘要失敗只記錄、不外拋：AI 仍照常行動並回報 steps_taken，規則狀態照常前進
    for _ in range(3):
        assert maybe_run_red_army_turn("g", broken, max_actions=1) is True

    assert broken.ai_red_army_status["state"] == "idle"
    assert broken.ai_red_army_status["steps_taken"] > 0
    assert broken.action_log, "AI 的行動照常寫入 log"
    assert broken.ai_red_army_public_report is None


# ---------- 客廳輪流：結束回合前，current player 仍是紅軍，等公開視窗確認（知道了／A／逾時）才輪到下一位 ----------

import asyncio


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _drive(game, *, on_wait=None):
    """跑完 AI 紅軍這一回合。on_wait(game) 在每次等待時呼叫（模擬前端／時間流逝）。"""
    clock = _Clock()
    waits = []
    broadcasts = []

    async def on_advance():
        broadcasts.append(game.state(game.players[1].id)["ai_red_army"].get("awaiting_ack"))

    async def sleep(seconds):
        waits.append(seconds)
        clock.t += seconds
        if on_wait:
            on_wait(game, clock)

    asyncio.run(runtime.drive_red_army_turns("hold-game", game, on_advance, delay_seconds=0.0, sleep=sleep, clock=clock))
    return clock, waits, broadcasts


def test_hold_disabled_by_default_ends_turn_without_waiting():
    game, red, other = _ai_game()
    clock, waits, _ = _drive(game)
    assert game.current_player().id == other.id
    assert game.ai_red_army_ack is None
    assert clock.t == 0.0 and not waits


def test_hold_keeps_red_army_current_player_until_acknowledged_then_advances():
    game, red, other = _ai_game()
    assert runtime.set_public_hold(game, True) is True
    observed = []

    def on_wait(g, clock):
        # 每次等待：權威狀態（Game 與 state()）都必須仍是紅軍的回合
        view = g.state(other.id)
        observed.append({
            "current": g.current_player().id, "state_current": view["current_player"],
            "awaiting": view["ai_red_army"]["awaiting_ack"], "turn": g.turn,
        })
        if len(observed) == 3:
            assert runtime.acknowledge_ai_turn(g) is True

    _, _, broadcasts = _drive(game, on_wait=on_wait)

    assert len(observed) >= 3
    assert all(o["current"] == red.id and o["state_current"] == red.name for o in observed)
    assert all(o["awaiting"] == {"turn": observed[0]["turn"], "timeout_seconds": runtime.AI_ACK_TIMEOUT_SECONDS} for o in observed)
    assert any(b is not None for b in broadcasts)  # 等待狀態有被廣播給前端
    # 確認之後才推進到下一位，等待狀態清除
    assert game.current_player().id == other.id
    assert game.state(other.id)["ai_red_army"]["awaiting_ack"] is None
    assert runtime.acknowledge_ai_turn(game) is False  # 沒有在等待，不能重複確認


def test_hold_times_out_without_acknowledgement_then_advances():
    game, red, other = _ai_game()
    runtime.set_public_hold(game, True)
    seen_red_current = []

    def on_wait(g, clock):
        seen_red_current.append(g.current_player().id == red.id)

    clock, waits, _ = _drive(game, on_wait=on_wait)

    assert all(seen_red_current) and len(seen_red_current) >= 2
    assert clock.t >= runtime.AI_ACK_TIMEOUT_SECONDS
    assert game.current_player().id == other.id


def test_hold_only_applies_to_ai_games_and_the_turn_ending_advance():
    plain = Game([('p1', 'red'), ('p2', 'other')])
    assert runtime.set_public_hold(plain, True) is False
    game, red, other = _ai_game()
    runtime.set_public_hold(game, True)
    # 回合中的其他行動（含第一步的事件階段 advance）不會等待確認
    assert not runtime._ends_ai_turn(game, {"kind": "buy_card", "index": 0})
    from server.game_models import TurnPhase
    game.turn_phase = TurnPhase.EVENT
    assert not runtime._ends_ai_turn(game, {"kind": "advance_turn"})  # 事件階段的 advance 不算結束回合
    game.turn_phase = TurnPhase.ACTION
    assert runtime._ends_ai_turn(game, {"kind": "advance_turn"})
    runtime.set_public_hold(game, False)
    assert game.ai_red_army_ack is None


def test_public_hold_lasts_only_while_at_least_one_registered_display_is_connected():
    game, _, _ = _ai_game()
    assert runtime.set_public_hold(game, True, "living-room-a") is True
    assert runtime.set_public_hold(game, True, "living-room-b") is True
    assert game.ai_red_army_public_hold is True
    runtime.set_public_hold(game, False, "living-room-a")
    assert game.ai_red_army_public_hold is True
    setattr(game, "ai_red_army_ack", {"turn": game.turn, "acknowledged": False})
    runtime.set_public_hold(game, False, "living-room-b")
    assert game.ai_red_army_public_hold is False
    assert game.ai_red_army_ack is None
