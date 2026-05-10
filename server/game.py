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
SUPPORT_CARDS_PATH = BASE_DIR / "data" / "cards" / "support_cards.v1.1.json"
SUPPORT_TAXONOMY_PATH = BASE_DIR / "SUPPORT_CARD_TAXONOMY.json"


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
        self.moves_left = 0
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
        self.moves_left = 0
        self.build_range_bonus = 0


class Game:
    def __init__(self, players_data, market_mode="sample_53"):
        if len(players_data) < 2 or len(players_data) > 4:
            raise ValueError("Game requires 2–4 players")

        self.id = str(uuid.uuid4())
        self.turn = 1
        self.current_player_index = 0
        self.game_phase = GamePhase.SETUP
        self.turn_phase = TurnPhase.EVENT
        self.winner = None
        self.market_mode = market_mode or "sample_53"

        self.map = self._load_json(MAP_PATH)
        self.factions_data = self._load_json(FACTIONS_PATH)
        self.factions = self.factions_data["factions"]
        self.ability_templates = self.factions_data.get("ability_templates", {})
        self.board_regions = self._load_json(BOARD_TOWNS_PATH)["regions"]
        self.structured_cards = self._load_json(STRUCTURED_ACTION_PATH)["cards"]
        self.support_cards = self._load_json(SUPPORT_CARDS_PATH)
        self.support_taxonomy = self._load_json(SUPPORT_TAXONOMY_PATH).get("cards", []) if SUPPORT_TAXONOMY_PATH.exists() else []
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
        self.victory_engine = VictoryEngine(self.factions, self.board_regions)

        self.turn_log = self._new_turn_log()
        self.action_log = []
        self.purchase_deck = self._initial_purchase_deck()
        self.purchase_area = self._initial_purchase_area()
        self.static_purchase_supply = {name: 1 for name in ['宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥']}
        self.pending_choice = None
        self.era_notification = None

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

    def _support_card_runtime_type(self, name):
        mapping = {
            '英美奧援': 'support',
            '東洋奧援': 'support',
            '南洋奧援': 'support',
            '印度奧援': 'support',
            '天方奧援': 'support',
            '歐洲奧援': 'support',
            '北國奧援': 'support',
            '臺灣奧援': 'support',
            '紅軍奧援': 'support',
        }
        return mapping.get(name, 'support')

    def _support_card_cost(self, support_name):
        entry = self._support_taxonomy_entry(support_name) or {}
        text = entry.get('cost', '')
        if text == '起始牌':
            return {'money': 0, 'propaganda': 0}
        money = 0
        propaganda = 0
        if isinstance(text, str):
            import re
            m = re.search(r'(\d+)資金', text)
            p = re.search(r'(\d+)宣傳', text)
            money = int(m.group(1)) if m else 0
            propaganda = int(p.group(1)) if p else 0
        return {'money': money, 'propaganda': propaganda}

    def _make_support_card(self, support_name):
        entry = self._support_taxonomy_entry(support_name) or {}
        return Card(support_name, self._support_card_runtime_type(support_name), self._support_card_cost(support_name), effect={'support_taxonomy': entry})

    def _static_purchase_cards(self):
        names = ['宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥']
        cards = []
        for name in names:
            for c in self.structured_cards:
                if c.get('name') == name:
                    cards.append(Card(c['name'], c['type'], c.get('resources', {})))
                    break
        return cards

    def _initial_purchase_area(self):
        cards = self._static_purchase_cards()
        cards.extend(self._draw_purchase_cards(5))
        return cards

    def _initial_purchase_deck(self):
        support_pool = []
        for entry in self.support_taxonomy:
            name = entry.get('name')
            copies = int(entry.get('copies') or 0)
            if not name or copies <= 0:
                continue
            support_pool.extend([self._make_support_card(name) for _ in range(copies)])

        general_pool = []
        excluded = {'宣傳家', '思想家', '資助者', '資本家', '追隨者', '樂捐者'}
        for card in self.structured_cards:
            if card.get('name') in excluded:
                continue
            copies = int(card.get('copies') or card.get('count') or 1)
            for _ in range(max(1, copies)):
                general_pool.append(Card(card['name'], card['type'], card.get('resources', {})))

        if self.market_mode == 'all_cards':
            deck_cards = support_pool + general_pool
        else:
            random.shuffle(support_pool)
            support_sample = support_pool[:18]
            random.shuffle(general_pool)
            general_sample = general_pool[:35]
            deck_cards = support_sample + general_sample

        random.shuffle(deck_cards)
        return Deck(deck_cards)

    def _draw_purchase_cards(self, count):
        if not getattr(self, 'purchase_deck', None):
            return []
        drawn = self.purchase_deck.draw(count)
        if len(drawn) < count:
            if not self.purchase_deck.draw_pile and not self.purchase_deck.discard_pile:
                self.purchase_deck = self._initial_purchase_deck()
                drawn.extend(self.purchase_deck.draw(count - len(drawn)))
        return drawn

    def _return_removed_card_to_purchase_supply(self, card):
        card_name = getattr(card, 'name', str(card))
        static_names = {getattr(c, 'name', str(c)) for c in self._static_purchase_cards()}
        if card_name in static_names:
            current = int(self.static_purchase_supply.get(card_name, 1) or 1)
            self.static_purchase_supply[card_name] = current + 1
            self.log(f"{card_name} returned to static purchase supply")
            return {'zone': 'static_supply', 'name': card_name, 'count': self.static_purchase_supply[card_name]}
        if getattr(self, 'purchase_deck', None):
            self.purchase_deck.discard([card])
            self.log(f"{card_name} returned to purchase deck discard")
            return {'zone': 'deck_discard', 'name': card_name}
        return None

    def _remove_card_from_game(self, card):
        card_name = getattr(card, 'name', str(card))
        self.log(f"{card_name} was removed from game")
        return {'zone': 'removed', 'name': card_name}

    def _resolve_underground_party(self, player, count=3):
        if not getattr(self, 'purchase_deck', None):
            return {'error': 'Purchase deck unavailable'}
        choices = self.purchase_deck.draw(count)
        if not choices:
            return {'error': 'Purchase deck empty'}
        self.pending_choice = {
            'type': 'underground_party',
            'player_id': player.id,
            'cards': choices,
            'prompt': '地下黨：從購買區牌庫頂拿取3張牌，任選其中1張加入手牌，其餘移除。'
        }
        self.log(f"{player.name} revealed 3 cards for 地下黨")
        return {'pending_choice': True}

    def resolve_pending_choice(self, player_id, index):
        choice = self.pending_choice or {}
        if not choice:
            return {'error': 'No pending choice'}
        if choice.get('player_id') != player_id:
            return {'error': 'Not your pending choice'}
        cards = choice.get('cards') or []
        if index is None or index < 0 or index >= len(cards):
            return {'error': 'Invalid choice index'}
        player = next((p for p in self.players if p.id == player_id), None)
        if not player:
            return {'error': 'Player not found'}
        chosen = cards[index]
        player.hand.append(chosen)
        removed = []
        for i, card in enumerate(cards):
            if i == index:
                continue
            returned = self._return_removed_card_to_purchase_supply(card)
            if returned is None:
                returned = self._remove_card_from_game(card)
            removed.append(returned)
        self.pending_choice = None
        self.log(f"{player.name} chose {getattr(chosen, 'name', str(chosen))} via 地下黨")
        return {
            'success': True,
            'chosen_card': getattr(chosen, 'name', str(chosen)),
            'removed_cards': removed,
        }

    def _support_card_effect_text(self, card_name, tier, region_index):
        entry = self._support_taxonomy_entry(card_name)
        if not entry:
            return None
        regions = entry.get('regions', []) or []
        if region_index is None or region_index >= len(regions):
            return None
        region_entry = regions[region_index]
        if tier >= 3:
            return region_entry.get('tier_3')
        if tier == 2:
            return region_entry.get('tier_2')
        return region_entry.get('tier_1')

    def _resolve_support_card_effect(self, card_name, tier, region_index):
        text = self._support_card_effect_text(card_name, tier, region_index)
        if not text:
            return None, None

        if card_name == '印度奧援':
            count = 3 if tier >= 3 else 2 if tier == 2 else 1
            return 'add_internal_conflict', {'count': count, 'target': 'red_army'}
        if card_name == '英美奧援':
            amount = 3 if tier >= 3 else 2 if tier == 2 else 1
            return 'gain_resource', {'money': amount}
        if card_name == '歐洲奧援':
            amount = 4 if tier >= 3 else 3 if tier == 2 else 2
            return 'gain_resource', {'propaganda': amount}
        if card_name == '南洋奧援':
            if tier >= 3:
                return 'draw', {'count': 2}
            if tier == 2:
                return 'draw', {'count': 1}
            return 'draw_then_discard', {'draw': 1, 'discard': 1}
        if card_name == '東洋奧援':
            if tier >= 3:
                return 'build_anywhere_inner', {'count': 1}
            if tier == 2:
                return 'build_near_inner', {'count': 1}
            return 'gain_resource', {'propaganda': 2}
        if card_name == '北國奧援':
            if tier >= 3:
                return 'dissolve_many_near', {'count': 2}
            if tier == 2:
                return 'dissolve_many_near', {'count': 1}
            return 'dissolve_self_and_enemy', {'count': 1}
        if card_name == '臺灣奧援':
            if tier >= 3:
                return 'dissolve_and_build', {'count': 1}
            if tier == 2:
                return 'dissolve_many_near', {'count': 1}
            return 'gain_resource', {'propaganda': 1}
        if card_name == '天方奧援':
            if tier >= 3:
                return 'force_discard_near', {'count': 2, 'random': True}
            if tier == 2:
                return 'force_discard_near', {'count': 1, 'random': True}
            return 'force_discard_near', {'count': 1, 'random': False}
        return 'text_only', {'text': text}

    def _execute_support_card(self, player, card):
        card_name = getattr(card, 'name', str(card))
        tier, region_index, matched = self._support_card_tier(player, card_name)
        effect_type, payload = self._resolve_support_card_effect(card_name, tier, region_index)
        if effect_type == 'gain_resource':
            player.resources['money'] += int(payload.get('money', 0) or 0)
            player.resources['propaganda'] += int(payload.get('propaganda', 0) or 0)
        elif effect_type == 'draw':
            player.hand.extend(player.deck.draw(int(payload.get('count', 0) or 0)))
        elif effect_type == 'draw_then_discard':
            draw_count = int(payload.get('draw', 0) or 0)
            discard_count = int(payload.get('discard', 0) or 0)
            player.hand.extend(player.deck.draw(draw_count))
            for _ in range(min(discard_count, len(player.hand))):
                discarded = player.hand.pop()
                player.deck.discard([discarded])
        elif effect_type == 'add_internal_conflict':
            count = int(payload.get('count', 0) or 0)
            target = next((p for p in self.players if p.faction_id == 'red_army'), None)
            if target:
                cards = [Card('分神', 'disruption', {}) for _ in range(count)]
                target.deck.discard(cards)
        elif effect_type == 'build_anywhere_inner':
            inner_towns = self.board_regions.get('china', {}).get('towns', []) or []
            target_town = next((town for town in inner_towns if self.can_develop_in_town(player, town)), None)
            if target_town:
                player.organizations[target_town] = player.organizations.get(target_town, 0) + 1
        elif effect_type == 'build_near_inner':
            inner_towns = set(self.board_regions.get('china', {}).get('towns', []) or [])
            target_town = None
            for origin in list(player.organizations.keys()):
                neighbors = set(self.map.get('towns', {}).get(origin, {}).get('road', []) or []) | set(self.map.get('towns', {}).get(origin, {}).get('rail', []) or [])
                target_town = next((town for town in neighbors if town in inner_towns and self.can_develop_in_town(player, town)), None)
                if target_town:
                    break
            if target_town:
                player.organizations[target_town] = player.organizations.get(target_town, 0) + 1
        elif effect_type == 'dissolve_many_near':
            count = int(payload.get('count', 0) or 0)
            for other in self.players:
                if other is player:
                    continue
                enemy_towns = [town for town, c in (other.organizations or {}).items() if c > 0]
                while count > 0 and enemy_towns:
                    town = enemy_towns.pop(0)
                    result = self.dissolve_organization(player, other, town, source='support_card')
                    if result.get('success'):
                        count -= 1
                    else:
                        break
        elif effect_type == 'dissolve_self_and_enemy':
            own_town = next((town for town, c in (player.organizations or {}).items() if c > 0), None)
            if own_town:
                player.organizations[own_town] -= 1
                if player.organizations[own_town] <= 0:
                    del player.organizations[own_town]
            for other in self.players:
                if other is player:
                    continue
                enemy_town = next((town for town, c in (other.organizations or {}).items() if c > 0), None)
                if enemy_town:
                    self.dissolve_organization(player, other, enemy_town, source='support_card')
                    break
        elif effect_type == 'dissolve_and_build':
            built = False
            for other in self.players:
                if other is player:
                    continue
                enemy_town = next((town for town, c in (other.organizations or {}).items() if c > 0), None)
                if enemy_town:
                    result = self.dissolve_organization(player, other, enemy_town, source='support_card')
                    if result.get('success'):
                        player.organizations[enemy_town] = player.organizations.get(enemy_town, 0) + 1
                        built = True
                    break
            if not built:
                pass
        elif effect_type == 'force_discard_near':
            count = int(payload.get('count', 0) or 0)
            random_pick = bool(payload.get('random'))
            target = next((other for other in self.players if other is not player and other.hand), None)
            if target:
                for _ in range(min(count, len(target.hand))):
                    idx = 0 if not random_pick else random.randrange(len(target.hand))
                    discarded = target.hand.pop(idx)
                    target.deck.discard([discarded])
        self.log(f"{player.name} resolved {card_name} at tier {tier} (matched rulers: {', '.join(matched) if matched else 'none'})")
        return {'tier': tier, 'matched_rulers': matched, 'effect_type': effect_type, 'effect_text': self._support_card_effect_text(card_name, tier, region_index)}

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
            if p.base and p.organizations.get(p.base, 0) > 0:
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
            "played_nonstarter_names": [],
            "combo_reward_triggered": False,
            "guerrilla_triggered": False,
            "faction_action_used": False,
            "india_flag_money_triggered": False,
        }

    def _resolve_ability_ref(self, ability):
        if isinstance(ability, dict) and ability.get("ref"):
            template = dict(self.ability_templates.get(ability.get("ref"), {}))
            template.update({k: v for k, v in ability.items() if k != "ref"})
            if ability.get("name_override"):
                template["name"] = ability["name_override"]
            return template
        return ability if isinstance(ability, dict) else None

    def _resolve_ability_text(self, text):
        if not isinstance(text, str) or "【" not in text or "】" not in text:
            return None
        name = text.split("【", 1)[1].split("】", 1)[0]
        mapping = {
            "商貿組織": {"ref": "first_money_draw", "name_override": "商貿組織"},
            "展現實力": {"ref": "combo_three_unique", "name_override": "展現實力"},
            "殉道者": {"ref": "martyr_draw", "name_override": "殉道者"},
            "青山里": {"ref": "martyr_draw", "name_override": "青山里"},
            "星星之火": {"ref": "first_propaganda_draw", "name_override": "星星之火"},
            "民族調和": {"ref": "first_propaganda_draw", "name_override": "民族調和"},
            "基金會": {"ref": "first_money_gain2", "name_override": "基金會"},
            "共合會": {"ref": "first_money_gain2", "name_override": "共合會"},
            "本土社團": {"ref": "on_build_draw_inner", "name_override": "本土社團"},
            "民國之心": {"ref": "on_build_draw_inner_or_nanyang", "name_override": "民國之心"},
            "選我河山": {"ref": "on_build_draw", "name_override": "選我河山"},
            "還我河山": {"ref": "on_build_draw", "name_override": "還我河山"},
        }
        mapped = mapping.get(name)
        if mapped:
            return self._resolve_ability_ref(mapped)

        direct = {
            "華文傳媒": {"name": "華文傳媒", "type": "passive", "effect": "可以用資金支付宣傳。"},
            "各界資助": {"name": "各界資助", "type": "setup", "effect": "在遊戲開始時額外將1張資助者洗入起始牌庫。"},
            "民主陣線": {"name": "民主陣線", "type": "activated", "effect": "您可以用2點任意資源購買已被移除的任1張牌。"},
            "立場試探": {"name": "立場試探", "type": "activated", "effect": "展示牌庫頂牌；若購買費用為奇數則加入手牌，若為偶數則放入棄牌堆。"},
            "賭徒耳語": {"name": "賭徒耳語", "type": "activated", "effect": "將1張手牌放進牌庫底，猜牌庫頂牌購買費用奇偶；若猜中獲得3點宣傳與3點資金。"},
            "活動家": {"name": "活動家", "type": "setup", "effect": "在遊戲開始時額外將2張宣傳家洗入起始牌庫。"},
            "人同此心": {"name": "人同此心", "type": "triggered", "effect": "當您每回合第1次打出購買費用含宣傳的牌時，獲得2點宣傳。"},
            "共享組織": {"name": "共享組織", "type": "passive", "effect": "可與指定陣營共用組織。"},
        }
        return direct.get(name)

    def _resolve_faction_abilities(self, faction_id):
        faction = self.faction_by_id.get(faction_id, {})
        resolved = []
        for ability in faction.get("abilities", []):
            item = self._resolve_ability_ref(ability)
            if item:
                resolved.append(item)
        for text in faction.get("abilities_text", []):
            item = self._resolve_ability_text(text)
            if item:
                resolved.append(item)
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

    def _player_is_nonviolent(self, player):
        return self._player_has_ability(player, "非暴力")

    def _support_taxonomy_entry(self, card_name):
        for entry in self.support_taxonomy:
            if entry.get("name") == card_name:
                return entry
        return None

    def _is_support_card(self, card):
        card_name = getattr(card, "name", str(card))
        return self._support_taxonomy_entry(card_name) is not None

    def _is_india_flag_card(self, card):
        entry = self._support_taxonomy_entry(getattr(card, "name", str(card)))
        if entry is not None:
            return bool(entry.get("counts_as_flag_card"))
        return False

    def _player_ruler_presence(self, player):
        rulers = set()
        for town, count in (player.organizations or {}).items():
            if count <= 0:
                continue
            town_data = self.map.get("towns", {}).get(town, {})
            for ruler in (town_data.get("ruler", []) or []):
                rulers.add(ruler)
        return rulers

    def _support_card_tier(self, player, card_name):
        entry = self._support_taxonomy_entry(card_name)
        if not entry:
            return 1, None, []
        present = self._player_ruler_presence(player)
        best_tier = 1
        best_idx = 0 if (entry.get("regions", []) or []) else None
        best_matched = []
        for idx, region in enumerate(entry.get("regions", []) or []):
            preferred = region.get("preferred_rulers", []) or []
            matched = [r for r in preferred if r in present]
            tier = 1 + min(2, len(matched))
            if tier > best_tier:
                best_tier = tier
                best_idx = idx
                best_matched = matched
        return best_tier, best_idx, best_matched

    def _player_has_india_research_room(self, player):
        return self._player_has_ability(player, "印度研究分析室")

    def _can_player_gain_flag_card(self, player, card):
        if not self._player_has_india_research_room(player):
            return True, None
        if not self._is_support_card(card):
            return True, None
        if self._is_india_flag_card(card):
            return True, None
        return False, "印度研究分析室：不能持有印度旗幟以外的旗幟卡"

    def _card_is_banned_for_player(self, player, card):
        card_type = getattr(card, "card_type", None)
        if self._player_is_nonviolent(player) and card_type in {"armed", "equipment"}:
            return True
        return False

    def _resource_total(self, resources):
        return int(resources.get("money", 0) or 0) + int(resources.get("propaganda", 0) or 0)

    def _purchase_area_card_cost_total(self, card):
        card_name = getattr(card, 'name', str(card))
        for c in self.structured_cards:
            if c.get('name') == card_name:
                cost = c.get('cost', {})
                return int(cost.get('money', 0) or 0) + int(cost.get('propaganda', 0) or 0)
        entry = self._support_taxonomy_entry(card_name)
        if entry and isinstance(entry.get('cost'), str):
            text = entry['cost']
            money = 0
            propaganda = 0
            if '資金' in text:
                try:
                    money = int(text.split('資金')[0].split('+')[-1].strip()[-1])
                except Exception:
                    money = 0
            if '宣傳' in text:
                try:
                    propaganda = int(text.split('宣傳')[0].split('+')[-1].strip()[-1])
                except Exception:
                    propaganda = 0
            return money + propaganda
        return 0

    def _purchase_area_card_cost_money(self, card):
        card_name = getattr(card, 'name', str(card))
        for c in self.structured_cards:
            if c.get('name') == card_name:
                cost = c.get('cost', {})
                return int(cost.get('money', 0) or 0)
        entry = self._support_taxonomy_entry(card_name)
        if entry and isinstance(entry.get('cost'), str) and '資金' in entry['cost']:
            try:
                return int(entry['cost'].split('資金')[0].split('+')[-1].strip()[-1])
            except Exception:
                return 0
        return 0

    def _top_card_cost_total(self, card):
        return self._purchase_area_card_cost_total(card)

    def _activated_faction_action(self, player, action_name, **kwargs):
        if self.turn_log.get('faction_action_used'):
            return {"error": "Faction action already used this turn"}

        if action_name == '民主陣線':
            if self._resource_total(player.resources) < 2:
                return {"error": "Not enough resources"}
            spend = 2
            propaganda_spend = min(player.resources['propaganda'], spend)
            player.resources['propaganda'] -= propaganda_spend
            spend -= propaganda_spend
            if spend > 0:
                player.resources['money'] = max(0, player.resources['money'] - spend)
            from server.cards import Card
            gained = Card('已移除牌', 'command', {})
            player.deck.discard([gained])
            self.turn_log['faction_action_used'] = True
            self.log(f"{player.name} triggered 民主陣線 and gained a removed card proxy")
            return {"success": True}

        if action_name == '立場試探':
            if not player.deck.draw_pile:
                return {"error": "Deck empty"}
            card = player.deck.draw_pile.pop()
            total = self._top_card_cost_total(card)
            self.turn_log['faction_action_used'] = True
            if total % 2 == 1:
                player.hand.append(card)
                self.log(f"{player.name} triggered 立場試探 and added {card.name} to hand")
            else:
                player.deck.discard([card])
                self.log(f"{player.name} triggered 立場試探 and discarded {card.name}")
            return {"success": True}

        if action_name in {'賭徒耳語', '民族祭儀'}:
            if not player.hand:
                return {"error": "No hand card to bottom-deck"}
            guess = kwargs.get('guess')
            if guess not in {'odd', 'even'}:
                return {"error": "Guess required"}
            bottom = player.hand.pop()
            player.deck.draw_pile.insert(0, bottom)
            if not player.deck.draw_pile:
                return {"error": "Deck empty"}
            card = player.deck.draw_pile.pop()
            total = self._top_card_cost_total(card)
            guessed_odd = guess == 'odd'
            self.turn_log['faction_action_used'] = True
            hit = (total % 2 == 1 and guessed_odd) or (total % 2 == 0 and not guessed_odd)
            if action_name == '賭徒耳語':
                if hit:
                    player.resources['money'] += 3
                    player.resources['propaganda'] += 3
            else:
                if hit:
                    player.resources['money'] += 2
                    player.resources['propaganda'] += 2
                else:
                    player.resources['propaganda'] += 2
            player.deck.discard([card])
            self.log(f"{player.name} triggered {action_name}, guessed {guess}, and revealed {card.name}")
            return {"success": True}

        return {"error": "Unknown faction action"}

    def _apply_guerrilla_on_build(self, player, town):
        if self.turn_log.get("guerrilla_triggered"):
            return
        if not self._player_has_ability(player, "游擊隊"):
            return
        inner_towns = set(self.board_regions.get("china", {}).get("towns", []))
        if town not in inner_towns:
            return

        self.turn_log["guerrilla_triggered"] = True
        red_player = next((p for p in self.players if p.faction_id == "red_army"), None)
        if red_player and red_player.hand:
            discarded = red_player.hand.pop()
            red_player.deck.discard([discarded])
            self.log(f"{player.name} triggered 游擊隊 and forced {red_player.name} to discard {getattr(discarded, 'name', str(discarded))}")
        else:
            player.hand.extend(player.deck.draw(1))
            self.log(f"{player.name} triggered 游擊隊 and drew 1 card")

    def _can_target_org_with_dissolve(self, attacker, defender, source="card"):
        if self._player_has_ability(defender, "盟旗學校"):
            if not attacker.hand:
                return False, "盟旗學校：須先棄1張手牌，才可以瓦解蒙古組織"
            discarded = attacker.hand.pop()
            attacker.deck.discard([discarded])
            self.log(f"{attacker.name} discarded {getattr(discarded, 'name', str(discarded))} to bypass 盟旗學校")
        return True, None

    def _starter_card(self, name):
        if name == "宣傳家":
            return Card("宣傳家", "propaganda", {"propaganda": 2})
        if name == "資助者":
            return Card("資助者", "money", {"money": 2})
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
            elif ability.get("name") in {"達賴救援", "東突厥斯坦政府", "活動家"}:
                player.deck.discard([self._starter_card("宣傳家"), self._starter_card("宣傳家")])
            elif ability.get("name") == "各界資助":
                player.deck.discard([self._starter_card("資助者")])

    def _apply_turn_end_faction_abilities(self, player):
        effective = self._player_effective_abilities(player)
        built_towns = self.turn_log.get("built_towns", []) or []
        built_in_china = any(t in set(self.board_regions.get("china", {}).get("towns", [])) for t in built_towns)
        built_in_nanyang = any(t in {"曼谷", "吉隆坡", "新加坡", "雅加達", "河內", "胡志明市", "仰光"} for t in built_towns)

        for ability in effective:
            if not isinstance(ability, dict):
                continue
            name = ability.get("name")
            if name in {"本土社團", "選我河山", "還我河山"} and built_in_china:
                player.hand.extend(player.deck.draw(1))
                self.log(f"{player.name} triggered {name} and drew 1 card")
            elif name == "民國之心" and (built_in_china or built_in_nanyang):
                player.hand.extend(player.deck.draw(1))
                self.log(f"{player.name} triggered 民國之心 and drew 1 card")
            elif name in {"商貿組織", "民族調和", "星星之火", "基金會", "共合會", "展現實力"}:
                # not turn-end abilities
                continue

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

    def _canonical_faction_name_to_id(self, name):
        mapping = {
            '地下教會': 'underground_church',
            '性別革命': 'gender_revolution',
            '客家': 'hakka',
            '潮汕': 'chaoshan',
            '閩': 'min',
            '吳越': 'wuyue',
            '滇': 'dian',
            '滬': 'hu',
            '粵': 'yue',
            '澳門': 'aomen',
            '綠線臺灣': 'taiwan_green',
            '藍線臺灣': 'taiwan_blue',
            '民國派': 'republican',
        }
        return mapping.get(name, name)

    def _factions_sharing_with(self, faction_id):
        faction = self.faction_by_id.get(faction_id, {})
        shared = {self._canonical_faction_name_to_id(x) for x in (faction.get('shared_organizations_with', []) or [])}
        for text in faction.get('special_rules', []) or []:
            if '共用組織' in text:
                if '粵、澳門' in text:
                    shared.update(['yue', 'aomen'])
                if '藍線臺灣' in text:
                    shared.update(['taiwan_blue'])
                if '綠線臺灣' in text:
                    shared.update(['taiwan_green'])
        return shared

    def _shared_org_count(self, player, town):
        count = player.organizations.get(town, 0)
        shared_with = self._factions_sharing_with(player.faction_id)
        if not shared_with:
            return count
        for other in self.players:
            if other is player:
                continue
            if other.faction_id in shared_with:
                count += other.organizations.get(town, 0)
        return count

    def _shared_origin_owner(self, player, town):
        if player.organizations.get(town, 0) > 0:
            return player
        shared_with = self._factions_sharing_with(player.faction_id)
        if not shared_with:
            return None
        for other in self.players:
            if other is player:
                continue
            if other.faction_id in shared_with and other.organizations.get(town, 0) > 0:
                return other
        return None

    def _town_has_shared_org_access(self, player, town):
        return self._shared_origin_owner(player, town) is not None

    def can_develop_in_town(self, player, town):
        if self._town_has_shared_org_access(player, town) and self.can_faction_develop_in_town(player.faction_id, town):
            return True
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
        self.purchase_deck = self._initial_purchase_deck()
        self.purchase_area = self._initial_purchase_area()

        for idx, p in enumerate(self.players):
            p.resources = {"money": 0, "propaganda": 0}
            p.moves_left = 0
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

    def play_card(self, index, mode=None):
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Not in ACTION phase"}

        if mode not in {"resource", "action"}:
            return {"error": "Card play mode must be resource or action"}

        player = self.current_player()
        if index < 0 or index >= len(player.hand):
            return {"error": "Invalid index"}
        if mode == "action" and self._card_is_banned_for_player(player, player.hand[index]):
            return {"error": "非暴力：不能打出武裝或裝備類卡牌"}

        played_card = player.hand.pop(index)
        card_name = getattr(played_card, "name", str(played_card))

        if mode == "resource":
            for key, value in getattr(played_card, 'resources', {}).items():
                player.resources[key] += value
            player.deck.discard([played_card])
            self.log(f"{player.name} played {card_name} as resource")
            return {"success": True}

        effective_type = getattr(played_card, "card_type", None)
        if self._player_has_ability(player, "國際線") and getattr(played_card, "card_type", None) == "money":
            effective_type = "propaganda"

        support_resolution = None
        if effective_type == 'support':
            support_resolution = self._execute_support_card(player, played_card)
        elif effective_type == "money":
            self.turn_log["played_money_card"] = True
        if effective_type == "propaganda":
            self.turn_log["played_propaganda_card"] = True
        if self._player_has_india_research_room(player) and self._is_india_flag_card(played_card) and not self.turn_log.get("india_flag_money_triggered"):
            self.turn_log["india_flag_money_triggered"] = True
            player.resources["money"] += 2
            self.log(f"{player.name} triggered 印度研究分析室 and gained 2 money")

        if card_name not in {"追隨者", "樂捐者"}:
            played_names = self.turn_log.setdefault("played_nonstarter_names", [])
            if card_name not in played_names:
                played_names.append(card_name)

        action_context = {'current_card': played_card, 'card_name': card_name}
        if effective_type != 'support':
            if card_name in getattr(self.action_engine, 'cards', {}):
                self.action_engine.execute(card_name, player, self, context=action_context, include_resources=False)
            else:
                pass

        for ability in self._player_effective_abilities(player):
            if not isinstance(ability, dict):
                continue
            name = ability.get("name")
            if name == "商貿組織" and effective_type == "money" and not self.turn_log.get("faction_first_money_triggered"):
                self.turn_log["faction_first_money_triggered"] = True
                player.hand.extend(player.deck.draw(1))
                self.log(f"{player.name} triggered 商貿組織 and drew 1 card")
            elif name in {"民族調和", "星星之火"} and effective_type == "propaganda" and not self.turn_log.get("faction_first_propaganda_triggered"):
                self.turn_log["faction_first_propaganda_triggered"] = True
                player.hand.extend(player.deck.draw(1))
                self.log(f"{player.name} triggered {name} and drew 1 card")
            elif name == "人同此心" and effective_type == "propaganda" and not self.turn_log.get("faction_first_prop_gain_triggered"):
                self.turn_log["faction_first_prop_gain_triggered"] = True
                player.resources["propaganda"] += 2
                self.log(f"{player.name} triggered 人同此心 and gained 2 propaganda")
            elif name in {"基金會", "共合會"} and effective_type == "money" and not self.turn_log.get("faction_first_money_gain_triggered"):
                self.turn_log["faction_first_money_gain_triggered"] = True
                player.resources["money"] += 2
                self.log(f"{player.name} triggered {name} and gained 2 money")
            elif name == "展現實力" and not self.turn_log.get("combo_reward_triggered"):
                if len(self.turn_log.get("played_nonstarter_names", [])) >= 3:
                    self.turn_log["combo_reward_triggered"] = True
                    player.resources["money"] += 3
                    self.log(f"{player.name} triggered 展現實力 and gained 3 money")

        if not action_context.get('removed_current_card'):
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
        self._apply_turn_end_faction_abilities(player)
        player.discard_hand()
        player.reset_turn()
        player.draw_to_five()
        while len(self.purchase_area) < len(self._static_purchase_cards()) + 5:
            drawn = self._draw_purchase_cards(1)
            if not drawn:
                break
            self.purchase_area.extend(drawn)
        self.log(f"End of turn for {player.name}")

        self.turn_log = self._new_turn_log()

        # ✅ Tick active eras at end of full turn
        if self.era_engine:
            expired_eras = self.era_engine.tick()
            if self.era_notification and self.era_notification.get("id") in set(expired_eras):
                self.era_notification = None

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
        if not self._town_has_shared_org_access(player, town):
            return {"error": "No organization in town"}
        if not self.can_develop_in_town(player, town):
            return {"error": "Cannot develop in this town"}

        player.organizations[town] = player.organizations.get(town, 0) + 1
        self.turn_log.setdefault("built_towns", []).append(town)
        self._apply_guerrilla_on_build(player, town)
        self.log(f"{player.name} built organization in {town}")
        return {"success": True}

    def build_organization_with_support(self, origin_town, target_town):
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Not in ACTION phase"}

        player = self.current_player()
        if not origin_town or not target_town:
            return {"error": "Origin and target required"}
        if origin_town not in self.map.get("towns", {}) or target_town not in self.map.get("towns", {}):
            return {"error": "Invalid town"}
        origin_owner = self._shared_origin_owner(player, origin_town)
        if not origin_owner:
            return {"error": "No organization in origin"}
        if not self.can_develop_in_town(player, target_town):
            return {"error": "Cannot develop in this town"}

        safehouse_bonus = 1 if self._player_has_ability(player, "安全屋") else 0
        max_distance = 1 + int(getattr(player, 'build_range_bonus', 0) or 0) + safehouse_bonus
        if origin_town != target_town:
            frontier = [(origin_town, 0)]
            seen = {origin_town}
            reached = False
            while frontier:
                town, dist = frontier.pop(0)
                if dist >= max_distance:
                    continue
                neighbors = set(self.map['towns'].get(town, {}).get('road', []) or []) | set(self.map['towns'].get(town, {}).get('rail', []) or [])
                for nxt in neighbors:
                    if nxt == target_town:
                        reached = True
                        frontier = []
                        break
                    if nxt not in seen:
                        seen.add(nxt)
                        frontier.append((nxt, dist + 1))
            if not reached:
                return {"error": "Target out of build range"}

        player.organizations[target_town] = player.organizations.get(target_town, 0) + 1
        self.turn_log.setdefault("built_towns", []).append(target_town)
        self._apply_guerrilla_on_build(player, target_town)
        self.log(f"{player.name} built organization in {target_town} from {origin_town}")
        return {"success": True}

    def dissolve_organization(self, attacker, defender, town, source="card"):
        if not town:
            return {"error": "No organization in target town"}

        target_owner = self._shared_origin_owner(defender, town)
        if not target_owner:
            return {"error": "No organization in target town"}

        ok, err = self._can_target_org_with_dissolve(attacker, target_owner, source=source)
        if not ok:
            return {"error": err}

        target_owner.organizations[town] -= 1
        if target_owner.organizations[town] <= 0:
            del target_owner.organizations[town]

        if target_owner is defender:
            self.log(f"{attacker.name} dissolved 1 organization from {defender.name} at {town}")
        else:
            self.log(f"{attacker.name} dissolved 1 shared organization via {defender.name} from {target_owner.name} at {town}")

        inner_towns = set(self.board_regions.get("china", {}).get("towns", []))
        if town in inner_towns and any(self._player_has_ability(target_owner, n) for n in {"殉道者", "青山里"}):
            target_owner.hand.extend(target_owner.deck.draw(1))
            self.log(f"{target_owner.name} triggered martyr-style ability and drew 1 card")

        return {
            "success": True,
            "actual_owner": target_owner.name,
            "shared_target": target_owner is not defender,
        }

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
        origin_owner = self._shared_origin_owner(player, from_town)
        if not origin_owner:
            return {"error": "No organization in origin"}
        if mode not in ("road", "rail"):
            return {"error": "Invalid move mode"}

        neighbors = self.map["towns"].get(from_town, {}).get(mode, []) or []
        if to_town not in neighbors:
            return {"error": f"No {mode} connection"}

        # Movement points represent movement counts, not distance/cost budget.
        # Every legal organization move consumes one count; cards/effects grant counts.
        cost = 1
        if player.moves_left < cost:
            return {"error": "Not enough move points"}

        if from_town == origin_owner.base and origin_owner.organizations.get(from_town, 0) <= 1:
            return {"error": "Base anchor organization cannot move"}

        origin_owner.organizations[from_town] -= 1
        if origin_owner.organizations[from_town] <= 0:
            del origin_owner.organizations[from_town]

        player.organizations[to_town] = player.organizations.get(to_town, 0) + 1
        player.moves_left -= cost
        if origin_owner is player:
            self.log(f"{player.name} moved 1 organization from {from_town} to {to_town} via {mode}")
        else:
            self.log(f"{player.name} moved 1 shared organization from {origin_owner.name}:{from_town} to {to_town} via {mode}")
        return {"success": True}

    def _card_purchase_cost(self, card):
        card_name = getattr(card, 'name', str(card))
        if getattr(card, "card_type", None) == "support":
            return self._support_card_cost(card_name)
        for c in self.structured_cards:
            if c.get('name') == card_name:
                cost = c.get('cost', {}) or {}
                return {
                    'money': int(cost.get('money', 0) or 0),
                    'propaganda': int(cost.get('propaganda', 0) or 0),
                }
        return {'money': 0, 'propaganda': 0}

    def _copy_purchase_card(self, card):
        return Card(
            getattr(card, 'name', str(card)),
            getattr(card, 'card_type', None),
            dict(getattr(card, 'resources', {}) or {}),
            getattr(card, 'effect', None),
        )

    def buy_card(self, index):
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Not in ACTION phase"}

        player = self.current_player()
        if index < 0 or index >= len(self.purchase_area):
            return {"error": "Invalid index"}

        card = self.purchase_area[index]
        if not card:
            return {"error": "No card in slot"}
        if self._player_is_nonviolent(player) and self._card_is_banned_for_player(player, card):
            return {"error": "非暴力：不能購買武裝或裝備類卡牌"}
        ok, err = self._can_player_gain_flag_card(player, card)
        if not ok:
            return {"error": err}

        static_count = len(self._static_purchase_cards())
        is_static_purchase = index < static_count
        card_name = getattr(card, 'name', str(card))
        if is_static_purchase:
            supply = int(self.static_purchase_supply.get(card_name, 0) or 0)
            if supply <= 0:
                return {"error": "Static purchase card is out of supply"}

        card_type = getattr(card, "card_type", None)
        cost = self._card_purchase_cost(card)
        cost_money = int(cost.get('money', 0) or 0)
        cost_propaganda = int(cost.get('propaganda', 0) or 0)

        if self._player_has_ability(player, "華文傳媒") and card_type == "propaganda":
            if player.resources['money'] < cost_propaganda:
                return {"error": "Not enough money for propaganda purchase"}
            player.resources['money'] -= cost_propaganda
        else:
            if player.resources['money'] < cost_money or player.resources['propaganda'] < cost_propaganda:
                return {"error": "Not enough resources"}
            player.resources['money'] -= cost_money
            player.resources['propaganda'] -= cost_propaganda

        player.deck.discard([self._copy_purchase_card(card)])
        if is_static_purchase:
            self.static_purchase_supply[card_name] = int(self.static_purchase_supply.get(card_name, 0) or 0) - 1
        else:
            self.purchase_area.pop(index)
        self.log(f"{player.name} bought {card_name}")
        return {"success": True}

    # ---------- Era Trigger ----------

    def _era_card_entry(self, era_name):
        path = BASE_DIR / "data" / "cards" / "event_and_era_cards.v1.1.json"
        if not path.exists():
            return None
        try:
            rows = self._load_json(path)
        except Exception:
            return None
        for row in rows:
            if isinstance(row, list) and row and row[0] == era_name:
                return row
        return None

    def _era_notification_payload(self, era):
        era_name = era.get("name", "未知時代")
        row = self._era_card_entry(era_name)
        trigger_text = None
        success_text = None
        fail_text = None
        if row and len(row) >= 5:
            trigger_text = row[2] or None
            success_text = row[3] or None
            fail_text = row[4] or None
        trigger = era.get("trigger") or {}
        if not trigger_text and trigger.get("type") == "count_only":
            trigger_text = f"在指定區域擁有至少 {trigger.get('count', 0)} 個有效組織。"
        duration = era.get("duration", {})
        if duration.get("type") == "turns":
            duration_text = f"持續 {duration.get('value', 0)} 回合"
        elif duration.get("type") == "permanent":
            duration_text = "持續至遊戲結束"
        else:
            duration_text = "持續時間未明"
        return {
            "id": era.get("id"),
            "name": era_name,
            "trigger_text": trigger_text or "（條件資料暫缺）",
            "success_text": success_text or "（紅軍壓制效果暫缺）",
            "fail_text": fail_text or "（革命反撲效果暫缺）",
            "duration_text": duration_text,
            "remaining": None,
            "minimized": False,
        }

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
                if self.era_engine.activate_era(era_id):
                    self.era_notification = self._era_notification_payload(era)
                    self.log(f"Era triggered: {era.get('name', era_id)}")

    def _player_matches_era_trigger(self, player, trigger):
        faction_id = trigger.get("faction_id")
        if faction_id and player.faction_id != faction_id:
            return False
        camp = trigger.get("camp")
        if camp:
            faction = self.faction_by_id.get(player.faction_id, {})
            if faction.get("camp") != camp and player.faction_id != camp:
                return False
        return True

    def _player_region_org_count(self, player, region):
        region_towns = self.board_regions.get(region, {}).get("towns", [])
        return sum(
            v for town, v in player.organizations.items()
            if town in region_towns
        )

    def _player_requirement_org_count(self, player, requirement):
        if requirement.get("region"):
            return self._player_region_org_count(player, requirement.get("region"))
        if requirement.get("ruler"):
            ruler = requirement.get("ruler")
            return sum(
                v for town, v in player.organizations.items()
                if ruler in (self.map.get("towns", {}).get(town, {}).get("ruler") or [])
            )
        return 0

    def _evaluate_era_trigger(self, trigger):
        t = trigger.get("type")

        if t == "count_only":
            region = trigger.get("region")
            count = trigger.get("count", 0)

            for p in self.players:
                if not self._player_matches_era_trigger(p, trigger):
                    continue
                if self._player_region_org_count(p, region) >= count:
                    return True

        if t == "count_and_required":
            requirements = trigger.get("requirements")
            if requirements:
                for p in self.players:
                    if not self._player_matches_era_trigger(p, trigger):
                        continue
                    if all(
                        self._player_requirement_org_count(p, req) >= req.get("count", 0)
                        for req in requirements
                    ):
                        return True
            else:
                region = trigger.get("region")
                count = trigger.get("count", 0)
                for p in self.players:
                    if not self._player_matches_era_trigger(p, trigger):
                        continue
                    if self._player_region_org_count(p, region) >= count:
                        return True

        return False

    # ---------- State ----------

    def state(self):
        # aggregate map control
        town_control = {}
        shared_access = {}
        for p in self.players:
            for town, count in p.organizations.items():
                if town not in town_control:
                    town_control[town] = []
                town_control[town].append({"player": p.name, "count": count})
            for town in self.map.get('towns', {}).keys():
                if self._shared_org_count(p, town) > p.organizations.get(town, 0):
                    shared_access.setdefault(town, []).append(p.faction_id)

        active_era_details = self.era_engine.get_active_era_details() if self.era_engine else []
        notification = None
        if self.era_notification:
            notification = dict(self.era_notification)
            active_match = next((e for e in active_era_details if e.get("id") == notification.get("id")), None)
            if active_match:
                notification["remaining"] = active_match.get("remaining")
                notification["duration"] = active_match.get("duration")

        pending_choice = None
        if self.pending_choice:
            pending_choice = {
                'type': self.pending_choice.get('type'),
                'player_id': self.pending_choice.get('player_id'),
                'prompt': self.pending_choice.get('prompt'),
                'cards': [getattr(card, 'name', str(card)) for card in (self.pending_choice.get('cards') or [])],
            }

        return {
            "turn": self.turn,
            "game_phase": self.game_phase,
            "turn_phase": self.turn_phase,
            "winner": self.winner,
            "current_player": self.current_player().name,
            "active_eras": self.era_engine.get_active_eras() if self.era_engine else [],
            "active_era_details": active_era_details,
            "era_notification": notification,
            "market_mode": self.market_mode,
            "pending_base_choices": self.pending_base_choices,
            "pending_choice": pending_choice,
            "action_log": self.action_log,
            "purchase_area": [getattr(card, 'name', str(card)) for card in self.purchase_area],
            "static_purchase_supply": dict(getattr(self, 'static_purchase_supply', {})),
            "map": {
                "towns": town_control,
                "shared_access": shared_access
            },
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "faction": p.faction_id,
                    "base": p.base,
                    "resources": p.resources,
                    "moves_left": p.moves_left,
                    "hand": [getattr(card, 'name', str(card)) for card in p.hand],
                    "deck_count": len(p.deck.draw_pile) if p.deck else 0,
                    "discard_count": len(p.deck.discard_pile) if p.deck else 0,
                    "orgs": p.organizations
                }
                for p in self.players
            ]
        }
