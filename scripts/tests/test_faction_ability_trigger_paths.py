from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, Player, TurnPhase


EXPECTED_ABILITY_NAMES = {
    "中紀委", "人同此心", "印度研究分析室", "各界資助", "商貿組織", "國安部", "國際線",
    "基金會", "安全屋", "展現實力", "攬炒策略", "政工部", "新疆社會管控", "星星之火",
    "本土社團", "東突厥斯坦政府", "殉道者", "民主陣線", "民國之心", "民族祭儀",
    "民族調和", "活動家", "游擊隊", "盟旗學校", "立場試探", "紅軍派系", "統戰部",
    "華文傳媒", "賭徒耳語", "達賴救援", "選我河山", "青山里", "非暴力",
}


def make_game(faction_id: str, base: str) -> tuple[Game, Player, Player]:
    game = Game([("p1", "玩家"), ("p2", "紅軍")])
    player, red = game.players
    player.faction_id = faction_id
    player.base = base
    player.organizations = {base: 1}
    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}
    game.current_player_index = 0
    game.round_start_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.current_event = None
    game.event_progress = None
    game.pending_choice = None
    game.turn_log = game._new_turn_log()
    game.action_log = []
    return game, player, red


def resolved_ability_names(game: Game) -> set[str]:
    names: set[str] = set()
    player = game.players[0]
    for faction in game.factions:
        player.faction_id = faction["id"]
        for base in faction.get("bases") or [None]:
            player.base = base.get("name") if isinstance(base, dict) else base
            names.update(
                ability["name"]
                for ability in game._player_effective_abilities(player)
                if isinstance(ability, dict) and ability.get("name")
            )
    return names


def test_all_faction_abilities_resolve_from_active_catalog():
    game, _, _ = make_game("taiwan_green", "臺北")
    assert resolved_ability_names(game) == EXPECTED_ABILITY_NAMES


def test_taiwan_green_support_build_is_recorded_and_draws_at_turn_end():
    game, player, _ = make_game("taiwan_green", "臺北")
    player.hand = [Card(f"手牌{i}", "command", {}) for i in range(5)]
    player.deck.draw_pile = [Card("本土社團加抽", "command", {})]

    result = game._resolve_support_interaction_result(
        player,
        {"town": "成都"},
        {"context": {"effect_type": "interactive_build_anywhere_inner", "card_name": "東洋奧援"}},
    )
    assert result.get("success") is True
    assert game.turn_log["built_towns"] == ["成都"]

    game._apply_turn_end_faction_abilities(player)
    assert len(player.hand) == 6
    assert player.hand[-1].name == "本土社團加抽"
    assert any("triggered 本土社團 and drew 1 card" in entry for entry in game.action_log)


def test_taiwan_blue_and_republican_turn_end_build_triggers():
    for faction_id, base, ability, town in [
        ("taiwan_blue", "臺北", "民國之心", "曼谷"),
        ("republican", "任意牆內", "選我河山", "成都"),
    ]:
        game, player, _ = make_game(faction_id, base)
        player.hand = [Card(f"手牌{i}", "command", {}) for i in range(5)]
        player.deck.draw_pile = [Card(f"{ability}加抽", "command", {})]
        game._record_action_build(player, town)
        game._apply_turn_end_faction_abilities(player)
        assert len(player.hand) == 6
        assert any(f"triggered {ability} and drew 1 card" in entry for entry in game.action_log)


def test_support_build_runs_guerrilla_once():
    game, player, red = make_game("tibet_dehradun", "德拉敦")
    red.hand = [Card("紅軍手牌甲", "command", {}), Card("紅軍手牌乙", "command", {})]

    result = game._resolve_support_interaction_result(
        player,
        {"town": "拉薩"},
        {"context": {"effect_type": "interactive_build_anywhere_inner", "card_name": "東洋奧援"}},
    )
    assert result.get("success") is True
    assert len(red.hand) == 1
    game._record_action_build(player, "昆明")
    assert len(red.hand) == 1
    assert game.turn_log["guerrilla_triggered"] is True


def test_safehouse_extends_card_and_support_build_range_only_in_wall_inner_towns():
    game, player, _ = make_game("hong_kong", "香港城")
    inner = set(game._towns_for_region_alias("china"))
    one_step = game._towns_within_steps(["香港城"], max_steps=1)
    two_step_inner = (
        game._towns_within_steps(["香港城"], max_steps=2) - one_step
    ) & inner
    expected = {town for town in two_step_inner if game._can_player_build_in_town(player, town)}
    assert expected

    card_choices = {entry["town"] for entry in game._card_build_town_choices(player, {"range": 1})}
    support_choices = {entry["town"] for entry in game._interactive_support_build_towns(player, near_only=True)}
    assert expected <= card_choices
    assert expected <= support_choices


def test_card_play_triggered_abilities_fire_once_for_each_ability_family():
    scenarios = [
        ("federalists", "任意牆內", True, False, "商貿組織", "draw"),
        ("kazakh", "阿拉木圖", False, True, "民族調和", "draw"),
        ("new_left", "任意牆內", False, True, "星星之火", "draw"),
        ("uyghur_munich", "慕尼黑", True, False, "基金會", "money"),
        ("gender_revolution", "任意牆內城鎮", False, True, "人同此心", "propaganda"),
    ]
    for faction_id, base, money_cost, propaganda_cost, ability, reward in scenarios:
        game, player, _ = make_game(faction_id, base)
        player.hand = []
        player.deck.draw_pile = [Card("加抽乙", "command", {}), Card("加抽甲", "command", {})]
        before_resources = dict(player.resources)
        game._apply_card_play_faction_abilities(
            player,
            cost_has_money=money_cost,
            cost_has_propaganda=propaganda_cost,
        )
        first_hand = len(player.hand)
        first_resources = dict(player.resources)
        game._apply_card_play_faction_abilities(
            player,
            cost_has_money=money_cost,
            cost_has_propaganda=propaganda_cost,
        )
        if reward == "draw":
            assert first_hand == 1 and len(player.hand) == 1
        elif reward == "money":
            assert first_resources["money"] == before_resources["money"] + 2
            assert player.resources == first_resources
        else:
            assert first_resources["propaganda"] == before_resources["propaganda"] + 2
            assert player.resources == first_resources
        assert sum(f"triggered {ability}" in entry for entry in game.action_log) == 1


def test_interactive_support_defers_card_trigger_until_target_resolves():
    game, player, _ = make_game("federalists", "成都")
    player.organizations = {"成都": 1}
    player.hand = [game._make_support_card("東洋奧援")]
    player.deck.draw_pile = [Card("商貿組織加抽", "command", {})]
    game._support_card_tier = lambda _player, _card: (3, 0, [])

    played = game.play_card(0, mode="action")
    assert played.get("pending_choice") is True
    assert game.pending_choice["choice_key"] == "support_interaction"
    assert not game.turn_log.get("faction_first_money_triggered")

    resolved = game.resolve_pending_choice(player.id, 0)
    assert resolved.get("success") is True
    assert game.turn_log["faction_first_money_triggered"] is True
    assert [card.name for card in player.hand] == ["商貿組織加抽"]


def test_show_strength_triggers_once_after_three_unique_nonstarter_cards():
    game, player, _ = make_game("manchuria", "東京")
    game.turn_log["played_nonstarter_names"] = ["甲", "乙", "丙"]
    game._apply_card_play_faction_abilities(player, cost_has_money=False, cost_has_propaganda=False)
    assert player.resources["money"] == 3
    game._apply_card_play_faction_abilities(player, cost_has_money=False, cost_has_propaganda=False)
    assert player.resources["money"] == 3
    assert game.turn_log["combo_reward_triggered"] is True


def test_martyr_and_green_hill_draw_when_wall_inner_organization_is_dissolved():
    for faction_id, base, ability in [
        ("underground_church", "任意牆內城鎮", "殉道者"),
        ("chaoxian", "延邊", "青山里"),
    ]:
        game, defender, attacker = make_game(faction_id, base)
        defender.base = "巴黎"
        defender.organizations = {"成都": 1}
        defender.hand = []
        defender.deck.draw_pile = [Card(f"{ability}加抽", "command", {})]
        attacker.hand = [Card("攻擊成本", "command", {})]
        result = game.dissolve_organization(attacker, defender, "成都")
        assert result.get("success") is True
        assert len(defender.hand) == 1


def test_setup_abilities_add_their_printed_static_cards():
    scenarios = [
        ("hong_kong", "倫敦", "宣傳家", 1),
        ("tibet_dharamsala", "達蘭薩拉", "宣傳家", 2),
        ("uyghur_munich", "慕尼黑", "宣傳家", 2),
        ("minyun", "巴黎", "資助者", 1),
        ("gender_revolution", "任意牆內城鎮", "宣傳家", 2),
    ]
    for faction_id, base, card_name, expected_gain in scenarios:
        game, player, _ = make_game(faction_id, base)

        def count_card() -> int:
            cards = list(player.hand) + list(player.deck.draw_pile) + list(player.deck.discard_pile)
            return sum(card.name == card_name for card in cards)

        before = count_card()
        game._apply_setup_abilities(player)
        assert count_card() == before + expected_gain


def test_non_red_activated_faction_actions_resolve():
    game, player, _ = make_game("minyun", "巴黎")
    player.resources = {"money": 2, "propaganda": 0}
    assert game._activated_faction_action(player, "民主陣線").get("success") is True

    game, player, _ = make_game("liberals", "任意牆內城鎮")
    player.deck.draw_pile = [Card("立場牌", "command", {})]
    assert game._activated_faction_action(player, "立場試探").get("success") is True

    game, player, _ = make_game("reform_opening", "任意牆內")
    player.hand = []
    player.deck.draw_pile = [Card(name, "command", {}) for name in ["甲", "乙", "丙"]]
    started = game._activated_faction_action(player, "紅軍派系")
    assert started.get("pending_choice") is True
    assert game.resolve_pending_choice(player.id, [0, 1, 2]).get("success") is True
    assert len(player.hand) == 1

    game, player, _ = make_game("aomen", "澳門")
    player.hand = [Card("墊牌", "command", {})]
    player.deck.draw_pile = [Card("偶數牌", "command", {})]
    gambler = game._activated_faction_action(player, "賭徒耳語", guess="even")
    assert gambler.get("success") is True
    assert gambler["result"]["hit"] is True

    game, player, _ = make_game("zhuang", "南寧")
    player.hand = [Card("墊牌", "command", {})]
    player.deck.draw_pile = [Card("偶數牌", "command", {})]
    ritual = game._activated_faction_action(player, "民族祭儀", guess="odd")
    assert ritual.get("pending_choice") is True
    assert game.resolve_pending_choice(player.id, 0).get("success") is True
    assert player.resources["propaganda"] == 2


def test_red_army_activated_faction_actions_resolve():
    game, red, opponent = make_game("red_army", "北京")
    opponent.faction_id = "liberals"
    red.deck.draw_pile = [Card("統戰加抽", "command", {})]
    assert game._activated_faction_action(red, "統戰部", _skip_reaction_prompt=True).get("success") is True

    game, red, opponent = make_game("red_army", "北京")
    opponent.faction_id = "liberals"
    result = game._activated_faction_action(
        red,
        "政工部",
        target_player_id=opponent.id,
        _skip_reaction_prompt=True,
    )
    assert result.get("success") is True
    assert opponent.deck.draw_pile[-1].name == "內鬥"

    game, red, opponent = make_game("red_army", "北京")
    opponent.faction_id = "liberals"
    opponent.base = "巴黎"
    opponent.organizations = {"天津": 1}
    started = game._activated_faction_action(red, "國安部", _skip_reaction_prompt=True)
    assert started.get("pending_choice") is True
    assert game.resolve_pending_choice(red.id, 0).get("success") is True
    assert "天津" not in opponent.organizations

    game, red, opponent = make_game("red_army", "北京")
    opponent.faction_id = "liberals"
    red.hand = [Card("手牌甲", "command", {}), Card("手牌乙", "command", {})]
    red.deck.draw_pile = [Card("補牌甲", "command", {}), Card("補牌乙", "command", {})]
    started = game._activated_faction_action(red, "中紀委", _skip_reaction_prompt=True)
    assert started.get("pending_choice") is True
    assert game.resolve_pending_choice(red.id, [0, 1]).get("success") is True
    assert {card.name for card in red.hand} == {"補牌甲", "補牌乙"}


def test_payment_and_restriction_abilities_are_enforced():
    for ability_faction, base in [("falun_gong", "紐約"), ("hong_kong", "倫敦")]:
        game, player, _ = make_game(ability_faction, base)
        payment = game._purchase_payment_cost(player, Card("宣傳家", "propaganda", {"propaganda": 2}))
        assert payment["money"] > 0 and payment["propaganda"] == 0

    game, player, _ = make_game("uyghur_munich", "慕尼黑")
    assert game._player_is_nonviolent(player)
    assert game._player_is_distance_restricted(player)
    assert game._card_is_banned_for_player(player, Card("武裝者", "armed", {}))
    non_india_support = game._make_support_card("東洋奧援")
    allowed, error = game._can_player_gain_flag_card(player, non_india_support)
    assert allowed and error is None

    game, player, _ = make_game("tibet_dehradun", "德拉敦")
    assert game._player_has_india_research_room(player)
    allowed, error = game._can_player_gain_flag_card(player, game._make_support_card("東洋奧援"))
    assert not allowed and "印度研究分析室" in (error or "")
