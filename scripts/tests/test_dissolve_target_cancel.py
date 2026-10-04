"""Regression tests for the cancellable-dissolve-target-selection feature.

Scope: a player who actively plays a dissolve-organization card/support-tier can cancel while
picking the target(s), before committing, with a *complete* rollback (card stays in hand,
no resource/action/supply consumption, no organization changes, no effect or resolution log
entry, pending_choice cleared) -- verified via full state-equality checks, not just spot fields.

Covered cards/tiers (see `DISSOLVE_INTERACTIVE_EFFECT_TYPES` in server/game_card_play.py):
  - 內應間諜 (single-target, no sacrifice)
  - 派遣間諜 (two-phase: sacrifice own org, then dissolve an enemy org)
  - 情報網 option B (single-target, via a `choose_one` gate)
  - 北國奧援 I (two-phase, like 派遣間諜), II (single-target), III (multi-target, count=2)
  - 臺灣奧援 II (single-target), III (single-target + build combo)

Also verifies forced/mandatory dissolve choices (event_red_dissolve, era_red_bonus_dissolve_target)
remain non-cancellable, and that non-owners cannot cancel someone else's pending choice.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import copy

import pytest

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.uyghur_era_red_dissolve import UyghurEraRedDissolveTestRoutes


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def make_game(actor_faction="taiwan_green", enemy_faction="red_army"):
    game = Game([("actor", "Actor"), ("enemy", "Enemy")])
    actor, enemy = game.players
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.current_player_index = 0
    game.pending_base_choices = {}
    actor.faction_id = actor_faction
    enemy.faction_id = enemy_faction
    # 固定成無效果事件，讓測試與事件亂數脫鉤（比照其他 action-card 測試的既有作法）。
    game.current_event = dict(game._event_by_name("歲月靜好"))
    game.event_progress = {"count": 0, "required": 0, "succeeded": True, "settled": True, "status": "idle"}
    game.event_modifiers = []
    game.pending_choice = None
    game.turn_log = game._new_turn_log()
    game.action_log = []
    return game, actor, enemy


def action_card(game, name):
    definition = next(c for c in game.structured_cards if c["name"] == name)
    return Card(definition["name"], definition["type"], definition.get("resources", {}))


def snapshot(game):
    """A structural snapshot of everything the cancel feature promises to leave untouched."""
    return {
        "hands": {p.id: [c.name for c in p.hand] for p in game.players},
        "discards": {p.id: [c.name for c in p.deck.discard_pile] for p in game.players},
        "draw_piles": {p.id: [c.name for c in p.deck.draw_pile] for p in game.players},
        "resources": {p.id: dict(p.resources) for p in game.players},
        "organizations": {p.id: dict(p.organizations) for p in game.players},
        "static_purchase_supply": dict(game.static_purchase_supply),
        "random_purchase_supply": [c.name for c in game.random_purchase_supply] if hasattr(game, "random_purchase_supply") else None,
        "purchase_area": [getattr(c, "name", str(c)) for c in game.purchase_area],
        "turn_phase": game.turn_phase,
        "current_player_index": game.current_player_index,
        # deepcopy -- turn_log holds nested lists/dicts (e.g. played_nonstarter_names,
        # red_army_base_dissolves) that later in-place mutation would otherwise leak back into
        # this "before" snapshot through shared list/dict references.
        "turn_log": copy.deepcopy(game.turn_log),
        "action_log_len": len(game.action_log),
        "pending_choice": copy.deepcopy(game.pending_choice),
    }


def assert_full_rollback(before, after, *, log_entries_allowed=True, ignore_hand_order=False):
    """Every field must be byte-identical except action_log length (informational
    play/cancel log lines are tolerated -- see `cancel_pending_choice`'s own precedent for
    北國奧援: it always logs a "取消了 X" line -- but no *effect* fields may differ).

    ignore_hand_order: when two independently-cancelled flows both re-insert their own card at
    the SAME remembered hand index, restoring them in a different order than they were removed
    can leave the hand containing the exact same cards in a different position (cosmetic, not a
    leak -- no card/resource/organization content differs). Set True to compare hands as
    multisets instead of ordered lists for exactly that scenario.
    """
    for key in before:
        if key == "action_log_len":
            continue
        if key == "hands" and ignore_hand_order:
            before_hands = {pid: sorted(names) for pid, names in before[key].items()}
            after_hands = {pid: sorted(names) for pid, names in after[key].items()}
            assert after_hands == before_hands, f"hands differ (as multisets): before={before_hands!r} after={after_hands!r}"
            continue
        assert after[key] == before[key], f"{key} differs: before={before[key]!r} after={after[key]!r}"
    assert after["pending_choice"] is None
    if not log_entries_allowed:
        assert after["action_log_len"] == before["action_log_len"]


# ---------------------------------------------------------------------------
# 內應間諜 -- single-target, no sacrifice
# ---------------------------------------------------------------------------

def test_embedded_agent_single_target_choice_is_cancellable_with_full_rollback():
    game, actor, enemy = make_game()
    actor.organizations = {"北京": 1}
    enemy.organizations = {"天津": 1}
    actor.hand = [action_card(game, "內應間諜")]

    before = snapshot(game)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert game.pending_choice["choice_key"] == "card_dissolve_interaction"
    assert game.pending_choice["step"] == "target"
    assert game.pending_choice.get("cancellable") is True
    choice_id = game.pending_choice.get("choice_id")

    cancelled = game.cancel_pending_choice(actor.id, expected_choice_id=choice_id)
    assert cancelled.get("success") is True, cancelled
    assert cancelled.get("cancelled") is True

    after = snapshot(game)
    assert_full_rollback(before, after)


def test_embedded_agent_single_target_resolves_immediately_when_confirmed():
    game, actor, enemy = make_game()
    actor.organizations = {"北京": 1}
    enemy.organizations = {"天津": 1}
    actor.hand = [action_card(game, "內應間諜")]

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    index = next(i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] == "天津")

    resolved = game.resolve_pending_choice(actor.id, index)
    assert resolved.get("success") is True, resolved
    assert game.pending_choice is None
    assert enemy.organizations.get("天津", 0) == 0
    assert [c.name for c in actor.deck.discard_pile] == ["內應間諜"]


def test_embedded_agent_with_no_legal_target_never_opens_a_pending_choice():
    game, actor, enemy = make_game()
    actor.organizations = {"臺北": 1}
    enemy.organizations = {}  # nothing within range
    actor.hand = [action_card(game, "內應間諜")]
    before = snapshot(game)

    result = game.play_card(0, mode="action")

    assert result.get("error") == "No target organization within range"
    assert game.pending_choice is None
    after = snapshot(game)
    # Illegal play must be a no-op too (unrelated to cancel, but the same guarantee).
    assert after["hands"] == before["hands"]
    assert after["organizations"] == before["organizations"]


def test_embedded_agent_sole_target_unaffordable_under_mongol_shield_is_a_full_noop():
    # Parent-level review, corrected defect 1: 盟旗學校 (a Mongol faction passive) requires the
    # ATTACKER to discard a hand card to dissolve a Mongol organization. If the attacker cannot
    # pay that cost, the Mongol organization is simply NOT a legal target -- exactly like any
    # other target that fails a range/ownership check -- and must never be offered as a pickable
    # target at all. Repro (a): the attacker's hand becomes empty once 內應間諜 (its only card)
    # is played, and the ONLY enemy organization in range belongs to a Mongol player. The old
    # code still displayed it as the sole target; selecting it returned a 盟旗學校 error and left
    # an unresolvable pending choice (with the card already spent) -- the player was stuck.
    game, actor, enemy = make_game()
    actor.organizations = {"臺北": 1}
    enemy.faction_id = "mongol"
    enemy.base = "太原"
    enemy.organizations = {"新北": 1}  # within range of 臺北, but attacker cannot afford 盟旗學校
    actor.hand = [action_card(game, "內應間諜")]
    before = snapshot(game)

    result = game.play_card(0, mode="action")

    assert result.get("error") == "No target organization within range", result
    assert game.pending_choice is None
    after = snapshot(game)
    # The unaffordable-target rejection must be a full no-op, exactly like the genuinely-no-org
    # case above -- the card must NOT be popped/lost even transiently on the way to this error.
    assert after["hands"] == before["hands"]
    assert after["organizations"] == before["organizations"]


def test_north_support_tier3_never_offers_more_mongol_targets_than_affordable_cumulatively():
    # Companion repro (b) + the cumulative-affordability requirement: a multi-pick flow must
    # never offer more 盟旗學校-protected targets than the attacker can actually pay for across
    # the WHOLE selection. Attacker has exactly 1 hand card left (after playing 北國奧援 III) and
    # 2 Mongol organizations are in range alongside 1 ordinary (unprotected) one -- only 1 of the
    # 2 Mongol organizations may ever be offered as a legal target, never both, and the ordinary
    # target must still be offered normally.
    game = Game([("actor", "Actor"), ("red", "Red"), ("mongol", "Mongol")])
    actor, red, mongol = game.players
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.current_player_index = 0
    game.pending_base_choices = {}
    actor.faction_id = "liberals"
    red.faction_id = "red_army"
    mongol.faction_id = "mongol"
    game.current_event = dict(game._event_by_name("歲月靜好"))
    game.event_progress = {"count": 0, "required": 0, "succeeded": True, "settled": True, "status": "idle"}
    game.event_modifiers = []
    game.pending_choice = None
    game.turn_log = game._new_turn_log()
    game.action_log = []

    actor.base = "北京"
    actor.organizations = {"北京": 1}
    filler_card = Card("填充卡", "command", {})
    actor.hand = [game._make_support_card("北國奧援"), filler_card]
    game._support_card_tier = lambda _player, _card: (3, 0, [])
    red.base = "西安"
    red.organizations = {"天津": 1}
    mongol.base = "太原"
    mongol.organizations = {"石家莊": 1, "承德": 1}

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert [c.name for c in actor.hand] == ["填充卡"], "only the filler card should remain in hand"

    targets = game.pending_choice["targets"]
    mongol_towns_offered = [t["town"] for t in targets if t["town"] in ("石家莊", "承德")]
    assert len(mongol_towns_offered) == 1, (
        "attacker has exactly 1 hand card -- only 1 of the 2 Mongol organizations may ever be "
        f"offered as a legal target, not both: got {mongol_towns_offered}"
    )
    assert any(t["town"] == "天津" for t in targets), "the ordinary (unprotected) target must still be offered"


def test_north_support_tier3_second_pick_listing_offers_remaining_affordable_mongol_target_regardless_of_dict_order():
    # Parent-level review, Critical 2: an already-picked town is still physically present in
    # `other.organizations` (board mutation is deferred to final commit), so a naive
    # implementation that only subtracts a flat count from the starting shield-discard budget
    # while still walking every candidate (already-picked ones included) can have an
    # already-picked town spuriously re-consume budget that was already reserved for it --
    # starving the SECOND, genuinely-still-open, genuinely-affordable Mongol candidate of budget
    # purely as an artifact of `other.organizations` dict iteration order. Repro: attacker has 2
    # spare cards, 3 Mongol organizations in range (only 2 of which can ever be offered
    # together). Pick the FIRST-offered one; the listing for the remaining pick must still
    # correctly offer the second still-affordable Mongol target, not come back empty.
    game = Game([("actor", "Actor"), ("mongol", "Mongol")])
    actor, mongol = game.players
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.current_player_index = 0
    game.pending_base_choices = {}
    actor.faction_id = "liberals"
    mongol.faction_id = "mongol"
    game.current_event = dict(game._event_by_name("歲月靜好"))
    game.event_progress = {"count": 0, "required": 0, "succeeded": True, "settled": True, "status": "idle"}
    game.event_modifiers = []
    game.pending_choice = None
    game.turn_log = game._new_turn_log()
    game.action_log = []

    actor.base = "北京"
    actor.organizations = {"北京": 1}
    filler1 = Card("填充卡1", "command", {})
    filler2 = Card("填充卡2", "command", {})
    actor.hand = [game._make_support_card("北國奧援"), filler1, filler2]
    game._support_card_tier = lambda _player, _card: (3, 0, [])
    # 3 Mongol orgs in range -- with 2 spare hand cards, exactly 2 of these 3 may ever be
    # offered together (never all 3).
    mongol.base = "太原"
    mongol.organizations = {"承德": 1, "石家莊": 1, "天津": 1}

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    initial_towns = [t["town"] for t in game.pending_choice["targets"]]
    assert len(initial_towns) == 2, f"expected exactly 2 of the 3 Mongol orgs offered initially: {initial_towns}"

    # Pick whichever one was offered first (this is the one that iterates first in
    # `mongol.organizations` -- the exact scenario that triggers the dict-order bug).
    first_town = initial_towns[0]
    first_index = next(i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] == first_town)
    picked_first = game.resolve_pending_choice(actor.id, first_index)
    assert picked_first.get("selected_count") == 1, picked_first

    remaining_towns = [t["town"] for t in game.pending_choice["targets"]] if game.pending_choice else []
    expected_remaining = initial_towns[1]
    assert remaining_towns == [expected_remaining], (
        f"second-pick listing must still offer the other still-affordable Mongol target "
        f"({expected_remaining!r}), got {remaining_towns!r} -- a dict-iteration-order artifact "
        f"must not silently under-deliver targets that are genuinely still affordable"
    )


def test_support_card_queued_behind_open_choice_fails_affordability_pre_pop_without_orphaning_the_open_choice():
    # Parent-level review, Critical 1: playing card A (內應間諜) opens an in-progress
    # pending_choice. While it's still open, attempting to queue card B (北國奧援, forced to a
    # single-target dissolve tier) behind it -- whose sole legal target (the only enemy
    # organization on the board) is Mongol-shielded, and which is the attacker's ONLY remaining
    # hand card at that point -- must be rejected cleanly, WITHOUT losing track of card A's own
    # still-open choice.
    #
    # The old bug: `_card_can_queue_map_action`'s (and play_card's own) legality pre-check for
    # card B ran BEFORE card B was popped from hand, so `player.hand` still included card B
    # itself -- inflating affordability by 1 and reporting the Mongol target as pickable when it
    # actually wasn't. That let `queueing_map_card` come back True, which moved card A's
    # pending_choice into `_deferred_build_choice` and popped card B; only THEN did the real
    # post-pop check correctly reject card B (rolling it back into hand) -- but nothing restored
    # `self.pending_choice` from `_deferred_build_choice` on that path, permanently orphaning
    # card A's choice (`game.pending_choice` ends up None with card A fully spent and its own
    # flow never resolved -- and `_resume_card_build_queue_if_idle` would later resurrect that
    # orphaned choice during a DIFFERENT player's turn: a real softlock, not just a lost card).
    #
    # Reserving the about-to-be-played card's own hand slot in the pre-pop check (this round's
    # primary fix) makes the pre-pop and post-pop checks agree, so this now correctly gets
    # rejected BEFORE card B is ever popped/queued at all -- card A's choice is never even
    # touched, which is the strongest form of "no state loss."
    game, actor, mongol = make_game(actor_faction="taiwan_green", enemy_faction="mongol")
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    mongol.base = "太原"
    mongol.organizations = {"天津": 1}  # sole target on the whole board, Mongol-shielded

    card_a = action_card(game, "內應間諜")
    card_b = game._make_support_card("北國奧援")
    actor.hand = [card_a, card_b]
    game._support_card_tier = lambda _player, _card: (2, 0, [])  # single-target dissolve tier

    # Card A: opens an in-progress pending_choice (owned by actor), still unresolved. Its own
    # target listing is itself computed post-pop (hand=[card_b], size 1) so 天津 is correctly
    # still affordable FOR CARD A at this point (nothing has been reserved against it yet).
    played_a = game.play_card(0, mode="action")
    assert played_a.get("pending_choice") is True, played_a
    choice_a_id = game.pending_choice.get("choice_id")
    assert game.pending_choice.get("player_id") == actor.id
    assert [c.name for c in actor.hand] == ["北國奧援"]

    # Card B is now the attacker's ONLY remaining hand card -- queuing it behind card A's still-
    # open choice must fail cleanly (its own play would need to discard a hand card for 盟旗學校,
    # but playing it would leave zero cards to pay that cost with).
    played_b = game.play_card(0, mode="action")

    assert played_b.get("error"), played_b
    assert [c.name for c in actor.hand] == ["北國奧援"], (
        f"card B must still be in hand after a clean rejection: {[c.name for c in actor.hand]}"
    )

    # Card A's own pending_choice must survive completely intact -- not orphaned/lost.
    assert game.pending_choice is not None, (
        "card A's in-progress choice was lost -- card A was fully spent with its effect never "
        "resolved and no way for the player to ever recover it"
    )
    assert game.pending_choice.get("choice_id") == choice_a_id
    assert game.pending_choice.get("player_id") == actor.id

    # And card A's own flow can still be resolved normally afterward.
    index = next(i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] == "天津")
    resolved_a = game.resolve_pending_choice(actor.id, index)
    assert resolved_a.get("success") is True, resolved_a
    assert game.pending_choice is None
    assert mongol.organizations.get("天津", 0) == 0


def test_resume_card_build_queue_never_resurrects_a_deferred_choice_for_the_wrong_player():
    # Parent-level review, Critical 1 (defense-in-depth invariant): _resume_card_build_queue_if_idle
    # must never resurrect self._deferred_build_choice into self.pending_choice when it belongs
    # to someone other than whoever's turn it currently is (self.current_player()) -- doing so
    # would softlock the game (neither the choice's real owner nor the current player could ever
    # resolve it, since resolve_pending_choice requires choice['player_id'] == player_id, and
    # ordinary action-gating would then block all further play). This is a last-resort safety net
    # on top of this round's primary fix (which prevents a legality-check disagreement from ever
    # orphaning a choice into _deferred_build_choice in the first place) -- exercised directly
    # here since the primary fix means this mismatch is no longer reachable through ordinary
    # play_card()/resolve_pending_choice() calls.
    #
    # Deliberately checked against self.current_player(), NOT the `player` argument this method
    # is called with: a LEGITIMATE resume routinely happens on behalf of a different player than
    # the deferred choice's own owner (e.g. called with the REACTOR right after they resolve
    # their own cancel-reaction choice, correctly handing control back to the original actor's
    # still-queued entry) -- that must keep working, which the companion assertion below verifies.
    game, actor, enemy = make_game(actor_faction="taiwan_green", enemy_faction="mongol")
    orphaned_choice = {
        'type': 'support_flow_choice',
        'choice_key': 'card_dissolve_interaction',
        'player_id': actor.id,
        'step': 'target',
        'targets': [],
    }
    game._deferred_build_choice = dict(orphaned_choice)
    game.pending_choice = None

    # Simulate the turn having advanced to a DIFFERENT player than the deferred choice's owner.
    game.current_player_index = game.players.index(enemy)
    result = game._resume_card_build_queue_if_idle(enemy)

    assert result is None
    assert game.pending_choice is None, (
        "a deferred choice belonging to a different player than whoever's turn it currently is "
        f"must never be resurrected into self.pending_choice: {game.pending_choice}"
    )
    assert game._deferred_build_choice is None, "the orphaned choice must be dropped, not left dangling"

    # Companion: it's still the ORIGINAL owner's turn (the ordinary case, and also the
    # after-a-reaction-resolves case, where the `player` argument can legitimately be someone
    # else entirely) -- the deferred choice must still resume normally.
    game.current_player_index = game.players.index(actor)
    game._deferred_build_choice = dict(orphaned_choice)
    result_correct = game._resume_card_build_queue_if_idle(enemy)
    assert result_correct is not None and result_correct.get('success') is True, result_correct
    assert game.pending_choice is not None
    assert game.pending_choice.get('player_id') == actor.id


# ---------------------------------------------------------------------------
# 派遣間諜 -- two-phase: sacrifice own org, then dissolve enemy org
# ---------------------------------------------------------------------------

def test_field_agent_cancel_at_sacrifice_town_stage_is_a_full_rollback():
    game, actor, enemy = make_game()
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    actor.hand = [action_card(game, "派遣間諜")]
    before = snapshot(game)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert game.pending_choice["step"] == "sacrifice_town"
    assert game.pending_choice.get("cancellable") is True
    choice_id = game.pending_choice.get("choice_id")

    cancelled = game.cancel_pending_choice(actor.id, expected_choice_id=choice_id)
    assert cancelled.get("success") is True, cancelled

    after = snapshot(game)
    assert_full_rollback(before, after)


def test_field_agent_cancel_at_target_stage_after_sacrifice_pick_is_still_a_full_rollback():
    game, actor, enemy = make_game()
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    actor.hand = [action_card(game, "派遣間諜")]
    before = snapshot(game)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    sacrificed = game.resolve_pending_choice(actor.id, 0)
    assert sacrificed.get("pending_choice") is True, sacrificed
    assert game.pending_choice["step"] == "target"
    assert game.pending_choice.get("cancellable") is True
    # Requirement #7: no own organization is removed until the FINAL confirmation.
    assert actor.organizations == {"北京": 1, "上海": 1}

    choice_id = game.pending_choice.get("choice_id")
    cancelled = game.cancel_pending_choice(actor.id, expected_choice_id=choice_id)
    assert cancelled.get("success") is True, cancelled

    after = snapshot(game)
    assert_full_rollback(before, after)


def test_field_agent_confirming_both_stages_dissolves_atomically():
    game, actor, enemy = make_game()
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    actor.hand = [action_card(game, "派遣間諜")]

    game.play_card(0, mode="action")
    game.resolve_pending_choice(actor.id, 0)
    assert actor.organizations == {"北京": 1, "上海": 1}
    resolved = game.resolve_pending_choice(actor.id, 0)

    assert resolved.get("success") is True, resolved
    assert game.pending_choice is None
    assert actor.organizations == {"北京": 1}
    assert sum(enemy.organizations.values()) == 2


def test_field_agent_stale_sacrifice_is_rejected_at_final_confirmation():
    # Between the sacrifice pick and the final target confirm, some other effect removes the
    # sacrificed organization from the board -- the final confirmation must re-validate and
    # reject rather than resolve on stale data (requirement #9), and must not partially apply
    # the enemy dissolve either.
    game, actor, enemy = make_game()
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    actor.hand = [action_card(game, "派遣間諜")]

    game.play_card(0, mode="action")
    game.resolve_pending_choice(actor.id, 0)
    assert game.pending_choice["step"] == "target"

    # Simulate the sacrificed organization disappearing out from under the pending choice.
    del actor.organizations["上海"]

    resolved = game.resolve_pending_choice(actor.id, 0)
    assert resolved.get("error") == "Sacrificed organization is no longer valid"
    assert sum(enemy.organizations.values()) == 3


# ---------------------------------------------------------------------------
# 情報網 option B -- single-target dissolve gated behind a choose_one pick
# ---------------------------------------------------------------------------

def test_intel_network_option_b_dissolve_choice_is_cancellable_with_full_rollback():
    game, actor, enemy = make_game()
    actor.organizations = {"北京": 1}
    enemy.organizations = {"天津": 1}
    actor.hand = [action_card(game, "情報網")]
    before = snapshot(game)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert game.pending_choice["choice_key"] == "choose_one"
    b_index = next(i for i, o in enumerate(game.pending_choice["options"]) if o.get("label", "").startswith("Ｂ") or "瓦解" in str(o))

    chosen = game.resolve_pending_choice(actor.id, b_index)
    assert chosen.get("pending_choice") is True, chosen
    assert game.pending_choice["choice_key"] == "intel_network_dissolve_target"
    assert game.pending_choice.get("cancellable") is True
    choice_id = game.pending_choice.get("choice_id")

    cancelled = game.cancel_pending_choice(actor.id, expected_choice_id=choice_id)
    assert cancelled.get("success") is True, cancelled

    after = snapshot(game)
    assert_full_rollback(before, after)


def test_intel_network_option_b_resolves_immediately_when_confirmed():
    game, actor, enemy = make_game()
    actor.organizations = {"北京": 1}
    enemy.organizations = {"天津": 1}
    actor.hand = [action_card(game, "情報網")]

    played = game.play_card(0, mode="action")
    b_index = next(i for i, o in enumerate(game.pending_choice["options"]) if "瓦解" in str(o))
    game.resolve_pending_choice(actor.id, b_index)
    assert game.pending_choice["choice_key"] == "intel_network_dissolve_target"

    resolved = game.resolve_pending_choice(actor.id, 0)
    assert resolved.get("success") is True, resolved
    assert game.pending_choice is None
    assert enemy.organizations.get("天津", 0) == 0


# ---------------------------------------------------------------------------
# 北國奧援 -- I (two-phase), II (single), III (multi, count=2)
# ---------------------------------------------------------------------------

def test_north_support_tier1_cancel_at_either_stage_is_a_full_rollback():
    game, actor, enemy = make_game(actor_faction="liberals")
    actor.base = "巴黎"
    actor.organizations = {"巴黎": 1, "日內瓦": 1}
    actor.hand = [game._make_support_card("北國奧援", variant_index=1)]
    enemy.faction_id = "red_army"
    enemy.base = "北京"
    enemy.organizations = {"慕尼黑": 1}
    before = snapshot(game)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert played.get("tier") == 1
    assert game.pending_choice["step"] == "sacrifice_town"
    assert game.pending_choice.get("cancellable") is True

    cancelled = game.cancel_pending_choice(actor.id)
    assert cancelled.get("success") is True, cancelled
    after = snapshot(game)
    assert_full_rollback(before, after)

    # Replay and cancel at the SECOND stage instead.
    actor.hand = [game._make_support_card("北國奧援", variant_index=1)]
    before2 = snapshot(game)
    game.play_card(0, mode="action")
    game.resolve_pending_choice(actor.id, 0)
    assert game.pending_choice["step"] == "target"
    assert game.pending_choice.get("cancellable") is True
    assert actor.organizations == {"巴黎": 1, "日內瓦": 1}

    cancelled2 = game.cancel_pending_choice(actor.id)
    assert cancelled2.get("success") is True, cancelled2
    after2 = snapshot(game)
    assert_full_rollback(before2, after2)


def test_north_support_tier2_single_target_cancellable_and_resolves_immediately():
    game, actor, enemy = make_game(actor_faction="liberals")
    actor.base = "北京"
    actor.organizations = {"北京": 1}
    actor.hand = [game._make_support_card("北國奧援")]
    game._support_card_tier = lambda _player, _card: (2, 0, [])
    enemy.faction_id = "red_army"
    enemy.base = "西安"
    enemy.organizations = {"天津": 1}
    before = snapshot(game)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert game.pending_choice["step"] == "target"
    assert game.pending_choice.get("cancellable") is True

    cancelled = game.cancel_pending_choice(actor.id)
    assert cancelled.get("success") is True, cancelled
    after = snapshot(game)
    assert_full_rollback(before, after)

    # Replay and confirm instead of cancelling.
    actor.hand = [game._make_support_card("北國奧援")]
    game.play_card(0, mode="action")
    index = 0
    resolved = game.resolve_pending_choice(actor.id, index)
    assert resolved.get("success") is True, resolved
    assert game.pending_choice is None
    assert sum(enemy.organizations.values()) == 0


def test_north_support_tier3_multi_target_select_change_confirm_and_cancel():
    game, actor, enemy = make_game(actor_faction="liberals")
    actor.base = "北京"
    actor.organizations = {"北京": 1}
    actor.hand = [game._make_support_card("北國奧援")]
    game._support_card_tier = lambda _player, _card: (3, 0, [])
    enemy.faction_id = "red_army"
    enemy.base = "西安"
    enemy.organizations = {"天津": 1, "石家莊": 1}
    before = snapshot(game)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert len(game.pending_choice["targets"]) == 2
    assert game.pending_choice.get("cancellable") is True

    # Pick one target -- nothing should be dissolved yet (deferred to the final Confirm).
    first_town = game.pending_choice["targets"][0]["town"]
    first = game.resolve_pending_choice(actor.id, 0)
    assert first.get("pending_choice") is True, first
    assert first.get("selected_count") == 1
    assert first.get("total_count") == 2
    assert sum(enemy.organizations.values()) == 2
    assert game.pending_choice.get("cancellable") is True
    assert first_town not in [t["town"] for t in game.pending_choice["targets"]]

    # Cancel here: full rollback even though one target has already been "selected".
    cancelled = game.cancel_pending_choice(actor.id)
    assert cancelled.get("success") is True, cancelled
    after = snapshot(game)
    assert_full_rollback(before, after)

    # Replay: pick a *different* target this time (changing the selection is free before the
    # final Confirm -- each pick before the last is just a local re-arm), then confirm both.
    actor.hand = [game._make_support_card("北國奧援")]
    game.play_card(0, mode="action")
    second_town = game.pending_choice["targets"][1]["town"]
    second_index = next(i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] == second_town)
    picked_first = game.resolve_pending_choice(actor.id, second_index)
    assert picked_first.get("selected_count") == 1
    assert sum(enemy.organizations.values()) == 2, "still nothing dissolved before the final pick"

    final = game.resolve_pending_choice(actor.id, 0)
    assert final.get("success") is True, final
    assert game.pending_choice is None
    assert final.get("target_count") == 2
    assert sum(enemy.organizations.values()) == 0


def test_north_support_tier3_stale_pick_with_no_replacement_resolves_the_still_valid_target():
    # Parent-level review, defect 2 (CORRECTED premise): 北國奧援 III's actual printed text is
    # 「瓦解己方組織1格內的2個對手組織」 -- dissolve UP TO 2 organizations, not EXACTLY 2.
    # Resolving fewer than 2 when no further legal target exists is correct, intended behavior.
    # So: if one accumulated pick goes stale before final confirmation and NO further legal
    # replacement target exists at all, the correct outcome is to resolve every STILL-VALID
    # selected target now -- even if that's fewer than the card's stated max -- not to fizzle
    # the whole flow. (This test replaces this round's earlier, incorrect regression, which
    # itself codified a full-fizzle expectation built on the wrong all-or-nothing premise.)
    game, actor, enemy = make_game(actor_faction="liberals")
    actor.base = "北京"
    actor.organizations = {"北京": 1}
    actor.hand = [game._make_support_card("北國奧援")]
    game._support_card_tier = lambda _player, _card: (3, 0, [])
    enemy.faction_id = "red_army"
    enemy.base = "西安"
    enemy.organizations = {"天津": 1, "石家莊": 1}

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert len(game.pending_choice["targets"]) == 2

    # Pick 天津 first (accumulates; still not dissolved).
    tianjin_index = next(i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] == "天津")
    picked_first = game.resolve_pending_choice(actor.id, tianjin_index)
    assert picked_first.get("selected_count") == 1
    assert sum(enemy.organizations.values()) == 2

    # 天津 goes stale before the final pick (simulates some other action removing it, e.g. a
    # different player's own dissolve of the same organization in between).
    del enemy.organizations["天津"]

    # Pick the only remaining offered target (石家莊) -- this fills remaining_count to 0 and
    # triggers the final-confirmation code path with one stale (天津) and one live (石家莊) pick,
    # with no further legal target anywhere (only 2 orgs existed on the board to begin with).
    remaining_index = 0
    final = game.resolve_pending_choice(actor.id, remaining_index)

    # Correct outcome: 石家莊 (still legal) gets dissolved; 天津 (stale) is simply excluded from
    # the result -- a partial ("up to 2") commit is the intended behavior here, not a bug.
    assert final.get("success") is True, final
    assert enemy.organizations.get("石家莊", 0) == 0, (
        "石家莊 should have been dissolved: with no legal replacement for the stale 天津 pick, "
        "北國奧援 III's own 'up to 2' wording means the still-valid pick(s) resolve on their own"
    )
    assert final.get("target_count") == 1, final
    assert game.pending_choice is None


def test_north_support_tier3_stale_second_target_resolves_queued_first_target():
    game, actor, enemy = make_game(actor_faction="liberals")
    actor.base = "北京"
    actor.organizations = {"北京": 1}
    actor.hand = [game._make_support_card("北國奧援")]
    game._support_card_tier = lambda _player, _card: (3, 0, [])
    enemy.faction_id = "red_army"
    enemy.base = "西安"
    enemy.organizations = {"天津": 1, "石家莊": 1}

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    tianjin_index = next(
        i for i, target in enumerate(game.pending_choice["targets"])
        if target["town"] == "天津"
    )
    first = game.resolve_pending_choice(actor.id, tianjin_index)
    assert first.get("pending_choice") is True, first
    assert enemy.organizations == {"天津": 1, "石家莊": 1}

    # The only offered second target goes stale before its confirmation.
    shijiazhuang_index = next(
        i for i, target in enumerate(game.pending_choice["targets"])
        if target["town"] == "石家莊"
    )
    del enemy.organizations["石家莊"]
    final = game.resolve_pending_choice(actor.id, shijiazhuang_index)

    assert final.get("success") is True, final
    assert final.get("effect_fizzled") is not True, final
    assert final.get("target_count") == 1, final
    assert enemy.organizations.get("天津", 0) == 0
    assert game.pending_choice is None


def test_north_support_tier3_stale_pick_can_still_be_confirmed_after_re_pick():
    # Companion to the defect-2 regression above: when a legal replacement target DOES exist for
    # a vacated (stale) slot, the choice must still reopen for that re-pick -- confirming again
    # must then atomically dissolve everything (both the earlier still-valid pick and the new
    # one). 承德 (not 上海 -- confirmed independently NOT in range of 北京 for this card, which
    # meant this test's own recovery-path assertions never actually ran; 承德 IS in range, the
    # same town already used correctly in setup_multi_target_stale_final_pick's own test route)
    # is the 3rd org, so the reopened choice genuinely has a legal replacement to re-pick.
    game, actor, enemy = make_game(actor_faction="liberals")
    actor.base = "北京"
    actor.organizations = {"北京": 1}
    actor.hand = [game._make_support_card("北國奧援")]
    game._support_card_tier = lambda _player, _card: (3, 0, [])
    enemy.faction_id = "red_army"
    enemy.base = "西安"
    enemy.organizations = {"天津": 1, "石家莊": 1, "承德": 1}

    game.play_card(0, mode="action")
    tianjin_index = next(i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] == "天津")
    game.resolve_pending_choice(actor.id, tianjin_index)
    del enemy.organizations["天津"]

    shijiazhuang_index = next(i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] == "石家莊")
    rejected = game.resolve_pending_choice(actor.id, shijiazhuang_index)
    assert enemy.organizations.get("石家莊", 0) == 1, "must not have dissolved 石家莊 on the rejected attempt"

    # This branch must actually execute (承德 genuinely reopens as the replacement target) --
    # asserted unconditionally now, not left contingent on an `if`, so a future regression that
    # silently stops reopening the choice fails loudly instead of being skipped.
    assert game.pending_choice is not None, (
        "expected the choice to reopen with 承德 as a legal replacement target"
    )
    assert len(game.pending_choice["targets"]) >= 1
    replacement_index = next(
        i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] == "承德"
    )
    final = game.resolve_pending_choice(actor.id, replacement_index)
    assert final.get("success") is True, final
    assert game.pending_choice is None
    assert enemy.organizations.get("石家莊", 0) == 0
    assert enemy.organizations.get("承德", 0) == 0
    assert enemy.organizations.get("天津", 0) == 0


# ---------------------------------------------------------------------------
# 臺灣奧援 -- II (single-target), III (single-target + build combo)
# ---------------------------------------------------------------------------

def _taiwan_support_game(tier):
    game, actor, enemy = make_game(actor_faction="taiwan_green")
    actor.base = "佬沃"
    actor.organizations = {"屏東": 1, "佬沃": 1, "馬祖": 1}
    actor.hand = [game._make_support_card("臺灣奧援")]
    actor.resources = {"money": 0, "propaganda": 0}
    actor.deck.draw_pile = []
    actor.deck.discard_pile = []
    enemy.faction_id = "red_army"
    enemy.base = "北京"
    enemy.organizations = {"福州": 1}
    enemy.deck.discard_pile = []

    original_resolver = game._support_card_tier

    def forced_tier(player, card):
        if getattr(player, "id", None) == actor.id and getattr(card, "name", str(card)) == "臺灣奧援":
            return tier, 0, ["東洋", "南洋"]
        return original_resolver(player, card)

    game._support_card_tier = forced_tier
    return game, actor, enemy


def test_taiwan_support_tier2_single_target_cancellable_with_full_rollback():
    game, actor, enemy = _taiwan_support_game(2)
    before = snapshot(game)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert game.pending_choice.get("cancellable") is True

    cancelled = game.cancel_pending_choice(actor.id)
    assert cancelled.get("success") is True, cancelled
    after = snapshot(game)
    assert_full_rollback(before, after)


def test_taiwan_support_tier3_dissolve_and_build_cancellable_with_full_rollback():
    game, actor, enemy = _taiwan_support_game(3)
    before = snapshot(game)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert played.get("effect_type") == "interactive_dissolve_and_build"
    assert game.pending_choice.get("cancellable") is True

    cancelled = game.cancel_pending_choice(actor.id)
    assert cancelled.get("success") is True, cancelled
    after = snapshot(game)
    assert_full_rollback(before, after)

    # Confirm instead: dissolve then build lands atomically as before (unaffected).
    actor.hand = [game._make_support_card("臺灣奧援")]
    game.play_card(0, mode="action")
    resolved = game.resolve_pending_choice(actor.id, 0)
    assert resolved.get("built") is True, resolved
    assert actor.organizations.get("福州", 0) == 1
    assert enemy.organizations.get("福州", 0) == 0


# ---------------------------------------------------------------------------
# Regression: play-then-cancel must not leak post-play faction-ability triggers
# (independent review finding -- money/propaganda-cost-triggered abilities like 商貿組織 fire
# as soon as a card is committed to play, e.g. drawing a card and latching
# turn_log['faction_first_money_triggered']. Since these dissolve flows only commit the card
# once cancel_pending_choice can no longer be called (see DISSOLVE_INTERACTIVE_EFFECT_TYPES'
# deferred-mutation design above), any such trigger fired eagerly at choice-open time -- before
# the flow's real final confirmation -- must ALSO be deferred, or a cancel would restore the
# card/hand/organizations but leave the drawn card and latched turn_log flag behind: a free,
# repeatable resource-generation exploit via play-then-cancel every turn.
# ---------------------------------------------------------------------------

def test_embedded_agent_cancel_does_not_leak_money_triggered_faction_ability():
    # federalists' 商貿組織: first money-cost card played each turn draws 1 card.
    game, actor, enemy = make_game(actor_faction="federalists")
    actor.organizations = {"北京": 1}
    enemy.organizations = {"天津": 1}
    actor.hand = [action_card(game, "內應間諜")]
    before = snapshot(game)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    # The trigger must not have fired yet -- the choice is still cancellable.
    assert game.turn_log.get("faction_first_money_triggered") in (None, False)
    assert [c.name for c in actor.hand] == []

    cancelled = game.cancel_pending_choice(actor.id)
    assert cancelled.get("success") is True, cancelled

    after = snapshot(game)
    assert_full_rollback(before, after)
    assert after["turn_log"].get("faction_first_money_triggered") in (None, False)


def test_embedded_agent_confirm_still_fires_money_triggered_faction_ability():
    # Non-regression: the deferral must not prevent the trigger from firing on a real resolve.
    game, actor, enemy = make_game(actor_faction="federalists")
    actor.organizations = {"北京": 1}
    enemy.organizations = {"天津": 1}
    actor.hand = [action_card(game, "內應間諜")]
    actor.deck.draw_pile = list(actor.deck.draw_pile) + [Card("商貿組織抽到", "command", {})]

    game.play_card(0, mode="action")
    index = next(i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] == "天津")
    resolved = game.resolve_pending_choice(actor.id, index)

    assert resolved.get("success") is True, resolved
    assert game.turn_log.get("faction_first_money_triggered") is True
    assert [c.name for c in actor.hand] == ["商貿組織抽到"]
    assert sum("triggered 商貿組織" in entry for entry in game.action_log) == 1


def test_field_agent_cancel_at_sacrifice_stage_does_not_leak_money_triggered_faction_ability():
    game, actor, enemy = make_game(actor_faction="federalists")
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    actor.hand = [action_card(game, "派遣間諜")]
    before = snapshot(game)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert game.turn_log.get("faction_first_money_triggered") in (None, False)

    cancelled = game.cancel_pending_choice(actor.id)
    assert cancelled.get("success") is True, cancelled

    after = snapshot(game)
    assert_full_rollback(before, after)
    assert after["turn_log"].get("faction_first_money_triggered") in (None, False)


def test_field_agent_cancel_at_target_stage_does_not_leak_money_triggered_faction_ability():
    # The exploit as originally reported: confirm stage 1 (which does NOT itself fire the
    # trigger -- see the sacrifice-stage test above), THEN cancel stage 2. Before the fix, the
    # trigger fired the moment the (stage-1) choice opened and was never revisited on a later
    # stage's cancel.
    game, actor, enemy = make_game(actor_faction="federalists")
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    actor.hand = [action_card(game, "派遣間諜")]
    before = snapshot(game)

    game.play_card(0, mode="action")
    sacrificed = game.resolve_pending_choice(actor.id, 0)
    assert sacrificed.get("pending_choice") is True, sacrificed
    assert game.turn_log.get("faction_first_money_triggered") in (None, False)
    assert [c.name for c in actor.hand] == []

    cancelled = game.cancel_pending_choice(actor.id)
    assert cancelled.get("success") is True, cancelled

    after = snapshot(game)
    assert_full_rollback(before, after)
    assert after["turn_log"].get("faction_first_money_triggered") in (None, False)


def test_field_agent_confirm_still_fires_money_triggered_faction_ability_once():
    game, actor, enemy = make_game(actor_faction="federalists")
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    actor.hand = [action_card(game, "派遣間諜")]
    actor.deck.draw_pile = list(actor.deck.draw_pile) + [Card("商貿組織抽到", "command", {})]

    game.play_card(0, mode="action")
    game.resolve_pending_choice(actor.id, 0)
    assert game.turn_log.get("faction_first_money_triggered") in (None, False)
    resolved = game.resolve_pending_choice(actor.id, 0)

    assert resolved.get("success") is True, resolved
    assert game.turn_log.get("faction_first_money_triggered") is True
    assert [c.name for c in actor.hand] == ["商貿組織抽到"]
    assert sum("triggered 商貿組織" in entry for entry in game.action_log) == 1


def test_north_support_tier1_cancel_at_target_stage_does_not_leak_money_triggered_faction_ability():
    game, actor, enemy = make_game(actor_faction="federalists")
    actor.base = "巴黎"
    actor.organizations = {"巴黎": 1, "日內瓦": 1}
    actor.hand = [game._make_support_card("北國奧援", variant_index=1)]
    enemy.faction_id = "red_army"
    enemy.base = "北京"
    enemy.organizations = {"慕尼黑": 1}
    before = snapshot(game)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert played.get("tier") == 1
    sacrificed = game.resolve_pending_choice(actor.id, 0)
    assert sacrificed.get("pending_choice") is True, sacrificed
    assert game.turn_log.get("faction_first_money_triggered") in (None, False)

    cancelled = game.cancel_pending_choice(actor.id)
    assert cancelled.get("success") is True, cancelled

    after = snapshot(game)
    assert_full_rollback(before, after)
    assert after["turn_log"].get("faction_first_money_triggered") in (None, False)


def test_intel_network_option_b_cancel_does_not_leak_money_triggered_faction_ability():
    game, actor, enemy = make_game(actor_faction="federalists")
    actor.organizations = {"北京": 1}
    enemy.organizations = {"天津": 1}
    actor.hand = [action_card(game, "情報網")]
    before = snapshot(game)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert game.pending_choice["choice_key"] == "choose_one"
    # The trigger must not fire even at the choose_one gate -- picking B below can still lead to
    # a cancellable nested choice.
    assert game.turn_log.get("faction_first_money_triggered") in (None, False)
    b_index = next(i for i, o in enumerate(game.pending_choice["options"]) if "瓦解" in str(o))

    chosen = game.resolve_pending_choice(actor.id, b_index)
    assert chosen.get("pending_choice") is True, chosen
    assert game.pending_choice["choice_key"] == "intel_network_dissolve_target"
    assert game.turn_log.get("faction_first_money_triggered") in (None, False)
    assert [c.name for c in actor.hand] == []

    cancelled = game.cancel_pending_choice(actor.id)
    assert cancelled.get("success") is True, cancelled

    after = snapshot(game)
    assert_full_rollback(before, after)
    assert after["turn_log"].get("faction_first_money_triggered") in (None, False)


def test_intel_network_option_b_confirm_still_fires_money_triggered_faction_ability():
    game, actor, enemy = make_game(actor_faction="federalists")
    actor.organizations = {"北京": 1}
    enemy.organizations = {"天津": 1}
    actor.hand = [action_card(game, "情報網")]
    actor.deck.draw_pile = list(actor.deck.draw_pile) + [Card("商貿組織抽到", "command", {})]

    game.play_card(0, mode="action")
    b_index = next(i for i, o in enumerate(game.pending_choice["options"]) if "瓦解" in str(o))
    game.resolve_pending_choice(actor.id, b_index)
    resolved = game.resolve_pending_choice(actor.id, 0)

    assert resolved.get("success") is True, resolved
    assert game.turn_log.get("faction_first_money_triggered") is True
    assert [c.name for c in actor.hand] == ["商貿組織抽到"]
    assert sum("triggered 商貿組織" in entry for entry in game.action_log) == 1


def test_intel_network_via_declined_reaction_does_not_leak_money_triggered_faction_ability():
    # 4th independent-review finding: 情報網 falls through to `_resume_reaction_pending_action`'s
    # OWN copy of play_card's "resolve deferred play -> apply faction triggers" tail whenever an
    # opponent merely HOLDS an unconditionally-eligible reaction card (爆料黑幕/產業滲透/情報網),
    # regardless of whether they actually react -- this is ordinary, no-special-setup-required
    # game flow (see _reaction_card_cancel_predicate). That second tail lacked the same
    # 情報網-aware deferral play_card's own tail has, so it fired the faction trigger immediately
    # (before the player even reached the choose_one gate) AND, with this feature's ref-counted
    # turn_log tracking, double-noted the cost contribution (play_card's own eager note already
    # ran before the reaction prompt opened) -- leaving played_money_card/played_propaganda_card
    # PERMANENTLY stuck True for the rest of the turn even after a full, "successful" cancel,
    # since the single matching decrement could never catch up to the double increment.
    game, actor, enemy = make_game(actor_faction="federalists")
    actor.organizations = {"北京": 1}
    enemy.faction_id = "red_army"
    enemy.organizations = {"天津": 1}
    enemy.hand = [Card("爆料黑幕", "reaction", {})]
    actor.hand = [action_card(game, "情報網")]
    before = snapshot(game)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert game.pending_choice.get("choice_key") == "cancel_other_player_action"
    assert game.turn_log.get("_money_cost_card_refs") == 1

    declined = game.resolve_pending_choice(enemy.id, 0)
    assert declined.get("success") is True, declined
    assert game.pending_choice["choice_key"] == "choose_one"
    # Must NOT have double-counted this card's own contribution just by resuming past a merely-
    # held (never actually played) reaction card, and must NOT have fired the trigger yet -- the
    # player hasn't even picked A/B/C.
    assert game.turn_log.get("_money_cost_card_refs") == 1
    assert game.turn_log.get("faction_first_money_triggered") in (None, False)
    assert [c.name for c in actor.hand] == []

    b_index = next(i for i, o in enumerate(game.pending_choice["options"]) if "瓦解" in str(o))
    chosen = game.resolve_pending_choice(actor.id, b_index)
    assert chosen.get("pending_choice") is True, chosen
    assert game.pending_choice["choice_key"] == "intel_network_dissolve_target"
    assert game.turn_log.get("_money_cost_card_refs") == 1
    assert game.turn_log.get("faction_first_money_triggered") in (None, False)

    cancelled = game.cancel_pending_choice(actor.id)
    assert cancelled.get("success") is True, cancelled

    after = snapshot(game)
    assert_full_rollback(before, after)
    assert after["turn_log"].get("faction_first_money_triggered") in (None, False)
    assert after["turn_log"].get("_money_cost_card_refs") == 0
    assert after["turn_log"].get("played_money_card") is False


def test_intel_network_via_declined_reaction_confirm_still_fires_trigger_once():
    # Non-regression: the fix above must not prevent the trigger from firing (exactly once) when
    # the flow is actually confirmed instead of cancelled.
    game, actor, enemy = make_game(actor_faction="federalists")
    actor.organizations = {"北京": 1}
    enemy.faction_id = "red_army"
    enemy.organizations = {"天津": 1}
    enemy.hand = [Card("爆料黑幕", "reaction", {})]
    actor.hand = [action_card(game, "情報網")]
    actor.deck.draw_pile = list(actor.deck.draw_pile) + [Card("商貿組織抽到", "command", {})]

    game.play_card(0, mode="action")
    game.resolve_pending_choice(enemy.id, 0)  # decline
    b_index = next(i for i, o in enumerate(game.pending_choice["options"]) if "瓦解" in str(o))
    game.resolve_pending_choice(actor.id, b_index)
    resolved = game.resolve_pending_choice(actor.id, 0)

    assert resolved.get("success") is True, resolved
    assert game.turn_log.get("faction_first_money_triggered") is True
    assert game.turn_log.get("_money_cost_card_refs") == 1
    assert [c.name for c in actor.hand] == ["商貿組織抽到"]
    assert sum("triggered 商貿組織" in entry for entry in game.action_log) == 1


# ---------------------------------------------------------------------------
# Regression: 派遣間諜/內應間諜 played while an opponent merely holds (and then declines) a
# reaction-eligible card must still open their dissolve-target choice via the same
# _start_card_dissolve_interaction path play_card's own direct route uses -- not silently fall
# through to generic action-engine logic (these cards carry no "effect" array for that generic
# pipeline to execute), which discards the card, fires cost/faction-ability hooks, and produces
# NO dissolve at all. (Parent-level review, defect 3.)
# ---------------------------------------------------------------------------

def test_field_agent_via_declined_reaction_still_opens_dissolve_choice():
    game, actor, enemy = make_game()
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.faction_id = "red_army"
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    enemy.hand = [Card("爆料黑幕", "reaction", {})]
    actor.hand = [action_card(game, "派遣間諜")]
    before_hand_len = len(actor.hand)

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert game.pending_choice.get("choice_key") == "cancel_other_player_action"

    declined = game.resolve_pending_choice(enemy.id, 0)
    assert declined.get("success") is True, declined
    # The card must not have been silently discarded with nothing to show for it: the dissolve
    # interaction's own (cancellable) choice must actually be open.
    assert game.pending_choice is not None, (
        "no pending choice opened after the declined reaction -- 派遣間諜 was discarded for "
        "nothing"
    )
    assert game.pending_choice.get("choice_key") == "card_dissolve_interaction"
    assert game.pending_choice.get("step") == "sacrifice_town"
    assert game.pending_choice.get("cancellable") is True
    assert [c.name for c in actor.deck.discard_pile] == ["派遣間諜"]
    assert len(actor.hand) == before_hand_len - 1

    # And it plays out exactly like the direct (no-reactor) path from here: cancel fully
    # restores the card, or confirming both stages dissolves normally.
    cancelled = game.cancel_pending_choice(actor.id)
    assert cancelled.get("success") is True, cancelled
    assert [c.name for c in actor.hand] == ["派遣間諜"]
    assert actor.deck.discard_pile == []
    assert actor.organizations == {"北京": 1, "上海": 1}
    assert enemy.organizations == {"天津": 1, "杭州": 1, "香港城": 1}


def test_field_agent_via_declined_reaction_confirm_still_dissolves():
    game, actor, enemy = make_game()
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.faction_id = "red_army"
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    enemy.hand = [Card("爆料黑幕", "reaction", {})]
    actor.hand = [action_card(game, "派遣間諜")]

    game.play_card(0, mode="action")
    game.resolve_pending_choice(enemy.id, 0)  # decline
    assert game.pending_choice.get("choice_key") == "card_dissolve_interaction"
    sacrificed = game.resolve_pending_choice(actor.id, 0)
    assert sacrificed.get("pending_choice") is True, sacrificed
    final = game.resolve_pending_choice(actor.id, 0)

    assert final.get("success") is True, final
    assert game.pending_choice is None
    assert actor.organizations == {"北京": 1}
    assert sum(enemy.organizations.values()) == 2


def test_embedded_agent_via_declined_reaction_still_opens_dissolve_choice():
    game, actor, enemy = make_game()
    actor.organizations = {"北京": 1}
    enemy.faction_id = "red_army"
    enemy.organizations = {"天津": 1}
    enemy.hand = [Card("爆料黑幕", "reaction", {})]
    actor.hand = [action_card(game, "內應間諜")]

    game.play_card(0, mode="action")
    declined = game.resolve_pending_choice(enemy.id, 0)

    assert declined.get("success") is True, declined
    assert game.pending_choice is not None, (
        "no pending choice opened after the declined reaction -- 內應間諜 was discarded for "
        "nothing"
    )
    assert game.pending_choice.get("choice_key") == "card_dissolve_interaction"
    assert game.pending_choice.get("step") == "target"
    assert game.pending_choice.get("cancellable") is True

    index = next(i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] == "天津")
    resolved = game.resolve_pending_choice(actor.id, index)
    assert resolved.get("success") is True, resolved
    assert enemy.organizations.get("天津", 0) == 0


# ---------------------------------------------------------------------------
# Forced/mandatory dissolve choices must NOT become cancellable
# ---------------------------------------------------------------------------

def test_event_red_dissolve_forced_choice_is_not_cancellable():
    game = Game([("p1", "red"), ("p2", "other")])
    red, other = game.players
    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}
    other.faction_id = "hong_kong"
    other.base = "香港城"
    other.organizations = {"天津": 1}
    game.current_event = {"name": "Test Event"}

    result = game._apply_event_effect_red_dissolve({"scope": "牆內"}, other)
    assert result == {"success": True, "pending_choice": True}
    assert game.pending_choice.get("choice_key") == "event_red_dissolve"
    assert not game.pending_choice.get("cancellable")

    cancelled = game.cancel_pending_choice(red.id)
    assert cancelled.get("error") == "This choice cannot be cancelled"
    assert game.pending_choice is not None


def test_era_red_bonus_dissolve_target_forced_choice_is_not_cancellable():
    runtime = GameSetupRuntime(
        manager=type("FakeManager", (), {"__init__": lambda self: setattr(self, "games", {}) or setattr(self, "connections", {})})(),
        lobby={}, lobby_hosts={}, lobby_factions={}, lobby_bases={}, lobby_ready={},
    )
    result = UyghurEraRedDissolveTestRoutes(lambda: runtime).test_setup_uyghur_era_red_dissolve_proof({})
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    _actor, red = game.players

    assert game.pending_choice["choice_key"] == "era_red_bonus_dissolve_target"
    assert not game.pending_choice.get("cancellable")

    cancelled = game.cancel_pending_choice(red.id)
    assert cancelled.get("error") == "This choice cannot be cancelled"
    assert game.pending_choice is not None


# ---------------------------------------------------------------------------
# Regression: interleaved flows (a second card queued behind an unresolved first one) must not
# let a deferred faction-ability trigger fire early or leak past a cancel of either flow
# (2nd independent-review finding). Queueing a card's map-interaction behind an already-active
# pending choice is ordinary, frequently-tested game machinery (see
# scripts/tests/test_build_entitlement_queue.py) -- no special setup needed, reachable through
# normal play. The exploit chain: play card A (opens a cancellable dissolve choice), play card B
# (a two-stage or gated flow) while A is still unresolved so B's flow gets queued/deferred behind
# A, resolve B's first (non-map-classified) stage -- this swaps which flow is
# `self.pending_choice` vs. parked in the queue/deferred slot -- then cancel BOTH flows in turn.
# Zero net resource/card leakage must hold regardless of which flow ends up "active" vs. "parked"
# at any point, and regardless of how many places a paused choice can be parked
# (self.pending_choice / self._queued_card_build_choices / self._deferred_build_choice).
# ---------------------------------------------------------------------------

def test_two_stage_card_queued_behind_another_unresolved_card_cancel_both_leaks_nothing():
    # federalists' 商貿組織: first money-cost card played each turn draws 1 card. Card A =
    # 內應間諜 (single-target), Card B = 北國奧援 tier I (two-stage: sacrifice_town, then target).
    game, actor, enemy = make_game(actor_faction="federalists")
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.faction_id = "red_army"
    enemy.base = "西安"
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    actor.hand = [action_card(game, "內應間諜"), game._make_support_card("北國奧援", variant_index=1)]
    before = snapshot(game)

    played_a = game.play_card(0, mode="action")
    assert played_a.get("pending_choice") is True, played_a
    played_b = game.play_card(0, mode="action")
    assert played_b.get("pending_choice") is True, played_b
    assert played_b.get("tier") == 1

    # Resolve B's first (sacrifice_town) stage -- NOT classified as a map interaction
    # (choice_is_card_map_interaction only recognizes step=='target'), which is exactly the
    # interleaving that swaps which flow ends up as self.pending_choice vs. queued/deferred.
    current = game.pending_choice
    assert current.get("choice_key") == "support_interaction"
    assert current.get("step") == "sacrifice_town"
    resolved_stage1 = game.resolve_pending_choice(actor.id, 0)
    assert resolved_stage1.get("pending_choice") is True, resolved_stage1
    # Neither card's deferred trigger may have fired yet -- both flows are still cancellable.
    assert game.turn_log.get("faction_first_money_triggered") in (None, False)
    assert [c.name for c in actor.hand] == []

    # Cancel whichever flow is currently active, then cancel the other (now reactivated).
    first_cancel = game.cancel_pending_choice(actor.id)
    assert first_cancel.get("success") is True, first_cancel
    assert game.pending_choice is not None, "the other flow's parked choice must reactivate"
    second_cancel = game.cancel_pending_choice(actor.id)
    assert second_cancel.get("success") is True, second_cancel

    after = snapshot(game)
    # Full state-equality check, turn_log included: both cards are fully back in hand, no cards
    # drawn, no discard/resource/organization change, no pending choice left open, the deferred
    # faction trigger never fired, AND the reference-counted played_money_card/
    # played_propaganda_card/played_nonstarter_names bookkeeping is exactly clean (not just
    # "looks False" but the underlying _*_refs counters are back to zero -- see
    # _note_*/_undo_* helpers) despite this cancelling in PLAY order (A then B), not
    # reverse-of-play/LIFO order. Hand ORDER can differ (each cancel restores its own card at its
    # own remembered index -- cosmetic, not a leak; see assert_full_rollback's ignore_hand_order
    # docstring) when two flows are un-nested this way.
    assert_full_rollback(before, after, ignore_hand_order=True)
    assert after["turn_log"].get("faction_first_money_triggered") in (None, False)
    assert sorted(after["hands"][actor.id]) == sorted(["北國奧援", "內應間諜"])


def test_intel_network_queued_behind_another_unresolved_card_cancel_both_leaks_nothing():
    # Card A = 內應間諜 (single-target), Card B = 情報網 (choose_one gate -- never engages the
    # build/dissolve queue at all, so A's choice is parked in `_deferred_build_choice` instead
    # while B's choose_one becomes active).
    game, actor, enemy = make_game(actor_faction="federalists")
    actor.organizations = {"北京": 1}
    enemy.faction_id = "red_army"
    enemy.organizations = {"天津": 1, "杭州": 1}
    actor.hand = [action_card(game, "內應間諜"), action_card(game, "情報網")]
    before = snapshot(game)

    played_a = game.play_card(0, mode="action")
    assert played_a.get("pending_choice") is True, played_a
    played_b = game.play_card(0, mode="action")
    assert played_b.get("pending_choice") is True, played_b
    assert game.pending_choice["choice_key"] == "choose_one"
    assert game._deferred_build_choice is not None

    b_index = next(i for i, o in enumerate(game.pending_choice["options"]) if "瓦解" in str(o))
    chosen = game.resolve_pending_choice(actor.id, b_index)
    assert chosen.get("pending_choice") is True, chosen
    # Neither card's deferred trigger may have fired yet.
    assert game.turn_log.get("faction_first_money_triggered") in (None, False)
    assert [c.name for c in actor.hand] == []

    first_cancel = game.cancel_pending_choice(actor.id)
    assert first_cancel.get("success") is True, first_cancel
    assert game.pending_choice is not None, "the other flow's parked choice must reactivate"
    second_cancel = game.cancel_pending_choice(actor.id)
    assert second_cancel.get("success") is True, second_cancel

    after = snapshot(game)
    # Full state-equality check, turn_log included (see the sibling 北國奧援 test above).
    assert_full_rollback(before, after, ignore_hand_order=True)
    assert after["turn_log"].get("faction_first_money_triggered") in (None, False)
    assert sorted(after["hands"][actor.id]) == sorted(["情報網", "內應間諜"])


def test_two_stage_card_queued_then_both_confirmed_still_fires_each_trigger_once():
    # Non-regression: interleaving two flows must not prevent EITHER trigger from firing
    # exactly once when both are actually confirmed (not cancelled).
    game, actor, enemy = make_game(actor_faction="federalists")
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.faction_id = "red_army"
    enemy.base = "西安"
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    actor.hand = [action_card(game, "內應間諜"), game._make_support_card("北國奧援", variant_index=1)]
    actor.deck.draw_pile = list(actor.deck.draw_pile) + [Card("商貿組織抽到", "command", {})]

    game.play_card(0, mode="action")
    game.play_card(0, mode="action")
    game.resolve_pending_choice(actor.id, 0)  # B's sacrifice_town stage
    assert game.turn_log.get("faction_first_money_triggered") in (None, False)

    # Confirm whichever flow is active (A's target choice), then confirm B's target choice too.
    resolved_1 = game.resolve_pending_choice(actor.id, 0)
    assert resolved_1.get("success") is True, resolved_1
    assert game.turn_log.get("faction_first_money_triggered") is True
    assert sum("triggered 商貿組織" in entry for entry in game.action_log) == 1

    assert game.pending_choice is not None
    resolved_2 = game.resolve_pending_choice(actor.id, 0)
    assert resolved_2.get("success") is True, resolved_2
    assert game.pending_choice is None
    # Still exactly once overall -- 商貿組織 only triggers on the FIRST money-cost card each turn.
    assert sum("triggered 商貿組織" in entry for entry in game.action_log) == 1


def test_interleaved_double_cancel_does_not_enable_an_early_combo_reward():
    # 3rd independent-review repro A: a phantom entry in turn_log['played_nonstarter_names']
    # surviving a full double-cancel of two interleaved flows could let manchuria's 展現實力
    # ability ("3 distinct non-starter plays this turn" -> pending choice for a reward) fire
    # after only 2 REAL plays. 展現實力 is a passive faction ability checked automatically after
    # EVERY card play (_apply_card_play_faction_abilities -> _maybe_trigger_combo_reward), not a
    # card of its own. Reproduces the exact interleaving (內應間諜 + 北國奧援 tier I, cancelled in
    # play order), then plays 2 more genuinely-distinct filler cards and asserts the reward does
    # NOT fire (would require a 3rd distinct play if the phantom entries were truly gone), then
    # plays a genuine 3rd and confirms the reward DOES fire there -- proving the fix didn't also
    # break the legitimate trigger.
    game, actor, enemy = make_game(actor_faction="manchuria")
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.faction_id = "red_army"
    enemy.base = "西安"
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    actor.hand = [
        action_card(game, "內應間諜"),
        game._make_support_card("北國奧援", variant_index=1),
        Card("非起始牌甲", "command", {}),
        Card("非起始牌乙", "command", {}),
        Card("非起始牌丙", "command", {}),
    ]

    game.play_card(0, mode="action")
    game.play_card(0, mode="action")
    game.resolve_pending_choice(actor.id, 0)
    game.cancel_pending_choice(actor.id)
    game.cancel_pending_choice(actor.id)
    assert game.turn_log["played_nonstarter_names"] == []
    assert game.turn_log["combo_reward_triggered"] is False

    filler_a = next(i for i, c in enumerate(actor.hand) if c.name == "非起始牌甲")
    game.play_card(filler_a, mode="action")
    assert game.turn_log["played_nonstarter_names"] == ["非起始牌甲"]
    assert game.turn_log["combo_reward_triggered"] is False

    filler_b = next(i for i, c in enumerate(actor.hand) if c.name == "非起始牌乙")
    game.play_card(filler_b, mode="action")
    assert len(game.turn_log["played_nonstarter_names"]) == 2
    assert game.turn_log["combo_reward_triggered"] is False, (
        "展現實力's combo reward fired after only 2 real plays -- the phantom nonstarter-name "
        "entry from the cancelled flows leaked through"
    )

    # A genuine 3rd distinct play: the reward SHOULD legitimately fire here.
    filler_c = next(i for i, c in enumerate(actor.hand) if c.name == "非起始牌丙")
    result = game.play_card(filler_c, mode="action")
    assert result.get("success") is True, result
    assert len(game.turn_log["played_nonstarter_names"]) == 3
    assert game.turn_log["combo_reward_triggered"] is True


def test_interleaved_double_cancel_does_not_grant_a_leaked_bonus_draw():
    # 3rd independent-review repro B: turn_log['played_propaganda_card'] stuck True after a full
    # double-cancel of two interleaved flows would let a freshly-played 點燃熱情 draw its bonus
    # card (conditional_draw on played_propaganda_card, server/effect_engine.py) it should not be
    # entitled to. Compares against a clean-turn_log control run for an exact expected draw count.
    def play_out(game, actor, enemy):
        actor.base = "北京"
        actor.organizations = {"北京": 1, "上海": 1}
        enemy.faction_id = "red_army"
        enemy.base = "西安"
        enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
        actor.hand = [
            action_card(game, "內應間諜"),
            game._make_support_card("北國奧援", variant_index=1),
            action_card(game, "點燃熱情"),
        ]
        actor.deck.draw_pile = [Card(f"補牌{i}", "command", {}) for i in range(10)]

    # Control: play only 點燃熱情 (no interleaving at all) -- establishes the correct draw count.
    control_game, control_actor, control_enemy = make_game(actor_faction="taiwan_green")
    play_out(control_game, control_actor, control_enemy)
    hot_index_control = next(i for i, c in enumerate(control_actor.hand) if c.name == "點燃熱情")
    control_hand_len = len(control_actor.hand)
    control_result = control_game.play_card(hot_index_control, mode="action")
    assert control_result.get("success") is True, control_result
    control_drawn = len(control_actor.hand) - (control_hand_len - 1)

    # Exploit attempt: interleave + double-cancel first, then play the same 點燃熱情.
    game, actor, enemy = make_game(actor_faction="taiwan_green")
    play_out(game, actor, enemy)
    game.play_card(0, mode="action")
    game.play_card(0, mode="action")
    game.resolve_pending_choice(actor.id, 0)
    game.cancel_pending_choice(actor.id)
    game.cancel_pending_choice(actor.id)
    assert game.turn_log.get("played_propaganda_card") in (None, False)

    hot_index = next(i for i, c in enumerate(actor.hand) if c.name == "點燃熱情")
    hand_len_before = len(actor.hand)
    result = game.play_card(hot_index, mode="action")
    assert result.get("success") is True, result
    drawn = len(actor.hand) - (hand_len_before - 1)
    assert drawn == control_drawn, (
        f"drew {drawn} card(s) vs. the clean-turn_log control's {control_drawn} -- a leaked "
        f"played_propaganda_card flag granted an extra bonus draw"
    )


# ---------------------------------------------------------------------------
# Authorization: only the owning player may cancel their own pending choice
# ---------------------------------------------------------------------------

def test_non_owner_cannot_cancel_someone_elses_pending_dissolve_choice():
    game, actor, enemy = make_game()
    actor.organizations = {"北京": 1}
    enemy.organizations = {"天津": 1}
    actor.hand = [action_card(game, "內應間諜")]

    game.play_card(0, mode="action")
    assert game.pending_choice.get("cancellable") is True

    rejected = game.cancel_pending_choice(enemy.id)
    assert rejected.get("error") == "Not your pending choice"
    assert game.pending_choice is not None


def test_stale_choice_id_is_rejected_for_both_cancel_and_resolve():
    game, actor, enemy = make_game()
    actor.organizations = {"北京": 1}
    enemy.organizations = {"天津": 1}
    actor.hand = [action_card(game, "內應間諜")]

    game.play_card(0, mode="action")
    real_choice_id = game.pending_choice.get("choice_id")
    stale_id = (real_choice_id or "") + "-stale"

    assert game.cancel_pending_choice(actor.id, expected_choice_id=stale_id) == {"error": "Stale pending choice"}
    assert game.resolve_pending_choice(actor.id, 0, expected_choice_id=stale_id) == {"error": "Stale pending choice"}
    assert game.pending_choice is not None


# ---------------------------------------------------------------------------
# Interaction with the unrelated reaction/counter-cancel mechanic (爆料黑幕-style)
# ---------------------------------------------------------------------------

def test_reaction_cancel_of_the_original_card_play_is_unaffected_by_the_new_cancel_feature():
    # An opponent using 爆料黑幕 to cancel the ORIGINAL 內應間諜 play is a completely different
    # mechanic (a reaction_choice on the *opponent's* pending_choice) from the new
    # player-initiated dissolve-target cancel. Confirm it still works exactly as before, and
    # that no dissolve-target pending choice (and thus no new cancellability) is ever reached.
    game, actor, enemy = make_game()
    actor.organizations = {"北京": 1}
    enemy.organizations = {"天津": 1}
    enemy.hand = [Card("爆料黑幕", "reaction", {})]
    actor.hand = [action_card(game, "內應間諜")]

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert game.pending_choice.get("type") == "reaction_choice"
    assert game.pending_choice.get("choice_key") == "cancel_other_player_action"
    # The reaction window's own choice is not part of the dissolve-cancel feature.
    assert not game.pending_choice.get("cancellable")

    cancel_reaction = game.resolve_pending_choice(enemy.id, 1)
    assert cancel_reaction.get("success") is True, cancel_reaction
    assert game.pending_choice is None
    # The card play was cancelled by the reaction -- no dissolve happened, card is discarded
    # (not restored to hand -- that is the reaction mechanic's own, pre-existing semantics).
    assert actor.hand == []
    assert [c.name for c in actor.deck.discard_pile] == ["內應間諜"]
    assert enemy.organizations.get("天津", 0) == 1


# ---------------------------------------------------------------------------
# Regression: event_progress must not be restored via an absolute point-in-time snapshot on
# cancel -- same class of bug as the turn_log played_money_card/played_propaganda_card/
# played_nonstarter_names fields (already fixed via reference-counted _note_*/_undo_* helpers),
# but event_progress was missed. Under two interleaved cancellable plays that each independently
# advance the SAME mission's progress, cancelling both (in either order) must return
# event_progress to exactly its pre-both-plays state, not get stomped by whichever cancel runs
# second restoring its own stale absolute snapshot over the other's already-correct undo.
# (Parent-level review, defect 1.)
# ---------------------------------------------------------------------------

def _pin_money_cost_mission(game, required=3):
    game.current_event = {
        "name": "Test Money Mission",
        "type": "mission",
        "trigger": {"type": "play_card_with_money", "count": required},
    }
    game.event_progress = game._new_event_progress(game.current_event)
    game.event_modifiers = []


def _count(game, player):
    """The player's OWN progress toward the mission (missions are tracked per player)."""
    return game.event_progress["player_progress"][player.id]["count"]


def test_interleaved_double_cancel_restores_event_progress_correctly():
    game, actor, enemy = make_game(actor_faction="taiwan_green")
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.faction_id = "red_army"
    enemy.base = "西安"
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    _pin_money_cost_mission(game, required=3)
    actor.hand = [action_card(game, "內應間諜"), game._make_support_card("北國奧援", variant_index=1)]
    before_progress = dict(game.event_progress)
    assert before_progress["count"] == 0

    # Each play's own _track_event_progress('play_card_with_money', ...) call fires
    # synchronously and unconditionally inside play_card(), before any pending choice even
    # opens -- so after playing BOTH cards, count should already be 2 (1 each).
    played_a = game.play_card(0, mode="action")
    assert played_a.get("pending_choice") is True, played_a
    played_b = game.play_card(0, mode="action")
    assert played_b.get("pending_choice") is True, played_b
    assert _count(game, actor) == 2, game.event_progress

    # Resolve B's first (sacrifice_town) stage -- swaps which flow is self.pending_choice vs.
    # queued, exactly like the turn_log interleaving regressions above.
    resolved_stage1 = game.resolve_pending_choice(actor.id, 0)
    assert resolved_stage1.get("pending_choice") is True, resolved_stage1
    assert _count(game, actor) == 2

    # Cancel whichever flow is currently active, then cancel the other (now reactivated).
    first_cancel = game.cancel_pending_choice(actor.id)
    assert first_cancel.get("success") is True, first_cancel
    assert game.pending_choice is not None, "the other flow's parked choice must reactivate"
    second_cancel = game.cancel_pending_choice(actor.id)
    assert second_cancel.get("success") is True, second_cancel

    assert _count(game, actor) == 0, (
        f"event_progress not fully restored after cancelling both interleaved plays: "
        f"{game.event_progress}"
    )
    assert game.event_progress == before_progress


def test_interleaved_cancel_one_confirm_other_leaves_event_progress_at_one():
    # Mixed case: cancelling ONE of two interleaved contributors must leave exactly the OTHER
    # (still-confirmed) contribution's progress in place -- not 0 (over-undo) and not 2
    # (under-undo/stale-snapshot stomp).
    game, actor, enemy = make_game(actor_faction="taiwan_green")
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.faction_id = "red_army"
    enemy.base = "西安"
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    _pin_money_cost_mission(game, required=3)
    actor.hand = [action_card(game, "內應間諜"), game._make_support_card("北國奧援", variant_index=1)]

    game.play_card(0, mode="action")
    game.play_card(0, mode="action")
    assert _count(game, actor) == 2
    game.resolve_pending_choice(actor.id, 0)  # B's sacrifice_town stage

    # Cancel the currently-active flow (whichever that is)...
    game.cancel_pending_choice(actor.id)
    assert _count(game, actor) == 1, game.event_progress

    # ...then CONFIRM the other one instead of also cancelling it.
    assert game.pending_choice is not None
    remaining_choice_key = game.pending_choice.get("choice_key")
    if remaining_choice_key == "card_dissolve_interaction":
        index = next(i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] in ("天津", "杭州", "香港城"))
        result = game.resolve_pending_choice(actor.id, index)
    else:
        # 北國奧援's target step (2nd stage of its own two-phase flow) -- one resolve away.
        result = game.resolve_pending_choice(actor.id, 0)
    assert result.get("success") is True, result
    assert _count(game, actor) == 1, (
        "confirming the surviving flow must not touch event_progress a second time, and the "
        f"cancelled flow's contribution must stay undone: {game.event_progress}"
    )


def test_event_progress_cancel_non_interleaved_still_fully_restores():
    # Non-regression: the simple, non-interleaved single-cancel case (the only case the old
    # absolute-snapshot restore ever needed to handle) must still work exactly as before.
    game, actor, enemy = make_game(actor_faction="taiwan_green")
    actor.organizations = {"北京": 1}
    enemy.faction_id = "red_army"
    enemy.organizations = {"天津": 1}
    _pin_money_cost_mission(game, required=3)
    actor.hand = [action_card(game, "內應間諜")]
    before_progress = dict(game.event_progress)

    game.play_card(0, mode="action")
    assert _count(game, actor) == 1
    cancelled = game.cancel_pending_choice(actor.id)
    assert cancelled.get("success") is True, cancelled
    assert game.event_progress == before_progress


def test_event_progress_confirm_path_still_reaches_success_normally():
    # Non-regression: confirming (not cancelling) a dissolve card must still let event_progress
    # cross its success threshold exactly as before.
    game, actor, enemy = make_game(actor_faction="taiwan_green")
    actor.organizations = {"北京": 1}
    enemy.faction_id = "red_army"
    enemy.organizations = {"天津": 1}
    _pin_money_cost_mission(game, required=1)
    actor.hand = [action_card(game, "內應間諜")]

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True, played
    assert game.event_progress["succeeded"] is True
    index = next(i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] == "天津")
    resolved = game.resolve_pending_choice(actor.id, index)
    assert resolved.get("success") is True, resolved
    assert game.event_progress["succeeded"] is True
    assert _count(game, actor) == 1


# ---------------------------------------------------------------------------
# Regression: last_actor_id/last_actor_name attribution under SAME-ACTOR interleaving.
#
# The count/succeeded/status fields tested above were already correct after the first Defect 1
# fix. The remaining bug was narrower: _undo_event_progress_delta used to decide whether it was
# still safe to revert last_actor_id/last_actor_name by comparing raw actor-id VALUES
# (`progress.get('last_actor_id') == delta.get('last_actor_id_after')`). That comparison can't
# tell "this specific play's own attribution, still uncontested" apart from "a different,
# still-live play that happens to write the identical actor id" -- which is exactly what happens
# when the SAME PLAYER makes two interleaved cancellable event-progress-contributing plays in one
# turn. Fixed by keying the undo off a fresh per-_track_event_progress-call identity token
# (`event_progress['last_actor_token']`, set in Game._track_event_progress) instead of the actor
# id value. (Parent-level review, defect 1 follow-up.)
# ---------------------------------------------------------------------------

def test_same_actor_interleaved_cancel_first_played_keeps_surviving_plays_attribution():
    # A (內應間諜) played first, then B (北國奧援) played second -- B becomes the active
    # pending_choice, A is parked. Resolving B's own first (sacrifice_town) stage reactivates A
    # (see test_interleaved_cancel_one_confirm_other_leaves_event_progress_at_one above for the
    # same swap). Cancelling A (the FIRST-played card, but currently active again) must leave
    # B's own already-recorded last_actor_id/last_actor_name attribution untouched -- not popped
    # to absent, even though A and B share the exact same actor id.
    game, actor, enemy = make_game(actor_faction="taiwan_green")
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.faction_id = "red_army"
    enemy.base = "西安"
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    _pin_money_cost_mission(game, required=3)
    actor.hand = [action_card(game, "內應間諜"), game._make_support_card("北國奧援", variant_index=1)]

    game.play_card(0, mode="action")  # A: 內應間諜
    game.play_card(0, mode="action")  # B: 北國奧援 (now active; A parked)

    resolve_stage1 = game.resolve_pending_choice(actor.id, 0)  # B's sacrifice_town stage
    assert resolve_stage1.get("pending_choice") is True, resolve_stage1
    assert game.pending_choice.get("choice_key") == "card_dissolve_interaction", (
        "expected A to be reactivated after B's own first stage resolves"
    )

    cancel_a = game.cancel_pending_choice(actor.id)
    assert cancel_a.get("success") is True, cancel_a
    assert _count(game, actor) == 1, (
        "A's own contribution must be undone, leaving exactly B's still-live contribution"
    )
    # The bug: same-value last_actor_id comparison would treat A's cancel as "still credited"
    # (A and B wrote the identical actor id) and pop attribution entirely, even though B's
    # contribution -- which legitimately owns this attribution -- is still live and uncancelled.
    assert "last_actor_id" in game.event_progress and game.event_progress.get("last_actor_id") == actor.id, (
        f"B's still-live attribution must survive cancelling A: {game.event_progress}"
    )
    assert "last_actor_name" in game.event_progress and game.event_progress.get("last_actor_name") == actor.name, (
        f"B's still-live attribution must survive cancelling A: {game.event_progress}"
    )

    # Confirming B afterward doesn't re-track (tracking only happens at play time) -- attribution
    # must still correctly credit B all the way through to B's own final commit.
    assert game.pending_choice is not None
    assert game.pending_choice.get("choice_key") == "support_interaction"
    final_index = next(i for i in range(len(game.pending_choice["targets"])))
    final = game.resolve_pending_choice(actor.id, final_index)
    assert final.get("success") is True, final
    assert _count(game, actor) == 1
    assert game.event_progress.get("last_actor_id") == actor.id, (
        f"B's attribution must still be correct after B's own final confirmation: {game.event_progress}"
    )
    assert game.event_progress.get("last_actor_name") == actor.name


def test_same_actor_interleaved_cancel_later_played_keeps_earlier_plays_attribution():
    # Companion / reverse-order case: cancel the LATER-played card (B) while it's still the
    # active pending_choice (no need to resolve any of its stages first), then confirm the
    # EARLIER-played card (A) that reactivates. This is the order the reviewer noted "already
    # worked by coincidence" under the old value-comparison code -- confirm the token-based fix
    # doesn't regress it.
    game, actor, enemy = make_game(actor_faction="taiwan_green")
    actor.base = "北京"
    actor.organizations = {"北京": 1, "上海": 1}
    enemy.faction_id = "red_army"
    enemy.base = "西安"
    enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
    _pin_money_cost_mission(game, required=3)
    actor.hand = [action_card(game, "內應間諜"), game._make_support_card("北國奧援", variant_index=1)]

    game.play_card(0, mode="action")  # A: 內應間諜
    game.play_card(0, mode="action")  # B: 北國奧援 (now active; A parked)
    assert game.pending_choice.get("choice_key") == "support_interaction"

    cancel_b = game.cancel_pending_choice(actor.id)
    assert cancel_b.get("success") is True, cancel_b
    assert game.pending_choice is not None
    assert game.pending_choice.get("choice_key") == "card_dissolve_interaction", (
        "expected A to be reactivated after cancelling B"
    )
    assert _count(game, actor) == 1, (
        "B's own contribution must be undone, leaving exactly A's still-live contribution"
    )
    assert game.event_progress.get("last_actor_id") == actor.id, (
        f"A's still-live attribution must survive cancelling B: {game.event_progress}"
    )
    assert game.event_progress.get("last_actor_name") == actor.name

    final_index = next(
        i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] in ("天津", "杭州", "香港城")
    )
    final = game.resolve_pending_choice(actor.id, final_index)
    assert final.get("success") is True, final
    assert _count(game, actor) == 1
    assert game.event_progress.get("last_actor_id") == actor.id, (
        f"A's attribution must still be correct after A's own final confirmation: {game.event_progress}"
    )
    assert game.event_progress.get("last_actor_name") == actor.name
