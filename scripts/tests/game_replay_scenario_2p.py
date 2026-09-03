"""A deterministic 2-player scenario for game_replay_harness.py.

Self-contained (doesn't import scripts/validate/validate_full_gameplay_2p.py)
so this regression fixture doesn't depend on that script's own evolution —
the two serve different purposes (that one is a one-off smoke-test/report
generator; this one is a committed baseline for diffing refactors against).
"""

from server.game import Game, TurnPhase, GamePhase


def _resolve_base_selection(game, capture):
    if game.game_phase != GamePhase.BASE_SELECTION:
        return
    for pid, choice_data in list(game.pending_base_choices.items()):
        labels = choice_data.get('labels', [])
        resolved = choice_data.get('resolved', {})
        for label in labels:
            for town in resolved.get(label, []):
                result = game.set_base_choice(pid, town, label=label)
                if result.get('success'):
                    break
            else:
                continue
            break
    capture(game, 'base_selection_resolved')


def _resolve_pending_choice(game, capture, label):
    choice = game.pending_choice
    if not choice:
        return False
    player_id = choice.get('player_id')
    choice_type = choice.get('type')
    if choice_type == 'multi_card_choice':
        min_count = int(choice.get('min_count', choice.get('count', 0)) or 0)
        index = list(range(min_count))
    else:
        index = 0
    game.resolve_pending_choice(player_id, index)
    capture(game, label, {'choice_key': choice.get('choice_key'), 'choice_type': choice_type})
    return True


def _advance_to_action(game, capture, cycle):
    safety = 0
    while game.turn_phase == TurnPhase.EVENT and safety < 8:
        if game.pending_choice:
            _resolve_pending_choice(game, capture, f'cycle_{cycle}_event_choice')
        else:
            game.advance_turn_phase()
            capture(game, f'cycle_{cycle}_advance_event_step')
        safety += 1


def _drain_pending_choices(game, capture, label, limit=6):
    """Resolve chained pending choices (e.g. a card-triggered build, then a
    reaction prompt) the way a real client would, instead of stalling."""
    count = 0
    while game.pending_choice and count < limit:
        _resolve_pending_choice(game, capture, f'{label}_choice_{count}')
        count += 1


def _force_deterministic_setup(game):
    anti, red = game.players
    anti.name = 'anti'
    anti.faction_id = 'hong_kong'
    anti.base = '香港城'
    anti.organizations = {'香港城': 1}
    red.name = 'red'
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.EVENT
    return anti, red


def _card_has_build_effect(game, card_name):
    for entry in game.structured_cards:
        if entry.get('name') == card_name:
            return any((eff or {}).get('type') == 'build' for eff in entry.get('effect', []) or [])
    return False


def _play_one_card(game, player):
    """If a build-capable card is in hand, play it (mode='action') so its
    build effect actually fires. Otherwise cash in card 0's printed
    resource (mode='action' silently no-ops on pure resource cards instead
    of erroring, so 'resource' mode is the only way to see an effect)."""
    if not player.hand:
        return None
    build_index = next(
        (i for i, c in enumerate(player.hand) if _card_has_build_effect(game, getattr(c, 'name', None))),
        None,
    )
    if build_index is not None:
        return game.play_card(build_index, mode='action')
    return game.play_card(0, mode='resource')


def scenario(capture):
    game = Game([('p1', 'anti'), ('p2', 'red')])
    _resolve_base_selection(game, capture)
    _force_deterministic_setup(game)
    capture(game, 'init')

    for cycle in range(1, 17):
        _advance_to_action(game, capture, cycle)
        player = game.current_player()

        played = 0
        while player.hand and played < 3:
            _play_one_card(game, player)
            played += 1
            _drain_pending_choices(game, capture, f'cycle_{cycle}_play_{played}')
        capture(game, f'cycle_{cycle}_play_card')

        for from_town in list(player.organizations.keys()):
            if from_town == player.base and player.organizations.get(from_town, 0) <= 1:
                continue
            town = game.map['towns'].get(from_town, {})
            moved = False
            for mode in ('road', 'rail'):
                for target in list(town.get(mode) or []):
                    game.move_organization(from_town, target, mode)
                    moved = True
                    break
                if moved:
                    break
            if moved:
                break
        capture(game, f'cycle_{cycle}_move')

        if game.purchase_area:
            affordable = [
                i for i, card in enumerate(game.purchase_area)
                if game._player_can_afford_purchase(player, card)
            ]
            if affordable:
                game.buy_cards(affordable[:2])
                _drain_pending_choices(game, capture, f'cycle_{cycle}_buy')
        capture(game, f'cycle_{cycle}_buy')

        game.advance_turn_phase()
        _drain_pending_choices(game, capture, f'cycle_{cycle}_end_turn')
        capture(game, f'cycle_{cycle}_end_turn')

    game._check_victory()
    capture(game, 'final')
