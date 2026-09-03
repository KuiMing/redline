from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game
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


def _new_game():
    return Game([("p1", "A"), ("p2", "B")])


def test_resolve_ability_ref_passthrough_for_plain_ability_dict():
    game = _new_game()
    ability = {"name": "統戰部", "type": "activated", "effect": "抽1張牌"}
    assert game._resolve_ability_ref(ability) == resolve_ability_ref(game.ability_templates, ability) == ability


def test_resolve_ability_ref_resolves_template_and_name_override():
    game = _new_game()
    ability = {"ref": "on_build_draw_inner_or_nanyang", "name_override": "民國之心"}
    expected = game._resolve_ability_ref(ability)
    actual = resolve_ability_ref(game.ability_templates, ability)
    assert expected == actual
    assert actual["name"] == "民國之心"


def test_resolve_ability_ref_none_for_non_dict():
    game = _new_game()
    assert game._resolve_ability_ref("not a dict") is None
    assert resolve_ability_ref(game.ability_templates, "not a dict") is None


def test_resolve_ability_text_alias_mapping():
    game = _new_game()
    text = "【商貿組織】當您每回合第1次打出購買費用含資金的牌時，抽1張牌。"
    expected = game._resolve_ability_text(text)
    actual = resolve_ability_text(game.ability_templates, text)
    assert expected == actual
    assert actual["name"] == "商貿組織"


def test_resolve_ability_text_direct_mapping():
    game = _new_game()
    text = "【賭徒耳語】在己方行動階段，可將1張手牌放進牌庫底，猜牌庫頂牌購買費用奇偶，並展示牌庫頂牌。若猜中可獲得3點宣傳與3點資金。"
    expected = game._resolve_ability_text(text)
    actual = resolve_ability_text(game.ability_templates, text)
    assert expected == actual == {"name": "賭徒耳語", "type": "activated", "effect": "將1張手牌放進牌庫底，猜牌庫頂牌購買費用奇偶；若猜中獲得3點宣傳與3點資金。"}


def test_resolve_ability_text_none_when_no_brackets():
    game = _new_game()
    assert game._resolve_ability_text("plain text") is None
    assert resolve_ability_text(game.ability_templates, "plain text") is None


def test_resolve_faction_abilities_matches_game_method_for_dict_abilities():
    game = _new_game()
    faction_id = "red_army"
    expected = game._resolve_faction_abilities(faction_id)
    actual = resolve_faction_abilities(game.faction_by_id, game.ability_templates, faction_id)
    assert expected == actual
    assert len(actual) == 4


def test_resolve_faction_abilities_matches_game_method_for_text_abilities():
    game = _new_game()
    faction_id = "yue"
    expected = game._resolve_faction_abilities(faction_id)
    actual = resolve_faction_abilities(game.faction_by_id, game.ability_templates, faction_id)
    assert expected == actual
    assert len(actual) == 1
    assert actual[0]["name"] == "商貿組織"


def test_player_base_data_matches_game_method():
    game = _new_game()
    for player in game.players:
        expected = game._player_base_data(player)
        actual = player_base_data(game.faction_by_id, player.faction_id, player.base)
        assert expected == actual


def test_player_effective_abilities_matches_game_method():
    game = _new_game()
    for player in game.players:
        expected = game._player_effective_abilities(player)
        actual = player_effective_abilities(
            game.faction_by_id, game.ability_templates, player.faction_id, player.base
        )
        assert expected == actual


def test_player_has_ability_matches_game_method():
    game = _new_game()
    for player in game.players:
        for name in ("統戰部", "商貿組織", "not a real ability"):
            expected = game._player_has_ability(player, name)
            actual = player_has_ability(
                game.faction_by_id, game.ability_templates, player.faction_id, player.base, name
            )
            assert expected == actual


def test_camp_token_for_faction_id_matches_game_method():
    game = _new_game()
    for faction_id in ("red_army", "hong_kong", "taiwan_blue", "nonexistent"):
        expected = game._camp_token_for_faction_id(faction_id)
        actual = camp_token_for_faction_id(game.faction_by_id, faction_id)
        assert expected == actual
    assert game._camp_token_for_faction_id("red_army") == "紅軍"
    assert game._camp_token_for_faction_id("hong_kong") == "香港"
    assert game._camp_token_for_faction_id("taiwan_blue") == "臺灣"


def test_canonical_faction_name_to_id_matches_game_method():
    game = _new_game()
    for name in ("民國派", "滇", "unknown_name"):
        expected = game._canonical_faction_name_to_id(name)
        actual = canonical_faction_name_to_id(name)
        assert expected == actual
    assert game._canonical_faction_name_to_id("民國派") == "republican"
    assert game._canonical_faction_name_to_id("滇") == "dian"
    assert game._canonical_faction_name_to_id("unknown_name") == "unknown_name"


def test_factions_sharing_with_matches_game_method_for_hong_kong():
    game = _new_game()
    expected = game._factions_sharing_with("hong_kong")
    actual = factions_sharing_with(game.faction_by_id, "hong_kong")
    assert expected == actual
    assert actual == {"yue", "aomen"}


def test_factions_sharing_with_matches_game_method_for_taiwan_blue():
    game = _new_game()
    expected = game._factions_sharing_with("taiwan_blue")
    actual = factions_sharing_with(game.faction_by_id, "taiwan_blue")
    assert expected == actual
    assert actual == {"republican", "dian"}


def test_player_camp_falls_back_to_faction_id_when_faction_has_no_camp():
    game = _new_game()
    player = game.players[0]
    player.faction_id = "hong_kong"
    expected = game._player_camp(player)
    actual = player_camp(game.faction_by_id, player)
    assert expected == actual


def test_player_matches_camp_true_for_no_camp_filter():
    game = _new_game()
    player = game.players[0]
    assert game._player_matches_camp(player, None) is True
    assert player_matches_camp(game.faction_by_id, player, None) is True


def test_player_matches_camp_matches_by_own_camp_or_faction_id():
    game = _new_game()
    player = game.players[0]
    player.faction_id = "red_army"
    camp = game._player_camp(player)
    assert game._player_matches_camp(player, camp) is True
    assert player_matches_camp(game.faction_by_id, player, camp) is True
    assert game._player_matches_camp(player, "no_such_camp_xyz") is False


def test_players_matching_camp_matches_game_method():
    game = _new_game()
    game.players[0].faction_id = "red_army"
    game.players[1].faction_id = "hong_kong"
    camp = game._player_camp(game.players[0])
    expected = game._players_matching_camp(camp)
    actual = players_matching_camp(game.faction_by_id, game.players, camp)
    assert [p.id for p in expected] == [p.id for p in actual]
    assert game.players[0] in expected
    assert game.players[1] not in expected
