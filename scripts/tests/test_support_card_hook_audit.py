from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, TurnPhase


ORDINARY_SUPPORTS = [
    ("英美奧援", 1),
    ("東洋奧援", 3),
    ("南洋奧援", 2),
    ("印度奧援", 1),
    ("天方奧援", 2),
    ("歐洲奧援", 1),
    ("北國奧援", 2),
    ("臺灣奧援", 3),
]


def make_game(faction_id: str = "federalists"):
    game = Game([("p1", "玩家"), ("p2", "紅軍")])
    player, red = game.players
    player.faction_id = faction_id
    player.base = "成都"
    player.organizations = {"北京": 1}
    player.resources = {"money": 0, "propaganda": 0}
    player.deck.draw_pile = [Card(f"補牌{i}", "command", {}) for i in range(12)]
    player.deck.discard_pile = []

    red.faction_id = "red_army"
    red.base = "巴黎"
    red.organizations = {"天津": 1}
    red.hand = [Card(f"紅軍手牌{i}", "command", {}) for i in range(4)]
    red.deck.discard_pile = []

    game.current_player_index = 0
    game.round_start_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.current_event = None
    game.event_progress = None
    game.pending_choice = None
    game.turn_log = game._new_turn_log()
    game.action_log = []
    return game, player, red


def resolve_all_support_choices(game: Game, player, *, limit: int = 8):
    result = {"success": True}
    for _ in range(limit):
        choice = game.pending_choice
        if not choice:
            return result
        assert choice.get("player_id") == player.id
        result = game.resolve_pending_choice(player.id, 0)
        assert result.get("error") is None, result
    raise AssertionError("support flow did not settle within limit")


@pytest.mark.parametrize(("card_name", "tier"), ORDINARY_SUPPORTS)
def test_every_ordinary_support_path_runs_post_play_faction_hooks_once(card_name: str, tier: int):
    game, player, _ = make_game("federalists")
    player.hand = [game._make_support_card(card_name)]
    game._support_card_tier = lambda _player, _card: (tier, 0, [])

    played = game.play_card(0, mode="action")
    assert played.get("success") is True, played
    if game.pending_choice:
        resolve_all_support_choices(game, player)

    assert game.pending_choice is None
    assert game.turn_log["faction_first_money_triggered"] is True
    assert sum("triggered 商貿組織" in entry for entry in game.action_log) == 1


def test_india_support_consumes_static_distraction_supply_and_stops_when_empty():
    game, player, red = make_game("liberals")
    player.hand = [game._make_support_card("印度奧援")]
    game._support_card_tier = lambda _player, _card: (3, 0, ["印度"])
    game.static_purchase_supply["分神"] = 2

    result = game.play_card(0, mode="action")

    assert result.get("success") is True
    assert game.static_purchase_supply["分神"] == 0
    assert [card.name for card in red.deck.discard_pile] == ["分神", "分神"]
    assert any("分神" in entry and "供應" in entry for entry in game.action_log)


def test_india_research_room_triggers_after_declined_reaction_and_counts_for_event():
    game, player, red = make_game("tibet_dehradun")
    player.hand = [game._make_support_card("印度奧援")]
    red.hand = [Card("爆料黑幕", "reaction", {})]
    game._support_card_tier = lambda _player, _card: (1, 0, [])
    game.current_event = {
        "name": "能力任務測試",
        "type": "mission",
        "trigger": {"type": "use_faction_ability", "count": 1},
    }
    game.event_progress = {"count": 0, "required": 1, "succeeded": False, "settled": False, "status": "active"}

    prompted = game.play_card(0, mode="action")
    assert prompted.get("pending_choice") is True
    assert game.pending_choice.get("choice_key") == "cancel_other_player_action"

    resolved = game.resolve_pending_choice(red.id, 0)

    assert resolved.get("success") is True
    assert player.resources["money"] == 2
    assert game.turn_log["india_flag_money_triggered"] is True
    assert game.event_progress["count"] == 1
    assert game.event_progress["succeeded"] is True
    assert sum("triggered 印度研究分析室" in entry for entry in game.action_log) == 1


def test_india_research_room_immediate_path_counts_for_event_once():
    game, player, _ = make_game("tibet_dehradun")
    player.hand = [game._make_support_card("印度奧援")]
    game._support_card_tier = lambda _player, _card: (1, 0, [])
    game.current_event = {
        "name": "能力任務測試",
        "type": "mission",
        "trigger": {"type": "use_faction_ability", "count": 1},
    }
    game.event_progress = {"count": 0, "required": 1, "succeeded": False, "settled": False, "status": "active"}

    result = game.play_card(0, mode="action")

    assert result.get("success") is True
    assert player.resources["money"] == 2
    assert game.event_progress["count"] == 1
    assert sum("triggered 印度研究分析室" in entry for entry in game.action_log) == 1


def test_cancelled_india_support_does_not_apply_effect_or_india_research_room():
    game, player, red = make_game("tibet_dehradun")
    player.hand = [game._make_support_card("印度奧援")]
    red.hand = [Card("爆料黑幕", "reaction", {})]
    game._support_card_tier = lambda _player, _card: (3, 0, [])
    game.static_purchase_supply["分神"] = 3
    game.current_event = {
        "name": "能力任務測試",
        "type": "mission",
        "trigger": {"type": "use_faction_ability", "count": 1},
    }
    game.event_progress = {"count": 0, "required": 1, "succeeded": False, "settled": False, "status": "active"}

    prompted = game.play_card(0, mode="action")
    assert prompted.get("pending_choice") is True
    cancelled = game.resolve_pending_choice(red.id, 1)

    assert cancelled.get("success") is True
    assert player.resources["money"] == 0
    assert game.turn_log["india_flag_money_triggered"] is False
    assert game.event_progress["count"] == 0
    assert game.static_purchase_supply["分神"] == 3
    assert [card.name for card in red.deck.discard_pile] == ["爆料黑幕"]
    assert [card.name for card in player.deck.discard_pile] == ["印度奧援"]


def test_canceling_beiguo_support_restores_played_card_combo_state():
    game, player, _ = make_game("manchuria")
    player.hand = [game._make_support_card("北國奧援")]
    game._support_card_tier = lambda _player, _card: (2, 0, [])
    game.turn_log["played_nonstarter_names"] = ["甲", "乙"]

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True
    assert game.pending_choice.get("cancellable") is True
    assert game.turn_log["played_nonstarter_names"] == ["甲", "乙", "北國奧援"]

    cancelled = game.cancel_pending_choice(player.id)

    assert cancelled.get("success") is True
    assert [card.name for card in player.hand] == ["北國奧援"]
    assert game.turn_log["played_nonstarter_names"] == ["甲", "乙"]
    assert game.turn_log["combo_reward_triggered"] is False


def test_canceling_borrowed_beiguo_support_restores_exact_card_and_return_marker():
    game, player, owner = make_game("manchuria")
    borrowed = game._make_support_card("北國奧援")
    setattr(borrowed, "_return_to_owner_topdeck", owner.id)
    player.hand = [borrowed]
    game._support_card_tier = lambda _player, _card: (2, 0, [])

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True
    assert any(card is borrowed for card in owner.deck.draw_pile)

    cancelled = game.cancel_pending_choice(player.id)

    assert cancelled.get("success") is True
    assert player.hand == [borrowed]
    assert getattr(borrowed, "_return_to_owner_topdeck") == owner.id
    assert not any(card is borrowed for card in owner.deck.draw_pile)
    assert game.pending_choice is None


def test_shared_organizations_are_support_origins_targets_and_sacrifices():
    game = Game([("actor", "粵"), ("sharer", "香港"), ("enemy", "敵方")])
    actor, sharer, enemy = game.players
    actor.faction_id = "yue"
    actor.base = "韶關"
    actor.organizations = {}
    sharer.faction_id = "hong_kong"
    sharer.base = "香港"
    sharer.organizations = {"廣州": 1}
    enemy.faction_id = "red_army"
    enemy.base = "巴黎"
    enemy.organizations = {"深圳": 1}
    enemy.hand = [Card("敵方手牌", "command", {})]
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.turn_log = game._new_turn_log()

    assert "廣州" in game._organization_towns_for_player(actor)
    reachable_inner = game._towns_within_steps(["廣州"], max_steps=1) & set(game._towns_for_region_alias("china"))
    expected_builds = {
        town for town in reachable_inner
        if game._can_player_build_in_town(actor, town)
    }
    actual_builds = {
        entry["town"] for entry in game._interactive_support_build_towns(actor, near_only=True)
    }
    assert expected_builds
    assert actual_builds == expected_builds
    assert any(
        entry["player_id"] == enemy.id and entry["town"] == "深圳"
        for entry in game._interactive_support_dissolve_targets(actor)
    )
    assert game._player_has_org_within_steps_of_player(actor, enemy, max_steps=1)
    assert any(entry["town"] == "廣州" for entry in game._interactive_support_sacrifice_towns(actor))


def test_support_can_target_an_opponents_shared_physical_organization():
    game = Game([("actor", "聯邦派"), ("target", "粵"), ("owner", "香港")])
    actor, target, owner = game.players
    actor.faction_id = "federalists"
    actor.base = "天津"
    actor.organizations = {"深圳": 1}
    target.faction_id = "yue"
    target.base = "韶關"
    target.organizations = {}
    owner.faction_id = "hong_kong"
    owner.base = "香港"
    owner.organizations = {"廣州": 1}
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.turn_log = game._new_turn_log()

    targets = game._interactive_support_dissolve_targets(actor)
    shared_target = next(
        entry for entry in targets
        if entry["player_id"] == target.id and entry["town"] == "廣州"
    )
    assert game._can_replace_dissolved_org_with_own(actor, target, "廣州") is True

    dissolved = game.dissolve_organization(actor, target, shared_target["town"])
    assert dissolved.get("success") is True
    assert "廣州" not in owner.organizations


def test_beiguo_tier_one_can_sacrifice_a_shared_physical_organization():
    game = Game([("actor", "粵"), ("sharer", "香港"), ("enemy", "敵方")])
    actor, sharer, enemy = game.players
    actor.faction_id = "yue"
    actor.base = "韶關"
    actor.organizations = {}
    actor.hand = [game._make_support_card("北國奧援")]
    sharer.faction_id = "hong_kong"
    sharer.base = "香港"
    sharer.organizations = {"廣州": 1}
    enemy.faction_id = "red_army"
    enemy.base = "巴黎"
    enemy.organizations = {"深圳": 1}
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.turn_log = game._new_turn_log()
    game._support_card_tier = lambda _player, _card: (1, 0, [])

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True
    sacrifice_index = next(
        index for index, entry in enumerate(game.pending_choice["towns"])
        if entry["town"] == "廣州"
    )
    resolved = game.resolve_pending_choice(actor.id, sacrifice_index)

    assert resolved.get("success") is True
    assert resolved.get("pending_choice") is True
    assert "廣州" not in sharer.organizations
    assert game.pending_choice.get("step") == "target"


def test_stale_support_target_refreshes_choice_instead_of_consuming_interaction():
    game, player, red = make_game("federalists")
    player.hand = [game._make_support_card("東洋奧援")]
    game._support_card_tier = lambda _player, _card: (3, 0, [])

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True
    stale_town = game.pending_choice["towns"][0]["town"]
    red.organizations[stale_town] = 1

    stale = game.resolve_pending_choice(player.id, 0)

    assert stale.get("error") == "Invalid build town"
    assert stale.get("retryable") is True
    assert stale.get("pending_choice") is True
    assert game.pending_choice is not None
    assert stale_town not in {entry["town"] for entry in game.pending_choice["towns"]}

    completed = game.resolve_pending_choice(player.id, 0)
    assert completed.get("success") is True
    assert game.pending_choice is None


def test_red_army_support_separates_printed_resources_from_zero_purchase_cost():
    game, _, red = make_game("liberals")
    support = game._make_support_card("紅軍奧援")

    assert game._is_starter_support_card("紅軍奧援") is True
    assert support.resources == {"money": 1, "propaganda": 1}
    assert game._card_purchase_cost(support) == {"money": 0, "propaganda": 0}


def test_red_player_can_use_red_army_support_as_resource_without_choosing_target():
    # 2026-08-08 使用者更正：紅軍自己用紅軍奧援當資源時，直接取得資源、卡片進自己棄牌堆，
    # 不問要放進哪位反共玩家的棄牌堆（那是行動模式才有的效果）。
    game, anti_red, red = make_game("liberals")
    game.current_player_index = 1
    red.hand = [game._make_support_card("紅軍奧援")]
    red.resources = {"money": 0, "propaganda": 0}
    red.deck.draw_pile = [Card("不應抽到", "command", {})]
    red.deck.discard_pile = []
    anti_red.deck.discard_pile = []
    game.turn_log = game._new_turn_log()

    result = game.play_card(0, mode="resource")

    assert result.get("success") is True
    assert not result.get("pending_choice")
    assert game.pending_choice is None
    assert red.resources == {"money": 1, "propaganda": 1}
    assert [card.name for card in red.deck.draw_pile] == ["不應抽到"]
    assert [card.name for card in red.deck.discard_pile] == ["紅軍奧援"]
    assert anti_red.deck.discard_pile == []


def test_anti_red_player_can_use_red_army_support_as_resource_and_return_it_to_red_discard():
    game, anti_red, red = make_game("liberals")
    anti_red.hand = [game._make_support_card("紅軍奧援")]
    anti_red.resources = {"money": 0, "propaganda": 0}
    anti_red.deck.draw_pile = [Card("不應抽到", "command", {})]
    red.deck.discard_pile = []

    result = game.play_card(0, mode="resource")

    assert result.get("success") is True
    assert anti_red.resources == {"money": 1, "propaganda": 1}
    assert [card.name for card in anti_red.deck.draw_pile] == ["不應抽到"]
    assert [card.name for card in red.deck.discard_pile] == ["紅軍奧援"]
    assert game.pending_choice is None


def test_red_player_action_mode_draws_but_does_not_gain_red_support_resources():
    game, anti_red, red = make_game("liberals")
    game.current_player_index = 1
    red.hand = [game._make_support_card("紅軍奧援")]
    red.resources = {"money": 0, "propaganda": 0}
    red.deck.draw_pile = [Card("行動抽牌", "command", {})]
    anti_red.hand = []
    anti_red.deck.discard_pile = []
    game.turn_log = game._new_turn_log()

    prompted = game.play_card(0, mode="action")
    assert prompted.get("pending_choice") is True
    resolved = game.resolve_pending_choice(red.id, 0)

    assert resolved.get("success") is True
    assert red.resources == {"money": 0, "propaganda": 0}
    assert [card.name for card in red.hand] == ["行動抽牌"]
    assert [card.name for card in anti_red.deck.discard_pile] == ["紅軍奧援"]


def test_anti_red_player_action_mode_draws_and_returns_red_support_without_resources():
    game, anti_red, red = make_game("liberals")
    anti_red.hand = [game._make_support_card("紅軍奧援")]
    anti_red.resources = {"money": 0, "propaganda": 0}
    anti_red.deck.draw_pile = [Card("行動抽牌", "command", {})]
    red.hand = []
    red.deck.discard_pile = []

    result = game.play_card(0, mode="action")

    assert result.get("success") is True
    assert anti_red.resources == {"money": 0, "propaganda": 0}
    assert [card.name for card in anti_red.hand] == ["行動抽牌"]
    assert [card.name for card in red.deck.discard_pile] == ["紅軍奧援"]


def test_canceling_red_army_support_does_not_grant_purchase_cost_bonus_draw():
    game, reactor, red = make_game("liberals")
    game.current_player_index = 1
    red.hand = [game._make_support_card("紅軍奧援")]
    red.deck.draw_pile = [Card("不應抽到", "command", {})]
    reactor.hand = [Card("爆料黑幕", "reaction", {})]
    reactor.deck.draw_pile = [Card("取消獎勵牌", "command", {})]
    game.turn_log = game._new_turn_log()

    prompted = game.play_card(0, mode="action")
    assert prompted.get("pending_choice") is True
    cancelled = game.resolve_pending_choice(reactor.id, 1)

    assert cancelled.get("success") is True
    assert game.turn_log.get("canceled_propaganda_card") is False
    assert [card.name for card in reactor.hand] == []
    assert [card.name for card in reactor.deck.draw_pile] == ["取消獎勵牌"]
    assert [card.name for card in red.deck.draw_pile] == ["不應抽到"]
