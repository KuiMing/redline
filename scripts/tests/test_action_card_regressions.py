from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase


def make_game():
    g = Game([('p1', 'P1'), ('p2', 'P2')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    g.players[0].faction_id = 'red_army'
    return g


def card(g, name):
    c = next(c for c in g.structured_cards if c['name'] == name)
    return Card(c['name'], c['type'], c.get('resources', {}))


def names(cards):
    result = []
    for c in cards:
        if isinstance(c, dict) and 'card' in c:
            c = c['card']
        result.append(getattr(c, 'name', str(c)))
    return result


def play_only(g, name):
    p = g.current_player()
    p.hand = [card(g, name)]
    p.resources = {'money': 0, 'propaganda': 0}
    result = g.play_card(0, mode='action')
    assert result.get('success'), result
    return p


def test_press_advantage_prompts_for_eligible_discard_card_and_leaves_high_cost_cards():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '乘勝追擊')]
    p.deck.discard_pile = [
        card(g, '宣傳家'),      # total cost 3: eligible
        card(g, '合作談判'),    # total cost 4: ineligible, should not be offered
        card(g, '走漏風聲'),    # total cost 2: eligible
    ]

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'gain_from_discard'
    assert g.pending_choice['source_name'] == '乘勝追擊'
    assert g.pending_choice['max_cost'] == 3
    assert names(g.pending_choice['cards']) == ['宣傳家', '走漏風聲']
    assert names(p.deck.discard_pile) == ['宣傳家', '合作談判', '走漏風聲', '乘勝追擊']

    resolved = g.resolve_pending_choice(p.id, 1)

    assert resolved.get('success'), resolved
    assert resolved.get('chosen_card') == '走漏風聲'
    assert names(p.hand) == ['走漏風聲']
    assert names(p.deck.discard_pile) == ['宣傳家', '合作談判', '乘勝追擊']
    assert g.pending_choice is None
    assert any('gained 走漏風聲 from discard via 乘勝追擊' in entry for entry in g.action_log)



def test_recruit_talent_selects_any_card_from_own_deck_not_topdeck_only():
    g = make_game()
    p = g.current_player()
    p.faction_id = 'tibet_dehradun'
    p.hand = [card(g, '網羅人才')]
    # Deck top is TopCard (last element). DesiredCard is deliberately not on top.
    p.deck.draw_pile = [Card('DesiredCard', 'command', {}), Card('MiddleCard', 'command', {}), Card('TopCard', 'command', {})]
    p.deck.discard_pile = [Card('DiscardOnly', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'recruit_talent'
    assert names(g.pending_choice['cards']) == ['DesiredCard', 'MiddleCard', 'TopCard']
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    assert 'DesiredCard' in names(p.hand)
    assert 'TopCard' not in names(p.hand)
    assert 'DiscardOnly' in names(p.deck.discard_pile)


def test_red_army_recruit_talent_can_select_from_own_deck_or_discard():
    g = make_game()
    p = g.current_player()
    p.faction_id = 'red_army'
    p.hand = [card(g, '網羅人才')]
    p.deck.draw_pile = [Card('DeckChoiceA', 'command', {}), Card('DeckChoiceB', 'command', {})]
    p.deck.discard_pile = [Card('DiscardChoice', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'recruit_talent'
    assert names(g.pending_choice['cards']) == ['DeckChoiceA', 'DeckChoiceB', 'DiscardChoice']
    assert g.state()['pending_choice']['cards'] == [
        {'name': 'DeckChoiceA', 'zone': 'draw_pile', 'zone_label': '牌庫'},
        {'name': 'DeckChoiceB', 'zone': 'draw_pile', 'zone_label': '牌庫'},
        {'name': 'DiscardChoice', 'zone': 'discard_pile', 'zone_label': '棄牌堆'},
    ]

    resolved = g.resolve_pending_choice(p.id, 2)

    assert resolved.get('success'), resolved
    assert resolved.get('source_zone') == 'discard_pile'
    assert names(p.hand) == ['DiscardChoice']
    assert names(p.deck.discard_pile) == ['網羅人才']
    assert 'DeckChoiceA' not in names(p.deck.draw_pile)
    assert 'DeckChoiceB' not in names(p.deck.draw_pile)
    assert g.pending_choice is None
    assert any('recruited DiscardChoice from discard via 網羅人才' in entry for entry in g.action_log)


def test_red_support_requires_red_army_to_choose_rebel_discard_target_before_resolving_resource_mode():
    g = make_game()
    red = g.current_player()
    rebel = g.players[1]
    rebel.faction_id = 'hong_kong'
    red.hand = [Card('紅軍奧援', 'support', {'money': 1, 'propaganda': 1})]
    red.resources = {'money': 0, 'propaganda': 0}
    rebel.deck.discard_pile = []

    result = g.play_card(0, mode='resource')

    assert result.get('pending_choice') is True
    assert red.resources == {'money': 0, 'propaganda': 0}
    assert names(red.hand) == []
    assert g.pending_choice and g.pending_choice['type'] == 'target_choice'
    assert g.pending_choice['choice_key'] == 'red_support_target_player'
    assert g.pending_choice['player_id'] == red.id
    assert [entry['label'] for entry in g.pending_choice['targets']] == ['P2']

    state_choice = g.state()['pending_choice']
    assert state_choice['type'] == 'target_choice'
    assert state_choice['choice_key'] == 'red_support_target_player'
    assert state_choice['player_id'] == red.id
    assert state_choice['targets'] == [{'id': rebel.id, 'label': 'P2'}]
    assert state_choice['source_name'] == '紅軍奧援'
    assert state_choice['mode'] == 'resource'

    resolved = g.resolve_pending_choice(red.id, 0)

    assert resolved.get('success'), resolved
    assert resolved.get('target_player_name') == 'P2'
    assert red.resources == {'money': 1, 'propaganda': 1}
    assert names(red.hand) == []
    assert names(rebel.deck.discard_pile)[-1] == '紅軍奧援'
    assert g.pending_choice is None


def test_red_support_requires_red_army_to_choose_rebel_discard_target_before_resolving_action_mode():
    g = make_game()
    red = g.current_player()
    rebel = g.players[1]
    rebel.faction_id = 'hong_kong'
    red.hand = [Card('紅軍奧援', 'support', {'money': 1, 'propaganda': 1})]
    red.deck.draw_pile = [Card('DrawnCard', 'command', {})]
    rebel.deck.discard_pile = []

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True
    assert names(red.hand) == ['DrawnCard']
    assert names(red.deck.draw_pile) == []
    assert g.pending_choice and g.pending_choice['choice_key'] == 'red_support_target_player'
    assert g.pending_choice['mode'] == 'action'

    resolved = g.resolve_pending_choice(red.id, 0)

    assert resolved.get('success'), resolved
    assert resolved.get('target_player_name') == 'P2'
    assert names(red.hand) == ['DrawnCard']
    assert names(rebel.deck.discard_pile)[-1] == '紅軍奧援'
    assert g.pending_choice is None


def test_taiwan_support_tier1_gains_propaganda_without_opening_target_choice():
    g = make_game()
    actor = g.current_player()
    enemy = g.players[1]

    actor.faction_id = 'taiwan_green'
    actor.base = '東京'
    actor.organizations = {'東京': 1}
    actor.hand = [g._make_support_card('臺灣奧援')]
    actor.resources = {'money': 0, 'propaganda': 0}

    enemy.faction_id = 'red_army'
    enemy.base = '北京'
    enemy.organizations = {'北京': 1}

    result = g.play_card(0, mode='action')

    assert result.get('success') is True, result
    assert actor.resources == {'money': 0, 'propaganda': 1}
    assert g.pending_choice is None


def test_north_support_uses_support_region_for_tier3_and_requires_full_pair_for_tier2():
    g = make_game()
    actor = g.current_player()

    actor.faction_id = 'liberals'
    actor.base = '海參崴'

    actor.organizations = {'海參崴': 1}
    tier3 = g._support_card_tier(actor, '北國奧援')
    assert tier3[0] == 3
    assert g._resolve_support_card_effect('北國奧援', tier3[0], tier3[1]) == ('interactive_dissolve_many_near', {'count': 2})

    actor.organizations = {'巴黎': 1}
    tier1 = g._support_card_tier(actor, '北國奧援')
    assert tier1[0] == 1
    assert g._resolve_support_card_effect('北國奧援', tier1[0], tier1[1]) == ('interactive_dissolve_self_and_enemy', {'count': 1})

    actor.organizations = {'巴黎': 1, '沖繩': 1}
    tier2 = g._support_card_tier(actor, '北國奧援')
    assert tier2 == (2, 0, ['歐洲', '東洋'])
    assert g._resolve_support_card_effect('北國奧援', tier2[0], tier2[1]) == ('interactive_dissolve_many_near', {'count': 1})


def test_north_support_tier1_sacrifices_the_selected_own_org_before_dissolving_enemy():
    g = make_game()
    actor = g.current_player()
    enemy = g.players[1]

    actor.faction_id = 'liberals'
    actor.base = '巴黎'
    actor.organizations = {'巴黎': 1, '日內瓦': 1}
    actor.hand = [g._make_support_card('北國奧援')]
    actor.resources = {'money': 0, 'propaganda': 0}

    enemy.faction_id = 'red_army'
    enemy.base = '慕尼黑'
    enemy.organizations = {'慕尼黑': 1}

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert result.get('tier') == 1
    assert result.get('effect_type') == 'interactive_dissolve_self_and_enemy'
    assert g.pending_choice['step'] == 'sacrifice_town'
    assert g.pending_choice['towns'] == [{
        'town': '日內瓦',
        'label': '日內瓦（可瓦解鄰近敵方組織）',
        'target_count': 1,
    }]

    sacrificed = g.resolve_pending_choice(actor.id, 0)

    assert sacrificed.get('success'), sacrificed
    assert sacrificed.get('pending_choice') is True, sacrificed
    assert actor.organizations == {'巴黎': 1}
    assert g.pending_choice['step'] == 'target'
    assert g.pending_choice['targets'] == [{
        'id': f'{enemy.id}::慕尼黑',
        'label': 'P2｜慕尼黑',
        'player_id': enemy.id,
        'town': '慕尼黑',
        'sacrifice_town': '日內瓦',
    }]

    resolved = g.resolve_pending_choice(actor.id, 0)

    assert resolved.get('success'), resolved
    assert actor.organizations == {'巴黎': 1}
    assert enemy.organizations.get('慕尼黑', 0) == 0


def test_taiwan_support_tier3_requires_target_choice_and_builds_in_same_town_after_resolution():
    g = make_game()
    actor = g.current_player()
    enemy = g.players[1]

    actor.faction_id = 'taiwan_green'
    actor.base = '佬沃'
    actor.organizations = {'屏東': 1, '佬沃': 1, '馬祖': 1}
    actor.hand = [g._make_support_card('臺灣奧援')]
    actor.resources = {'money': 0, 'propaganda': 0}
    actor.deck.draw_pile = []
    actor.deck.discard_pile = []

    enemy.faction_id = 'red_army'
    enemy.base = '福州'
    enemy.organizations = {'福州': 1}
    enemy.deck.discard_pile = []

    original_resolver = g._support_card_tier
    def forced_tier(player, card):
        card_name = getattr(card, 'name', str(card))
        if getattr(player, 'id', None) == actor.id and card_name == '臺灣奧援':
            return 3, 0, ['東洋', '南洋']
        return original_resolver(player, card)
    g._support_card_tier = forced_tier

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert result.get('tier') == 3
    assert result.get('effect_type') == 'interactive_dissolve_and_build'
    assert g.pending_choice and g.pending_choice['type'] == 'support_flow_choice'
    assert g.pending_choice['step'] == 'target'
    assert g.pending_choice['source_name'] == '臺灣奧援'
    assert g.pending_choice['context']['effect_type'] == 'interactive_dissolve_and_build'
    assert g.pending_choice['targets'] == [{
        'id': f'{enemy.id}::福州',
        'label': 'P2｜福州',
        'player_id': enemy.id,
        'town': '福州',
        'requires_self_sacrifice': False,
    }]

    state_choice = g.state()['pending_choice']
    assert state_choice['type'] == 'support_flow_choice'
    assert state_choice['step'] == 'target'
    assert state_choice['source_name'] == '臺灣奧援'
    assert state_choice['targets'] == [{
        'id': f'{enemy.id}::福州',
        'label': 'P2｜福州',
        'player_id': enemy.id,
        'town': '福州',
        'requires_self_sacrifice': False,
    }]

    resolved = g.resolve_pending_choice(actor.id, 0)

    assert resolved.get('success'), resolved
    assert enemy.organizations.get('福州', 0) == 0
    assert actor.organizations['福州'] == 1
    assert g.pending_choice is None



def test_taiwan_support_tier2_requires_target_choice_without_auto_resolution():
    g = make_game()
    actor = g.current_player()
    enemy = g.players[1]

    actor.faction_id = 'taiwan_green'
    actor.base = '東京'
    actor.organizations = {'東京': 1, '佬沃': 1}
    actor.hand = [g._make_support_card('臺灣奧援')]

    enemy.faction_id = 'red_army'
    enemy.base = '大阪'
    enemy.organizations = {'大阪': 1}

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert result.get('tier') == 2
    assert result.get('effect_type') == 'interactive_dissolve_many_near'
    assert g.pending_choice['type'] == 'support_flow_choice'
    assert g.pending_choice['step'] == 'target'
    assert g.pending_choice['context']['effect_type'] == 'interactive_dissolve_many_near'
    assert actor.organizations == {'東京': 1, '佬沃': 1}
    assert enemy.organizations == {'大阪': 1}

    resolved = g.resolve_pending_choice(actor.id, 0)

    assert resolved.get('success'), resolved
    assert enemy.organizations.get('大阪', 0) == 0
    assert actor.organizations == {'東京': 1, '佬沃': 1}



def test_lure_exhaustion_draws_then_prompts_target_choice_after_self_remove():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '誘導虛耗')]
    p2.hand = [Card('EnemyCard', 'command', {})]
    p1.deck.draw_pile = [Card('DrawnCard', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert names(p1.hand) == ['DrawnCard']
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'optional_trash'

    resolved = g.resolve_pending_choice(p1.id, 0)

    assert resolved.get('success'), resolved
    assert resolved.get('pending_choice') is True
    assert names(p1.deck.discard_pile) == ['誘導虛耗']
    assert g.pending_choice and g.pending_choice['type'] == 'target_choice'
    assert g.pending_choice['choice_key'] == 'bait_exhaustion_target'
    assert [entry['label'] for entry in g.pending_choice['targets']] == ['P2']

    state_choice = g.state()['pending_choice']
    assert state_choice['type'] == 'target_choice'
    assert state_choice['choice_key'] == 'bait_exhaustion_target'
    assert state_choice['source_name'] == '誘導虛耗'
    assert state_choice['step'] is None
    assert state_choice['options'] == []
    assert state_choice['towns'] == []
    assert state_choice['targets'] == [{'id': p2.id, 'label': 'P2'}]

    target_resolved = g.resolve_pending_choice(p1.id, 0)

    assert target_resolved.get('success'), target_resolved
    assert target_resolved.get('pending_choice') is True
    assert target_resolved.get('target_player_name') == 'P2'
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'bait_exhaustion_target_discard'
    assert g.pending_choice['player_id'] == p2.id
    assert names(g.pending_choice['cards']) == ['EnemyCard']

    target_state_choice = g.state()['pending_choice']
    assert target_state_choice['type'] == 'card_choice'
    assert target_state_choice['choice_key'] == 'bait_exhaustion_target_discard'
    assert target_state_choice['player_id'] == p2.id
    assert target_state_choice['cards'] == ['EnemyCard']
    assert target_state_choice['source_name'] == '誘導虛耗'

    discard_resolved = g.resolve_pending_choice(p2.id, 0)

    assert discard_resolved.get('success'), discard_resolved
    assert discard_resolved.get('discarded_card') == 'EnemyCard'
    assert discard_resolved.get('target_player_name') == 'P2'
    assert names(p2.hand) == []
    assert names(p2.deck.discard_pile) == ['EnemyCard']
    assert g.turn_log.get('successful_discard') is True


def test_imitate_tactics_uses_target_player_top_card_not_own_top_card():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '模仿戰術')]
    p1.deck.draw_pile = [Card('OwnTop', 'command', {})]
    p2.deck.draw_pile = [Card('TargetBottom', 'command', {}), Card('OpponentTop', 'command', {'money': 1})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert 'OpponentTop' in names(p1.hand)
    assert 'OwnTop' not in names(p1.hand)
    assert names(p2.deck.draw_pile) == ['TargetBottom']

    idx = names(p1.hand).index('OpponentTop')
    result = g.play_card(idx, mode='resource')
    assert result.get('success'), result
    assert names(p2.deck.draw_pile)[-1] == 'OpponentTop'
    assert 'OpponentTop' not in names(p1.deck.discard_pile)


def test_imitate_tactics_borrowed_card_returns_to_owner_topdeck_after_action_play():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '模仿戰術')]
    p2.deck.draw_pile = [Card('TargetBottom', 'command', {}), Card('點燃熱情', 'command', {'propaganda': 1})]
    p1.deck.draw_pile = [Card('Bottom', 'command', {}), Card('FirstDraw', 'command', {}), Card('SecondDraw', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    borrowed_index = names(p1.hand).index('點燃熱情')
    action_result = g.play_card(borrowed_index, mode='action')
    assert action_result.get('success'), action_result
    assert names(p2.deck.draw_pile)[-1] == '點燃熱情'
    assert '點燃熱情' not in names(p1.deck.discard_pile)
    assert names(p1.hand) == ['SecondDraw']



def test_business_network_borrowed_transport_card_grants_its_action_effect_after_choice_resolution():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '企業人脈')]
    g.purchase_area = [
        card(g, '宣傳家'),
        card(g, '思想家'),
        card(g, '資助者'),
        card(g, '資本家'),
        card(g, '分神'),
        card(g, '內鬥'),
        card(g, '合作談判'),
        card(g, '交通經驗乙'),
        card(g, '模仿戰術'),
    ]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'use_purchase_area_card'
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['合作談判', '交通經驗乙', '模仿戰術']

    resolved = g.resolve_pending_choice(p.id, 1)
    assert resolved.get('success'), resolved
    assert resolved.get('chosen_card') == '交通經驗乙'
    assert resolved.get('purchase_index') == 7
    assert p.moves_left == 4
    assert '交通經驗乙' not in names(p.hand)
    assert '交通經驗乙' not in names(p.deck.discard_pile)
    assert names(g.purchase_area)[7] == '交通經驗乙'



def test_red_support_uses_csv_resource_values_when_played_as_resource():
    g = make_game()
    p = g.current_player()
    rebel = g.players[1]
    rebel.faction_id = 'hong_kong'
    p.hand = [g._make_support_card('紅軍奧援')]
    p.resources = {'money': 0, 'propaganda': 0}

    result = g.play_card(0, mode='resource')

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert p.resources == {'money': 0, 'propaganda': 0}
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    assert p.resources == {'money': 1, 'propaganda': 1}
    assert names(rebel.deck.discard_pile)[-1] == '紅軍奧援'



def test_red_support_action_draws_and_moves_to_red_army_discard_when_rebel_plays_it():
    g = make_game()
    p1, p2 = g.players
    p1.faction_id = 'liberals'
    p2.faction_id = 'red_army'
    p1.hand = []
    p2.hand = []
    g.current_player_index = 0
    support = g._make_support_card('紅軍奧援')
    p1.deck.draw_pile = []
    p1.deck.discard_pile = [Card('DrawnCard', 'command', {})]
    p2.deck.discard_pile = []

    resolution = g._execute_support_card(p1, support)

    assert names(p1.hand) == ['DrawnCard']
    assert names(p1.deck.discard_pile) == []
    assert names(p2.deck.discard_pile) == ['紅軍奧援']
    assert resolution['effect_type'] == 'red_support_draw_and_pass'
    assert resolution['moved_to_player_id'] == p2.id



def test_red_support_action_draws_and_moves_to_rebel_discard_when_red_army_plays_it():
    g = make_game()
    p1, p2 = g.players
    p1.faction_id = 'red_army'
    p2.faction_id = 'liberals'
    p1.hand = []
    p2.hand = []
    g.current_player_index = 0
    support = g._make_support_card('紅軍奧援')
    p1.deck.draw_pile = []
    p1.deck.discard_pile = [Card('DrawnCard', 'command', {})]
    p2.deck.discard_pile = []

    resolution = g._execute_support_card(p1, support)

    assert names(p1.hand) == ['DrawnCard']
    assert names(p1.deck.discard_pile) == []
    assert names(p2.deck.discard_pile) == []
    assert resolution['effect_type'] == 'red_support_draw_and_pass'
    assert resolution['effect_text'] is None
    assert resolution['pending_choice'] is True
    assert g.pending_choice and g.pending_choice['choice_key'] == 'red_support_target_player'

    resolved = g.resolve_pending_choice(p1.id, 0)

    assert resolved.get('success'), resolved
    assert names(p1.hand) == ['DrawnCard']
    assert names(p2.deck.discard_pile) == ['紅軍奧援']
    assert resolved['moved_to_player_id'] == p2.id



def test_intel_network_state_serializes_three_options_for_ui():
    g = Game([('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3'), ('p4', 'P4')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    g.players[0].faction_id = 'red_army'
    p1, p2, p3, p4 = g.players
    p1.hand = [card(g, '情報網')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1}
    p2.deck.discard_pile = [Card('棄牌A', 'command', {})]
    p3.deck.discard_pile = [Card('棄牌B', 'command', {})]
    p4.deck.discard_pile = [Card('棄牌C', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    state_choice = g.state()['pending_choice']
    assert state_choice['type'] == 'option_choice'
    assert state_choice['choice_key'] == 'choose_one'
    assert state_choice['source_name'] == '情報網'
    assert [opt['label'] for opt in state_choice['options']] == [
        '在至多3位玩家棄牌堆各放入1張內鬥',
        '瓦解己方組織1格內的1個對手組織',
        '取消1張對方所打出行動卡之能力',
    ]



def test_intel_network_first_branch_adds_internal_conflict_without_running_other_branches():
    g = Game([('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3'), ('p4', 'P4')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    g.players[0].faction_id = 'red_army'
    p1, p2, p3, p4 = g.players
    p1.hand = [card(g, '情報網')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1}
    p2.deck.discard_pile = [Card('棄牌A', 'command', {})]
    p3.deck.discard_pile = [Card('棄牌B', 'command', {})]
    p4.deck.discard_pile = [Card('棄牌C', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    resolved = g.resolve_pending_choice(p1.id, 0)
    assert resolved.get('success'), resolved
    assert names(p1.deck.discard_pile) == ['情報網']
    assert names(p2.deck.discard_pile) == ['棄牌A', '內鬥']
    assert names(p3.deck.discard_pile) == ['棄牌B', '內鬥']
    assert names(p4.deck.discard_pile) == ['棄牌C', '內鬥']
    state_players = {player['name']: player for player in g.state()['players']}
    assert state_players['P2']['discard_pile'] == ['棄牌A', '內鬥']
    assert state_players['P3']['discard_pile'] == ['棄牌B', '內鬥']
    assert state_players['P4']['discard_pile'] == ['棄牌C', '內鬥']
    assert p2.organizations.get('天津', 0) == 1


def test_intel_network_can_choose_dissolve_branch_instead_of_default_internal_conflict():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '情報網')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1}

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'option_choice'
    assert g.pending_choice['choice_key'] == 'choose_one'
    resolved = g.resolve_pending_choice(p1.id, 1)
    assert resolved.get('success'), resolved
    assert resolved.get('pending_choice') is True
    assert g.pending_choice and g.pending_choice['choice_key'] == 'intel_network_dissolve_target'
    assert [entry['label'] for entry in g.pending_choice['targets']] == ['P2｜天津']
    target_resolved = g.resolve_pending_choice(p1.id, 0)
    assert target_resolved.get('success'), target_resolved
    assert p2.organizations.get('天津', 0) == 0
    assert names(p2.deck.discard_pile).count('內鬥') == 0



def test_intel_network_can_choose_cancel_branch_without_running_other_branches():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '情報網')]
    p2.hand = [Card('EnemyCard', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'option_choice'
    resolved = g.resolve_pending_choice(p1.id, 2)
    assert resolved.get('success'), resolved
    assert names(p2.deck.discard_pile).count('內鬥') == 0
    assert g.turn_log.get('canceled_propaganda_card') is None



def test_intel_network_reaction_cancels_other_player_action_without_bonus_draw():
    g = make_game()
    actor, reactor = g.players
    actor.hand = [card(g, '領導')]
    actor.deck.draw_pile = [Card('ShouldNotDraw', 'command', {})]
    reactor.hand = [card(g, '情報網')]
    reactor.deck.draw_pile = [Card('IntelShouldNotDrawBonus', 'command', {})]
    reactor.deck.discard_pile = []

    result = g.play_card(0, mode='action', reaction={'player_id': reactor.id, 'card_index': 0})

    assert result.get('success'), result
    assert names(actor.hand) == []
    assert names(actor.deck.discard_pile) == ['領導']
    assert names(reactor.hand) == []
    assert names(reactor.deck.discard_pile)[-1] == '情報網'
    assert names(reactor.hand) == []
    assert g.turn_log.get('canceled_card') is True
    assert g.turn_log.get('canceled_propaganda_card') is None
    assert g.turn_log.get('canceled_money_cost_card') is None



def test_intel_network_reaction_does_not_trigger_on_resource_play():
    g = make_game()
    actor, reactor = g.players
    actor.hand = [card(g, '領導')]
    actor.resources = {'money': 0, 'propaganda': 0}
    reactor.hand = [card(g, '情報網')]

    result = g.play_card(0, mode='resource', reaction={'player_id': reactor.id, 'card_index': 0})

    assert result.get('success'), result
    assert actor.resources == {'money': 0, 'propaganda': 1}
    assert names(reactor.hand) == ['情報網']
    assert names(reactor.deck.discard_pile) == []
    assert g.turn_log.get('canceled_card') is None


def test_first_other_player_action_prompts_cancel_reaction_once_with_all_available_cards():
    g = make_game()
    actor, reactor = g.players
    actor.hand = [card(g, '點燃熱情')]
    actor.deck.draw_pile = [Card('ShouldNotDrawYet', 'command', {})]
    reactor.hand = [card(g, '情報網'), card(g, '爆料黑幕'), card(g, '產業滲透')]

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert g.pending_choice and g.pending_choice['type'] == 'reaction_choice'
    assert g.pending_choice['choice_key'] == 'cancel_other_player_action'
    assert g.pending_choice['player_id'] == reactor.id
    assert g.pending_choice['acting_player_id'] == actor.id
    assert g.pending_choice['played_card_name'] == '點燃熱情'
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['情報網', '爆料黑幕', '產業滲透']
    assert names(actor.hand) == []
    assert names(actor.deck.discard_pile) == []
    assert names(actor.deck.draw_pile) == ['ShouldNotDrawYet']

    state_choice = g.state()['pending_choice']
    assert state_choice['type'] == 'reaction_choice'
    assert [entry['name'] for entry in state_choice['cards']] == ['情報網', '爆料黑幕', '產業滲透']
    assert state_choice['prompt'] == 'P1 打出 點燃熱情。是否要取消對方的行動？'

    skipped = g.resolve_pending_choice(reactor.id, 0)
    assert skipped.get('success'), skipped
    assert skipped.get('skipped_reaction') is True
    assert names(actor.hand) == ['ShouldNotDrawYet']
    assert names(actor.deck.discard_pile) == ['點燃熱情']
    assert names(reactor.hand) == ['情報網', '爆料黑幕', '產業滲透']

    actor.hand = [card(g, '領導')]
    actor.deck.draw_pile = [Card('ShouldDrawWithoutSecondPrompt', 'command', {})]
    second = g.play_card(0, mode='action')

    assert second.get('success'), second
    assert not second.get('pending_choice')
    assert g.pending_choice is None
    assert names(actor.hand) == ['ShouldDrawWithoutSecondPrompt']
    assert names(reactor.hand) == ['情報網', '爆料黑幕', '產業滲透']


def test_cancel_reaction_prompt_can_select_one_reaction_card_to_cancel_action():
    g = make_game()
    actor, reactor = g.players
    actor.hand = [card(g, '領導')]
    actor.deck.draw_pile = [Card('ShouldNotDraw', 'command', {})]
    reactor.hand = [card(g, '情報網'), card(g, '爆料黑幕')]
    reactor.deck.discard_pile = []

    prompted = g.play_card(0, mode='action')
    assert prompted.get('pending_choice') is True, prompted

    resolved = g.resolve_pending_choice(reactor.id, 1)

    assert resolved.get('success'), resolved
    assert resolved.get('canceled_card') == '領導'
    assert resolved.get('reaction_card') == '情報網'
    assert g.pending_choice is None
    assert names(actor.hand) == []
    assert names(actor.deck.draw_pile) == ['ShouldNotDraw']
    assert names(actor.deck.discard_pile) == ['領導']
    assert names(reactor.hand) == ['爆料黑幕']
    assert names(reactor.deck.discard_pile)[-1] == '情報網'
    assert g.turn_log.get('canceled_card') is True


def test_tianfang_support_tier1_prompts_actor_target_choice_then_target_discard_choice():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [g._make_support_card('天方奧援')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1}
    p2.hand = [Card('EnemyCardA', 'command', {}), Card('EnemyCardB', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert g.pending_choice and g.pending_choice['type'] == 'support_flow_choice'
    assert g.pending_choice['step'] == 'target'
    assert g.pending_choice['context']['effect_type'] == 'force_discard_near'
    assert g.pending_choice['context']['effect_payload'] == {'count': 1, 'random': False}
    assert [entry['label'] for entry in g.pending_choice['targets']] == ['P2']

    state_choice = g.state()['pending_choice']
    assert state_choice['type'] == 'support_flow_choice'
    assert state_choice['targets'] == [{'id': p2.id, 'label': 'P2', 'player_id': p2.id}]
    assert state_choice['source_name'] == '天方奧援'

    target_resolved = g.resolve_pending_choice(p1.id, 0)

    assert target_resolved.get('success'), target_resolved
    assert target_resolved.get('pending_choice') is True
    assert target_resolved.get('target_player_id') == p2.id
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'tianfang_support_target_discard'
    assert g.pending_choice['player_id'] == p2.id
    assert names(g.pending_choice['cards']) == ['EnemyCardA', 'EnemyCardB']

    target_state_choice = g.state()['pending_choice']
    assert target_state_choice['type'] == 'card_choice'
    assert target_state_choice['choice_key'] == 'tianfang_support_target_discard'
    assert target_state_choice['player_id'] == p2.id
    assert target_state_choice['cards'] == ['EnemyCardA', 'EnemyCardB']
    assert target_state_choice['source_name'] == '天方奧援'

    discard_resolved = g.resolve_pending_choice(p2.id, 1)

    assert discard_resolved.get('success'), discard_resolved
    assert discard_resolved.get('discarded_card') == 'EnemyCardB'
    assert discard_resolved.get('target_player_name') == 'P2'
    assert names(p2.hand) == ['EnemyCardA']
    assert names(p2.deck.discard_pile) == ['EnemyCardB']



def test_tianfang_support_tier3_discards_two_random_cards_from_chosen_target_in_range():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [g._make_support_card('天方奧援')]
    p1.faction_id = 'india'
    p1.organizations = {'喀布爾': 1, '拉瓦爾品第': 1}
    p2.organizations = {'杜尚貝': 1}
    p2.hand = [Card('EnemyCardA', 'command', {}), Card('EnemyCardB', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert result.get('tier') == 3
    assert g.pending_choice and g.pending_choice['context']['effect_payload'] == {'count': 2, 'random': True}

    resolved = g.resolve_pending_choice(p1.id, 0)

    assert resolved.get('success'), resolved
    assert resolved.get('target_player_id') == p2.id
    assert sorted(resolved.get('discarded_cards')) == ['EnemyCardA', 'EnemyCardB']
    assert names(p2.hand) == []
    assert sorted(names(p2.deck.discard_pile)) == ['EnemyCardA', 'EnemyCardB']



def test_divide_adds_internal_conflict_to_other_players_not_self():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '離間')]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert names(p1.deck.discard_pile).count('內鬥') == 0
    assert names(p2.deck.discard_pile).count('內鬥') == 3


def test_announce_action_topdecks_latest_card_bought_this_turn_and_gains_propaganda():
    g = make_game()
    p = g.current_player()
    bought = Card('PurchasedCard', 'command', {})
    p.deck.discard_pile = [bought]
    g.turn_log['purchased_cards_this_turn'] = [bought]

    p = play_only(g, '行動預告')

    assert p.resources['propaganda'] == 1
    assert names(p.deck.draw_pile)[-1] == 'PurchasedCard'
    assert 'PurchasedCard' not in names(p.deck.discard_pile)


def test_action_fundraising_topdecks_latest_card_bought_this_turn_and_gains_money():
    g = make_game()
    p = g.current_player()
    bought = Card('PurchasedCard', 'command', {})
    p.deck.discard_pile = [bought]
    g.turn_log['purchased_cards_this_turn'] = [bought]

    p = play_only(g, '行動募資')

    assert p.resources['money'] == 1
    assert names(p.deck.draw_pile)[-1] == 'PurchasedCard'
    assert 'PurchasedCard' not in names(p.deck.discard_pile)



def test_end_turn_prompts_action_announcement_and_draws_purchased_card_after_resolution():
    g = make_game()
    p = g.current_player()
    bought = Card('PurchasedCard', 'command', {})
    p.hand = [card(g, '行動預告'), Card('Filler', 'command', {})]
    p.deck.draw_pile = [Card('Bottom1', 'command', {}), Card('Bottom2', 'command', {}), Card('Bottom3', 'command', {}), Card('Bottom4', 'command', {}), Card('Bottom5', 'command', {})]
    p.deck.discard_pile = [bought]
    g.turn_log['purchased_cards_this_turn'] = [bought]
    g.turn_phase = TurnPhase.END

    result = g.advance_turn_phase()

    assert result.get('pending_choice') is True
    assert g.pending_choice and g.pending_choice['type'] == 'option_choice'
    assert g.pending_choice['choice_key'] == 'end_turn_topdeck_action'
    assert [option['label'] for option in g.pending_choice['options']] == ['不使用', '使用 行動預告']
    assert names(p.hand) == ['行動預告', 'Filler']

    resolved = g.resolve_pending_choice(p.id, 1)

    assert resolved.get('success'), resolved
    assert g.turn_phase == TurnPhase.EVENT
    assert 'PurchasedCard' in names(p.hand)
    assert 'PurchasedCard' not in names(p.deck.discard_pile)
    assert '行動預告' in names(p.deck.discard_pile)
    assert any('used 行動預告 before drawing new hand' in line for line in g.action_log)



def test_end_turn_can_skip_action_fundraising_prompt_and_purchased_card_stays_discarded():
    g = make_game()
    p = g.current_player()
    bought = Card('PurchasedCard', 'command', {})
    p.hand = [card(g, '行動募資')]
    p.deck.draw_pile = [Card('Draw1', 'command', {}), Card('Draw2', 'command', {}), Card('Draw3', 'command', {}), Card('Draw4', 'command', {}), Card('Draw5', 'command', {})]
    p.deck.discard_pile = [bought]
    g.turn_log['purchased_cards_this_turn'] = [bought]
    g.turn_phase = TurnPhase.END

    result = g.advance_turn_phase()

    assert result.get('pending_choice') is True
    assert [option['label'] for option in g.pending_choice['options']] == ['不使用', '使用 行動募資']
    resolved = g.resolve_pending_choice(p.id, 0)

    assert resolved.get('success'), resolved
    assert g.turn_phase == TurnPhase.EVENT
    assert 'PurchasedCard' not in names(p.hand)
    assert 'PurchasedCard' in names(p.deck.discard_pile)
    assert any('skipped end-turn action topdeck prompt' in line for line in g.action_log)



def test_negotiation_draws_actor_and_chosen_other_player_only_and_gains_two_propaganda():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '合作談判')]
    p1.deck.draw_pile = [Card('ActorDraw', 'command', {})]
    p2.deck.draw_pile = [Card('TargetDraw', 'command', {})]
    p2.hand = []
    p1.resources = {'money': 0, 'propaganda': 0}

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert names(p1.hand) == ['ActorDraw']
    assert names(p2.hand) == ['TargetDraw']
    assert p1.resources['propaganda'] == 2


def test_fujian_stance_probe_adds_odd_cost_top_card_to_hand():
    g = make_game()
    p = g.current_player()
    p.faction_id = 'fujian'
    p.hand = []
    p.deck.draw_pile = [Card('Bottom', 'command', {}), card(g, '點燃熱情')]

    result = g._activated_faction_action(p, '立場試探')

    assert result.get('success'), result
    assert names(p.hand) == ['點燃熱情']
    assert names(p.deck.discard_pile) == []
    assert g.turn_log.get('faction_action_used') is True



def test_fujian_stance_probe_discards_even_cost_top_card():
    g = make_game()
    p = g.current_player()
    p.faction_id = 'fujian'
    p.hand = []
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('EvenTop', 'command', {'money': 2})]

    result = g._activated_faction_action(p, '立場試探')

    assert result.get('success'), result
    assert names(p.hand) == []
    assert names(p.deck.discard_pile) == ['EvenTop']
    assert g.turn_log.get('faction_action_used') is True



def test_fujian_stance_probe_treats_starter_donor_as_odd_cost_and_adds_it_to_hand():
    g = make_game()
    p = g.current_player()
    p.faction_id = 'fujian'
    p.hand = [Card('Existing', 'command', {})]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('樂捐者', 'money', {'money': 1})]
    p.deck.discard_pile = []

    result = g._activated_faction_action(p, '立場試探')

    assert result.get('success'), result
    assert names(p.hand) == ['Existing', '樂捐者']
    assert names(p.deck.discard_pile) == []
    assert g.action_log[-1] == '[Turn 1] P1 triggered 立場試探 and added 樂捐者 to hand'



def test_underground_party_keeps_one_card_and_returns_the_rest_to_purchase_deck_system():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '地下黨')]
    starting_purchase_count = len(g.purchase_deck.draw_pile) + len(g.purchase_deck.discard_pile)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'underground_party'
    revealed = list(g.pending_choice['cards'])
    chosen_name = names(revealed)[0]
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    assert chosen_name in names(p.hand)
    ending_purchase_count = len(g.purchase_deck.draw_pile) + len(g.purchase_deck.discard_pile)
    assert ending_purchase_count == starting_purchase_count - 1


def test_field_agent_requires_target_org_within_one_step_of_sacrificed_org():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '派遣間諜')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'香港城': 1}

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('error') == 'No target organization within range'
    assert p1.organizations == {'北京': 1}
    assert p2.organizations == {'香港城': 1}



def test_field_agent_prompts_sacrifice_then_target_org_like_north_support():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '派遣間諜')]
    p1.organizations = {'北京': 1, '上海': 1}
    p2.organizations = {'天津': 1, '杭州': 1, '香港城': 1}

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert g.pending_choice and g.pending_choice['type'] == 'support_flow_choice'
    assert g.pending_choice['choice_key'] == 'card_dissolve_interaction'
    assert g.pending_choice['step'] == 'sacrifice_town'
    assert g.pending_choice['source_name'] == '派遣間諜'
    assert g.pending_choice['towns'] == [
        {'town': '北京', 'label': '北京（可瓦解鄰近敵方組織）', 'target_count': 1},
        {'town': '上海', 'label': '上海（可瓦解鄰近敵方組織）', 'target_count': 1},
    ]

    sacrificed = g.resolve_pending_choice(p1.id, 1)

    assert sacrificed.get('success'), sacrificed
    assert sacrificed.get('pending_choice') is True
    assert p1.organizations == {'北京': 1}
    assert g.pending_choice['step'] == 'target'
    assert g.pending_choice['targets'] == [{
        'id': f'{p2.id}::杭州',
        'label': 'P2｜杭州',
        'player_id': p2.id,
        'town': '杭州',
        'sacrifice_town': '上海',
    }]

    resolved = g.resolve_pending_choice(p1.id, 0)

    assert resolved.get('success'), resolved
    assert p1.organizations == {'北京': 1}
    assert p2.organizations.get('杭州', 0) == 0
    assert p2.organizations.get('天津', 0) == 1
    assert p2.organizations.get('香港城', 0) == 1
    assert g.pending_choice is None



def test_embedded_agent_requires_target_org_within_one_step_of_own_org():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '內應間諜')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'香港城': 1}

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('error') == 'No target organization within range'
    assert p1.organizations == {'北京': 1}
    assert p2.organizations == {'香港城': 1}



def test_embedded_agent_prompts_exact_in_range_target_org_without_self_sacrifice():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '內應間諜')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1, '香港城': 1}

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert g.pending_choice and g.pending_choice['type'] == 'support_flow_choice'
    assert g.pending_choice['choice_key'] == 'card_dissolve_interaction'
    assert g.pending_choice['step'] == 'target'
    assert g.pending_choice['source_name'] == '內應間諜'
    assert g.pending_choice['targets'] == [{
        'id': f'{p2.id}::天津',
        'label': 'P2｜天津',
        'player_id': p2.id,
        'town': '天津',
        'requires_self_sacrifice': False,
    }]

    resolved = g.resolve_pending_choice(p1.id, 0)

    assert resolved.get('success'), resolved
    assert p1.organizations == {'北京': 1}
    assert p2.organizations.get('天津', 0) == 0
    assert p2.organizations.get('香港城', 0) == 1
    assert g.pending_choice is None



def test_armed_c_requires_target_player_with_org_within_one_step_of_self_org():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '武裝者')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'香港城': 1}
    p2.hand = [Card('Enemy1', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('error') == 'Target player has no organization within range'
    assert names(p2.hand) == ['Enemy1']
    assert names(p2.deck.discard_pile) == []



def test_armed_c_target_player_chooses_one_discard_when_in_range():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '武裝者')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1}
    p2.hand = [Card('Enemy1', 'command', {}), Card('Enemy2', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'armed_target_discard'
    assert g.pending_choice['player_id'] == p2.id
    assert names(g.pending_choice['cards']) == ['Enemy1', 'Enemy2']
    assert names(p2.hand) == ['Enemy1', 'Enemy2']
    resolved = g.resolve_pending_choice(p2.id, 0)
    assert resolved.get('success'), resolved
    assert names(p2.hand) == ['Enemy2']
    assert names(p2.deck.discard_pile)[-1] == 'Enemy1'
    assert any('P1 used 武裝者 to force P2 to discard Enemy1' in line for line in g.action_log)



def test_armed_b_requires_target_player_with_org_within_one_step_of_self_org():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '武裝小隊')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'香港城': 1}
    p2.hand = [Card('Enemy1', 'command', {}), Card('Enemy2', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('error') == 'Target player has no organization within range'
    assert names(p2.hand) == ['Enemy1', 'Enemy2']
    assert names(p2.deck.discard_pile) == []



def test_armed_b_target_player_chooses_two_discards_when_in_range():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '武裝小隊')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1}
    p2.hand = [Card('Enemy1', 'command', {}), Card('Enemy2', 'command', {}), Card('Enemy3', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert g.pending_choice and g.pending_choice['type'] == 'multi_card_choice'
    assert g.pending_choice['choice_key'] == 'armed_target_discard'
    assert g.pending_choice['player_id'] == p2.id
    assert g.pending_choice['count'] == 2
    assert names(g.pending_choice['cards']) == ['Enemy1', 'Enemy2', 'Enemy3']
    resolved = g.resolve_pending_choice(p2.id, [0, 2])
    assert resolved.get('success'), resolved
    assert names(p2.hand) == ['Enemy2']
    assert names(p2.deck.discard_pile) == ['Enemy1', 'Enemy3']
    assert any('P1 used 武裝小隊 to force P2 to discard 2 card(s)' in line for line in g.action_log)



def test_armed_group_target_player_chooses_two_discards_then_actor_draws():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '武裝集團')]
    p1.organizations = {'北京': 1}
    p1.deck.draw_pile = [Card('RewardDraw', 'command', {})]
    p2.organizations = {'天津': 1}
    p2.hand = [Card('Enemy1', 'command', {}), Card('Enemy2', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert g.pending_choice and g.pending_choice['type'] == 'multi_card_choice'
    assert g.pending_choice['choice_key'] == 'armed_target_discard'
    assert g.pending_choice['player_id'] == p2.id
    assert g.pending_choice['count'] == 2
    assert names(g.pending_choice['cards']) == ['Enemy1', 'Enemy2']
    assert 'RewardDraw' not in names(p1.hand)
    resolved = g.resolve_pending_choice(p2.id, [0, 1])
    assert resolved.get('success'), resolved
    assert names(p2.hand) == []
    assert names(p2.deck.discard_pile) == ['Enemy1', 'Enemy2']
    assert 'RewardDraw' in names(p1.hand)
    assert g.turn_log.get('successful_discard') is True
    assert any('P1 used 武裝集團 to force P2 to discard 2 card(s)' in line for line in g.action_log)


def test_shift_public_opinion_refreshes_random_market_instead_of_using_player_deck_cards():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '輿論丕變')]
    p.deck.draw_pile = [Card('PlayerDeckTop', 'command', {})]
    before_random_market = names(g.purchase_area[6:])

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    after_random_market = names(g.purchase_area[6:])
    assert len(after_random_market) == 5
    assert after_random_market != before_random_market
    assert 'PlayerDeckTop' not in after_random_market
    assert p.resources['propaganda'] == 1


def test_purge_cards_return_removed_cards_to_purchase_deck_system():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '批判'), Card('TrashTarget', 'command', {})]
    starting_purchase_count = len(g.purchase_deck.draw_pile) + len(g.purchase_deck.discard_pile)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['choice_key'] == 'trash_from_hand_or_discard'
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    ending_purchase_count = len(g.purchase_deck.draw_pile) + len(g.purchase_deck.discard_pile)
    assert ending_purchase_count == starting_purchase_count + 1



def test_major_purge_returns_two_removed_cards_to_purchase_deck_system():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '批鬥'), Card('TrashTarget1', 'command', {}), Card('TrashTarget2', 'command', {})]
    starting_purchase_count = len(g.purchase_deck.draw_pile) + len(g.purchase_deck.discard_pile)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['choice_key'] == 'trash_from_hand_or_discard'
    assert g.pending_choice['type'] == 'multi_card_choice'
    resolved = g.resolve_pending_choice(p.id, [0, 1])
    assert resolved.get('success'), resolved
    ending_purchase_count = len(g.purchase_deck.draw_pile) + len(g.purchase_deck.discard_pile)
    assert ending_purchase_count == starting_purchase_count + 2


def test_ignite_passion_draws_two_after_other_propaganda_cost_card_played():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '點燃熱情')]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('FirstDraw', 'command', {}), Card('SecondDraw', 'command', {})]
    g.turn_log['played_propaganda_card'] = True

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert names(p.hand) == ['SecondDraw', 'FirstDraw']



def test_build_confidence_draws_two_after_other_money_cost_card_played():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '樹立信心')]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('FirstDraw', 'command', {}), Card('SecondDraw', 'command', {})]
    g.turn_log['played_money_card'] = True

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert names(p.hand) == ['SecondDraw', 'FirstDraw']



def test_forge_consensus_grants_propaganda_when_both_discards_are_non_starters():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '凝聚共識'), Card('KeepMe', 'command', {})]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('UsefulA', 'command', {}), Card('UsefulB', 'command', {})]
    p.deck.discard_pile = [Card('ExistingDiscard', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert p.resources['propaganda'] == 0
    assert g.pending_choice and g.pending_choice['type'] == 'multi_card_choice'
    assert g.pending_choice['choice_key'] == 'discard_self'
    assert names(g.pending_choice['cards']) == ['KeepMe', 'UsefulB', 'UsefulA', 'Bottom']
    resolved = g.resolve_pending_choice(p.id, [1, 2])
    assert resolved.get('success'), resolved
    assert p.resources['propaganda'] == 2
    assert g.turn_log.get('non_starter_discard') is True
    assert 'KeepMe' in names(p.hand)
    assert 'Bottom' in names(p.hand)
    assert names(p.deck.discard_pile) == ['ExistingDiscard', '凝聚共識', 'UsefulB', 'UsefulA']


def test_forge_consensus_does_not_grant_propaganda_before_pending_choice_or_when_discards_are_starters():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '凝聚共識'), Card('KeepMe', 'command', {})]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('追隨者', 'starter', {}), Card('樂捐者', 'starter', {})]
    p.deck.discard_pile = [Card('ExistingDiscard', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert p.resources['propaganda'] == 0
    assert g.pending_choice and g.pending_choice['type'] == 'multi_card_choice'
    resolved = g.resolve_pending_choice(p.id, [1, 2])
    assert resolved.get('success'), resolved
    assert p.resources['propaganda'] == 0
    assert names(p.deck.discard_pile) == ['ExistingDiscard', '凝聚共識', '樂捐者', '追隨者']



def test_expand_gains_can_choose_any_card_from_own_discard():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '擴大戰果')]
    p.deck.discard_pile = [Card('WantedCard', 'command', {}), Card('TopCard', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'gain_any_from_discard'
    assert names(g.pending_choice['cards']) == ['WantedCard', 'TopCard']
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    assert 'WantedCard' in names(p.hand)
    assert 'TopCard' not in names(p.hand)



def test_business_network_borrows_only_from_random_market_and_keeps_market_card_in_place():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '企業人脈')]
    static_name = names(g.purchase_area[:6])[0]
    random_names = names(g.purchase_area[6:])

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['choice_key'] == 'use_purchase_area_card'
    assert [entry['name'] for entry in g.pending_choice['cards']] == random_names
    assert static_name not in [entry['name'] for entry in g.pending_choice['cards']]
    assert names(g.purchase_area[:6])[0] == static_name
    assert names(g.purchase_area[6:]) == random_names



def test_business_network_borrowed_card_returns_to_purchase_area_after_resource_play():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '企業人脈')]
    random_name = names(g.purchase_area[6:])[0]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['choice_key'] == 'use_purchase_area_card'
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    assert resolved.get('chosen_card') == random_name
    assert random_name not in names(p.deck.discard_pile)
    assert names(g.purchase_area[6:])[0] == random_name



def test_business_network_borrowed_card_returns_to_purchase_area_after_action_play():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '企業人脈')]
    g.purchase_area = [
        card(g, '宣傳家'),
        card(g, '思想家'),
        card(g, '資助者'),
        card(g, '資本家'),
        card(g, '分神'),
        card(g, '內鬥'),
        card(g, '行動預告'),
    ]
    random_name = names(g.purchase_area[6:])[0]
    p.deck.discard_pile = [Card('PurchasedCard', 'command', {})]
    g.turn_log['purchased_cards_this_turn'] = [p.deck.discard_pile[0]]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['choice_key'] == 'use_purchase_area_card'
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    assert resolved.get('chosen_card') == random_name
    assert random_name not in names(p.deck.discard_pile)
    assert names(g.purchase_area[6:])[0] == random_name



def test_industry_infiltration_can_cancel_target_action_card_and_draw_when_canceled_card_has_money_cost():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '擴大戰果')]
    p1.deck.discard_pile = [Card('DiscardTarget', 'command', {})]
    p2.hand = [card(g, '產業滲透')]
    p2.deck.draw_pile = [Card('ReactionDraw', 'command', {})]

    result = g.play_card(0, mode='action', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert names(p1.hand) == []
    assert names(p1.deck.discard_pile)[-1] == '擴大戰果'
    assert 'DiscardTarget' in names(p1.deck.discard_pile)
    assert 'ReactionDraw' in names(p2.hand)
    assert names(p2.deck.discard_pile)[-1] == '產業滲透'
    assert g.turn_log.get('canceled_money_cost_card') is True



def test_industry_infiltration_does_not_draw_when_canceled_card_has_no_money_only_cost():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '凝聚共識')]
    p1.deck.draw_pile = [Card('Bottom', 'command', {}), Card('WouldHaveDrawn', 'command', {})]
    p2.hand = [card(g, '產業滲透')]
    p2.deck.draw_pile = [Card('ReactionDraw', 'command', {})]

    result = g.play_card(0, mode='action', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert 'ReactionDraw' not in names(p2.hand)
    assert g.turn_log.get('canceled_money_cost_card') is None
    assert 'WouldHaveDrawn' in names(p1.hand)



def test_industry_infiltration_requires_an_actual_action_card_target_to_cancel():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [Card('樂捐者', 'money', {'money': 1})]
    p2.hand = [card(g, '產業滲透')]

    result = g.play_card(0, mode='resource', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert names(p2.hand) == ['產業滲透']
    assert names(p2.deck.discard_pile) == []
    assert g.turn_log.get('canceled_money_cost_card') is None



def test_expose_scandal_requires_an_actual_action_card_target_to_cancel():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [Card('追隨者', 'propaganda', {'propaganda': 1})]
    p2.hand = [card(g, '爆料黑幕')]

    result = g.play_card(0, mode='resource', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert names(p1.hand) == []
    assert names(p2.hand) == ['爆料黑幕']
    assert names(p2.deck.discard_pile) == []
    assert g.turn_log.get('canceled_propaganda_card') is None



def test_expose_scandal_cannot_cancel_another_expose_scandal_reaction():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '點燃熱情')]
    p1.deck.draw_pile = [Card('Bottom', 'command', {}), Card('WouldHaveDrawn', 'command', {})]
    p2.hand = [card(g, '爆料黑幕'), card(g, '爆料黑幕')]
    p2.deck.draw_pile = [Card('ReactionDraw', 'command', {})]

    result = g.play_card(
        0,
        mode='action',
        reaction={'player_id': p2.id, 'card_index': 0, 'reaction': {'player_id': p1.id, 'card_index': 0}},
    )

    assert result.get('success'), result
    assert names(p1.hand) == []
    assert names(p1.deck.discard_pile)[-1] == '點燃熱情'
    assert names(p2.hand) == ['爆料黑幕', 'ReactionDraw']
    assert names(p2.deck.discard_pile) == ['爆料黑幕']



def test_expose_scandal_reaction_must_be_from_another_player_holding_expose_scandal():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '點燃熱情')]
    p1.deck.draw_pile = [Card('Bottom', 'command', {}), Card('WouldHaveDrawn', 'command', {})]
    p2.hand = [card(g, '高效行動')]

    result = g.play_card(0, mode='action', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert 'WouldHaveDrawn' in names(p1.hand)
    assert names(p2.hand) == ['高效行動']
    assert names(p2.deck.discard_pile) == []



def test_expose_scandal_can_cancel_target_action_card_and_prevent_its_effect():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '點燃熱情')]
    p1.deck.draw_pile = [Card('Bottom', 'command', {}), Card('WouldHaveDrawn', 'command', {})]
    starting_discard = len(p1.deck.discard_pile)
    p2.hand = [card(g, '爆料黑幕')]
    p2.deck.draw_pile = []

    result = g.play_card(0, mode='action', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert names(p1.hand) == []
    assert len(p1.deck.discard_pile) == starting_discard + 1
    assert names(p1.deck.discard_pile)[-1] == '點燃熱情'
    assert names(p2.hand) == []
    assert names(p2.deck.discard_pile) == ['爆料黑幕']
    assert g.turn_log.get('canceled_propaganda_card') is True



def test_expose_scandal_only_draws_when_canceled_card_has_propaganda_cost():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '擴大戰果')]
    p1.deck.discard_pile = [Card('DiscardTarget', 'command', {})]
    p2.hand = [card(g, '爆料黑幕')]
    p2.deck.draw_pile = [Card('ReactionDraw', 'command', {})]

    result = g.play_card(0, mode='action', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert 'ReactionDraw' not in names(p2.hand)
    assert g.turn_log.get('canceled_propaganda_card') is False



def test_expose_scandal_draws_when_canceled_card_has_propaganda_cost():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '點燃熱情')]
    p1.deck.draw_pile = [Card('Bottom', 'command', {}), Card('WouldHaveDrawn', 'command', {})]
    p2.hand = [card(g, '爆料黑幕')]
    p2.deck.draw_pile = [Card('ReactionDraw', 'command', {})]

    result = g.play_card(0, mode='action', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert 'ReactionDraw' in names(p2.hand)
    assert g.turn_log.get('canceled_propaganda_card') is True



def test_efficient_action_can_choose_any_two_cards_to_discard():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '高效行動'), Card('KeepMe', 'command', {})]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('DrawA', 'command', {}), Card('DrawB', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'multi_card_choice'
    assert g.pending_choice['choice_key'] == 'discard_self'
    assert names(g.pending_choice['cards']) == ['KeepMe', 'DrawB', 'DrawA', 'Bottom']
    resolved = g.resolve_pending_choice(p.id, [1, 2])
    assert resolved.get('success'), resolved
    assert names(p.hand) == ['KeepMe', 'Bottom']
    assert names(p.deck.discard_pile)[-3:] == ['高效行動', 'DrawB', 'DrawA']



def test_thought_building_draws_one_and_extends_build_range_this_turn():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '思想建設')]
    p.deck.draw_pile = [Card('DrawnCard', 'command', {})]
    p.build_range_bonus = 0

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert names(p.hand) == ['DrawnCard']
    assert p.build_range_bonus == 1



def test_strategic_thinker_trashes_self_then_grants_build_and_three_moves():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '思想家')]
    p.organizations = {'北京': 1}
    p.moves_left = 0
    starting_supply = g.static_purchase_supply.get('思想家', 0)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.organizations.get('北京', 0) == 2
    assert p.moves_left == 3
    assert '思想家' not in names(p.deck.discard_pile)
    assert g.static_purchase_supply.get('思想家', 0) == starting_supply + 1



def test_propagandist_trashes_self_then_grants_build_and_one_move():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '宣傳家')]
    p.organizations = {'北京': 1}
    p.moves_left = 0
    starting_supply = g.static_purchase_supply.get('宣傳家', 0)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.organizations.get('北京', 0) == 2
    assert p.moves_left == 1
    assert '宣傳家' not in names(p.deck.discard_pile)
    assert g.static_purchase_supply.get('宣傳家', 0) == starting_supply + 1



def test_capitalist_trashes_self_and_grants_three_money_and_three_propaganda():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '資本家')]
    p.resources = {'money': 0, 'propaganda': 0}
    starting_supply = g.static_purchase_supply.get('資本家', 0)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.resources == {'money': 3, 'propaganda': 3}
    assert '資本家' not in names(p.deck.discard_pile)
    assert g.static_purchase_supply.get('資本家', 0) == starting_supply + 1



def test_funder_trashes_self_and_grants_two_money_and_two_propaganda():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '資助者')]
    p.resources = {'money': 0, 'propaganda': 0}
    starting_supply = g.static_purchase_supply.get('資助者', 0)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.resources == {'money': 2, 'propaganda': 2}
    assert '資助者' not in names(p.deck.discard_pile)
    assert g.static_purchase_supply.get('資助者', 0) == starting_supply + 1



def test_distraction_trashes_self_and_returns_to_static_supply():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '分神')]
    starting_supply = g.static_purchase_supply.get('分神', 0)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert '分神' not in names(p.deck.discard_pile)
    assert g.static_purchase_supply.get('分神', 0) == starting_supply + 1



def test_leadership_draws_one_card():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '領導')]
    p.deck.draw_pile = [Card('Draw1', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert names(p.hand) == ['Draw1']



def test_leadership_reshuffles_discard_to_draw_after_reaction_skip_and_can_advance():
    g = make_game()
    actor, reactor = g.players
    actor.hand = [card(g, '領導')]
    actor.deck.draw_pile = []
    actor.deck.discard_pile = [Card('DiscardDraw1', 'command', {})]
    reactor.hand = [card(g, '爆料黑幕')]

    prompted = g.play_card(0, mode='action')

    assert prompted.get('pending_choice') is True, prompted
    assert g.pending_choice and g.pending_choice['type'] == 'reaction_choice'
    assert g.pending_choice['player_name'] == reactor.name
    assert names(actor.hand) == []
    assert any('played 領導; waiting up to 10 seconds for P2 to choose cancel reaction' in entry for entry in g.action_log)

    skipped = g.resolve_pending_choice(reactor.id, 0)

    assert skipped.get('success'), skipped
    assert skipped.get('skipped_reaction') is True
    assert g.pending_choice is None
    assert names(actor.hand) == ['DiscardDraw1']
    assert names(actor.deck.discard_pile) == ['領導']
    advanced = g.advance_turn_phase()
    assert advanced.get('success'), advanced
    assert g.turn_phase == TurnPhase.END



def test_plotting_draws_two_cards():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '謀劃')]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('Draw1', 'command', {}), Card('Draw2', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert names(p.hand) == ['Draw2', 'Draw1']



def test_strategy_draws_three_cards():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '戰略')]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('Draw1', 'command', {}), Card('Draw2', 'command', {}), Card('Draw3', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert names(p.hand) == ['Draw3', 'Draw2', 'Draw1']



def test_transport_c_grants_two_moves():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '交通經驗丙')]
    p.moves_left = 0

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.moves_left == 2



def test_transport_b_grants_four_moves():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '交通經驗乙')]
    p.moves_left = 0

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.moves_left == 4



def test_transport_a_grants_six_moves():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '交通經驗甲')]
    p.moves_left = 0

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.moves_left == 6



def test_organization_c_builds_one_in_current_town():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '組織經驗丙')]
    p.organizations = {'北京': 1}

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.organizations.get('北京', 0) == 2



def test_organization_b_builds_two_in_current_town():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '組織經驗乙')]
    p.organizations = {'北京': 1}

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.organizations.get('北京', 0) == 3



def test_organization_a_builds_one_even_with_ignore_distance_flag():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '組織經驗甲')]
    p.organizations = {'北京': 1}

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.organizations.get('北京', 0) == 2



def test_press_advantage_only_gains_card_costing_three_or_less_from_discard():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '乘勝追擊')]
    cheap = Card('CheapTarget', 'command', {})
    expensive = Card('ExpensiveTarget', 'command', {})
    p.deck.discard_pile = [cheap, expensive]
    g.structured_cards.append({'name': 'CheapTarget', 'cost': {'money': 2, 'propaganda': 0}})
    g.structured_cards.append({'name': 'ExpensiveTarget', 'cost': {'money': 4, 'propaganda': 0}})

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'gain_from_discard'
    assert names(g.pending_choice['cards']) == ['CheapTarget']
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    assert 'CheapTarget' in names(p.hand)
    assert 'ExpensiveTarget' not in names(p.hand)
    assert 'ExpensiveTarget' in names(p.deck.discard_pile)



def test_missing_cards_exist_in_structured_action_data():
    g = make_game()
    structured = {c['name']: c for c in g.structured_cards}
    for name in ['企業人脈', '產業滲透', '企畫遊說', '行動募資', '點燃熱情', '樹立信心', '凝聚共識', '擴大戰果', '爆料黑幕', '乘勝追擊']:
        assert name in structured
        assert structured[name].get('effect'), name


def test_planning_lobby_reveals_top_card_cost_and_grants_correct_money():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '企畫遊說')]
    p.deck.draw_pile = [Card('CheapBottom', 'command', {}), Card('ExpensiveTop', 'command', {})]
    # Make ExpensiveTop cost >= 3 via structured card lookup name.
    g.structured_cards.append({'name': 'ExpensiveTop', 'cost': {'money': 3, 'propaganda': 0}})

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.resources['money'] == 4
    assert names(p.deck.draw_pile)[-1] == 'ExpensiveTop'



def test_criticism_prompts_player_to_choose_card_from_hand_or_discard_then_trashes_selected_card():
    g = make_game()
    p = g.current_player()
    selected = Card('SelectedDiscard', 'command', {})
    other_discard = Card('OtherDiscard', 'command', {})
    hand_keep = Card('HandKeep', 'command', {})
    p.hand = [card(g, '批判'), hand_keep]
    p.deck.discard_pile = [selected, other_discard]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['choice_key'] == 'trash_from_hand_or_discard'
    assert g.pending_choice['type'] == 'card_choice'
    pending_cards = g.pending_choice['cards']
    assert [entry['zone'] for entry in pending_cards] == ['hand', 'discard', 'discard']
    assert [getattr(entry['card'], 'name', str(entry['card'])) for entry in pending_cards] == ['HandKeep', 'SelectedDiscard', 'OtherDiscard']

    resolved = g.resolve_pending_choice(p.id, 1)
    assert resolved.get('success'), resolved
    assert resolved.get('chosen_card') == 'SelectedDiscard'
    assert resolved.get('zone') == 'discard'
    assert 'SelectedDiscard' not in names(p.deck.discard_pile)
    assert 'OtherDiscard' in names(p.deck.discard_pile)
    assert 'HandKeep' in names(p.hand)
    assert g.pending_choice is None


if __name__ == '__main__':
    tests = [obj for name, obj in globals().items() if name.startswith('test_')]
    failures = 0
    for test in tests:
        try:
            test()
            print(f'PASS {test.__name__}')
        except Exception as exc:
            failures += 1
            print(f'FAIL {test.__name__}: {exc}')
    if failures:
        raise SystemExit(1)


def test_intel_network_first_option_adds_internal_conflict_to_up_to_three_other_players_only():
    g = Game([('p1', 'viewer'), ('p2', 'enemyA'), ('p3', 'enemyB'), ('p4', 'enemyC')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    actor, enemy_a, enemy_b, enemy_c = g.players
    actor.faction_id = 'red_army'
    for player in g.players[1:]:
        player.faction_id = 'hong_kong'
    actor.hand = [card(g, '情報網')]
    for player in g.players:
        player.deck.discard_pile = []

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert g.pending_choice and g.pending_choice['type'] == 'option_choice'

    resolved = g.resolve_pending_choice(actor.id, 0)

    assert resolved.get('success'), resolved
    assert names(actor.deck.discard_pile) == ['情報網']
    assert names(enemy_a.deck.discard_pile) == ['內鬥']
    assert names(enemy_b.deck.discard_pile) == ['內鬥']
    assert names(enemy_c.deck.discard_pile) == ['內鬥']
    assert g.pending_choice is None
