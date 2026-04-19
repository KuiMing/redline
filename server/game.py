import uuid
import random
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent.parent
MAP_PATH = BASE_DIR / "map.json"
FACTIONS_PATH = BASE_DIR / "data" / "factions" / "all_faction.json"


class Player:
    def __init__(self, name, faction_id):
        self.id = str(uuid.uuid4())
        self.name = name
        self.faction_id = faction_id
        self.organizations = {}
        self.base = None


class Game:
    def __init__(self, player_names):
        if len(player_names) != 4:
            raise ValueError("Game requires exactly 4 players")

        self.id = str(uuid.uuid4())
        self.turn = 1
        self.current_player_index = 0
        self.players = []
        self.phase = "setup_base"  # first interactive phase

        self.map = self._load_map()
        self.factions = self._load_factions()

        self._assign_factions(player_names)

    def _load_map(self):
        with open(MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_factions(self):
        with open(FACTIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["factions"]

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

    def set_base(self, town_name):
        if self.phase != "setup_base":
            return {"error": "Not in base setup phase"}

        if town_name not in self.map["towns"]:
            return {"error": "Invalid town"}

        player = self.current_player()

        # prevent duplicate bases
        if any(p.base == town_name for p in self.players):
            return {"error": "Town already taken as base"}

        player.base = town_name
        player.organizations[town_name] = 1

        # move to next player or finish phase
        if all(p.base is not None for p in self.players):
            self.phase = "main"
        else:
            self.next_player()

        return {"success": True}

    def state(self):
        return {
            "game_id": self.id,
            "turn": self.turn,
            "phase": self.phase,
            "current_player": self.current_player().name,
            "players": [
                {
                    "name": p.name,
                    "faction": p.faction_id,
                    "base": p.base,
                    "organizations": p.organizations
                }
                for p in self.players
            ]
        }
