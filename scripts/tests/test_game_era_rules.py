"""Unit tests for server/game_era_rules.py — the pure era display/
notification cluster extracted from game.py (item 23, extract-era-service).

evaluate_era_trigger was added in a later slice once
game_organization_scope_rules.organization_towns_for_player (and its
dependents) were verified pure.
"""

from server.game import Game
from server.game_era_rules import (
    era_card_entry,
    era_notification_payload,
    player_matches_era_trigger,
    era_stage_for_player,
    evaluate_era_trigger,
)


def _new_game():
    return Game([('p1', 'a'), ('p2', 'b')])


# ---------- era_card_entry ----------

def test_era_card_entry_finds_a_known_era_by_name():
    # Any era name present in data/cards/event_and_era_cards.v1.1.json works;
    # pull one from the live structured_eras catalog so this doesn't hardcode
    # a name that could drift out of sync with the data file.
    game = _new_game()
    era_name = game.structured_eras[0]['name']
    row = era_card_entry(era_name)
    assert row is not None
    assert row[0] == era_name


def test_era_card_entry_returns_none_for_an_unknown_name():
    assert era_card_entry('這個時代不存在_xyz') is None


# ---------- era_notification_payload ----------

def test_era_notification_payload_fills_in_placeholders_when_data_missing():
    payload = era_notification_payload({'id': 'x', 'name': '不存在的時代_xyz', 'trigger': {}, 'duration': {}})
    assert payload['name'] == '不存在的時代_xyz'
    assert payload['summary_text'] == '（時代關卡簡述暫缺）'
    assert payload['duration_text'] == '持續時間未明'
    assert payload['remaining'] is None
    assert payload['minimized'] is False


def test_era_notification_payload_uses_real_catalog_text_for_a_known_era():
    game = _new_game()
    era = game.structured_eras[0]
    payload = era_notification_payload(era)
    assert payload['id'] == era.get('id')
    assert payload['name'] == era.get('name')


def test_era_notification_payload_duration_text_for_turns_and_permanent():
    turns_payload = era_notification_payload({'name': 'x', 'trigger': {}, 'duration': {'type': 'turns', 'value': 3}})
    assert turns_payload['duration_text'] == '持續 3 回合'
    permanent_payload = era_notification_payload({'name': 'x', 'trigger': {}, 'duration': {'type': 'permanent'}})
    assert permanent_payload['duration_text'] == '持續至遊戲結束'


def test_era_notification_payload_count_only_trigger_text_fallback():
    payload = era_notification_payload({'name': '不存在的時代_xyz', 'trigger': {'type': 'count_only', 'count': 5}, 'duration': {}})
    assert payload['trigger_text'] == '在指定區域擁有至少 5 個有效組織。'


# ---------- player_matches_era_trigger ----------

def test_player_matches_era_trigger_with_no_conditions_always_matches():
    game = _new_game()
    player = game.players[0]
    assert player_matches_era_trigger(game.faction_by_id, player, {}) is True


def test_player_matches_era_trigger_by_faction_id():
    game = _new_game()
    player = game.players[0]
    player.faction_id = 'red_army'
    assert player_matches_era_trigger(game.faction_by_id, player, {'faction_id': 'red_army'}) is True
    assert player_matches_era_trigger(game.faction_by_id, player, {'faction_id': 'hong_kong'}) is False


def test_player_matches_era_trigger_by_camp():
    game = _new_game()
    player = game.players[0]
    player.faction_id = 'red_army'
    camp = game.faction_by_id.get('red_army', {}).get('camp')
    assert player_matches_era_trigger(game.faction_by_id, player, {'camp': camp}) is True
    assert player_matches_era_trigger(game.faction_by_id, player, {'camp': 'no_such_camp_xyz'}) is False


# ---------- era_stage_for_player ----------

def test_era_stage_for_player_returns_none_for_red_army():
    game = _new_game()
    player = game.players[0]
    player.faction_id = 'red_army'
    assert era_stage_for_player(game.structured_eras, game.faction_by_id, [], player) is None


def test_era_stage_for_player_returns_none_for_no_player():
    game = _new_game()
    assert era_stage_for_player(game.structured_eras, game.faction_by_id, [], None) is None


def test_era_stage_for_player_finds_a_matching_era_and_marks_active():
    game = _new_game()
    player = game.players[0]
    player.faction_id = 'hong_kong'
    # Find an era this faction actually matches, if any exist in the catalog —
    # otherwise this scenario legitimately doesn't apply to this faction and
    # the function should return None, which is also a valid, checked outcome.
    matching_era = next(
        (era for era in game.structured_eras if player_matches_era_trigger(game.faction_by_id, player, era.get('trigger') or {})),
        None,
    )
    result = era_stage_for_player(game.structured_eras, game.faction_by_id, [matching_era['id']] if matching_era else [], player)
    if matching_era is None:
        assert result is None
    else:
        assert result is not None
        assert result['id'] == matching_era['id']
        assert result['achieved'] is True


# ---------- evaluate_era_trigger ----------

def test_evaluate_era_trigger_count_only_false_when_the_threshold_is_unreachable():
    game = _new_game()
    trigger = {'type': 'count_only', 'region': 'china', 'count': 9999}
    assert evaluate_era_trigger(game.map, game.towns_by_ruler, game.faction_by_id, game.players, trigger) is False


def test_evaluate_era_trigger_count_only_true_when_the_threshold_is_zero():
    # A count of 0 is trivially satisfied by every matching player, regardless
    # of their actual organization count — checks the wiring, not the counting.
    game = _new_game()
    trigger = {'type': 'count_only', 'region': 'china', 'count': 0}
    assert evaluate_era_trigger(game.map, game.towns_by_ruler, game.faction_by_id, game.players, trigger) is True


def test_evaluate_era_trigger_unknown_type_returns_false():
    game = _new_game()
    assert evaluate_era_trigger(game.map, game.towns_by_ruler, game.faction_by_id, game.players, {'type': 'no_such_type'}) is False


def test_evaluate_era_trigger_count_and_required_with_requirements_list():
    game = _new_game()
    trigger = {
        'type': 'count_and_required',
        'requirements': [{'region': 'china', 'count': 0}],
    }
    assert evaluate_era_trigger(game.map, game.towns_by_ruler, game.faction_by_id, game.players, trigger) is True
