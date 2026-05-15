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
    return [getattr(c, 'name', str(c)) for c in cards]


def play_only(g, name):
    p = g.current_player()
    p.hand = [card(g, name)]
    p.resources = {'money': 0, 'propaganda': 0}
    result = g.play_card(0, mode='action')
    assert result.get('success'), result
    return p


def test_recruit_talent_selects_any_card_from_own_deck_not_topdeck_only():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '網羅人才')]
    # Deck top is TopCard (last element). DesiredCard is deliberately not on top.
    p.deck.draw_pile = [Card('DesiredCard', 'command', {}), Card('MiddleCard', 'command', {}), Card('TopCard', 'command', {})]
    p.deck.discard_pile = []

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'recruit_talent'
    assert names(g.pending_choice['cards']) == ['DesiredCard', 'MiddleCard', 'TopCard']
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    assert 'DesiredCard' in names(p.hand)
    assert 'TopCard' not in names(p.hand)


def test_lure_exhaustion_draws_then_self_removes_and_sets_successful_discard():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '誘導虛耗')]
    p2.hand = [Card('EnemyCard', 'command', {})]
    p1.deck.draw_pile = [Card('DrawnCard', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert names(p1.hand) == ['DrawnCard']
    assert '誘導虛耗' not in names(p1.deck.discard_pile)
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



def test_intel_network_runs_only_one_default_option_not_cancel_too():
    g = make_game()
    p = play_only(g, '情報網')

    assert g.pending_choice and g.pending_choice['type'] == 'option_choice'
    assert g.pending_choice['choice_key'] == 'choose_one'
    assert len(g.pending_choice['options']) == 3
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    assert names(p.deck.discard_pile).count('內鬥') == 1
    assert not g.turn_log.get('canceled_propaganda_card')



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



def test_armed_c_discards_one_when_target_player_has_org_within_one_step():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '武裝者')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1}
    p2.hand = [Card('Enemy1', 'command', {}), Card('Enemy2', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert names(p2.hand) == ['Enemy1']
    assert names(p2.deck.discard_pile)[-1] == 'Enemy2'



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



def test_armed_group_draws_after_successful_enemy_discard():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '武裝集團')]
    p1.organizations = {'北京': 1}
    p1.deck.draw_pile = [Card('RewardDraw', 'command', {})]
    p2.organizations = {'天津': 1}
    p2.hand = [Card('Enemy1', 'command', {}), Card('Enemy2', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert names(p2.hand) == []
    assert names(p2.deck.discard_pile) == ['Enemy2', 'Enemy1']
    assert 'RewardDraw' in names(p1.hand)
    assert g.turn_log.get('successful_discard') is True


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
