from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game


def make_game(player_count=3):
    players = [(f'p{i}', f'P{i}') for i in range(player_count)]
    game = Game(players)
    for player in game.players:
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
