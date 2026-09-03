"""A 4-player scenario for game_replay_harness.py targeting the faction
ability *execution* dispatchers (`_apply_card_play_faction_abilities`,
`_apply_turn_end_faction_abilities`) ahead of extracting them — item 21.

Forces factions known to hold abilities those dispatchers actually branch
on (verified against data/factions/all_faction.integrated.v2.json), so the
turn_log "already triggered this turn" flags and the elif-chain ordering
in those two methods get real exercise, not just the base 2p scenario's
hong_kong/red_army pairing (neither of which holds any of these).

Covered this way: 基金會 (tibet_dharamsala, first-money-play resource gain),
展現實力 (manchuria, 3-card combo -> pending choice), first_propaganda_draw
(kazakh, first-propaganda-play card draw).

NOT covered (left for a follow-up scenario if a future PR needs it):
商貿組織, 人同此心, 共合會, 還我河山/本土社團/民國之心 (turn-end abilities,
need a taiwan faction — doesn't fit in the same 4-player slot as the three
above), 印度研究分析室 (tibet_dehradun conflicts with tibet_dharamsala's
tibet_family slot). red_army's own activated actions (統戰部/政工部/國安部/
中紀委, `_activated_faction_action`) are also out of scope here — that's a
separate, later PR per the coordinator's split.
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


def _find_purchase_card(game, name):
    for card in game.purchase_area:
        if getattr(card, 'name', None) == name:
            return game._copy_purchase_card(card)
    return None


def _force_deterministic_setup(game):
    tibet, manchuria, kazakh, red = game.players
    tibet.name = 'tibet'
    tibet.faction_id = 'tibet_dharamsala'
    tibet.base = '達蘭薩拉'
    tibet.organizations = {'達蘭薩拉': 1}
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

    # Directly seed each target ability's actual trigger condition into the
    # relevant player's hand — same spirit as force-assigning faction_id/base
    # above; natural card draw makes hitting the exact condition (a specific
    # purchase-cost resource type, or 3 *different* non-starter names in one
    # turn for 展現實力) too unreliable to depend on for a committed baseline.
    money_card = _find_purchase_card(game, '資助者')  # money-cost -> 基金會 (tibet)
    if money_card:
        tibet.hand.append(money_card)
    propaganda_card = _find_purchase_card(game, '宣傳家')  # propaganda-cost -> star ability (kazakh)
    if propaganda_card:
        kazakh.hand.append(propaganda_card)
    for combo_name in ('資助者', '宣傳家', '資本家'):  # 3 distinct non-starter names in one turn -> 展現實力 (manchuria)
        combo_card = _find_purchase_card(game, combo_name)
        if combo_card:
            manchuria.hand.append(combo_card)

    return tibet, manchuria, kazakh, red


def _play_one_card(game, player):
    """Starter cards ('追隨者'/'樂捐者') have zero purchase cost, so playing
    them never sets cost_has_money/cost_has_propaganda — they can't trigger
    基金會/the propaganda-draw star ability even in mode='action'. Prefer any
    non-starter card in hand (mode='action', so the ability dispatcher and
    the 展現實力 combo counter both actually run); fall back to cashing in a
    starter card's printed resource so money/propaganda keep flowing to
    afford purchases."""
    if not player.hand:
        return None
    non_starter_index = next(
        (i for i, c in enumerate(player.hand) if getattr(c, 'name', None) not in {'追隨者', '樂捐者'}),
        None,
    )
    if non_starter_index is not None:
        result = game.play_card(non_starter_index, mode='action')
        if not result.get('error'):
            return result
        # Not legally playable right now (e.g. no legal build town) — don't
        # get stuck retrying it every iteration; fall through to a starter
        # card so the turn still makes progress.
    starter_index = next(
        (i for i, c in enumerate(player.hand) if getattr(c, 'name', None) in {'追隨者', '樂捐者'}),
        None,
    )
    if starter_index is not None:
        return game.play_card(starter_index, mode='resource')
    return None


def scenario(capture):
    game = Game([('p1', 'tibet'), ('p2', 'manchuria'), ('p3', 'kazakh'), ('p4', 'red')])
    _resolve_base_selection(game, capture)
    _force_deterministic_setup(game)
    capture(game, 'init')

    for cycle in range(1, 13):
        _advance_to_action(game, capture, cycle)
        player = game.current_player()

        played = 0
        while player.hand and played < 4:
            _play_one_card(game, player)
            played += 1
            _drain_pending_choices(game, capture, f'cycle_{cycle}_play_{played}')
        capture(game, f'cycle_{cycle}_play_card', {'triggered_by': player.name})

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

    capture(game, 'final')
