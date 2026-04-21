"""
Clean unified Game engine core (Engine Cleanup Phase)
- Centralized state machine
- Integrated ActionEngine, EffectEngine, EraEngine, VictoryEngine
- No duplicated logic
- Deterministic turn flow
"""

import uuid
import random
import json
from pathlib import Path
from enum import Enum

from server.deck import Deck
from server.cards import Card
from server.action_engine import ActionCardEngine
from server.effect_engine import EffectEngine
from server.era_engine import EraEngine
from server.victory import VictoryEngine

BASE_DIR = Path(__file__).resolve().parent.parent
MAP_PATH = BASE_DIR / "map.json"
FACTIONS_PATH = BASE_DIR / "data" / "factions" / "all_faction.json"
BOARD_TOWNS_PATH = BASE_DIR / "data" / "board_towns.v1.1.json"
STRUCTURED_ACTION_PATH = BASE_DIR / "data" / "action_cards_structured.v1.1.json"
ERA_STRUCTURED_PATH = BASE_DIR / "data" / "era_structured.v1.1.json"


class GamePhase(str, Enum):
    SETUP = "setup"
    MAIN = "main"
    FINISHED = "finished"


class TurnPhase(str, Enum):
    EVENT = "event"
    ACTION = "action"
    END = "end"


class Player:
    def __init__(self, name, faction_id):
        self.id = str(uuid.uuid4())
        self.name = name
        self.faction_id = faction_id
        self.organizations = {}
        self.base = None
        self.resources = {"money": 0, "propaganda": 0}
        self.moves_left = 2
        self.hand = []
        self.deck = None

    def total_organizations(self):
        return sum(self.organizations.values())

    def draw_to_five(self):
        needed = 5 - len(self.hand)
        if needed > 0:
            self.hand.extend(self.deck.draw(needed))

    def discard_hand(self):
        self.deck.discard(self.hand)
        self.hand = []

    def reset_turn(self):
        self.resources = {"money": 0, "propaganda": 0}
        self.moves_left = 2


class Game:
    def __init__(self, player_names):
        if len(player_names) != 4:
            raise ValueError("Game requires exactly 4 players")

        self.id = str(uuid.uuid4())
        self.turn = 1
        self.current_player_index = 0
        self.game_phase = GamePhase.SETUP
        self.turn_phase = TurnPhase.EVENT
        self.winner = None

        self.map = self._load_json(MAP_PATH)
        self.factions = self._load_json(FACTIONS_PATH)["factions"]
        self.board_regions = self._load_json(BOARD_TOWNS_PATH)["regions"]
        self.structured_cards = self._load_json(STRUCTURED_ACTION_PATH)["cards"]
        self.structured_eras = self._load_json(ERA_STRUCTURED_PATH)["eras"]

        self.players = []
        self._assign_factions(player_names)
        self._init_decks()

        self.action_engine = ActionCardEngine(self.structured_cards)
        self.effect_engine = EffectEngine()
        self.era_engine = EraEngine(self.structured_eras)
        self.victory_engine = VictoryEngine(self.factions, self.board_regions)

        self.turn_log = self._new_turn_log()

    # ---------- Init ----------

    def _load_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _assign_factions(self, names):
        red = next(f for f in self.factions if f["id"] == "red_army")
        others = [f for f in self.factions if f["id"] != "red_army"]
        random.shuffle(others)
        selected = [red] + others[:3]
        random.shuffle(selected)

        for name, faction in zip(names, selected):
            self.players.append(Player(name, faction["id"]))

    def _init_decks(self):
        for p in self.players:
            starter = []
            for _ in range(7):
                starter.append(Card("追隨者", "propaganda", {"propaganda": 1}))
            for _ in range(3):
                starter.append(Card("樂捐者", "money", {"money": 1}))
            p.deck = Deck(starter)
            p.hand = p.deck.draw(5)

    def _new_turn_log(self):
        return {
            "played_money_card": False,
            "played_propaganda_card": False,
            "non_starter_discard": False,
            "successful_discard": False,
        }

    # ---------- Core ----------

    def current_player(self):
        return self.players[self.current_player_index]

    def play_card(self, index):
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Not in ACTION phase"}

        player = self.current_player()
        if index < 0 or index >= len(player.hand):
            return {"error": "Invalid index"}

        card_name = player.hand.pop(index)
        self.action_engine.execute(card_name, player, self)
        player.deck.discard([card_name])
        return {"success": True}

    def advance_turn_phase(self):
        if self.turn_phase == TurnPhase.EVENT:
            self.turn_phase = TurnPhase.ACTION
        elif self.turn_phase == TurnPhase.ACTION:
            self.turn_phase = TurnPhase.END
        elif self.turn_phase == TurnPhase.END:
            self._end_turn()
        return {"success": True}

    def _end_turn(self):
        self._check_victory()
        if self.game_phase == GamePhase.FINISHED:
            return

        player = self.current_player()
        player.discard_hand()
        player.reset_turn()
        player.draw_to_five()

        self.turn_log = self._new_turn_log()

        self.current_player_index = (self.current_player_index + 1) % 4
        if self.current_player_index == 0:
            self.turn += 1
        self.turn_phase = TurnPhase.EVENT

    def _check_victory(self):
        win, winner = self.victory_engine.evaluate(self)
        if win:
            self.game_phase = GamePhase.FINISHED
            self.winner = winner

    # ---------- State ----------

    def state(self):
        return {
            "turn": self.turn,
            "game_phase": self.game_phase,
            "turn_phase": self.turn_phase,
            "winner": self.winner,
            "current_player": self.current_player().name,
            "players": [
                {
                    "name": p.name,
                    "faction": p.faction_id,
                    "resources": p.resources,
                    "hand": p.hand,
                    "orgs": p.organizations
                }
                for p in self.players
            ]
        }
