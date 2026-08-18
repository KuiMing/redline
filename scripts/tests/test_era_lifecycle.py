import random
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.era_engine import EraEngine
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
    game.pending_choice = None
    # Keep this focused on public lifecycle advancement rather than event effects.
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
    # 出牌與購買同屬一個行動階段，只需一次「結束行動階段」就換到下一位玩家。
    assert game.turn_phase == TurnPhase.ACTION
    assert game.advance_turn_phase() == {"success": True}
    assert game.turn_phase == TurnPhase.ACTION


def _legal_inside_wall_towns(game, player):
    return [
        town
        for town in game._towns_for_region_alias("china")
        if game.can_faction_develop_in_town(player.faction_id, town)
    ]


def test_taiwan_era_triggers_at_seven_distinct_inside_wall_organizations_via_phase_lifecycle():
    game, taiwan, _red = _make_game()
    legal_inside_towns = _legal_inside_wall_towns(game, taiwan)
    assert len(legal_inside_towns) >= 7

    taiwan.organizations = {town: 1 for town in legal_inside_towns[:6]}
    _advance_current_player_turn(game)
    assert "taiwan" not in game.era_engine.get_active_eras()

    taiwan.organizations[legal_inside_towns[6]] = 1
    _advance_current_player_turn(game)
    assert "taiwan" in game.era_engine.get_active_eras()
    assert game.era_engine.get_active_era_details()[0]["remaining"] == 2


def test_timed_era_is_not_consumed_on_activation_boundary_or_reactivated_after_expiry():
    game, taiwan, _red = _make_game()
    legal_inside_towns = _legal_inside_wall_towns(game, taiwan)
    taiwan.organizations = {town: 1 for town in legal_inside_towns[:7]}

    # Era trigger detection only runs once a full round wraps (after every player,
    # Red Army included, has acted). Start with Red Army (the last seat) as the
    # current player so a single advance ends its turn and wraps the round,
    # triggering detection — the era must NOT activate on the non-red seat's own
    # turn-end mid-round.
    game.current_player_index = 1
    _advance_current_player_turn(game)
    assert game.era_engine.get_active_era_details()[0]["remaining"] == 2
    activation_discard_count = len(taiwan.deck.discard_pile)
    # The round wrap drew a fresh real event; keep it idle so the following turn
    # ends don't settle it and prompt a choice (unrelated to era duration ticking).
    game.current_event = {"id": "next-idle", "name": "next idle", "type": "idle"}
    game.event_progress = {
        "count": 0,
        "required": 0,
        "succeeded": True,
        "settled": True,
        "status": "idle",
    }

    _advance_current_player_turn(game)
    assert game.era_engine.get_active_era_details()[0]["remaining"] == 1
    game.current_event = {"id": "next-idle", "name": "next idle", "type": "idle"}
    game.event_progress = {
        "count": 0,
        "required": 0,
        "succeeded": True,
        "settled": True,
        "status": "idle",
    }
    _advance_current_player_turn(game)
    assert "taiwan" not in game.era_engine.get_active_eras()
    assert "taiwan" in game.era_engine.get_activated_eras()
    assert len(taiwan.deck.discard_pile) == activation_discard_count


def test_expired_one_time_era_is_achieved_but_not_active_in_viewer_public_state():
    game, taiwan, _red = _make_game()
    legal_inside_towns = _legal_inside_wall_towns(game, taiwan)
    taiwan.organizations = {town: 1 for town in legal_inside_towns[:7]}
    # Detection runs at the round-wrap boundary; advancing Red Army (last seat)
    # completes the round and activates the era.
    game.current_player_index = 1
    _advance_current_player_turn(game)
    game.era_engine.tick()
    game.era_engine.tick()

    stage = game.state(viewer_player_id=taiwan.id)["my_era_stage"]
    assert stage["id"] == "taiwan"
    assert stage["achieved"] is True
    assert stage["active"] is False
    assert stage["remaining"] is None


def test_era_engine_without_activation_history_treats_active_eras_as_activated():
    engine = EraEngine([{
        "id": "legacy-era",
        "name": "legacy era",
        "duration": {"type": "turns", "value": 1},
    }])
    engine.active["legacy-era"] = {
        "remaining": 1,
        "definition": engine.get_definition("legacy-era"),
    }
    del engine.activated

    assert engine.get_activated_eras() == ["legacy-era"]
    assert engine.activate_era("legacy-era") is False
    engine.tick()
    assert engine.get_active_eras() == []
    assert engine.get_activated_eras() == ["legacy-era"]


def test_era_activation_effect_failure_is_not_retried_after_partial_mutation():
    game, taiwan, _red = _make_game()
    legal_inside_towns = _legal_inside_wall_towns(game, taiwan)
    taiwan.organizations = {town: 1 for town in legal_inside_towns[:7]}
    apply_calls = []

    def fail_after_partial_mutation(era):
        apply_calls.append(era["id"])
        taiwan.deck.discard_pile.append("partial activation mutation")
        raise RuntimeError("test partial activation failure")

    game._apply_era_activation_effects = fail_after_partial_mutation
    try:
        game._check_era_trigger()
    except RuntimeError as exc:
        assert str(exc) == "test partial activation failure"
    else:
        raise AssertionError("partial activation failure was not propagated")

    assert "taiwan" in game.era_engine.get_activated_eras()
    assert game._pending_era_activations == []
    assert apply_calls == ["taiwan"]
    assert taiwan.deck.discard_pile[-1] == "partial activation mutation"

    assert game._continue_era_activation_queue() == {
        "success": True,
        "pending_choice": False,
        "queued": [],
    }
    assert apply_calls == ["taiwan"]
    assert taiwan.deck.discard_pile.count("partial activation mutation") == 1


def _configure_same_boundary_auto_discard_event(game):
    game.current_event = {"id": "old-idle", "name": "old idle", "type": "idle"}
    game.event_progress = {
        "count": 0,
        "required": 0,
        "succeeded": True,
        "settled": True,
        "status": "idle",
    }
    game.event_deck.draw_pile = [{
        "id": "test-auto-discard",
        "name": "test auto discard",
        "type": "auto",
        "effect": {"type": "discard_self", "count": 1},
    }]
    game.event_deck.discard_pile = []
    # Ending the final player wraps the round and draws the configured auto event.
    game.current_player_index = 1
    game.round_start_player_index = 0


def test_tibet_red_suppression_defers_to_red_turn_instead_of_blocking_non_red_actor():
    """Deadlock regression（playtest 回報：上海合作組織＋藏國騷亂 同輪，非紅軍陣營回合結束後雙方卡死）.

    藏國騷亂的紅軍壓制是互動效果（紅軍選牌棄掉後建組織）。時代關卡在整輪結束的 round-wrap
    才偵測，此時當前玩家是該輪起始玩家——本例是非紅軍的藏國。舊行為會在此刻直接啟動、把
    pending_choice 掛在紅軍身上：當前的非紅軍玩家被這個「別人的」待選擇卡死整個回合
    （advance_turn_phase／play_card 都被 pending_choice 擋下），而紅軍又不是當前玩家，雙方卡死。
    修法：互動對象非當前玩家的時代啟動延後到該對象自己的回合（比照紅軍事件 auto_pending 的
    延後機制），紅軍在自己的回合處理自己的選擇；同輪抽到的紅軍事件維持 auto_deferred，等時代
    壓制解完才真正套用（事件仍序列在時代之後）。
    """
    game, tibet, red = _make_game("tibet_dharamsala")
    inside_towns = [town for town in _legal_inside_wall_towns(game, tibet) if game._shared_org_count(red, town) == 0]
    assert len(inside_towns) >= 7
    tibet.organizations = {town: 1 for town in inside_towns[:7]}
    _configure_same_boundary_auto_discard_event(game)

    # Round wrap: current becomes the non-red round-start player (Tibet). The era is
    # detected but its interactive choice belongs to Red Army, so activation is DEFERRED
    # (left queued) rather than stranding a choice on the non-red actor.
    _advance_current_player_turn(game)
    assert game.current_player() is tibet
    assert "tibet" not in game.era_engine.get_activated_eras()
    assert game._pending_era_activations == ["tibet"]
    assert game.pending_choice is None
    assert game.event_progress["status"] == "auto_deferred"
    # The non-red actor is NOT blocked — the deadlock is gone. That single
    # 結束行動階段 also finishes Tibet's turn; Red Army takes the seat and the deferred
    # era now activates as Red Army's OWN, resolvable choice.
    assert game.advance_turn_phase() == {"success": True}
    assert game.turn_phase == TurnPhase.ACTION

    assert game.current_player() is red
    assert "tibet" in game.era_engine.get_activated_eras()
    pending = game.pending_choice
    assert pending is not None
    assert pending["choice_key"] == "era_red_discard_to_build_near_target"
    assert pending["player_id"] == red.id
    assert game.event_progress["status"] == "auto_deferred"

    # Red Army resolves the suppression on its own turn; only THEN does the auto event
    # apply — the era still serializes before the event.
    first = game.resolve_pending_choice(red.id, [0])
    assert first.get("pending_choice") is True
    assert game.pending_choice["choice_key"] == "era_red_build_near_target"
    second = game.resolve_pending_choice(red.id, 0)
    assert second.get("pending_choice") is True
    pending = game.pending_choice
    assert pending is not None
    assert pending["choice_key"] == "event_discard_self"
    # Auto event now resolves on Red Army's turn (current player at application time).
    assert pending["player_id"] == red.id
    assert game.event_progress["settled"] is True
    assert game.resolve_pending_choice(red.id, [0]).get("success") is True


def test_manchuria_activation_choice_completes_before_same_boundary_auto_event_choice():
    game, manchuria, _red = _make_game("manchuria")
    inside_towns = [town for town in _legal_inside_wall_towns(game, manchuria) if game._shared_org_count(_red, town) == 0]
    assert len(inside_towns) >= 10
    manchuria.organizations = {town: 1 for town in inside_towns[:10]}
    _configure_same_boundary_auto_discard_event(game)

    _advance_current_player_turn(game)
    assert "manchuria" in game.era_engine.get_active_eras()
    pending = game.pending_choice
    assert pending is not None
    assert pending["choice_key"] == "era_inspect_deck_top_and_reorder"
    assert game.event_progress["status"] == "auto_deferred"

    result = game.resolve_pending_choice(manchuria.id, [0, 1])
    assert result.get("pending_choice") is True
    pending = game.pending_choice
    assert pending is not None
    assert pending["choice_key"] == "event_discard_self"
    assert pending["player_id"] == manchuria.id
    assert game.event_progress["settled"] is True


def test_simultaneous_tibet_and_manchuria_eras_serialize_before_auto_event():
    random.seed(20260728)
    game = Game([("tibet", "tibet"), ("manchuria", "manchuria"), ("red", "red")], market_mode="all_cards")
    tibet, manchuria, red = game.players
    for player, player_id, faction_id in (
        (tibet, "tibet", "tibet_dharamsala"),
        (manchuria, "manchuria", "manchuria"),
        (red, "red", "red_army"),
    ):
        player.id = player_id
        player.name = player_id
        player.faction_id = faction_id
        player.organizations = {}
    inside_towns = [town for town in _legal_inside_wall_towns(game, tibet) if town != "北京"]
    tibet.organizations = {town: 1 for town in inside_towns[:7]}
    manchuria.organizations = {town: 1 for town in inside_towns[7:17]}
    red.organizations = {"北京": 1}
    game.current_player_index = 2
    game.round_start_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.winner = None
    game.pending_choice = None
    _configure_same_boundary_auto_discard_event(game)
    game.current_player_index = 2

    # Round wrap: current becomes the non-red round-start player (Tibet). BOTH detected
    # eras are interactive and target a player who is not Tibet (Red Army for the Tibet
    # suppression, Manchuria for the Manchuria reorder), so both activations are DEFERRED.
    # No pending_choice is stranded on Tibet — the deadlock is gone.
    _advance_current_player_turn(game)
    assert game.current_player() is tibet
    assert game.era_engine.get_activated_eras() == []
    assert game._pending_era_activations == ["tibet", "manchuria"]
    assert game.pending_choice is None
    assert game.event_progress["status"] == "auto_deferred"
    # Each era activates on its own target's turn. Tibet ends → Manchuria takes the seat
    # and the Manchuria reorder activates as Manchuria's own choice; the Tibet suppression
    # stays queued (its target, Red Army, has not acted yet).
    assert game.advance_turn_phase() == {"success": True}

    assert game.current_player() is manchuria
    assert game.era_engine.get_activated_eras() == ["manchuria"]
    assert game._pending_era_activations == ["tibet"]
    assert game.pending_choice["choice_key"] == "era_inspect_deck_top_and_reorder"
    assert game.pending_choice["player_id"] == manchuria.id
    assert game.event_progress["status"] == "auto_deferred"

    manchuria_result = game.resolve_pending_choice(manchuria.id, [0, 1])
    assert manchuria_result.get("success") is True
    assert game.pending_choice is None
    # Tibet suppression still deferred until Red Army's turn; auto event still not applied.
    assert game._pending_era_activations == ["tibet"]
    assert game.event_progress["status"] == "auto_deferred"

    # Manchuria ends → Red Army takes the seat and the Tibet suppression finally activates
    # as Red Army's own choice.
    game.turn_phase = TurnPhase.ACTION
    _advance_current_player_turn(game)
    assert game.current_player() is red
    assert set(game.era_engine.get_activated_eras()) == {"tibet", "manchuria"}
    assert game._pending_era_activations == []
    assert game.pending_choice["choice_key"] == "era_red_discard_to_build_near_target"
    assert game.pending_choice["player_id"] == red.id

    first_tibet = game.resolve_pending_choice(red.id, [0])
    assert first_tibet.get("pending_choice") is True
    assert game.pending_choice["choice_key"] == "era_red_build_near_target"
    second_tibet = game.resolve_pending_choice(red.id, 0)
    assert second_tibet.get("pending_choice") is True
    # Only after BOTH eras have resolved does the auto event apply (on Red Army's turn).
    assert game.pending_choice["choice_key"] == "event_discard_self"
    assert game.pending_choice["player_id"] == red.id
    assert game.event_progress["settled"] is True


def test_era_detection_deferred_to_round_wrap_so_red_army_can_still_invalidate_it():
    """P1 regression（時代關卡觸發時機應等整輪含紅軍行動完才判定）.

    A non-red player satisfies an era's org-count trigger on its own turn, but
    before the round wraps Red Army dissolves one of that player's organizations,
    dropping it back below the threshold. Because trigger *detection* is deferred
    to the round-wrap boundary (after every player incl. Red Army has acted), the
    era must NOT activate — neither mid-round on the non-red turn, nor at the wrap.
    """
    game, taiwan, _red = _make_game()
    legal_inside_towns = _legal_inside_wall_towns(game, taiwan)
    assert len(legal_inside_towns) >= 7
    taiwan.organizations = {town: 1 for town in legal_inside_towns[:7]}

    # Taiwan (seat 0) opens the round already holding 7 inside-wall orgs — the
    # taiwan era's exact trigger condition. Ending its own turn must NOT activate
    # the era: the round has not wrapped and Red Army has not yet acted.
    game.current_player_index = 0
    _advance_current_player_turn(game)
    assert "taiwan" not in game.era_engine.get_active_eras()
    assert "taiwan" not in game.era_engine.get_activated_eras()
    assert game._pending_era_activations == []

    # Red Army acts later in the SAME round and dissolves one of Taiwan's
    # inside-wall organizations, dropping Taiwan to 6 before the round wraps.
    del taiwan.organizations[legal_inside_towns[6]]

    # Ending Red Army's turn wraps the round; detection runs now and sees only 6
    # orgs, so the era must not be (retro-)activated.
    _advance_current_player_turn(game)
    assert game.current_player_index == game.round_start_player_index  # round wrapped
    assert "taiwan" not in game.era_engine.get_active_eras()
    assert "taiwan" not in game.era_engine.get_activated_eras()
    assert game._pending_era_activations == []


def test_era_activates_at_round_wrap_when_condition_survives_red_army_turn():
    """Positive path: the same trigger condition still holds after Red Army's turn,
    so the era DOES activate — but only at the round-wrap boundary, not on the
    non-red player's own mid-round turn."""
    game, taiwan, _red = _make_game()
    legal_inside_towns = _legal_inside_wall_towns(game, taiwan)
    assert len(legal_inside_towns) >= 7
    taiwan.organizations = {town: 1 for town in legal_inside_towns[:7]}

    game.current_player_index = 0
    _advance_current_player_turn(game)
    # Deferred: not detected on Taiwan's own turn mid-round.
    assert "taiwan" not in game.era_engine.get_active_eras()

    # Red Army acts but leaves the condition intact; ending its turn wraps the
    # round and detection finally activates the era.
    _advance_current_player_turn(game)
    assert game.current_player_index == game.round_start_player_index
    assert "taiwan" in game.era_engine.get_active_eras()


def test_queued_interactive_era_keeps_draining_without_a_new_round_wrap():
    """Queue continuation must run independently of the deferred detection scan.

    An era already queued (as if detection enqueued it on a previous round wrap)
    with an interactive activation is drained and resolves across several actions
    on ordinary, non-wrapping turns — it must NOT stall waiting for another round
    to wrap. This is why detection and _continue_era_activation_queue are split.
    """
    game, tibet, red = _make_game("tibet_dharamsala")
    inside_towns = [t for t in _legal_inside_wall_towns(game, tibet) if game._shared_org_count(red, t) == 0]
    assert len(inside_towns) >= 7
    tibet.organizations = {t: 1 for t in inside_towns[:7]}

    # Pre-queue the tibet activation directly, as detection would have on a prior
    # round wrap, but leave it un-activated/mid-flight.
    game._pending_era_activations = ["tibet"]
    # Seat 0 ends -> index 1: NOT a round wrap, so detection does not run. The
    # only thing that can advance the queue here is continuation.
    game.current_player_index = 0
    game.round_start_player_index = 0

    _advance_current_player_turn(game)
    assert game.current_player_index != game.round_start_player_index  # no wrap occurred
    # Continuation drained & activated the queued era on this non-wrapping turn,
    # leaving its interactive red-army activation mid-flight.
    assert "tibet" in game.era_engine.get_activated_eras()
    assert game.pending_choice is not None
    assert game.pending_choice["choice_key"] == "era_red_discard_to_build_near_target"

    # The mid-flight interactive activation resolves across subsequent actions with
    # no further round wrap required.
    first = game.resolve_pending_choice(red.id, [0])
    assert first.get("pending_choice") is True
    assert game.pending_choice["choice_key"] == "era_red_build_near_target"
    game.resolve_pending_choice(red.id, 0)
    assert game._pending_era_activations == []
    assert game.current_player_index != game.round_start_player_index  # still no new wrap
