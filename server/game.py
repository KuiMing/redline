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
MAP_PATH = BASE_DIR / "data" / "map.json"
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
    def __init__(self, players_data):
        if len(players_data) < 2 or len(players_data) > 4:
            raise ValueError("Game requires 2–4 players")

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
        # ✅ Load structured eras
        self.structured_eras = self._load_json(ERA_STRUCTURED_PATH)["eras"]

        self.players = []
        self._assign_factions(players_data)
        self._init_decks()
        self._seed_starting_positions()

        self.action_engine = ActionCardEngine(self.structured_cards)
        self.effect_engine = EffectEngine()
        self.era_engine = EraEngine(self.structured_eras)
        # ✅ TEMP: force activate hong_kong era for UI test
        if "hong_kong" in self.era_engine.era_defs:
            self.era_engine.activate_era("hong_kong")
        self.victory_engine = VictoryEngine(self.factions, self.board_regions)

        self.turn_log = self._new_turn_log()
        self.action_log = []

    # ---------- Init ----------

    def _load_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _assign_factions(self, players_data):
        red = next(f for f in self.factions if f["id"] == "red_army")
        others = [f for f in self.factions if f["id"] != "red_army"]
        random.shuffle(others)

        selected = [red] + others[:len(players_data)-1]
        random.shuffle(selected)

        for (player_id, name), faction in zip(players_data, selected):
            p = Player(name, faction["id"])
            p.id = player_id
            self.players.append(p)

    def _init_decks(self):
        for p in self.players:
            starter = []
            for _ in range(7):
                starter.append(Card("追隨者", "propaganda", {"propaganda": 1}))
            for _ in range(3):
                starter.append(Card("樂捐者", "money", {"money": 1}))
            p.deck = Deck(starter)
            p.hand = p.deck.draw(5)

    def _seed_starting_positions(self):
        # Minimal playable seed so map/interaction has real current-player towns.
        # TODO: replace with proper rules-driven setup.
        preferred = {
            "taiwan": ["臺北", "高雄"],
            "red_army": ["北京", "上海"],
            "eastern_turkistan": ["喀什", "烏魯木齊"],
            "hong_kong": ["香港城", "九龍城"],
            "manchuria": ["瀋陽", "長春"],
            "mongolia": ["烏蘭巴托", "喬巴山"],
            "tibet": ["拉薩", "日喀則"],
        }

        fallback_cycle = ["北京", "臺北", "香港城", "東京", "首爾", "廣州", "上海", "烏蘭巴托"]
        used = set()

        for idx, p in enumerate(self.players):
            towns = preferred.get(p.faction_id, [])
            assigned = []
            for town in towns:
                if town in self.map.get("towns", {}) and town not in used:
                    assigned.append(town)
                    used.add(town)
            while len(assigned) < 2:
                town = fallback_cycle[(idx + len(assigned)) % len(fallback_cycle)]
                if town in self.map.get("towns", {}) and town not in used:
                    assigned.append(town)
                    used.add(town)
                else:
                    break
            for town in assigned:
                p.organizations[town] = 1
            if assigned:
                p.base = assigned[0]

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

    def log(self, message):
        self.action_log.append(f"[Turn {self.turn}] {message}")
        if len(self.action_log) > 100:
            self.action_log.pop(0)

    def play_card(self, index):
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Not in ACTION phase"}

        player = self.current_player()
        if index < 0 or index >= len(player.hand):
            return {"error": "Invalid index"}

        card_name = player.hand.pop(index)
        self.action_engine.execute(card_name, player, self)
        player.deck.discard([card_name])
        self.log(f"{player.name} played {card_name}")
        return {"success": True}

    def advance_turn_phase(self):
        if self.turn_phase == TurnPhase.EVENT:
            self._check_era_trigger()
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
        self.log(f"End of turn for {player.name}")

        self.turn_log = self._new_turn_log()

        # ✅ Tick active eras at end of full turn
        if self.era_engine:
            self.era_engine.tick()

        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        if self.current_player_index == 0:
            self.turn += 1
        self.turn_phase = TurnPhase.EVENT

    def _check_victory(self):
        win, winner = self.victory_engine.evaluate(self)
        if win:
            self.game_phase = GamePhase.FINISHED
            self.winner = winner

    # ---------- Era Trigger ----------

    def _check_era_trigger(self):
        if not hasattr(self, "era_engine"):
            return

        active_ids = set(self.era_engine.get_active_eras())

        for era in self.structured_eras:
            era_id = era.get("id")
            if era_id in active_ids:
                continue

            trigger = era.get("trigger")
            if not trigger:
                continue

            if self._evaluate_era_trigger(trigger):
                self.era_engine.activate_era(era_id)

    def _evaluate_era_trigger(self, trigger):
        t = trigger.get("type")

        if t == "count_only":
            region = trigger.get("region")
            count = trigger.get("count", 0)

            for p in self.players:
                region_towns = self.board_regions.get(region, {}).get("towns", [])
                region_count = sum(
                    v for town, v in p.organizations.items()
                    if town in region_towns
                )
                if region_count >= count:
                    return True

        if t == "count_and_required":
            region = trigger.get("region")
            count = trigger.get("count", 0)

            for p in self.players:
                region_towns = self.board_regions.get(region, {}).get("towns", [])
                region_count = sum(
                    v for town, v in p.organizations.items()
                    if town in region_towns
                )
                if region_count >= count:
                    return True

        return False

    # ---------- State ----------

    def state(self):
        # aggregate map control
        town_control = {}
        for p in self.players:
            for town, count in p.organizations.items():
                if town not in town_control:
                    town_control[town] = []
                town_control[town].append({"player": p.name, "count": count})

        return {
            "turn": self.turn,
            "game_phase": self.game_phase,
            "turn_phase": self.turn_phase,
            "winner": self.winner,
            "current_player": self.current_player().name,
            "active_eras": self.era_engine.get_active_eras() if self.era_engine else [],
            "map": {
                "towns": town_control
            },
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "faction": p.faction_id,
                    "resources": p.resources,
                    "hand": [getattr(card, 'name', str(card)) for card in p.hand],
                    "orgs": p.organizations
                }
                for p in self.players
            ]
        }
