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
