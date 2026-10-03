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

import logging
from typing import Any

from red_army_policy import run_red_army_turn

logger = logging.getLogger(__name__)

# game_id -> currently inside a run_red_army_turn() call for that game.
_RUNNING: set[str] = set()

_STALLED_STATUSES = {
    "blocked_fingerprint_loop",
    "blocked_retry_exhausted",
    "blocked_step_budget",
}


def maybe_run_red_army_turn(game_id: str, game: Any) -> bool:
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
        return False

    if game_id in _RUNNING:
        # Another invocation is already driving this exact game_id forward
        # (reentrant/duplicate wake-up event) — never run two concurrently.
        return False

    _RUNNING.add(game_id)
    try:
        result = run_red_army_turn(game, ai_player_id)
    except Exception as exc:  # pragma: no cover - defensive isolation path
        logger.exception("Red Army AI runner crashed for game %s", game_id)
        game.ai_red_army_status = {
            "state": "error",
            "message": str(exc),
        }
        return False
    finally:
        _RUNNING.discard(game_id)

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

    return result.steps_taken > 0
