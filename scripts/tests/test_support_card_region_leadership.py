from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, TurnPhase


def make_game(player_count=3):
    players = [(f'p{i}', f'P{i}') for i in range(player_count)]
    game = Game(players)
    deterministic_factions = ['red_army', 'liberals', 'taiwan_green', 'tibet_dehradun']
    for index, player in enumerate(game.players):
        player.faction_id = deterministic_factions[index]
        player.organizations = {}
    return game


def towns_for(game, ruler):
    return [
        town
        for town, data in game.map.get('towns', {}).items()
        if ruler in (data.get('ruler', []) or [])
    ]


def place_region_counts(game, ruler, counts):
    towns = towns_for(game, ruler)
    assert len(towns) >= sum(counts), (ruler, len(towns), counts)
    cursor = 0
    for player, count in zip(game.players, counts):
        for town in towns[cursor:cursor + count]:
            player.organizations[town] = 1
        cursor += count


def test_all_support_variants_require_region_leadership_for_tier_two_and_three():
    template = make_game()
    entries = [
        entry for entry in template.support_taxonomy
        if entry.get('regions') and not template._is_starter_support_card(entry.get('name'))
    ]
    assert [entry['name'] for entry in entries] == [
        '英美奧援', '東洋奧援', '南洋奧援', '印度奧援',
        '天方奧援', '歐洲奧援', '北國奧援', '臺灣奧援',
    ]

    for entry in entries:
        for variant_index, variant in enumerate(entry['regions']):
            card_name = entry['name']
            preferred = variant['preferred_rulers']
            support_region = entry['support_region']

            # Presence is insufficient: actor has one organization, another player has two.
            game = make_game()
            card = game._make_support_card(card_name, variant_index=variant_index)
            place_region_counts(game, preferred[0], [1, 2, 0])
            assert game._support_card_tier(game.players[0], card) == (1, variant_index, []), (
                card_name, variant_index, preferred[0], 'presence must not grant tier II'
            )

            # Ties count as "has the most": one organization each grants tier II.
            game = make_game()
            card = game._make_support_card(card_name, variant_index=variant_index)
            place_region_counts(game, preferred[0], [1, 1, 0])
            assert game._support_card_tier(game.players[0], card) == (
                2, variant_index, [preferred[0]]
            ), (card_name, variant_index, preferred[0], 'co-leader must grant tier II')

            # The same comparison applies to the card's own support region for tier III.
            game = make_game()
            card = game._make_support_card(card_name, variant_index=variant_index)
            place_region_counts(game, support_region, [1, 2, 0])
            assert game._support_card_tier(game.players[0], card) == (1, variant_index, []), (
                card_name, variant_index, support_region, 'presence must not grant tier III'
            )

            game = make_game()
            card = game._make_support_card(card_name, variant_index=variant_index)
            place_region_counts(game, support_region, [1, 1, 0])
            assert game._support_card_tier(game.players[0], card) == (3, variant_index, []), (
                card_name, variant_index, support_region, 'co-leader must grant tier III'
            )


def test_tier_two_keeps_or_semantics_but_matches_only_regions_where_actor_is_a_leader():
    game = make_game()
    actor, rival, third = game.players
    card = game._make_support_card('北國奧援', variant_index=0)  # 歐洲／東洋

    place_region_counts(game, '歐洲', [1, 2, 0])
    place_region_counts(game, '東洋', [1, 1, 0])

    assert game._support_card_tier(actor, card) == (2, 0, ['東洋'])


def test_zero_organizations_never_counts_as_tied_for_most():
    game = make_game()
    actor = game.players[0]
    card = game._make_support_card('英美奧援', variant_index=0)

    assert game._support_card_tier(actor, card) == (1, 0, [])


def test_shared_physical_organization_counts_for_each_sharing_player_region_leadership():
    game = make_game()
    actor, sharing_partner, rival = game.players
    actor.faction_id = 'hong_kong'
    sharing_partner.faction_id = 'yue'
    rival.faction_id = 'red_army'

    # The 粵-owned Paris organization is shared with 香港 and therefore counts as one
    # European organization for the actor. Rival owns one separate European organization:
    # actor is a co-leader and qualifies for tier II.
    sharing_partner.organizations = {'巴黎': 1}
    rival.organizations = {'日內瓦': 1}
    actor.organizations = {}
    card = game._make_support_card('英美奧援', variant_index=0)  # 歐洲／天方

    assert game._organization_towns_for_player(actor) == ['巴黎']
    assert game._support_card_tier(actor, card) == (2, 0, ['歐洲'])


def test_purchased_support_card_keeps_variant_through_discard_shuffle_and_draw():
    game = make_game()
    actor = game.current_player()
    actor.organizations = {'東京': 1}
    game.players[1].organizations = {}
    game.players[2].organizations = {}
    actor.resources = {'money': 5, 'propaganda': 5}
    actor.hand = []
    actor.deck.draw_pile = []
    actor.deck.discard_pile = []
    game.turn_phase = TurnPhase.END

    static_cards = game._static_purchase_cards()
    market_card = game._make_support_card('英美奧援', variant_index=1)  # II：東洋／臺灣
    game.purchase_area = static_cards + [market_card]

    result = game.buy_cards([len(static_cards)])

    assert result.get('success'), result
    purchased = actor.deck.discard_pile[-1]
    assert getattr(purchased, 'variant_index', None) == 1
    assert game._support_card_variant_info(purchased)['tier2_regions'] == ['東洋', '臺灣']

    drawn = actor.deck.draw(1)
    assert len(drawn) == 1
    actor.hand.extend(drawn)
    assert getattr(actor.hand[0], 'variant_index', None) == 1
    assert game._support_card_tier(actor, actor.hand[0]) == (2, 1, ['東洋'])


def test_purchase_area_copy_preserves_support_variant_without_adding_it_to_normal_cards():
    game = make_game()
    support = game._make_support_card('北國奧援', variant_index=1)
    borrowed_copy = game._copy_purchase_card(support)

    assert getattr(borrowed_copy, 'variant_index', None) == 1
    assert game._support_card_variant_info(borrowed_copy)['tier2_regions'] == ['天方', '印度']

    normal = Card('一般牌', 'command', {'money': 1})
    normal_copy = game._copy_purchase_card(normal)
    assert not hasattr(normal_copy, 'variant_index')
