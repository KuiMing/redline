import uuid
import random
from pathlib import Path
import json
from enum import Enum
from server.deck import Deck
from server.cards import Card
from server.victory import VictoryEngine

BASE_DIR = Path(__file__).resolve().parent.parent
MAP_PATH = BASE_DIR / "map.json"
FACTIONS_PATH = BASE_DIR / "data" / "factions" / "all_faction.json"
BOARD_TOWNS_PATH = BASE_DIR / "data" / "board_towns.v1.1.json"


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
        self.moves_left = 0
        self.resources = {"money": 0, "propaganda": 0}
        self.hand = []
        self.deck = None

    def total_organizations(self):
        return sum(self.organizations.values())


class Game:
    def __init__(self, player_names):
        if len(player_names) != 4:
            raise ValueError("Game requires exactly 4 players")

        self.id = str(uuid.uuid4())
        self.turn = 1
        self.current_player_index = 0
        self.players = []

        self.game_phase = GamePhase.SETUP
        self.turn_phase = TurnPhase.EVENT
        self.winner = None

        self.map = self._load_map()
        self.factions = self._load_factions()
        self.board_regions = self._load_board_regions()

        self.victory_engine = VictoryEngine(self.factions, self.board_regions)

        self._assign_factions(player_names)
        self._init_decks()

    def _load_map(self):
        with open(MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_factions(self):
        with open(FACTIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)["factions"]

    def _load_board_regions(self):
        with open(BOARD_TOWNS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)["regions"]

    def _assign_factions(self, player_names):
        red_faction = next(f for f in self.factions if f["id"] == "red_army")
        other_factions = [f for f in self.factions if f["id"] != "red_army"]

        random.shuffle(other_factions)
        selected = [red_faction] + other_factions[:3]
        random.shuffle(selected)

        for name, faction in zip(player_names, selected):
            self.players.append(Player(name, faction["id"]))

    def current_player(self):
        return self.players[self.current_player_index]

    def _check_victory(self):
        win, winner = self.victory_engine.evaluate(self)
        if win:
            self.game_phase = GamePhase.FINISHED
            self.winner = winner

    def advance_turn_phase(self):
        if self.turn_phase == TurnPhase.EVENT:
            self.turn_phase = TurnPhase.ACTION
        elif self.turn_phase == TurnPhase.ACTION:
            self.turn_phase = TurnPhase.END
        elif self.turn_phase == TurnPhase.END:
            self._check_victory()
            if self.game_phase != GamePhase.FINISHED:
                self.current_player_index = (self.current_player_index + 1) % 4
                if self.current_player_index == 0:
                    self.turn += 1
                self.turn_phase = TurnPhase.EVENT
        return {"success": True}

    def state(self):
        return {
            "game_id": self.id,
            "turn": self.turn,
            "game_phase": self.game_phase,
            "turn_phase": self.turn_phase,
            "winner": self.winner,
            "current_player": self.current_player().name,
            "players": [
                {
                    "name": p.name,
                    "faction": p.faction_id,
                    "total_orgs": p.total_organizations()
                }
                for p in self.players
            ]
        }
