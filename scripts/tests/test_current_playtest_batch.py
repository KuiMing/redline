from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase


def make_game():
    game = Game([('red', 'Red'), ('taiwan_green', 'Taiwan')])
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.current_player_index = 0
    game.players[0].faction_id = 'red_army'
    game.players[1].faction_id = 'taiwan_green'
    game.pending_base_choices = {}
    noop_event = game._event_by_name('歲月靜好')
    game.current_event = dict(noop_event or {})
    game.event_progress = {'count': 0, 'required': 0, 'succeeded': True, 'settled': True, 'status': 'idle'}
    game.event_modifiers = []
    game.pending_choice = None
    return game


def action_card(game, name):
    definition = next(card for card in game.structured_cards if card['name'] == name)
    return Card(definition['name'], definition['type'], definition.get('resources', {}))


def card_names(cards):
    return [getattr(card, 'name', str(card)) for card in cards]


def test_elite_defection_failure_after_refill_discards_exactly_one_named_card():
    game = Game([('host', 'host'), ('red', 'hostda')])
    host, red = game.players
    host.faction_id = 'taiwan_green'
    red.faction_id = 'red_army'
    game.current_player_index = 0
    game.round_start_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.END
    game.pending_base_choices = {}
    game.pending_choice = None

    selected_donor = Card('樂捐者', 'resource', {'money': 1})
    played_donor = Card('樂捐者', 'resource', {'money': 1})
    host.hand = []
    host.deck.draw_pile = [Card('牌庫甲', 'command', {}), Card('牌庫乙', 'command', {}), selected_donor]
    host.deck.discard_pile = [played_donor] + [Card(f'既有棄牌{i}', 'command', {}) for i in range(9)]
    red.hand = [Card(f'紅軍手牌{i}', 'command', {}) for i in range(5)]

    game.current_event = game._event_by_name('紅軍權貴出逃')
    game.event_progress = {
        'count': 0,
        'required': 3,
        'succeeded': False,
        'settled': False,
        'status': 'active',
        'last_actor_id': host.id,
    }

    result = game.advance_turn_phase()
    assert result.get('pending_choice') is True
    assert len(host.hand) == 5
    assert len(host.deck.draw_pile) == 8
    assert host.deck.discard_pile == []
    donor_index = next(i for i, card in enumerate(game.pending_choice['cards']) if card is selected_donor)

    resolved = game.resolve_pending_choice(host.id, [donor_index])
    assert resolved.get('success') is True
    assert resolved.get('chosen_cards') == ['樂捐者']
    assert len(host.hand) == 4
    assert len(host.deck.draw_pile) == 8
    assert host.deck.discard_pile == [selected_donor]
    remaining_non_discard = host.hand + host.deck.draw_pile
    assert played_donor in remaining_non_discard
    assert sum(card is played_donor for card in remaining_non_discard) == 1
    assert any('host discarded 1 chosen card(s): 樂捐者' in line for line in game.action_log)


def test_end_turn_logs_reshuffle_only_when_refill_exhausts_draw_pile():
    enough = make_game()
    player = enough.current_player()
    player.hand = [Card(f'保留{i}', 'command', {}) for i in range(4)]
    player.deck.draw_pile = [Card('牌庫保留牌', 'command', {})]
    player.deck.discard_pile = [Card('棄牌唯一一張', 'command', {})]
    enough._end_turn()
    assert not any('牌庫用盡' in line and '洗牌' in line for line in enough.action_log)

    exhausted = make_game()
    player = exhausted.current_player()
    player.hand = [Card(f'保留{i}', 'command', {}) for i in range(4)]
    player.deck.draw_pile = []
    player.deck.discard_pile = [Card('棄牌唯一一張', 'command', {})]
    exhausted._end_turn()
    assert any('牌庫用盡' in line and '將棄牌堆 1 張牌洗成新牌庫' in line for line in exhausted.action_log)


def test_red_end_turn_preserves_discard_when_draw_pile_can_complete_refill():
    game = make_game()
    red = game.current_player()
    red.hand = [Card('保留手牌', 'command', {})]
    red.deck.draw_pile = [Card(f'抽牌{i}', 'command', {}) for i in range(1, 5)]
    red.deck.discard_pile = [Card('既有棄牌A', 'command', {}), Card('既有棄牌B', 'command', {})]
    before_total = len(red.hand) + len(red.deck.draw_pile) + len(red.deck.discard_pile)

    game._end_turn()

    assert len(red.hand) == 5
    assert card_names(red.deck.discard_pile) == ['既有棄牌A', '既有棄牌B']
    assert len(red.hand) + len(red.deck.draw_pile) + len(red.deck.discard_pile) == before_total


def test_red_end_turn_reshuffles_discard_only_after_draw_pile_is_exhausted_and_conserves_cards():
    game = make_game()
    red = game.current_player()
    red.hand = [Card('保留手牌', 'command', {})]
    red.deck.draw_pile = [Card('牌庫最後一張', 'command', {})]
    red.deck.discard_pile = [Card(f'棄牌{i}', 'command', {}) for i in range(1, 5)]
    before_total = len(red.hand) + len(red.deck.draw_pile) + len(red.deck.discard_pile)

    game._end_turn()

    assert len(red.hand) == 5
    assert len(red.deck.draw_pile) == 1
    assert red.deck.discard_pile == []
    assert len(red.hand) + len(red.deck.draw_pile) + len(red.deck.discard_pile) == before_total


def test_taiwan_support_counts_as_prior_propaganda_cost_card_for_ignite_passion():
    game = make_game()
    red = game.current_player()
    red.hand = [game._make_support_card('臺灣奧援', variant_index=0), action_card(game, '點燃熱情')]
    red.deck.draw_pile = [Card('抽牌底', 'command', {}), Card('抽牌一', 'command', {}), Card('抽牌二', 'command', {})]

    support_result = game.play_card(0, mode='action')
    assert support_result.get('success'), support_result
    assert game.pending_choice is None

    ignite_result = game.play_card(0, mode='action')
    assert ignite_result.get('success'), ignite_result
    assert card_names(red.hand) == ['抽牌二', '抽牌一']


def test_north_support_initial_choice_can_be_cancelled_without_spending_card_or_mutating_board():
    game = make_game()
    red, opponent = game.players
    red.base = '北京'
    red.organizations = {'北京': 1, '承德': 1}
    opponent.base = '臺北'
    opponent.organizations = {'臺北': 1, '天津': 1}
    north_support = game._make_support_card('北國奧援', variant_index=0)
    red.hand = [north_support]
    red.deck.discard_pile = []

    play_result = game.play_card(0, mode='action')

    assert play_result.get('pending_choice') is True, play_result
    assert game.pending_choice and game.pending_choice.get('cancellable') is True
    assert game.state(red.id)['pending_choice']['cancellable'] is True
    assert red.hand == []
    assert red.deck.discard_pile == [north_support]
    assert red.organizations == {'北京': 1, '承德': 1}
    assert opponent.organizations == {'臺北': 1, '天津': 1}

    cancel_result = game.cancel_pending_choice(red.id)

    assert cancel_result.get('success') is True, cancel_result
    assert game.pending_choice is None
    assert red.hand == [north_support]
    assert red.deck.discard_pile == []
    assert red.organizations == {'北京': 1, '承德': 1}
    assert opponent.organizations == {'臺北': 1, '天津': 1}
    assert game.turn_log['played_money_card'] is False
    assert game.turn_log['played_propaganda_card'] is False


def test_discard_state_preserves_support_variant_for_full_card_preview():
    game = make_game()
    red = game.current_player()
    support = game._make_support_card('臺灣奧援', variant_index=1)
    red.deck.discard_pile = [action_card(game, '點燃熱情'), support]

    red_state = next(player for player in game.state(red.id)['players'] if player['id'] == red.id)

    assert red_state['discard_pile'] == ['點燃熱情', '臺灣奧援']
    assert red_state['discard_variants'][0] is None
    assert red_state['discard_variants'][1]['variant_index'] == 1


def test_multiple_propagandists_accumulate_build_entitlements_and_resolve_two_builds():
    game = make_game()
    red = game.current_player()
    game.players[1].organizations = {}
    red.organizations = {'臺北': 1}
    red.hand = [action_card(game, '宣傳家'), action_card(game, '宣傳家')]

    first_play = game.play_card(0, mode='action')
    assert first_play.get('pending_choice') is True, first_play
    assert game.pending_choice and game.pending_choice['source_name'] == '宣傳家'
    assert game.state(red.id)['pending_choice']['remaining_builds'] == 1

    second_play = game.play_card(0, mode='action')
    assert second_play.get('pending_choice') is True, second_play
    assert game.pending_choice and game.pending_choice['remaining_builds'] == 2
    assert game.state(red.id)['pending_choice']['remaining_builds'] == 2

    first_towns = [entry['town'] for entry in game.pending_choice['towns']]
    first_town = first_towns[0]
    first_build = game.resolve_pending_choice(red.id, 0)
    assert first_build.get('pending_choice') is True, first_build
    assert first_build.get('remaining_builds') == 1
    assert red.organizations[first_town] == 1
    assert red.moves_left == 1
    assert game.pending_choice and game.pending_choice['remaining_builds'] == 1

    second_towns = [entry['town'] for entry in game.pending_choice['towns']]
    assert first_town not in second_towns
    second_town = second_towns[0]
    second_build = game.resolve_pending_choice(red.id, 0)
    assert second_build.get('remaining_builds') == 0, second_build
    assert game.pending_choice is None
    assert red.organizations[second_town] == 1
    assert red.moves_left == 2
    assert len(red.organizations) == 3


def test_north_support_tier_three_resolves_two_targets_and_only_initial_step_is_cancellable():
    game = make_game()
    red, opponent = game.players
    red.organizations = {'北京': 1}
    opponent.organizations = {'天津': 1, '石家莊': 1}
    red.hand = [game._make_support_card('北國奧援', variant_index=0)]
    game._support_card_tier = lambda player, card: (3, 0, ['北國'])

    play_result = game.play_card(0, mode='action')
    assert play_result.get('pending_choice') is True, play_result
    assert game.pending_choice and game.pending_choice.get('cancellable') is True
    assert len(game.pending_choice['targets']) == 2

    first_result = game.resolve_pending_choice(red.id, 0)
    assert first_result.get('pending_choice') is True, first_result
    assert first_result.get('remaining_count') == 1
    assert game.pending_choice and game.pending_choice.get('cancellable') is not True
    assert game.cancel_pending_choice(red.id).get('error') == 'This choice cannot be cancelled'
    assert sum(opponent.organizations.values()) == 1

    second_result = game.resolve_pending_choice(red.id, 0)
    assert second_result.get('success') is True, second_result
    assert game.pending_choice is None
    assert opponent.organizations == {}


def _era_restriction_game(faction_id, era_id=None, origin='上海'):
    """建立一個「時代關卡已生效」的對局：時代關卡的無視距離限制只是 active modifier，
    直接 activate_era 即可，不需要真的打到觸發條件。"""
    game = Game([('actor', 'Actor'), ('red', 'Red')])
    actor, red = game.players
    actor.faction_id = faction_id
    red.faction_id = 'red_army'
    actor.organizations = {origin: 1}
    red.organizations = {}
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.current_player_index = 0
    game.pending_base_choices = {}
    game.turn_log = game._new_turn_log()
    if era_id:
        assert game.era_engine.activate_era(era_id)
    return game, actor


def _build_effect(game, card_name):
    definition = next(card for card in game.structured_cards if card['name'] == card_name)
    return next(effect for effect in definition['effect'] if effect.get('type') == 'build')


def _card_build_towns(game, player, card_name):
    return {entry['town'] for entry in game._card_build_town_choices(player, _build_effect(game, card_name))}


def test_ideologue_card_data_carries_inner_fallback_range():
    # 思想家過去沒有 inner_fallback_range，導致受距離限制時整片牆內被排除（無法建立），
    # 而非卡面規則的「退回 1 格」。比照姊妹牌組織經驗甲補上。
    game = Game([('a', 'A'), ('b', 'B')])
    assert _build_effect(game, '思想家').get('inner_fallback_range') == 1
    assert _build_effect(game, '組織經驗甲').get('inner_fallback_range') == 1


def test_rebels_era_downgrades_ignore_distance_card_builds_to_one_step_inside_wall():
    game, actor = _era_restriction_game('liberals', era_id='rebels')
    inner_towns = set(game._towns_for_region_alias('china'))
    near_inner = game._towns_within_steps(['上海'], max_steps=1) & inner_towns

    baseline, baseline_actor = _era_restriction_game('liberals')
    for card_name in ('思想家', '組織經驗甲'):
        towns = _card_build_towns(game, actor, card_name)
        inner_offered = towns & inner_towns
        assert inner_offered, card_name
        assert inner_offered <= near_inner, (card_name, sorted(inner_offered))
        # 牆外仍維持無視距離
        assert (towns - inner_towns) - game._towns_within_steps(['上海'], max_steps=1)
        # 對照組：時代關卡未觸發時可拿到遠方牆內城鎮
        assert (_card_build_towns(baseline, baseline_actor, card_name) & inner_towns) - near_inner


def test_kazakh_era_applies_the_same_ignore_distance_restriction():
    game, actor = _era_restriction_game('kazakh', era_id='kazakh', origin='烏魯木齊')
    inner_towns = set(game._towns_for_region_alias('china'))
    near_inner = game._towns_within_steps(['烏魯木齊'], max_steps=1) & inner_towns
    inner_offered = _card_build_towns(game, actor, '思想家') & inner_towns
    assert inner_offered and inner_offered <= near_inner


def test_era_ignore_distance_fallback_extends_with_build_range_bonus():
    game, actor = _era_restriction_game('liberals', era_id='rebels')
    actor.build_range_bonus = 1
    inner_towns = set(game._towns_for_region_alias('china'))
    near_1 = game._towns_within_steps(['上海'], max_steps=1) & inner_towns
    near_2 = game._towns_within_steps(['上海'], max_steps=2) & inner_towns
    inner_offered = _card_build_towns(game, actor, '思想家') & inner_towns
    assert inner_offered - near_1
    assert inner_offered <= near_2


def test_rebels_era_downgrades_east_asia_support_tier_three_to_near_inner():
    game, actor = _era_restriction_game('liberals', era_id='rebels')
    anywhere = {entry['town'] for entry in game._interactive_support_build_towns(actor, near_only=False)}
    near = {entry['town'] for entry in game._interactive_support_build_towns(actor, near_only=True)}
    assert anywhere == near

    baseline, baseline_actor = _era_restriction_game('liberals')
    baseline_anywhere = {
        entry['town'] for entry in baseline._interactive_support_build_towns(baseline_actor, near_only=False)
    }
    assert len(baseline_anywhere) > len(near)


def test_era_ignore_distance_restriction_does_not_leak_to_other_camps():
    game, actor = _era_restriction_game('kazakh', era_id='rebels', origin='烏魯木齊')
    inner_towns = set(game._towns_for_region_alias('china'))
    near_inner = game._towns_within_steps(['烏魯木齊'], max_steps=1) & inner_towns
    assert (_card_build_towns(game, actor, '思想家') & inner_towns) - near_inner
    anywhere = {entry['town'] for entry in game._interactive_support_build_towns(actor, near_only=False)}
    near = {entry['town'] for entry in game._interactive_support_build_towns(actor, near_only=True)}
    assert len(anywhere) > len(near)


def test_active_era_details_carry_full_explanation_for_every_viewer():
    """時代關卡達成浮窗縮小後，任何玩家都要能再點釘選卡片看完整說明，因此每個生效中的
    時代都必須帶著達成條件／紅軍壓制／革命反撲／期限文字，而不是只有 era_notification。"""
    game, actor = _era_restriction_game('liberals', era_id='rebels')
    opponent = game.players[1]
    game.era_notification = game._era_notification_payload(game.era_engine.get_definition('rebels'))
    for viewer in (actor, opponent):
        state = game.state(viewer_player_id=viewer.id)
        details = state['active_era_details']
        assert details, viewer.name
        item = next(d for d in details if d['id'] == 'rebels')
        for field in ('name', 'trigger_text', 'success_text', 'fail_text', 'duration_text'):
            assert item.get(field), (viewer.name, field)
        assert item['name'] == '[反賊]公知世代的終結'
        # 觸發通知本身也是全域廣播，不是只給觸發者
        assert state['era_notification']['id'] == 'rebels', viewer.name
