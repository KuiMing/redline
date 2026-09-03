"""A 4-player scenario for game_replay_harness.py targeting the generic
activated-ability branches of `_activated_faction_action` — 民主陣線/
立場試探/賭徒耳語 (紅軍派系 and 民族祭儀 are not covered by this scenario;
see the module docstring bottom for why).

These don't resolve to a `name` field directly on any faction's raw
ability list — they're reached via the ability alias/ref-template system
(server/game_faction_rules.py), so finding holders required querying
Game._player_effective_abilities(...) directly rather than grepping
data/factions/*.json for the literal ability name (that grep comes back
empty and is misleading). Verified holders: liberals -> 立場試探,
minyun -> 民主陣線, aomen -> 賭徒耳語.

紅軍派系 (reform_opening) and 民族祭儀 (11 factions, e.g. hani) don't fit
in the same 4-player slot as red_army (mandatory in any 2+ player game)
plus these three — left for a follow-up scenario if a future PR needs it.
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


def _drain_pending_choices(game, capture, label, limit=6):
    count = 0
    while game.pending_choice and count < limit:
        _resolve_pending_choice(game, capture, f'{label}_choice_{count}')
        count += 1


def _advance_to_action(game, capture, cycle):
    safety = 0
    while game.turn_phase == TurnPhase.EVENT and safety < 8:
        if game.pending_choice:
            _resolve_pending_choice(game, capture, f'cycle_{cycle}_event_choice')
        else:
            game.advance_turn_phase()
            capture(game, f'cycle_{cycle}_advance_event_step')
        safety += 1


def _force_deterministic_setup(game):
    liberals, minyun, aomen, red = game.players
    liberals.name = 'liberals'
    liberals.faction_id = 'liberals'
    liberals.base = '三亞'
    liberals.organizations = {'三亞': 1}
    minyun.name = 'minyun'
    minyun.faction_id = 'minyun'
    minyun.base = '巴黎'
    minyun.organizations = {'巴黎': 1}
    # 民主陣線 requires >= 2 total resources; seed directly rather than
    # depending on natural resource-card draws landing before its turn.
    minyun.resources = {'money': 1, 'propaganda': 1}
    aomen.name = 'aomen'
    aomen.faction_id = 'aomen'
    aomen.base = '澳門'
    aomen.organizations = {'澳門': 1}
    red.name = 'red'
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.EVENT
    return liberals, minyun, aomen, red


def scenario(capture):
    game = Game([('p1', 'liberals'), ('p2', 'minyun'), ('p3', 'aomen'), ('p4', 'red')])
    _resolve_base_selection(game, capture)
    liberals, minyun, aomen, red = _force_deterministic_setup(game)
    capture(game, 'init')

    for cycle in range(1, 13):
        _advance_to_action(game, capture, cycle)
        player = game.current_player()

        if player is liberals:
            game._activated_faction_action(player, '立場試探')
            _drain_pending_choices(game, capture, f'cycle_{cycle}_liberals_action')
            capture(game, f'cycle_{cycle}_liberals_action_attempted')
        elif player is minyun:
            game._activated_faction_action(player, '民主陣線')
            _drain_pending_choices(game, capture, f'cycle_{cycle}_minyun_action')
            capture(game, f'cycle_{cycle}_minyun_action_attempted')
        elif player is aomen:
            game._activated_faction_action(player, '賭徒耳語', guess='odd')
            _drain_pending_choices(game, capture, f'cycle_{cycle}_aomen_action')
            capture(game, f'cycle_{cycle}_aomen_action_attempted')
        else:
            played = 0
            while player.hand and played < 2:
                game.play_card(0, mode='resource')
                played += 1

        game.advance_turn_phase()
        _drain_pending_choices(game, capture, f'cycle_{cycle}_end_turn')
        capture(game, f'cycle_{cycle}_end_turn')

    capture(game, 'final')
