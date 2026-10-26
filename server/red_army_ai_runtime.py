"""Server-side wake-up hook that drives the `red_army_policy` engine for a
room whose lobby toggled "AI 紅軍" on (see server/lobby_routes.py's
`set_ai_red_army()` / `start_game()`).

Design (see the top-level feature report for the full rationale):

- **Trigger**: `maybe_run_red_army_turn(game_id, game)` is called from
  `server/main.py`'s `broadcast_game_state()` — the one place every
  state-changing event (a human's websocket action, an auto-skipped
  reaction timeout, …) already funnels through to notify connected
  clients. There is no browser-side poll/interval driving this; the
  "wake-up" is this hook being invoked again the next time *any* event
  broadcasts a new state. `broadcast_game_state()` calls this function
  once more after re-broadcasting if the AI actually advanced the game, so
  a single human action can legitimately cascade into several AI turns in
  a row (e.g. the human's turn ends, the next two players are both AI —
  not currently possible with only one Red Army seat, but the recursion
  is written to be correct in general) without needing a second external
  trigger.
- **No-op by construction** when: the game has no AI seat
  (`game.ai_red_army_player_id` unset — i.e. AI Red Army was off for this
  room), the game has already finished, or it is not actually Red Army's
  turn / Red Army does not own the current pending choice — the last of
  those is enforced inside `red_army_policy.policy.step()` itself
  (requirement: a human's reaction window or pending_choice must stop the
  AI), this module never second-guesses that.
- **Duplicate-runner prevention**: `_RUNNING`, a plain module-level set of
  game_ids currently inside a `run_red_army_turn()` call. Because Python's
  asyncio event loop is single-threaded and this function never awaits
  internally, nothing can genuinely race it today — but the guard is kept
  as an explicit, testable invariant (and defends against a future caller
  that `asyncio.to_thread`s this, or two recursive/re-entrant calls on the
  same call stack) rather than relying on that implementation detail.
- **Error isolation**: any exception raised out of
  `red_army_policy.run_red_army_turn()` is caught here, logged, and
  recorded on `game.ai_red_army_status` as `{"state": "error", ...}` — it
  never propagates into the websocket handler or crashes the room/process.
  An anomalous-but-not-exceptional terminal status (the policy's own
  step/retry/loop-guard budgets tripping) is recorded as `{"state":
  "stalled", ...}` for the same reason: the frontend should be able to
  show *something* comprehensible instead of the AI silently hanging.
- Never mutates `Game` state directly — only ever calls
  `red_army_policy.run_red_army_turn()`, which itself only acts through
  `Game`'s existing authoritative action methods (see
  `red_army_policy/action_submitter.py`).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

from red_army_policy import run_red_army_turn
from red_army_policy.policy import SubmitDeferred

logger = logging.getLogger(__name__)

# Fixed pause between two consecutive successful AI actions so humans can
# follow what happened. Tests monkeypatch this or pass `sleep`/`delay_seconds`.
AI_ACTION_DELAY_SECONDS = 3.0

# 客廳輪流公開視窗：AI 紅軍要結束回合時，先停在 current player＝紅軍，最長等這麼久（逾時視同確認）。
AI_ACK_TIMEOUT_SECONDS = 10.0
# 等待確認期間重新檢查的間隔；確認（知道了／A）最多晚這麼久生效。
AI_ACK_POLL_SECONDS = 0.2

# game_ids with an async pacing loop (drive_red_army_turns) in flight; held
# across awaits so a human event arriving mid-delay can't start a second one.
_DRIVING: set[str] = set()

# game_id -> clock() reading at the last *successful* AI action. Survives the
# driver exiting (e.g. while a human reacts) so any later wake-up still honours
# the remaining cooldown. Rejected attempts never touch it.
_LAST_SUCCESS: dict[str, float] = {}

# game_id -> currently inside a run_red_army_turn() call for that game.
_RUNNING: set[str] = set()

# 背景繼續的公開視窗確認等待（drive_red_army_turns 的 detach_ack_wait）；保留參照直到結束。
_ACK_WAITERS: set[asyncio.Task] = set()


def forget_game(game_id: str) -> None:
    """Drop the per-game cooldown state (game finished / fresh start).

    `_DRIVING` / `_RUNNING` are deliberately left alone: they are ownership
    guards released only by the live driver's own `finally`. A driver may
    still be awaiting a broadcast or cooldown, and discarding its guard here
    would let a second driver start and double-submit.
    """
    _LAST_SUCCESS.pop(game_id, None)


# 公開行動摘要（客廳輪流的置中公開視窗）上限：只保留最近這些步驟、每步最多這些行。
_PUBLIC_REPORT_MAX_STEPS = 40
_PUBLIC_REPORT_MAX_LINES = 12
_PUBLIC_REPORT_MAX_LINE_CHARS = 200


def _ai_player(game: Any, ai_player_id: str) -> Any:
    return next((p for p in getattr(game, "players", []) or [] if getattr(p, "id", None) == ai_player_id), None)


def _public_resources(player: Any) -> dict[str, int]:
    """資金與宣傳是公開資訊（HUD 與 players 投影都會顯示），不含手牌或牌庫。"""
    resources = getattr(player, "resources", None) or {}
    return {"money": int(resources.get("money", 0) or 0), "propaganda": int(resources.get("propaganda", 0) or 0)}


def set_public_hold(game: Any, enabled: bool, holder_id: Any = "__legacy__") -> bool:
    """登記客廳輪流顯示端。至少一個登記仍有效時，AI 紅軍結束回合前才等待確認。"""
    if not getattr(game, "ai_red_army_player_id", None):
        return False
    holders = getattr(game, "ai_red_army_public_hold_clients", None)
    if not isinstance(holders, set):
        holders = game.ai_red_army_public_hold_clients = set()
    if enabled:
        holders.add(holder_id)
    else:
        holders.discard(holder_id)
    game.ai_red_army_public_hold = bool(holders)
    if not game.ai_red_army_public_hold:
        game.ai_red_army_ack = None
    return True


def acknowledge_ai_turn(game: Any) -> bool:
    """公開視窗的「知道了」／A：放行正在等待確認的 AI 紅軍結束回合。沒有在等待時回 False。"""
    ack = getattr(game, "ai_red_army_ack", None)
    if not ack or ack.get("released") or ack.get("acknowledged"):
        return False
    ack["acknowledged"] = True
    return True


def _ends_ai_turn(game: Any, action: Any) -> bool:
    phase = getattr(getattr(game, "turn_phase", None), "value", getattr(game, "turn_phase", None))
    return bool(action) and action.get("kind") == "advance_turn" and phase == "action"


def _record_public_report(game: Any, ai_player_id: str, turn: Any, log_seq: int, resources_before: dict[str, int]) -> None:
    """把這一步 AI 行動新增的公開 log 與公開資源變化存到 `game.ai_red_army_public_report`。

    只讀 Game 的公開投影（`public_action_log_since`）與公開資源；顯示層失敗不得影響規則結算，
    所以任何例外都只記錄、不外拋。
    """
    try:
        player = _ai_player(game, ai_player_id)
        lines = [
            str(line)[:_PUBLIC_REPORT_MAX_LINE_CHARS]
            for line in game.public_action_log_since(log_seq)
        ][-_PUBLIC_REPORT_MAX_LINES:]
        after = _public_resources(player) if player is not None else {"money": 0, "propaganda": 0}
        delta = {key: after[key] - resources_before.get(key, 0) for key in after}
        if not lines and not any(delta.values()):
            return  # 單純換階段等沒有任何公開變化的一步，不留空白項目
        report = getattr(game, "ai_red_army_public_report", None)
        if not report or report.get("turn") != turn:
            report = {"turn": turn, "actor_name": getattr(player, "name", ""), "next_seq": 1, "steps": []}
        report["steps"].append({
            "seq": report["next_seq"],
            "lines": lines,
            "resources": after,
            "delta": delta,
        })
        report["next_seq"] += 1
        report["steps"] = report["steps"][-_PUBLIC_REPORT_MAX_STEPS:]
        game.ai_red_army_public_report = report
    except Exception:  # pragma: no cover - defensive isolation path
        logger.exception("Red Army AI public report failed for the current game")


_STALLED_STATUSES = {
    "blocked_fingerprint_loop",
    "blocked_retry_exhausted",
    "blocked_step_budget",
}


def maybe_run_red_army_turn(
    game_id: str, game: Any, max_actions: int | None = None, pre_submit: Any = None,
) -> bool:
    """Drive the AI Red Army forward as far as it can go right now, if at
    all. Returns True iff it actually attempted at least one decision this
    call (i.e. the caller should re-broadcast the resulting state) — False
    for every no-op case (AI disabled, game over, not AI's turn, already
    running, or a crash isolated below).
    """
    ai_player_id = getattr(game, "ai_red_army_player_id", None)
    if not ai_player_id:
        return False

    # GamePhase is a `str, Enum` — GamePhase.FINISHED == "finished" holds
    # directly via the str mixin, so this also works against a plain string
    # double used by a test fixture that doesn't import GamePhase at all.
    if getattr(game, "game_phase", None) == "finished":
        _LAST_SUCCESS.pop(game_id, None)
        return False

    if game_id in _RUNNING:
        # Another invocation is already driving this exact game_id forward
        # (reentrant/duplicate wake-up event) — never run two concurrently.
        return False

    ai_player = _ai_player(game, ai_player_id)
    log_seq_before = getattr(game, "_log_seq", 0)
    turn_before = getattr(game, "turn", None)
    resources_before = _public_resources(ai_player) if ai_player is not None else {"money": 0, "propaganda": 0}
    _RUNNING.add(game_id)
    try:
        if max_actions is None and pre_submit is None:
            result = run_red_army_turn(game, ai_player_id)
        else:
            result = run_red_army_turn(
                game, ai_player_id, max_successful_actions=max_actions, pre_submit=pre_submit,
            )
    except Exception as exc:  # pragma: no cover - defensive isolation path
        logger.exception("Red Army AI runner crashed for game %s", game_id)
        game.ai_red_army_status = {
            "state": "error",
            "message": str(exc),
        }
        return False
    finally:
        _RUNNING.discard(game_id)

    if result.status == "submit_deferred":
        # Stopped before submitting (cooldown); nothing happened, keep status.
        return False

    if result.status in _STALLED_STATUSES:
        game.ai_red_army_status = {
            "state": "stalled",
            "last_run_status": result.status,
            "steps_taken": result.steps_taken,
        }
    elif result.status == "game_over":
        game.ai_red_army_status = {
            "state": "finished",
            "last_run_status": result.status,
            "steps_taken": result.steps_taken,
        }
    else:
        game.ai_red_army_status = {
            "state": "idle",
            "last_run_status": result.status,
            "steps_taken": result.steps_taken,
        }

    if result.steps_taken > 0:
        _record_public_report(game, ai_player_id, turn_before, log_seq_before, resources_before)

    return result.steps_taken > 0


async def drive_red_army_turns(
    game_id: str,
    game: Any,
    on_advance: Callable[[], Awaitable[None]],
    *,
    delay_seconds: float | None = None,
    sleep: Callable[[float], Awaitable[Any]] | None = None,
    clock: Callable[[], float] | None = None,
    detach_ack_wait: bool = False,
) -> None:
    """Play the AI one successful action at a time, `on_advance` (broadcast)
    after each, keeping >= `delay_seconds` between successful actions.

    Cooldown semantics: the deadline is `_LAST_SUCCESS[game_id] + delay`,
    checked by the policy immediately before every submission. If it hasn't
    passed, nothing is submitted; we `await sleep(remaining)` (non-blocking)
    and re-run against fresh state. So the wait is never taken speculatively:
    after the last action, at turn end, or while waiting on another player
    there is no sleep and the driver exits. Time a human spends reacting
    counts toward the cooldown; rejected retries neither wait nor reset it.
    Rules/legality stay in the policy and Game.

    `detach_ack_wait`: the public-window ack wait (up to AI_ACK_TIMEOUT_SECONDS)
    continues in a background task instead of inside this call. The caller is
    the websocket handler that broadcast the human's turn end; blocking it here
    would leave the 知道了／A `ack_ai_red_army` sent on that same socket unread
    until the timeout.
    """
    if game_id in _DRIVING:
        return
    delay = AI_ACTION_DELAY_SECONDS if delay_seconds is None else delay_seconds
    sleeper = sleep or asyncio.sleep
    now = clock or time.monotonic
    remaining: list[float] = []
    signals: list[str] = []

    def _gate(action: Any = None) -> None:
        last = _LAST_SUCCESS.get(game_id)
        if last is not None:
            wait = last + delay - now()
            if wait > 0:
                remaining.append(wait)
                raise SubmitDeferred()
        if not (getattr(game, "ai_red_army_public_hold", False) and _ends_ai_turn(game, action)):
            return
        # 客廳輪流：結束回合前先停在 current player＝紅軍，等公開視窗確認（知道了／A）或逾時，之後才真的推進到下一位。
        ack = getattr(game, "ai_red_army_ack", None)
        if not ack or ack.get("turn") != game.turn:
            ack = game.ai_red_army_ack = {
                "turn": game.turn, "timeout_seconds": AI_ACK_TIMEOUT_SECONDS,
                "deadline": now() + AI_ACK_TIMEOUT_SECONDS, "acknowledged": False, "released": False,
            }
            signals.append("awaiting_ack")
        if ack["released"]:
            return
        if ack["acknowledged"] or now() >= ack["deadline"]:
            ack["released"] = True
            signals.append("ack_released")
            return
        remaining.append(min(AI_ACK_POLL_SECONDS, ack["deadline"] - now()))
        signals.append("ack_wait")
        raise SubmitDeferred()

    _gate.accepts_action = True  # type: ignore[attr-defined]

    _DRIVING.add(game_id)
    detached = False
    try:
        while True:
            remaining.clear()
            signals.clear()
            advanced = maybe_run_red_army_turn(game_id, game, max_actions=1, pre_submit=_gate)
            if "awaiting_ack" in signals:
                await on_advance()  # 讓前端看到「紅軍回合結束，等待確認」（current player 仍是紅軍）
            if remaining:
                if detach_ack_wait and "ack_wait" in signals:
                    detached = True
                    break
                await sleeper(remaining[0])
                continue
            if not advanced:
                break
            # The authoritative phase decides "finished": a final action hits
            # max_successful_actions=1 and reports action_limit, not game_over.
            if getattr(game, "game_phase", None) == "finished":
                game.ai_red_army_status = {
                    "state": "finished",
                    "last_run_status": "game_over",
                    "steps_taken": (game.ai_red_army_status or {}).get("steps_taken", 0),
                }
                _LAST_SUCCESS.pop(game_id, None)
                await on_advance()
                break
            status = (game.ai_red_army_status or {}).get("last_run_status")
            await on_advance()
            if status == "action_limit":
                # Observable-time baseline: starts once the broadcast is done.
                _LAST_SUCCESS[game_id] = now()
            else:
                if status == "game_over":
                    _LAST_SUCCESS.pop(game_id, None)
                break
    finally:
        _DRIVING.discard(game_id)
    if detached:
        # 等待確認改在背景繼續（輪詢確認／逾時後照常推進並廣播）；呼叫端的 websocket 才能讀到同一條連線送來的確認。
        task = asyncio.get_running_loop().create_task(drive_red_army_turns(
            game_id, game, on_advance, delay_seconds=delay_seconds, sleep=sleep, clock=clock))
        _ACK_WAITERS.add(task)
        task.add_done_callback(_ACK_WAITERS.discard)
