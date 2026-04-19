import uuid
import random
from pathlib import Path
import json
from enum import Enum
from server.deck import Deck
from server.cards import Card

BASE_DIR = Path(__file__).resolve().parent.parent
MAP_PATH = BASE_DIR / "map.json"
FACTIONS_PATH = BASE_DIR / "data" / "factions" / "all_faction.json"
BOARD_TOWNS_PATH = BASE_DIR / "data" / "board_towns.v1.1.json"

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

        self.resources = {"money": 0, "propaganda": 0}
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

    def reset_resources(self):
        self.resources = {"money": 0, "propaganda": 0}


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

        self.purchase_area = []

        self._assign_factions(player_names)
        self._init_decks()
        self._init_purchase_area()

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

    def _init_decks(self):
        for player in self.players:
            starter_cards = []
            for _ in range(7):
                starter_cards.append(Card("追隨者", "propaganda", {"propaganda": 1}))
            for _ in range(3):
                starter_cards.append(Card("樂捐者", "money", {"money": 1}))

            player.deck = Deck(starter_cards)
            player.hand = player.deck.draw(5)

    def _init_purchase_area(self):
        # minimal sample purchase cards
        self.purchase_area = [
            Card("宣傳家", "propaganda", {"propaganda": 2}),
            Card("資助者", "money", {"money": 2}),
            Card("領導", "draw", {"propaganda": 1}),
            Card("交通經驗丙", "move", {"money": 1})
        ]

    def current_player(self):
        return self.players[self.current_player_index]

    # ---------- Card Mechanics ----------

    def play_card(self, card_index):
        player = self.current_player()
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Can only play cards in ACTION phase"}

        if card_index < 0 or card_index >= len(player.hand):
            return {"error": "Invalid card index"}

        card = player.hand.pop(card_index)
        card.apply(player, self)
        player.deck.discard([card])

        return {"success": True}

    def buy_card(self, card_index):
        player = self.current_player()
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Can only buy in ACTION phase"}

        if card_index < 0 or card_index >= len(self.purchase_area):
            return {"error": "Invalid purchase index"}

        card = self.purchase_area[card_index]
        cost = 2  # simplified flat cost

        if player.resources["money"] < cost:
            return {"error": "Not enough money"}

        player.resources["money"] -= cost
        player.deck.discard([card])

        return {"success": True}

    # ---------- Turn Flow ----------

    def advance_turn_phase(self):
        if self.turn_phase == TurnPhase.EVENT:
            self.turn_phase = TurnPhase.ACTION
        elif self.turn_phase == TurnPhase.ACTION:
            self.turn_phase = TurnPhase.END
        elif self.turn_phase == TurnPhase.END:
            self._cleanup_end_turn()
            self.turn_phase = TurnPhase.EVENT
        return {"success": True}

    def _cleanup_end_turn(self):
        player = self.current_player()
        player.discard_hand()
        player.reset_resources()
        player.draw_to_five()

        self.current_player_index = (self.current_player_index + 1) % 4
        if self.current_player_index == 0:
            self.turn += 1

    # ---------- State ----------

    def state(self):
        return {
            "game_id": self.id,
            "turn": self.turn,
            "game_phase": self.game_phase,
            "turn_phase": self.turn_phase,
            "winner": self.winner,
            "current_player": self.current_player().name,
            "purchase_area": [c.name for c in self.purchase_area],
            "players": [
                {
                    "name": p.name,
                    "faction": p.faction_id,
                    "resources": p.resources,
                    "hand": [c.name for c in p.hand],
                    "total_orgs": p.total_organizations()
                }
                for p in self.players
            ]
        }
