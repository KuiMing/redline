from pathlib import Path
import asyncio
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server import main as server_main


def make_game():
    g = Game([('actor', 'actor'), ('reactor', 'reactor')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    # Game initialization may randomly draw an interactive event and create its own
    # pending choice. Reaction privacy tests must start from a neutral action state.
    g.pending_choice = None
    return g


def card(g, name):
    card_def = next(c for c in g.structured_cards if c['name'] == name)
    return Card(card_def['name'], card_def['type'], card_def.get('resources', {}))


def names(cards):
    return [getattr(c, 'name', str(c)) for c in cards]


def test_reaction_choice_projection_hides_reaction_cards_from_non_reactor():
    g = make_game()
    actor, reactor = g.players
    actor.hand = [card(g, '領導')]
    actor.deck.draw_pile = [Card('Draw1', 'command', {})]
    reactor.hand = [card(g, '爆料黑幕')]

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    actor_state = g.state(actor.id)
    reactor_state = g.state(reactor.id)
    assert actor_state['pending_choice']['type'] == 'reaction_choice'
    assert actor_state['pending_choice']['cards'] == []
    assert actor_state['pending_choice']['source_name'] == '等待反應'
    assert '爆料黑幕' not in str(actor_state['pending_choice'])
    assert actor_state['players'][1]['hand'] == ['未知手牌']
    assert reactor_state['players'][1]['hand'] == ['爆料黑幕']
    assert reactor_state['pending_choice']['cards'] == [{'name': '爆料黑幕', 'card_index': 0}]


def test_reaction_choice_projection_includes_target_player_for_reactor():
    g = Game([('actor', 'actor'), ('bystander', 'bystander'), ('reactor', 'reactor')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    g.pending_choice = None
    actor, bystander, reactor = g.players
    actor.hand = [card(g, '誘導虛耗')]
    actor.deck.draw_pile = [Card('DrawnCard', 'command', {})]
    reactor.hand = [card(g, '爆料黑幕')]

    result = g.play_card(0, mode='action', target_player_id=bystander.id)

    assert result.get('pending_choice') is True, result
    reactor_state = g.state(reactor.id)
    assert reactor_state['pending_choice']['type'] == 'reaction_choice'
    assert reactor_state['pending_choice']['target_player_id'] == bystander.id
    assert reactor_state['pending_choice']['target_player_name'] == bystander.name


def test_reaction_choice_auto_skips_after_timeout_and_resolves_action():
    async def run_case():
        g = make_game()
        actor, reactor = g.players
        actor.hand = [card(g, '領導')]
        actor.deck.draw_pile = []
        actor.deck.discard_pile = [Card('DiscardDraw1', 'command', {})]
        reactor.hand = [card(g, '爆料黑幕')]
        game_id = 'reaction-timeout-test'
        old_timeout = server_main.REACTION_RESPONSE_TIMEOUT_SECONDS
        server_main.REACTION_RESPONSE_TIMEOUT_SECONDS = 0.01
        server_main.manager.games[game_id] = g
        server_main.manager.connections[game_id] = {}
        try:
            prompted = g.play_card(0, mode='action')
            assert prompted.get('pending_choice') is True, prompted
            server_main.schedule_reaction_timeout(game_id, g)
            await asyncio.sleep(0.05)
            assert g.pending_choice is None
            assert names(actor.hand) == ['DiscardDraw1']
            assert names(actor.deck.discard_pile) == ['領導']
            assert names(reactor.hand) == ['爆料黑幕']
            assert any('timed out' in entry and 'treated as no cancel' in entry for entry in g.action_log)
        finally:
            server_main.REACTION_RESPONSE_TIMEOUT_SECONDS = old_timeout
            task = server_main.reaction_timeout_tasks.pop(game_id, None)
            if task:
                task.cancel()
            server_main.manager.games.pop(game_id, None)
            server_main.manager.connections.pop(game_id, None)

    asyncio.run(run_case())
