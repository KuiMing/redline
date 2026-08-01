from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase


def negotiation_card(game):
    definition = next(card for card in game.structured_cards if card['name'] == '合作談判')
    return Card(definition['name'], definition['type'], definition.get('resources', {}))


def make_game():
    game = Game([('actor', 'Actor'), ('ally', 'Ally'), ('enemy', 'Enemy'), ('observer', 'Observer')])
    actor, ally, enemy, observer = game.players
    actor.faction_id = 'liberals'
    ally.faction_id = 'hong_kong'
    enemy.faction_id = 'red_army'
    observer.faction_id = 'taiwan_green'
    actor.hand = [negotiation_card(game)]
    actor.deck.draw_pile = [Card('ActorDraw', 'command', {})]
    ally.deck.draw_pile = [Card('AllyDraw', 'command', {})]
    enemy.deck.draw_pile = [Card('EnemyDraw', 'command', {})]
    observer.deck.draw_pile = [Card('ObserverDraw', 'command', {})]
    for player in game.players:
        if player is not actor:
            player.hand = []
        player.deck.discard_pile = []
        player.resources = {'money': 0, 'propaganda': 0}
    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.pending_base_choices = {}
    game.pending_choice = None
    game._player_effective_abilities = lambda player: []
    noop = game._event_by_name('歲月靜好')
    game.current_event = dict(noop or {})
    game.event_progress = {'count': 0, 'required': 0, 'succeeded': True, 'settled': True, 'status': 'idle'}
    game.event_notification = game._event_display_payload()
    return game


def snapshot(game):
    return {
        'hands': {player.id: [card.name for card in player.hand] for player in game.players},
        'decks': {player.id: [card.name for card in player.deck.draw_pile] for player in game.players},
        'discards': {player.id: [card.name for card in player.deck.discard_pile] for player in game.players},
        'resources': {player.id: dict(player.resources) for player in game.players},
        'pending_choice': game.pending_choice,
        'action_log': list(game.action_log),
    }


def test_negotiation_can_target_enemy_and_only_actor_and_enemy_draw():
    game = make_game()
    actor, ally, enemy, observer = game.players

    result = game.play_card(0, mode='action', target_player_id=enemy.id)

    assert result.get('success') is True, result
    assert [card.name for card in actor.hand] == ['ActorDraw']
    assert [card.name for card in enemy.hand] == ['EnemyDraw']
    assert ally.hand == []
    assert observer.hand == []
    assert [card.name for card in ally.deck.draw_pile] == ['AllyDraw']
    assert [card.name for card in observer.deck.draw_pile] == ['ObserverDraw']
    assert actor.resources == {'money': 0, 'propaganda': 2}
    assert enemy.resources == {'money': 0, 'propaganda': 0}
    assert [card.name for card in actor.deck.discard_pile] == ['合作談判']


@pytest.mark.parametrize('target_player_id', [None, 'actor', 'missing-player'])
def test_negotiation_rejects_missing_self_or_unknown_target_without_mutation(target_player_id):
    game = make_game()
    before = snapshot(game)

    result = game.play_card(0, mode='action', target_player_id=target_player_id)

    assert result.get('error') == '合作談判必須指定任意一名其他玩家'
    assert snapshot(game) == before
