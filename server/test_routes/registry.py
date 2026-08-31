"""Aggregates every /test/* route module and registers them onto the FastAPI app.

Keeps main.py free of the per-route import and GameSetupRuntime/manager/
broadcaster wiring boilerplate: main.py calls register_test_routes(...)
once at startup and re-exports the bound test_setup_* callables it gets
back (scripts/tests/*_test_route.py call several of these directly via
main.test_setup_x for backward compatibility).
"""

from types import SimpleNamespace
from typing import Any, Callable, Union

from fastapi import APIRouter, FastAPI

from server.test_routes.bait_exhaustion_ui import BaitExhaustionUiTestRoutes
from server.test_routes.belt_road_red_turn import BeltRoadRedTurnTestRoutes
from server.test_routes.build_queue import BuildQueueRuntime, BuildQueueTestRoutes
from server.test_routes.build_view_persistence import BuildViewPersistenceTestRoutes
from server.test_routes.business_network_transport import BusinessNetworkTransportTestRoutes
from server.test_routes.card_scenario import CardScenarioTestRoutes
from server.test_routes.ccdi_choice import CcdiChoiceTestRoutes
from server.test_routes.destroyed_red_base_marker import DestroyedRedBaseMarkerTestRoutes
from server.test_routes.discard_reshuffle import DiscardReshuffleTestRoutes
from server.test_routes.discard_topdeck_choice import DiscardTopdeckChoiceTestRoutes
from server.test_routes.draw_privacy import DrawPrivacyTestRoutes
from server.test_routes.elite_defection_discard import EliteDefectionDiscardTestRoutes
from server.test_routes.elite_defection_event import EliteDefectionEventTestRoutes
from server.test_routes.end_turn_topdeck import EndTurnTopdeckTestRoutes
from server.test_routes.enemy_occupancy import EnemyOccupancyTestRoutes
from server.test_routes.era_event_layout import EraEventLayoutTestRoutes
from server.test_routes.era_notification import EraNotificationTestRoutes
from server.test_routes.era_restrict_ignore_distance import (
    EraRestrictIgnoreDistanceTestRoutes,
)
from server.test_routes.event_card import EventCardTestRoutes
from server.test_routes.expand_results import ExpandResultsTestRoutes
from server.test_routes.faction_action_used import FactionActionUsedTestRoutes
from server.test_routes.force_base_selection import ForceBaseSelectionTestRoutes
from server.test_routes.hand_preview import HandPreviewRuntime, HandPreviewTestRoutes
from server.test_routes.hong_kong_era_red_discard import HongKongEraRedDiscardTestRoutes
from server.test_routes.hong_kong_safehouse import HongKongSafehouseTestRoutes
from server.test_routes.hu_taiwan_shared import HuTaiwanSharedTestRoutes
from server.test_routes.india_support_purchase import IndiaSupportPurchaseTestRoutes
from server.test_routes.inside_wall import InsideWallTestRoutes
from server.test_routes.intel_network import IntelNetworkTestRoutes
from server.test_routes.intel_network_reaction import IntelNetworkReactionTestRoutes
from server.test_routes.manchuria_era_reorder import ManchuriaEraReorderTestRoutes
from server.test_routes.move_confirmation import MoveConfirmationTestRoutes
from server.test_routes.negotiation import NegotiationTestRoutes
from server.test_routes.npc_inner_build import NpcInnerBuildTestRoutes
from server.test_routes.npc_red_dissolve import NpcRedDissolveTestRoutes
from server.test_routes.peer_choice_notice import PeerChoiceNoticeTestRoutes
from server.test_routes.pending_choice_board_guard import PendingChoiceBoardGuardTestRoutes
from server.test_routes.planning_lobby_ui import PlanningLobbyUiTestRoutes
from server.test_routes.press_advantage import PressAdvantageTestRoutes
from server.test_routes.purchase_deck_ui import PurchaseDeckUiTestRoutes
from server.test_routes.recruit_talent import RecruitTalentTestRoutes
from server.test_routes.red_army_abilities import RedArmyAbilitiesTestRoutes
from server.test_routes.red_support import RedSupportTestRoutes
from server.test_routes.remove_to_purchase import RemoveToPurchaseTestRoutes
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.safehouse_range import SafehouseRangeTestRoutes
from server.test_routes.scope_audit import ScopeAuditTestRoutes
from server.test_routes.set_hand import SetHandTestRoutes
from server.test_routes.shared_dissolve import SharedDissolveTestRoutes
from server.test_routes.show_strength_choice import ShowStrengthChoiceTestRoutes
from server.test_routes.spy import SpyTestRoutes
from server.test_routes.support import SupportTestRoutes
from server.test_routes.support_card_play import SupportCardPlayTestRoutes
from server.test_routes.taiwan_support import TaiwanSupportTestRoutes
from server.test_routes.tibet_era_red_build import TibetEraRedBuildTestRoutes
from server.test_routes.trade_war_event import TradeWarEventTestRoutes
from server.test_routes.trash_choice_ui import TrashChoiceUiTestRoutes
from server.test_routes.underground_party import UndergroundPartyTestRoutes
from server.test_routes.urumqi_event import UrumqiEventTestRoutes
from server.test_routes.uyghur_era_red_dissolve import UyghurEraRedDissolveTestRoutes
from server.test_routes.victory import VictoryTestRoutes

def register_test_routes(
    *,
    app: Union[FastAPI, APIRouter],
    runtime_provider: Callable[[], GameSetupRuntime],
    manager_provider: Callable[[], Any],
    broadcaster_provider: Callable[[], Any],
) -> SimpleNamespace:

    def _build_queue_runtime():
        rt = runtime_provider()
        return BuildQueueRuntime(
            manager=rt.manager,
            lobby=rt.lobby,
            lobby_hosts=rt.lobby_hosts,
            lobby_factions=rt.lobby_factions,
            lobby_bases=rt.lobby_bases,
        )

    def _hand_preview_runtime():
        rt = runtime_provider()
        return HandPreviewRuntime(
            manager=rt.manager,
            lobby=rt.lobby,
            lobby_hosts=rt.lobby_hosts,
            lobby_factions=rt.lobby_factions,
            lobby_bases=rt.lobby_bases,
        )

    _set_hand_test_routes = SetHandTestRoutes(manager_provider)
    app.include_router(_set_hand_test_routes.router)
    test_set_hand = _set_hand_test_routes.test_set_hand


    _build_view_persistence_test_routes = BuildViewPersistenceTestRoutes(
        manager_provider,
        broadcaster_provider,
    )
    app.include_router(_build_view_persistence_test_routes.router)
    test_setup_build_view_persistence_proof = (
        _build_view_persistence_test_routes.test_setup_build_view_persistence_proof
    )


    _build_queue_test_routes = BuildQueueTestRoutes(
        _build_queue_runtime
    )
    app.include_router(_build_queue_test_routes.router)
    test_setup_build_queue_proof = (
        _build_queue_test_routes.test_setup_build_queue_proof
    )


    _negotiation_test_routes = NegotiationTestRoutes(
        runtime_provider
    )
    app.include_router(_negotiation_test_routes.router)
    test_setup_negotiation_proof = (
        _negotiation_test_routes.test_setup_negotiation_proof
    )


    _scope_audit_test_routes = ScopeAuditTestRoutes(
        runtime_provider
    )
    app.include_router(_scope_audit_test_routes.router)
    test_setup_scope_audit_proof = (
        _scope_audit_test_routes.test_setup_scope_audit_proof
    )


    _inside_wall_test_routes = InsideWallTestRoutes(
        runtime_provider
    )
    app.include_router(_inside_wall_test_routes.router)
    test_setup_inside_wall_proof = (
        _inside_wall_test_routes.test_setup_inside_wall_proof
    )


    _card_scenario_test_routes = CardScenarioTestRoutes(manager_provider)
    app.include_router(_card_scenario_test_routes.router)
    test_setup_card_scenario = _card_scenario_test_routes.test_setup_card_scenario


    _force_base_selection_test_routes = ForceBaseSelectionTestRoutes(
        runtime_provider
    )
    app.include_router(_force_base_selection_test_routes.router)
    test_force_base_selection = (
        _force_base_selection_test_routes.test_force_base_selection
    )


    _intel_network_test_routes = IntelNetworkTestRoutes(
        runtime_provider
    )
    app.include_router(_intel_network_test_routes.router)
    test_setup_intel_network_proof = (
        _intel_network_test_routes.test_setup_intel_network_proof
    )


    _press_advantage_test_routes = PressAdvantageTestRoutes(
        runtime_provider
    )
    app.include_router(_press_advantage_test_routes.router)
    test_setup_press_advantage_proof = (
        _press_advantage_test_routes.test_setup_press_advantage_proof
    )


    _expand_results_test_routes = ExpandResultsTestRoutes(
        runtime_provider
    )
    app.include_router(_expand_results_test_routes.router)
    test_setup_expand_results_proof = (
        _expand_results_test_routes.test_setup_expand_results_proof
    )


    _intel_network_reaction_test_routes = IntelNetworkReactionTestRoutes(
        runtime_provider
    )
    app.include_router(_intel_network_reaction_test_routes.router)
    test_setup_intel_network_cancel_reaction_proof = (
        _intel_network_reaction_test_routes.test_setup_intel_network_cancel_reaction_proof
    )
    test_resolve_intel_network_cancel_reaction_proof = (
        _intel_network_reaction_test_routes.test_resolve_intel_network_cancel_reaction_proof
    )


    _hong_kong_safehouse_test_routes = HongKongSafehouseTestRoutes(
        runtime_provider
    )
    app.include_router(_hong_kong_safehouse_test_routes.router)
    test_setup_hong_kong_safehouse = (
        _hong_kong_safehouse_test_routes.test_setup_hong_kong_safehouse
    )


    _pending_choice_board_guard_test_routes = PendingChoiceBoardGuardTestRoutes(
        runtime_provider
    )
    app.include_router(_pending_choice_board_guard_test_routes.router)
    test_setup_pending_choice_board_guard = (
        _pending_choice_board_guard_test_routes.test_setup_pending_choice_board_guard
    )


    _enemy_occupancy_test_routes = EnemyOccupancyTestRoutes(
        runtime_provider
    )
    app.include_router(_enemy_occupancy_test_routes.router)
    test_setup_enemy_occupancy_proof = (
        _enemy_occupancy_test_routes.test_setup_enemy_occupancy_proof
    )


    _move_confirmation_test_routes = MoveConfirmationTestRoutes(
        runtime_provider
    )
    app.include_router(_move_confirmation_test_routes.router)
    test_setup_move_confirmation_proof = (
        _move_confirmation_test_routes.test_setup_move_confirmation_proof
    )


    _destroyed_red_base_marker_test_routes = DestroyedRedBaseMarkerTestRoutes(
        runtime_provider
    )
    app.include_router(_destroyed_red_base_marker_test_routes.router)
    test_setup_destroyed_red_base_marker_proof = (
        _destroyed_red_base_marker_test_routes.test_setup_destroyed_red_base_marker_proof
    )


    _hu_taiwan_shared_test_routes = HuTaiwanSharedTestRoutes(
        runtime_provider
    )
    app.include_router(_hu_taiwan_shared_test_routes.router)
    test_setup_hu_taiwan_shared = (
        _hu_taiwan_shared_test_routes.test_setup_hu_taiwan_shared
    )


    _shared_dissolve_test_routes = SharedDissolveTestRoutes(
        runtime_provider
    )
    app.include_router(_shared_dissolve_test_routes.router)
    test_setup_shared_dissolve = (
        _shared_dissolve_test_routes.test_setup_shared_dissolve
    )


    _india_support_purchase_test_routes = IndiaSupportPurchaseTestRoutes(
        runtime_provider
    )
    app.include_router(_india_support_purchase_test_routes.router)
    test_setup_india_support_purchase = (
        _india_support_purchase_test_routes.test_setup_india_support_purchase
    )


    _remove_to_purchase_test_routes = RemoveToPurchaseTestRoutes(
        runtime_provider
    )
    app.include_router(_remove_to_purchase_test_routes.router)
    test_setup_remove_to_purchase = (
        _remove_to_purchase_test_routes.test_setup_remove_to_purchase
    )


    _underground_party_test_routes = UndergroundPartyTestRoutes(
        runtime_provider
    )
    app.include_router(_underground_party_test_routes.router)
    test_setup_underground_party = (
        _underground_party_test_routes.test_setup_underground_party
    )


    _recruit_talent_test_routes = RecruitTalentTestRoutes(
        runtime_provider
    )
    app.include_router(_recruit_talent_test_routes.router)
    test_setup_recruit_talent_proof = (
        _recruit_talent_test_routes.test_setup_recruit_talent_proof
    )


    _support_card_play_test_routes = SupportCardPlayTestRoutes(
        runtime_provider
    )
    app.include_router(_support_card_play_test_routes.router)
    test_setup_support_card_play = (
        _support_card_play_test_routes.test_setup_support_card_play
    )


    _purchase_deck_ui_test_routes = PurchaseDeckUiTestRoutes(
        runtime_provider
    )
    app.include_router(_purchase_deck_ui_test_routes.router)
    test_setup_purchase_deck_ui = (
        _purchase_deck_ui_test_routes.test_setup_purchase_deck_ui
    )


    _hand_preview_test_routes = HandPreviewTestRoutes(
        _hand_preview_runtime
    )
    app.include_router(_hand_preview_test_routes.router)
    test_setup_hand_preview = _hand_preview_test_routes.test_setup_hand_preview


    _end_turn_topdeck_test_routes = EndTurnTopdeckTestRoutes(
        runtime_provider
    )
    app.include_router(_end_turn_topdeck_test_routes.router)
    test_setup_end_turn_topdeck_proof = (
        _end_turn_topdeck_test_routes.test_setup_end_turn_topdeck_proof
    )


    _business_network_transport_test_routes = BusinessNetworkTransportTestRoutes(
        runtime_provider
    )
    app.include_router(_business_network_transport_test_routes.router)
    test_setup_business_network_transport_proof = (
        _business_network_transport_test_routes.test_setup_business_network_transport_proof
    )


    _planning_lobby_ui_test_routes = PlanningLobbyUiTestRoutes(
        runtime_provider
    )
    app.include_router(_planning_lobby_ui_test_routes.router)
    test_setup_planning_lobby_ui = (
        _planning_lobby_ui_test_routes.test_setup_planning_lobby_ui
    )


    _trash_choice_ui_test_routes = TrashChoiceUiTestRoutes(
        runtime_provider
    )
    app.include_router(_trash_choice_ui_test_routes.router)
    test_setup_trash_choice_ui = (
        _trash_choice_ui_test_routes.test_setup_trash_choice_ui
    )


    _red_support_test_routes = RedSupportTestRoutes(
        runtime_provider
    )
    app.include_router(_red_support_test_routes.router)
    test_setup_red_support_proof = (
        _red_support_test_routes.test_setup_red_support_proof
    )


    _red_army_abilities_test_routes = RedArmyAbilitiesTestRoutes(
        runtime_provider
    )
    app.include_router(_red_army_abilities_test_routes.router)
    test_setup_red_army_abilities_proof = (
        _red_army_abilities_test_routes.test_setup_red_army_abilities_proof
    )


    _spy_test_routes = SpyTestRoutes(
        runtime_provider
    )
    app.include_router(_spy_test_routes.router)
    test_setup_spy_proof = _spy_test_routes.test_setup_spy_proof


    _victory_test_routes = VictoryTestRoutes(
        runtime_provider
    )
    app.include_router(_victory_test_routes.router)
    test_setup_victory_proof = _victory_test_routes.test_setup_victory_proof


    _draw_privacy_test_routes = DrawPrivacyTestRoutes(
        runtime_provider,
        broadcaster_provider,
    )
    app.include_router(_draw_privacy_test_routes.router)
    test_setup_draw_privacy_proof = (
        _draw_privacy_test_routes.test_setup_draw_privacy_proof
    )
    test_trigger_draw_privacy_proof = (
        _draw_privacy_test_routes.test_trigger_draw_privacy_proof
    )


    _elite_defection_discard_test_routes = EliteDefectionDiscardTestRoutes(
        runtime_provider
    )
    app.include_router(_elite_defection_discard_test_routes.router)
    test_setup_elite_defection_discard_proof = (
        _elite_defection_discard_test_routes.test_setup_elite_defection_discard_proof
    )


    _discard_reshuffle_test_routes = DiscardReshuffleTestRoutes(
        runtime_provider
    )
    app.include_router(_discard_reshuffle_test_routes.router)
    test_setup_discard_reshuffle_proof = (
        _discard_reshuffle_test_routes.test_setup_discard_reshuffle_proof
    )


    _support_test_routes = SupportTestRoutes(
        runtime_provider
    )
    app.include_router(_support_test_routes.router)
    test_setup_support_proof = _support_test_routes.test_setup_support_proof


    _taiwan_support_test_routes = TaiwanSupportTestRoutes(test_setup_support_proof)
    app.include_router(_taiwan_support_test_routes.router)
    test_setup_taiwan_support_proof = (
        _taiwan_support_test_routes.test_setup_taiwan_support_proof
    )


    _bait_exhaustion_ui_test_routes = BaitExhaustionUiTestRoutes(
        runtime_provider
    )
    app.include_router(_bait_exhaustion_ui_test_routes.router)
    test_setup_bait_exhaustion_ui = (
        _bait_exhaustion_ui_test_routes.test_setup_bait_exhaustion_ui
    )


    _manchuria_era_reorder_test_routes = ManchuriaEraReorderTestRoutes(
        runtime_provider
    )
    app.include_router(_manchuria_era_reorder_test_routes.router)
    test_setup_manchuria_era_reorder_proof = (
        _manchuria_era_reorder_test_routes.test_setup_manchuria_era_reorder_proof
    )


    _event_card_test_routes = EventCardTestRoutes(
        runtime_provider
    )
    app.include_router(_event_card_test_routes.router)
    test_setup_event_card_proof = _event_card_test_routes.test_setup_event_card_proof


    _npc_red_dissolve_test_routes = NpcRedDissolveTestRoutes(
        runtime_provider
    )
    app.include_router(_npc_red_dissolve_test_routes.router)
    test_setup_national_people_congress_red_dissolve_proof = (
        _npc_red_dissolve_test_routes.test_setup_national_people_congress_red_dissolve_proof
    )


    _npc_inner_build_test_routes = NpcInnerBuildTestRoutes(
        runtime_provider
    )
    app.include_router(_npc_inner_build_test_routes.router)
    test_setup_national_people_congress_inner_build_proof = (
        _npc_inner_build_test_routes.test_setup_national_people_congress_inner_build_proof
    )


    _trade_war_event_test_routes = TradeWarEventTestRoutes(
        runtime_provider
    )
    app.include_router(_trade_war_event_test_routes.router)
    test_setup_trade_war_event_proof = (
        _trade_war_event_test_routes.test_setup_trade_war_event_proof
    )


    _discard_topdeck_choice_test_routes = DiscardTopdeckChoiceTestRoutes(
        runtime_provider
    )
    app.include_router(_discard_topdeck_choice_test_routes.router)
    test_setup_discard_topdeck_choice = (
        _discard_topdeck_choice_test_routes.test_setup_discard_topdeck_choice
    )


    _ccdi_choice_test_routes = CcdiChoiceTestRoutes(
        runtime_provider
    )
    app.include_router(_ccdi_choice_test_routes.router)
    test_setup_ccdi_choice = _ccdi_choice_test_routes.test_setup_ccdi_choice


    _elite_defection_event_test_routes = EliteDefectionEventTestRoutes(
        runtime_provider
    )
    app.include_router(_elite_defection_event_test_routes.router)
    test_setup_elite_defection_event_proof = (
        _elite_defection_event_test_routes.test_setup_elite_defection_event_proof
    )


    _belt_road_red_turn_test_routes = BeltRoadRedTurnTestRoutes(
        runtime_provider,
        broadcaster_provider,
    )
    app.include_router(_belt_road_red_turn_test_routes.router)
    test_setup_belt_road_red_turn_proof = (
        _belt_road_red_turn_test_routes.test_setup_belt_road_red_turn_proof
    )


    _tibet_era_red_build_test_routes = TibetEraRedBuildTestRoutes(
        runtime_provider
    )
    app.include_router(_tibet_era_red_build_test_routes.router)
    test_setup_tibet_era_red_build_proof = (
        _tibet_era_red_build_test_routes.test_setup_tibet_era_red_build_proof
    )


    _era_event_layout_test_routes = EraEventLayoutTestRoutes(manager_provider)
    app.include_router(_era_event_layout_test_routes.router)
    test_setup_era_event_layout_proof = (
        _era_event_layout_test_routes.test_setup_era_event_layout_proof
    )


    _era_notification_test_routes = EraNotificationTestRoutes(
        runtime_provider
    )
    app.include_router(_era_notification_test_routes.router)
    test_setup_era_notification_proof = (
        _era_notification_test_routes.test_setup_era_notification_proof
    )


    _hong_kong_era_red_discard_test_routes = HongKongEraRedDiscardTestRoutes(
        runtime_provider
    )
    app.include_router(_hong_kong_era_red_discard_test_routes.router)
    test_setup_hong_kong_era_red_discard_proof = (
        _hong_kong_era_red_discard_test_routes.test_setup_hong_kong_era_red_discard_proof
    )


    _uyghur_era_red_dissolve_test_routes = UyghurEraRedDissolveTestRoutes(
        runtime_provider
    )
    app.include_router(_uyghur_era_red_dissolve_test_routes.router)
    test_setup_uyghur_era_red_dissolve_proof = (
        _uyghur_era_red_dissolve_test_routes.test_setup_uyghur_era_red_dissolve_proof
    )


    _urumqi_event_test_routes = UrumqiEventTestRoutes(
        runtime_provider
    )
    app.include_router(_urumqi_event_test_routes.router)
    test_setup_urumqi_event_proof = (
        _urumqi_event_test_routes.test_setup_urumqi_event_proof
    )


    _faction_action_used_test_routes = FactionActionUsedTestRoutes(
        runtime_provider
    )
    app.include_router(_faction_action_used_test_routes.router)
    test_setup_faction_action_used_proof = (
        _faction_action_used_test_routes.test_setup_faction_action_used_proof
    )


    _show_strength_choice_test_routes = ShowStrengthChoiceTestRoutes(
        runtime_provider
    )
    app.include_router(_show_strength_choice_test_routes.router)
    test_setup_show_strength_choice_proof = (
        _show_strength_choice_test_routes.test_setup_show_strength_choice_proof
    )


    _peer_choice_notice_test_routes = PeerChoiceNoticeTestRoutes(
        runtime_provider
    )
    app.include_router(_peer_choice_notice_test_routes.router)
    test_setup_peer_choice_notice_proof = (
        _peer_choice_notice_test_routes.test_setup_peer_choice_notice_proof
    )


    _safehouse_range_test_routes = SafehouseRangeTestRoutes(
        runtime_provider
    )
    app.include_router(_safehouse_range_test_routes.router)
    test_setup_safehouse_range_proof = (
        _safehouse_range_test_routes.test_setup_safehouse_range_proof
    )


    _era_restrict_ignore_distance_test_routes = EraRestrictIgnoreDistanceTestRoutes(
        runtime_provider
    )
    app.include_router(_era_restrict_ignore_distance_test_routes.router)
    test_setup_era_restrict_ignore_distance_proof = (
        _era_restrict_ignore_distance_test_routes.test_setup_era_restrict_ignore_distance_proof
    )


    return SimpleNamespace(
        test_set_hand=test_set_hand,
        test_setup_build_view_persistence_proof=test_setup_build_view_persistence_proof,
        test_setup_build_queue_proof=test_setup_build_queue_proof,
        test_setup_negotiation_proof=test_setup_negotiation_proof,
        test_setup_scope_audit_proof=test_setup_scope_audit_proof,
        test_setup_inside_wall_proof=test_setup_inside_wall_proof,
        test_setup_card_scenario=test_setup_card_scenario,
        test_force_base_selection=test_force_base_selection,
        test_setup_intel_network_proof=test_setup_intel_network_proof,
        test_setup_press_advantage_proof=test_setup_press_advantage_proof,
        test_setup_expand_results_proof=test_setup_expand_results_proof,
        test_setup_intel_network_cancel_reaction_proof=test_setup_intel_network_cancel_reaction_proof,
        test_resolve_intel_network_cancel_reaction_proof=test_resolve_intel_network_cancel_reaction_proof,
        test_setup_hong_kong_safehouse=test_setup_hong_kong_safehouse,
        test_setup_pending_choice_board_guard=test_setup_pending_choice_board_guard,
        test_setup_enemy_occupancy_proof=test_setup_enemy_occupancy_proof,
        test_setup_move_confirmation_proof=test_setup_move_confirmation_proof,
        test_setup_destroyed_red_base_marker_proof=test_setup_destroyed_red_base_marker_proof,
        test_setup_hu_taiwan_shared=test_setup_hu_taiwan_shared,
        test_setup_shared_dissolve=test_setup_shared_dissolve,
        test_setup_india_support_purchase=test_setup_india_support_purchase,
        test_setup_remove_to_purchase=test_setup_remove_to_purchase,
        test_setup_underground_party=test_setup_underground_party,
        test_setup_recruit_talent_proof=test_setup_recruit_talent_proof,
        test_setup_support_card_play=test_setup_support_card_play,
        test_setup_purchase_deck_ui=test_setup_purchase_deck_ui,
        test_setup_hand_preview=test_setup_hand_preview,
        test_setup_end_turn_topdeck_proof=test_setup_end_turn_topdeck_proof,
        test_setup_business_network_transport_proof=test_setup_business_network_transport_proof,
        test_setup_planning_lobby_ui=test_setup_planning_lobby_ui,
        test_setup_trash_choice_ui=test_setup_trash_choice_ui,
        test_setup_red_support_proof=test_setup_red_support_proof,
        test_setup_red_army_abilities_proof=test_setup_red_army_abilities_proof,
        test_setup_spy_proof=test_setup_spy_proof,
        test_setup_victory_proof=test_setup_victory_proof,
        test_setup_draw_privacy_proof=test_setup_draw_privacy_proof,
        test_trigger_draw_privacy_proof=test_trigger_draw_privacy_proof,
        test_setup_elite_defection_discard_proof=test_setup_elite_defection_discard_proof,
        test_setup_discard_reshuffle_proof=test_setup_discard_reshuffle_proof,
        test_setup_support_proof=test_setup_support_proof,
        test_setup_taiwan_support_proof=test_setup_taiwan_support_proof,
        test_setup_bait_exhaustion_ui=test_setup_bait_exhaustion_ui,
        test_setup_manchuria_era_reorder_proof=test_setup_manchuria_era_reorder_proof,
        test_setup_event_card_proof=test_setup_event_card_proof,
        test_setup_national_people_congress_red_dissolve_proof=test_setup_national_people_congress_red_dissolve_proof,
        test_setup_national_people_congress_inner_build_proof=test_setup_national_people_congress_inner_build_proof,
        test_setup_trade_war_event_proof=test_setup_trade_war_event_proof,
        test_setup_discard_topdeck_choice=test_setup_discard_topdeck_choice,
        test_setup_ccdi_choice=test_setup_ccdi_choice,
        test_setup_elite_defection_event_proof=test_setup_elite_defection_event_proof,
        test_setup_belt_road_red_turn_proof=test_setup_belt_road_red_turn_proof,
        test_setup_tibet_era_red_build_proof=test_setup_tibet_era_red_build_proof,
        test_setup_era_event_layout_proof=test_setup_era_event_layout_proof,
        test_setup_era_notification_proof=test_setup_era_notification_proof,
        test_setup_hong_kong_era_red_discard_proof=test_setup_hong_kong_era_red_discard_proof,
        test_setup_uyghur_era_red_dissolve_proof=test_setup_uyghur_era_red_dissolve_proof,
        test_setup_urumqi_event_proof=test_setup_urumqi_event_proof,
        test_setup_faction_action_used_proof=test_setup_faction_action_used_proof,
        test_setup_show_strength_choice_proof=test_setup_show_strength_choice_proof,
        test_setup_peer_choice_notice_proof=test_setup_peer_choice_notice_proof,
        test_setup_safehouse_range_proof=test_setup_safehouse_range_proof,
        test_setup_era_restrict_ignore_distance_proof=test_setup_era_restrict_ignore_distance_proof,
    )
