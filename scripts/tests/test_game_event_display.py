"""Characterization tests for server/game_event_display.py — extracted
from Game._event_display_payload/_event_condition_text/_event_result_text/
_event_effect_actor_text/_event_region_text/_event_effect_text (game.py
refactor item 22, first slice: the pure display/text-formatting cluster).
"""

from server.game_event_display import (
    event_condition_text,
    event_result_text,
    event_effect_actor_text,
    event_region_text,
    event_effect_text,
    event_display_payload,
)


# ---------- event_condition_text ----------

def test_condition_text_empty_trigger():
    assert event_condition_text({}) == '無'
    assert event_condition_text(None) == '無'


def test_condition_text_known_types():
    assert event_condition_text({'type': 'draw', 'count': 2}) == '藉由卡牌效果或能力抽牌至少 2 次'
    assert event_condition_text({'type': 'build_organization'}) == '建立組織至少 1 次'


def test_condition_text_unknown_type_falls_back_to_the_raw_type():
    assert event_condition_text({'type': 'something_new'}) == 'something_new至少 1 次'


def test_condition_text_buy_card_detail():
    trigger = {'type': 'buy_card', 'min_cost': 3, 'card_names': ['分神', '內鬥']}
    text = event_condition_text(trigger)
    assert '總費用 3 點以上' in text
    assert '分神或內鬥' in text


def test_condition_text_scope_suffix():
    text = event_condition_text({'type': 'build_organization', 'scope': '牆內'})
    assert '（牆內）' in text


def test_condition_text_event_param_is_accepted_but_unused():
    # Matches the original method's signature/behavior exactly — `event`
    # doesn't change the result.
    trigger = {'type': 'draw', 'count': 1}
    assert event_condition_text(trigger, event={'name': 'irrelevant'}) == event_condition_text(trigger)


# ---------- event_result_text ----------

def test_result_text_no_event():
    assert event_result_text(None, {}) == ''


def test_result_text_mission_statuses():
    event = {'type': 'mission'}
    assert event_result_text(event, {'status': 'success_pending'}) == '非紅軍任務條件已達成，等待全體玩家行動結束後結算'
    assert event_result_text(event, {'status': 'success'}) == '非紅軍任務成功'
    assert event_result_text(event, {'status': 'failure'}) == '非紅軍任務失敗，紅軍效果生效'
    assert event_result_text(event, {'status': 'active'}) == '非紅軍任務進行中'
    assert event_result_text(event, {}) == '非紅軍任務進行中'


def test_result_text_non_mission_statuses():
    event = {'type': 'other'}
    assert event_result_text(event, {'status': 'auto'}) == '紅軍事件效果已自動套用'
    assert event_result_text(event, {'status': 'auto_pending', 'auto_target_player_name': '玩家A'}) == '等待 玩家A 回合發動紅軍事件效果'
    assert event_result_text(event, {'status': 'auto_pending'}) == '等待 紅軍 回合發動紅軍事件效果'
    assert event_result_text(event, {'status': 'idle'}) == '本次事件無效果'
    assert event_result_text(event, {'status': 'active'}) == ''


# ---------- event_effect_actor_text ----------

def test_effect_actor_text_known_and_unknown_and_empty():
    assert event_effect_actor_text({'player_faction': 'red_army'}) == '紅軍'
    assert event_effect_actor_text({'target_faction': 'hong_kong'}) == '香港'
    assert event_effect_actor_text({'target_camp': 'unmapped_camp'}) == 'unmapped_camp'
    assert event_effect_actor_text({}) == ''
    assert event_effect_actor_text({}, default_actor='taiwan') == '台灣'


# ---------- event_region_text ----------

def test_region_text_known_and_unknown_and_none():
    assert event_region_text('southeast_asia') == '南洋'
    assert event_region_text('some_unmapped_region') == 'some_unmapped_region'
    assert event_region_text(None) == '指定區域'


# ---------- event_effect_text ----------

def test_effect_text_none_type():
    assert event_effect_text(None) == '無'
    assert event_effect_text({'type': 'none'}) == '無'


def test_effect_text_known_type_with_actor():
    text = event_effect_text({'type': 'draw', 'count': 2, 'player_faction': 'red_army'})
    assert text == '紅軍：抽 2 張牌'


def test_effect_text_known_type_without_actor():
    assert event_effect_text({'type': 'draw', 'count': 1}) == '抽 1 張牌'


def test_effect_text_default_actor():
    text = event_effect_text({'type': 'draw', 'count': 1}, default_actor='hong_kong')
    assert text == '香港：抽 1 張牌'


def test_effect_text_unknown_type_falls_back_to_the_raw_type():
    assert event_effect_text({'type': 'mystery_effect'}) == 'mystery_effect'


def test_effect_text_uses_region_text_for_regional_effects():
    text = event_effect_text({'type': 'build_organization_in_region', 'region': 'southeast_asia', 'count': 1})
    assert '南洋' in text


# ---------- event_display_payload ----------

def test_display_payload_no_event_returns_none():
    assert event_display_payload(None, {}) is None


def test_display_payload_assembles_all_text_fields():
    event = {
        'id': 'e1',
        'name': '測試事件',
        'type': 'mission',
        'trigger': {'type': 'draw', 'count': 1},
        'success': {'type': 'draw', 'count': 1},
        'failure': {'type': 'none'},
        'effect': {'type': 'none'},
    }
    progress = {'status': 'success'}
    payload = event_display_payload(event, progress)
    assert payload['id'] == 'e1'
    assert payload['name'] == '測試事件'
    assert payload['status'] == 'success'
    assert payload['result_text'] == '非紅軍任務成功'
    assert payload['trigger_text'] == event_condition_text(event['trigger'])
    assert payload['success_text'] == event_effect_text(event['success'], default_actor='非紅軍')
    assert payload['failure_text'] == '無'
    assert payload['effect_text'] == '無'


def test_display_payload_defaults_status_to_active_when_progress_has_none():
    event = {'id': 'e2', 'trigger': {}, 'success': {}, 'failure': {}, 'effect': {}}
    payload = event_display_payload(event, {})
    assert payload['status'] == 'active'
