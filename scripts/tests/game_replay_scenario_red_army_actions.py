"""A 4-player scenario for game_replay_harness.py targeting red army's
activated special actions (統戰部/政工部/國安部/中紀委) inside
`_activated_faction_action` — the part of item 21
(extract-faction-ability-service) not covered by
game_replay_scenario_faction_abilities.py (which only exercises the
card-play/turn-end ability dispatchers, not this one).

Same 4-player cast as that scenario (tibet_dharamsala/manchuria/kazakh/
red_army) so red army has valid non-red targets for 政工部/國安部. Explicitly
calls `game._activated_faction_action(...)` on red army's own turns instead
of relying on organic play, since `_red_army_action_limit()` caps usable
actions per turn at `len(non_red_players)` (3 here) and each of 政工部/國安部
is further capped at once per (action, target) pair per turn — natural play
is very unlikely to happen to trigger a specific one of the 4 named actions.

NOT covered: the generic activated abilities in the same dispatcher
(民主陣線/紅軍派系/立場試探/賭徒耳語/民族祭儀) — those are a separate,
later PR per the coordinator's split.
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
    tibet, manchuria, kazakh, red = game.players
    tibet.name = 'tibet'
    tibet.faction_id = 'tibet_dharamsala'
    tibet.base = '達蘭薩拉'
    # Also seed an organization in 天津 — inside the "china" region alias and
    # within 1 step of red army's 北京 base — the exact condition
    # _red_army_state_security_targets() requires. Without a target meeting
    # both conditions simultaneously, 國安部 always returns a no-op
    # "no_dissolve_target" result and this scenario can't exercise it; none
    # of the three non-red factions' natural starting bases satisfy this.
    tibet.organizations = {'達蘭薩拉': 1, '天津': 1}
    manchuria.name = 'manchuria'
    manchuria.faction_id = 'manchuria'
    manchuria.base = '東京'
    manchuria.organizations = {'東京': 1}
    kazakh.name = 'kazakh'
    kazakh.faction_id = 'kazakh'
    kazakh.base = '阿拉木圖'
    kazakh.organizations = {'阿拉木圖': 1}
    red.name = 'red'
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.EVENT
    return tibet, manchuria, kazakh, red


# 統戰部/政工部/國安部/中紀委, cycled one per red army turn so each gets its
# own turn (the per-target-per-action once-per-turn cap on 政工部/國安部
# means trying two of those on the same target in one turn would no-op the
# second anyway).
_RED_ARMY_ACTIONS_IN_ORDER = ['統戰部', '政工部', '國安部', '中紀委']


def scenario(capture):
    game = Game([('p1', 'tibet'), ('p2', 'manchuria'), ('p3', 'kazakh'), ('p4', 'red')])
    _resolve_base_selection(game, capture)
    tibet, manchuria, kazakh, red = _force_deterministic_setup(game)
    capture(game, 'init')

    red_turn_index = 0
    for cycle in range(1, 21):
        _advance_to_action(game, capture, cycle)
        player = game.current_player()

        if player is red:
            action_name = _RED_ARMY_ACTIONS_IN_ORDER[red_turn_index % len(_RED_ARMY_ACTIONS_IN_ORDER)]
            red_turn_index += 1
            kwargs = {}
            if action_name in {'政工部', '國安部'}:
                kwargs['target_player_id'] = tibet.id
            game._activated_faction_action(player, action_name, **kwargs)
            _drain_pending_choices(game, capture, f'cycle_{cycle}_red_army_action')
            capture(game, f'cycle_{cycle}_red_army_action_attempted', {'action_name': action_name})
        else:
            played = 0
            while player.hand and played < 2:
                game.play_card(0, mode='resource')
                played += 1

        game.advance_turn_phase()
        _drain_pending_choices(game, capture, f'cycle_{cycle}_end_turn')
        capture(game, f'cycle_{cycle}_end_turn')

    capture(game, 'final')
