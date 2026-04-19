import uuid
import random
from pathlib import Path
import json
from enum import Enum

BASE_DIR = Path(__file__).resolve().parent.parent
MAP_PATH = BASE_DIR / "map.json"
FACTIONS_PATH = BASE_DIR / "data" / "factions" / "all_faction.json"
BOARD_TOWNS_PATH = BASE_DIR / "data" / "board_towns.v1.1.json"

ROAD_COST = 1
RAIL_COST = 3
WALL_EXTRA_COST = 1
WIN_THRESHOLD = 14


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

        self._assign_factions(player_names)

    def _load_map(self):
        with open(MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_factions(self):
        with open(FACTIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["factions"]

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

    def next_player(self):
        self.current_player_index = (self.current_player_index + 1) % 4

    # ---------- Phase Guards ----------

    def _ensure_game_phase(self, expected):
        if self.game_phase != expected:
            return {"error": f"Invalid game phase. Expected {expected}"}
        return None

    def _ensure_turn_phase(self, expected):
        if self.turn_phase != expected:
            return {"error": f"Invalid turn phase. Expected {expected}"}
        return None

    # ---------- Setup ----------

    def set_base(self, town_name):
        error = self._ensure_game_phase(GamePhase.SETUP)
        if error:
            return error

        if town_name not in self.map["towns"]:
            return {"error": "Invalid town"}

        player = self.current_player()

        if any(p.base == town_name for p in self.players):
            return {"error": "Town already taken as base"}

        player.base = town_name
        player.organizations[town_name] = 1

        if all(p.base is not None for p in self.players):
            self.game_phase = GamePhase.MAIN
            self.turn_phase = TurnPhase.EVENT
            for p in self.players:
                p.moves_left = 2
        else:
            self.next_player()

        return {"success": True}

    # ---------- Organization Mechanics ----------

    def dissolve_organization(self, town_name, target_player_name):
        error = self._ensure_game_phase(GamePhase.MAIN)
        if error:
            return error

        error = self._ensure_turn_phase(TurnPhase.ACTION)
        if error:
            return error

        target = next((p for p in self.players if p.name == target_player_name), None)
        if not target:
            return {"error": "Target player not found"}

        if target.organizations.get(town_name, 0) <= 0:
            return {"error": "No organization to dissolve"}

        target.organizations[town_name] -= 1
        if target.organizations[town_name] == 0:
            del target.organizations[town_name]

        return {"success": True}

    # ---------- Turn Flow ----------

    def advance_turn_phase(self):
        if self.turn_phase == TurnPhase.EVENT:
            self.turn_phase = TurnPhase.ACTION
        elif self.turn_phase == TurnPhase.ACTION:
            self.turn_phase = TurnPhase.END
        elif self.turn_phase == TurnPhase.END:
            self._check_victory()
            if self.game_phase != GamePhase.FINISHED:
                self._end_turn()
                self.turn_phase = TurnPhase.EVENT
        return {"success": True}

    def _end_turn(self):
        self.next_player()
        if self.current_player_index == 0:
            self.turn += 1
        self.current_player().moves_left = 2

    # ---------- Victory ----------

    def _count_taiwan_orgs(self, player):
        taiwan_towns = set(self.board_regions["taiwan"]["towns"])
        return sum(count for town, count in player.organizations.items() if town in taiwan_towns)

    def _check_victory(self):
        for player in self.players:
            if player.faction_id == "red_army":
                if self._count_taiwan_orgs(player) >= WIN_THRESHOLD:
                    self.game_phase = GamePhase.FINISHED
                    self.winner = "red_army"
                    return
            else:
                if player.total_organizations() >= WIN_THRESHOLD:
                    self.game_phase = GamePhase.FINISHED
                    self.winner = player.name
                    return

    # ---------- State ----------

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
                    "base": p.base,
                    "organizations": p.organizations,
                    "total_orgs": p.total_organizations()
                }
                for p in self.players
            ]
        }
