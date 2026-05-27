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
from server.events import EventDeck

BASE_DIR = Path(__file__).resolve().parent.parent
MAP_PATH = BASE_DIR / "data" / "map.json"
FACTIONS_PATH = BASE_DIR / "data" / "factions" / "all_faction.integrated.v2.json"
STRUCTURED_ACTION_PATH = BASE_DIR / "data" / "action_cards_structured.v1.1.json"
ERA_STRUCTURED_PATH = BASE_DIR / "data" / "era_structured.v1.1.json"
SUPPORT_CARDS_PATH = BASE_DIR / "data" / "cards" / "support_cards.v1.1.json"
SUPPORT_TAXONOMY_PATH = BASE_DIR / "data" / "cards" / "support_taxonomy.v1.1.json"
EVENT_STRUCTURED_PATH = BASE_DIR / "data" / "events_structured.v1.1.json"
EVENT_CARD_COUNTS_PATH = BASE_DIR / "data" / "cards" / "event_and_era_cards.v1.1.json"
STATIC_PURCHASE_CARD_NAMES = ('宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥')


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
        self.towns_by_ruler = self._build_towns_by_ruler(self.map)
        self.structured_cards = self._load_json(STRUCTURED_ACTION_PATH)["cards"]
        self.support_cards = self._load_json(SUPPORT_CARDS_PATH)
        self.support_taxonomy = self._load_json(SUPPORT_TAXONOMY_PATH).get("cards", []) if SUPPORT_TAXONOMY_PATH.exists() else []
        # ✅ Load structured eras
        self.structured_eras = self._load_json(ERA_STRUCTURED_PATH)["eras"]
        self.structured_events = self._load_json(EVENT_STRUCTURED_PATH).get("events", [])

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
        self.victory_engine = VictoryEngine(self.factions)

        self.turn_log = self._new_turn_log()
        self.action_log = []
        self.purchase_deck = self._initial_purchase_deck()
        self.purchase_area = self._initial_purchase_area()
        self.static_purchase_supply = {name: 1 for name in STATIC_PURCHASE_CARD_NAMES}
        self.event_deck = EventDeck(self._initial_event_cards())
        self.current_event = None
        self.event_progress = None
        self.event_modifiers = []
        self.event_notification = None
        self.pending_choice = None
        self.era_notification = None
        self.red_army_destroyed_bases = set()

    # ---------- Init ----------

    def _load_json(self, path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _event_card_counts(self):
        counts = {}
        if not EVENT_CARD_COUNTS_PATH.exists():
            return counts
        rows = self._load_json(EVENT_CARD_COUNTS_PATH)
        for row in rows:
            if not isinstance(row, list) or len(row) < 6:
                continue
            name = row[0]
            if not name or name in {'事件卡名稱', '時代關卡名稱'}:
                continue
            try:
                count = int(row[5])
            except (TypeError, ValueError):
                continue
            counts[name] = count
        return counts

    def _initial_event_cards(self):
        counts = self._event_card_counts()
        cards = []
        for event in self.structured_events:
            name = event.get('name')
            if name and '（副本）' in name:
                continue
            copies = int(counts.get(name, 1) or 1)
            for _ in range(max(1, copies)):
                cards.append(dict(event))
        return cards

    def _event_by_name(self, name):
        for event in self.structured_events:
            if event.get('name') == name or event.get('id') == name:
                return dict(event)
        return None

    def _event_display_payload(self, event=None):
        event = event or self.current_event
        if not event:
            return None
        trigger = event.get('trigger') or {}
        success = event.get('success') or {}
        failure = event.get('failure') or {}
        progress = dict(self.event_progress or {})
        return {
            'id': event.get('id'),
            'name': event.get('name'),
            'type': event.get('type'),
            'trigger': trigger,
            'success': success,
            'failure': failure,
            'progress': progress,
            'status': progress.get('status') or 'active',
            'result_text': self._event_result_text(event),
            'trigger_text': self._event_condition_text(trigger, event),
            'success_text': self._event_effect_text(success),
            'failure_text': self._event_effect_text(failure),
        }

    def _event_condition_text(self, trigger, event=None):
        if not trigger:
            return '無'
        labels = {
            'use_faction_ability': '使用或觸發陣營特殊能力',
            'play_card_with_money': '打出購買費用含資金的卡牌',
            'play_card_with_propaganda': '打出購買費用含宣傳的卡牌',
            'buy_card': '購買符合條件的卡牌',
            'end_turn_state': '回合結束時符合狀態',
            'build_organization': '建立組織',
            'move_organization': '進行組織遷移',
            'draw': '藉由卡牌效果或能力抽牌',
        }
        count = int(trigger.get('count', 1) or 1)
        scope = trigger.get('scope')
        scope_text = f'（{scope}）' if scope else ''
        detail = ''
        if trigger.get('type') == 'buy_card':
            criteria = []
            if trigger.get('min_cost') is not None:
                criteria.append(f"總費用 {trigger.get('min_cost')} 點以上")
            if trigger.get('card_names'):
                criteria.append('或'.join(trigger.get('card_names') or []))
            if criteria:
                detail = f"（{' / '.join(criteria)}）"
        if trigger.get('type') == 'end_turn_state' and trigger.get('condition') == 'own_organization_in_scope':
            detail = f"（己方至少 {count} 個組織）"
        return f"{labels.get(trigger.get('type'), trigger.get('type') or '未知條件')}{scope_text}{detail}至少 {count} 次"

    def _event_result_text(self, event=None):
        event = event or self.current_event
        if not event:
            return ''
        progress = dict(self.event_progress or {})
        status = progress.get('status') or 'active'
        if event.get('type') == 'mission':
            if status == 'success_pending':
                return '非紅軍任務條件已達成，等待結算'
            if status == 'success':
                return '非紅軍任務成功'
            if status == 'failure':
                return '非紅軍任務失敗，紅軍效果生效'
            return '非紅軍任務進行中'
        if status == 'auto':
            return '紅軍事件效果已自動套用'
        if status == 'idle':
            return '本次事件無效果'
        return ''

    def _event_effect_text(self, effect):
        if not effect or effect.get('type') == 'none':
            return '無'
        t = effect.get('type')
        count = int(effect.get('count', effect.get('amount', 1)) or 1)
        card = effect.get('card')
        labels = {
            'draw': f'抽 {count} 張牌',
            'gain_card': f'獲得 {count} 張{card or "指定牌"}',
            'discard_self': f'己方選 {count} 張手牌棄掉',
            'discard_random': f'被隨機棄掉 {count} 張手牌',
            'red_dissolve': f'紅軍瓦解 {count} 個組織',
            'add_internal_conflict': f'獲得 {count} 張內鬥',
            'move': f'獲得 {count} 次組織遷移',
            'reduce_cost': f'本回合購牌費用降低 {effect.get("amount", 1)}',
            'restrict_build': '本回合建立組織受限',
            'ignore_distance': '本回合無視距離限制',
            'scoped_card_range': f'本回合{effect.get("target_region", "指定區域")}目標距離增加為 {effect.get("range", 1)} 格',
            'build_organization': f'建立 {count} 個組織',
            'build_organization_in_region': f'在{effect.get("region", "指定區域")}免費建立 {count} 個組織',
            'build_organization_near_own': f'在己方組織 {effect.get("max_steps", 1)} 格內建立 {count} 個組織',
            'topdeck_from_discard': f'從棄牌堆選 {count} 張置於牌庫頂',
            'trash_from_hand_or_discard': f'從手牌或棄牌堆移除 {count} 張牌',
        }
        return labels.get(t, t or '未知效果')

    def _start_event_phase(self):
        event = self.event_deck.draw() if getattr(self, 'event_deck', None) else None
        self.current_event = dict(event) if event else None
        self.event_modifiers = self._active_event_modifiers()
        if not self.current_event:
            self.event_progress = None
            self.event_notification = None
            return
        event_type = self.current_event.get('type')
        trigger = self.current_event.get('trigger') or {}
        required = int(trigger.get('count', 0) or 0)
        self.event_progress = {'count': 0, 'required': required, 'succeeded': False, 'settled': False, 'status': 'active'}
        if event_type == 'idle':
            self.event_progress.update({'succeeded': True, 'settled': True, 'status': 'idle'})
            self.log(f"Event drawn: {self.current_event.get('name')} (no-op)")
        elif event_type == 'auto':
            self._apply_event_effect(self.current_event.get('effect') or {}, self.current_player(), outcome='auto')
            self.event_progress.update({'succeeded': True, 'settled': True, 'status': 'auto'})
            self.log(f"Event drawn: {self.current_event.get('name')} (auto)")
        else:
            self.log(f"Event drawn: {self.current_event.get('name')}")
        self.event_notification = self._event_display_payload()

    def _event_trigger_matches_scope(self, trigger, town=None):
        scope = trigger.get('scope')
        if not scope:
            return True
        if scope == '牆內':
            return town is None or town in set(self._towns_for_region_alias('china'))
        return True

    def _event_trigger_actor_allowed(self, player):
        if player is None:
            return True
        return getattr(player, 'faction_id', None) != 'red_army'

    def _track_event_progress(self, trigger_type, amount=1, town=None, player=None):
        event = self.current_event or {}
        if event.get('type') != 'mission' or not self.event_progress or self.event_progress.get('settled'):
            return
        trigger = event.get('trigger') or {}
        if trigger.get('type') != trigger_type:
            return
        if not self._event_trigger_actor_allowed(player):
            return
        if not self._event_trigger_matches_scope(trigger, town=town):
            return
        self.event_progress['count'] = int(self.event_progress.get('count', 0) or 0) + int(amount or 1)
        required = int(trigger.get('count', 1) or 1)
        if self.event_progress['count'] >= required:
            self.event_progress['succeeded'] = True
            self.event_progress['status'] = 'success_pending'
            result = self._settle_current_event()
            self.event_notification = self._event_display_payload()
            return result
        self.event_notification = self._event_display_payload()
        return {'success': True}

    def _event_purchase_trigger_matches(self, trigger, card, original_cost=None):
        if (trigger or {}).get('type') != 'buy_card':
            return False
        card_name = getattr(card, 'name', str(card))
        if card_name in set(trigger.get('card_names') or []):
            return True
        min_cost = trigger.get('min_cost')
        if min_cost is not None:
            cost = original_cost or self._card_purchase_cost(card)
            total = int((cost or {}).get('money', 0) or 0) + int((cost or {}).get('propaganda', 0) or 0)
            if total >= int(min_cost or 0):
                return True
        return False

    def _track_event_purchase(self, card, original_cost=None, player=None):
        event = self.current_event or {}
        if event.get('type') != 'mission' or not self.event_progress or self.event_progress.get('settled'):
            return {'success': True}
        trigger = event.get('trigger') or {}
        if not self._event_purchase_trigger_matches(trigger, card, original_cost=original_cost):
            return {'success': True}
        return self._track_event_progress('buy_card', player=player) or {'success': True}

    def _event_state_condition_met(self, trigger, player):
        condition = (trigger or {}).get('condition')
        if condition == 'own_organization_in_scope':
            scope = (trigger or {}).get('scope')
            required = int((trigger or {}).get('count', 1) or 1)
            if scope == '牆內':
                allowed = set(self._towns_for_region_alias('china'))
            else:
                allowed = set(self.map.get('towns', {}) or {})
            count = sum(
                int(n or 0)
                for town, n in (getattr(player, 'organizations', {}) or {}).items()
                if town in allowed and int(n or 0) > 0
            )
            return count >= required, count
        return False, 0

    def _event_build_towns_near_own(self, player, max_steps=1):
        origins = [town for town, count in (getattr(player, 'organizations', {}) or {}).items() if count > 0]
        if not origins:
            return []
        candidates = set()
        for origin in origins:
            frontier = [(origin, 0)]
            seen = {origin}
            while frontier:
                town, dist = frontier.pop(0)
                if dist >= int(max_steps or 1):
                    continue
                for nxt in sorted(self._town_neighbors(town)):
                    if nxt in seen:
                        continue
                    seen.add(nxt)
                    candidates.add(nxt)
                    frontier.append((nxt, dist + 1))
        return [
            {'town': town}
            for town in sorted(candidates)
            if self.can_develop_in_town(player, town)
        ]

    def _draw_player_cards(self, player, count=1, source='effect'):
        drawn = player.deck.draw(int(count or 1))
        player.hand.extend(drawn)
        if source not in {'refill', 'era'} and drawn:
            self._track_event_progress('draw', amount=len(drawn), player=player)
        return drawn

    def _active_event_modifiers(self):
        return [
            modifier for modifier in (getattr(self, 'event_modifiers', []) or [])
            if int((modifier or {}).get('remaining_turns', 1) or 0) > 0
        ]

    def _event_modifier_active(self, modifier_type):
        return any((m or {}).get('type') == modifier_type for m in self._active_event_modifiers())

    def _event_reduce_cost_amount(self):
        return sum(int((m or {}).get('amount', 0) or 0) for m in self._active_event_modifiers() if (m or {}).get('type') == 'reduce_cost')

    def _event_modifier_from_effect(self, effect):
        modifier = dict(effect or {})
        duration = int(modifier.get('duration', 1) or 1)
        modifier['duration'] = max(1, duration)
        modifier['remaining_turns'] = int(modifier.get('remaining_turns', modifier['duration']) or modifier['duration'])
        modifier['event_id'] = (self.current_event or {}).get('id')
        modifier['event_name'] = (self.current_event or {}).get('name')
        return modifier

    def _tick_event_modifiers_at_turn_end(self):
        active = []
        for modifier in self._active_event_modifiers():
            remaining = int((modifier or {}).get('remaining_turns', 1) or 1) - 1
            if remaining > 0:
                next_modifier = dict(modifier)
                next_modifier['remaining_turns'] = remaining
                active.append(next_modifier)
        self.event_modifiers = active

    def _town_matches_region_alias(self, town, region):
        if not region:
            return True
        return town in set(self._towns_for_region_alias(region))

    def _event_scoped_card_range(self, player, card_type, target_region=None):
        best = None
        for modifier in self._active_event_modifiers():
            if (modifier or {}).get('type') != 'scoped_card_range':
                continue
            faction = modifier.get('player_faction')
            if faction and getattr(player, 'faction_id', None) != faction:
                continue
            allowed_types = set(modifier.get('card_types') or [])
            if allowed_types and card_type not in allowed_types:
                continue
            mod_region = modifier.get('target_region')
            if target_region and mod_region and target_region != mod_region:
                continue
            rng = int(modifier.get('range', 1) or 1)
            best = rng if best is None else max(best, rng)
        return best

    def _event_card_range_context(self, player, card):
        card_type = getattr(card, 'card_type', None)
        target_region = None
        scoped_range = self._event_scoped_card_range(player, card_type)
        if scoped_range is not None:
            for modifier in self._active_event_modifiers():
                if (modifier or {}).get('type') == 'scoped_card_range' and card_type in set(modifier.get('card_types') or []):
                    faction = modifier.get('player_faction')
                    if not faction or getattr(player, 'faction_id', None) == faction:
                        target_region = modifier.get('target_region')
                        break
        return {'range_limit': scoped_range or 1, 'target_region': target_region}

    def _gain_event_card(self, player, card_name, count=1):
        gained = 0
        for _ in range(int(count or 1)):
            if card_name in STATIC_PURCHASE_CARD_NAMES:
                supply = int(self.static_purchase_supply.get(card_name, 0) or 0)
                if supply <= 0:
                    self.log(f"Event could not gain {card_name}: static supply empty")
                    continue
                self.static_purchase_supply[card_name] = supply - 1
            player.deck.discard([self._starter_card(card_name)])
            gained += 1
        if gained:
            self.log(f"{player.name} gained {gained} {card_name} from event")
        return gained

    def _topdeck_static_purchase_card(self, target_player, card_name, source_name):
        if card_name in STATIC_PURCHASE_CARD_NAMES:
            supply = int(self.static_purchase_supply.get(card_name, 0) or 0)
            if supply <= 0:
                self.log(f"{source_name}: could not place {card_name} on {target_player.name}'s deck because static supply was empty")
                return False
            self.static_purchase_supply[card_name] = supply - 1
        target_player.deck.draw_pile.append(self._starter_card(card_name))
        return True

    def _red_player(self):
        return next((p for p in self.players if p.faction_id == 'red_army'), None)

    def _event_effect_player(self, default_player, effect):
        faction = (effect or {}).get('player_faction')
        if not faction:
            return default_player
        return next((p for p in self.players if getattr(p, 'faction_id', None) == faction), default_player)

    def _player_camp(self, player):
        faction = self.faction_by_id.get(getattr(player, 'faction_id', None), {})
        return faction.get('camp') or getattr(player, 'faction_id', None)

    def _player_matches_camp(self, player, camp):
        if not camp:
            return True
        return self._player_camp(player) == camp or getattr(player, 'faction_id', None) == camp

    def _players_matching_camp(self, camp):
        return [player for player in self.players if self._player_matches_camp(player, camp)]

    def _card_matches_types(self, card, card_types):
        if not card_types:
            return True
        return getattr(card, 'card_type', None) in set(card_types or [])

    def _event_build_towns_in_region(self, player, region):
        region_towns = set(self._towns_for_region_alias(region))
        return [
            {'town': town, 'region': region}
            for town in sorted(region_towns)
            if self.can_develop_in_town(player, town)
        ]

    def _apply_event_effect(self, effect, player, outcome='success'):
        effect = effect or {'type': 'none'}
        t = effect.get('type')
        count = int(effect.get('count', 1) or 1)
        player = self._event_effect_player(player, effect)
        if t in (None, 'none'):
            self.log(f"Event {outcome}: no effect")
            return {'success': True, 'effect': t or 'none'}
        if t == 'draw':
            self._draw_player_cards(player, count)
        elif t == 'gain_card':
            self._gain_event_card(player, effect.get('card'), count)
        elif t == 'discard_self':
            cards = list(player.hand)
            if not cards:
                self.log(f"Event {outcome}: {player.name} has no hand card to discard")
            else:
                self._set_pending_multi_card_choice(player, 'event_discard_self', cards, f"{self.current_event.get('name')}：請選擇 {min(count, len(cards))} 張手牌棄掉。", min(count, len(cards)), source_name=self.current_event.get('name'))
                return {'success': True, 'pending_choice': True}
        elif t == 'discard_random':
            for _ in range(min(count, len(player.hand))):
                card = random.choice(player.hand)
                player.hand.remove(card)
                player.deck.discard([card])
        elif t == 'red_dissolve':
            red = self._red_player()
            if red:
                targets = []
                for other in self.players:
                    if other is red:
                        continue
                    for town, n in (other.organizations or {}).items():
                        if n > 0 and self._event_trigger_matches_scope({'scope': effect.get('scope')}, town=town):
                            targets.append({'id': f'{other.id}:{town}', 'player_id': other.id, 'town': town, 'label': f'{other.name}｜{town}'})
                if targets:
                    self._set_pending_target_choice(red, 'event_red_dissolve', targets, f"{self.current_event.get('name')}：紅軍選擇要瓦解的組織。", source_name=self.current_event.get('name'))
                    return {'success': True, 'pending_choice': True}
        elif t == 'add_internal_conflict':
            self._gain_event_card(player, '內鬥', count)
        elif t == 'move':
            player.moves_left += count
        elif t in {'reduce_cost', 'restrict_build', 'ignore_distance', 'scoped_card_range'}:
            self.event_modifiers.append(self._event_modifier_from_effect(effect))
        elif t == 'build_organization':
            towns = [{'town': town} for town in sorted(self.map.get('towns', {})) if self.can_develop_in_town(player, town)]
            if towns:
                self._set_pending_town_choice(player, 'event_build_organization', towns, f"{self.current_event.get('name')}：選擇要建立組織的城鎮。", source_name=self.current_event.get('name'))
                return {'success': True, 'pending_choice': True}
        elif t == 'build_organization_in_region':
            region = effect.get('region')
            towns = self._event_build_towns_in_region(player, region)
            if towns:
                self._set_pending_town_choice(
                    player,
                    'event_build_organization',
                    towns,
                    f"{self.current_event.get('name')}：在指定區域免費建立 {min(count, len(towns))} 個組織。",
                    source_name=self.current_event.get('name'),
                    count=min(count, len(towns)),
                    region=region,
                    free=bool(effect.get('free', True)),
                    ignore_distance=bool(effect.get('ignore_distance', True)),
                )
                return {'success': True, 'pending_choice': True}
            self.log(f"Event {outcome}: {player.name} has no valid town in {region} to build")
        elif t == 'build_organization_near_own':
            max_steps = int(effect.get('max_steps', 1) or 1)
            towns = self._event_build_towns_near_own(player, max_steps=max_steps)
            if towns:
                self._set_pending_town_choice(
                    player,
                    'event_build_organization',
                    towns,
                    f"{self.current_event.get('name')}：在己方組織 {max_steps} 格內免費建立 {min(count, len(towns))} 個組織。",
                    source_name=self.current_event.get('name'),
                    count=min(count, len(towns)),
                )
                return {'success': True, 'pending_choice': True}
            self.log(f"Event {outcome}: {player.name} has no valid nearby town to build")
        elif t == 'topdeck_from_discard':
            cards = list(player.deck.discard_pile)
            if cards:
                choice_count = min(count, len(cards))
                if choice_count == 1:
                    self._set_pending_card_choice(
                        player,
                        'event_topdeck_from_discard',
                        cards,
                        f"{self.current_event.get('name')}：從棄牌堆選 1 張牌置於牌庫頂。",
                        source_name=self.current_event.get('name'),
                    )
                else:
                    self._set_pending_multi_card_choice(
                        player,
                        'event_topdeck_from_discard',
                        cards,
                        f"{self.current_event.get('name')}：從棄牌堆選 {choice_count} 張牌置於牌庫頂。",
                        choice_count,
                        source_name=self.current_event.get('name'),
                    )
                return {'success': True, 'pending_choice': True}
            self.log(f"Event {outcome}: {player.name} has no discard card to topdeck")
        elif t == 'trash_from_hand_or_discard':
            cards = [
                {'card': card, 'zone': 'hand', 'zone_label': '手牌'}
                for card in list(player.hand)
            ] + [
                {'card': card, 'zone': 'discard', 'zone_label': '棄牌堆'}
                for card in list(player.deck.discard_pile)
            ]
            if cards:
                choice_count = min(count, len(cards))
                prompt = f"{self.current_event.get('name')}：請從己方手牌或棄牌堆中移除 {choice_count} 張牌。"
                if choice_count == 1:
                    self._set_pending_card_choice(
                        player,
                        'trash_from_hand_or_discard',
                        cards,
                        prompt,
                        source_name=self.current_event.get('name'),
                        count=1,
                    )
                else:
                    self._set_pending_multi_card_choice(
                        player,
                        'trash_from_hand_or_discard',
                        cards,
                        prompt,
                        choice_count,
                        source_name=self.current_event.get('name'),
                    )
                return {'success': True, 'pending_choice': True}
            self.log(f"Event {outcome}: {player.name} has no hand/discard card to remove")
        self.log(f"Event {outcome} resolved: {self.current_event.get('name')} / {t}")
        return {'success': True, 'effect': t}

    def _settle_current_event(self):
        event = self.current_event or {}
        if event.get('type') != 'mission' or not self.event_progress or self.event_progress.get('settled'):
            return {'success': True}
        player = self.current_player()
        trigger = event.get('trigger') or {}
        if trigger.get('type') == 'end_turn_state' and not self.event_progress.get('succeeded'):
            met, count = self._event_state_condition_met(trigger, player)
            self.event_progress['count'] = count
            if met:
                self.event_progress['succeeded'] = True
                self.event_progress['status'] = 'success_pending'
        succeeded = bool(self.event_progress.get('succeeded'))
        effect = event.get('success') if succeeded else event.get('failure')
        self.event_progress['settled'] = True
        self.event_progress['status'] = 'success' if succeeded else 'failure'
        result = self._apply_event_effect(effect or {'type': 'none'}, player, outcome='success' if succeeded else 'failure')
        self.event_notification = self._event_display_payload()
        return result

    def _build_towns_by_ruler(self, map_data):
        grouped = {}
        for town, info in (map_data.get("towns", {}) or {}).items():
            for ruler in (info.get("ruler") or []):
                grouped.setdefault(ruler, []).append(town)
        for towns in grouped.values():
            towns.sort()
        return grouped

    def _towns_for_region_alias(self, region):
        alias_to_ruler = {
            "china": "紅軍",
            "taiwan": "臺灣",
            "hong_kong": "紅軍",
            "southeast_asia": "南洋",
            "manchuria": "滿洲",
            "outer_manchuria": "北國",
            "mongolian_plateau": "蒙古",
            "inner_mongolia": "紅軍",
            "turkestan": "紅軍",
            "tibet_region": "藏國",
            "india": "印度",
            "middle_east": "天方",
            "japan": "東洋",
            "korean_peninsula": "東洋",
            "trans_siberian": "北國",
            "anglo_america": "英美",
            "europe": "歐洲",
        }
        ruler = alias_to_ruler.get(region, region)
        towns = list(self.towns_by_ruler.get(ruler, []))
        if towns:
            return towns
        # Some era regions (for example tibet_region) are represented by camp tags
        # rather than ruler tags on the current map data.
        camp_towns = [
            town for town, info in (self.map.get("towns", {}) or {}).items()
            if ruler in (info.get("camp") or [])
        ]
        camp_towns.sort()
        return camp_towns

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

    def _is_starter_support_card(self, support_name):
        entry = self._support_taxonomy_entry(support_name) or {}
        return entry.get('cost') == '起始牌'

    def _init_decks(self):
        for p in self.players:
            starter = []
            for _ in range(7):
                starter.append(Card("追隨者", "propaganda", {"propaganda": 1}))
            for _ in range(3):
                starter.append(Card("樂捐者", "money", {"money": 1}))
            if p.faction_id == 'red_army':
                starter.append(self._make_support_card("紅軍奧援"))
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
        if support_name == '紅軍奧援':
            return {'money': 1, 'propaganda': 1}
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
        cards = []
        for name in STATIC_PURCHASE_CARD_NAMES:
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
            if not name or copies <= 0 or self._is_starter_support_card(name):
                continue
            support_pool.extend([self._make_support_card(name) for _ in range(copies)])

        general_pool = []
        excluded = set(STATIC_PURCHASE_CARD_NAMES) | {'追隨者', '樂捐者'}
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

    def _town_neighbors(self, town):
        if not town:
            return set()
        entry = self.map.get('towns', {}).get(town, {}) or {}
        return set(entry.get('road', []) or []) | set(entry.get('rail', []) or [])

    def _towns_within_steps(self, origins, max_steps=1):
        origins = [town for town in (origins or []) if town in self.map.get('towns', {})]
        if max_steps < 0 or not origins:
            return set()
        seen = set(origins)
        frontier = [(town, 0) for town in origins]
        while frontier:
            town, dist = frontier.pop(0)
            if dist >= max_steps:
                continue
            for nxt in self._town_neighbors(town):
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append((nxt, dist + 1))
        return seen

    def _player_has_org_within_steps_of_player(self, source_player, target_player, max_steps=1, target_region=None):
        source_towns = [town for town, count in (getattr(source_player, 'organizations', {}) or {}).items() if count > 0]
        target_towns = {
            town
            for town, count in (getattr(target_player, 'organizations', {}) or {}).items()
            if count > 0 and self._town_matches_region_alias(town, target_region)
        }
        if not source_towns or not target_towns:
            return False
        reachable = self._towns_within_steps(source_towns, max_steps=max_steps)
        return bool(reachable & target_towns)

    def _find_target_town_within_steps_of_player(self, source_player, target_player, max_steps=1, target_region=None):
        source_towns = [town for town, count in (getattr(source_player, 'organizations', {}) or {}).items() if count > 0]
        if not source_towns:
            return None
        reachable = self._towns_within_steps(source_towns, max_steps=max_steps)
        for town, count in (getattr(target_player, 'organizations', {}) or {}).items():
            if count > 0 and town in reachable and self._town_matches_region_alias(town, target_region):
                return town
        return None

    def _set_pending_card_choice(self, player, choice_key, cards, prompt, **extra):
        card_list = list(cards)
        card_zones = extra.pop('card_zones', None)
        if card_zones:
            normalized_cards = []
            for card, zone in zip(card_list, card_zones):
                normalized_cards.append({
                    'card': card,
                    'zone': zone.get('zone') if isinstance(zone, dict) else None,
                    'zone_label': zone.get('zone_label') if isinstance(zone, dict) else None,
                })
            card_list = normalized_cards
        self.pending_choice = {
            'type': 'card_choice',
            'choice_key': choice_key,
            'player_id': player.id,
            'cards': card_list,
            'prompt': prompt,
            **extra,
        }
        return {'pending_choice': True}

    def _set_pending_multi_card_choice(self, player, choice_key, cards, prompt, count, **extra):
        self.pending_choice = {
            'type': 'multi_card_choice',
            'choice_key': choice_key,
            'player_id': player.id,
            'cards': list(cards),
            'prompt': prompt,
            'count': count,
            **extra,
        }
        return {'pending_choice': True}

    def _set_pending_option_choice(self, player, choice_key, options, prompt, **extra):
        self.pending_choice = {
            'type': 'option_choice',
            'choice_key': choice_key,
            'player_id': player.id,
            'options': list(options),
            'prompt': prompt,
            **extra,
        }
        return {'pending_choice': True}

    def _set_pending_town_choice(self, player, choice_key, towns, prompt, **extra):
        normalized = []
        for town in list(towns or []):
            if isinstance(town, dict):
                item = dict(town)
            else:
                item = {'town': town}
            if item.get('town'):
                normalized.append(item)
        self.pending_choice = {
            'type': 'town_choice',
            'choice_key': choice_key,
            'player_id': player.id,
            'towns': normalized,
            'prompt': prompt,
            **extra,
        }
        return {'pending_choice': True}

    def _set_pending_target_choice(self, player, choice_key, targets, prompt, **extra):
        normalized = []
        for target in list(targets or []):
            if isinstance(target, dict):
                item = dict(target)
            else:
                item = {'id': str(target), 'label': str(target)}
            if item.get('id') is not None:
                normalized.append(item)
        self.pending_choice = {
            'type': 'target_choice',
            'choice_key': choice_key,
            'player_id': player.id,
            'targets': normalized,
            'prompt': prompt,
            **extra,
        }
        return {'pending_choice': True}

    def _set_pending_support_flow_choice(self, player, choice_key, step, prompt, **extra):
        self.pending_choice = {
            'type': 'support_flow_choice',
            'choice_key': choice_key,
            'player_id': player.id,
            'step': step,
            'prompt': prompt,
            **extra,
        }
        return {'pending_choice': True}

    def _resolve_underground_party(self, player, count=3):
        if not getattr(self, 'purchase_deck', None):
            return {'error': 'Purchase deck unavailable'}
        choices = self.purchase_deck.draw(count)
        if not choices:
            return {'error': 'Purchase deck empty'}
        self._set_pending_card_choice(
            player,
            'underground_party',
            choices,
            '地下黨：從購買區牌庫頂拿取3張牌，任選其中1張加入手牌，其餘移除。',
        )
        self.log(f"{player.name} revealed 3 cards for 地下黨")
        return {'pending_choice': True}

    def _resolve_card_choice(self, player, choice, index):
        cards = choice.get('cards') or []
        if index is None or index < 0 or index >= len(cards):
            return {'error': 'Invalid choice index'}
        chosen = cards[index]
        choice_key = choice.get('choice_key')

        if choice_key == 'recruit_talent':
            source_cards = choice.get('source_cards') or []
            chosen_entry = chosen if isinstance(chosen, dict) else None
            chosen_card = chosen_entry.get('card') if chosen_entry else chosen
            source_zone = None
            if chosen_entry:
                source_zone = chosen_entry.get('zone')
            elif chosen_card in player.deck.discard_pile:
                source_zone = 'discard_pile'
            elif chosen_card in player.deck.draw_pile:
                source_zone = 'draw_pile'
            for card in list(source_cards):
                if card is chosen_card:
                    continue
                if card in player.deck.draw_pile:
                    player.deck.draw_pile.remove(card)
                if card in player.deck.discard_pile:
                    player.deck.discard_pile.remove(card)
            if chosen_card in player.deck.draw_pile:
                player.deck.draw_pile.remove(chosen_card)
                source_zone = source_zone or 'draw_pile'
            if chosen_card in player.deck.discard_pile:
                player.deck.discard_pile.remove(chosen_card)
                source_zone = source_zone or 'discard_pile'
            player.hand.append(chosen_card)
            import random
            random.shuffle(player.deck.draw_pile)
            self.pending_choice = None
            chosen_name = getattr(chosen_card, 'name', str(chosen_card))
            if source_zone == 'discard_pile':
                self.log(f"{player.name} recruited {chosen_name} from discard via 網羅人才")
            else:
                self.log(f"{player.name} recruited {chosen_name} from deck")
            return {'success': True, 'chosen_card': chosen_name, 'source_zone': source_zone}

        if choice_key in {'gain_any_from_discard', 'gain_from_discard'}:
            if chosen not in player.deck.discard_pile:
                return {'error': 'Chosen card not in discard pile'}
            player.deck.discard_pile.remove(chosen)
            player.hand.append(chosen)
            self.pending_choice = None
            source_name = choice.get('source_name') or choice_key
            self.log(f"{player.name} gained {getattr(chosen, 'name', str(chosen))} from discard via {source_name}")
            return {'success': True, 'chosen_card': getattr(chosen, 'name', str(chosen))}

        if choice_key == 'event_topdeck_from_discard':
            if chosen not in player.deck.discard_pile:
                return {'error': 'Chosen card not in discard pile'}
            player.deck.discard_pile.remove(chosen)
            player.deck.draw_pile.append(chosen)
            self.pending_choice = None
            source_name = choice.get('source_name') or (self.current_event or {}).get('name') or choice_key
            chosen_name = getattr(chosen, 'name', str(chosen))
            self.log(f"{player.name} placed {chosen_name} on deck top via {source_name}")
            return {'success': True, 'chosen_card': chosen_name}

        if choice_key == 'underground_party':
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

        if choice_key == 'use_purchase_area_card':
            source_entry = chosen if isinstance(chosen, dict) else {'card': chosen}
            source = source_entry.get('card')
            purchase_index = source_entry.get('purchase_index')
            if source is None:
                return {'error': 'Chosen purchase-area card missing'}
            borrowed = self._copy_purchase_card(source)
            if purchase_index is not None:
                setattr(borrowed, '_return_to_purchase_area_index', purchase_index)
            player.hand.append(borrowed)
            self.pending_choice = None
            self.log(f"{player.name} borrowed {getattr(borrowed, 'name', str(borrowed))} from purchase area")
            borrowed_index = len(player.hand) - 1
            action_result = self.play_card(borrowed_index, mode='action')
            if action_result.get('error'):
                return action_result
            response = {
                'success': True,
                'chosen_card': getattr(borrowed, 'name', str(borrowed)),
                'purchase_index': purchase_index,
            }
            if 'pending_choice' in action_result:
                response['pending_choice'] = action_result.get('pending_choice')
            return response

        if choice_key == 'trash_from_hand_or_discard':
            card = chosen.get('card') if isinstance(chosen, dict) else chosen
            zone = chosen.get('zone') if isinstance(chosen, dict) else None
            zone_label = chosen.get('zone_label') if isinstance(chosen, dict) else None
            if zone == 'hand':
                if card not in player.hand:
                    return {'error': 'Chosen card not in hand'}
                player.hand.remove(card)
            elif zone == 'discard':
                if card not in player.deck.discard_pile:
                    return {'error': 'Chosen card not in discard pile'}
                player.deck.discard_pile.remove(card)
            else:
                return {'error': 'Unsupported trash source'}
            if getattr(card, 'name', str(card)) not in {'追隨者', '樂捐者'}:
                self.turn_log['non_starter_discard'] = True
            returned = self._return_removed_card_to_purchase_supply(card)
            if returned is None:
                returned = self._remove_card_from_game(card)
            self.pending_choice = None
            source_name = choice.get('source_name') or choice_key
            self.log(f"{player.name} trashed {getattr(card, 'name', str(card))} from {zone_label or zone} via {source_name}")
            return {
                'success': True,
                'chosen_card': getattr(card, 'name', str(card)),
                'zone': zone,
                'zone_label': zone_label,
                'removed_card': returned,
            }

        if choice_key == 'optional_trash':
            card = chosen.get('card') if isinstance(chosen, dict) else chosen
            zone = chosen.get('zone') if isinstance(chosen, dict) else None
            zone_label = chosen.get('zone_label') if isinstance(chosen, dict) else None
            removes_current_card = bool(chosen.get('removes_current_card')) if isinstance(chosen, dict) else False
            if card is None:
                return {'error': 'Chosen card missing'}
            if zone == 'current_card':
                pass
            elif zone == 'hand':
                if card not in player.hand:
                    return {'error': 'Chosen card not in hand'}
                player.hand.remove(card)
            else:
                return {'error': 'Unsupported optional trash source'}
            if getattr(card, 'name', str(card)) not in {'追隨者', '樂捐者'}:
                self.turn_log['non_starter_discard'] = True
            returned = self._return_removed_card_to_purchase_supply(card)
            if returned is None:
                returned = self._remove_card_from_game(card)
            if removes_current_card:
                choice_context = choice.get('context') if isinstance(choice.get('context'), dict) else None
                if isinstance(choice_context, dict):
                    choice_context['removed_current_card'] = True
            source_name = choice.get('source_name') or choice_key
            self.log(f"{player.name} trashed {getattr(card, 'name', str(card))} from {zone_label or zone} via {source_name}")
            followup = choice.get('followup_target_choice') if isinstance(choice, dict) else None
            if isinstance(followup, dict) and followup.get('targets'):
                self.pending_choice = {
                    'type': 'target_choice',
                    'choice_key': followup.get('choice_key') or 'target_choice',
                    'player_id': player.id,
                    'targets': list(followup.get('targets') or []),
                    'prompt': followup.get('prompt') or '請選擇目標。',
                    'source_name': followup.get('source_name') or source_name,
                    'context': {
                        'source_name': source_name,
                        'removed_card': returned,
                        'removed_current_card': removes_current_card,
                        'trashed_card_name': getattr(card, 'name', str(card)),
                        **(choice.get('context') if isinstance(choice.get('context'), dict) else {}),
                    },
                }
                return {
                    'success': True,
                    'chosen_card': getattr(card, 'name', str(card)),
                    'zone': zone,
                    'zone_label': zone_label,
                    'removed_card': returned,
                    'removed_current_card': removes_current_card,
                    'pending_choice': True,
                }
            self.pending_choice = None
            return {
                'success': True,
                'chosen_card': getattr(card, 'name', str(card)),
                'zone': zone,
                'zone_label': zone_label,
                'removed_card': returned,
                'removed_current_card': removes_current_card,
            }

        if choice_key in {'armed_target_discard', 'era_bonus_discard_on_red_card'}:
            if chosen not in player.hand:
                return {'error': 'Chosen card not in hand'}
            player.hand.remove(chosen)
            player.deck.discard([chosen])
            self.turn_log['successful_discard'] = True
            self.pending_choice = None
            initiator = next((p for p in self.players if getattr(p, 'id', None) == choice.get('initiator_player_id')), None)
            if initiator is not None and choice.get('draw_on_success'):
                self._draw_player_cards(initiator, int(choice.get('draw_on_success')))
            initiator_name = choice.get('initiator_player_name') or '其他玩家'
            target_name = choice.get('target_player_name') or player.name
            source_name = choice.get('source_name') or choice_key
            self.log(f"{initiator_name} used {source_name} to force {target_name} to discard {getattr(chosen, 'name', str(chosen))}")
            if choice_key == 'era_bonus_discard_on_red_card':
                self.turn_log.setdefault('era_effects_applied', []).append({
                    'era': (choice.get('context') or {}).get('era_id') if isinstance(choice.get('context'), dict) else None,
                    'type': 'bonus_discard_on_red_card',
                    'status': 'resolved',
                    'discarded_count': 1,
                    'target_player_id': getattr(player, 'id', None),
                })
            response = {
                'success': True,
                'discarded_card': getattr(chosen, 'name', str(chosen)),
                'target_player_name': target_name,
                'initiator_player_name': initiator_name,
                'choice_key': choice_key,
            }
            followup = self._start_era_followup_target_choice(choice.get('era_followup_target_choice'))
            if followup and followup.get('pending_choice'):
                response['pending_choice'] = True
            return response

        if choice_key == 'bait_exhaustion_target_discard':
            if chosen not in player.hand:
                return {'error': 'Chosen card not in hand'}
            player.hand.remove(chosen)
            player.deck.discard([chosen])
            self.turn_log['successful_discard'] = True
            self.pending_choice = None
            choice_context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            initiator_name = choice_context.get('initiator_player_name') or '其他玩家'
            target_name = choice_context.get('target_player_name') or player.name
            source_name = choice.get('source_name') or choice_context.get('source_name') or '誘導虛耗'
            self.log(f"{initiator_name} used {source_name} to force {target_name} to discard {getattr(chosen, 'name', str(chosen))}")
            return {
                'success': True,
                'discarded_card': getattr(chosen, 'name', str(chosen)),
                'target_player_name': target_name,
                'initiator_player_name': initiator_name,
                'choice_key': choice_key,
            }

        if choice_key == 'tianfang_support_target_discard':
            if chosen not in player.hand:
                return {'error': 'Chosen card not in hand'}
            player.hand.remove(chosen)
            player.deck.discard([chosen])
            self.pending_choice = None
            choice_context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            initiator_name = choice_context.get('initiator_player_name') or '其他玩家'
            target_name = choice_context.get('target_player_name') or player.name
            source_name = choice.get('source_name') or choice_context.get('source_name') or '天方奧援'
            self.log(f"{initiator_name} used {source_name} to force {target_name} to discard {getattr(chosen, 'name', str(chosen))}")
            return {
                'success': True,
                'discarded_card': getattr(chosen, 'name', str(chosen)),
                'target_player_name': target_name,
                'initiator_player_name': initiator_name,
                'choice_key': choice_key,
            }

        if choice_key == 'era_red_discard_to_build_near_target':
            if chosen not in player.hand:
                return {'error': 'Chosen card not in hand'}
            context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            effect = context.get('effect') if isinstance(context.get('effect'), dict) else {}
            towns = self._era_build_towns_near_target(player, effect)
            if not towns:
                return {'error': 'No valid era build towns'}
            player.hand.remove(chosen)
            player.deck.discard([chosen])
            source_name = choice.get('source_name') or context.get('era_name') or '時代關卡'
            self._set_pending_town_choice(
                player,
                'era_red_build_near_target',
                towns,
                f"{source_name}：選擇要免費建立紅軍組織的城鎮。",
                source_name=source_name,
                context={
                    **context,
                    'discarded_card': getattr(chosen, 'name', str(chosen)),
                },
            )
            self.log(f"{player.name} discarded {getattr(chosen, 'name', str(chosen))} for {source_name}")
            return {
                'success': True,
                'discarded_card': getattr(chosen, 'name', str(chosen)),
                'choice_key': choice_key,
                'pending_choice': True,
                'town_count': len(towns),
            }

        return {'error': 'Unsupported pending choice type'}

    def _resolve_multi_card_choice(self, player, choice, indices):
        cards = choice.get('cards') or []
        count = int(choice.get('count', 1) or 1)
        min_count = int(choice.get('min_count', count) if choice.get('min_count') is not None else count)
        if not isinstance(indices, list):
            return {'error': 'Invalid choice count'}
        if choice.get('choice_key') == 'red_army_ccdi_discard_draw':
            if len(indices) < min_count or len(indices) > count:
                return {'error': 'Invalid choice count'}
        elif len(indices) != count:
            return {'error': 'Invalid choice count'}
        if len(set(indices)) != len(indices):
            return {'error': 'Duplicate choice indices'}
        if any(i is None or i < 0 or i >= len(cards) for i in indices):
            return {'error': 'Invalid choice index'}
        choice_key = choice.get('choice_key')
        selected_cards = [cards[i] for i in indices]

        if choice_key == 'red_army_ccdi_discard_draw':
            ok, err = self._red_army_can_use_action(player, '中紀委')
            if not ok:
                return {'error': err}
            for card in selected_cards:
                if card not in player.hand:
                    return {'error': 'Chosen card not in hand'}
            for card in selected_cards:
                player.hand.remove(card)
                player.deck.discard([card])
            drawn = self._draw_player_cards(player, len(selected_cards)) if selected_cards else []
            self._mark_red_army_action_used('中紀委')
            self._track_event_progress('use_faction_ability', player=player)
            self.pending_choice = None
            self.log(f"{player.name} triggered 中紀委, discarded {len(selected_cards)}, and drew {len(drawn)}")
            return {
                'success': True,
                'name': '中紀委',
                'chosen_cards': [getattr(card, 'name', str(card)) for card in selected_cards],
                'discarded': len(selected_cards),
                'drawn': len(drawn),
                'choice_key': choice_key,
            }

        if choice_key == 'era_inspect_deck_top_and_reorder':
            inspected_cards = list(choice.get('cards') or [])
            top_count = int(choice.get('top_count', count) or count)
            if len(indices) != top_count:
                return {'error': 'Invalid choice count'}
            if any(card not in player.deck.draw_pile for card in inspected_cards):
                return {'error': 'Inspected deck cards changed'}
            for card in inspected_cards:
                player.deck.draw_pile.remove(card)
            selected_set = set(selected_cards)
            remaining_top_first = [card for card in inspected_cards if card not in selected_set]
            # Deck.draw() pops from the end, so append bottom-to-top. The first clicked
            # selected card becomes the next card drawn; the second clicked card is below it.
            player.deck.draw_pile.extend(reversed(remaining_top_first))
            player.deck.draw_pile.extend(reversed(selected_cards))
            self.pending_choice = None
            selected_names = [getattr(card, 'name', str(card)) for card in selected_cards]
            inspected_names = [getattr(card, 'name', str(card)) for card in inspected_cards]
            new_top_names = [getattr(card, 'name', str(card)) for card in reversed(player.deck.draw_pile[-top_count:])]
            self.turn_log.setdefault('era_effects_applied', []).append({
                'era': (choice.get('context') or {}).get('era_id') if isinstance(choice.get('context'), dict) else None,
                'type': 'inspect_deck_top_and_reorder',
                'inspected': inspected_names,
                'selected_top': selected_names,
            })
            source_name = choice.get('source_name') or '時代關卡'
            self.log(f"{player.name} reordered deck top via {source_name}: {', '.join(selected_names)}")
            return {
                'success': True,
                'choice_key': choice_key,
                'inspected_cards': inspected_names,
                'chosen_cards': selected_names,
                'deck_top': new_top_names,
            }

        if choice_key in {'discard_self', 'event_discard_self'}:
            for card in selected_cards:
                if card not in player.hand:
                    return {'error': 'Chosen card not in hand'}
            non_starters = [card for card in selected_cards if getattr(card, 'name', str(card)) not in {'追隨者', '樂捐者'}]
            if len(non_starters) == len(selected_cards):
                self.turn_log['non_starter_discard'] = True
            for card in selected_cards:
                player.hand.remove(card)
                player.deck.discard([card])
            if choice.get('grant_propaganda_if_all_non_starter') and len(non_starters) == len(selected_cards):
                player.resources['propaganda'] += int(choice.get('grant_propaganda_if_all_non_starter'))
            self.pending_choice = None
            self.log(f"{player.name} discarded {len(selected_cards)} chosen card(s)")
            return {'success': True, 'chosen_cards': [getattr(card, 'name', str(card)) for card in selected_cards]}

        if choice_key in {'armed_target_discard', 'era_bonus_discard_on_red_card'}:
            for card in selected_cards:
                if card not in player.hand:
                    return {'error': 'Chosen card not in hand'}
            for card in selected_cards:
                player.hand.remove(card)
                player.deck.discard([card])
            self.turn_log['successful_discard'] = True
            self.pending_choice = None
            initiator = next((p for p in self.players if getattr(p, 'id', None) == choice.get('initiator_player_id')), None)
            if initiator is not None and choice.get('draw_on_success'):
                self._draw_player_cards(initiator, int(choice.get('draw_on_success')))
            initiator_name = choice.get('initiator_player_name') or '其他玩家'
            target_name = choice.get('target_player_name') or player.name
            source_name = choice.get('source_name') or choice_key
            chosen_names = [getattr(card, 'name', str(card)) for card in selected_cards]
            self.log(f"{initiator_name} used {source_name} to force {target_name} to discard {len(chosen_names)} card(s)")
            if choice_key == 'era_bonus_discard_on_red_card':
                self.turn_log.setdefault('era_effects_applied', []).append({
                    'era': (choice.get('context') or {}).get('era_id') if isinstance(choice.get('context'), dict) else None,
                    'type': 'bonus_discard_on_red_card',
                    'status': 'resolved',
                    'discarded_count': len(chosen_names),
                    'target_player_id': getattr(player, 'id', None),
                })
            response = {
                'success': True,
                'chosen_cards': chosen_names,
                'target_player_name': target_name,
                'initiator_player_name': initiator_name,
                'choice_key': choice_key,
            }
            followup = self._start_era_followup_target_choice(choice.get('era_followup_target_choice'))
            if followup and followup.get('pending_choice'):
                response['pending_choice'] = True
            return response

        if choice_key == 'trash_from_hand_or_discard':
            starters = {'追隨者', '樂捐者'}
            chosen_cards = []
            zones = []
            removed_cards = []
            for entry in selected_cards:
                card = entry.get('card') if isinstance(entry, dict) else entry
                zone = entry.get('zone') if isinstance(entry, dict) else None
                zone_label = entry.get('zone_label') if isinstance(entry, dict) else None
                if zone == 'hand':
                    if card not in player.hand:
                        return {'error': 'Chosen card not in hand'}
                    player.hand.remove(card)
                elif zone == 'discard':
                    if card not in player.deck.discard_pile:
                        return {'error': 'Chosen card not in discard pile'}
                    player.deck.discard_pile.remove(card)
                else:
                    return {'error': 'Unsupported trash source'}
                if getattr(card, 'name', str(card)) not in starters:
                    self.turn_log['non_starter_discard'] = True
                returned = self._return_removed_card_to_purchase_supply(card)
                if returned is None:
                    returned = self._remove_card_from_game(card)
                chosen_cards.append(getattr(card, 'name', str(card)))
                zones.append(zone_label or zone)
                removed_cards.append(returned)
            self.pending_choice = None
            source_name = choice.get('source_name') or choice_key
            self.log(f"{player.name} trashed {len(chosen_cards)} chosen card(s) via {source_name}")
            return {
                'success': True,
                'chosen_cards': chosen_cards,
                'zones': zones,
                'removed_cards': removed_cards,
            }

        return {'error': 'Unsupported pending choice type'}

    def _resolve_option_choice(self, player, choice, index):
        options = choice.get('options') or []
        if index is None or index < 0 or index >= len(options):
            return {'error': 'Invalid choice index'}
        choice_key = choice.get('choice_key')

        if choice_key == 'choose_one':
            selected = options[index]
            context = dict(choice.get('context') or {})
            context['choice_index'] = index
            self.pending_choice = None
            result = None
            pending_target_result = None
            for nested in selected.get('effect', []):
                nested_type = nested.get('type') if isinstance(nested, dict) else None
                source_name = context.get('card_name') or choice.get('source_name')
                if nested_type == 'dissolve' and source_name == '情報網':
                    targets = self._interactive_support_dissolve_targets(player, require_self_sacrifice=False)
                    if targets:
                        pending_target_result = self._set_pending_target_choice(
                            player,
                            'intel_network_dissolve_target',
                            targets,
                            '情報網：選擇 1 個要瓦解的鄰近敵方組織。',
                            source_name='情報網',
                            context=context,
                        )
                        result = pending_target_result
                        continue
                nested_result = self.effect_engine.execute(nested, player, self, context=context)
                if isinstance(nested_result, dict) and nested_result.get('pending_choice'):
                    result = nested_result
            self.log(f"{player.name} resolved choose_one option {index}")
            return {
                'success': True,
                'choice_index': index,
                'label': selected.get('label'),
                **({'pending_choice': True} if isinstance(result, dict) and result.get('pending_choice') else {}),
            }

        if choice_key == 'end_turn_topdeck_action':
            selected = options[index]
            self.pending_choice = None
            if selected.get('action') == 'skip':
                self.log(f"{player.name} skipped end-turn action topdeck prompt")
                self._end_turn()
                return {'success': True, 'choice_index': index, 'skipped': True}
            hand_index = selected.get('hand_index')
            card_name = selected.get('card_name')
            if hand_index is None or hand_index < 0 or hand_index >= len(player.hand):
                return {'error': 'Chosen action card not in hand'}
            played_card = player.hand[hand_index]
            if getattr(played_card, 'name', str(played_card)) != card_name:
                return {'error': 'Chosen action card changed'}
            player.hand.pop(hand_index)
            structured = next((c for c in self.structured_cards if c.get('name') == card_name), None)
            for effect in list((structured or {}).get('effect') or []):
                self.effect_engine.execute(effect, player, self, context={'card_name': card_name})
            player.deck.discard([played_card])
            self.log(f"{player.name} used {card_name} before drawing new hand")
            self._end_turn()
            return {'success': True, 'choice_index': index, 'chosen_card': card_name}

        return {'error': 'Unsupported pending choice type'}

    def _resolve_town_choice(self, player, choice, index):
        towns = choice.get('towns') or []
        if index is None or index < 0 or index >= len(towns):
            return {'error': 'Invalid choice index'}
        selected = towns[index] or {}
        town = selected.get('town')
        if not town:
            return {'error': 'Invalid town choice'}
        choice_key = choice.get('choice_key')
        if choice_key == 'event_build_organization':
            player.organizations[town] = player.organizations.get(town, 0) + 1
            self.log(f"{player.name} built organization in {town} via event")
        elif choice_key == 'era_red_build_near_target':
            player.organizations[town] = player.organizations.get(town, 0) + 1
            self.turn_log.setdefault('era_effects_applied', []).append({
                'era': (choice.get('context') or {}).get('era_id'),
                'type': 'red_discard_to_build_near_target',
                'town': town,
                'discarded_card': (choice.get('context') or {}).get('discarded_card'),
            })
            self.log(f"{player.name} built organization in {town} via era effect")
        self.pending_choice = None
        return {
            'success': True,
            'choice_index': index,
            'town': town,
            'selected': selected,
            'choice_key': choice_key,
        }

    def _resolve_target_choice(self, player, choice, index):
        targets = choice.get('targets') or []
        if index is None or index < 0 or index >= len(targets):
            return {'error': 'Invalid choice index'}
        selected = targets[index] or {}
        target_id = selected.get('id')
        if target_id is None:
            return {'error': 'Invalid target choice'}
        choice_key = choice.get('choice_key')
        if choice_key == 'bait_exhaustion_target':
            target_player = next((p for p in self.players if getattr(p, 'id', None) == target_id), None)
            if target_player is None:
                return {'error': 'Target player not found'}
            if not getattr(target_player, 'hand', None):
                return {'error': 'Target player has no hand cards'}
            source_name = (choice.get('context') or {}).get('source_name') or '誘導虛耗'
            self.pending_choice = {
                'type': 'card_choice',
                'choice_key': 'bait_exhaustion_target_discard',
                'player_id': target_player.id,
                'cards': list(target_player.hand),
                'prompt': f"{source_name}：請選擇 1 張手牌棄掉。",
                'source_name': source_name,
                'context': {
                    'initiator_player_id': player.id,
                    'initiator_player_name': getattr(player, 'name', str(getattr(player, 'id', ''))),
                    'target_player_id': target_player.id,
                    'target_player_name': getattr(target_player, 'name', str(target_id)),
                    **(choice.get('context') if isinstance(choice.get('context'), dict) else {}),
                },
            }
            return {
                'success': True,
                'choice_index': index,
                'target_id': target_id,
                'selected': selected,
                'choice_key': choice_key,
                'target_player_name': getattr(target_player, 'name', str(target_id)),
                'pending_choice': True,
            }
        if choice_key in {'intel_network_dissolve_target', 'event_red_dissolve', 'era_red_bonus_dissolve_target'}:
            target_player_id = selected.get('player_id') or target_id
            town = selected.get('town')
            target_player = next((p for p in self.players if getattr(p, 'id', None) == target_player_id), None)
            if target_player is None:
                return {'error': 'Target player not found'}
            if not town:
                return {'error': 'Target town not found'}
            if choice_key == 'intel_network_dissolve_target' and not self._player_has_org_within_steps_of_player(player, target_player, max_steps=1):
                return {'error': 'Target player is not within range'}
            if choice_key == 'era_red_bonus_dissolve_target':
                context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
                max_steps = int(context.get('max_steps', 1) or 1)
                target_camp = context.get('target_camp')
                if target_camp and not self._player_matches_camp(target_player, target_camp):
                    return {'error': 'Target player is not valid for era effect'}
                source_towns = [src for src, count in (getattr(player, 'organizations', {}) or {}).items() if count > 0]
                if town not in self._towns_within_steps(source_towns, max_steps=max_steps):
                    return {'error': 'Target organization is not within era range'}
            result = self.dissolve_organization(player, target_player, town, source='card')
            if result.get('error'):
                return result
            self.pending_choice = None
            if choice_key == 'era_red_bonus_dissolve_target':
                self.turn_log.setdefault('era_effects_applied', []).append({
                    'era': (choice.get('context') or {}).get('era_id') if isinstance(choice.get('context'), dict) else None,
                    'type': 'bonus_dissolve_on_red_card_near_self',
                    'status': 'resolved',
                    'town': town,
                    'target_player_id': target_player_id,
                })
            return {
                'success': True,
                'choice_index': index,
                'target_id': target_id,
                'selected': selected,
                'choice_key': choice_key,
                'target_player_name': getattr(target_player, 'name', str(target_player_id)),
                'town': town,
            }
        if choice_key == 'red_army_propaganda_department_target':
            target_player = next((p for p in self.players if getattr(p, 'id', None) == target_id), None)
            if target_player is None or getattr(target_player, 'faction_id', None) == 'red_army':
                return {'error': 'Target player not found'}
            ok, err = self._red_army_can_use_action(player, '政工部', target_player.id)
            if not ok:
                return {'error': err}
            topdecked = '內鬥'
            added = self._topdeck_static_purchase_card(target_player, topdecked, '政工部')
            self._mark_red_army_action_used('政工部', target_player.id)
            self._track_event_progress('use_faction_ability', player=player)
            self.pending_choice = None
            if added:
                self.log(f"{player.name} triggered 政工部 and placed {topdecked} on {target_player.name}'s deck")
            else:
                self.log(f"{player.name} triggered 政工部 but {topdecked} supply was empty")
            return {
                'success': True,
                'choice_index': index,
                'target_id': target_id,
                'selected': selected,
                'choice_key': choice_key,
                'name': '政工部',
                'target_player_name': getattr(target_player, 'name', str(target_id)),
                'topdecked_card': topdecked if added else None,
                'static_supply_empty': not added,
            }
        if choice_key == 'red_army_state_security_target':
            target_player_id = selected.get('player_id') or target_id
            town = selected.get('town')
            target_player = next((p for p in self.players if getattr(p, 'id', None) == target_player_id), None)
            if target_player is None:
                return {'error': 'Target player not found'}
            if not town:
                return {'error': 'Target town not found'}
            ok, err = self._red_army_can_use_action(player, '國安部', target_player.id)
            if not ok:
                return {'error': err}
            result = self.dissolve_organization(player, target_player, town, source='faction_action')
            if result.get('error'):
                return result
            self._mark_red_army_action_used('國安部', target_player.id)
            self._track_event_progress('use_faction_ability', player=player)
            self.pending_choice = None
            return {
                'success': True,
                'choice_index': index,
                'target_id': target_id,
                'selected': selected,
                'choice_key': choice_key,
                'name': '國安部',
                'target_player_name': getattr(target_player, 'name', str(target_player_id)),
                'town': town,
            }
        if choice_key == 'red_support_target_player':
            target_player = next((p for p in self.players if getattr(p, 'id', None) == target_id), None)
            if target_player is None:
                return {'error': 'Target player not found'}
            context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            mode = choice.get('mode') or context.get('mode')
            card = context.get('card')
            if card is None:
                return {'error': 'Support card context missing'}
            if mode == 'resource':
                for key, value in getattr(card, 'resources', {}).items():
                    player.resources[key] += value
            elif mode != 'action':
                return {'error': 'Invalid support mode'}
            target_player.deck.discard([card])
            self.pending_choice = None
            self.log(f"{player.name} passed 紅軍奧援 to {target_player.name}'s discard pile")
            return {
                'success': True,
                'choice_index': index,
                'target_id': target_id,
                'selected': selected,
                'choice_key': choice_key,
                'target_player_name': getattr(target_player, 'name', str(target_id)),
                'moved_to_player_id': getattr(target_player, 'id', None),
                'moved_to_player_name': getattr(target_player, 'name', str(target_id)),
            }
        self.pending_choice = None
        return {
            'success': True,
            'choice_index': index,
            'target_id': target_id,
            'selected': selected,
            'choice_key': choice_key,
        }

    def _resolve_support_flow_choice(self, player, choice, index):
        step = choice.get('step')
        if step in {'town', 'sacrifice_town'}:
            result = self._resolve_town_choice(player, choice, index)
        elif step == 'target':
            result = self._resolve_target_choice(player, choice, index)
        else:
            return {'error': 'Unsupported support flow step'}
        if result.get('error'):
            return result
        response = self._resolve_support_interaction_result(player, result, choice)
        if not isinstance(response, dict) or response.get('error') or response.get('pending_choice'):
            return response
        context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
        followup = self._start_era_followup_discard_choice(context.get('era_followup_discard_choice'))
        if followup and followup.get('pending_choice'):
            response['pending_choice'] = True
        return response

    def resolve_pending_choice(self, player_id, index):
        choice = self.pending_choice or {}
        if not choice:
            return {'error': 'No pending choice'}
        if choice.get('player_id') != player_id:
            return {'error': 'Not your pending choice'}
        player = next((p for p in self.players if p.id == player_id), None)
        if not player:
            return {'error': 'Player not found'}
        if choice.get('type') == 'card_choice':
            return self._resolve_card_choice(player, choice, index)
        if choice.get('type') == 'multi_card_choice':
            return self._resolve_multi_card_choice(player, choice, index)
        if choice.get('type') == 'option_choice':
            return self._resolve_option_choice(player, choice, index)
        if choice.get('type') == 'town_choice':
            return self._resolve_town_choice(player, choice, index)
        if choice.get('type') == 'target_choice':
            return self._resolve_target_choice(player, choice, index)
        if choice.get('type') == 'support_flow_choice':
            return self._resolve_support_flow_choice(player, choice, index)
        if choice.get('type') == 'reaction_choice':
            return self._resolve_reaction_choice(player, choice, index)
        return {'error': 'Unsupported pending choice type'}

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
            return region_entry.get('tier_2') or region_entry.get('tier_3')
        return region_entry.get('tier_1')

    def _resolve_support_card_effect(self, card_name, tier, region_index):
        if card_name == '紅軍奧援':
            return 'red_support_draw_and_pass', {'draw': 1}
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
                return 'interactive_build_anywhere_inner', {'count': 1}
            if tier == 2 and region_index == 0:
                return 'interactive_build_anywhere_inner', {'count': 1}
            if tier == 2:
                return 'interactive_build_near_inner', {'count': 1}
            return 'gain_resource', {'propaganda': 2}
        if card_name == '北國奧援':
            if tier >= 3:
                return 'interactive_dissolve_many_near', {'count': 2}
            if tier == 2:
                return 'interactive_dissolve_many_near', {'count': 1}
            return 'interactive_dissolve_self_and_enemy', {'count': 1}
        if card_name == '臺灣奧援':
            if tier >= 3:
                return 'interactive_dissolve_and_build', {'count': 1}
            if tier == 2:
                return 'interactive_dissolve_many_near', {'count': 1}
            return 'gain_resource', {'propaganda': 1}
        if card_name == '天方奧援':
            if tier >= 3:
                return 'force_discard_near', {'count': 2, 'random': True}
            if tier == 2:
                return 'force_discard_near', {'count': 1, 'random': True}
            return 'force_discard_near', {'count': 1, 'random': False}
        if card_name == '紅軍奧援':
            return 'red_support_draw_and_pass', {'draw': 1}
        return 'text_only', {'text': text}

    def _interactive_support_build_towns(self, player, near_only=False):
        inner_towns = set(self._towns_for_region_alias('china'))
        if near_only:
            reachable = set()
            for origin in list((player.organizations or {}).keys()):
                neighbors = set(self.map.get('towns', {}).get(origin, {}).get('road', []) or []) | set(self.map.get('towns', {}).get(origin, {}).get('rail', []) or [])
                reachable |= {town for town in neighbors if town in inner_towns}
        else:
            reachable = inner_towns
        return [
            {'town': town}
            for town in sorted(reachable)
            if self.can_develop_in_town(player, town)
        ]

    def _target_players_for_interaction(self, player, target_player_id=None):
        if target_player_id is not None:
            target = next((p for p in self.players if getattr(p, 'id', None) == target_player_id), None)
            return [target] if target is not None and target is not player else []
        return [other for other in self.players if other is not player]

    def _interactive_support_dissolve_targets(self, player, require_self_sacrifice=False, max_steps=1, target_players=None, target_region=None):
        targets = []
        opponents = list(target_players) if target_players is not None else [other for other in self.players if other is not player]
        source_towns = [town for town, count in (player.organizations or {}).items() if count > 0]
        reachable = self._towns_within_steps(source_towns, max_steps=max_steps)
        for other in opponents:
            if other is None or other is player:
                continue
            for town, count in (other.organizations or {}).items():
                if count <= 0 or town not in reachable or not self._town_matches_region_alias(town, target_region):
                    continue
                targets.append({
                    'id': f'{getattr(other, "id", other.name)}::{town}',
                    'label': f'{other.name}｜{town}',
                    'player_id': getattr(other, 'id', None),
                    'town': town,
                    'requires_self_sacrifice': require_self_sacrifice,
                })
        return targets

    def _interactive_support_dissolve_targets_near_town(self, player, origin_town, max_steps=1, target_players=None, target_region=None):
        reachable = self._towns_within_steps([origin_town], max_steps=max_steps)
        targets = []
        opponents = list(target_players) if target_players is not None else [other for other in self.players if other is not player]
        for other in opponents:
            if other is None or other is player:
                continue
            for town, count in (other.organizations or {}).items():
                if count <= 0 or town not in reachable or not self._town_matches_region_alias(town, target_region):
                    continue
                targets.append({
                    'id': f'{getattr(other, "id", other.name)}::{town}',
                    'label': f'{other.name}｜{town}',
                    'player_id': getattr(other, 'id', None),
                    'town': town,
                    'sacrifice_town': origin_town,
                })
        return targets

    def _interactive_support_discard_targets_near(self, player):
        targets = []
        for other in self.players:
            if other is player:
                continue
            if not getattr(other, 'hand', None):
                continue
            if not self._player_has_org_within_steps_of_player(player, other, max_steps=1):
                continue
            targets.append({
                'id': getattr(other, 'id', None),
                'label': getattr(other, 'name', str(getattr(other, 'id', ''))),
                'player_id': getattr(other, 'id', None),
            })
        return targets

    def _interactive_support_sacrifice_towns(self, player, max_steps=1, target_players=None, target_region=None):
        towns = []
        for town, count in (player.organizations or {}).items():
            if count <= 0:
                continue
            targets = self._interactive_support_dissolve_targets_near_town(
                player,
                town,
                max_steps=max_steps,
                target_players=target_players,
                target_region=target_region,
            )
            if not targets:
                continue
            towns.append({
                'town': town,
                'label': f'{town}（可瓦解鄰近敵方組織）',
                'target_count': len(targets),
            })
        return towns

    def _start_card_dissolve_interaction(self, player, card_name, requires_self_sacrifice=False, range_limit=1, target_player_id=None, target_region=None, extra_context=None):
        target_players = self._target_players_for_interaction(player, target_player_id)
        effect_type = 'interactive_dissolve_self_and_enemy' if requires_self_sacrifice else 'interactive_dissolve_many_near'
        base_context = {
            'card_name': card_name,
            'effect_type': effect_type,
            'effect_payload': {'range': range_limit, 'target_region': target_region},
            'target_player_id': target_player_id,
            **(extra_context if isinstance(extra_context, dict) else {}),
        }
        if requires_self_sacrifice:
            towns = self._interactive_support_sacrifice_towns(
                player,
                max_steps=range_limit,
                target_players=target_players,
                target_region=target_region,
            )
            if not towns:
                return None
            result = self._set_pending_support_flow_choice(
                player,
                'card_dissolve_interaction',
                'sacrifice_town',
                f'{card_name}：先選擇 1 個要瓦解的己方組織。',
                source_name=card_name,
                towns=towns,
                context=base_context,
            )
            return {'pending_choice': True, **result}
        targets = self._interactive_support_dissolve_targets(
            player,
            require_self_sacrifice=False,
            max_steps=range_limit,
            target_players=target_players,
            target_region=target_region,
        )
        if not targets:
            return None
        result = self._set_pending_support_flow_choice(
            player,
            'card_dissolve_interaction',
            'target',
            f'{card_name}：選擇 1 個要瓦解的鄰近敵方組織。',
            source_name=card_name,
            targets=targets,
            context=base_context,
        )
        return {'pending_choice': True, **result}

    def _start_support_interaction(self, player, card_name, tier, region_index, effect_type, payload):
        effect_text = self._support_card_effect_text(card_name, tier, region_index)
        base_context = {
            'card_name': card_name,
            'tier': tier,
            'region_index': region_index,
            'effect_type': effect_type,
            'effect_payload': dict(payload or {}),
            'effect_text': effect_text,
        }
        if effect_type == 'interactive_build_anywhere_inner':
            towns = self._interactive_support_build_towns(player, near_only=False)
            if not towns:
                return None
            result = self._set_pending_support_flow_choice(
                player,
                'support_interaction',
                'town',
                f'{card_name}：選擇 1 個建立組織的牆內城鎮。',
                source_name=card_name,
                towns=towns,
                context=base_context,
            )
            return {'pending_choice': True, **result}
        if effect_type == 'interactive_build_near_inner':
            towns = self._interactive_support_build_towns(player, near_only=True)
            if not towns:
                return None
            result = self._set_pending_support_flow_choice(
                player,
                'support_interaction',
                'town',
                f'{card_name}：選擇 1 個己方組織 1 格內的牆內城鎮建立組織。',
                source_name=card_name,
                towns=towns,
                context=base_context,
            )
            return {'pending_choice': True, **result}
        if effect_type == 'interactive_dissolve_many_near':
            targets = self._interactive_support_dissolve_targets(player, require_self_sacrifice=False)
            if not targets:
                return None
            result = self._set_pending_support_flow_choice(
                player,
                'support_interaction',
                'target',
                f'{card_name}：選擇 1 個要瓦解的鄰近敵方組織。',
                source_name=card_name,
                targets=targets,
                context=base_context,
            )
            return {'pending_choice': True, **result}
        if effect_type == 'interactive_dissolve_self_and_enemy':
            towns = self._interactive_support_sacrifice_towns(player)
            if not towns:
                return None
            result = self._set_pending_support_flow_choice(
                player,
                'support_interaction',
                'sacrifice_town',
                f'{card_name}：先選擇 1 個要瓦解的己方組織。',
                source_name=card_name,
                towns=towns,
                context=base_context,
            )
            return {'pending_choice': True, **result}
        if effect_type == 'interactive_dissolve_and_build':
            targets = self._interactive_support_dissolve_targets(player, require_self_sacrifice=False)
            if not targets:
                return None
            result = self._set_pending_support_flow_choice(
                player,
                'support_interaction',
                'target',
                f'{card_name}：先選擇 1 個要瓦解的敵方組織，成功後可在同地建立組織。',
                source_name=card_name,
                targets=targets,
                context=base_context,
            )
            return {'pending_choice': True, **result}
        if effect_type == 'force_discard_near':
            targets = self._interactive_support_discard_targets_near(player)
            if not targets:
                return None
            count = int((payload or {}).get('count', 0) or 0)
            random_pick = bool((payload or {}).get('random'))
            discard_text = f'隨機棄 {count} 張手牌' if random_pick else '選 1 張手牌棄掉'
            result = self._set_pending_support_flow_choice(
                player,
                'support_interaction',
                'target',
                f'{card_name}：選擇 1 位己方組織 1 格內的玩家，令其{discard_text}。',
                source_name=card_name,
                targets=targets,
                context=base_context,
            )
            return {'pending_choice': True, **result}
        return None

    def _resolve_support_interaction_result(self, player, result, choice):
        context = dict((choice or {}).get('context') or {})
        effect_type = context.get('effect_type')
        card_name = context.get('card_name') or '奧援卡'
        if effect_type in {'interactive_build_anywhere_inner', 'interactive_build_near_inner'}:
            town = result.get('town')
            if not town or not self.can_develop_in_town(player, town):
                return {'error': 'Invalid build town'}
            player.organizations[town] = player.organizations.get(town, 0) + 1
            self.log(f"{player.name} resolved {card_name} and built in {town}")
            return {'success': True, 'town': town}
        if effect_type == 'interactive_dissolve_self_and_enemy' and choice.get('step') == 'sacrifice_town':
            sacrifice_town = result.get('town')
            if not sacrifice_town or (player.organizations or {}).get(sacrifice_town, 0) <= 0:
                return {'error': 'Invalid own organization to sacrifice'}
            targets = self._interactive_support_dissolve_targets_near_town(
                player,
                sacrifice_town,
                max_steps=int((context.get('effect_payload') or {}).get('range', 1) or 1),
                target_players=self._target_players_for_interaction(player, context.get('target_player_id')),
            )
            if not targets:
                return {'error': 'No enemy organization within range of sacrificed organization'}
            player.organizations[sacrifice_town] -= 1
            if player.organizations[sacrifice_town] <= 0:
                del player.organizations[sacrifice_town]
            self.log(f"{player.name} dissolved 1 own organization at {sacrifice_town} for {card_name}")
            next_context = dict(context)
            next_context['sacrifice_town'] = sacrifice_town
            self._set_pending_support_flow_choice(
                player,
                'support_interaction',
                'target',
                f'{card_name}：選擇 {sacrifice_town} 1 格內的 1 個敵方組織瓦解。',
                source_name=card_name,
                targets=targets,
                context=next_context,
            )
            return {'success': True, 'pending_choice': True, 'town': sacrifice_town}
        if effect_type in {'interactive_dissolve_many_near', 'interactive_dissolve_self_and_enemy', 'interactive_dissolve_and_build'}:
            selected = result.get('selected') or {}
            target_player_id = selected.get('player_id')
            town = selected.get('town')
            target_player = next((p for p in self.players if getattr(p, 'id', None) == target_player_id), None)
            if target_player is None or not town:
                return {'error': 'Invalid dissolve target'}
            if effect_type == 'interactive_dissolve_self_and_enemy':
                sacrifice_town = context.get('sacrifice_town')
                if not sacrifice_town:
                    return {'error': 'Missing sacrificed organization'}
                if town not in self._towns_within_steps([sacrifice_town], max_steps=1):
                    return {'error': 'Target organization is not within range of sacrificed organization'}
            dissolve_result = self.dissolve_organization(player, target_player, town, source='support_card')
            if dissolve_result.get('error'):
                return dissolve_result
            if effect_type == 'interactive_dissolve_and_build' and self.can_develop_in_town(player, town):
                player.organizations[town] = player.organizations.get(town, 0) + 1
                self.log(f"{player.name} resolved {card_name} and built in {town} after dissolve")
            return {'success': True, 'town': town, 'target_player_id': target_player_id}
        if effect_type == 'force_discard_near':
            selected = result.get('selected') or {}
            target_player_id = selected.get('player_id') or selected.get('id')
            target_player = next((p for p in self.players if getattr(p, 'id', None) == target_player_id), None)
            if target_player is None:
                return {'error': 'Invalid discard target'}
            if not getattr(target_player, 'hand', None):
                return {'error': 'Target player has no hand cards'}
            if choice_key == 'intel_network_dissolve_target' and not self._player_has_org_within_steps_of_player(player, target_player, max_steps=1):
                return {'error': 'Target player is not within range'}
            count = int(context.get('effect_payload', {}).get('count', 0) or 0)
            random_pick = bool(context.get('effect_payload', {}).get('random'))
            if random_pick:
                discarded_names = []
                for _ in range(min(count, len(target_player.hand))):
                    idx = random.randrange(len(target_player.hand))
                    discarded = target_player.hand.pop(idx)
                    discarded_names.append(getattr(discarded, 'name', str(discarded)))
                    target_player.deck.discard([discarded])
                self.log(f"{player.name} resolved {card_name} targeting {target_player.name} and discarded {len(discarded_names)} random card(s)")
                return {
                    'success': True,
                    'target_player_id': target_player_id,
                    'target_player_name': getattr(target_player, 'name', str(target_player_id)),
                    'discarded_cards': discarded_names,
                }
            self.pending_choice = {
                'type': 'card_choice',
                'choice_key': 'tianfang_support_target_discard',
                'player_id': target_player.id,
                'cards': list(target_player.hand),
                'prompt': f"{card_name}：請選擇 1 張手牌棄掉。",
                'source_name': card_name,
                'context': {
                    'initiator_player_id': player.id,
                    'initiator_player_name': getattr(player, 'name', str(getattr(player, 'id', ''))),
                    'target_player_id': target_player.id,
                    'target_player_name': getattr(target_player, 'name', str(target_player_id)),
                    **context,
                },
            }
            return {
                'success': True,
                'pending_choice': True,
                'target_player_id': target_player_id,
                'target_player_name': getattr(target_player, 'name', str(target_player_id)),
            }
        return {'error': 'Unsupported support interaction result'}

    def _resolve_red_support_target_choice(self, player, card, mode):
        current_faction = self.faction_by_id.get(player.faction_id, {})
        current_camp = current_faction.get('camp')
        if current_camp != 'red_army':
            return None
        targets = [
            {'id': getattr(other, 'id', None), 'label': getattr(other, 'name', str(getattr(other, 'id', '')))}
            for other in self.players
            if other is not player and self.faction_by_id.get(other.faction_id, {}).get('camp') != 'red_army'
        ]
        if not targets:
            return None
        self._set_pending_target_choice(
            player,
            'red_support_target_player',
            targets,
            '紅軍奧援：請選擇要將本牌放入哪位反共玩家的棄牌堆。',
            source_name='紅軍奧援',
            mode=mode,
            context={
                'card_name': '紅軍奧援',
                'mode': mode,
                'card': card,
            },
        )
        return {'pending_choice': True, 'card_moved_out_of_play': True}

    def _execute_support_card(self, player, card):
        card_name = getattr(card, 'name', str(card))
        tier, region_index, matched = self._support_card_tier(player, card_name)
        effect_type, payload = self._resolve_support_card_effect(card_name, tier, region_index)
        interaction_started = self._start_support_interaction(player, card_name, tier, region_index, effect_type, payload)
        if interaction_started:
            self.log(f"{player.name} started interactive support resolution for {card_name} at tier {tier}")
            return {'tier': tier, 'matched_rulers': matched, 'effect_type': effect_type, 'effect_text': self._support_card_effect_text(card_name, tier, region_index), 'pending_choice': True}
        if effect_type == 'gain_resource':
            player.resources['money'] += int(payload.get('money', 0) or 0)
            player.resources['propaganda'] += int(payload.get('propaganda', 0) or 0)
        elif effect_type == 'red_support_draw_and_pass':
            self._draw_player_cards(player, int(payload.get('draw', 0) or 0))
            current_faction = self.faction_by_id.get(player.faction_id, {})
            current_camp = current_faction.get('camp')
            pending_red_target = self._resolve_red_support_target_choice(player, card, mode='action')
            if pending_red_target and pending_red_target.get('pending_choice'):
                return {
                    'tier': tier,
                    'matched_rulers': matched,
                    'effect_type': effect_type,
                    'effect_text': self._support_card_effect_text(card_name, tier, region_index),
                    'pending_choice': True,
                    'card_moved_out_of_play': True,
                }
            if current_camp == 'red_army':
                target = next((p for p in self.players if p is not player and self.faction_by_id.get(p.faction_id, {}).get('camp') != 'red_army'), None)
            else:
                target = next((p for p in self.players if p is not player and self.faction_by_id.get(p.faction_id, {}).get('camp') == 'red_army'), None)
            if target is not None:
                target.deck.discard([card])
                self.log(f"{player.name} passed {card_name} to {target.name}'s discard pile")
                return {
                    'tier': tier,
                    'matched_rulers': matched,
                    'effect_type': effect_type,
                    'effect_text': self._support_card_effect_text(card_name, tier, region_index),
                    'moved_to_player_id': getattr(target, 'id', None),
                    'moved_to_player_name': target.name,
                    'card_moved_out_of_play': True,
                }
        elif effect_type == 'draw':
            self._draw_player_cards(player, int(payload.get('count', 0) or 0))
        elif effect_type == 'draw_then_discard':
            draw_count = int(payload.get('draw', 0) or 0)
            discard_count = int(payload.get('discard', 0) or 0)
            self._draw_player_cards(player, draw_count)
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
            inner_towns = self._towns_for_region_alias('china')
            target_town = next((town for town in inner_towns if self.can_develop_in_town(player, town)), None)
            if target_town:
                player.organizations[target_town] = player.organizations.get(target_town, 0) + 1
        elif effect_type == 'build_near_inner':
            inner_towns = set(self._towns_for_region_alias('china'))
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
                "任意牆內": self._towns_for_region_alias("china"),
                "任意牆內城鎮": self._towns_for_region_alias("china"),
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
            "任意牆內": self._towns_for_region_alias("china"),
            "任意牆內城鎮": self._towns_for_region_alias("china"),
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
            "red_army_action_count": 0,
            "red_army_targeted_actions": {},
            "india_flag_money_triggered": False,
            "purchased_cards_this_turn": [],
            "reaction_prompted_player_ids": [],
            "red_army_base_dissolves": {},
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
        support_region = entry.get("support_region")
        best_tier = 1
        best_idx = 0 if (entry.get("regions", []) or []) else None
        best_matched = []
        for idx, region in enumerate(entry.get("regions", []) or []):
            preferred = region.get("preferred_rulers", []) or []
            matched = [r for r in preferred if r in present]
            tier = 1
            if support_region and support_region in present and region.get("tier_3"):
                tier = 3
            elif len(matched) >= len(preferred) and preferred:
                tier = 2
            if tier > best_tier or (tier == best_tier and best_matched == [] and matched):
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
        resources = getattr(card, 'resources', None)
        if isinstance(resources, dict):
            return self._resource_total(resources)
        return self._purchase_area_card_cost_total(card)

    def _non_red_players(self):
        return [p for p in self.players if getattr(p, 'faction_id', None) != 'red_army']

    def _red_army_action_limit(self):
        return len(self._non_red_players())

    def _red_army_action_count(self):
        return int(self.turn_log.get('red_army_action_count', 0) or 0)

    def _red_army_targeted_action_key(self, action_name, target_player_id):
        return f'{action_name}:{target_player_id}'

    def _red_army_can_use_action(self, player, action_name, target_player_id=None):
        if getattr(player, 'faction_id', None) != 'red_army':
            return False, 'Only Red Army can use this faction action'
        if self._red_army_action_count() >= self._red_army_action_limit():
            return False, 'Red Army faction action limit reached this turn'
        if action_name in {'政工部', '國安部'} and target_player_id:
            used = self.turn_log.setdefault('red_army_targeted_actions', {})
            if used.get(self._red_army_targeted_action_key(action_name, target_player_id)):
                return False, f'{action_name} already used on this player this turn'
        return True, None

    def _mark_red_army_action_used(self, action_name, target_player_id=None):
        self.turn_log['red_army_action_count'] = self._red_army_action_count() + 1
        if action_name in {'政工部', '國安部'} and target_player_id:
            used = self.turn_log.setdefault('red_army_targeted_actions', {})
            used[self._red_army_targeted_action_key(action_name, target_player_id)] = True
        self.turn_log['faction_action_used'] = self._red_army_action_count() >= self._red_army_action_limit()

    def _red_army_target_players(self, action_name):
        targets = []
        for other in self._non_red_players():
            if action_name in {'政工部', '國安部'}:
                ok, _ = self._red_army_can_use_action(self._red_player(), action_name, getattr(other, 'id', None))
                if not ok:
                    continue
            targets.append({
                'id': getattr(other, 'id', None),
                'label': getattr(other, 'name', str(getattr(other, 'id', ''))),
                'player_id': getattr(other, 'id', None),
            })
        return targets

    def _red_army_state_security_targets(self, player):
        inner_towns = set(self._towns_for_region_alias('china'))
        targets = []
        reachable = self._towns_within_steps([
            town for town, count in (player.organizations or {}).items() if count > 0
        ], max_steps=1)
        for other in self._non_red_players():
            ok, _ = self._red_army_can_use_action(player, '國安部', getattr(other, 'id', None))
            if not ok:
                continue
            for town, count in (other.organizations or {}).items():
                if count > 0 and town in inner_towns and town in reachable:
                    targets.append({
                        'id': f'{getattr(other, "id", other.name)}::{town}',
                        'label': f'{other.name}｜{town}',
                        'player_id': getattr(other, 'id', None),
                        'town': town,
                    })
        return targets

    def _resolve_red_army_action_target(self, player, action_name, target_player_id=None):
        if target_player_id:
            target = next((p for p in self.players if getattr(p, 'id', None) == target_player_id), None)
            if target is None or getattr(target, 'faction_id', None) == 'red_army':
                return None, {'error': 'Invalid Red Army target'}
            ok, err = self._red_army_can_use_action(player, action_name, target_player_id)
            if not ok:
                return None, {'error': err}
            return target, None
        targets = self._red_army_target_players(action_name)
        if not targets:
            return None, {'error': 'No valid target'}
        self._set_pending_target_choice(
            player,
            'red_army_propaganda_department_target' if action_name == '政工部' else 'red_army_state_security_player',
            targets,
            f'{action_name}：請選擇目標玩家。',
            source_name=action_name,
        )
        return None, {'pending_choice': True}

    def _start_red_army_state_security(self, player):
        targets = self._red_army_state_security_targets(player)
        if not targets:
            return {'error': 'No valid State Security target'}
        self._set_pending_target_choice(
            player,
            'red_army_state_security_target',
            targets,
            '國安部：選擇其他玩家在紅軍組織 1 格內的 1 個牆內組織瓦解。',
            source_name='國安部',
        )
        return {'pending_choice': True}

    def _activated_faction_action(self, player, action_name, **kwargs):
        red_army_actions = {'統戰部', '政工部', '國安部', '中紀委'}
        skip_reaction_prompt = bool(kwargs.pop('_skip_reaction_prompt', False))
        if action_name not in red_army_actions and self.turn_log.get('faction_action_used'):
            return {"error": "Faction action already used this turn"}

        if action_name in red_army_actions and not skip_reaction_prompt:
            target_player_id = kwargs.get('target_player_id') if action_name in {'政工部'} else None
            ok, err = self._red_army_can_use_action(player, action_name, target_player_id)
            if not ok:
                return {'error': err}
            prompt = self._red_army_action_reaction_prompt(player, action_name, kwargs)
            if prompt:
                return prompt

        if action_name == '統戰部':
            ok, err = self._red_army_can_use_action(player, action_name)
            if not ok:
                return {'error': err}
            drawn = self._draw_player_cards(player, 1)
            self._mark_red_army_action_used(action_name)
            self._track_event_progress('use_faction_ability', player=player)
            self.log(f"{player.name} triggered 統戰部 and drew {len(drawn)} card(s)")
            return {'success': True, 'result': {'name': action_name, 'drawn': len(drawn)}}

        if action_name == '政工部':
            target, pending_or_error = self._resolve_red_army_action_target(player, action_name, kwargs.get('target_player_id'))
            if pending_or_error:
                return pending_or_error
            topdecked = '內鬥'
            added = self._topdeck_static_purchase_card(target, topdecked, action_name)
            self._mark_red_army_action_used(action_name, target.id)
            self._track_event_progress('use_faction_ability', player=player)
            if added:
                self.log(f"{player.name} triggered 政工部 and placed {topdecked} on {target.name}'s deck")
            else:
                self.log(f"{player.name} triggered 政工部 but {topdecked} supply was empty")
            return {'success': True, 'result': {'name': action_name, 'target_player_name': target.name, 'topdecked_card': topdecked if added else None, 'static_supply_empty': not added}}

        if action_name == '國安部':
            ok, err = self._red_army_can_use_action(player, action_name)
            if not ok:
                return {'error': err}
            return self._start_red_army_state_security(player)

        if action_name == '中紀委':
            ok, err = self._red_army_can_use_action(player, action_name)
            if not ok:
                return {'error': err}
            cards = list(player.hand)
            if not cards:
                self._mark_red_army_action_used(action_name)
                self._track_event_progress('use_faction_ability', player=player)
                self.log(f"{player.name} triggered 中紀委 with no hand cards")
                return {'success': True, 'result': {'name': action_name, 'discarded': 0, 'drawn': 0}}
            self._set_pending_multi_card_choice(
                player,
                'red_army_ccdi_discard_draw',
                cards,
                '中紀委：可棄掉任意張手牌，然後抽等量的牌。',
                len(cards),
                source_name='中紀委',
                min_count=0,
            )
            return {'pending_choice': True}

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
            self._track_event_progress('use_faction_ability', player=player)
            self.log(f"{player.name} triggered 民主陣線 and gained a removed card proxy")
            return {"success": True}

        if action_name == '立場試探':
            if not player.deck.draw_pile:
                return {"error": "Deck empty"}
            card = player.deck.draw_pile.pop()
            total = self._top_card_cost_total(card)
            self.turn_log['faction_action_used'] = True
            self._track_event_progress('use_faction_ability', player=player)
            destination = 'hand' if total % 2 == 1 else 'discard'
            if destination == 'hand':
                player.hand.append(card)
                self.log(f"{player.name} triggered 立場試探 and added {card.name} to hand")
            else:
                player.deck.discard([card])
                self.log(f"{player.name} triggered 立場試探 and discarded {card.name}")
            return {
                "success": True,
                "result": {
                    "name": action_name,
                    "revealed_card": getattr(card, 'name', str(card)),
                    "cost_total": total,
                    "destination": destination,
                },
            }

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
            self._track_event_progress('use_faction_ability', player=player)
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
            reward = {
                "money": 3 if action_name == '賭徒耳語' and hit else (2 if action_name == '民族祭儀' and hit else 0),
                "propaganda": 3 if action_name == '賭徒耳語' and hit else (2 if action_name == '民族祭儀' else 0),
            }
            return {
                "success": True,
                "result": {
                    "name": action_name,
                    "revealed_card": getattr(card, 'name', str(card)),
                    "cost_total": total,
                    "guess": guess,
                    "hit": hit,
                    "reward": reward,
                    "destination": "discard",
                },
            }

        return {"error": "Unknown faction action"}

    def _apply_guerrilla_on_build(self, player, town):
        if self.turn_log.get("guerrilla_triggered"):
            return
        if not self._player_has_ability(player, "游擊隊"):
            return
        inner_towns = set(self._towns_for_region_alias("china"))
        if town not in inner_towns:
            return

        self.turn_log["guerrilla_triggered"] = True
        red_player = next((p for p in self.players if p.faction_id == "red_army"), None)
        if red_player and red_player.hand:
            discarded = red_player.hand.pop()
            red_player.deck.discard([discarded])
            self.log(f"{player.name} triggered 游擊隊 and forced {red_player.name} to discard {getattr(discarded, 'name', str(discarded))}")
        else:
            self._draw_player_cards(player, 1)
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
        if name in {"分神", "內鬥"}:
            return Card(name, "disruption", {})
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
        built_in_china = any(t in set(self._towns_for_region_alias("china")) for t in built_towns)
        built_in_nanyang = any(t in {"曼谷", "吉隆坡", "新加坡", "雅加達", "河內", "胡志明市", "仰光"} for t in built_towns)

        for ability in effective:
            if not isinstance(ability, dict):
                continue
            name = ability.get("name")
            if name in {"本土社團", "選我河山", "還我河山"} and built_in_china:
                self._draw_player_cards(player, 1)
                self.log(f"{player.name} triggered {name} and drew 1 card")
            elif name == "民國之心" and (built_in_china or built_in_nanyang):
                self._draw_player_cards(player, 1)
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

        # Red Army can only develop where explicit red camp tag exists, and destroyed Red Army bases cannot be rebuilt.
        if faction_id == "red_army":
            if town in set(getattr(self, 'red_army_destroyed_bases', set()) or []):
                return False
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
            player.hand.insert(1, Card("可移除手牌", "command", {}))

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

        if card_name == '情報網':
            player.organizations = {'北京': 1}
            other_players = [p for p in self.players if p is not player]
            if other_players:
                other_players[0].organizations = {'天津': 1}
                other_players[0].deck.discard_pile = [starter('對手棄牌A')]
            if len(other_players) > 1:
                other_players[1].deck.discard_pile = [starter('對手棄牌B')]
            if len(other_players) > 2:
                other_players[2].deck.discard_pile = [starter('對手棄牌C')]

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

    def _reaction_card_cancel_predicate(self, reaction_card_name, canceled_cost):
        if reaction_card_name == '爆料黑幕':
            return True
        if reaction_card_name == '產業滲透':
            return int((canceled_cost or {}).get('money', 0) or 0) > 0
        if reaction_card_name == '情報網':
            return True
        return False

    def _reaction_prompt_candidates(self, acting_player, played_card):
        cost = self._card_purchase_cost(played_card) or {}
        candidates = []
        for player in self.players:
            if player is acting_player:
                continue
            if player.id in set(self.turn_log.get('reaction_prompted_player_ids') or []):
                continue
            cards = []
            for hand_index, hand_card in enumerate(getattr(player, 'hand', []) or []):
                name = getattr(hand_card, 'name', str(hand_card))
                if name not in {'爆料黑幕', '產業滲透', '情報網'}:
                    continue
                if not self._reaction_card_cancel_predicate(name, cost):
                    continue
                cards.append({'name': name, 'card_index': hand_index})
            if cards:
                candidates.append({'player': player, 'cards': cards})
        return candidates

    def _resume_reaction_pending_action(self, choice, reaction_context=None):
        player = choice.get('acting_player')
        played_card = choice.get('played_card')
        card_name = choice.get('played_card_name')
        effective_type = choice.get('effective_type')
        action_context = dict(choice.get('action_context') or {})
        red_army_action_name = action_context.get('red_army_action_name')
        if red_army_action_name:
            if reaction_context is not None:
                self._resolve_reaction_context(reaction_context)
                self.log(f"{player.name}'s {red_army_action_name} was canceled by reaction")
                return {"success": True, "canceled": True}
            red_kwargs = dict(action_context.get('red_army_action_kwargs') or {})
            red_kwargs['_skip_reaction_prompt'] = True
            return self._activated_faction_action(player, red_army_action_name, **red_kwargs)
        action_context['current_card'] = played_card
        action_context['card_name'] = card_name
        support_resolution = choice.get('support_resolution')

        if reaction_context is not None:
            action_context['reaction_context'] = reaction_context
            action_context['card_canceled'] = True

        if effective_type != 'support':
            if card_name in getattr(self.action_engine, 'cards', {}):
                if not action_context.get('card_canceled'):
                    action_result = self.action_engine.execute(card_name, player, self, context=action_context, include_resources=False)
                    if isinstance(action_result, dict) and action_result.get('pending_choice'):
                        if not action_context.get('removed_current_card'):
                            if not self._return_borrowed_card_to_owner_topdeck(played_card):
                                player.deck.discard([played_card])
                        self.log(f"{player.name} played {card_name}")
                        return {"success": True, "pending_choice": True}

        self._resolve_reaction_context(reaction_context)

        for ability in self._player_effective_abilities(player):
            if not isinstance(ability, dict):
                continue
            name = ability.get("name")
            if name == "商貿組織" and effective_type == "money" and not self.turn_log.get("faction_first_money_triggered"):
                self.turn_log["faction_first_money_triggered"] = True
                self._draw_player_cards(player, 1)
                self.log(f"{player.name} triggered 商貿組織 and drew 1 card")
            elif name in {"民族調和", "星星之火"} and effective_type == "propaganda" and not self.turn_log.get("faction_first_propaganda_triggered"):
                self.turn_log["faction_first_propaganda_triggered"] = True
                self._draw_player_cards(player, 1)
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

        if self.pending_choice:
            if not action_context.get('removed_current_card'):
                if not self._return_borrowed_card_to_owner_topdeck(played_card):
                    player.deck.discard([played_card])
            self.log(f"{player.name} played {card_name}")
            return {"success": True, "pending_choice": True}

        if not action_context.get('removed_current_card'):
            if not self._return_borrowed_card_to_owner_topdeck(played_card):
                player.deck.discard([played_card])
        self.log(f"{player.name} played {card_name}")
        return {"success": True}

    def _set_pending_reaction_choice(self, reacting_player, acting_player, played_card, card_name, candidates, effective_type, action_context, support_resolution=None):
        prompted = self.turn_log.setdefault('reaction_prompted_player_ids', [])
        if reacting_player.id not in prompted:
            prompted.append(reacting_player.id)
        self.pending_choice = {
            'type': 'reaction_choice',
            'choice_key': 'cancel_other_player_action',
            'player_id': reacting_player.id,
            'acting_player': acting_player,
            'acting_player_id': acting_player.id,
            'acting_player_name': acting_player.name,
            'played_card': played_card,
            'played_card_name': card_name,
            'effective_type': effective_type,
            'action_context': dict(action_context or {}),
            'support_resolution': support_resolution,
            'cards': list(candidates),
            'prompt': f'{acting_player.name} 打出 {card_name}。是否要取消對方的行動？',
            'source_name': '取消反應',
        }
        return {'pending_choice': True}

    def _resolve_reaction_choice(self, player, choice, index):
        cards = choice.get('cards') or []
        if index is None:
            return {'error': 'Invalid choice index'}
        if index == 0:
            self.pending_choice = None
            result = self._resume_reaction_pending_action(choice, reaction_context=None)
            result['skipped_reaction'] = True
            return result
        card_choice_index = index - 1
        if card_choice_index < 0 or card_choice_index >= len(cards):
            return {'error': 'Invalid choice index'}
        selected = cards[card_choice_index]
        reaction_context = self._build_reaction_context(
            choice.get('acting_player'),
            choice.get('played_card'),
            choice.get('played_card_name'),
            'action',
            {'player_id': player.id, 'card_index': selected.get('card_index')},
        )
        if reaction_context is None:
            return {'error': 'Invalid reaction card'}
        self.pending_choice = None
        result = self._resume_reaction_pending_action(choice, reaction_context=reaction_context)
        result['reaction_card'] = reaction_context.get('reaction_card_name')
        result['canceled_card'] = reaction_context.get('canceled_card_name')
        return result

    def _build_reaction_context(self, player, played_card, card_name, mode, reaction):
        if mode != 'action' or not reaction:
            return None
        reaction_player_id = reaction.get('player_id')
        reaction_card_index = reaction.get('card_index')
        reaction_player = next((p for p in self.players if getattr(p, 'id', None) == reaction_player_id), None)
        if reaction_player is None or reaction_player == player or reaction_card_index is None:
            return None
        if reaction_card_index < 0 or reaction_card_index >= len(reaction_player.hand):
            return None
        reaction_card = reaction_player.hand[reaction_card_index]
        reaction_card_name = getattr(reaction_card, 'name', str(reaction_card))
        if reaction_card_name not in {'爆料黑幕', '產業滲透', '情報網'}:
            return None

        cost = self._card_purchase_cost(played_card) or {}
        if not self._reaction_card_cancel_predicate(reaction_card_name, cost):
            return None

        reaction_played = reaction_player.hand.pop(reaction_card_index)
        reaction_context = {
            'reacting_player': reaction_player,
            'reaction_card': reaction_played,
            'reaction_card_name': reaction_card_name,
            'canceled_card': played_card,
            'canceled_card_name': card_name,
            'canceled_card_cost': cost,
        }
        self.turn_log['canceled_card'] = True
        has_propaganda_cost = int(cost.get('propaganda', 0) or 0) > 0
        has_money_cost = int(cost.get('money', 0) or 0) > 0
        if reaction_card_name == '爆料黑幕':
            self.turn_log['canceled_propaganda_card'] = has_propaganda_cost
        elif reaction_card_name == '產業滲透':
            self.turn_log['canceled_money_cost_card'] = has_money_cost
        self.log(f"{reaction_player.name} reacted with {reaction_card_name} to cancel {card_name}")
        return reaction_context

    def _red_army_action_reaction_prompt(self, player, action_name, kwargs):
        virtual_card = Card(action_name, 'command', {})
        reaction_candidates = self._reaction_prompt_candidates(player, virtual_card)
        if not reaction_candidates:
            return None
        first_candidate = reaction_candidates[0]
        return self._set_pending_reaction_choice(
            first_candidate['player'],
            player,
            virtual_card,
            action_name,
            first_candidate['cards'],
            'action',
            {
                'red_army_action_name': action_name,
                'red_army_action_kwargs': dict(kwargs or {}),
            },
        )

    def _resolve_reaction_context(self, reaction_context):
        if reaction_context is None:
            return
        reaction_player = reaction_context['reacting_player']
        reaction_card_name = reaction_context.get('reaction_card_name') or '爆料黑幕'
        if reaction_card_name == '情報網':
            self.effect_engine.execute({'type': 'cancel_card'}, reaction_player, self, context=reaction_context)
        else:
            self.action_engine.execute(reaction_card_name, reaction_player, self, context=reaction_context, include_resources=False)
        return_borrowed = self._return_borrowed_card_to_owner_topdeck(reaction_context['reaction_card'])
        if not return_borrowed and reaction_context['reaction_card'] not in reaction_player.deck.discard_pile:
            reaction_player.deck.discard([reaction_context['reaction_card']])

    def play_card(self, index, mode=None, target_player_id=None, reaction=None):
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Not in ACTION phase"}

        if mode not in {"resource", "action"}:
            return {"error": "Card play mode must be resource or action"}

        player = self.current_player()
        if index < 0 or index >= len(player.hand):
            return {"error": "Invalid index"}
        pending_card = player.hand[index]
        pending_card_name = getattr(pending_card, "name", str(pending_card))
        if mode == "action" and self._card_is_banned_for_player(player, pending_card):
            return {"error": "非暴力：不能打出武裝或裝備類卡牌"}
        if mode == "action" and pending_card_name == "走漏風聲" and target_player_id is not None:
            target = next((p for p in self.players if getattr(p, "id", None) == target_player_id), None)
            if target is None or target == player:
                return {"error": "走漏風聲必須指定其他玩家"}
        if mode == "action" and pending_card_name in {"武裝者", "武裝小隊", "武裝集團"}:
            target = next((p for p in self.players if getattr(p, "id", None) == target_player_id), None) if target_player_id is not None else None
            if target is None or target == player:
                return {"error": "武裝卡必須指定其他玩家"}
            range_context = self._event_card_range_context(player, pending_card)
            if not self._player_has_org_within_steps_of_player(player, target, max_steps=range_context['range_limit'], target_region=range_context['target_region']):
                return {"error": "Target player has no organization within range"}
        if mode == "action" and pending_card_name in {"派遣間諜", "內應間諜"} and target_player_id is not None:
            target = next((p for p in self.players if getattr(p, "id", None) == target_player_id), None)
            if target is None or target == player:
                return {"error": "間諜卡必須指定其他玩家"}
            target_players = [target]
            range_context = self._event_card_range_context(player, pending_card)
            if pending_card_name == "派遣間諜":
                valid = bool(self._interactive_support_sacrifice_towns(player, max_steps=range_context['range_limit'], target_players=target_players, target_region=range_context['target_region']))
            else:
                valid = bool(self._interactive_support_dissolve_targets(player, max_steps=range_context['range_limit'], target_players=target_players, target_region=range_context['target_region']))
            if not valid:
                return {"error": "No target organization within range"}

        played_card = player.hand.pop(index)
        card_name = pending_card_name

        if mode == "resource":
            if getattr(played_card, 'name', str(played_card)) == '紅軍奧援':
                support_resolution = self._resolve_red_support_target_choice(player, played_card, mode='resource')
                if support_resolution and support_resolution.get('pending_choice'):
                    self.log(f"{player.name} played {card_name} as resource")
                    return {"success": True, "pending_choice": True}
            for key, value in getattr(played_card, 'resources', {}).items():
                player.resources[key] += value
            self._apply_era_resource_card_bonus(player, played_card)
            purchase_cost = self._card_purchase_cost(played_card)
            if int(purchase_cost.get('money', 0) or 0) > 0:
                self._track_event_progress('play_card_with_money', player=player)
            if int(purchase_cost.get('propaganda', 0) or 0) > 0:
                self._track_event_progress('play_card_with_propaganda', player=player)
            if not self._return_borrowed_card_to_owner_topdeck(played_card):
                player.deck.discard([played_card])
            self.log(f"{player.name} played {card_name} as resource")
            return {"success": True}

        effective_type = getattr(played_card, "card_type", None)
        if getattr(played_card, 'name', str(played_card)) == '紅軍奧援' and mode == "action":
            self._draw_player_cards(player, 1)
            support_resolution = self._resolve_red_support_target_choice(player, played_card, mode='action')
            if support_resolution and support_resolution.get('pending_choice'):
                self.log(f"{player.name} played {card_name}")
                return {"success": True, **support_resolution}
            player.deck.discard([played_card])
            self.log(f"{player.name} played {card_name}")
            return {"success": True}
        if self._player_has_ability(player, "國際線") and getattr(played_card, "card_type", None) == "money":
            effective_type = "propaganda"

        support_resolution = None
        action_context = {'current_card': played_card, 'card_name': card_name}
        era_followup_target_choice = self._era_followup_target_choice_for_play_card(player, played_card)
        if era_followup_target_choice:
            action_context['era_followup_target_choice'] = era_followup_target_choice
        era_followup_discard_choice = self._era_followup_discard_choice_for_play_card(player, played_card, target_player_id=target_player_id)
        if era_followup_discard_choice:
            action_context['era_followup_discard_choice'] = era_followup_discard_choice
        if target_player_id is not None:
            action_context['target_player_id'] = target_player_id
        if effective_type == 'support':
            support_resolution = self._execute_support_card(player, played_card)
            if support_resolution and support_resolution.get('pending_choice'):
                if support_resolution.get('card_moved_out_of_play'):
                    action_context['removed_current_card'] = True
                if not action_context.get('removed_current_card'):
                    if not self._return_borrowed_card_to_owner_topdeck(played_card):
                        player.deck.discard([played_card])
                self.log(f"{player.name} played {card_name}")
                return {"success": True, "pending_choice": True, **support_resolution}
            if support_resolution and support_resolution.get('card_moved_out_of_play'):
                action_context['removed_current_card'] = True
        elif effective_type == "money":
            self.turn_log["played_money_card"] = True
        if effective_type == "propaganda":
            self.turn_log["played_propaganda_card"] = True
        purchase_cost = self._card_purchase_cost(played_card)
        if int(purchase_cost.get('money', 0) or 0) > 0:
            self._track_event_progress('play_card_with_money', player=player)
        if int(purchase_cost.get('propaganda', 0) or 0) > 0:
            self._track_event_progress('play_card_with_propaganda', player=player)
        if self._player_has_india_research_room(player) and self._is_india_flag_card(played_card) and not self.turn_log.get("india_flag_money_triggered"):
            self.turn_log["india_flag_money_triggered"] = True
            player.resources["money"] += 2
            self.log(f"{player.name} triggered 印度研究分析室 and gained 2 money")

        if card_name not in {"追隨者", "樂捐者"}:
            played_names = self.turn_log.setdefault("played_nonstarter_names", [])
            if card_name not in played_names:
                played_names.append(card_name)

        reaction_context = self._build_reaction_context(player, played_card, card_name, mode, reaction)
        if reaction_context is None and reaction is None:
            reaction_candidates = self._reaction_prompt_candidates(player, played_card)
            if reaction_candidates:
                first_candidate = reaction_candidates[0]
                return self._set_pending_reaction_choice(
                    first_candidate['player'],
                    player,
                    played_card,
                    card_name,
                    first_candidate['cards'],
                    effective_type,
                    action_context,
                    support_resolution=support_resolution,
                )

        if reaction_context is not None:
            action_context['reaction_context'] = reaction_context
            action_context['card_canceled'] = True
        if effective_type != 'support':
            if card_name in {"派遣間諜", "內應間諜"}:
                if not action_context.get('card_canceled'):
                    spy_result = self._start_card_dissolve_interaction(
                        player,
                        card_name,
                        requires_self_sacrifice=(card_name == "派遣間諜"),
                        range_limit=self._event_card_range_context(player, played_card)['range_limit'],
                        target_player_id=target_player_id,
                        target_region=self._event_card_range_context(player, played_card)['target_region'],
                        extra_context={'era_followup_discard_choice': action_context.get('era_followup_discard_choice')} if action_context.get('era_followup_discard_choice') else None,
                    )
                    if spy_result and spy_result.get('pending_choice'):
                        if not action_context.get('removed_current_card'):
                            if not self._return_borrowed_card_to_owner_topdeck(played_card):
                                player.deck.discard([played_card])
                        self.log(f"{player.name} played {card_name}")
                        return {"success": True, "pending_choice": True, **spy_result}
                    return {"error": "No target organization within range"}
            elif card_name in getattr(self.action_engine, 'cards', {}):
                if not action_context.get('card_canceled'):
                    action_result = self.action_engine.execute(card_name, player, self, context=action_context, include_resources=False)
                    if isinstance(action_result, dict) and action_result.get('pending_choice'):
                        self._apply_era_play_card_effects(player, played_card)
                        if not action_context.get('removed_current_card'):
                            if not self._return_borrowed_card_to_owner_topdeck(played_card):
                                player.deck.discard([played_card])
                        self.log(f"{player.name} played {card_name}")
                        return {"success": True, "pending_choice": True}
            else:
                pass

        self._resolve_reaction_context(reaction_context)

        for ability in self._player_effective_abilities(player):
            if not isinstance(ability, dict):
                continue
            name = ability.get("name")
            if name == "商貿組織" and effective_type == "money" and not self.turn_log.get("faction_first_money_triggered"):
                self.turn_log["faction_first_money_triggered"] = True
                self._draw_player_cards(player, 1)
                self.log(f"{player.name} triggered 商貿組織 and drew 1 card")
            elif name in {"民族調和", "星星之火"} and effective_type == "propaganda" and not self.turn_log.get("faction_first_propaganda_triggered"):
                self.turn_log["faction_first_propaganda_triggered"] = True
                self._draw_player_cards(player, 1)
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

        if self.pending_choice:
            if not action_context.get('removed_current_card'):
                if not self._return_borrowed_card_to_owner_topdeck(played_card):
                    player.deck.discard([played_card])
            self.log(f"{player.name} played {card_name}")
            return {"success": True, "pending_choice": True}

        if not action_context.get('removed_current_card'):
            self._apply_era_play_card_effects(player, played_card)
            if not self._return_borrowed_card_to_owner_topdeck(played_card):
                player.deck.discard([played_card])
        self.log(f"{player.name} played {card_name}")
        return {"success": True}

    def _available_purchased_cards_for_end_turn_topdeck(self, player):
        purchased = list(self.turn_log.get('purchased_cards_this_turn') or [])
        return [card for card in purchased if card in player.deck.discard_pile]

    def _prompt_end_turn_topdeck_action_if_available(self):
        player = self.current_player()
        if not self._available_purchased_cards_for_end_turn_topdeck(player):
            return None
        eligible_names = {'行動預告', '行動募資'}
        options = [{'label': '不使用', 'action': 'skip'}]
        for idx, card in enumerate(list(player.hand)):
            card_name = getattr(card, 'name', str(card))
            if card_name in eligible_names:
                options.append({'label': f'使用 {card_name}', 'action': 'use', 'card_name': card_name, 'hand_index': idx})
        if len(options) <= 1:
            return None
        self._set_pending_option_choice(
            player,
            'end_turn_topdeck_action',
            options,
            '回合結束前：你本回合有購得的牌，可使用行動預告／行動募資將其中 1 張置於牌庫頂，接著補牌時抽上手。',
        )
        self.log(f"{player.name} may use 行動預告/行動募資 before drawing new hand")
        return {'pending_choice': True}

    def advance_turn_phase(self):
        if self.pending_choice:
            return {"error": "Resolve pending choice before advancing phase"}
        if self.turn_phase == TurnPhase.EVENT:
            self._check_era_trigger()
            if not self.current_event:
                self._start_event_phase()
                return {"success": True}
            self.turn_phase = TurnPhase.ACTION
        elif self.turn_phase == TurnPhase.ACTION:
            event_result = self._settle_current_event()
            if event_result and event_result.get('pending_choice'):
                return {"success": True, "pending_choice": True}
            self.turn_phase = TurnPhase.END
        elif self.turn_phase == TurnPhase.END:
            pending = self._prompt_end_turn_topdeck_action_if_available()
            if pending:
                return {"success": True, "pending_choice": True}
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

        self.current_event = None
        self.event_progress = None
        self._tick_event_modifiers_at_turn_end()
        self.event_notification = None
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
        if self._event_modifier_active('restrict_build'):
            return {"error": "Current event restricts building organizations"}
        if town not in self.map.get("towns", {}):
            return {"error": "Invalid town"}
        if not self._town_has_shared_org_access(player, town):
            return {"error": "No organization in town"}
        if town in set(getattr(self, 'red_army_destroyed_bases', set()) or []) and getattr(player, 'faction_id', None) == 'red_army':
            return {"error": "Red Army base has been destroyed and cannot be rebuilt"}
        if not self.can_develop_in_town(player, town):
            return {"error": "Cannot develop in this town"}

        player.organizations[town] = player.organizations.get(town, 0) + 1
        self.turn_log.setdefault("built_towns", []).append(town)
        self._track_event_progress('build_organization', town=town, player=player)
        self._apply_era_build_effects(player, town)
        self._apply_guerrilla_on_build(player, town)
        self.log(f"{player.name} built organization in {town}")
        return {"success": True}

    def build_organization_with_support(self, origin_town, target_town):
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Not in ACTION phase"}

        player = self.current_player()
        if not origin_town or not target_town:
            return {"error": "Origin and target required"}
        if self._event_modifier_active('restrict_build'):
            return {"error": "Current event restricts building organizations"}
        if origin_town not in self.map.get("towns", {}) or target_town not in self.map.get("towns", {}):
            return {"error": "Invalid town"}
        origin_owner = self._shared_origin_owner(player, origin_town)
        if not origin_owner:
            return {"error": "No organization in origin"}
        if target_town in set(getattr(self, 'red_army_destroyed_bases', set()) or []) and getattr(player, 'faction_id', None) == 'red_army':
            return {"error": "Red Army base has been destroyed and cannot be rebuilt"}
        if not self.can_develop_in_town(player, target_town):
            return {"error": "Cannot develop in this town"}

        safehouse_bonus = 1 if self._player_has_ability(player, "安全屋") else 0
        max_distance = 1 + int(getattr(player, 'build_range_bonus', 0) or 0) + safehouse_bonus
        if origin_town != target_town and (not self._event_modifier_active('ignore_distance') or self._era_restricts_ignore_distance_build(player, target_town)):
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
        self._track_event_progress('build_organization', town=target_town, player=player)
        self._apply_era_build_effects(player, target_town)
        self._apply_guerrilla_on_build(player, target_town)
        self.log(f"{player.name} built organization in {target_town} from {origin_town}")
        return {"success": True}

    def _record_red_army_base_dissolve(self, attacker, target_owner, town):
        if getattr(target_owner, 'faction_id', None) != 'red_army':
            return
        if town != getattr(target_owner, 'base', None):
            return
        counts = self.turn_log.setdefault('red_army_base_dissolves', {})
        attacker_id = getattr(attacker, 'id', getattr(attacker, 'name', 'attacker'))
        key = f'{attacker_id}:{town}'
        counts[key] = int(counts.get(key, 0) or 0) + 1
        if counts[key] < 2:
            return
        self.red_army_destroyed_bases.add(town)
        if target_owner.organizations.get(town, 0) > 0:
            del target_owner.organizations[town]
        if getattr(target_owner, 'base', None) == town:
            target_owner.base = None
        self.log(f"{attacker.name} destroyed Red Army base at {town}")

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
        self._record_red_army_base_dissolve(attacker, target_owner, town)

        if target_owner is defender:
            self.log(f"{attacker.name} dissolved 1 organization from {defender.name} at {town}")
        else:
            self.log(f"{attacker.name} dissolved 1 shared organization via {defender.name} from {target_owner.name} at {town}")

        inner_towns = set(self._towns_for_region_alias("china"))
        if town in inner_towns and any(self._player_has_ability(target_owner, n) for n in {"殉道者", "青山里"}):
            self._draw_player_cards(target_owner, 1)
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
        if to_town not in neighbors and not self._event_modifier_active('ignore_distance'):
            return {"error": f"No {mode} connection"}
        if getattr(origin_owner, 'faction_id', None) == 'red_army' and not self.can_faction_develop_in_town('red_army', to_town):
            return {"error": "Red Army organization cannot leave Red Army development space"}

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
        self._track_event_progress('move_organization', player=player)
        if origin_owner is player:
            self.log(f"{player.name} moved 1 organization from {from_town} to {to_town} via {mode}")
        else:
            self.log(f"{player.name} moved 1 shared organization from {origin_owner.name}:{from_town} to {to_town} via {mode}")
        return {"success": True}

    def _card_purchase_cost(self, card):
        card_name = getattr(card, 'name', str(card))
        if getattr(card, "card_type", None) == "support" or getattr(card, "type", None) == "support":
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

    def _return_borrowed_card_to_owner_topdeck(self, card):
        purchase_index = getattr(card, '_return_to_purchase_area_index', None)
        if purchase_index is not None:
            if 0 <= purchase_index < len(getattr(self, 'purchase_area', []) or []):
                self.log(f"{getattr(card, 'name', str(card))} returned to purchase area slot {purchase_index}")
                return True
        owner_id = getattr(card, '_return_to_owner_topdeck', None)
        if not owner_id:
            return False
        owner = next((p for p in self.players if getattr(p, 'id', None) == owner_id), None)
        if owner is None:
            return False
        try:
            delattr(card, '_return_to_owner_topdeck')
        except AttributeError:
            pass
        owner.deck.draw_pile.append(card)
        self.log(f"{getattr(card, 'name', str(card))} returned to {owner.name}'s deck top")
        return True

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
        reduction = self._event_reduce_cost_amount()
        if reduction > 0:
            money_reduction = min(cost_money, reduction)
            cost_money -= money_reduction
            reduction -= money_reduction
            if reduction > 0:
                cost_propaganda = max(0, cost_propaganda - reduction)

        era_reduction = self._era_purchase_cost_reduction(player, card)
        cost_money = max(0, cost_money - int(era_reduction.get('money', 0) or 0))
        cost_propaganda = max(0, cost_propaganda - int(era_reduction.get('propaganda', 0) or 0))

        if self._player_has_ability(player, "華文傳媒") and card_type == "propaganda":
            if player.resources['money'] < cost_propaganda:
                return {"error": "Not enough money for propaganda purchase"}
            player.resources['money'] -= cost_propaganda
        else:
            if player.resources['money'] < cost_money or player.resources['propaganda'] < cost_propaganda:
                return {"error": "Not enough resources"}
            player.resources['money'] -= cost_money
            player.resources['propaganda'] -= cost_propaganda

        purchased_card = self._copy_purchase_card(card)
        player.deck.discard([purchased_card])
        self.turn_log.setdefault('purchased_cards_this_turn', []).append(purchased_card)
        if is_static_purchase:
            self.static_purchase_supply[card_name] = int(self.static_purchase_supply.get(card_name, 0) or 0) - 1
        else:
            self.purchase_area.pop(index)
        self.log(f"{player.name} bought {card_name}")
        event_result = self._track_event_purchase(purchased_card, original_cost=cost, player=player)
        if isinstance(event_result, dict) and event_result.get('pending_choice'):
            return {"success": True, "pending_choice": True}
        return {"success": True}

    # ---------- Era Trigger ----------

    def _era_effect_target_players(self, effect):
        camp = (effect or {}).get('target_camp')
        faction = (effect or {}).get('target_faction')
        if faction:
            return [p for p in self.players if getattr(p, 'faction_id', None) == faction]
        if camp:
            return self._players_matching_camp(camp)
        return []

    def _apply_era_static_cards_to_discard(self, effect, era_name):
        card_name = (effect or {}).get('card')
        count = int((effect or {}).get('count', 1) or 1)
        targets = self._era_effect_target_players(effect)
        added = {}
        for target in targets:
            gained = self._gain_event_card(target, card_name, count)
            added[target.id] = gained
            if gained:
                self.log(f"Era {era_name}: added {gained} {card_name} to {target.name}'s discard")
        return added

    def _apply_era_draw(self, effect, era_name):
        count = int((effect or {}).get('count', 1) or 1)
        targets = self._era_effect_target_players(effect)
        drawn = {}
        for target in targets:
            cards = self._draw_player_cards(target, count, source='era')
            drawn[target.id] = [getattr(card, 'name', str(card)) for card in cards]
            self.log(f"Era {era_name}: {target.name} drew {len(cards)} card(s)")
        return drawn

    def _era_build_towns_near_target(self, builder, effect):
        target_players = self._era_effect_target_players(effect)
        target_region = (effect or {}).get('target_region')
        max_steps = int((effect or {}).get('max_steps', 1) or 1)
        source_towns = []
        for target in target_players:
            for town, count in (getattr(target, 'organizations', {}) or {}).items():
                if count > 0 and self._town_matches_region_alias(town, target_region):
                    source_towns.append(town)
        if not source_towns:
            return []
        reachable = self._towns_within_steps(source_towns, max_steps=max_steps)
        towns = []
        for town in sorted(reachable):
            if self.can_develop_in_town(builder, town):
                towns.append({'town': town, 'near_target_towns': sorted([src for src in source_towns if town in self._towns_within_steps([src], max_steps=max_steps)])})
        return towns

    def _start_era_red_discard_build_flow(self, effect, era):
        red = self._red_player()
        if red is None:
            return {'type': (effect or {}).get('type'), 'status': 'no_red_player'}
        if not getattr(red, 'hand', None):
            return {'type': (effect or {}).get('type'), 'status': 'red_has_no_hand_cards'}
        towns = self._era_build_towns_near_target(red, effect)
        if not towns:
            return {'type': (effect or {}).get('type'), 'status': 'no_valid_build_towns'}
        era_name = (era or {}).get('name', (era or {}).get('id', '時代關卡'))
        self._set_pending_card_choice(
            red,
            'era_red_discard_to_build_near_target',
            list(red.hand),
            f"{era_name}：紅軍請棄 1 張手牌，接著在目標組織 {int((effect or {}).get('max_steps', 1) or 1)} 格內免費建立 1 個組織。",
            source_name=era_name,
            context={
                'era_id': (era or {}).get('id'),
                'era_name': era_name,
                'effect': dict(effect or {}),
            },
        )
        return {'type': (effect or {}).get('type'), 'status': 'pending_discard_choice', 'player_id': red.id, 'town_count': len(towns)}

    def _start_era_inspect_deck_top_and_reorder_flow(self, effect, era):
        targets = self._era_effect_target_players(effect)
        if not targets:
            return {'type': (effect or {}).get('type'), 'status': 'no_target_player'}
        player = targets[0]
        look_count = int((effect or {}).get('look_count', 1) or 1)
        top_count = int((effect or {}).get('top_count', 1) or 1)
        inspected = list(reversed(player.deck.draw_pile[-look_count:]))
        if len(inspected) < top_count:
            return {'type': (effect or {}).get('type'), 'status': 'not_enough_deck_cards', 'player_id': player.id, 'inspected_count': len(inspected)}
        era_name = (era or {}).get('name', (era or {}).get('id', '時代關卡'))
        self._set_pending_multi_card_choice(
            player,
            'era_inspect_deck_top_and_reorder',
            inspected,
            f"{era_name}：檢視牌庫頂 {len(inspected)} 張，請依序選擇 {top_count} 張放回牌庫頂。第一張會成為下一張抽到的牌。",
            top_count,
            top_count=top_count,
            look_count=len(inspected),
            source_name=era_name,
            context={
                'era_id': (era or {}).get('id'),
                'era_name': era_name,
                'effect': dict(effect or {}),
            },
        )
        return {
            'type': (effect or {}).get('type'),
            'status': 'pending_reorder_choice',
            'player_id': player.id,
            'inspected_count': len(inspected),
            'top_count': top_count,
        }

    def _apply_era_activation_effects(self, era):
        effects = (era or {}).get('effects') or {}
        results = {}
        era_name = (era or {}).get('name', (era or {}).get('id', 'era'))
        for side, effect in effects.items():
            effect_type = (effect or {}).get('type')
            if effect_type == 'add_static_cards_to_discard':
                results[side] = {'type': effect_type, 'added': self._apply_era_static_cards_to_discard(effect, era_name)}
            elif effect_type == 'draw' and (effect or {}).get('immediate', False):
                results[side] = {'type': effect_type, 'drawn': self._apply_era_draw(effect, era_name)}
            elif effect_type == 'red_discard_to_build_near_target':
                results[side] = self._start_era_red_discard_build_flow(effect, era)
            elif effect_type == 'inspect_deck_top_and_reorder':
                results[side] = self._start_era_inspect_deck_top_and_reorder_flow(effect, era)
            else:
                results[side] = {'type': effect_type, 'status': 'active_modifier_or_pending_runtime'}
        return results

    def _active_era_effects(self):
        if not getattr(self, 'era_engine', None):
            return []
        effects = []
        for detail in self.era_engine.get_active_era_details():
            for side, effect in ((detail.get('effects') or {}).items()):
                effects.append((detail, side, effect or {}))
        return effects

    def _era_purchase_cost_reduction(self, player, card):
        reductions = {'money': 0, 'propaganda': 0}
        for _era, _side, effect in self._active_era_effects():
            if (effect or {}).get('type') != 'reduce_purchase_cost':
                continue
            if not self._player_matches_camp(player, effect.get('target_camp')):
                continue
            if not self._card_matches_types(card, effect.get('card_types') or []):
                continue
            resource = effect.get('resource', 'money')
            if resource not in reductions:
                continue
            reductions[resource] += int(effect.get('amount', 0) or 0)
        return reductions

    def _apply_era_resource_card_bonus(self, player, card):
        applied = []
        for era, _side, effect in self._active_era_effects():
            if (effect or {}).get('type') != 'hand_card_resource_bonus':
                continue
            if not self._player_matches_camp(player, effect.get('target_camp')):
                continue
            if not self._card_matches_types(card, effect.get('card_types') or []):
                continue
            resource = effect.get('resource')
            amount = int(effect.get('amount', 0) or 0)
            if resource not in {'money', 'propaganda'} or amount <= 0:
                continue
            player.resources[resource] += amount
            applied.append({'era': era.get('id'), 'type': effect.get('type'), 'resource': resource, 'amount': amount})
            self.log(f"Era {era.get('name', era.get('id'))}: {player.name} gained {amount} {resource} from resource-card bonus")
        if applied:
            self.turn_log.setdefault('era_effects_applied', []).extend(applied)
        return applied

    def _era_bonus_dissolve_targets_for_effect(self, player, effect):
        max_steps = int((effect or {}).get('max_steps', 1) or 1)
        target_camp = (effect or {}).get('target_camp')
        source_towns = [town for town, count in (getattr(player, 'organizations', {}) or {}).items() if count > 0]
        if not source_towns:
            return []
        reachable = self._towns_within_steps(source_towns, max_steps=max_steps)
        targets = []
        for other in self.players:
            if other is player:
                continue
            if target_camp and not self._player_matches_camp(other, target_camp):
                continue
            for town, count in (getattr(other, 'organizations', {}) or {}).items():
                if count <= 0 or town not in reachable:
                    continue
                targets.append({
                    'id': f'{getattr(other, "id", other.name)}::{town}',
                    'label': f'{other.name}｜{town}',
                    'player_id': getattr(other, 'id', None),
                    'town': town,
                })
        return targets

    def _era_followup_target_choice_for_play_card(self, player, card):
        for era, _side, effect in self._active_era_effects():
            if (effect or {}).get('type') != 'bonus_dissolve_on_red_card_near_self':
                continue
            if not self._player_matches_camp(player, effect.get('player_faction')):
                continue
            if not self._card_matches_types(card, effect.get('card_types') or []):
                continue
            targets = self._era_bonus_dissolve_targets_for_effect(player, effect)
            if not targets:
                continue
            era_name = era.get('name', era.get('id', '時代關卡'))
            return {
                'era_id': era.get('id'),
                'era_name': era_name,
                'targets': targets,
                'max_steps': int((effect or {}).get('max_steps', 1) or 1),
                'target_camp': (effect or {}).get('target_camp'),
                'card_name': getattr(card, 'name', str(card)),
            }
        return None

    def _era_followup_discard_choice_for_play_card(self, player, card, target_player_id=None):
        for era, _side, effect in self._active_era_effects():
            if (effect or {}).get('type') != 'bonus_discard_on_red_card':
                continue
            if not self._player_matches_camp(player, effect.get('player_faction')):
                continue
            if not self._card_matches_types(card, effect.get('card_types') or []):
                continue
            targets = self._target_players_for_interaction(player, target_player_id)
            target_camp = effect.get('target_camp')
            target = next(
                (
                    other for other in targets
                    if other is not None
                    and self._player_matches_camp(other, target_camp)
                    and getattr(other, 'hand', None)
                ),
                None,
            )
            if target is None:
                continue
            return {
                'era_id': era.get('id'),
                'era_name': era.get('name', era.get('id', '時代關卡')),
                'target_player_id': getattr(target, 'id', None),
                'target_player_name': getattr(target, 'name', str(getattr(target, 'id', ''))),
                'initiator_player_id': getattr(player, 'id', None),
                'initiator_player_name': getattr(player, 'name', str(getattr(player, 'id', ''))),
                'card_name': getattr(card, 'name', str(card)),
                'discard_count': int(effect.get('discard_count', 1) or 1),
            }
        return None

    def _start_era_followup_discard_choice(self, payload):
        if not isinstance(payload, dict):
            return None
        target = next((p for p in self.players if getattr(p, 'id', None) == payload.get('target_player_id')), None)
        if target is None or not getattr(target, 'hand', None):
            return None
        count = min(int(payload.get('discard_count', 1) or 1), len(target.hand))
        if count <= 0:
            return None
        era_name = payload.get('era_name') or '時代關卡'
        prompt = f"{era_name}：紅軍打出 {payload.get('card_name') or '間諜類卡牌'}，請棄掉 {count} 張手牌。"
        extra = {
            'source_name': era_name,
            'initiator_player_id': payload.get('initiator_player_id'),
            'initiator_player_name': payload.get('initiator_player_name') or '紅軍',
            'target_player_name': payload.get('target_player_name') or getattr(target, 'name', '目標玩家'),
            'context': {
                'era_id': payload.get('era_id'),
                'era_name': era_name,
                'card_name': payload.get('card_name'),
            },
        }
        if count == 1:
            result = self._set_pending_card_choice(target, 'era_bonus_discard_on_red_card', list(target.hand), prompt, **extra)
        else:
            result = self._set_pending_multi_card_choice(target, 'era_bonus_discard_on_red_card', list(target.hand), prompt, count=count, **extra)
        self.turn_log.setdefault('era_effects_applied', []).append({
            'era': payload.get('era_id'),
            'type': 'bonus_discard_on_red_card',
            'status': 'pending_discard_choice',
            'target_player_id': getattr(target, 'id', None),
            'discard_count': count,
        })
        self.log(f"Era {era_name}: {target.name} must discard {count} after Red Army played {payload.get('card_name')}")
        return result

    def _start_era_followup_target_choice(self, payload):
        if not isinstance(payload, dict):
            return None
        red = self._red_player()
        if red is None:
            return None
        era_name = payload.get('era_name') or '時代關卡'
        targets = list(payload.get('targets') or [])
        if not targets:
            return None
        result = self._set_pending_target_choice(
            red,
            'era_red_bonus_dissolve_target',
            targets,
            f"{era_name}：紅軍選擇 1 個維吾爾組織瓦解。",
            source_name=era_name,
            context={
                'era_id': payload.get('era_id'),
                'era_name': era_name,
                'max_steps': payload.get('max_steps', 1),
                'target_camp': payload.get('target_camp'),
                'card_name': payload.get('card_name'),
            },
        )
        self.turn_log.setdefault('era_effects_applied', []).append({
            'era': payload.get('era_id'),
            'type': 'bonus_dissolve_on_red_card_near_self',
            'status': 'pending_target_choice',
            'target_count': len(targets),
        })
        self.log(f"Era {era_name}: {red.name} may dissolve 1 target organization after playing {payload.get('card_name')}")
        return result

    def _apply_era_play_card_effects(self, player, card):
        applied = []
        for era, _side, effect in self._active_era_effects():
            if (effect or {}).get('type') != 'gain_resource_on_play_card':
                continue
            if not self._player_matches_camp(player, effect.get('target_camp')):
                continue
            if not self._card_matches_types(card, effect.get('card_types') or []):
                continue
            resource = effect.get('resource')
            amount = int(effect.get('amount', 0) or 0)
            if resource not in {'money', 'propaganda'} or amount <= 0:
                continue
            player.resources[resource] += amount
            applied.append({'era': era.get('id'), 'type': effect.get('type'), 'resource': resource, 'amount': amount})
            self.log(f"Era {era.get('name', era.get('id'))}: {player.name} gained {amount} {resource} for playing {getattr(card, 'name', str(card))}")
        if applied:
            self.turn_log.setdefault('era_effects_applied', []).extend(applied)
        return applied

    def _apply_era_build_effects(self, player, town):
        applied = []
        built_count = len(self.turn_log.get('built_towns') or [])
        for era, _side, effect in self._active_era_effects():
            if not self._player_matches_camp(player, effect.get('target_camp')):
                continue
            effect_type = (effect or {}).get('type')
            if effect_type == 'gain_resource_on_build_in_region':
                region = effect.get('region')
                if region and not self._town_matches_region_alias(town, region):
                    continue
                resource = effect.get('resource')
                amount = int(effect.get('amount', 0) or 0)
                if resource not in {'money', 'propaganda'} or amount <= 0:
                    continue
                player.resources[resource] += amount
                applied.append({'era': era.get('id'), 'type': effect_type, 'resource': resource, 'amount': amount, 'town': town})
                self.log(f"Era {era.get('name', era.get('id'))}: {player.name} gained {amount} {resource} for building in {town}")
            elif effect_type == 'build_count_draw_bonus':
                required = int(effect.get('build_count', 0) or 0)
                draw_count = int(effect.get('draw_count', 0) or 0)
                key = f"era_build_count_draw_bonus:{era.get('id')}"
                if required <= 0 or draw_count <= 0 or built_count < required or self.turn_log.get(key):
                    continue
                drawn = self._draw_player_cards(player, draw_count, source='era')
                self.turn_log[key] = True
                applied.append({'era': era.get('id'), 'type': effect_type, 'drawn': [getattr(c, 'name', str(c)) for c in drawn], 'built_count': built_count})
                self.log(f"Era {era.get('name', era.get('id'))}: {player.name} drew {len(drawn)} card(s) after building {built_count} organizations")
        if applied:
            self.turn_log.setdefault('era_effects_applied', []).extend(applied)
        return applied

    def _era_restricts_ignore_distance_build(self, player, target_town):
        for era, _side, effect in self._active_era_effects():
            if (effect or {}).get('type') != 'restrict_ignore_distance_build':
                continue
            if not self._player_matches_camp(player, effect.get('target_camp')):
                continue
            scope = effect.get('scope')
            if scope and not self._town_matches_region_alias(target_town, scope):
                continue
            return True
        return False

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
                    activation_results = self._apply_era_activation_effects(era)
                    self.era_notification = self._era_notification_payload(era)
                    self.era_notification['runtime_effects'] = activation_results
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
        region_towns = self._towns_for_region_alias(region)
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
                notification = {**self._era_notification_payload(active_match), **notification}
                notification["remaining"] = active_match.get("remaining")
                notification["duration"] = active_match.get("duration")

        pending_choice = None
        if self.pending_choice:
            pending_choice = {
                'type': self.pending_choice.get('type'),
                'choice_key': self.pending_choice.get('choice_key'),
                'player_id': self.pending_choice.get('player_id'),
                'prompt': self.pending_choice.get('prompt'),
                'source_name': self.pending_choice.get('source_name'),
                'count': self.pending_choice.get('count'),
                'min_count': self.pending_choice.get('min_count'),
                'mode': self.pending_choice.get('mode'),
                'acting_player_id': self.pending_choice.get('acting_player_id'),
                'acting_player_name': self.pending_choice.get('acting_player_name'),
                'played_card_name': self.pending_choice.get('played_card_name'),
                'region': self.pending_choice.get('region'),
                'free': self.pending_choice.get('free'),
                'ignore_distance': self.pending_choice.get('ignore_distance'),
                'cards': [
                    dict(card) if isinstance(card, dict) and 'name' in card and 'card' not in card else {
                        'name': getattr(card.get('card'), 'name', str(card.get('card'))),
                        'zone': card.get('zone'),
                        'zone_label': card.get('zone_label'),
                    } if isinstance(card, dict) else getattr(card, 'name', str(card))
                    for card in (self.pending_choice.get('cards') or [])
                ],
                'options': [
                    dict(option) if isinstance(option, dict) else option
                    for option in (self.pending_choice.get('options') or [])
                ],
                'towns': [
                    dict(entry) if isinstance(entry, dict) else {'town': entry}
                    for entry in (self.pending_choice.get('towns') or [])
                ],
                'targets': [
                    dict(entry) if isinstance(entry, dict) else {'id': entry, 'label': str(entry)}
                    for entry in (self.pending_choice.get('targets') or [])
                ],
                'step': self.pending_choice.get('step'),
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
            "current_event": self._event_display_payload(),
            "event_deck_count": len(self.event_deck.draw_pile) if getattr(self, 'event_deck', None) else 0,
            "red_army_action_count": self.turn_log.get('red_army_action_count', 0),
            "red_army_action_limit": self._red_army_action_limit(),
            "event_discard_count": len(self.event_deck.discard_pile) if getattr(self, 'event_deck', None) else 0,
            "event_modifiers": list(getattr(self, 'event_modifiers', []) or []),
            "market_mode": self.market_mode,
            "pending_base_choices": self.pending_base_choices,
            "pending_choice": pending_choice,
            "faction_action_used": bool(self.turn_log.get('faction_action_used')),
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
                    "discard_pile": [getattr(card, 'name', str(card)) for card in p.deck.discard_pile] if p.deck else [],
                    "orgs": p.organizations
                }
                for p in self.players
            ]
        }
