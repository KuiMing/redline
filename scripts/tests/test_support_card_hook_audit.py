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


def test_shared_organizations_are_available_to_every_spatial_support_effect():
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
    actual_builds = {
        entry["town"] for entry in game._interactive_support_build_towns(actor, near_only=True)
    }
    assert "梅州" in actual_builds
    assert any(
        entry["player_id"] == enemy.id and entry["town"] == "深圳"
        for entry in game._interactive_support_dissolve_targets(actor, include_shared_source=True)
    )
    assert game._player_has_org_within_steps_of_player(
        actor, enemy, max_steps=1, include_shared_source=True
    )
    assert any(
        entry["town"] == "廣州"
        for entry in game._interactive_support_sacrifice_towns(actor, include_shared_source=True)
    )


@pytest.mark.parametrize(("tier", "discard_count"), [(1, 1), (2, 1), (3, 2)])
def test_tianfang_support_uses_gender_revolution_base_shared_with_taiwan_green(
    tier, discard_count
):
    game = Game([("red", "紅軍"), ("tw", "臺灣綠線"), ("gender", "性別革命")])
    red, taiwan, gender = game.players
    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}
    red.hand = [Card(f"紅軍手牌 {index}", "command", {}) for index in range(3)]
    taiwan.faction_id = "taiwan_green"
    taiwan.base = "臺北"
    taiwan.organizations = {"臺北": 1}
    taiwan.hand = [game._make_support_card("天方奧援")]
    gender.faction_id = "gender_revolution"
    gender.base = "天津"
    gender.organizations = {"天津": 1}
    game.current_player_index = 1
    game.turn_phase = TurnPhase.ACTION
    game.turn_log = game._new_turn_log()
    game._support_card_tier = lambda _player, _card: (tier, 0, [])

    played = game.play_card(0, mode="action")

    assert played.get("pending_choice") is True, played
    assert any(
        entry["player_id"] == red.id
        for entry in game.pending_choice["targets"]
    )
    assert game.pending_choice["context"]["include_shared_source"] is True
    red_target_index = next(
        index
        for index, entry in enumerate(game.pending_choice["targets"])
        if entry["player_id"] == red.id
    )
    resolved = game.resolve_pending_choice(taiwan.id, red_target_index)
    assert resolved.get("success") is True, resolved
    if tier == 1:
        assert resolved.get("pending_choice") is True, resolved
        assert game.pending_choice["player_id"] == red.id
        resolved = game.resolve_pending_choice(red.id, 0)
        assert resolved.get("success") is True, resolved
    assert len(red.hand) == 3 - discard_count
    assert len(red.deck.discard_pile) == discard_count


@pytest.mark.parametrize(
    ("card_name", "tier", "expected_choice_key"),
    [
        ("東洋奧援", 2, "support_interaction"),
        ("北國奧援", 2, "support_interaction"),
        ("北國奧援", 3, "support_interaction"),
        ("臺灣奧援", 2, "support_interaction"),
        ("臺灣奧援", 3, "support_interaction"),
    ],
)
def test_other_spatial_support_cards_use_shared_organization_as_range_origin(
    card_name, tier, expected_choice_key
):
    game = Game([("actor", "臺灣綠線"), ("sharer", "性別革命"), ("enemy", "紅軍")])
    actor, sharer, enemy = game.players
    actor.faction_id = "taiwan_green"
    actor.base = "臺北"
    actor.organizations = {"臺北": 1}
    actor.hand = [game._make_support_card(card_name)]
    sharer.faction_id = "gender_revolution"
    sharer.base = "天津"
    sharer.organizations = {"天津": 1}
    enemy.faction_id = "red_army"
    enemy.base = "巴黎"
    enemy.organizations = {} if card_name == "東洋奧援" else {"北京": 1}
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.turn_log = game._new_turn_log()
    game._support_card_tier = lambda _player, _card: (tier, 0, [])

    played = game.play_card(0, mode="action")

    assert played.get("pending_choice") is True, played
    assert game.pending_choice["choice_key"] == expected_choice_key
    choices = game.pending_choice.get("towns") or game.pending_choice.get("targets") or []
    assert any(entry.get("town") == "北京" for entry in choices)
    assert game.pending_choice["context"]["include_shared_source"] is True


def test_beiguo_tier_three_keeps_shared_origin_for_second_dissolve():
    game = Game([("actor", "臺灣綠線"), ("sharer", "性別革命"), ("enemy", "紅軍")])
    actor, sharer, enemy = game.players
    actor.faction_id = "taiwan_green"
    actor.base = "臺北"
    actor.organizations = {"臺北": 1}
    actor.hand = [game._make_support_card("北國奧援")]
    sharer.faction_id = "gender_revolution"
    sharer.base = "天津"
    sharer.organizations = {"天津": 1}
    enemy.faction_id = "red_army"
    enemy.base = "巴黎"
    enemy.organizations = {"北京": 1, "濟南": 1}
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.turn_log = game._new_turn_log()
    game._support_card_tier = lambda _player, _card: (3, 0, [])

    assert game.play_card(0, mode="action").get("pending_choice") is True
    first_index = next(
        index for index, entry in enumerate(game.pending_choice["targets"])
        if entry["town"] == "北京"
    )
    first = game.resolve_pending_choice(actor.id, first_index)

    assert first.get("pending_choice") is True, first
    assert game.pending_choice["context"]["include_shared_source"] is True
    assert [entry["town"] for entry in game.pending_choice["targets"]] == ["濟南"]
    final = game.resolve_pending_choice(actor.id, 0)
    assert final.get("success") is True, final
    assert enemy.organizations == {}


def test_stale_tianfang_choice_refresh_keeps_shared_origins():
    game = Game([
        ("actor", "臺灣綠線"),
        ("sharer", "性別革命"),
        ("red_one", "紅軍一"),
        ("red_two", "紅軍二"),
    ])
    actor, sharer, red_one, red_two = game.players
    actor.faction_id = "taiwan_green"
    actor.base = "臺北"
    actor.organizations = {"臺北": 1}
    actor.hand = [game._make_support_card("天方奧援")]
    sharer.faction_id = "gender_revolution"
    sharer.base = "天津"
    sharer.organizations = {"天津": 1, "南京": 1}
    sharer.hand = []
    red_one.faction_id = "red_army"
    red_one.base = "北京"
    red_one.organizations = {"北京": 1}
    red_one.hand = [Card("已失效目標", "command", {})]
    red_two.faction_id = "red_army"
    red_two.base = "上海"
    red_two.organizations = {"上海": 1}
    red_two.hand = [Card("仍合法目標", "command", {})]
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.turn_log = game._new_turn_log()
    game._support_card_tier = lambda _player, _card: (1, 0, [])

    assert game.play_card(0, mode="action").get("pending_choice") is True
    stale_index = next(
        index for index, entry in enumerate(game.pending_choice["targets"])
        if entry["player_id"] == red_one.id
    )
    red_one.hand = []
    stale = game.resolve_pending_choice(actor.id, stale_index)

    assert stale.get("retryable") is True, stale
    assert game.pending_choice["context"]["include_shared_source"] is True
    assert [entry["player_id"] for entry in game.pending_choice["targets"]] == [red_two.id]
    completed = game.resolve_pending_choice(actor.id, 0)
    assert completed.get("success") is True, completed
    assert completed.get("pending_choice") is True, completed
    assert game.pending_choice["player_id"] == red_two.id
    completed = game.resolve_pending_choice(red_two.id, 0)
    assert completed.get("success") is True, completed
    assert red_two.hand == []


def test_support_cannot_target_an_opponents_shared_physical_organization():
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

    targets = game._interactive_support_dissolve_targets(actor, include_shared_source=False)
    assert not any(
        entry["player_id"] == target.id and entry["town"] == "廣州"
        for entry in targets
    )
    assert game._can_replace_dissolved_org_with_own(actor, target, "廣州") is False
    assert owner.organizations == {"廣州": 1}


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

    assert played.get("pending_choice") is True, played
    assert [entry["town"] for entry in game.pending_choice["towns"]] == ["廣州"]
    sacrificed = game.resolve_pending_choice(actor.id, 0)
    assert sacrificed.get("pending_choice") is True, sacrificed
    assert sharer.organizations == {}
    assert game.pending_choice["step"] == "target"
    assert [(entry["player_id"], entry["town"]) for entry in game.pending_choice["targets"]] == [
        (enemy.id, "深圳")
    ]


def test_beiguo_tier_one_sacrifices_own_org_then_dissolves_enemy_within_one_step():
    game = Game([("actor", "粵"), ("enemy", "敵方")])
    actor, enemy = game.players
    actor.faction_id = "yue"
    actor.base = "韶關"
    actor.organizations = {"廣州": 1}
    actor.hand = [game._make_support_card("北國奧援")]
    enemy.faction_id = "red_army"
    enemy.base = "巴黎"
    enemy.organizations = {"深圳": 1}
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.turn_log = game._new_turn_log()
    game._support_card_tier = lambda _player, _card: (1, 0, [])

    played = game.play_card(0, mode="action")

    assert played.get("pending_choice") is True, played
    assert game.pending_choice["step"] == "sacrifice_town"
    assert [entry["town"] for entry in game.pending_choice["towns"]] == ["廣州"]

    sacrificed = game.resolve_pending_choice(actor.id, 0)

    assert sacrificed.get("pending_choice") is True, sacrificed
    assert actor.organizations == {}
    assert game.pending_choice["step"] == "target"
    assert [(entry["player_id"], entry["town"]) for entry in game.pending_choice["targets"]] == [
        (enemy.id, "深圳")
    ]

    resolved = game.resolve_pending_choice(actor.id, 0)

    assert resolved.get("success") is True, resolved
    assert enemy.organizations == {}
    assert game.pending_choice is None


def test_self_sacrifice_spy_applies_target_region_before_consuming_origin():
    game = Game([("actor", "粵"), ("target", "目標")])
    actor, target = game.players
    actor.faction_id = "yue"
    actor.base = "韶關"
    actor.organizations = {"馬祖": 1}
    target.faction_id = "red_army"
    target.base = "巴黎"
    target.organizations = {"金門": 1, "福州": 1}

    resolved = game._resolve_support_interaction_result(
        actor,
        {"town": "馬祖"},
        {
            "step": "sacrifice_town",
            "context": {
                "effect_type": "interactive_dissolve_self_and_enemy",
                "card_name": "派遣間諜",
                "effect_payload": {"range": 1, "target_region": "china"},
                "include_shared_source": True,
            },
        },
    )

    assert resolved.get("pending_choice") is True, resolved
    assert actor.organizations == {}
    assert [entry["town"] for entry in game.pending_choice["targets"]] == ["福州"]
    assert "1 格內" in game.pending_choice["prompt"]


def test_shared_spy_consent_applies_target_region_and_range_prompt():
    game = Game([("actor", "粵"), ("owner", "香港"), ("target", "目標")])
    actor, owner, target = game.players
    actor.faction_id = "yue"
    actor.base = "韶關"
    owner.faction_id = "hong_kong"
    owner.base = "香港城"
    owner.organizations = {"馬祖": 1}
    target.faction_id = "red_army"
    target.base = "巴黎"
    target.organizations = {"金門": 1, "福州": 1, "廈門": 1}
    choice = {
        "choice_key": "shared_spy_origin_consent",
        "options": ["不同意", "同意"],
        "context": {
            "actor_player_id": actor.id,
            "owner_player_id": owner.id,
            "sacrifice_town": "馬祖",
            "flow_context": {
                "effect_type": "interactive_dissolve_self_and_enemy",
                "card_name": "派遣間諜",
                "effect_payload": {"range": 2, "target_region": "china"},
                "include_shared_source": True,
            },
        },
    }

    resolved = game._resolve_option_choice(owner, choice, 1)

    assert resolved.get("pending_choice") is True, resolved
    assert owner.organizations == {}
    assert [entry["town"] for entry in game.pending_choice["targets"]] == ["福州", "廈門"]
    assert "2 格內" in game.pending_choice["prompt"]


def test_spy_resolution_preserves_effect_range_policy():
    game = Game([("actor", "粵"), ("target", "目標")])
    actor, target = game.players
    actor.faction_id = "yue"
    actor.base = "韶關"
    actor.organizations = {"臺北": 1}
    target.faction_id = "red_army"
    target.base = "巴黎"
    target.organizations = {"新竹": 1}

    resolved = game._resolve_support_interaction_result(
        actor,
        {"selected": {"player_id": target.id, "town": "新竹"}},
        {
            "context": {
                "effect_type": "interactive_dissolve_many_near",
                "card_name": "內應間諜",
                "effect_payload": {"range": 2, "count": 1},
                "include_shared_source": True,
            },
        },
    )

    assert resolved.get("success") is True, resolved
    assert target.organizations == {}


def test_intel_network_revalidates_the_selected_organization_not_only_its_owner():
    game = Game([("actor", "粵"), ("target", "目標")])
    actor, target = game.players
    actor.faction_id = "yue"
    actor.base = "韶關"
    actor.organizations = {"臺北": 1}
    target.faction_id = "red_army"
    target.base = "巴黎"
    target.organizations = {"新北": 1, "新竹": 1}
    choice = {
        "choice_key": "intel_network_dissolve_target",
        "targets": [{"id": f"{target.id}::新竹", "player_id": target.id, "town": "新竹"}],
        "context": {"source_name": "情報網"},
    }

    resolved = game._resolve_target_choice(actor, choice, 0)

    assert resolved.get("error") == "Target organization is no longer within range"
    assert target.organizations == {"新北": 1, "新竹": 1}


def test_support_discard_revalidation_does_not_fall_back_to_shared_origin():
    game = Game([("actor", "粵"), ("sharer", "香港"), ("target", "目標")])
    actor, sharer, target = game.players
    actor.faction_id = "yue"
    actor.base = "韶關"
    actor.organizations = {"廣州": 1}
    sharer.faction_id = "hong_kong"
    sharer.base = "香港"
    sharer.organizations = {"廣州": 1}
    target.faction_id = "red_army"
    target.base = "巴黎"
    target.organizations = {"深圳": 1}
    target.hand = [Card("應保留", "command", {})]

    assert game._player_has_org_within_steps_of_player(
        actor, target, max_steps=1, include_shared_source=False
    ) is True

    actor.organizations.clear()

    assert game._player_has_org_within_steps_of_player(
        actor, target, max_steps=1, include_shared_source=False
    ) is False
    assert game._player_has_org_within_steps_of_player(
        actor, target, max_steps=1, include_shared_source=True
    ) is True

    resolved = game._resolve_support_interaction_result(
        actor,
        {"selected": {"player_id": target.id}},
        {
            "choice_key": "support_interaction",
            "step": "target",
            "context": {
                "effect_type": "force_discard_near",
                "card_name": "天方奧援",
                "effect_payload": {"range": 1, "count": 1, "random": True},
                "include_shared_source": False,
            },
        },
    )

    assert resolved.get("error") == "Target player is not within range"
    assert [card.name for card in target.hand] == ["應保留"]


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


def test_anti_red_player_can_use_red_army_support_as_resource_and_discard_it_own_pile():
    # 「打出」指行動模式。反共玩家選擇資源模式時，只取得印刷資源，
    # 並依一般資源牌規則把牌放進自己的棄牌堆。
    game, anti_red, red = make_game("liberals")
    anti_red.hand = [game._make_support_card("紅軍奧援")]
    anti_red.resources = {"money": 0, "propaganda": 0}
    anti_red.deck.draw_pile = [Card("不應抽到", "command", {})]
    anti_red.deck.discard_pile = []
    red.deck.discard_pile = []

    result = game.play_card(0, mode="resource")

    assert result.get("success") is True
    assert result.get("card_returned_to") is None
    assert anti_red.resources == {"money": 1, "propaganda": 1}
    assert [card.name for card in anti_red.deck.draw_pile] == ["不應抽到"]
    assert [card.name for card in anti_red.deck.discard_pile] == ["紅軍奧援"]
    assert red.deck.discard_pile == []
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
