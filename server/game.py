"""
Clean unified Game engine core (Engine Cleanup Phase)
- Centralized state machine
- Integrated ActionEngine, EffectEngine, EraEngine, VictoryEngine
- No duplicated logic
- Deterministic turn flow
"""

import uuid
import random

from server.deck import Deck
from server.cards import Card
from server.action_engine import ActionCardEngine
from server.effect_engine import EffectEngine
from server.era_engine import EraEngine
from server.victory import VictoryEngine
from server.events import EventDeck
from server.game_models import GamePhase, Player, TurnPhase
from server.game_catalog import (
    MAP_PATH,
    FACTIONS_PATH,
    STRUCTURED_ACTION_PATH,
    ERA_STRUCTURED_PATH,
    SUPPORT_CARDS_PATH,
    SUPPORT_TAXONOMY_PATH,
    EVENT_STRUCTURED_PATH,
    EVENT_CARD_COUNTS_PATH,
    load_json,
    build_towns_by_ruler,
)
from server.game_map_rules import (
    is_inside_wall_town,
    town_neighbors,
    towns_within_steps,
    towns_for_region_alias,
    town_matches_region_alias,
)
from server.game_market_cost_rules import (
    support_card_cost,
    card_purchase_cost,
    event_reduce_cost_amount,
    armory_purchase_cost_reduction,
    era_purchase_cost_reduction,
    purchase_area_card_cost_total,
    purchase_area_card_cost_money,
    top_card_cost_total,
)
from server.game_market_transactions import (
    purchase_payment_policy,
    allocate_purchase_payments,
)
from server.game_base_setup import (
    classify_base_options,
    resolve_starting_base,
    base_option_to_towns,
    candidate_base_names,
)
from server.game_faction_rules import (
    resolve_ability_ref,
    resolve_ability_text,
    resolve_faction_abilities,
    player_base_data,
    player_effective_abilities,
    player_has_ability,
    camp_token_for_faction_id,
    canonical_faction_name_to_id,
    factions_sharing_with,
    player_camp,
    player_matches_camp,
    players_matching_camp,
)
from server.game_event_display import event_display_payload
from server.game_event_triggers import (
    event_trigger_matches_scope,
    event_trigger_actor_allowed,
    event_purchase_trigger_matches,
    event_state_condition_met,
)
from server.game_era_rules import (
    era_notification_payload,
    player_matches_era_trigger,
    era_stage_for_player,
    evaluate_era_trigger,
)
from server.game_support_rules import (
    support_taxonomy_entry,
    is_starter_support_card,
    support_card_runtime_type,
    is_support_card,
    is_india_flag_card,
    support_card_variant_info,
    support_card_effect_text,
    resolve_support_card_effect,
    make_support_card,
    support_card_tier,
)
from server.game_log_rules import project_action_log
from server.game_organization_scope_rules import (
    shared_origin_owner,
    shared_org_count,
    town_has_shared_org_access,
    town_blocks_movement_for_player,
    organization_towns_for_player,
    player_organization_scope_counts,
    player_ruler_organization_counts,
    player_ruler_leadership,
    player_ruler_presence,
    player_region_org_count,
    player_requirement_org_count,
)
from server.game_choice_rules import choice_is_card_map_interaction
from server.game_build_eligibility_rules import (
    camp_token_for_player,
    red_army_base_build_blocked,
    can_faction_develop_in_town,
    organization_entries_at,
    town_has_physical_organization,
    organization_occupancy_violations,
    rail_reachable_within_three,
    org_supply_limit,
    player_is_nonviolent,
    player_is_distance_restricted,
    faction_restricts_ignore_distance_build,
    era_restricts_ignore_distance_build,
    ignore_distance_build_restricted,
    restricted_build_fallback_towns,
    active_era_effects,
)
from server.game_card_rules import (
    active_event_modifiers,
    event_modifier_active,
    card_matches_types,
    card_build_effects,
    card_dissolve_effects,
    card_can_queue_build,
)
from server.game_support_target_rules import (
    can_dissolve_base_target,
    target_players_for_interaction,
    player_has_org_within_steps_of_player,
    find_target_town_within_steps_of_player,
    interactive_support_dissolve_targets,
    interactive_support_dissolve_targets_near_town,
    interactive_support_discard_targets_near,
    interactive_support_sacrifice_towns,
)
from server.game_card_play import CardPlayMixin, CANCELLABLE_CHOICE_KEYS

STATIC_PURCHASE_CARD_SUPPLY = {
    # data/raw/action_cards.csv 「卡牌張數」
    '宣傳家': 15,
    '思想家': 15,
    '資助者': 15,
    '資本家': 15,
    '分神': 30,
    '內鬥': 20,
}
STATIC_PURCHASE_CARD_NAMES = tuple(STATIC_PURCHASE_CARD_SUPPLY)

# rules.md 步驟⑦：事件牌庫為混洗後抽出的 20 張
EVENT_DECK_SIZE = 20


class Game(CardPlayMixin):
    def __init__(self, players_data, market_mode="sample_53"):
        if len(players_data) < 2 or len(players_data) > 4:
            raise ValueError("Game requires 2–4 players")

        self.id = str(uuid.uuid4())
        self.turn = 1
        self.current_player_index = 0
        self.round_start_player_index = 0
        self.game_phase = GamePhase.SETUP
        self.turn_phase = TurnPhase.ACTION
        self.winner = None
        self.co_winners = []
        # 香港 special_rules（2026-07-11 裁決 S5-1）：香港抗暴之戰結算後、下一回合開始前的免費根據地遷移窗口
        self.hk_free_base_relocation = False
        # 事件在回合結束補牌後結算時，先凍結換人；香港完成「遷移／留在」後才交棒。
        self.hk_relocation_blocks_turn_handoff = False
        # 紅軍回合結束後觸發互動式時代關卡時，先讓紅軍完成該關卡，再將席位交給下一位。
        self.era_blocks_turn_handoff = False
        # 若紅軍正好是整輪最後一席，時代效果必須記在新回合；交棒時不可再次增加回合數。
        self._era_turn_preincremented = False
        self._pending_guerrilla_players = []
        self._pending_show_strength_players = []
        self.market_mode = market_mode or "sample_53"

        self.map = load_json(MAP_PATH)
        self.factions_data = load_json(FACTIONS_PATH)
        self.factions = self.factions_data["factions"]
        self.ability_templates = self.factions_data.get("ability_templates", {})
        self.towns_by_ruler = build_towns_by_ruler(self.map)
        self.structured_cards = load_json(STRUCTURED_ACTION_PATH)["cards"]
        self.support_cards = load_json(SUPPORT_CARDS_PATH)
        self.support_taxonomy = load_json(SUPPORT_TAXONOMY_PATH).get("cards", []) if SUPPORT_TAXONOMY_PATH.exists() else []
        # ✅ Load structured eras
        self.structured_eras = load_json(ERA_STRUCTURED_PATH)["eras"]
        self.structured_events = load_json(EVENT_STRUCTURED_PATH).get("events", [])

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

        self.static_purchase_supply = dict(STATIC_PURCHASE_CARD_SUPPLY)
        for p in self.players:
            self._apply_setup_abilities(p)

        self.action_engine = ActionCardEngine(self.structured_cards)
        self.effect_engine = EffectEngine()
        self.era_engine = EraEngine(self.structured_eras)
        self.victory_engine = VictoryEngine(self.factions)

        self.turn_log = self._new_turn_log()
        self.action_log = []
        self._action_log_visibility = []
        self.purchase_deck = self._initial_purchase_deck()
        self.purchase_area = self._initial_purchase_area()
        self.event_deck = EventDeck(self._draw_event_deck_cards())
        self.current_event = None
        self.event_progress = None
        self.event_modifiers = []
        self.event_notification = None
        self.pending_choice = None
        # While a card-build choice is active, another build-capable action card may be
        # committed. Preserve the active choice while that card resolves any prerequisite
        # choice, and queue each resulting build with its own range/effect continuation.
        self._deferred_build_choice = None
        self._queued_card_build_choices = []
        self._pending_era_activations = []
        self._deferred_auto_event = False
        self.era_notification = None
        if self.game_phase == GamePhase.MAIN:
            self._start_event_phase()

    # ---------- Init ----------

    def _event_card_counts(self):
        counts = {}
        if not EVENT_CARD_COUNTS_PATH.exists():
            return counts
        rows = load_json(EVENT_CARD_COUNTS_PATH)
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

    def _draw_event_deck_cards(self, deck_size=EVENT_DECK_SIZE):
        # rules.md 步驟⑦：「取出事件卡，混洗後抽出20張，牌面朝下，作為事件牌庫。」
        # 全池（依卡牌張數展開共 25 張）只抽 20 張入庫，其餘本場不使用。
        pool = self._initial_event_cards()
        if len(pool) <= deck_size:
            return pool
        return random.sample(pool, deck_size)

    def _event_by_name(self, name):
        for event in self.structured_events:
            if event.get('name') == name or event.get('id') == name:
                return dict(event)
        return None

    def _event_display_payload(self, event=None):
        event = event or self.current_event
        return event_display_payload(event, self.event_progress)

    def _start_event_phase(self):
        if getattr(self, 'hk_free_base_relocation', False):
            self.hk_free_base_relocation = False
            self.log('香港免費根據地遷移窗口已隨新回合開始關閉')
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
            result = self._apply_auto_event_if_ready()
            if result and result.get('pending_choice'):
                self.log(f"Event drawn: {self.current_event.get('name')} (auto pending choice)")
            elif result and result.get('deferred'):
                self.log(f"Event drawn: {self.current_event.get('name')} (auto deferred)")
            else:
                self.log(f"Event drawn: {self.current_event.get('name')} (auto)")
        else:
            self.log(f"Event drawn: {self.current_event.get('name')}")
        self.event_notification = self._event_display_payload()

    def _track_event_progress(self, trigger_type, amount=1, town=None, player=None):
        event = self.current_event or {}
        if event.get('type') != 'mission' or not self.event_progress or self.event_progress.get('settled'):
            return
        trigger = event.get('trigger') or {}
        if trigger.get('type') != trigger_type:
            return
        if not event_trigger_actor_allowed(player):
            return
        if not event_trigger_matches_scope(self.map, self.towns_by_ruler, trigger, town=town):
            return
        self.event_progress['count'] = int(self.event_progress.get('count', 0) or 0) + int(amount or 1)
        if player is not None:
            self.event_progress['last_actor_id'] = getattr(player, 'id', None)
            self.event_progress['last_actor_name'] = getattr(player, 'name', None)
        required = int(trigger.get('count', 1) or 1)
        if self.event_progress['count'] >= required:
            self.event_progress['succeeded'] = True
            self.event_progress['status'] = 'success_pending'
            self.event_notification = self._event_display_payload()
            return {'success': True}
        self.event_notification = self._event_display_payload()
        return {'success': True}

    def _track_event_purchase(self, card, original_cost=None, player=None):
        event = self.current_event or {}
        if event.get('type') != 'mission' or not self.event_progress or self.event_progress.get('settled'):
            return {'success': True}
        trigger = event.get('trigger') or {}
        if not event_purchase_trigger_matches(self.structured_cards, self.support_taxonomy, trigger, card, original_cost=original_cost):
            return {'success': True}
        return self._track_event_progress('buy_card', player=player) or {'success': True}

    def _event_build_towns_near_own(self, player, max_steps=1):
        origins = self._organization_towns_for_player(player)
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
            if self._can_player_build_in_town(player, town)
        ]

    def _draw_player_cards(self, player, count=1, source='effect', trigger_name=None):
        drawn = player.deck.draw(int(count or 1))
        player.hand.extend(drawn)
        if source not in {'refill', 'era'} and drawn:
            self._track_event_progress('draw', amount=len(drawn), player=player)
        # 2026-08-04 使用者需求：抽牌類效果（含紅軍奧援）的紀錄要寫出實際抽到哪些牌，
        # 不能只有「抽了 N 張」這種不具名的訊息，方便之後能直接從 log 診斷牌庫相關回報。
        # `trigger_name` 由呼叫端傳入觸發的卡名/效果名稱；沒傳時對 era 效果給通用說法，
        # 其餘沿用最簡潔的「抽到：...」。
        if drawn:
            self.log_private_draw(player, drawn, source=source, trigger_name=trigger_name)
        return drawn

    def _active_event_modifiers(self):
        return active_event_modifiers(getattr(self, 'event_modifiers', []))

    def _event_modifier_active(self, modifier_type):
        return event_modifier_active(getattr(self, 'event_modifiers', []), modifier_type)

    def _event_reduce_cost_amount(self):
        return event_reduce_cost_amount(self._active_event_modifiers())

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
        return town_matches_region_alias(self.map, self.towns_by_ruler, town, region)

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

    def _take_internal_conflict_cards(self, count, reason=''):
        """依 rules.md「放入分神或內鬥」與 2026-07-11 裁決（C1=B）：
        每需放入 1 張內鬥時，若內鬥供應耗盡，改以 2 張分神替代；
        分神供應也不足時，有多少放多少。回傳實際要放置的卡牌清單並扣除供應。"""
        cards = []
        for _ in range(int(count or 1)):
            ic = int(self.static_purchase_supply.get('內鬥', 0) or 0)
            if ic > 0:
                self.static_purchase_supply['內鬥'] = ic - 1
                cards.append(self._starter_card('內鬥'))
                continue
            placed = 0
            for _ in range(2):
                ds = int(self.static_purchase_supply.get('分神', 0) or 0)
                if ds <= 0:
                    break
                self.static_purchase_supply['分神'] = ds - 1
                cards.append(self._starter_card('分神'))
                placed += 1
            suffix = f'（{reason}）' if reason else ''
            if placed:
                self.log(f"內鬥供應已空：以 {placed} 張分神替代{suffix}")
            else:
                self.log(f"內鬥與分神供應皆空，無法放置{suffix}")
        return cards

    def _take_static_purchase_cards(self, card_name, count=1, reason=''):
        """Take up to count physical cards from the shared static purchase supply."""
        cards = []
        for _ in range(int(count or 1)):
            if card_name in STATIC_PURCHASE_CARD_NAMES:
                supply = int(self.static_purchase_supply.get(card_name, 0) or 0)
                if supply <= 0:
                    prefix = f'{reason}：' if reason else ''
                    self.log(f"{prefix}{card_name}供應已空，無法再放置")
                    break
                self.static_purchase_supply[card_name] = supply - 1
            cards.append(self._starter_card(card_name))
        return cards

    def _gain_event_card(self, player, card_name, count=1):
        if card_name == '內鬥':
            cards = self._take_internal_conflict_cards(count, reason='event')
            if cards:
                player.deck.discard(cards)
                self.log(f"{player.name} gained {len(cards)} card(s) ({'、'.join(getattr(c, 'name', str(c)) for c in cards)}) from event")
            return len(cards)
        cards = self._take_static_purchase_cards(card_name, count, reason='Event')
        if cards:
            player.deck.discard(cards)
            self.log(f"{player.name} gained {len(cards)} {card_name} from event")
        return len(cards)

    def _topdeck_static_purchase_card(self, target_player, card_name, source_name):
        if card_name == '內鬥':
            cards = self._take_internal_conflict_cards(1, reason=source_name)
            if not cards:
                self.log(f"{source_name}: could not place {card_name} on {target_player.name}'s deck because static supply was empty")
                return []
            for card in cards:
                target_player.deck.draw_pile.append(card)
            return [getattr(c, 'name', str(c)) for c in cards]
        if card_name in STATIC_PURCHASE_CARD_NAMES:
            supply = int(self.static_purchase_supply.get(card_name, 0) or 0)
            if supply <= 0:
                self.log(f"{source_name}: could not place {card_name} on {target_player.name}'s deck because static supply was empty")
                return []
            self.static_purchase_supply[card_name] = supply - 1
        target_player.deck.draw_pile.append(self._starter_card(card_name))
        return [card_name]

    def _red_player(self):
        return next((p for p in self.players if p.faction_id == 'red_army'), None)

    def _event_effect_player(self, default_player, effect):
        faction = (effect or {}).get('player_faction')
        if not faction:
            return default_player
        return next((p for p in self.players if getattr(p, 'faction_id', None) == faction), default_player)

    def _auto_event_target_player(self, event=None):
        event = event or self.current_event or {}
        return self._event_effect_player(self.current_player(), event.get('effect') or {})

    def _apply_auto_event_if_ready(self):
        event = self.current_event or {}
        if event.get('type') != 'auto':
            return {'success': True, 'skipped': True}
        if self.event_progress and self.event_progress.get('settled'):
            return {'success': True, 'skipped': True}
        # Era activation runs first at the action-first turn boundary. Interactive era
        # effects (Tibet/Manchuria) own pending_choice until resolved; an interactive
        # auto event must never overwrite that choice. Remember the continuation and
        # apply the already-drawn event as soon as the era flow is complete.
        if self.pending_choice or getattr(self, '_pending_era_activations', []):
            self._deferred_auto_event = True
            self.event_progress = self.event_progress or {
                'count': 0,
                'required': 0,
                'succeeded': False,
                'settled': False,
            }
            self.event_progress['status'] = 'auto_deferred'
            self.event_notification = self._event_display_payload()
            return {'success': True, 'deferred': True}

        self._deferred_auto_event = False
        effect = event.get('effect') or {}
        target_player = self._auto_event_target_player(event)
        current = self.current_player()
        target_faction = effect.get('player_faction')
        if target_faction and target_player and current and target_player.id != current.id:
            self.event_progress = self.event_progress or {'count': 0, 'required': 0, 'succeeded': False, 'settled': False}
            self.event_progress.update({
                'succeeded': False,
                'settled': False,
                'status': 'auto_pending',
                'auto_target_player_id': target_player.id,
                'auto_target_player_name': target_player.name,
                'auto_target_faction': target_faction,
            })
            self.event_notification = self._event_display_payload()
            return {'success': True, 'deferred': True, 'target_player_id': target_player.id}

        result = self._apply_event_effect(effect, current, outcome='auto') or {'success': True}
        self.event_progress = self.event_progress or {'count': 0, 'required': 0}
        self.event_progress.update({
            'succeeded': True,
            'settled': True,
            'status': 'auto',
            'auto_target_player_id': getattr(target_player, 'id', None),
            'auto_target_player_name': getattr(target_player, 'name', None),
            'auto_target_faction': target_faction,
        })
        self.event_notification = self._event_display_payload()
        if result.get('pending_choice'):
            return {'success': True, 'pending_choice': True, 'target_player_id': getattr(target_player, 'id', None)}
        return {'success': True, 'applied': True, 'target_player_id': getattr(target_player, 'id', None)}

    def _player_camp(self, player):
        return player_camp(self.faction_by_id, player)

    def _player_matches_camp(self, player, camp):
        return player_matches_camp(self.faction_by_id, player, camp)

    def _players_matching_camp(self, camp):
        return players_matching_camp(self.faction_by_id, self.players, camp)

    def _card_matches_types(self, card, card_types):
        return card_matches_types(card, card_types)

    def _event_build_towns_in_region(self, player, region):
        region_towns = set(self._towns_for_region_alias(region))
        return [
            {'town': town, 'region': region}
            for town in sorted(region_towns)
            if self._can_player_build_in_town(player, town)
        ]

    def _apply_event_effect(self, effect, player, outcome='success'):
        effect = effect or {'type': 'none'}
        t = effect.get('type')
        count = int(effect.get('count', 1) or 1)
        player = self._event_effect_player(player, effect)
        if t in (None, 'none'):
            self.log(f"Event {outcome}: no effect")
            return {'success': True, 'effect': t or 'none'}

        pending_result = None
        if t == 'draw':
            self._apply_event_effect_draw(player, count)
        elif t == 'gain_card':
            self._apply_event_effect_gain_card(player, effect, count)
        elif t == 'discard_self':
            pending_result = self._apply_event_effect_discard_self(player, count, outcome)
        elif t == 'discard_random':
            self._apply_event_effect_discard_random(player, effect, count, outcome)
        elif t == 'red_dissolve':
            pending_result = self._apply_event_effect_red_dissolve(effect)
        elif t == 'add_internal_conflict':
            self._apply_event_effect_add_internal_conflict(player, count)
        elif t == 'move':
            self._apply_event_effect_move(player, count)
        elif t in {'reduce_cost', 'restrict_build', 'ignore_distance', 'scoped_card_range'}:
            self._apply_event_effect_modifier(effect)
        elif t == 'build_organization':
            pending_result = self._apply_event_effect_build_organization(player)
        elif t == 'build_organization_in_region':
            pending_result = self._apply_event_effect_build_organization_in_region(player, effect, count)
        elif t == 'build_organization_near_own':
            pending_result = self._apply_event_effect_build_organization_near_own(player, effect, count)
        elif t == 'topdeck_from_discard':
            pending_result = self._apply_event_effect_topdeck_from_discard(player, count, outcome)
        elif t == 'trash_from_hand_or_discard':
            pending_result = self._apply_event_effect_trash_from_hand_or_discard(player, count, outcome)

        if pending_result is not None:
            return pending_result
        self.log(f"Event {outcome} resolved: {self.current_event.get('name')} / {t}")
        return {'success': True, 'effect': t}

    def _apply_event_effect_draw(self, player, count):
        """draw: draw `count` cards."""
        self._draw_player_cards(player, count)

    def _apply_event_effect_gain_card(self, player, effect, count):
        """gain_card: gain `count` copies of the named card."""
        self._gain_event_card(player, effect.get('card'), count)

    def _apply_event_effect_discard_self(self, player, count, outcome):
        """discard_self: player chooses which hand cards to discard."""
        cards = list(player.hand)
        if not cards:
            self.log(f"Event {outcome}: {player.name} has no hand card to discard")
            return None
        self.log(f"Event {outcome}: {player.name} must discard {min(count, len(cards))} hand card(s)")
        self._set_pending_multi_card_choice(player, 'event_discard_self', cards, f"{self.current_event.get('name')}：請選擇 {min(count, len(cards))} 張手牌棄掉。", min(count, len(cards)), source_name=self.current_event.get('name'))
        return {'success': True, 'pending_choice': True}

    def _apply_event_effect_discard_random(self, player, effect, count, outcome):
        """discard_random: randomly discard from the player, or (on a failure outcome
        with no explicit player_faction) every non-red player."""
        targets = [player]
        default_failure_targets_non_red = outcome == 'failure' and not (effect or {}).get('player_faction')
        if default_failure_targets_non_red:
            targets = [p for p in self.players if getattr(p, 'faction_id', None) != 'red_army']
        discarded_total = 0
        discarded_by_player = []
        for target in targets:
            discarded_for_target = 0
            for _ in range(min(count, len(target.hand))):
                card = random.choice(target.hand)
                target.hand.remove(card)
                target.deck.discard([card])
                discarded_total += 1
                discarded_for_target += 1
            if discarded_for_target:
                discarded_by_player.append(f"{target.name} discarded {discarded_for_target} random hand card(s)")
        if discarded_by_player:
            self.log(f"Event {outcome}: " + '; '.join(discarded_by_player))
        else:
            target_label = 'non-red player' if default_failure_targets_non_red else getattr(player, 'name', 'target player')
            self.log(f"Event {outcome}: no eligible {target_label} hand cards to discard")

    def _apply_event_effect_red_dissolve(self, effect):
        """red_dissolve: red army chooses a non-red organization to dissolve, scoped by effect."""
        red = self._red_player()
        if not red:
            return None
        targets = []
        for other in self.players:
            if other is red:
                continue
            for town, n in (other.organizations or {}).items():
                if (
                    n > 0
                    and event_trigger_matches_scope(self.map, self.towns_by_ruler, {'scope': effect.get('scope')}, town=town)
                    and self._can_dissolve_base_target(other, town)[0]
                ):
                    targets.append({'id': f'{other.id}:{town}', 'player_id': other.id, 'town': town, 'label': f'{other.name}｜{town}'})
        if not targets:
            return None
        self._set_pending_target_choice(red, 'event_red_dissolve', targets, f"{self.current_event.get('name')}：紅軍選擇要瓦解的組織。", source_name=self.current_event.get('name'))
        return {'success': True, 'pending_choice': True}

    def _apply_event_effect_add_internal_conflict(self, player, count):
        """add_internal_conflict: gain `count` 內鬥 cards."""
        self._gain_event_card(player, '內鬥', count)

    def _apply_event_effect_move(self, player, count):
        """move: grant `count` extra organization moves this turn."""
        player.moves_left += count

    def _apply_event_effect_modifier(self, effect):
        """reduce_cost/restrict_build/ignore_distance/scoped_card_range: register a turn-scoped event modifier."""
        self.event_modifiers.append(self._event_modifier_from_effect(effect))

    def _apply_event_effect_build_organization(self, player):
        """build_organization: player chooses any legal town to build in."""
        towns = [{'town': town} for town in sorted(self.map.get('towns', {})) if self._can_player_build_in_town(player, town)]
        if not towns:
            return None
        self._set_pending_town_choice(player, 'event_build_organization', towns, f"{self.current_event.get('name')}：選擇要建立組織的城鎮。", source_name=self.current_event.get('name'))
        return {'success': True, 'pending_choice': True}

    def _apply_event_effect_build_organization_in_region(self, player, effect, count):
        """build_organization_in_region: player builds free within a specific region."""
        region = effect.get('region')
        towns = self._event_build_towns_in_region(player, region)
        if not towns:
            self.log(f"{self.current_event.get('name')}：{player.name} 在指定區域內沒有合法的城鎮可以建立組織")
            return None
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

    def _apply_event_effect_build_organization_near_own(self, player, effect, count):
        """build_organization_near_own: player builds free near their own organizations."""
        max_steps = int(effect.get('max_steps', 1) or 1)
        towns = self._event_build_towns_near_own(player, max_steps=max_steps)
        if not towns:
            self.log(f"{self.current_event.get('name')}：{player.name} 在己方組織附近沒有合法的城鎮可以建立組織")
            return None
        self._set_pending_town_choice(
            player,
            'event_build_organization',
            towns,
            f"{self.current_event.get('name')}：在己方組織 {max_steps} 格內免費建立 {min(count, len(towns))} 個組織。",
            source_name=self.current_event.get('name'),
            count=min(count, len(towns)),
        )
        return {'success': True, 'pending_choice': True}

    def _apply_event_effect_topdeck_from_discard(self, player, count, outcome):
        """topdeck_from_discard: player chooses discard-pile cards to place on top of their deck."""
        cards = list(player.deck.discard_pile)
        if not cards:
            self.log(f"Event {outcome}: {player.name} has no discard card to topdeck")
            return None
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

    def _apply_event_effect_trash_from_hand_or_discard(self, player, count, outcome):
        """trash_from_hand_or_discard: player removes cards from hand/discard entirely."""
        cards = [
            {'card': card, 'zone': 'hand', 'zone_label': '手牌'}
            for card in list(player.hand)
        ] + [
            {'card': card, 'zone': 'discard', 'zone_label': '棄牌堆'}
            for card in list(player.deck.discard_pile)
        ]
        if not cards:
            self.log(f"Event {outcome}: {player.name} has no hand/discard card to remove")
            return None
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

    def _settle_current_event(self):
        event = self.current_event or {}
        if event.get('type') != 'mission' or not self.event_progress or self.event_progress.get('settled'):
            return {'success': True}
        player = self.current_player()
        if self.event_progress and self.event_progress.get('settlement_target_player_id'):
            player = next((p for p in self.players if p.id == self.event_progress.get('settlement_target_player_id')), player)
        elif self.event_progress and self.event_progress.get('failure_target_player_id'):
            player = next((p for p in self.players if p.id == self.event_progress.get('failure_target_player_id')), player)
        elif self.event_progress and self.event_progress.get('last_actor_id'):
            player = next((p for p in self.players if p.id == self.event_progress.get('last_actor_id')), player)
        trigger = event.get('trigger') or {}
        if trigger.get('type') == 'end_turn_state' and not self.event_progress.get('succeeded'):
            met, count = event_state_condition_met(self.map, self.towns_by_ruler, trigger, player)
            self.event_progress['count'] = count
            if met:
                self.event_progress['succeeded'] = True
                self.event_progress['status'] = 'success_pending'
        succeeded = bool(self.event_progress.get('succeeded'))
        effect = event.get('success') if succeeded else event.get('failure')
        self.event_progress['settled'] = True
        self.event_progress['status'] = 'success' if succeeded else 'failure'
        result = self._apply_event_effect(effect or {'type': 'none'}, player, outcome='success' if succeeded else 'failure')
        # 香港 special_rules：事件卡「香港抗暴之戰」發生並完成結算後，
        # 不論任務成功或失敗，香港可在下一回合開始前免費遷移一次根據地。
        if event.get('name') == '香港抗暴之戰' and any(getattr(pl, 'faction_id', None) == 'hong_kong' for pl in self.players):
            if result and result.get('pending_choice') and self.pending_choice:
                context = dict(self.pending_choice.get('context') or {})
                context['open_hk_free_base_relocation_after_resolution'] = True
                self.pending_choice['context'] = context
            else:
                self._open_hong_kong_base_relocation_window()
        self.event_notification = self._event_display_payload()
        return result

    def _is_inside_wall_town(self, town):
        """Classify a town by canonical map ruler, not runtime controller."""
        return is_inside_wall_town(self.map, town)

    def _player_organization_scope_counts(self, player, *, include_shared=False):
        return player_organization_scope_counts(
            self.map, self.faction_by_id, self.players, player, include_shared=include_shared
        )

    def _towns_for_region_alias(self, region):
        return towns_for_region_alias(self.map, self.towns_by_ruler, region)

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
        return is_starter_support_card(self.support_taxonomy, support_name)

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
        return support_card_runtime_type(name)

    def _support_card_cost(self, support_name):
        return support_card_cost(self.support_taxonomy, support_name)

    def _make_support_card(self, support_name, variant_index=0):
        return make_support_card(self.support_taxonomy, support_name, variant_index=variant_index)

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
            if not name or self._is_starter_support_card(name):
                continue
            for variant_index, region in enumerate(entry.get('regions', []) or []):
                copies = int(region.get('copies') or 0)
                if copies <= 0:
                    continue
                support_pool.extend([self._make_support_card(name, variant_index=variant_index) for _ in range(copies)])

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
        return town_neighbors(self.map, town)

    def _towns_within_steps(self, origins, max_steps=1):
        return towns_within_steps(self.map, origins, max_steps)

    def _card_build_town_choices(self, player, effect):
        if self._event_modifier_active('restrict_build'):
            return []
        if not player:
            return []
        build_range = (effect or {}).get('range', 1)
        all_towns = set(self.map.get('towns', {}) or {})
        if build_range == 'ignore_distance':
            candidates = all_towns
        else:
            source_towns = self._organization_towns_for_player(player)
            if not source_towns:
                return []
            max_steps = int(build_range or 1) + int(getattr(player, 'build_range_bonus', 0) or 0)
            candidates = self._towns_within_steps(source_towns, max_steps=max_steps)
            if self._player_has_ability(player, "安全屋"):
                inner_towns = set(self._towns_for_region_alias("china"))
                candidates |= self._towns_within_steps(source_towns, max_steps=max_steps + 1) & inner_towns
        # 組織經驗甲卡面：「無法無視距離建立牆內組織者，本牌於牆內建立組織距離為1格」。
        # 思想家亦比照同一條退回規則（卡面資料的 inner_fallback_range）。限制來源包含
        # 陣營能力（新疆社會管控）與時代關卡（restrict_ignore_distance_build），兩者共用。
        fallback_towns = None
        if build_range == 'ignore_distance':
            fallback_towns = self._restricted_build_fallback_towns(
                player, (effect or {}).get('inner_fallback_range', 0)
            )
        choices = []
        for town in sorted(candidates):
            if self._red_army_base_build_blocked(getattr(player, 'faction_id', None), town):
                continue
            if not self._can_player_build_in_town(player, town):
                continue
            if build_range == 'ignore_distance' and self._ignore_distance_build_restricted(player, town):
                if town not in fallback_towns:
                    continue
            choices.append({'town': town})
        return choices

    def _player_has_org_within_steps_of_player(self, source_player, target_player, max_steps=1, target_region=None):
        return player_has_org_within_steps_of_player(
            self.map, self.towns_by_ruler, self.faction_by_id, self.players,
            source_player, target_player, max_steps, target_region,
        )

    def _find_target_town_within_steps_of_player(self, source_player, target_player, max_steps=1, target_region=None):
        return find_target_town_within_steps_of_player(
            self.map, self.towns_by_ruler, self.faction_by_id, self.players,
            source_player, target_player, max_steps, target_region,
        )

    def _action_engine_cards(self):
        engine = getattr(self, 'action_engine', None)
        return getattr(engine, 'cards', {}) if engine is not None else {}

    def _card_build_effects(self, card):
        return card_build_effects(self._action_engine_cards(), card)

    def _card_dissolve_effects(self, card):
        return card_dissolve_effects(self._action_engine_cards(), card)

    def _card_can_queue_map_action(self, player, card):
        if self._card_build_effects(card) or self._card_dissolve_effects(card):
            return True
        if getattr(card, 'card_type', None) != 'support':
            return False
        tier, region_index, _ = self._support_card_tier(player, card)
        effect_type, _ = self._resolve_support_card_effect(
            getattr(card, 'name', str(card)),
            tier,
            region_index,
        )
        return (
            effect_type in {
                'interactive_build_anywhere_inner',
                'interactive_build_near_inner',
                'interactive_dissolve_many_near',
                'interactive_dissolve_and_build',
                'interactive_dissolve_self_and_enemy',
            }
            and self._support_card_has_legal_target(player, card)
        )

    def _choice_is_card_map_interaction(self, choice):
        return choice_is_card_map_interaction(choice)

    def _card_action_legality(self, player, card):
        build_effects = self._card_build_effects(card)
        if build_effects and not self._card_build_town_choices(player, build_effects[0]):
            return {
                'playable': False,
                'reason': '目前沒有城鎮可以建立組織。',
                'no_legal_build_town': True,
            }
        return {'playable': True}

    def _card_can_queue_build(self, card):
        return card_can_queue_build(self._action_engine_cards(), card)

    def _remaining_card_build_entitlements(self):
        total = self._build_choice_entitlement_count(self.pending_choice)
        total += sum(self._build_choice_entitlement_count(choice) for choice in self._queued_card_build_choices)
        return total

    def _activate_next_queued_card_build(self, player):
        unresolved = 0
        while self._queued_card_build_choices:
            choice = self._queued_card_build_choices.pop(0)
            unresolved += self._build_choice_entitlement_count(choice)
            if not self._refresh_queued_card_map_choice(player, choice):
                self.log(f"{player.name} 有排隊中的地圖卡牌效果（來自{choice.get('source_name') or '卡牌'}），但目前沒有合法目標")
                continue
            self.pending_choice = choice
            unresolved -= self._build_choice_entitlement_count(choice)
            remaining = self._refresh_card_build_choice_projection()
            response = {'success': True, 'pending_choice': True}
            if remaining:
                response['remaining_builds'] = remaining
            return response
        if unresolved:
            return {
                'success': True,
                'no_more_valid_towns': True,
                'remaining_builds_unresolved': unresolved,
                'remaining_builds': 0,
            }
        return {'success': True, 'remaining_builds': 0}

    def _resume_card_build_queue_if_idle(self, player):
        if self.pending_choice:
            return None
        if isinstance(self._deferred_build_choice, dict):
            self.pending_choice = self._deferred_build_choice
            self._deferred_build_choice = None
            remaining = self._refresh_card_build_choice_projection()
            response = {'success': True, 'pending_choice': True}
            if remaining:
                response['remaining_builds'] = remaining
            return response
        if self._queued_card_build_choices:
            return self._activate_next_queued_card_build(player)
        return None

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

    def _org_exp_repeat_qualifying_cards(self, player, min_cost):
        cards = []
        for card in list(player.hand):
            cost = self._card_purchase_cost(card) or {}
            total = int(cost.get('money', 0) or 0) + int(cost.get('propaganda', 0) or 0)
            if total >= min_cost:
                cards.append(card)
        return cards

    def _maybe_prompt_org_exp_repeat_build(self, player, context):
        # 組織經驗甲：「每從手上棄掉1張購買費用4點以上的牌，可重複上述動作1次」
        effect = (context or {}).get('effect') if isinstance(context, dict) else None
        min_cost = int(((effect or {}).get('repeat_on_discard_min_cost')) or 0)
        if not min_cost:
            return None
        qualifying = self._org_exp_repeat_qualifying_cards(player, min_cost)
        if not qualifying:
            return None
        if not self._card_build_town_choices(player, effect):
            return None  # 沒有合法城鎮可再建（含組織棋供應上限、距離限制）
        card_name = context.get('card_name') or context.get('source_name') or '組織經驗甲'
        self._set_pending_option_choice(
            player,
            'org_exp_repeat_prompt',
            [{'label': '不再建立'}, {'label': f'棄1張購買費用{min_cost}點以上的牌，再建立1次'}],
            f'{card_name}：是否要從手上棄掉1張購買費用{min_cost}點以上的牌，再建立1個組織？',
            source_name=card_name,
            context=dict(context),
        )
        return {'pending_choice': True}

    def _continue_era_and_event_flows(self):
        """Finish queued faction, era, and event choices in their required order."""
        if self.pending_choice:
            return None
        show_strength_result = self._continue_show_strength_choice_queue()
        if self.pending_choice:
            return show_strength_result
        guerrilla_result = self._continue_guerrilla_choice_queue()
        if self.pending_choice:
            return guerrilla_result
        era_result = self._continue_era_activation_queue()
        if self.pending_choice:
            return {'success': True, 'pending_choice': True, 'source': 'era'}
        if era_result and era_result.get('error'):
            return era_result
        event_result = self._continue_deferred_auto_event()
        if self.pending_choice:
            return {'success': True, 'pending_choice': True, 'source': 'event'}
        if getattr(self, 'era_blocks_turn_handoff', False):
            self.era_blocks_turn_handoff = False
            self._finish_end_turn_handoff()
            if self.pending_choice:
                return {'success': True, 'pending_choice': True, 'source': 'turn_handoff'}
            return event_result or {'success': True, 'turn_handoff': True}
        return event_result

    def _continue_deferred_auto_event(self):
        if not getattr(self, '_deferred_auto_event', False) or self.pending_choice:
            return None
        return self._apply_auto_event_if_ready()

    def _support_card_effect_text(self, card_name, tier, region_index):
        return support_card_effect_text(self.support_taxonomy, card_name, tier, region_index)

    def _resolve_support_card_effect(self, card_name, tier, region_index):
        return resolve_support_card_effect(self.support_taxonomy, card_name, tier, region_index)

    def _interactive_support_build_towns(self, player, near_only=False):
        inner_towns = set(self._towns_for_region_alias('china'))
        # 無法無視距離建立牆內組織者（陣營能力「新疆社會管控」，或時代關卡的
        # restrict_ignore_distance_build 紅色壓制，如[反賊]公知世代的終結、[哈薩克]伊塔事件）：
        # 比照組織經驗甲卡面的降級慣例，「牆內任意城鎮」清單降級為「己方組織1格內」
        # （若另有增加建立距離的能力則為2格；實作裁定，見 TODO 記錄）。
        near_towns = self._restricted_build_fallback_towns(player, 1)
        if near_only:
            reachable = near_towns & inner_towns
        else:
            # 逐城鎮判定，才能同時支援 scope 不是整個牆內的時代關卡效果；
            # 未受限制的城鎮仍維持「無視距離」。
            reachable = {
                town
                for town in inner_towns
                if town in near_towns or not self._ignore_distance_build_restricted(player, town)
            }
        return [
            {'town': town}
            for town in sorted(reachable)
            if self._can_player_build_in_town(player, town)
        ]

    def _target_players_for_interaction(self, player, target_player_id=None):
        return target_players_for_interaction(self.players, player, target_player_id)

    def _interactive_support_dissolve_targets(self, player, require_self_sacrifice=False, max_steps=1, target_players=None, target_region=None):
        return interactive_support_dissolve_targets(
            self.map, self.towns_by_ruler, self.faction_by_id, self.players, player,
            require_self_sacrifice, max_steps, target_players, target_region,
        )

    def _interactive_support_dissolve_targets_near_town(self, player, origin_town, max_steps=1, target_players=None, target_region=None):
        return interactive_support_dissolve_targets_near_town(
            self.map, self.towns_by_ruler, self.faction_by_id, self.players, player, origin_town,
            max_steps, target_players, target_region,
        )

    def _interactive_support_discard_targets_near(self, player):
        return interactive_support_discard_targets_near(self.map, self.towns_by_ruler, self.faction_by_id, self.players, player)

    def _can_replace_dissolved_org_with_own(self, player, target_player, town):
        """Non-mutating preflight for 臺灣奧援 III's dissolve-then-build target."""
        if not player or not target_player or not town or not self._has_org_supply(player):
            return False
        target_owner = self._shared_origin_owner(target_player, town)
        if target_owner is None:
            return False
        target_player = target_owner
        if not self._can_dissolve_base_target(target_player, town)[0]:
            return False
        # 2026-08-04 使用者裁決：紅軍根據地不再永久排除瓦解＋補位組合——只要根據地真的被
        # 瓦解移除（沿用既有 2 次命中才移除的耐久規則，見 `dissolve_organization()`／
        # `_can_dissolve_base_target()`），其他陣營的瓦解＋補位效果應該跟瓦解紅軍任何其他
        # 組織城鎮一樣可以補上自己的組織。這裡只是預先模擬「移除 1 個組織後能不能建立」的
        # 篩選，不知道耐久計數；真正的把關在 `_resolve_support_interaction_result()` 呼叫
        # `dissolve_organization()` 之後，對 `_can_player_build_in_town()` 的即時複查
        # （約 game.py:3013-3015）——如果這次只是根據地的第 1 次命中、組織其實還在，那個
        # 即時複查會正確擋下建立，不受這裡放寬的影響。
        original_count = target_player.organizations[town]
        try:
            if original_count <= 1:
                del target_player.organizations[town]
            else:
                target_player.organizations[town] = original_count - 1
            return self._can_player_build_in_town(player, town)
        finally:
            target_player.organizations[town] = original_count

    def _interactive_support_sacrifice_towns(self, player, max_steps=1, target_players=None, target_region=None):
        return interactive_support_sacrifice_towns(
            self.map, self.towns_by_ruler, self.faction_by_id, self.players, player,
            max_steps, target_players, target_region,
        )

    def _gain_red_support_printed_resources(self, player, card):
        """Apply 紅軍奧援's printed 1資金＋1宣傳 without treating it as purchase cost."""
        # Use the canonical fixed output rather than trusting an old/debug Card object that
        # may have been constructed before `_make_support_card()` learned this exception.
        card.resources = {'money': 1, 'propaganda': 1}
        player.resources['money'] += 1
        player.resources['propaganda'] += 1
        self._apply_era_resource_card_bonus(player, card)
        self.log(f"{player.name} 使用紅軍奧援作為資源，取得1資金與1宣傳")

    def _imitate_topdeck_targets(self, player):
        def has_deck_card(other):
            deck = getattr(other, 'deck', None)
            if deck is None:
                return False
            # draw() reshuffles the discard pile when the draw pile is empty, so a player with
            # cards in either pile still has a "牌庫頂牌" to reveal.
            return bool(getattr(deck, 'draw_pile', None) or getattr(deck, 'discard_pile', None))

        return [
            {'id': getattr(other, 'id', None), 'label': getattr(other, 'name', str(getattr(other, 'id', '')))}
            for other in self.players
            if other is not player and has_deck_card(other)
        ]

    def _prompt_imitate_topdeck_target(self, player):
        targets = self._imitate_topdeck_targets(player)
        if not targets:
            self.log(f"{player.name} 打出模仿戰術，但目前沒有其他玩家的牌庫頂牌可模仿")
            return {'success': True, 'no_target': True}
        self._set_pending_target_choice(
            player,
            'imitate_topdeck_target',
            targets,
            '模仿戰術：選擇 1 位玩家，展示其牌庫頂牌，本回合可以使用該牌。',
            source_name='模仿戰術',
        )
        return {'pending_choice': True}

    def _perform_imitate_topdeck(self, player, target_id):
        target = next((p for p in self.players if getattr(p, 'id', None) == target_id), None)
        if target is None or target is player:
            return {'error': 'Invalid imitate target'}
        drawn = target.deck.draw(1)
        if not drawn:
            self.log(f"{target.name} 沒有牌庫頂牌可供 {player.name} 模仿")
            return {'success': True, 'no_target': True}
        borrowed = drawn[0]
        setattr(borrowed, '_return_to_owner_topdeck', target.id)
        player.hand.append(borrowed)
        self.log(f"{player.name} 模仿了 {target.name} 的牌庫頂牌 {getattr(borrowed, 'name', str(borrowed))}")
        return {
            'success': True,
            'imitated_card': getattr(borrowed, 'name', None),
            'target_player_id': getattr(target, 'id', None),
            'target_player_name': getattr(target, 'name', None),
        }

    def _execute_support_card(self, player, card):
        card_name = getattr(card, 'name', str(card))
        tier, region_index, matched = self._support_card_tier(player, card)
        effect_type, payload = self._resolve_support_card_effect(card_name, tier, region_index)
        interaction_started = self._start_support_interaction(player, card_name, tier, region_index, effect_type, payload)
        if interaction_started:
            self.log(f"{player.name} started interactive support resolution for {card_name} at tier {tier}")
            response = {
                'tier': tier,
                'matched_rulers': matched,
                'effect_type': effect_type,
                'effect_text': self._support_card_effect_text(card_name, tier, region_index),
                'pending_choice': True,
            }
            if isinstance(interaction_started, dict):
                response.update({
                    key: value
                    for key, value in interaction_started.items()
                    if key in {'queued_map_choice', 'remaining_builds'}
                })
            return response
        interactive_effect_types = {
            'interactive_build_anywhere_inner',
            'interactive_build_near_inner',
            'interactive_dissolve_many_near',
            'interactive_dissolve_self_and_enemy',
            'interactive_dissolve_and_build',
            'force_discard_near',
        }
        if effect_type in interactive_effect_types:
            self.log(f"{card_name} had no legal target; no interactive effect was applied")
            return {
                'tier': tier,
                'matched_rulers': matched,
                'effect_type': effect_type,
                'effect_text': self._support_card_effect_text(card_name, tier, region_index),
                'no_legal_target': True,
            }
        if effect_type == 'gain_resource':
            player.resources['money'] += int(payload.get('money', 0) or 0)
            player.resources['propaganda'] += int(payload.get('propaganda', 0) or 0)
        elif effect_type == 'red_support_draw_and_pass':
            self._draw_player_cards(player, int(payload.get('draw', 0) or 0), trigger_name=card_name)
            current_faction = self.faction_by_id.get(player.faction_id, {})
            current_camp = current_faction.get('camp')
            pending_red_target = self._resolve_red_support_target_choice(player, card)
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
            self._draw_player_cards(player, int(payload.get('count', 0) or 0), trigger_name=card_name)
        elif effect_type == 'draw_then_discard':
            draw_count = int(payload.get('draw', 0) or 0)
            discard_count = int(payload.get('discard', 0) or 0)
            self._draw_player_cards(player, draw_count, trigger_name=card_name)
            # 卡面文字是「再從所有手牌中棄掉1張牌」，玩家可以自己選要棄哪一張（包含
            # 剛抽到的那張），不是寫死棄掉手牌最後一張（那樣等於抽了又立刻棄掉同一張，
            # 淨效果變成沒抽沒棄）。
            if discard_count > 0 and player.hand:
                self._set_pending_card_choice(
                    player,
                    'draw_then_discard_choice',
                    list(player.hand),
                    f'{card_name}：請從手牌中選擇 1 張棄掉。',
                    source_name=card_name,
                )
                return {
                    'tier': tier,
                    'matched_rulers': matched,
                    'effect_type': effect_type,
                    'effect_text': self._support_card_effect_text(card_name, tier, region_index),
                    'pending_choice': True,
                }
        elif effect_type == 'add_internal_conflict':
            count = int(payload.get('count', 0) or 0)
            target = next((p for p in self.players if p.faction_id == 'red_army'), None)
            if target:
                cards = self._take_static_purchase_cards('分神', count, reason=card_name)
                if cards:
                    target.deck.discard(cards)
                if len(cards) < count:
                    self.log(f"{player.name} resolved {card_name}: 分神供應僅能放置 {len(cards)}/{count} 張")
        self.log(f"{player.name} resolved {card_name} at tier {tier} (matched rulers: {', '.join(matched) if matched else 'none'})")
        return {'tier': tier, 'matched_rulers': matched, 'effect_type': effect_type, 'effect_text': self._support_card_effect_text(card_name, tier, region_index)}

    def _classify_base_options(self, faction):
        return classify_base_options(faction)

    def _resolve_starting_base(self, faction, used):
        return resolve_starting_base(
            self.map, self.towns_by_ruler, self.can_faction_develop_in_town, faction, used
        )

    def _base_option_to_towns(self, faction, option_name):
        return base_option_to_towns(
            self.map, self.towns_by_ruler, self.can_faction_develop_in_town, faction, option_name
        )

    def _candidate_base_names(self, faction):
        return candidate_base_names(
            self.map, self.towns_by_ruler, self.can_faction_develop_in_town, faction
        )

    def _compute_pending_base_choices(self):
        pending = {}
        used_fixed = {
            town
            for p in self.players
            for town, count in (p.organizations or {}).items()
            if count > 0
        }
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
            if kind == "fixed" and len(candidates) == 1 and candidates[0] not in used_fixed:
                p.base = candidates[0]
                p.organizations = {candidates[0]: 1}
                used_fixed.add(candidates[0])
            else:
                available_resolved = {
                    name: [town for town in self._base_option_to_towns(faction, name) if town not in used_fixed]
                    for name in names
                }
                pending[p.id] = {
                    "labels": names,
                    "resolved": available_resolved,
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
        if any(p.base == base_name for p in self.players if p.id != player_id) or self._town_has_physical_organization(base_name):
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
            if self.turn_phase == TurnPhase.ACTION and not self.current_event:
                self._start_event_phase()
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
            "red_army_base_dissolves": {},
            "red_army_base_build_blocks": [],
            "pending_topdeck_uses": 0,
        }

    def _resolve_ability_ref(self, ability):
        return resolve_ability_ref(self.ability_templates, ability)

    def _resolve_ability_text(self, text):
        return resolve_ability_text(self.ability_templates, text)

    def _resolve_faction_abilities(self, faction_id):
        return resolve_faction_abilities(self.faction_by_id, self.ability_templates, faction_id)

    def _player_base_data(self, player):
        return player_base_data(self.faction_by_id, player.faction_id, player.base)

    def _player_effective_abilities(self, player):
        return player_effective_abilities(
            self.faction_by_id, self.ability_templates, player.faction_id, player.base
        )

    def _player_has_ability(self, player, name):
        return player_has_ability(
            self.faction_by_id, self.ability_templates, player.faction_id, player.base, name
        )

    def _player_is_nonviolent(self, player):
        return player_is_nonviolent(self.faction_by_id, self.ability_templates, player)

    def _player_is_distance_restricted(self, player):
        return player_is_distance_restricted(self.faction_by_id, self.ability_templates, player)

    def _faction_restricts_ignore_distance_build(self, player, town):
        return faction_restricts_ignore_distance_build(
            self.map, self.towns_by_ruler, self.faction_by_id, self.ability_templates, player, town
        )

    def _ignore_distance_build_restricted(self, player, town):
        return ignore_distance_build_restricted(
            self.map,
            self.towns_by_ruler,
            self.faction_by_id,
            self.ability_templates,
            self._active_era_effects(),
            player,
            town,
        )

    def _restricted_build_fallback_towns(self, player, fallback_range):
        return restricted_build_fallback_towns(
            self.map, self.faction_by_id, self.players, self.ability_templates, player, fallback_range
        )

    def _support_taxonomy_entry(self, card_name):
        return support_taxonomy_entry(self.support_taxonomy, card_name)

    def _is_support_card(self, card):
        return is_support_card(self.support_taxonomy, card)

    def _is_india_flag_card(self, card):
        return is_india_flag_card(self.support_taxonomy, card)

    def _player_ruler_presence(self, player):
        return player_ruler_presence(self.map, self.faction_by_id, self.players, player)

    def _player_ruler_organization_counts(self, player):
        return player_ruler_organization_counts(self.map, self.faction_by_id, self.players, player)

    def _player_ruler_leadership(self, player):
        return player_ruler_leadership(self.map, self.faction_by_id, self.players, player)

    def _support_card_variant_info(self, card):
        return support_card_variant_info(self.support_taxonomy, card)

    def _support_card_tier(self, player, card):
        return support_card_tier(self.support_taxonomy, self.map, self.faction_by_id, self.players, player, card)

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
        return purchase_area_card_cost_total(self.structured_cards, self.support_taxonomy, card)

    def _purchase_area_card_cost_money(self, card):
        return purchase_area_card_cost_money(self.structured_cards, self.support_taxonomy, card)

    def _top_card_cost_total(self, card):
        # 2026-08-09 使用者 playtest 回報：立場試探／賭徒耳語／民族祭儀三個能力的文字都
        # 明講是猜「購買費用」奇偶（購買區標價，不是打出後拿到的資源），但這裡先前優先看
        # card.resources——而每張 Card 物件永遠有 resources 屬性（見 server/cards.py 的
        # `resources or {"money": 0, "propaganda": 0}` 預設），所以下面的購買費用查詢分支
        # 其實從未被真正執行過。對追隨者／樂捐者這類起始牌影響最大：它們沒有真正的購買
        # 價格（規則書：起始牌不會在遊戲中被購買），正確費用應為 0（偶數），但舊邏輯誤用
        # 印刷資源（例如樂捐者資源為1資金，被誤判成奇數）。
        return top_card_cost_total(self.structured_cards, self.support_taxonomy, card)

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

    def _red_army_unavailable_result(self, action_name, reason, message):
        """Return visible no-op feedback without consuming a Red Army action use."""
        return {
            'success': False,
            'result': {
                'name': action_name,
                'unavailable': True,
                'reason': reason,
                'message': message,
            },
        }

    def _red_army_action_preflight(self, player, action_name, target_player_id=None):
        if action_name == '政工部':
            internal_conflict = int(self.static_purchase_supply.get('內鬥', 0) or 0)
            distraction = int(self.static_purchase_supply.get('分神', 0) or 0)
            if internal_conflict <= 0 and distraction <= 0:
                return self._red_army_unavailable_result(
                    action_name,
                    'no_topdeck_supply',
                    '政工部：內鬥與分神供應皆空，目前沒有可放到目標牌庫頂的卡牌，未發動能力。',
                )

        if action_name == '國安部' and not self._red_army_state_security_targets(player):
            return self._red_army_unavailable_result(
                action_name,
                'no_dissolve_target',
                '國安部：目前沒有可以瓦解的組織（僅限紅軍組織 1 格內的牆內組織），未發動能力。',
            )

        if action_name == '中紀委' and not list(getattr(player, 'hand', None) or []):
            return self._red_army_unavailable_result(
                action_name,
                'no_hand_cards',
                '中紀委：目前沒有手牌可以棄掉，無法進行抽換，未發動能力。',
            )
        return None

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
                if (
                    count > 0
                    and town in inner_towns
                    and town in reachable
                    and self._can_dissolve_base_target(other, town)[0]
                ):
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
        if action_name not in red_army_actions:
            if self.turn_log.get('faction_action_used'):
                return {"error": "Faction action already used this turn"}
            # 後端也要驗證能力歸屬；不能只靠前端依陣營顯示按鈕
            if not self._player_has_ability(player, action_name):
                return {"error": "Player's faction does not have this ability"}

        if action_name in red_army_actions and not skip_reaction_prompt:
            target_player_id = kwargs.get('target_player_id') if action_name in {'政工部'} else None
            ok, err = self._red_army_can_use_action(player, action_name, target_player_id)
            if not ok:
                return {'error': err}
            unavailable = self._red_army_action_preflight(player, action_name, target_player_id)
            if unavailable:
                return unavailable
            prompt = self._red_army_action_reaction_prompt(player, action_name, kwargs)
            if prompt:
                return prompt

        if action_name == '統戰部':
            return self._activate_red_army_united_front(player)

        if action_name == '政工部':
            return self._activate_red_army_propaganda_department(player, kwargs.get('target_player_id'))

        if action_name == '國安部':
            return self._activate_red_army_state_security_action(player)

        if action_name == '中紀委':
            return self._activate_red_army_discipline_inspection(player)

        if action_name == '民主陣線':
            return self._activate_democratic_front(player)

        if action_name == '紅軍派系':
            return self._activate_red_army_faction_deck_reorder(player)

        if action_name == '立場試探':
            return self._activate_stance_probe(player)

        if action_name in {'賭徒耳語', '民族祭儀'}:
            return self._activate_guess_ability(player, action_name, kwargs.get('guess'))

        return {"error": "Unknown faction action"}

    def _activate_democratic_front(self, player):
        """民主陣線: spend 2 resources (propaganda first) for a removed-card proxy."""
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

    def _activate_red_army_faction_deck_reorder(self, player):
        """紅軍派系: inspect the top 3 cards, reorder them, then draw 1."""
        look = min(3, len(player.deck.draw_pile))
        if look <= 0:
            return {"error": "Deck empty"}
        inspected = list(reversed(player.deck.draw_pile[-look:]))
        self._set_pending_multi_card_choice(
            player,
            'era_inspect_deck_top_and_reorder',
            inspected,
            f"紅軍派系：檢視牌庫頂 {look} 張，請依序選擇 {look} 張放回牌庫頂（第一張會成為下一張抽到的牌），完成後抽 1 張牌。",
            look,
            top_count=look,
            look_count=look,
            source_name='紅軍派系',
            context={'draw_after_reorder': 1, 'faction_action_name': '紅軍派系'},
        )
        self.log(f"{player.name} triggered 紅軍派系 and inspected top {look} card(s)")
        return {'success': True, 'pending_choice': True, 'result': {'name': '紅軍派系', 'inspected_count': look}}

    def _activate_stance_probe(self, player):
        """立場試探: peek the top card, route it to hand (odd cost) or discard (even cost)."""
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
                "name": '立場試探',
                "revealed_card": getattr(card, 'name', str(card)),
                "cost_total": total,
                "destination": destination,
            },
        }

    def _activate_guess_ability(self, player, action_name, guess):
        """賭徒耳語/民族祭儀: bottom-deck a chosen hand card, then guess the new top card's cost parity.

        能力文字：「將1張手牌放進牌庫底」——由玩家選擇要墊哪一張；只有一張時不用問。
        """
        if not player.hand:
            return {"error": "No hand card to bottom-deck"}
        if guess not in {'odd', 'even'}:
            return {"error": "Guess required"}
        if len(player.hand) == 1:
            return self._resolve_guess_ability_with_bottom_card(player, action_name, guess, player.hand[0])
        self._set_pending_card_choice(
            player,
            'guess_ability_bottom_card',
            list(player.hand),
            f'{action_name}：請選擇 1 張手牌放進牌庫底。',
            source_name=action_name,
            context={'action_name': action_name, 'guess': guess},
        )
        return {'success': True, 'pending_choice': True}

    def _activate_red_army_united_front(self, player):
        """統戰部: draw 1 card."""
        ok, err = self._red_army_can_use_action(player, '統戰部')
        if not ok:
            return {'error': err}
        drawn = self._draw_player_cards(player, 1)
        self._mark_red_army_action_used('統戰部')
        self._track_event_progress('use_faction_ability', player=player)
        self.log(f"{player.name} triggered 統戰部 and drew {len(drawn)} card(s)")
        return {'success': True, 'result': {'name': '統戰部', 'drawn': len(drawn)}}

    def _activate_red_army_propaganda_department(self, player, target_player_id):
        """政工部: topdeck 內鬥 (fallback to whatever's in static supply) onto the target's deck."""
        target, pending_or_error = self._resolve_red_army_action_target(player, '政工部', target_player_id)
        if pending_or_error:
            return pending_or_error
        topdecked = '內鬥'
        added = self._topdeck_static_purchase_card(target, topdecked, '政工部')
        self._mark_red_army_action_used('政工部', target.id)
        self._track_event_progress('use_faction_ability', player=player)
        if added:
            self.log(f"{player.name} triggered 政工部 and placed {'、'.join(added)} on {target.name}'s deck")
        else:
            self.log(f"{player.name} triggered 政工部 but {topdecked} supply was empty")
        return {
            'success': True,
            'result': {
                'name': '政工部',
                'target_player_name': target.name,
                'topdecked_card': '、'.join(added) if added else None,
                'static_supply_empty': not added,
            },
        }

    def _activate_red_army_state_security_action(self, player):
        """國安部: open target selection for dissolving a nearby wall-inside organization."""
        ok, err = self._red_army_can_use_action(player, '國安部')
        if not ok:
            return {'error': err}
        return self._start_red_army_state_security(player)

    def _activate_red_army_discipline_inspection(self, player):
        """中紀委: discard any number of hand cards, then draw that many."""
        ok, err = self._red_army_can_use_action(player, '中紀委')
        if not ok:
            return {'error': err}
        cards = list(player.hand)
        if not cards:
            self._mark_red_army_action_used('中紀委')
            self._track_event_progress('use_faction_ability', player=player)
            self.log(f"{player.name} triggered 中紀委 with no hand cards")
            return {'success': True, 'result': {'name': '中紀委', 'discarded': 0, 'drawn': 0}}
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

    def _resolve_guess_ability_with_bottom_card(self, player, action_name, guess, bottom_card):
        if bottom_card not in player.hand:
            return {'error': 'Chosen card not in hand'}
        self.turn_log['faction_action_used'] = True
        self._track_event_progress('use_faction_ability', player=player)
        player.hand.remove(bottom_card)
        player.deck.draw_pile.insert(0, bottom_card)
        card = player.deck.draw_pile.pop()
        total = self._top_card_cost_total(card)
        guessed_odd = guess == 'odd'
        hit = (total % 2 == 1 and guessed_odd) or (total % 2 == 0 and not guessed_odd)
        # 能力文字只說「展示牌庫頂牌」：看完放回牌庫頂，不進棄牌堆
        player.deck.draw_pile.append(card)
        self.log(f"{player.name} triggered {action_name}, guessed {guess}, and revealed {card.name}")
        base_result = {
            'name': action_name,
            'revealed_card': getattr(card, 'name', str(card)),
            'cost_total': total,
            'guess': guess,
            'hit': hit,
            'bottom_card': getattr(bottom_card, 'name', str(bottom_card)),
            'destination': 'deck_top',
        }
        if action_name == '賭徒耳語':
            if hit:
                player.resources['money'] += 3
                player.resources['propaganda'] += 3
            return {'success': True, 'result': {**base_result, 'reward': {'money': 3 if hit else 0, 'propaganda': 3 if hit else 0}}}
        if hit:
            player.resources['money'] += 2
            player.resources['propaganda'] += 2
            return {'success': True, 'result': {**base_result, 'reward': {'money': 2, 'propaganda': 2}}}
        # 民族祭儀沒猜中：「獲得2點宣傳或2點資金」由玩家二選一
        self._set_pending_option_choice(
            player,
            'ethnic_ritual_miss_reward',
            [{'label': '獲得 2 點宣傳'}, {'label': '獲得 2 點資金'}],
            '民族祭儀：沒猜中，請選擇獲得 2 點宣傳或 2 點資金。',
            source_name=action_name,
            context={'base_result': base_result},
        )
        return {'success': True, 'pending_choice': True}

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
            self._pending_guerrilla_players.append(player.id)
            self.log(f"{player.name} triggered 游擊隊 and must choose to draw 1 card or force {red_player.name} to discard 1 card")
            if not self.pending_choice:
                self._continue_guerrilla_choice_queue()
        else:
            self._draw_player_cards(player, 1)
            self.log(f"{player.name} triggered 游擊隊 and drew 1 card")
        self._track_event_progress('use_faction_ability', player=player)

    def _continue_show_strength_choice_queue(self):
        if self.pending_choice:
            return None
        while self._pending_show_strength_players:
            player_id = self._pending_show_strength_players.pop(0)
            player = next((candidate for candidate in self.players if candidate.id == player_id), None)
            if player is None:
                continue
            self._set_pending_option_choice(
                player,
                'show_strength_reward',
                [{'label': '獲得 3 點宣傳'}, {'label': '獲得 3 點資金'}],
                '展現實力：請選擇獲得 3 點宣傳或 3 點資金。',
                source_name='展現實力',
            )
            return {'success': True, 'pending_choice': True, 'source': 'show_strength'}
        return None

    def _continue_guerrilla_choice_queue(self):
        if self.pending_choice:
            return None
        while self._pending_guerrilla_players:
            player_id = self._pending_guerrilla_players.pop(0)
            player = next((candidate for candidate in self.players if candidate.id == player_id), None)
            if player is None:
                continue
            red_player = next((candidate for candidate in self.players if candidate.faction_id == 'red_army'), None)
            if red_player is None or not red_player.hand:
                self._draw_player_cards(player, 1)
                self.log(f"{player.name} triggered 游擊隊 and drew 1 card because Red Army had no hand cards")
                continue
            self._set_pending_option_choice(
                player,
                'guerrilla_reward',
                [{'label': '抽 1 張牌'}, {'label': '令紅軍棄 1 張手牌'}],
                '游擊隊：請選擇抽 1 張牌，或令紅軍棄 1 張手牌。',
                source_name='游擊隊',
                context={'red_player_id': red_player.id},
            )
            return {'success': True, 'pending_choice': True, 'source': 'guerrilla'}
        return None

    def _record_action_build(self, player, town):
        """Apply every hook shared by a successful organization build during a player's action."""
        self.turn_log.setdefault("built_towns", []).append(town)
        self._track_event_progress('build_organization', town=town, player=player)
        # 安全屋不是單純的陣營說明文字；香港在牆內建立時，其「建立距離 +1」被動能力
        # 實際進入合法城鎮判定。事件卡「全國人大召開」的條件明列「使用或觸發陣營
        # 特殊能力」，因此成功建立牆內組織時必須把安全屋記為一次已觸發能力。移到倫敦／
        # 卡加利／多倫多後，安全屋已不在有效能力中，`_player_has_ability` 會自然排除。
        if (
            self._player_has_ability(player, "安全屋")
            and town in set(self._towns_for_region_alias("china"))
        ):
            self.log(f"{player.name} triggered 安全屋 while building in {town}")
            self._track_event_progress('use_faction_ability', player=player)
        self._apply_era_build_effects(player, town)
        self._apply_guerrilla_on_build(player, town)

    def _can_target_org_with_dissolve(self, attacker, defender, source="card"):
        if self._player_has_ability(defender, "盟旗學校"):
            self.log(f"{defender.name} triggered 盟旗學校 against {attacker.name}")
            self._track_event_progress('use_faction_ability', player=defender)
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

    def _add_setup_static_card_to_deck(self, player, card_name, count=1):
        gained = 0
        for _ in range(int(count or 1)):
            if card_name in STATIC_PURCHASE_CARD_NAMES:
                supply = int(self.static_purchase_supply.get(card_name, 0) or 0)
                if supply <= 0:
                    self.log(f"Setup could not add {card_name}: static supply empty")
                    continue
                self.static_purchase_supply[card_name] = supply - 1
            player.deck.draw_pile.append(self._starter_card(card_name))
            gained += 1
        return gained

    def _apply_setup_abilities(self, player):
        gained = 0
        for ability in self._player_effective_abilities(player):
            if not isinstance(ability, dict):
                continue
            if ability.get("name") == "攬炒策略":
                gained += self._add_setup_static_card_to_deck(player, "宣傳家")
            elif ability.get("name") in {"達賴救援", "東突厥斯坦政府", "活動家"}:
                gained += self._add_setup_static_card_to_deck(player, "宣傳家", 2)
            elif ability.get("name") == "各界資助":
                gained += self._add_setup_static_card_to_deck(player, "資助者")
        if gained:
            # 能力文字是「洗入起始牌庫」：把已抽的起手牌放回、連同額外卡整副重洗後
            # 重抽同樣張數——等同開局牌庫就含這些額外卡再抽起手，起手就可能抽到。
            hand_count = len(player.hand)
            if hand_count:
                player.deck.draw_pile.extend(player.hand)
                player.hand = []
                random.shuffle(player.deck.draw_pile)
                player.hand = player.deck.draw(hand_count)
            else:
                random.shuffle(player.deck.draw_pile)

    def _apply_card_play_faction_abilities(
        self,
        player,
        *,
        cost_has_money,
        cost_has_propaganda,
        played_card=None,
        used_faction_ability_names=None,
    ):
        """Apply each faction trigger once after a committed card clears reaction gating."""
        for used_name in list(used_faction_ability_names or []):
            self.log(f"{player.name} triggered {used_name} while playing a card")
            self._track_event_progress('use_faction_ability', player=player)
        for ability in self._player_effective_abilities(player):
            if not isinstance(ability, dict):
                continue
            name = ability.get("name")
            if self._maybe_trigger_first_money_draw(player, name, cost_has_money):
                continue
            if self._maybe_trigger_first_propaganda_draw(player, name, cost_has_propaganda):
                continue
            if self._maybe_trigger_first_propaganda_gain(player, name, cost_has_propaganda):
                continue
            if self._maybe_trigger_first_money_gain(player, name, cost_has_money):
                continue
            self._maybe_trigger_combo_reward(player, name)

        self._maybe_trigger_india_research_room(player, played_card)

    def _maybe_trigger_first_money_draw(self, player, name, cost_has_money):
        """商貿組織: first money-cost card play this turn -> draw 1 card."""
        if name != "商貿組織" or not cost_has_money or self.turn_log.get("faction_first_money_triggered"):
            return False
        self.turn_log["faction_first_money_triggered"] = True
        self._draw_player_cards(player, 1, trigger_name=name)
        self.log(f"{player.name} triggered {name} and drew 1 card")
        self._track_event_progress('use_faction_ability', player=player)
        return True

    def _maybe_trigger_first_propaganda_draw(self, player, name, cost_has_propaganda):
        """民族調和/星星之火: first propaganda-cost card play this turn -> draw 1 card."""
        if name not in {"民族調和", "星星之火"} or not cost_has_propaganda or self.turn_log.get("faction_first_propaganda_triggered"):
            return False
        self.turn_log["faction_first_propaganda_triggered"] = True
        self._draw_player_cards(player, 1, trigger_name=name)
        self.log(f"{player.name} triggered {name} and drew 1 card")
        self._track_event_progress('use_faction_ability', player=player)
        return True

    def _maybe_trigger_first_propaganda_gain(self, player, name, cost_has_propaganda):
        """人同此心: first propaganda-cost card play this turn -> gain 2 propaganda."""
        if name != "人同此心" or not cost_has_propaganda or self.turn_log.get("faction_first_prop_gain_triggered"):
            return False
        self.turn_log["faction_first_prop_gain_triggered"] = True
        player.resources["propaganda"] += 2
        self.log(f"{player.name} triggered 人同此心 and gained 2 propaganda")
        self._track_event_progress('use_faction_ability', player=player)
        return True

    def _maybe_trigger_first_money_gain(self, player, name, cost_has_money):
        """基金會/共合會: first money-cost card play this turn -> gain 2 money."""
        if name not in {"基金會", "共合會"} or not cost_has_money or self.turn_log.get("faction_first_money_gain_triggered"):
            return False
        self.turn_log["faction_first_money_gain_triggered"] = True
        player.resources["money"] += 2
        self.log(f"{player.name} triggered {name} and gained 2 money")
        self._track_event_progress('use_faction_ability', player=player)
        return True

    def _maybe_trigger_combo_reward(self, player, name):
        """展現實力: after 3 distinct non-starter card plays this turn -> pending choice for 3 propaganda or 3 money."""
        if name != "展現實力" or self.turn_log.get("combo_reward_triggered"):
            return False
        if len(self.turn_log.get("played_nonstarter_names", [])) < 3:
            return False
        self.turn_log["combo_reward_triggered"] = True
        self._pending_show_strength_players.append(player.id)
        self.log(f"{player.name} triggered 展現實力 and must choose 3 propaganda or 3 money")
        if not self.pending_choice:
            self._continue_show_strength_choice_queue()
        self._track_event_progress('use_faction_ability', player=player)
        return True

    def _maybe_trigger_india_research_room(self, player, played_card):
        """印度研究分析室: playing an India flag card -> gain 2 money (once per turn)."""
        if (
            played_card is None
            or not self._player_has_india_research_room(player)
            or not self._is_india_flag_card(played_card)
            or self.turn_log.get("india_flag_money_triggered")
        ):
            return False
        self.turn_log["india_flag_money_triggered"] = True
        player.resources["money"] += 2
        self.log(f"{player.name} triggered 印度研究分析室 and gained 2 money")
        self._track_event_progress('use_faction_ability', player=player)
        return True

    def _apply_turn_end_faction_abilities(self, player):
        effective = self._player_effective_abilities(player)
        built_towns = self.turn_log.get("built_towns", []) or []
        built_in_china = any(t in set(self._towns_for_region_alias("china")) for t in built_towns)
        built_in_nanyang = any(t in {"曼谷", "吉隆坡", "新加坡", "雅加達", "河內", "胡志明市", "仰光"} for t in built_towns)

        for ability in effective:
            if not isinstance(ability, dict):
                continue
            name = ability.get("name")
            if self._maybe_trigger_turn_end_build_draw(player, name, built_in_china):
                continue
            self._maybe_trigger_turn_end_expansion_draw(player, name, built_in_china, built_in_nanyang)

    def _maybe_trigger_turn_end_build_draw(self, player, name, built_in_china):
        """本土社團/還我河山: built in China this turn -> draw 1 card."""
        if name not in {"本土社團", "還我河山"} or not built_in_china:
            return False
        self._draw_player_cards(player, 1)
        self.log(f"{player.name} triggered {name} and drew 1 card")
        self._track_event_progress('use_faction_ability', player=player)
        return True

    def _maybe_trigger_turn_end_expansion_draw(self, player, name, built_in_china, built_in_nanyang):
        """民國之心: built in China or Nanyang this turn -> draw 1 card."""
        if name != "民國之心" or not (built_in_china or built_in_nanyang):
            return False
        self._draw_player_cards(player, 1)
        self.log(f"{player.name} triggered 民國之心 and drew 1 card")
        self._track_event_progress('use_faction_ability', player=player)
        return True

    def _camp_token_for_faction_id(self, faction_id):
        return camp_token_for_faction_id(self.faction_by_id, faction_id)

    def _camp_token_for_player(self, player):
        return camp_token_for_player(self.faction_by_id, player)

    def _red_army_base_build_blocked(self, faction_id, town):
        return red_army_base_build_blocked(getattr(self, 'turn_log', {}), faction_id, town)

    def can_faction_develop_in_town(self, faction_id, town):
        return can_faction_develop_in_town(self.map, self.faction_by_id, getattr(self, 'turn_log', {}), faction_id, town)

    def _canonical_faction_name_to_id(self, name):
        return canonical_faction_name_to_id(name)

    def _factions_sharing_with(self, faction_id):
        return factions_sharing_with(self.faction_by_id, faction_id)

    def _organization_entries_at(self, town):
        return organization_entries_at(self.players, town)

    def _town_has_physical_organization(self, town):
        return town_has_physical_organization(self.players, town)

    def _organization_towns_for_player(self, player):
        return organization_towns_for_player(self.map, self.faction_by_id, self.players, player)

    def _organization_occupancy_violations(self):
        return organization_occupancy_violations(self.map, self.players)

    def _place_organization(self, player, town, *, require_supply=True, require_development=True, enforce_base_build_block=True):
        if town not in self.map.get('towns', {}):
            return False
        if enforce_base_build_block and self._red_army_base_build_blocked(getattr(player, 'faction_id', None), town):
            return False
        if self._town_has_physical_organization(town):
            return False
        if require_supply and not self._has_org_supply(player):
            return False
        if require_development and not self.can_faction_develop_in_town(player.faction_id, town):
            return False
        player.organizations[town] = 1
        return True

    def _shared_org_count(self, player, town):
        return shared_org_count(self.faction_by_id, self.players, player, town)

    def _shared_origin_owner(self, player, town):
        return shared_origin_owner(self.faction_by_id, self.players, player, town)

    def _town_has_shared_org_access(self, player, town):
        return town_has_shared_org_access(self.faction_by_id, self.players, player, town)

    def _town_blocks_movement_for_player(self, player, town):
        return town_blocks_movement_for_player(self.faction_by_id, self.players, player, town)

    def _can_player_build_in_town(self, player, town):
        return self.can_develop_in_town(player, town)

    def _rail_reachable_within_three(self, player, from_town, to_town):
        return rail_reachable_within_three(
            self.map, self.towns_by_ruler, self.faction_by_id, self.players, player, from_town, to_town
        )

    def _org_supply_limit(self, player):
        return org_supply_limit(player)

    def _has_org_supply(self, player, count=1):
        # Routed through self._org_supply_limit (not the module's has_org_supply
        # composite) so that tests can monkeypatch _org_supply_limit and have it
        # take effect here — see test_build_entitlement_queue.py.
        return player.total_organizations() + count <= self._org_supply_limit(player)

    def can_develop_in_town(self, player, town):
        # Routed through self._has_org_supply for the same monkeypatch reason.
        if self._town_has_physical_organization(town):
            return False
        if not self._has_org_supply(player):
            return False
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
        self._action_log_visibility = []
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

    def _non_red_player_indices(self):
        return [
            idx for idx, player in enumerate(self.players)
            if getattr(player, 'faction_id', None) != 'red_army'
        ]

    def _is_final_non_red_turn_before_round_wrap(self, next_player_index):
        """Return True when the current END step finishes the non-red mission window.

        Event-card missions are non-red tasks: Red Army actions do not progress
        them, and failure penalties should fire before control passes to Red
        Army-only turns. With action-first turns, using the full table wrap as
        the settlement boundary delays cards like 紅軍權貴出逃 until after the
        Red Army turn and applies discard_self to the wrong player.
        """
        current = self.current_player()
        next_player = self.players[next_player_index]
        if getattr(current, 'faction_id', None) != 'red_army' and getattr(next_player, 'faction_id', None) == 'red_army':
            return True

        non_red_indices = self._non_red_player_indices()
        if not non_red_indices:
            return next_player_index == getattr(self, 'round_start_player_index', 0)

        round_start = getattr(self, 'round_start_player_index', 0)
        ordered = list(range(len(self.players)))
        ordered = ordered[round_start:] + ordered[:round_start]
        non_red_in_round_order = [idx for idx in ordered if idx in non_red_indices]
        if not non_red_in_round_order:
            return next_player_index == round_start
        return self.current_player_index == non_red_in_round_order[-1]

    def log(self, message, *, private_messages=None, public_message=None):
        prefix = f"[Turn {self.turn}] "
        self.action_log.append(prefix + str(message))
        visibility = None
        if private_messages or public_message is not None:
            visibility = {
                'private_messages': {
                    str(player_id): prefix + str(private_message)
                    for player_id, private_message in (private_messages or {}).items()
                },
                'public_message': prefix + str(public_message if public_message is not None else message),
            }
        self._action_log_visibility.append(visibility)
        if len(self.action_log) > 100:
            self.action_log.pop(0)
            self._action_log_visibility.pop(0)

    def log_private_draw(self, player, drawn, *, source='effect', trigger_name=None):
        drawn = list(drawn or [])
        if not drawn:
            return
        count = len(drawn)
        names = '、'.join(getattr(card, 'name', str(card)) for card in drawn)
        if trigger_name:
            private_message = f"{player.name} 因{trigger_name}抽到：{names}"
            public_message = f"{player.name} 因{trigger_name}抽了 {count} 張牌"
        elif source == 'era':
            private_message = f"{player.name} 因時代關卡效果抽到：{names}"
            public_message = f"{player.name} 因時代關卡效果抽了 {count} 張牌"
        else:
            private_message = f"{player.name} 抽到：{names}"
            public_message = f"{player.name} 抽了 {count} 張牌"
        self.log(
            private_message,
            private_messages={player.id: private_message},
            public_message=public_message,
        )

    def log_private_shared_draw(self, first_player, first_drawn, second_player, second_drawn, *, source_name):
        first_drawn = list(first_drawn or [])
        second_drawn = list(second_drawn or [])
        count = max(len(first_drawn), len(second_drawn))
        first_names = '、'.join(getattr(card, 'name', str(card)) for card in first_drawn)
        second_names = '、'.join(getattr(card, 'name', str(card)) for card in second_drawn)
        public_message = f"{first_player.name} 與 {second_player.name} 因{source_name}各抽了 {count} 張牌"
        first_message = f"{public_message}：{first_player.name}抽到：{first_names}；{second_player.name}抽了 {len(second_drawn)} 張牌"
        second_message = f"{public_message}：{first_player.name}抽了 {len(first_drawn)} 張牌；{second_player.name}抽到：{second_names}"
        diagnostic_message = (
            f"{public_message}：{first_player.name}抽到：{first_names}；"
            f"{second_player.name}抽到：{second_names}"
        )
        self.log(
            diagnostic_message,
            private_messages={
                first_player.id: first_message,
                second_player.id: second_message,
            },
            public_message=public_message,
        )

    def _project_action_log(self, viewer_player_id=None):
        return project_action_log(self.action_log, getattr(self, '_action_log_visibility', []), viewer_player_id)

    def _support_card_has_legal_target(self, player, card):
        # Non-mutating legal-target pre-check, sharing _support_interaction_targets (the
        # single source of truth) with _start_support_interaction so the two can never
        # disagree. Lets play_card reject an illegal interactive support play — and decide
        # whether to open a cancel-reaction window — *before* mutating the board or setting
        # up the support card's own interactive pending choice. Non-interactive support
        # effects (gain_resource / draw / draw_then_discard / add_internal_conflict) always
        # resolve, so _support_interaction_targets returns None for them.
        card_name = getattr(card, 'name', str(card))
        tier, region_index, _ = self._support_card_tier(player, card)
        effect_type, payload = self._resolve_support_card_effect(card_name, tier, region_index)
        targets = self._support_interaction_targets(player, effect_type, payload)
        if targets is None:
            return True
        return bool(targets)

    def _resume_after_optional_trash(self, player, choice, removed_current_card=False):
        context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
        card_name = context.get('card_name') or choice.get('source_name')
        current_card = context.get('current_card')
        if not removed_current_card and current_card is not None:
            if not self._return_borrowed_card_to_owner_topdeck(current_card):
                player.deck.discard([current_card])
        if not card_name or card_name == '誘導虛耗':
            return None
        card_def = getattr(self.action_engine, 'cards', {}).get(card_name) if getattr(self, 'action_engine', None) else None
        if not card_def:
            return None
        seen_optional = False
        effects = card_def.get('effect', [])
        for idx, effect in enumerate(effects):
            if not seen_optional:
                if effect.get('type') == 'optional_trash':
                    seen_optional = True
                continue
            context['remaining_effects'] = effects[idx + 1:]
            result = self.effect_engine.execute(effect, player, self, context=context)
            if isinstance(result, dict) and result.get('pending_choice'):
                return result
        return None

    def _available_purchased_cards_for_topdeck(self, player):
        purchased = list(self.turn_log.get('purchased_cards_this_turn') or [])
        return [card for card in purchased if card in player.deck.discard_pile]

    def _consume_one_pending_topdeck_use(self, player, *, end_turn_flow):
        remaining = self.turn_log.get('pending_topdeck_uses', 0)
        if remaining <= 0:
            return {'no_rights': True}
        candidates = self._available_purchased_cards_for_topdeck(player)
        if not candidates:
            return {'no_candidates': True}
        self.turn_log['pending_topdeck_uses'] = remaining - 1
        if len(candidates) == 1:
            card = candidates[0]
            player.deck.discard_pile.remove(card)
            player.deck.draw_pile.append(card)
            self.log(f"{player.name} 使用頂牌權利，將 {getattr(card, 'name', str(card))} 置於牌庫頂")
            return {'auto_placed': True}
        # 本回合買了多張：由玩家選擇要頂哪一張
        self._set_pending_card_choice(
            player,
            'topdeck_purchased_choice',
            list(candidates),
            '行動預告／行動募資：選擇 1 張本回合購得的牌置於牌庫頂。',
            source_name='行動預告／行動募資',
            context={'end_turn_topdeck_flow': bool(end_turn_flow)},
        )
        return {'pending_choice': True}

    def use_pending_topdeck_right(self):
        player = self.current_player()
        if self.pending_choice:
            return {'error': 'Resolve pending choice before using a topdeck right'}
        result = self._consume_one_pending_topdeck_use(player, end_turn_flow=False)
        if result.get('no_rights'):
            return {'error': 'No pending topdeck right available'}
        if result.get('no_candidates'):
            return {'error': 'No purchased card available to topdeck yet'}
        return {'success': True, **({'pending_choice': True} if result.get('pending_choice') else {})}

    def _prompt_end_turn_topdeck_action_if_available(self):
        player = self.current_player()
        result = self._consume_one_pending_topdeck_use(player, end_turn_flow=True)
        if result.get('pending_choice'):
            self.log(f"{player.name} may resolve remaining 行動預告/行動募資 topdeck rights before drawing new hand")
            return {'pending_choice': True}
        if result.get('no_candidates') and self.turn_log.get('pending_topdeck_uses', 0) > 0:
            dropped = self.turn_log.get('pending_topdeck_uses', 0)
            self.turn_log['pending_topdeck_uses'] = 0
            self.log(f"{player.name} 有 {dropped} 次頂牌權利本回合沒有可頂的牌，作廢")
            return None
        if result.get('auto_placed'):
            return self._prompt_end_turn_topdeck_action_if_available()
        return None

    def _mission_settlement_target_id(self):
        if self.event_progress and self.event_progress.get('last_actor_id'):
            return self.event_progress.get('last_actor_id')
        player = self.current_player()
        return getattr(player, 'id', None)

    def _should_defer_event_settlement_until_after_refill(self):
        event = self.current_event or {}
        if event.get('type') != 'mission' or not self.event_progress or self.event_progress.get('settled'):
            return False
        succeeded = bool(self.event_progress.get('succeeded'))
        effect = event.get('success') if succeeded else event.get('failure')
        effect_type = (effect or {}).get('type')
        # Top-deck rewards must resolve before refill so the chosen card can be drawn.
        if succeeded and effect_type == 'topdeck_from_discard':
            return False
        # All other mission outcomes are resolved after end-turn cleanup/refill so
        # rewards and penalties operate on the player's next hand instead of being
        # immediately discarded or dodged by emptying the hand.
        return True

    def advance_turn_phase(self):
        if self.pending_choice and not self._recover_stale_event_build_choice_if_satisfied():
            return {"error": "Resolve pending choice before advancing phase"}
        if getattr(self, 'hk_relocation_blocks_turn_handoff', False):
            return {"error": "請先決定香港根據地要遷移至何處，或選擇留在目前根據地"}
        if self.turn_phase == TurnPhase.EVENT:
            # Only drain already-queued (possibly interactive) era activations here;
            # do NOT run trigger detection mid-round. New eras become eligible only at
            # the round-wrap boundary in _end_turn(), after every player incl. Red Army
            # has acted (see _detect_era_triggers).
            self._continue_era_activation_queue()
            if not self.current_event:
                self._start_event_phase()
                return {"success": True}
            auto_result = self._apply_auto_event_if_ready()
            if auto_result and auto_result.get('pending_choice'):
                return {"success": True, "pending_choice": True}
            self.turn_phase = TurnPhase.ACTION
        else:
            # 行動階段（出牌／購買／陣營能力可自由交錯）只有一個不可逆的結束動作：
            # 按下「結束行動階段」→ 補牌至5張、換下一位玩家。TurnPhase.END 保留為
            # 這段結算流程的內部標記（香港根據地遷移等待窗口會停在這裡），不再是
            # 玩家需要按第二次按鈕才能離開的獨立階段。
            self.turn_phase = TurnPhase.END
            return self._finish_action_phase()
        return {"success": True}

    def _finish_action_phase(self):
        """結束目前玩家的行動階段：在正確時機結算本輪事件、清空待用的頂牌權利、
        補手牌到5張／補滿購買區、時代關卡 tick、把席位交給下一位玩家。
        呼叫前 self.turn_phase 必須已經是 TurnPhase.END。
        正常完成回傳 {"success": True}；卡在必要決定（事件結算選擇／香港根據地
        遷移）時回傳帶 pending_choice / pending_hk_relocation 的 dict，此時席位
        不會交出去。
        """
        # Mission events are round-wide: resolve after the final player's
        # purchase step, so buy_card triggers have a chance to progress.
        next_player_index = (self.current_player_index + 1) % len(self.players)
        is_round_final_action = self._is_final_non_red_turn_before_round_wrap(next_player_index)
        # A live `end_turn_state` trigger (e.g. 烏魯木齊七五事件's own_organization_in_scope)
        # is a FRESH state check at settlement, not an accumulated counter. It must be
        # judged only once the WHOLE round — Red Army included — has acted, because Red
        # Army's own turn this round can still dissolve the organization that satisfies
        # it (playtest 回報：所有事件卡都應該要所有人都輪過該回合才結算). Count-based
        # triggers stay at the final non-red turn (before Red Army-only turns) because
        # Red Army never progresses their counter and failure penalties belong to the
        # non-red actor; only the state check needs the true round-wrap boundary, which
        # mirrors the era-trigger / victory-declaration rule (P1: 判定時機應等整輪含紅軍
        # 行動完). The settlement target is still captured at the final non-red boundary
        # below and persists in event_progress until the wrap, so a later Red-Army seat
        # never becomes the target.
        trigger_type = ((self.current_event or {}).get('trigger') or {}).get('type')
        event_is_state_triggered = trigger_type == 'end_turn_state'
        is_true_round_wrap = next_player_index == getattr(self, 'round_start_player_index', 0)
        settle_boundary = is_true_round_wrap if event_is_state_triggered else is_round_final_action
        defer_event_settlement = settle_boundary and self._should_defer_event_settlement_until_after_refill()
        if is_round_final_action and self.event_progress is not None:
            self.event_progress['settlement_target_player_id'] = self._mission_settlement_target_id()
        if settle_boundary and not defer_event_settlement and not (self.event_progress or {}).get('settled'):
            event_result = self._settle_current_event()
            if event_result and event_result.get('pending_choice'):
                return {"success": True, "pending_choice": True}
        pending = self._prompt_end_turn_topdeck_action_if_available()
        if pending:
            return {"success": True, "pending_choice": True}
        # Snapshot the round's event before _end_turn: when this END also wraps the
        # round, _end_turn discards current_event/event_progress and draws the next
        # round's event. Without the snapshot the deferred settlement would settle
        # that untouched new event instead — dropping the earned success reward and
        # applying a bogus failure penalty for an event nobody has acted on yet.
        deferred_event = self.current_event if defer_event_settlement else None
        deferred_progress = self.event_progress if defer_event_settlement else None
        hong_kong_must_decide_before_handoff = bool(
            defer_event_settlement
            and (deferred_event or {}).get('name') == '香港抗暴之戰'
            and any(getattr(pl, 'faction_id', None) == 'hong_kong' for pl in self.players)
        )
        if hong_kong_must_decide_before_handoff:
            # 先完成本回合的補牌與回合結束能力，但不要把席位交給下一位玩家。
            # 香港事件的成功／失敗效果仍維持「補牌後結算」；必要棄牌完成後再開遷移窗口。
            self.hk_relocation_blocks_turn_handoff = True
            self._end_turn(advance_player=False)
            event_result = self._settle_current_event()
            if event_result and event_result.get('pending_choice'):
                return {"success": True, "pending_choice": True}
            if self.hk_free_base_relocation:
                return {"success": True, "pending_hk_relocation": True}
            self.hk_relocation_blocks_turn_handoff = False
            self._finish_end_turn_handoff()
            return {"success": True}

        self._end_turn()
        if defer_event_settlement and deferred_progress is not None and not deferred_progress.get('settled'):
            wrapped = self.current_event is not deferred_event
            if wrapped:
                next_event = self.current_event
                next_progress = self.event_progress
                next_notification = self.event_notification
                self.current_event = deferred_event
                self.event_progress = deferred_progress
                event_result = self._settle_current_event()
                self.current_event = next_event
                self.event_progress = next_progress
                # Keep the new round's event on display; the settled outcome is in the log.
                self.event_notification = next_notification
            else:
                event_result = self._settle_current_event()
            if event_result and event_result.get('pending_choice'):
                return {"success": True, "pending_choice": True}
        return {"success": True}

    def _end_turn(self, advance_player=True):
        # Victory *detection* is NOT run per player-turn. It is deferred to the
        # round-wrap boundary below so Red Army's turn this round can still
        # invalidate a condition (e.g. dissolve an organization propping up an
        # org-count victory) before a winner is declared — mirrors the era-trigger
        # round-wrap rule (P1: 宣布勝利時機應等整輪含紅軍行動完才公布). The guard
        # below stays as a defensive no-op in case _end_turn is re-entered after
        # the game already finished at a prior round wrap.
        if self.game_phase == GamePhase.FINISHED:
            return

        player = self.current_player()
        # rules.md／playtest 回報：回合結束是「抽牌補足到 5 張」——保留既有手牌，
        # 不足 5 才補到 5，已有 5 張以上則不抽；不可清空手牌重抽。
        player.reset_turn()
        refill_needed = max(0, 5 - len(player.hand))
        draw_count_before = len(player.deck.draw_pile) if player.deck else 0
        discard_count_before = len(player.deck.discard_pile) if player.deck else 0
        reshuffles_during_refill = refill_needed > draw_count_before and discard_count_before > 0
        player.draw_to_five()
        if reshuffles_during_refill:
            self.log(f"{player.name} 牌庫用盡，將棄牌堆 {discard_count_before} 張牌洗成新牌庫")
        # 回合結束型能力（本土社團/還我河山/民國之心等「行動階段結束時額外再抽1張」）
        # 在補滿之後觸發，額外抽的牌不會被補牌流程蓋掉（可達 6 張）。
        self._apply_turn_end_faction_abilities(player)
        while len(self.purchase_area) < len(self._static_purchase_cards()) + 5:
            drawn = self._draw_purchase_cards(1)
            if not drawn:
                break
            self.purchase_area.extend(drawn)
        self.log(f"End of turn for {player.name}")

        self._tick_event_modifiers_at_turn_end()
        self.event_notification = self._event_display_payload()
        self.turn_log = self._new_turn_log()

        # Keep draining any in-flight (interactive) era activation every turn so a
        # pending choice from an already-triggered era is not stalled.
        self._continue_era_activation_queue()

        # 時代關卡只在紅軍完成自己的回合後判定。不能在最後一位非紅軍玩家結束時
        # 先把關卡排入佇列，否則紅軍尚未獲得本回合瓦解組織的機會，下一次輪到紅軍
        # 就會立即觸發舊快照（playtest：第 13 回合藏國騷亂應等紅軍行動完，於第 14
        # 回合正式觸發）。若紅軍是整輪最後一席，先增加回合數，讓觸發與效果紀錄
        # 使用新回合編號；真正交棒時再略過重複增加。
        if getattr(player, 'faction_id', None) == 'red_army':
            # 「持續 N 回合」按完整輪次計算，不按每位玩家的個別行動回合計算。
            # 紅軍回合結束是既有時代關卡判定邊界：先扣除已生效關卡的期限，
            # 再偵測新關卡，避免新觸發的 2 回合效果立即被扣成 1 回合。
            if self.era_engine:
                expired_eras = self.era_engine.tick()
                if (
                    self.era_notification
                    and self.era_notification.get("id") in set(expired_eras)
                ):
                    self.era_notification = None
            next_player_index = (self.current_player_index + 1) % len(self.players)
            wraps_round = next_player_index == getattr(self, 'round_start_player_index', 0)
            if wraps_round and not self._era_turn_preincremented:
                self.turn += 1
                self._era_turn_preincremented = True
            self._detect_era_triggers()
            self._continue_era_activation_queue()
            if self.pending_choice:
                self.era_blocks_turn_handoff = bool(advance_player)
                return

        if advance_player:
            self._finish_end_turn_handoff()

    def _finish_end_turn_handoff(self):
        """Advance the seat after all end-turn effects and mandatory decisions finish."""
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        if self.current_player_index == getattr(self, 'round_start_player_index', 0):
            if self._era_turn_preincremented:
                self._era_turn_preincremented = False
            else:
                self.turn += 1
            # Round wrap: every player (Red Army included) has now acted this round.
            # This is the ONLY point victory is judged — a condition that briefly
            # looked satisfied earlier in the round but was undone by a later Red
            # Army action is correctly no longer declared a win (P1: 宣布勝利時機
            # 應等整輪含紅軍行動完才公布).
            # rules.md：第20回合結束前無人勝利→紅軍勝利。整輪結束、回合數推進到21的
            # 當下立刻判定（P1 playtest 回報：到第20回合沒有直接宣告勝利者），
            # 不讓遊戲滑進第21回合、也不再抽新事件。
            self._check_victory()
            if self.game_phase == GamePhase.FINISHED:
                return
            self.current_event = None
            self.event_progress = None
            self.event_notification = None
        # 既有存檔可能仍帶有尚未完成的時代佇列；交棒後繼續排空，但新關卡的
        # 偵測只會在紅軍回合結束時發生。
        self._continue_era_activation_queue()
        self.turn_phase = TurnPhase.ACTION
        if not self.current_event:
            self._start_event_phase()
        else:
            self._apply_auto_event_if_ready()

    def _check_victory(self):
        win, winner = self.victory_engine.evaluate(self)
        if win:
            self.game_phase = GamePhase.FINISHED
            self.winner = winner
            # rules.md 共同勝利（2026-07-11 裁決 A4）：反共玩家獲勝時，
            # 其他反共玩家達成自身勝利條件 2/3 以上（含）者為共同勝利者
            self.co_winners = self.victory_engine.co_winners(self, winner)
            if self.co_winners:
                self.log(f"共同勝利者：{'、'.join(self.co_winners)}")

    def _pending_board_action_error(self, allowed_choice_keys=None):
        """Reject a new board mutation while the game is waiting for a required choice.

        ``card_build_organization`` intentionally permits movement between queued builds so
        the next build range can refresh from the organization's new location. Callers must
        opt into that narrow exception explicitly; every other pending choice stays locked.
        """
        choice = self.pending_choice or {}
        allowed = set(allowed_choice_keys or [])
        if choice and choice.get('choice_key') not in allowed:
            return {"error": "請先完成目前的選擇"}
        return None

    def build_organization(self, town):
        player = self.current_player()
        pending_result = self._resolve_pending_build_choice_for_town(player, town)
        if pending_result is not None:
            return pending_result

        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Not in ACTION phase"}
        if not town:
            return {"error": "Town required"}
        if self._event_modifier_active('restrict_build'):
            return {"error": "Current event restricts building organizations"}
        if town not in self.map.get("towns", {}):
            return {"error": "Invalid town"}
        if not self._town_has_shared_org_access(player, town):
            return {"error": "No organization in town"}
        if self._red_army_base_build_blocked(getattr(player, 'faction_id', None), town):
            return {"error": "Red Army cannot rebuild this base during the current turn"}
        if not self._has_org_supply(player):
            return {"error": f"組織棋已達上限（{self._org_supply_limit(player)}），需先瓦解既有組織"}
        if not self._can_player_build_in_town(player, town):
            return {"error": "Cannot develop in this town"}

        self._place_organization(player, town)
        self._record_action_build(player, town)
        self.log(f"{player.name} built organization in {town}")
        return {"success": True, **({"pending_choice": True} if self.pending_choice else {})}

    def build_organization_with_support(self, origin_town, target_town):
        """內部輔助：以 origin_town 為起點、在距離內的 target_town 建立組織。

        注意：這**不是**玩家可直接操作的動作，前端與 WebSocket 都不再有入口。
        建立組織只能經由卡牌／奧援／事件／年代效果產生的待決選擇來完成
        （見 `_card_build_town_choices()`、`_interactive_support_build_towns()`、
        `build_organization()`）。這個方法只保留給年代／事件／占領規則的驗證腳本
        當作佈局工具使用，因此**不得**在此套用安全屋（或任何陣營被動）的距離加成——
        安全屋「建立牆內組織時距離 +1」只該在上述卡牌觸發的候選清單裡生效。
        """
        pending_error = self._pending_board_action_error()
        if pending_error:
            return pending_error
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
        if self._red_army_base_build_blocked(getattr(player, 'faction_id', None), target_town):
            return {"error": "Red Army cannot rebuild this base during the current turn"}
        if not self._has_org_supply(player):
            return {"error": f"組織棋已達上限（{self._org_supply_limit(player)}），需先瓦解既有組織"}
        if not self._can_player_build_in_town(player, target_town):
            return {"error": "Cannot develop in this town"}

        max_distance = 1 + int(getattr(player, 'build_range_bonus', 0) or 0)
        if origin_town != target_town and (not self._event_modifier_active('ignore_distance') or self._era_restricts_ignore_distance_build(player, target_town) or self._faction_restricts_ignore_distance_build(player, target_town)):
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

        self._place_organization(player, target_town)
        self._record_action_build(player, target_town)
        self.log(f"{player.name} built organization in {target_town} from {origin_town}")
        return {"success": True, **({"pending_choice": True} if self.pending_choice else {})}

    def _record_red_army_base_dissolve(self, attacker, target_owner, town):
        if getattr(target_owner, 'faction_id', None) != 'red_army':
            return False
        if town != getattr(target_owner, 'base', None):
            return False
        counts = self.turn_log.setdefault('red_army_base_dissolves', {})
        attacker_id = getattr(attacker, 'id', getattr(attacker, 'name', 'attacker'))
        key = f'{attacker_id}:{town}'
        counts[key] = int(counts.get(key, 0) or 0) + 1
        if counts[key] < 2:
            self.log(f"{attacker.name} 本回合第 1 次成功瓦解{town}紅軍根據地（1/2）；根據地組織仍保留")
            return False
        blocked = self.turn_log.setdefault('red_army_base_build_blocks', [])
        if town not in blocked:
            blocked.append(town)
        if target_owner.organizations.get(town, 0) > 0:
            del target_owner.organizations[town]
        self.log(f"{attacker.name} 本回合第 2 次成功瓦解{town}紅軍根據地（2/2）；移除根據地組織，紅軍本回合不能在該地建立組織")
        return True

    def _can_dissolve_base_target(self, target_owner, town):
        return can_dissolve_base_target(target_owner, town)

    def dissolve_organization(self, attacker, defender, town, source="card", _from_pending_choice=False):
        if not _from_pending_choice:
            pending_error = self._pending_board_action_error()
            if pending_error:
                return pending_error
        if not town:
            return {"error": "No organization in target town"}

        target_owner = self._shared_origin_owner(defender, town)
        if not target_owner:
            return {"error": "No organization in target town"}

        ok, err = self._can_dissolve_base_target(target_owner, town)
        if not ok:
            return {"error": err}

        ok, err = self._can_target_org_with_dissolve(attacker, target_owner, source=source)
        if not ok:
            return {"error": err}

        is_red_base = (
            getattr(target_owner, 'faction_id', None) == 'red_army'
            and town == getattr(target_owner, 'base', None)
        )
        red_base_destroyed = self._record_red_army_base_dissolve(attacker, target_owner, town) if is_red_base else False
        if not is_red_base:
            target_owner.organizations[town] -= 1
            if target_owner.organizations[town] <= 0:
                del target_owner.organizations[town]

        if not is_red_base:
            if target_owner is defender:
                self.log(f"{attacker.name} dissolved 1 organization from {defender.name} at {town}")
            else:
                self.log(f"{attacker.name} dissolved 1 shared organization via {defender.name} from {target_owner.name} at {town}")

        inner_towns = set(self._towns_for_region_alias("china"))
        if town in inner_towns and any(self._player_has_ability(target_owner, n) for n in {"殉道者", "青山里"}):
            self._draw_player_cards(target_owner, 1)
            self.log(f"{target_owner.name} triggered martyr-style ability and drew 1 card")
            self._track_event_progress('use_faction_ability', player=target_owner)

        return {
            "success": True,
            "actual_owner": target_owner.name,
            "shared_target": target_owner is not defender,
            "red_base_hit": is_red_base,
            "red_base_destroyed": red_base_destroyed,
        }

    def _hk_relocatable_base_towns(self):
        faction = self.faction_by_id.get('hong_kong', {})
        return [b.get('name') for b in (faction.get('bases') or []) if isinstance(b, dict) and b.get('type') == 'relocatable']

    def _open_hong_kong_base_relocation_window(self):
        self.hk_free_base_relocation = True
        self.log('香港抗暴之戰已結算：香港可於下一回合開始前免費遷移根據地（臺北/倫敦/卡加利/多倫多）')

    def _complete_hong_kong_relocation_turn_handoff(self):
        if not getattr(self, 'hk_relocation_blocks_turn_handoff', False):
            return
        self.hk_relocation_blocks_turn_handoff = False
        self._finish_end_turn_handoff()

    def relocate_hong_kong_base(self, player_id, to_town):
        """Use the one-time free forward-base window opened by 香港抗暴之戰."""
        pending_error = self._pending_board_action_error()
        if pending_error:
            return pending_error
        player = next((p for p in self.players if getattr(p, 'id', None) == player_id), None)
        if player is None:
            return {"error": "Player not found"}
        if getattr(player, 'faction_id', None) != 'hong_kong':
            return {"error": "Only Hong Kong can relocate its base"}
        targets = self._hk_relocatable_base_towns()
        if to_town not in targets:
            return {"error": f"根據地只能遷移至：{'、'.join(targets)}"}
        if to_town == player.base:
            return {"error": "Base is already there"}
        destination_entries = self._organization_entries_at(to_town)
        destination_has_own_organization = player.organizations.get(to_town, 0) > 0
        if destination_entries and not (
            destination_has_own_organization
            and all(owner is player for owner, _count in destination_entries)
        ):
            return {"error": "Cannot relocate base into occupied town"}
        free_window = bool(getattr(self, 'hk_free_base_relocation', False))
        if not free_window:
            return {"error": "香港抗暴之戰尚未完成結算，沒有免費遷移根據地的機會"}
        self.hk_free_base_relocation = False
        via = '香港抗暴之戰（免費）'
        old_base = player.base
        if not destination_has_own_organization:
            if old_base and player.organizations.get(old_base, 0) > 0:
                player.organizations[old_base] -= 1
                if player.organizations[old_base] <= 0:
                    del player.organizations[old_base]
            self._place_organization(player, to_town, require_supply=False, require_development=False, enforce_base_build_block=False)
        player.base = to_town
        self.log(f"{player.name} relocated base from {old_base} to {to_town} via {via}")
        self._complete_hong_kong_relocation_turn_handoff()
        return {"success": True, "from": old_base, "to": to_town, "free": free_window}

    def keep_hong_kong_base(self, player_id):
        pending_error = self._pending_board_action_error()
        if pending_error:
            return pending_error
        player = next((p for p in self.players if getattr(p, 'id', None) == player_id), None)
        if player is None:
            return {"error": "Player not found"}
        if getattr(player, 'faction_id', None) != 'hong_kong':
            return {"error": "Only Hong Kong can decide its base relocation"}
        if not getattr(self, 'hk_free_base_relocation', False):
            return {"error": "目前沒有免費遷移根據地的機會"}
        self.hk_free_base_relocation = False
        self.log(f"{player.name} chose to keep the Hong Kong base at {player.base}")
        self._complete_hong_kong_relocation_turn_handoff()
        return {"success": True, "kept": player.base}

    def _validate_organization_move(self, from_town, to_town, mode="road"):
        """Validate one organization move without mutating game state.

        This is the single legality source for both ``move_organization`` and the
        viewer-scoped map projection.  Keep every rule here so the browser never
        has to duplicate faction, occupancy, wall, route, supply, or base-anchor
        checks.
        """
        pending_error = self._pending_board_action_error(
            allowed_choice_keys={'card_build_organization'}
        )
        if pending_error:
            return pending_error
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
        inner_towns_for_wall = set(self._towns_for_region_alias('china'))
        wall_crossing = (from_town in inner_towns_for_wall) != (to_town in inner_towns_for_wall)
        legal_move = to_town in neighbors
        if mode == "rail" and not legal_move and not wall_crossing:
            legal_move = self._rail_reachable_within_three(player, from_town, to_town)
        # rules.md：翻牆需2次移動且僅移動1格——跨牆只能走直接相鄰連線
        if wall_crossing and to_town not in neighbors:
            legal_move = False
        # 赤鱲角機場（香港 special_rules，2026-07-11 使用者裁決 S5-2）：
        # 香港可花費 2 次遷移，將位於赤鱲角（地圖拼寫：赤臘角）的香港組織
        # 無視距離遷移到任何屬於香港發展空間的牆外城鎮。不可逆向操作。
        airport_move = (
            getattr(player, 'faction_id', None) == 'hong_kong'
            and origin_owner is player
            and from_town == '赤臘角'
            and to_town not in inner_towns_for_wall
            and self.can_faction_develop_in_town('hong_kong', to_town)
        )
        if not legal_move and airport_move:
            legal_move = True
        if not legal_move and not self._event_modifier_active('ignore_distance'):
            return {"error": f"No {mode} connection"}
        if self._town_has_physical_organization(to_town):
            return {"error": "Cannot move into occupied town"}
        if getattr(origin_owner, 'faction_id', None) == 'red_army' and not self.can_faction_develop_in_town('red_army', to_town):
            return {"error": "Red Army organization cannot leave Red Army development space"}
        # 2026-08-04 使用者裁決：「發展空間」（`can_faction_develop_in_town`）是建立組織
        # 專屬的限制，rules.md「組織遷移」一節（翻牆2次移動、鐵路3格、一般1格、可跨越己方
        # 不可跨越敵方）完全沒有提到目的地要屬於移動者陣營的發展空間；紅軍以外的玩家只要
        # 城鎮相鄰（或鐵路3格內）、目的地未被佔用、移動次數足夠，就應該可以把組織遷移過去，
        # 即使那座城鎮不是該陣營可以「建立」新組織的城鎮——建立與遷移是兩種不同動作，只有
        # 建立才受發展空間限制。紅軍根據地規則不同，紅軍組織仍受上面那條紅軍專屬檢查限制，
        # 不受本次放寬影響。原本這裡還有一條套用在所有陣營身上的發展空間檢查
        # （`目的城鎮不適用你的陣營，無法遷入`），已移除。
        # 移動共享組織時，組織會轉為移動者所有（總數 +1），需消耗自己的組織棋供應
        if origin_owner is not player and not self._has_org_supply(player):
            return {"error": f"組織棋已達上限（{self._org_supply_limit(player)}），無法接收共享組織"}

        # Movement points represent movement counts, not distance/cost budget.
        # Every legal organization move consumes one count; cards/effects grant counts.
        # 翻牆（牆內↔牆外）與赤鱲角機場移動花費 2 次遷移。
        movement_rules = self.map.get('movement_rules', {}) or {}
        move_cost = max(1, int(movement_rules.get('move_cost', 1) or 1))
        wall_crossing_cost = max(1, int(movement_rules.get('wall_crossing_cost', 2) or 2))
        cost = wall_crossing_cost if wall_crossing else (2 if airport_move and to_town not in neighbors else move_cost)
        if player.moves_left < cost:
            return {"error": "Not enough move points"}

        if from_town == origin_owner.base and origin_owner.organizations.get(from_town, 0) <= 1:
            return {"error": "Base anchor organization cannot move"}

        return {
            "success": True,
            "player": player,
            "origin_owner": origin_owner,
            "cost": cost,
            "wall_crossing": wall_crossing,
            "airport_move": airport_move,
        }

    def _legal_organization_moves(self):
        """Return current-player legal destinations grouped by origin and mode."""
        result = {}
        player = self.current_player()
        all_towns = self.map.get("towns", {})
        for from_town in self._organization_towns_for_player(player):
            modes = {"road": [], "rail": []}
            for mode in modes:
                for to_town in all_towns:
                    checked = self._validate_organization_move(from_town, to_town, mode)
                    if checked.get("success"):
                        modes[mode].append({"town": to_town, "cost": checked["cost"]})
            if modes["road"] or modes["rail"]:
                result[from_town] = modes
        return result

    def move_organization(self, from_town, to_town, mode="road"):
        checked = self._validate_organization_move(from_town, to_town, mode)
        if not checked.get("success"):
            return checked

        player = checked["player"]
        origin_owner = checked["origin_owner"]
        cost = checked["cost"]
        origin_owner.organizations[from_town] -= 1
        if origin_owner.organizations[from_town] <= 0:
            del origin_owner.organizations[from_town]

        self._place_organization(player, to_town, require_supply=False, require_development=False, enforce_base_build_block=False)
        player.moves_left -= cost
        self._track_event_progress('move_organization', player=player)
        if checked.get("airport_move") and to_town not in (self.map["towns"].get(from_town, {}).get(mode, []) or []):
            self.log(f"{player.name} triggered 赤鱲角機場 to move from {from_town} to {to_town}")
            self._track_event_progress('use_faction_ability', player=player)
        if origin_owner is player:
            self.log(f"{player.name} moved 1 organization from {from_town} to {to_town} via {mode}")
        else:
            self.log(f"{player.name} moved 1 shared organization from {origin_owner.name}:{from_town} to {to_town} via {mode}")
        return {"success": True}

    def _card_purchase_cost(self, card):
        return card_purchase_cost(self.structured_cards, self.support_taxonomy, card)

    def _effective_purchase_cost(self, player, card):
        cost = dict(self._card_purchase_cost(card) or {})
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

        cost_money = max(0, cost_money - self._armory_purchase_cost_reduction(player, card))
        return {'money': cost_money, 'propaganda': cost_propaganda}

    def _armory_purchase_cost_reduction(self, player, card):
        return armory_purchase_cost_reduction(self.map, card, getattr(player, 'organizations', {}) or {})

    def _purchase_payment_policy(self, player):
        return purchase_payment_policy(lambda name: self._player_has_ability(player, name))

    def _allocate_purchase_payments(self, player, cards, effective_costs=None):
        cards = list(cards or [])
        if effective_costs is None:
            effective_costs = [self._effective_purchase_cost(player, card) for card in cards]
        else:
            effective_costs = list(effective_costs)
        policy = self._purchase_payment_policy(player)
        return allocate_purchase_payments(player.resources, policy, cards, effective_costs)

    def _player_can_afford_purchase(self, player, card, effective_cost=None):
        cost = effective_cost if effective_cost is not None else self._effective_purchase_cost(player, card)
        return self._allocate_purchase_payments(player, [card], [cost])['success']

    def _purchase_payment_cost(self, player, card, effective_cost=None):
        cost = effective_cost if effective_cost is not None else self._effective_purchase_cost(player, card)
        return self._allocate_purchase_payments(player, [card], [cost])['payments'][0]

    def _copy_purchase_card(self, card):
        copied = Card(
            getattr(card, 'name', str(card)),
            getattr(card, 'card_type', None),
            dict(getattr(card, 'resources', {}) or {}),
            getattr(card, 'effect', None),
        )
        if hasattr(card, 'variant_index'):
            setattr(copied, 'variant_index', getattr(card, 'variant_index'))
        return copied

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

    def buy_cards(self, indices):
        # 行動階段內可自由交錯出牌與購買；TurnPhase.END 仍接受，因為現在只是
        # advance_turn_phase 內部的結算標記（香港根據地遷移等待窗口會停在該狀態）。
        if self.turn_phase not in (TurnPhase.ACTION, TurnPhase.END):
            return {"error": "Not in ACTION phase"}

        if not isinstance(indices, (list, tuple)) or not indices:
            return {"error": "No cards selected"}
        if any(isinstance(index, bool) or not isinstance(index, int) for index in indices):
            return {"error": "Invalid index"}
        if len(set(indices)) != len(indices):
            return {"error": "Duplicate purchase index"}

        player = self.current_player()
        static_count = len(self._static_purchase_cards())
        selected = []
        for index in indices:
            if index < 0 or index >= len(self.purchase_area):
                return {"error": "Invalid index"}
            card = self.purchase_area[index]
            if not card:
                return {"error": "No card in slot"}
            if self._player_is_nonviolent(player) and self._card_is_banned_for_player(player, card):
                return {"error": "非暴力：不能購買武裝類卡牌"}
            ok, err = self._can_player_gain_flag_card(player, card)
            if not ok:
                return {"error": err}

            is_static_purchase = index < static_count
            card_name = getattr(card, 'name', str(card))
            if is_static_purchase and int(self.static_purchase_supply.get(card_name, 0) or 0) <= 0:
                return {"error": "Static purchase card is out of supply"}

            original_cost = self._card_purchase_cost(card)
            effective_cost = self._effective_purchase_cost(player, card)
            selected.append({
                'index': index,
                'card': card,
                'card_name': card_name,
                'is_static': is_static_purchase,
                'original_cost': original_cost,
                'effective_cost': effective_cost,
            })

        allocation = self._allocate_purchase_payments(
            player,
            [item['card'] for item in selected],
            [item['effective_cost'] for item in selected],
        )
        if not allocation['success']:
            return {"error": "Not enough resources"}
        payment_total = allocation['payment']
        payment_ability_name = allocation['policy']['ability_name']
        for item, money_for_propaganda in zip(selected, allocation['substitution_money']):
            item['payment_ability_name'] = payment_ability_name if money_for_propaganda > 0 else None

        player.resources['money'] -= payment_total['money']
        player.resources['propaganda'] -= payment_total['propaganda']
        purchased_cards = [self._copy_purchase_card(item['card']) for item in selected]
        player.deck.discard(purchased_cards)
        self.turn_log.setdefault('purchased_cards_this_turn', []).extend(purchased_cards)

        for item in selected:
            if item['is_static']:
                card_name = item['card_name']
                self.static_purchase_supply[card_name] = int(self.static_purchase_supply.get(card_name, 0) or 0) - 1
        for item in sorted((entry for entry in selected if not entry['is_static']), key=lambda entry: entry['index'], reverse=True):
            self.purchase_area.pop(item['index'])

        pending_choice = False
        for item, purchased_card in zip(selected, purchased_cards):
            self.log(f"{player.name} bought {item['card_name']}")
            payment_ability_name = item.get('payment_ability_name')
            if payment_ability_name:
                self.log(f"{player.name} triggered {payment_ability_name} to pay propaganda with money")
                self._track_event_progress('use_faction_ability', player=player)
            event_result = self._track_event_purchase(purchased_card, original_cost=item['original_cost'], player=player)
            pending_choice = pending_choice or bool(isinstance(event_result, dict) and event_result.get('pending_choice'))

        result = {
            "success": True,
            "purchased_cards": [item['card_name'] for item in selected],
            "payment": payment_total,
        }
        if pending_choice:
            result['pending_choice'] = True
        return result

    def buy_card(self, index):
        return self.buy_cards([index])

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
            if self._can_player_build_in_town(builder, town):
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
        build_limit = int((effect or {}).get('builds_per_discard', 1) or 1) * len(red.hand)
        if build_limit <= 0:
            return {'type': (effect or {}).get('type'), 'status': 'red_has_no_hand_cards'}
        town_count = len(towns)
        if town_count <= 0:
            return {'type': (effect or {}).get('type'), 'status': 'no_valid_build_towns'}
        max_discard = min(len(red.hand), town_count)
        if max_discard <= 0:
            return {'type': (effect or {}).get('type'), 'status': 'no_valid_build_towns'}
        era_name = (era or {}).get('name', (era or {}).get('id', '時代關卡'))
        self._set_pending_multi_card_choice(
            red,
            'era_red_discard_to_build_near_target',
            list(red.hand),
            f"{era_name}：紅軍可棄掉任意張手牌，接著在目標組織 {int((effect or {}).get('max_steps', 1) or 1)} 格內免費建立同數量組織。",
            count=max_discard,
            min_count=1,
            source_name=era_name,
            context={
                'era_id': (era or {}).get('id'),
                'era_name': era_name,
                'effect': dict(effect or {}),
            },
        )
        return {'type': (effect or {}).get('type'), 'status': 'pending_discard_choice', 'player_id': red.id, 'town_count': len(towns), 'max_discard': max_discard}

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
        return active_era_effects(self.era_engine.get_active_era_details())

    def _era_purchase_cost_reduction(self, player, card):
        return era_purchase_cost_reduction(
            self._active_era_effects(),
            self._player_camp(player),
            getattr(player, 'faction_id', None),
            card,
        )

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
                if not self._can_dissolve_base_target(other, town)[0]:
                    continue
                targets.append({
                    'id': f'{getattr(other, "id", other.name)}::{town}',
                    'label': f'{other.name}｜{town}',
                    'player_id': getattr(other, 'id', None),
                    'town': town,
                })
        return targets

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
        return era_restricts_ignore_distance_build(
            self._active_era_effects(), self.faction_by_id, self.map, self.towns_by_ruler, player, target_town
        )

    def _era_notification_payload(self, era):
        return era_notification_payload(era)

    def _detect_era_triggers(self):
        """Scan for newly-qualifying eras and enqueue them for activation.

        This is the trigger-*detection* half of era handling. Normal turn flow calls
        it only after Red Army ends its turn. This gives Red Army its full opportunity
        to dissolve an organization and invalidate a condition reached by a non-red
        player earlier in the same numbered turn.

        Detection is deliberately separate from _continue_era_activation_queue():
        the queue continuation must keep running every turn / every choice
        resolution so an in-flight interactive era activation is not stalled,
        whereas detection is the part that must wait for Red Army's turn end.
        """
        if not hasattr(self, "era_engine"):
            return

        activated_ids = set(self.era_engine.get_activated_eras())
        queue = getattr(self, '_pending_era_activations', None)
        if queue is None:
            queue = []
            self._pending_era_activations = queue
        queued_ids = set(queue)

        for era in self.structured_eras:
            era_id = era.get("id")
            if era_id in activated_ids or era_id in queued_ids:
                continue

            trigger = era.get("trigger")
            if not trigger:
                continue

            if self._evaluate_era_trigger(trigger):
                queue.append(era_id)
                queued_ids.add(era_id)

    def _check_era_trigger(self):
        """Detect newly-qualifying eras, then drain the activation queue.

        Retained as the combined detect+continue entry point used by the
        `/test/*` scenario-setup endpoints and era validators/tests that force an
        immediate check. Normal turn flow does NOT call this per non-red player-turn:
        detection waits for Red Army's turn end while
        _continue_era_activation_queue keeps draining every turn.
        """
        if not hasattr(self, "era_engine"):
            return
        self._detect_era_triggers()
        return self._continue_era_activation_queue()

    def _era_activation_interactive_target(self, era):
        """Return the Player who would OWN an interactive pending_choice created by
        activating this era, or None when activation needs no interactive input.

        Only returns a player when activation would ACTUALLY create the choice — the
        same preconditions the start-flows guard on (target has hand cards / valid
        build towns / enough deck cards). When the choice would not be created, the
        era's non-interactive side-effects should still apply at the normal boundary,
        so we return None (no deferral).

        Used to defer an interactive era whose choice belongs to a player other than
        the current actor until it is actually that player's turn. Activating such an
        era at the round-wrap boundary while a different player leads the round
        strands a pending_choice the current player cannot resolve, hard-blocking
        their entire turn and deadlocking the game (playtest 回報：上海合作組織＋藏國
        騷亂 同輪觸發，非紅軍陣營回合結束後雙方卡住無法操作). Mirrors how a red-targeted
        auto event defers via `auto_pending` until Red Army's own turn.
        """
        effects = (era or {}).get('effects') or {}
        for effect in effects.values():
            etype = (effect or {}).get('type')
            if etype == 'red_discard_to_build_near_target':
                red = self._red_player()
                if red is None or not getattr(red, 'hand', None):
                    continue
                if not self._era_build_towns_near_target(red, effect):
                    continue
                if int((effect or {}).get('builds_per_discard', 1) or 1) * len(red.hand) <= 0:
                    continue
                return red
            if etype == 'inspect_deck_top_and_reorder':
                targets = self._era_effect_target_players(effect)
                if not targets:
                    continue
                player = targets[0]
                deck = getattr(player, 'deck', None)
                if deck is None:
                    continue
                look_count = int((effect or {}).get('look_count', 1) or 1)
                top_count = int((effect or {}).get('top_count', 1) or 1)
                if len(deck.draw_pile[-look_count:]) < top_count:
                    continue
                return player
        return None

    def _continue_era_activation_queue(self):
        """Activate qualifying eras serially, pausing for each choice chain.

        Record and dequeue each one-time activation immediately before applying its
        effects. This gives unexpected partial effect failures at-most-once semantics:
        continuing the queue cannot apply the same activation effect twice.

        An interactive era whose choice would be owned by a player who is NOT the
        current actor is *deferred* (left queued): activating it now would strand a
        pending_choice the current player cannot resolve, deadlocking their turn. It
        activates later, once its target becomes the current player — see the
        post-advance drain in _end_turn and _era_activation_interactive_target.
        """
        queue = getattr(self, '_pending_era_activations', None)
        if queue is None:
            queue = []
            self._pending_era_activations = queue
        if self.pending_choice:
            return {'success': True, 'pending_choice': True}

        while not self.pending_choice:
            activated_ids = set(self.era_engine.get_activated_eras())
            current = self.current_player()
            pick = None
            for index, era_id in enumerate(queue):
                if era_id in activated_ids:
                    pick = index
                    break
                era = self.era_engine.get_definition(era_id)
                if not era:
                    # Keep invalid data queued: do not mark or silently lose an
                    # activation whose effect cannot be found.
                    return {'error': f'Unknown queued era: {era_id}'}
                target = self._era_activation_interactive_target(era)
                if target is not None and current is not None and target.id != current.id:
                    # Interactive choice belongs to another player: defer to their turn.
                    continue
                pick = index
                break
            if pick is None:
                break

            era_id = queue[pick]
            if era_id in activated_ids:
                queue.pop(pick)
                continue
            if not self.era_engine.activate_era(era_id):
                return {'error': f'Could not activate queued era: {era_id}'}
            era = self.era_engine.get_definition(era_id)
            queue.pop(pick)
            activation_results = self._apply_era_activation_effects(era)
            self.era_notification = self._era_notification_payload(era)
            self.era_notification['runtime_effects'] = activation_results
            self.log(f"Era triggered: {era.get('name', era_id)}")

        return {
            'success': True,
            'pending_choice': bool(self.pending_choice),
            'queued': list(queue),
        }

    def _player_region_org_count(self, player, region):
        return player_region_org_count(self.map, self.towns_by_ruler, self.faction_by_id, self.players, player, region)

    def _player_requirement_org_count(self, player, requirement):
        return player_requirement_org_count(
            self.map, self.towns_by_ruler, self.faction_by_id, self.players, player, requirement
        )

    def _evaluate_era_trigger(self, trigger):
        return evaluate_era_trigger(self.map, self.towns_by_ruler, self.faction_by_id, self.players, trigger)

    # ---------- State ----------

    def _project_map_control(self):
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
        return town_control, shared_access

    def _project_era_state(self, viewer_player):
        """Returns (active_era_details enriched with notification text, my_era_stage,
        era_notification). my_era_stage is computed against the *raw* (pre-enrichment)
        active_era_details, matching the original inline ordering exactly."""
        active_era_details = self.era_engine.get_active_era_details() if self.era_engine else []
        my_era_stage = era_stage_for_player(
            self.structured_eras,
            self.faction_by_id,
            self.era_engine.get_activated_eras(),
            viewer_player,
            active_era_details,
        )
        # 前端「時代關卡達成」浮窗被縮小之後，任何玩家都要能再點右上角的釘選卡片重新叫出
        # 完整說明，因此每個生效中的時代都要附上達成條件／紅軍壓制／革命反撲／期限文字，
        # 而不是只有觸發當下那一個 era_notification 才有。
        active_era_details = [
            {**self._era_notification_payload(detail), **detail}
            for detail in active_era_details
        ]
        notification = None
        if self.era_notification:
            notification = dict(self.era_notification)
            active_match = next((e for e in active_era_details if e.get("id") == notification.get("id")), None)
            if active_match:
                notification = {**self._era_notification_payload(active_match), **notification}
                notification["remaining"] = active_match.get("remaining")
                notification["duration"] = active_match.get("duration")
        return active_era_details, my_era_stage, notification

    def _project_pending_choice(self, viewer_player_id, viewer_player):
        pending_choice = None
        if self.pending_choice:
            raw_pending_context = self.pending_choice.get('context')
            pending_context = dict(raw_pending_context) if isinstance(raw_pending_context, dict) else {}
            pending_effect_type = pending_context.get('effect_type')
            pending_is_build = (
                self.pending_choice.get('choice_key') in {'event_build_organization', 'era_red_build_near_target', 'card_build_organization'}
                or (
                    self.pending_choice.get('choice_key') == 'support_interaction'
                    and self.pending_choice.get('step') == 'town'
                    and pending_effect_type in {'interactive_build_anywhere_inner', 'interactive_build_near_inner'}
                )
            )
            # 統一各瓦解來源的 interaction_kind（2026-08-02 playtest 建議）：不論來自奧援卡
            # （北國/臺灣奧援等）、間諜卡瓦解互動、情報網、事件紅軍瓦解、時代加成瓦解或國安部，
            # 只要當前 pending choice 是「選擇一個組織來瓦解」，就統一標記，讓前端能一致地
            # 自動切換到戰略地圖並以 💀 標示合法目標，不必為每個 choice_key 各自硬編一次。
            # 排除 support_interaction 的 force_discard_near（同樣 step=='target' 但選的是玩家
            # 手牌目標，不是要瓦解的組織）。
            pending_is_dissolve = (
                self.pending_choice.get('choice_key') in {
                    'intel_network_dissolve_target',
                    'event_red_dissolve',
                    'era_red_bonus_dissolve_target',
                    'red_army_state_security_target',
                }
                or (
                    self.pending_choice.get('choice_key') in {'support_interaction', 'card_dissolve_interaction'}
                    and self.pending_choice.get('step') == 'target'
                    and pending_effect_type in {
                        'interactive_dissolve_many_near',
                        'interactive_dissolve_and_build',
                        'interactive_dissolve_self_and_enemy',
                    }
                )
            )
            pending_remaining_builds = self.pending_choice.get('remaining_builds')
            if self.pending_choice.get('choice_key') == 'card_build_organization':
                pending_remaining_builds = self._remaining_card_build_entitlements()
            elif pending_is_build and pending_remaining_builds is None:
                pending_remaining_builds = int((pending_context.get('effect_payload') or {}).get('count', 1) or 1)
            pending_is_reaction = self.pending_choice.get('type') == 'reaction_choice'
            pending_is_for_viewer = viewer_player_id is None or self.pending_choice.get('player_id') == viewer_player_id
            pending_cards = self.pending_choice.get('cards') or []
            if pending_is_reaction and not pending_is_for_viewer:
                serialized_pending_cards = []
                pending_prompt = f"{self.pending_choice.get('acting_player_name', '玩家')} 打出 {self.pending_choice.get('played_card_name', '卡牌')}。等待對方是否取消。"
                pending_source_name = '等待反應'
            else:
                serialized_pending_cards = [
                    dict(card) if isinstance(card, dict) and 'name' in card and 'card' not in card else {
                        'name': getattr(card.get('card'), 'name', str(card.get('card'))),
                        'zone': card.get('zone'),
                        'zone_label': card.get('zone_label'),
                    } if isinstance(card, dict) else getattr(card, 'name', str(card))
                    for card in pending_cards
                ]
                pending_prompt = self.pending_choice.get('prompt')
                pending_source_name = self.pending_choice.get('source_name')
            # 連續多次建立的候選城鎮清單即時投影（見 `_live_pending_town_choices()`）——不要
            # 相信 `self.pending_choice['towns']` 裡儲存的舊清單，每次序列化都用該效果的
            # 擁有者（不是目前這次 state() 呼叫的 viewer）當下的組織位置重新投影一次。
            pending_choice_owner = next(
                (p for p in self.players if getattr(p, 'id', None) == self.pending_choice.get('player_id')),
                None,
            )
            pending_live_towns = self._live_pending_town_choices(pending_choice_owner, self.pending_choice) if pending_choice_owner else None
            if pending_live_towns is not None:
                self.pending_choice['towns'] = pending_live_towns
            pending_choice = {
                'type': self.pending_choice.get('type'),
                'choice_key': self.pending_choice.get('choice_key'),
                'interaction_kind': (
                    'build_organization' if pending_is_build
                    else 'dissolve_organization' if pending_is_dissolve
                    else None
                ),
                'remaining_builds': pending_remaining_builds,
                'queueable_card_names': [
                    getattr(card, 'name', str(card))
                    for card in (getattr(viewer_player, 'hand', []) or [])
                    if (
                        self._choice_is_card_map_interaction(self.pending_choice)
                        and self.pending_choice.get('player_id') == getattr(viewer_player, 'id', None)
                        and self._card_can_queue_map_action(viewer_player, card)
                    )
                ],
                'cancellable': bool(self.pending_choice.get('cancellable')) or self.pending_choice.get('choice_key') in CANCELLABLE_CHOICE_KEYS,
                'player_id': self.pending_choice.get('player_id'),
                'player_name': self.pending_choice.get('player_name'),
                'prompt': pending_prompt,
                'source_name': pending_source_name,
                'count': self.pending_choice.get('count'),
                'min_count': self.pending_choice.get('min_count'),
                'mode': self.pending_choice.get('mode'),
                'acting_player_id': self.pending_choice.get('acting_player_id'),
                'acting_player_name': self.pending_choice.get('acting_player_name'),
                'played_card_name': self.pending_choice.get('played_card_name'),
                'region': self.pending_choice.get('region'),
                'free': self.pending_choice.get('free'),
                'ignore_distance': self.pending_choice.get('ignore_distance'),
                'cards': serialized_pending_cards,
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
        return pending_choice

    def _project_purchase_area(self, current_player):
        purchase_area_costs = [
            self._effective_purchase_cost(current_player, card)
            for card in self.purchase_area
        ]
        purchase_area_payments = [
            self._purchase_payment_cost(current_player, card, purchase_area_costs[idx])
            for idx, card in enumerate(self.purchase_area)
        ]
        purchase_area_affordable = [
            self._player_can_afford_purchase(current_player, card, purchase_area_costs[idx])
            for idx, card in enumerate(self.purchase_area)
        ]
        return purchase_area_costs, purchase_area_payments, purchase_area_affordable

    def _project_players(self, viewer_player_id):
        return [
            {
                "id": p.id,
                "name": p.name,
                "faction": p.faction_id,
                "base": p.base,
                "resources": p.resources,
                "moves_left": p.moves_left,
                "hand": [getattr(card, 'name', str(card)) for card in p.hand] if (viewer_player_id is None or p.id == viewer_player_id) else ['未知手牌' for _ in p.hand],
                "hand_variants": [self._support_card_variant_info(card) for card in p.hand] if (viewer_player_id is None or p.id == viewer_player_id) else [None for _ in p.hand],
                "hand_action_legality": [self._card_action_legality(p, card) for card in p.hand] if (viewer_player_id is None or p.id == viewer_player_id) else [None for _ in p.hand],
                "deck_count": len(p.deck.draw_pile) if p.deck else 0,
                "discard_count": len(p.deck.discard_pile) if p.deck else 0,
                "discard_pile": [getattr(card, 'name', str(card)) for card in p.deck.discard_pile] if p.deck else [],
                "discard_variants": [self._support_card_variant_info(card) for card in p.deck.discard_pile] if p.deck else [],
                "organization_counts": self._player_organization_scope_counts(p),
                "orgs": p.organizations
            }
            for p in self.players
        ]

    def state(self, viewer_player_id=None):
        town_control, shared_access = self._project_map_control()
        viewer_player = next(
            (player for player in self.players if player.id == viewer_player_id),
            None,
        ) if viewer_player_id is not None else None
        active_era_details, my_era_stage, notification = self._project_era_state(viewer_player)
        pending_choice = self._project_pending_choice(viewer_player_id, viewer_player)
        current_player = self.current_player()
        legal_organization_moves = (
            self._legal_organization_moves()
            if viewer_player is current_player
            else {}
        )
        purchase_area_costs, purchase_area_payments, purchase_area_affordable = self._project_purchase_area(current_player)

        return {
            "turn": self.turn,
            "game_phase": self.game_phase,
            "turn_phase": self.turn_phase,
            "winner": self.winner,
            "co_winners": list(getattr(self, 'co_winners', []) or []),
            "hk_free_base_relocation": bool(getattr(self, 'hk_free_base_relocation', False)),
            "current_player": self.current_player().name,
            "active_eras": self.era_engine.get_active_eras() if self.era_engine else [],
            "active_era_details": active_era_details,
            "my_era_stage": my_era_stage,
            "era_notification": notification,
            "current_event": self._event_display_payload(),
            "event_deck_count": len(self.event_deck.draw_pile) if getattr(self, 'event_deck', None) else 0,
            "red_army_action_count": self.turn_log.get('red_army_action_count', 0),
            "red_army_action_limit": self._red_army_action_limit(),
            "red_army_base_build_blocks": list(self.turn_log.get('red_army_base_build_blocks', []) or []),
            "pending_topdeck_uses": self.turn_log.get('pending_topdeck_uses', 0),
            "topdeck_candidates_count": len(self._available_purchased_cards_for_topdeck(self.current_player())),
            "event_discard_count": len(self.event_deck.discard_pile) if getattr(self, 'event_deck', None) else 0,
            "event_modifiers": list(getattr(self, 'event_modifiers', []) or []),
            "market_mode": self.market_mode,
            "pending_base_choices": self.pending_base_choices,
            "pending_choice": pending_choice,
            "faction_action_used": bool(self.turn_log.get('faction_action_used')),
            "action_log": self._project_action_log(viewer_player_id),
            "purchase_area": [getattr(card, 'name', str(card)) for card in self.purchase_area],
            "purchase_area_variants": [self._support_card_variant_info(card) for card in self.purchase_area],
            "purchase_area_costs": purchase_area_costs,
            "purchase_area_payments": purchase_area_payments,
            "purchase_area_affordable": purchase_area_affordable,
            "purchase_payment_policy": self._purchase_payment_policy(current_player),
            "static_purchase_supply": dict(getattr(self, 'static_purchase_supply', {})),
            "map": {
                "towns": town_control,
                "shared_access": shared_access,
                "legal_organization_moves": legal_organization_moves,
            },
            "players": self._project_players(viewer_player_id),
        }
