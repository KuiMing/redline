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
FACTIONS_PATH = BASE_DIR / "data" / "factions" / "all_faction.integrated.v2.json"
BOARD_TOWNS_PATH = BASE_DIR / "data" / "board_towns.v1.1.json"
STRUCTURED_ACTION_PATH = BASE_DIR / "data" / "action_cards_structured.v1.1.json"
ERA_STRUCTURED_PATH = BASE_DIR / "data" / "era_structured.v1.1.json"


class GamePhase(str, Enum):
    SETUP = "setup"
    BASE_SELECTION = "base_selection"
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
        self.moves_left = 3
        self.hand = []
        self.deck = None
        self.build_range_bonus = 0

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
        self.moves_left = 3
        self.build_range_bonus = 0


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
        self.factions_data = self._load_json(FACTIONS_PATH)
        self.factions = self.factions_data["factions"]
        self.ability_templates = self.factions_data.get("ability_templates", {})
        self.board_regions = self._load_json(BOARD_TOWNS_PATH)["regions"]
        self.structured_cards = self._load_json(STRUCTURED_ACTION_PATH)["cards"]
        # ✅ Load structured eras
        self.structured_eras = self._load_json(ERA_STRUCTURED_PATH)["eras"]

        self.players = []
        self._assign_factions(players_data)
        self.faction_by_id = {f["id"]: f for f in self.factions}
        self.faction_by_id.update({
            "uyghur_family": {
                "id": "uyghur_family",
                "name": "維吾爾",
                "camp": "uyghur",
                "bases": [
                    {"name": "伊斯坦堡", "variant_faction": "uyghur_istanbul"},
                    {"name": "慕尼黑", "variant_faction": "uyghur_munich"},
                    {"name": "華盛頓", "variant_faction": "uyghur_washington"},
                    {"name": "阿拉木圖", "variant_faction": "uyghur_almaty"},
                ],
            },
            "tibet_family": {
                "id": "tibet_family",
                "name": "西藏",
                "camp": "tibet",
                "bases": [
                    {"name": "達蘭薩拉", "variant_faction": "tibet_dharamsala"},
                    {"name": "德拉敦", "variant_faction": "tibet_dehradun"},
                    {"name": "哲古宗", "variant_faction": "tibet_chogu"},
                ],
            },
        })
        self._init_decks()
        self.pending_base_choices = self._compute_pending_base_choices()
        if self.pending_base_choices:
            self.game_phase = GamePhase.BASE_SELECTION
        else:
            self._assign_starting_bases()
            self.game_phase = GamePhase.MAIN

        for p in self.players:
            self._apply_setup_abilities(p)

        self.action_engine = ActionCardEngine(self.structured_cards)
        self.effect_engine = EffectEngine()
        self.era_engine = EraEngine(self.structured_eras)
        # ✅ TEMP: force activate hong_kong era for UI test
        if "hong_kong" in self.era_engine.era_defs:
            self.era_engine.activate_era("hong_kong")
        self.victory_engine = VictoryEngine(self.factions, self.board_regions)

        self.turn_log = self._new_turn_log()
        self.action_log = []
        self.purchase_area = []

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

    def _classify_base_options(self, faction):
        bases = faction.get("bases", [])
        names = []
        for b in bases:
            if isinstance(b, dict):
                name = b.get("name")
            else:
                name = b
            if name:
                names.append(name)
        tags = set(faction.get("tags", []))

        if faction.get("id") == "hong_kong":
            return "special", names
        if any(name.startswith("任意") for name in names):
            return "flex", names
        if "flex_base" in tags:
            return "flex", names
        first_base = bases[0] if bases else None
        if len(names) == 1 and isinstance(first_base, dict) and first_base.get("type") == "fixed":
            return "fixed", names
        return "candidate", names

    def _resolve_starting_base(self, faction, used):
        kind, names = self._classify_base_options(faction)
        towns = self.map.get("towns", {})

        # fixed / candidate / special currently choose first legal explicit town deterministically
        if kind in {"fixed", "candidate", "special"}:
            for name in names:
                if name in towns and name not in used and self.can_faction_develop_in_town(faction.get("id"), name):
                    return name
            return None

        # flex rules: deterministic fallback by semantic token
        if kind == "flex":
            semantic_pools = {
                "任意牆內": self.board_regions.get("china", {}).get("towns", []),
                "任意牆內城鎮": self.board_regions.get("china", {}).get("towns", []),
                "任意英美城鎮": ["華盛頓", "紐約", "多倫多", "卡加利", "溫哥華", "舊金山", "洛杉磯", "倫敦"],
                "任意南洋": ["曼谷", "吉隆坡", "新加坡", "雅加達", "河內", "胡志明市", "仰光"],
                "任意南洋城鎮": ["曼谷", "吉隆坡", "新加坡", "雅加達", "河內", "胡志明市", "仰光"],
                "任意東洋": ["東京", "大阪", "福岡", "札幌", "仙臺", "沖繩", "首爾", "釜山"],
            }
            for label in names:
                pool = semantic_pools.get(label, [])
                for town in pool:
                    if town in towns and town not in used and self.can_faction_develop_in_town(faction.get("id"), town):
                        return town
            return None

        return None

    def _base_option_to_towns(self, faction, option_name):
        towns = self.map.get("towns", {})
        if option_name in towns:
            return [option_name] if self.can_faction_develop_in_town(faction.get("id"), option_name) else []

        semantic_pools = {
            "任意牆內": self.board_regions.get("china", {}).get("towns", []),
            "任意牆內城鎮": self.board_regions.get("china", {}).get("towns", []),
            "任意英美城鎮": ["華盛頓", "紐約", "多倫多", "卡加利", "溫哥華", "舊金山", "洛杉磯", "倫敦"],
            "任意南洋": ["曼谷", "吉隆坡", "新加坡", "雅加達", "河內", "胡志明市", "仰光"],
            "任意南洋城鎮": ["曼谷", "吉隆坡", "新加坡", "雅加達", "河內", "胡志明市", "仰光"],
            "任意東洋": ["東京", "大阪", "福岡", "札幌", "仙臺", "沖繩", "首爾", "釜山"],
        }
        pool = semantic_pools.get(option_name, [])
        ordered = []
        seen = set()
        for town in pool:
            if town in towns and town not in seen and self.can_faction_develop_in_town(faction.get("id"), town):
                seen.add(town)
                ordered.append(town)
        return ordered

    def _candidate_base_names(self, faction):
        if faction.get("id") in {"uyghur_family", "tibet_family"}:
            return [b.get("name") for b in faction.get("bases", []) if b.get("name")]
        _, names = self._classify_base_options(faction)
        candidates = []
        seen = set()
        for option_name in names:
            for town in self._base_option_to_towns(faction, option_name):
                if town not in seen:
                    seen.add(town)
                    candidates.append(town)
        return candidates

    def _compute_pending_base_choices(self):
        pending = {}
        used_fixed = set()
        for p in self.players:
            faction = self.faction_by_id.get(p.faction_id)
            if not faction:
                continue
            if faction.get("id") in {"uyghur_family", "tibet_family"}:
                labels = [b.get("name") for b in faction.get("bases", []) if b.get("name")]
                pending[p.id] = {
                    "labels": labels,
                    "resolved": {name: [name] for name in labels},
                }
                continue
            kind, names = self._classify_base_options(faction)
            candidates = self._candidate_base_names(faction)
            if kind == "fixed" and len(candidates) == 1:
                p.base = candidates[0]
                p.organizations = {candidates[0]: 1}
                used_fixed.add(candidates[0])
            else:
                pending[p.id] = {
                    "labels": names,
                    "resolved": {name: self._base_option_to_towns(faction, name) for name in names},
                }
        return pending

    def set_base_choice(self, player_id, base_name, label=None):
        if self.game_phase != GamePhase.BASE_SELECTION:
            return {"error": "Not in BASE_SELECTION phase"}
        choice_data = self.pending_base_choices.get(player_id)
        if not choice_data:
            return {"error": "No pending base choice for player"}

        labels = choice_data.get("labels", [])
        resolved = choice_data.get("resolved", {})
        if label is None:
            if base_name in labels:
                label = base_name
            else:
                for option_label, towns in resolved.items():
                    if base_name in towns:
                        label = option_label
                        break
        if label not in labels:
            return {"error": "Invalid base option"}
        if base_name not in resolved.get(label, []):
            return {"error": "Invalid base choice"}
        if any(p.base == base_name for p in self.players if p.id != player_id):
            return {"error": "Base already taken"}

        player = next((p for p in self.players if p.id == player_id), None)
        if not player:
            return {"error": "Player not found"}

        faction = self.faction_by_id.get(player.faction_id, {})
        if faction.get("id") in {"uyghur_family", "tibet_family"}:
            variant_map = {
                b.get("name"): b.get("variant_faction")
                for b in faction.get("bases", [])
            }
            player.faction_id = variant_map.get(base_name, player.faction_id)

        player.base = base_name
        player.organizations = {base_name: 1}
        del self.pending_base_choices[player_id]

        if not self.pending_base_choices:
            self.game_phase = GamePhase.MAIN
        return {"success": True}

    def _assign_starting_bases(self):
        pending = self._compute_pending_base_choices()
        if pending:
            for player_id, choice_data in pending.items():
                labels = choice_data.get("labels", [])
                resolved = choice_data.get("resolved", {})
                if not labels:
                    continue
                label = labels[0]
                towns = resolved.get(label, [])
                if not towns:
                    continue
                self.set_base_choice(player_id, towns[0], label=label)

    def _new_turn_log(self):
        return {
            "played_money_card": False,
            "played_propaganda_card": False,
            "non_starter_discard": False,
            "successful_discard": False,
            "built_towns": [],
        }

    def _resolve_faction_abilities(self, faction_id):
        faction = self.faction_by_id.get(faction_id, {})
        resolved = []
        for ability in faction.get("abilities", []):
            if isinstance(ability, dict) and ability.get("ref"):
                template = dict(self.ability_templates.get(ability.get("ref"), {}))
                template.update({k: v for k, v in ability.items() if k != "ref"})
                if ability.get("name_override"):
                    template["name"] = ability["name_override"]
                resolved.append(template)
            else:
                resolved.append(ability)
        return resolved

    def _player_base_data(self, player):
        faction = self.faction_by_id.get(player.faction_id, {})
        for base in faction.get("bases", []):
            if isinstance(base, dict) and base.get("name") == player.base:
                return base
        return None

    def _player_effective_abilities(self, player):
        abilities = list(self._resolve_faction_abilities(player.faction_id))
        base = self._player_base_data(player)
        if base:
            abilities.extend(base.get("abilities", []))
        return abilities

    def _player_has_ability(self, player, name):
        return any(isinstance(a, dict) and a.get("name") == name for a in self._player_effective_abilities(player))

    def _starter_card(self, name):
        if name == "宣傳家":
            return Card("宣傳家", "propaganda", {"propaganda": 2})
        if name == "追隨者":
            return Card("追隨者", "propaganda", {"propaganda": 1})
        if name == "樂捐者":
            return Card("樂捐者", "money", {"money": 1})
        return Card(name, "command", {})

    def _apply_setup_abilities(self, player):
        for ability in self._player_effective_abilities(player):
            if not isinstance(ability, dict):
                continue
            if ability.get("name") == "攬炒策略":
                player.deck.discard([self._starter_card("宣傳家")])
            elif ability.get("name") in {"達賴救援", "東突厥斯坦政府"}:
                player.deck.discard([self._starter_card("宣傳家"), self._starter_card("宣傳家")])

    def _camp_token_for_faction_id(self, faction_id):
        faction = self.faction_by_id.get(faction_id, {})
        camp = faction.get("camp")
        mapping = {
            "red_army": "紅軍",
            "taiwan": "臺灣",
            "hong_kong": "香港",
            "manchuria": "滿洲",
            "mongol": "蒙古",
            "kazakh": "哈薩克",
            "tibet": "藏國",
            "uyghur": "維吾爾",
            "rebel": "反賊",
        }
        return mapping.get(camp)

    def _camp_token_for_player(self, player):
        return self._camp_token_for_faction_id(player.faction_id)

    def can_faction_develop_in_town(self, faction_id, town):
        town_data = self.map.get("towns", {}).get(town)
        if not town_data:
            return False

        camp_tags = town_data.get("camp", []) or []
        faction_token = self._camp_token_for_faction_id(faction_id)

        # Red Army can only develop where explicit red camp tag exists.
        if faction_id == "red_army":
            return "紅軍" in camp_tags

        # Non-red factions may develop in their own tagged towns OR towns with no camp tags.
        if not camp_tags:
            return True
        return faction_token in camp_tags

    def can_develop_in_town(self, player, town):
        return self.can_faction_develop_in_town(player.faction_id, town)

    def setup_test_card_scenario(self, player_id, card_name):
        player = next((p for p in self.players if p.id == player_id), None)
        if not player:
            return {"error": "Player not found"}

        card_def = next((c for c in self.structured_cards if c["name"] == card_name), None)
        if not card_def:
            return {"error": "Card not found"}

        def starter(name, card_type="starter"):
            return Card(name, card_type, {})

        self.current_player_index = self.players.index(player)
        self.turn_phase = TurnPhase.ACTION
        self.turn_log = self._new_turn_log()
        self.action_log = []
        self.purchase_area = []

        for idx, p in enumerate(self.players):
            p.resources = {"money": 0, "propaganda": 0}
            p.moves_left = 3
            p.build_range_bonus = 0
            if p is player:
                base = p.base or "北京"
                p.organizations = {base: 1}
                p.base = base
                p.hand = [Card(card_def["name"], card_def["type"], card_def.get("resources", {}))]
                p.deck.draw_pile = [starter("抽牌A"), starter("抽牌B"), starter("抽牌C"), starter("抽牌D")]
                p.deck.discard_pile = [starter("棄牌A"), starter("棄牌B")]
            else:
                base = p.base or "香港城"
                p.organizations = {base: 1 + (1 if idx % 2 else 0)}
                p.base = base
                p.hand = [starter("對手手牌1"), starter("對手手牌2")]
                p.deck.draw_pile = [starter("對手抽牌A"), starter("對手抽牌B")]
                p.deck.discard_pile = [starter("對手棄牌A")]

        effects = [e["type"] for e in card_def.get("effect", [])]

        if "optional_trash" in effects:
            player.hand.insert(0, Card("可垃圾牌", "command", {}))

        if "discard_self" in effects:
            player.hand.extend([Card("自棄1", "command", {}), Card("自棄2", "command", {})])

        if "gain_from_discard" in effects or "gain_any_from_discard" in effects:
            player.deck.discard_pile = [Card("可回收牌", "command", {})]

        if "trash_from_hand_or_discard" in effects:
            player.hand.insert(0, Card("非起始牌", "command", {}))
            player.deck.discard_pile = [starter("追隨者"), Card("棄牌區非起始牌", "command", {})]

        if "conditional_draw" in effects:
            for cond in [e for e in card_def.get("effect", []) if e["type"] == "conditional_draw"]:
                c = cond.get("condition")
                if c == "played_propaganda_card":
                    self.turn_log["played_propaganda_card"] = True
                elif c == "played_money_card":
                    self.turn_log["played_money_card"] = True
                elif c == "successful_discard":
                    self.turn_log["successful_discard"] = True
                elif c == "canceled_propaganda_card":
                    self.turn_log["canceled_propaganda_card"] = True

        if "conditional_bonus" in effects:
            self.turn_log["non_starter_discard"] = True

        if "shared_draw" in effects:
            for p in self.players:
                if p is not player:
                    p.hand = [starter("對手手牌1")]
                    p.deck.draw_pile = [starter("對手共抽1"), starter("對手共抽2")]

        if "dissolve" in effects:
            player.organizations = {"北京": 1}
            for p in self.players:
                if p is not player:
                    p.organizations = {"香港城": 1}
                    break

        if "refresh_purchase_area" in effects:
            player.deck.draw_pile = [Card("市場1", "command", {}), Card("市場2", "command", {}), Card("市場3", "command", {}), Card("市場4", "command", {})]

        return {
            "success": True,
            "player": player.name,
            "card": card_name,
            "hand": [getattr(c, 'name', str(c)) for c in player.hand],
            "turn_phase": self.turn_phase,
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

        played_card = player.hand.pop(index)
        card_name = getattr(played_card, "name", str(played_card))

        effective_type = getattr(played_card, "card_type", None)
        if self._player_has_ability(player, "國際線") and getattr(played_card, "card_type", None) == "money":
            effective_type = "propaganda"

        if effective_type == "money":
            self.turn_log["played_money_card"] = True
        if effective_type == "propaganda":
            self.turn_log["played_propaganda_card"] = True

        self.action_engine.execute(card_name, player, self)
        player.deck.discard([played_card])
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

    def build_organization(self, town):
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Not in ACTION phase"}

        player = self.current_player()
        if not town:
            return {"error": "Town required"}
        if town not in self.map.get("towns", {}):
            return {"error": "Invalid town"}
        if player.organizations.get(town, 0) <= 0:
            return {"error": "No organization in town"}
        if not self.can_develop_in_town(player, town):
            return {"error": "Cannot develop in this town"}

        player.organizations[town] = player.organizations.get(town, 0) + 1
        self.turn_log.setdefault("built_towns", []).append(town)
        self.log(f"{player.name} built organization in {town}")
        return {"success": True}

    def move_organization(self, from_town, to_town, mode="road"):
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Not in ACTION phase"}

        player = self.current_player()
        if not from_town or not to_town:
            return {"error": "Origin and destination required"}
        if from_town == to_town:
            return {"error": "Origin and destination must differ"}
        if from_town not in self.map.get("towns", {}) or to_town not in self.map.get("towns", {}):
            return {"error": "Invalid town"}
        if player.organizations.get(from_town, 0) <= 0:
            return {"error": "No organization in origin"}
        if mode not in ("road", "rail"):
            return {"error": "Invalid move mode"}

        neighbors = self.map["towns"].get(from_town, {}).get(mode, []) or []
        if to_town not in neighbors:
            return {"error": f"No {mode} connection"}

        cost_key = f"{mode}_cost"
        cost = self.map.get("movement_rules", {}).get(cost_key, 1)
        if player.moves_left < cost:
            return {"error": "Not enough move points"}

        player.organizations[from_town] -= 1
        if player.organizations[from_town] <= 0:
            del player.organizations[from_town]

        player.organizations[to_town] = player.organizations.get(to_town, 0) + 1
        player.moves_left -= cost
        self.log(f"{player.name} moved 1 organization from {from_town} to {to_town} via {mode}")
        return {"success": True}

    def buy_card(self, index):
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Not in ACTION phase"}

        player = self.current_player()
        if index < 0 or index >= len(self.purchase_area):
            return {"error": "Invalid index"}

        card = self.purchase_area[index]
        if not card:
            return {"error": "No card in slot"}

        card_type = getattr(card, "card_type", None)
        if card_type == "money":
            player.resources["money"] += 1
        elif card_type == "propaganda":
            player.resources["propaganda"] += 1

        player.deck.discard([card])
        self.purchase_area.pop(index)
        self.log(f"{player.name} bought {getattr(card, 'name', str(card))}")
        return {"success": True}

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
            "pending_base_choices": self.pending_base_choices,
            "action_log": self.action_log,
            "purchase_area": [getattr(card, 'name', str(card)) for card in self.purchase_area],
            "map": {
                "towns": town_control
            },
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "faction": p.faction_id,
                    "resources": p.resources,
                    "moves_left": p.moves_left,
                    "hand": [getattr(card, 'name', str(card)) for card in p.hand],
                    "orgs": p.organizations
                }
                for p in self.players
            ]
        }
