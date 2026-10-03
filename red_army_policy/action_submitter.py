"""Stage 6 — ActionSubmitter.

Submits exactly one decided action through `Game`'s own existing
action/authoritative methods (never by mutating `Game` attributes
directly) and reports whether the server accepted it. This is the single
place that decides "did that work" — it mirrors server/main.py's
websocket handler's kind -> method dispatch table and its
`_ws_action_error_message` success/failure interpretation exactly, so a
policy decision is submitted the same way a real browser client's click
would be.

Per requirement #3/#5: the caller (policy.py) must always re-read and
re-score from a fresh `Game.state()` after calling `submit()` — this
module never retries internally and never assumes success from a `kind`
match alone. It explicitly tolerates (by returning the server's own
error rather than raising) the documented false-positive-legality case:
legal_actions() can offer `use_topdeck_right` when the server will still
reject it (see candidate_generator.py's docstring) — that just comes back
as an ordinary failed result here, handled by the caller like any other
rejected submission.
"""

from __future__ import annotations

from typing import Any


def action_error_message(result: Any) -> str | None:
    """Same interpretation as server/main.py's `_ws_action_error_message`:
    a dict result is a real failure if it carries a nonempty `error`, OR
    explicitly reports `success: False` (server/game.py's
    `_red_army_unavailable_result` shape — a Red Army ability that is
    legitimately unavailable right now). Duplicated here (deliberately
    small, ~10 lines) rather than imported from server.main, so this
    package never has to import the FastAPI app/HTTP layer to interpret a
    plain result dict.
    """
    if not isinstance(result, dict):
        return None
    if result.get("error"):
        return result.get("error")
    if result.get("success") is False:
        inner = result.get("result")
        if isinstance(inner, dict) and inner.get("message"):
            return inner["message"]
        return "Action unavailable"
    return None


def submit(game: Any, player_id: str, action: dict[str, Any]) -> dict[str, Any]:
    kind = action.get("kind")

    if kind == "advance_turn":
        return game.advance_turn_phase()

    if kind == "play_card":
        return game.play_card(
            action["index"],
            mode=action.get("mode") or "resource",
            target_player_id=action.get("target_player_id"),
            target_player_ids=action.get("target_player_ids"),
        )

    if kind == "buy_card":
        return game.buy_card(action["index"])

    if kind == "move_organization":
        return game.move_organization(action["from_town"], action["to_town"], action.get("mode", "road"))

    if kind == "faction_action":
        actor = game.current_player()
        return game._activated_faction_action(
            actor,
            action.get("name"),
            guess=action.get("guess"),
            target_player_id=action.get("target_player_id"),
        )

    if kind == "use_topdeck_right":
        return game.use_pending_topdeck_right()

    if kind == "resolve_pending_choice":
        if "indices" in action:
            return game.resolve_pending_choice(
                player_id,
                action["indices"],
                expected_choice_id=action.get("choice_id"),
            )
        return game.resolve_pending_choice(
            player_id,
            action.get("index"),
            target_player_ids=action.get("target_player_ids"),
            expected_choice_id=action.get("choice_id"),
        )

    if kind == "set_base":
        return game.set_base_choice(player_id, action.get("town"), action.get("label"))

    if kind == "keep_hong_kong_base":
        return game.keep_hong_kong_base(player_id)

    if kind == "relocate_hong_kong_base":
        return game.relocate_hong_kong_base(player_id, action.get("town"))

    return {"error": f"ActionSubmitter has no dispatch for action kind {kind!r}"}
