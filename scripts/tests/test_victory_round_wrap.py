"""P1 regression: 宣布勝利時機應該等整輪（含紅軍）都行動完才公布.

Victory must only be declared once a full round has completed — after every
player, Red Army included, has taken their turn — because Red Army may act later
in the same round (e.g. dissolve an organization propping up an org-count victory
condition) and invalidate a condition that briefly looked satisfied earlier in
the round. These tests mirror the era-trigger round-wrap regressions in
test_era_lifecycle.py, adapted to victory's simpler evaluate-and-finish shape
(no interactive activation queue).
"""

import random
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.game import Game, GamePhase, TurnPhase


def _make_game(actor_faction="taiwan_green"):
    random.seed(20260728)
    game = Game([("actor", "actor"), ("red", "red")], market_mode="all_cards")
    actor, red = game.players
    actor.id = "actor"
    actor.name = "actor"
    actor.faction_id = actor_faction
    actor.organizations = {}
    red.id = "red"
    red.name = "red"
    red.faction_id = "red_army"
    red.organizations = {"北京": 1}
    game.current_player_index = 0
    game.round_start_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.winner = None
    game.co_winners = []
    game.pending_choice = None
    # Keep this focused on the victory-timing boundary rather than event effects.
    game.current_event = {"id": "test-idle", "name": "test idle", "type": "idle"}
    game.event_progress = {
        "count": 0,
        "required": 0,
        "succeeded": True,
        "settled": True,
        "status": "idle",
    }
    return game, actor, red


def _advance_current_player_turn(game):
    """Drive one player's ACTION -> END -> (next player's) ACTION, asserting the
    game did NOT finish on this turn (so the phase returns to ACTION)."""
    assert game.turn_phase == TurnPhase.ACTION
    assert game.advance_turn_phase() == {"success": True}
    assert game.turn_phase == TurnPhase.END
    assert game.advance_turn_phase() == {"success": True}
    assert game.turn_phase == TurnPhase.ACTION


def _advance_expecting_finish(game):
    """Drive the last player's ACTION -> END -> _end_turn where victory is expected
    to be declared at the round wrap; _end_turn returns early on FINISHED so the
    phase never returns to ACTION."""
    assert game.turn_phase == TurnPhase.ACTION
    assert game.advance_turn_phase() == {"success": True}
    assert game.turn_phase == TurnPhase.END
    assert game.advance_turn_phase() == {"success": True}


def _inside_wall_count_only_condition(game, player):
    faction = game.faction_by_id[player.faction_id]
    return next(
        c for c in faction["win_conditions"]
        if c.get("type") == "count_only" and c.get("scope") == "牆內"
    )


def _legal_inside_wall_towns(game, player, red):
    return [
        town
        for town in game._towns_for_region_alias("china")
        if game.can_faction_develop_in_town(player.faction_id, town)
        and game._shared_org_count(red, town) == 0
    ]


def test_victory_deferred_to_round_wrap_so_red_army_can_still_invalidate_it():
    """Non-red player satisfies its org-count victory on its own turn, but before
    the round wraps Red Army dissolves one propping organization, dropping it back
    below the threshold. Victory detection is deferred to the round-wrap boundary,
    so the game must NOT finish — neither mid-round on the non-red turn, nor at the
    wrap once Red Army has undone the condition."""
    game, actor, red = _make_game()
    condition = _inside_wall_count_only_condition(game, actor)
    required = condition["count"]
    legal = _legal_inside_wall_towns(game, actor, red)
    assert len(legal) >= required
    actor.organizations = {town: 1 for town in legal[:required]}

    # Actor (seat 0) opens the round already meeting its victory condition. Ending
    # its own turn must NOT finish the game: the round has not wrapped and Red Army
    # has not yet acted.
    game.current_player_index = 0
    _advance_current_player_turn(game)
    assert game.game_phase != GamePhase.FINISHED
    assert game.winner is None

    # Red Army acts later in the SAME round and dissolves one of the actor's
    # inside-wall organizations, dropping it to required-1 before the round wraps.
    del actor.organizations[legal[required - 1]]

    # Ending Red Army's turn wraps the round; victory is judged now and sees only
    # required-1 orgs, so no winner is declared.
    _advance_current_player_turn(game)
    assert game.current_player_index == game.round_start_player_index  # round wrapped
    assert game.game_phase != GamePhase.FINISHED
    assert game.winner is None


def test_victory_declared_at_round_wrap_when_condition_survives_red_army_turn():
    """Positive path: the same victory condition still holds after Red Army's turn,
    so victory IS declared — but only at the round-wrap boundary, not on the
    non-red player's own mid-round turn."""
    game, actor, red = _make_game()
    condition = _inside_wall_count_only_condition(game, actor)
    required = condition["count"]
    legal = _legal_inside_wall_towns(game, actor, red)
    assert len(legal) >= required
    actor.organizations = {town: 1 for town in legal[:required]}

    # Deferred: not declared on the actor's own turn mid-round.
    game.current_player_index = 0
    _advance_current_player_turn(game)
    assert game.game_phase != GamePhase.FINISHED
    assert game.winner is None

    # Red Army acts but leaves the condition intact; ending its turn wraps the
    # round and victory is finally declared at the boundary.
    _advance_expecting_finish(game)
    assert game.game_phase == GamePhase.FINISHED
    assert game.winner == actor.name


def test_turn20_red_army_fallback_still_declared_at_round_wrap():
    """The existing turn-20 fallback (Red Army survives to turn 21) is judged at
    the same round-wrap _check_victory() call, which this change does not touch."""
    game, actor, red = _make_game()
    actor.organizations = {}  # no non-red faction meets any condition
    game.turn = 20
    game.current_player_index = 0

    # Actor's own turn ends mid-round: turn has not yet advanced past 20.
    _advance_current_player_turn(game)
    assert game.game_phase != GamePhase.FINISHED

    # Red Army (seat 1) ends its turn, wrapping the round: turn -> 21 and the
    # round-wrap _check_victory() declares Red Army the fallback winner.
    _advance_expecting_finish(game)
    assert game.turn == 21
    assert game.game_phase == GamePhase.FINISHED
    assert game.winner == "red_army"
