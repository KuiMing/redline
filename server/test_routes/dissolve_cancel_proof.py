"""Test-only routes that land a game directly inside a player-initiated dissolve-target
pending choice, to exercise the cancellable-dissolve-target-selection feature's map UI
(legal-target highlighting, the Cancel affordance, single-target immediate resolution, and the
multi-target "N/M selected" + Confirm/Cancel flow) end to end against the real running server.

Also provides a forced/mandatory dissolve scenario (全國人大召開's event_red_dissolve) so the
Playwright proof can assert the map shows NO cancel affordance for it.
"""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


def _register_game(runtime: GameSetupRuntime, game: Game, host):
    game_id = str(uuid.uuid4())
    game.id = game_id
    runtime.manager.games[game_id] = game
    runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
    runtime.lobby[game_id] = [(p.id, p.name) for p in game.players]
    runtime.lobby_hosts[game_id] = host.id
    runtime.lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    runtime.lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}
    runtime.lobby_ready[game_id] = {p.id: True for p in game.players}
    return game_id


class DissolveCancelProofTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-dissolve-cancel-single-target",
            self.setup_single_target,
            methods=["POST"],
        )
        self.router.add_api_route(
            "/test/setup-dissolve-cancel-two-phase",
            self.setup_two_phase,
            methods=["POST"],
        )
        self.router.add_api_route(
            "/test/setup-dissolve-cancel-multi-target",
            self.setup_multi_target,
            methods=["POST"],
        )
        self.router.add_api_route(
            "/test/setup-dissolve-cancel-multi-target-stale-final-pick",
            self.setup_multi_target_stale_final_pick,
            methods=["POST"],
        )
        self.router.add_api_route(
            "/test/setup-dissolve-cancel-mongol-shield-target-filtering",
            self.setup_mongol_shield_target_filtering,
            methods=["POST"],
        )
        self.router.add_api_route(
            "/test/setup-dissolve-cancel-mongol-shield-second-pick-dict-order",
            self.setup_mongol_shield_second_pick_dict_order,
            methods=["POST"],
        )
        self.router.add_api_route(
            "/test/setup-dissolve-cancel-multi-target-stale-no-replacement",
            self.setup_multi_target_stale_no_replacement,
            methods=["POST"],
        )
        self.router.add_api_route(
            "/test/setup-dissolve-cancel-forced-event",
            self.setup_forced_event,
            methods=["POST"],
        )

    def _base_game(self):
        players = [(str(uuid.uuid4()), "玩家"), (str(uuid.uuid4()), "紅軍")]
        game = Game(players, market_mode="all_cards")
        actor, enemy = game.players
        actor.faction_id = "taiwan_green"
        enemy.faction_id = "red_army"
        game.pending_base_choices = []
        game.game_phase = GamePhase.MAIN
        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.current_event = dict(game._event_by_name("歲月靜好"))
        game.event_progress = {"count": 0, "required": 0, "succeeded": True, "settled": True, "status": "idle"}
        game.event_modifiers = []
        game.turn_log = game._new_turn_log()
        return game, actor, enemy

    def setup_single_target(self, payload: dict):
        """內應間諜 -- single-target dissolve, no sacrifice. Lands the game right after the
        card is played, with the map's dissolve-target pending choice already open."""
        runtime = self._runtime_provider()
        game, actor, enemy = self._base_game()
        actor.base = "北京"
        actor.organizations = {"北京": 1}
        enemy.base = "西安"
        enemy.organizations = {"天津": 1}
        actor.hand = [self._action_card(game, "內應間諜")]

        pre_play_state = game.state(actor.id)
        played = game.play_card(0, mode="action")

        game_id = _register_game(runtime, game, actor)
        return {
            "success": True,
            "game_id": game_id,
            "player_id": actor.id,
            "url": f"/?game_id={game_id}&player_id={actor.id}",
            "play_result": played,
            "pre_play_state": pre_play_state,
            "state": game.state(actor.id),
        }

    def setup_two_phase(self, payload: dict):
        """派遣間諜 -- two-phase: pick an own organization to sacrifice, then an enemy
        organization within range. Lands the game at the FIRST (sacrifice_town) stage."""
        runtime = self._runtime_provider()
        game, actor, enemy = self._base_game()
        actor.base = "北京"
        actor.organizations = {"北京": 1, "上海": 1}
        enemy.base = "西安"
        enemy.organizations = {"天津": 1, "杭州": 1, "香港城": 1}
        actor.hand = [self._action_card(game, "派遣間諜")]

        pre_play_state = game.state(actor.id)
        played = game.play_card(0, mode="action")

        game_id = _register_game(runtime, game, actor)
        return {
            "success": True,
            "game_id": game_id,
            "player_id": actor.id,
            "url": f"/?game_id={game_id}&player_id={actor.id}",
            "play_result": played,
            "pre_play_state": pre_play_state,
            "state": game.state(actor.id),
        }

    def setup_multi_target(self, payload: dict):
        """北國奧援 III -- multi-target dissolve (count=2), no sacrifice. Lands the game right
        after the card is played, with 2 legal targets and total_count=2."""
        runtime = self._runtime_provider()
        game, actor, enemy = self._base_game()
        actor.faction_id = "liberals"
        actor.base = "北京"
        actor.organizations = {"北京": 1}
        actor.hand = [game._make_support_card("北國奧援")]
        game._support_card_tier = lambda _player, _card: (3, 0, [])
        enemy.base = "西安"
        enemy.organizations = {"天津": 1, "石家莊": 1}

        pre_play_state = game.state(actor.id)
        played = game.play_card(0, mode="action")

        game_id = _register_game(runtime, game, actor)
        return {
            "success": True,
            "game_id": game_id,
            "player_id": actor.id,
            "url": f"/?game_id={game_id}&player_id={actor.id}",
            "play_result": played,
            "pre_play_state": pre_play_state,
            "state": game.state(actor.id),
        }

    def setup_multi_target_stale_final_pick(self, payload: dict):
        """北國奧援 III (count=2) with the FIRST pick (天津) already made and then made stale
        (its organization removed from the board, simulating some other action in between) --
        lands the game one resolve away from the multi-target final-confirmation's stale-pick
        rejection path (parent-level review, defect 2). A third enemy organization (承德, also
        within 1 tile of 北京 -- unlike 上海, which is NOT in range and so is never offered as a
        target at all) is still available so the stale rejection has a legal replacement target
        to re-open onto, exercising the "reopen for re-pick with an updated hint" branch rather
        than the full-fizzle branch -- this is the UI-visible retry state the frontend must
        render correctly on a stale-pick rejection. The frontend should see the choice re-open
        with an updated prompt/target list (still scoped to the ONE remaining pick) rather than
        either silently completing or losing the still-valid 石家莊 pick."""
        runtime = self._runtime_provider()
        game, actor, enemy = self._base_game()
        actor.faction_id = "liberals"
        actor.base = "北京"
        actor.organizations = {"北京": 1}
        actor.hand = [game._make_support_card("北國奧援")]
        game._support_card_tier = lambda _player, _card: (3, 0, [])
        enemy.base = "西安"
        enemy.organizations = {"天津": 1, "石家莊": 1, "承德": 1}

        game.play_card(0, mode="action")
        first_index = next(i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] == "天津")
        first_pick = game.resolve_pending_choice(actor.id, first_index)
        del enemy.organizations["天津"]  # 天津 goes stale before the final pick

        game_id = _register_game(runtime, game, actor)
        return {
            "success": True,
            "game_id": game_id,
            "player_id": actor.id,
            "url": f"/?game_id={game_id}&player_id={actor.id}",
            "first_pick_result": first_pick,
            "state": game.state(actor.id),
        }

    def setup_mongol_shield_target_filtering(self, payload: dict):
        """北國奧援 III (count=2) with one ordinary target and TWO Mongol-protected (盟旗學校)
        targets, but the attacker has only 1 other hand card left after playing -- the map's
        initial target list must show the ordinary target plus exactly ONE of the two Mongol
        targets (never both), proving a 盟旗學校-protected target the attacker cannot afford is
        never offered as a pickable target at all, individually or cumulatively across the whole
        multi-pick selection. (Parent-level review, corrected defect 1.)"""
        runtime = self._runtime_provider()
        players = [
            (str(uuid.uuid4()), "玩家"),
            (str(uuid.uuid4()), "紅軍"),
            (str(uuid.uuid4()), "蒙古"),
        ]
        game = Game(players, market_mode="all_cards")
        actor, red, mongol = game.players
        actor.faction_id = "liberals"
        red.faction_id = "red_army"
        mongol.faction_id = "mongol"
        game.pending_base_choices = []
        game.game_phase = GamePhase.MAIN
        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.current_event = dict(game._event_by_name("歲月靜好"))
        game.event_progress = {"count": 0, "required": 0, "succeeded": True, "settled": True, "status": "idle"}
        game.event_modifiers = []
        game.turn_log = game._new_turn_log()

        actor.base = "北京"
        actor.organizations = {"北京": 1}
        filler_card = Card("填充卡", "command", {})
        actor.hand = [game._make_support_card("北國奧援"), filler_card]
        game._support_card_tier = lambda _player, _card: (3, 0, [])
        red.base = "西安"
        red.organizations = {"天津": 1}
        mongol.base = "太原"
        mongol.organizations = {"石家莊": 1, "承德": 1}

        pre_play_state = game.state(actor.id)
        played = game.play_card(0, mode="action")

        game_id = _register_game(runtime, game, actor)
        return {
            "success": True,
            "game_id": game_id,
            "player_id": actor.id,
            "url": f"/?game_id={game_id}&player_id={actor.id}",
            "play_result": played,
            "pre_play_state": pre_play_state,
            "state": game.state(actor.id),
        }

    def setup_mongol_shield_second_pick_dict_order(self, payload: dict):
        """北國奧援 III (count=2) with THREE Mongol-protected (盟旗學校) targets in range, but the
        attacker has only 2 spare hand cards after playing -- exactly 2 of the 3 may ever be
        offered together. Lands the game with the FIRST pick already made, testing that the
        SECOND listing (computed fresh after that pick) still correctly offers the remaining
        still-affordable Mongol target regardless of `other.organizations` dict iteration order
        -- an already-picked town must never spuriously re-consume shield-discard budget that
        was already reserved for it, which would otherwise silently under-deliver the genuinely
        still-open, still-affordable second target. (Parent-level review, Critical 2.)"""
        runtime = self._runtime_provider()
        players = [
            (str(uuid.uuid4()), "玩家"),
            (str(uuid.uuid4()), "蒙古"),
        ]
        game = Game(players, market_mode="all_cards")
        actor, mongol = game.players
        actor.faction_id = "liberals"
        mongol.faction_id = "mongol"
        game.pending_base_choices = []
        game.game_phase = GamePhase.MAIN
        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.current_event = dict(game._event_by_name("歲月靜好"))
        game.event_progress = {"count": 0, "required": 0, "succeeded": True, "settled": True, "status": "idle"}
        game.event_modifiers = []
        game.turn_log = game._new_turn_log()

        actor.base = "北京"
        actor.organizations = {"北京": 1}
        filler1 = Card("填充卡1", "command", {})
        filler2 = Card("填充卡2", "command", {})
        actor.hand = [game._make_support_card("北國奧援"), filler1, filler2]
        game._support_card_tier = lambda _player, _card: (3, 0, [])
        mongol.base = "太原"
        mongol.organizations = {"承德": 1, "石家莊": 1, "天津": 1}

        played = game.play_card(0, mode="action")
        first_town = game.pending_choice["targets"][0]["town"]
        first_index = next(i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] == first_town)
        first_pick = game.resolve_pending_choice(actor.id, first_index)

        game_id = _register_game(runtime, game, actor)
        return {
            "success": True,
            "game_id": game_id,
            "player_id": actor.id,
            "url": f"/?game_id={game_id}&player_id={actor.id}",
            "play_result": played,
            "first_pick_result": first_pick,
            "first_town": first_town,
            "state": game.state(actor.id),
        }

    def setup_multi_target_stale_no_replacement(self, payload: dict):
        """北國奧援 III (count=2) with only 2 organizations on the board total -- the FIRST pick
        (天津) already made and then made stale, with NO third organization available anywhere
        as a replacement target. Confirming the sole remaining pick (石家莊) must now resolve it
        directly as a partial ("up to 2", per 北國奧援 III's own printed wording) commit, NOT
        fizzle the whole flow -- the map should show the effect completing with exactly 1
        organization dissolved rather than an error/fizzle state. (Parent-level review, corrected
        defect 2.)"""
        runtime = self._runtime_provider()
        game, actor, enemy = self._base_game()
        actor.faction_id = "liberals"
        actor.base = "北京"
        actor.organizations = {"北京": 1}
        actor.hand = [game._make_support_card("北國奧援")]
        game._support_card_tier = lambda _player, _card: (3, 0, [])
        enemy.base = "西安"
        enemy.organizations = {"天津": 1, "石家莊": 1}

        game.play_card(0, mode="action")
        first_index = next(i for i, t in enumerate(game.pending_choice["targets"]) if t["town"] == "天津")
        first_pick = game.resolve_pending_choice(actor.id, first_index)
        del enemy.organizations["天津"]  # 天津 goes stale before the final pick; no 3rd org exists

        game_id = _register_game(runtime, game, actor)
        return {
            "success": True,
            "game_id": game_id,
            "player_id": actor.id,
            "url": f"/?game_id={game_id}&player_id={actor.id}",
            "first_pick_result": first_pick,
            "state": game.state(actor.id),
        }

    def setup_forced_event(self, payload: dict):
        """全國人大召開's failure effect (event_red_dissolve) -- a MANDATORY dissolve choice the
        Red Army player never elected to play; the map must show NO cancel affordance for it."""
        runtime = self._runtime_provider()
        players = [(str(uuid.uuid4()), "紅軍"), (str(uuid.uuid4()), "玩家")]
        game = Game(players, market_mode="all_cards")
        red, other = game.players
        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 1}
        other.faction_id = "hong_kong"
        other.base = "香港城"
        other.organizations = {"天津": 1}
        game.pending_base_choices = []
        game.game_phase = GamePhase.MAIN
        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.current_event = {"name": "全國人大召開"}
        game.turn_log = game._new_turn_log()

        result = game._apply_event_effect_red_dissolve({"scope": "牆內"})

        game_id = _register_game(runtime, game, red)
        return {
            "success": True,
            "game_id": game_id,
            "player_id": red.id,
            "url": f"/?game_id={game_id}&player_id={red.id}",
            "effect_result": result,
            "state": game.state(red.id),
        }

    @staticmethod
    def _action_card(game, name):
        definition = next(c for c in game.structured_cards if c["name"] == name)
        return Card(definition["name"], definition["type"], definition.get("resources", {}))
