#!/usr/bin/env python3
"""Per-player mission-event outcome audit.

Every mission event card (main cards and 副本 copies) is run through the real game engine in a
4-seat game (Ben=澳門, Angie=蒙古, Cy=自由派, Red=紅軍; seat order Ben, Angie, Cy, Red) and
checked for the two authoritative rules:

1. each non-Red player is tracked, judged and rewarded/penalised INDIVIDUALLY;
2. every outcome is decided only when the full round ends (every player, Red Army included,
   acted once; never earlier), so Red Army's own actions inside the window can still change a player's result.

A separate seat-order check ([Ben, Red, Angie]) proves the round opens after Red (Angie -> Ben -> Red):
no earlier turn end settles anything; Red's turn end (the full-round end) does.

Players satisfy the trigger through real game actions on their own turn (playing cards, buying,
building, moving, using abilities); 盟旗學校 credit is earned through a real dissolve attempt.
Outcome effects are then applied by the real settlement queue, and every pending choice is
answered in order, so the audit also exercises the re-entrant per-player state machine.

Expected results come from the fixed hand-written oracle in event_card_oracle.py, never from the
loaded event definition: each card's runtime definition must first equal the oracle exactly, and
the expected per-player deltas are computed from the oracle's effects. A wrong value in the data
(main card, copy, or both) therefore fails the audit instead of validating itself.

Writes docs/records/event-cards/EVENT_OUTCOME_TIMING_AUDIT.{json,md}. Exit code 1 on any failure.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from server.cards import Card  # noqa: E402
from server.game import Game, GamePhase, TurnPhase  # noqa: E402
from event_card_oracle import MISSION_ORACLE, ORACLE_BY_NAME, definition_mismatches  # noqa: E402

RECORD_DIR = ROOT / 'docs' / 'records' / 'event-cards'
JSON_OUT = RECORD_DIR / 'EVENT_OUTCOME_TIMING_AUDIT.json'
MD_OUT = RECORD_DIR / 'EVENT_OUTCOME_TIMING_AUDIT.md'

# Test hook: a callable that mutates the (deep-copied) runtime event definitions of each audited
# game, used by the mutation regression tests to prove the audit catches wrong data.
RUNTIME_EVENT_MUTATOR = None

NON_RED = ('Ben', 'Angie', 'Cy')
# Distinct, non-base 牆內 towns used for the dissolvable / near-own organizations.
INSIDE_ORG_TOWNS = {'Ben': '成都', 'Angie': '西安', 'Cy': '武漢'}
# 澳門 is itself a 牆內 town, so players that must NOT qualify for 烏魯木齊七五事件 hold one of these.
OUTSIDE_ORGS = {'Ben': '曼谷', 'Angie': '烏蘭巴托', 'Cy': '臺北'}


def card(name):
    return Card(name, 'command', {})


def names(cards):
    return [getattr(c, 'name', str(c)) for c in cards]


def real_card(game, name):
    definition = next(c for c in game.structured_cards if c['name'] == name)
    return Card(definition['name'], definition['type'], definition.get('resources', {}))


class Audit:
    """One mission-event run: a fresh game, a scripted round, an automatic settlement."""

    def __init__(self, event_name, with_inside_orgs=False):
        self.event_name = event_name
        factions = {'Ben': 'aomen', 'Angie': 'mongol', 'Cy': 'liberals', 'Red': 'red_army'}
        game = Game(
            [('ben-id', 'Ben'), ('angie-id', 'Angie'), ('cy-id', 'Cy'), ('red-id', 'Red')],
            market_mode='all_cards',
            factions={f'{name.lower()}-id': faction for name, faction in factions.items()},
        )
        self.game = game
        if RUNTIME_EVENT_MUTATOR is not None:
            game.structured_events = copy.deepcopy(game.structured_events)
            RUNTIME_EVENT_MUTATOR(game.structured_events)
        bases = {'Ben': '澳門', 'Angie': '烏蘭巴托', 'Cy': '臺北', 'Red': '北京'}
        for player in game.players:
            player.base = bases[player.name]
            player.organizations = {player.base: 1}
            player.resources = {'money': 0, 'propaganda': 0}
            player.moves_left = 0
            player.hand = [card(f'{player.name}手牌{i}') for i in range(5)]
            player.deck.draw_pile = [card(f'{player.name}補牌{i}') for i in range(12)]
            player.deck.discard_pile = [card(f'{player.name}棄牌{i}') for i in range(3)]
        if with_inside_orgs:
            for name in NON_RED:
                self.player(name).organizations[INSIDE_ORG_TOWNS[name]] = 1
        game.pending_base_choices = {}
        game.game_phase = GamePhase.MAIN
        assert (game.current_player_index, game.round_start_player_index) == (0, 0)  # Red last
        game.event_deck.draw_pile = [game._event_by_name(event_name)]
        game.event_deck.discard_pile = []
        game.current_event = None
        game.pending_choice = None
        game.turn_log = game._new_turn_log()
        game.action_log = []
        game._start_event_phase()  # the real draw: builds the per-player progress
        game.turn_phase = TurnPhase.ACTION
        self.event = game.current_event
        # Expectations come from the fixed oracle, NOT from the loaded `self.event`.
        self.oracle = ORACLE_BY_NAME[event_name]
        self.definition_problems = [
            problem for problem in definition_mismatches(game.structured_events)
            if problem.startswith(f'{event_name}:')
        ]
        # The settled progress dict is replaced by the next round's event at the round wrap, so
        # keep a reference to the one this run is auditing.
        self.progress_ref = game.event_progress
        self.trigger = self.oracle['trigger']
        self.success_effect = self.oracle['success']
        self.failure_effect = self.oracle['failure']

    # ----- helpers -----
    def player(self, name):
        return next(p for p in self.game.players if p.name == name)

    def snapshot(self):
        inside = set(self.game._towns_for_region_alias('china'))
        return {
            p.name: {
                'hand': len(p.hand),
                'draw': len(p.deck.draw_pile),
                'discard': len(p.deck.discard_pile),
                'moves_left': p.moves_left,
                'orgs': sum(p.organizations.values()),
                'inside_orgs': sum(n for t, n in p.organizations.items() if t in inside),
                'discard_names': names(p.deck.discard_pile),
                'draw_top': names(p.deck.draw_pile[-1:]),
                'hand_names': names(p.hand),
            }
            for p in self.game.players
        }

    def progress_summary(self):
        entries = self.progress_ref.get('player_progress') or {}
        return {
            entry['player_name']: {'count': entry['count'], 'met': entry['met'], 'result': entry['result']}
            for entry in entries.values()
        }

    def resolve_choice(self):
        game = self.game
        choice = game.pending_choice
        kind = choice.get('type')
        owner = next(p for p in game.players if p.id == choice['player_id'])
        if kind == 'multi_card_choice':
            index = list(range(int(choice.get('count', 1) or 1)))
        else:
            index = 0
        result = game.resolve_pending_choice(owner.id, index)
        assert not result.get('error'), result
        return owner.name

    # ----- satisfying a trigger through real actions -----
    def satisfy(self, name):
        """Let `name` meet the trigger on their own turn. Returns False if it can't be done by
        the player alone on their own turn (蒙古's passive 盟旗學校 needs an attacker)."""
        game = self.game
        player = self.player(name)
        kind = self.trigger.get('type')
        player.resources = {'money': 20, 'propaganda': 20}
        if kind == 'use_faction_ability':
            ability = {'Ben': '賭徒耳語', 'Cy': '立場試探', 'Red': '統戰部'}.get(name)
            if ability is None:
                return False
            result = game._activated_faction_action(player, ability, guess='odd')
            assert not result.get('error'), result
            if game.pending_choice:
                self.resolve_choice()
        elif kind == 'play_card_with_money':
            player.hand.append(real_card(game, '乘勝追擊'))
            assert game.play_card(len(player.hand) - 1, mode='resource').get('success')
        elif kind == 'play_card_with_propaganda':
            player.hand.append(real_card(game, '宣傳家'))
            assert game.play_card(len(player.hand) - 1, mode='resource').get('success')
        elif kind == 'buy_card':
            index = names(game.purchase_area).index('資本家')
            result = game.buy_card(index)
            assert result.get('success'), result
        elif kind == 'draw':
            player.hand.append(real_card(game, '樹立信心'))
            result = game.play_card(len(player.hand) - 1, mode='action')
            assert result.get('success'), result
        elif kind == 'build_organization':
            origin, target = self.find_build_pair(player)
            player.organizations.setdefault(origin, 1)
            result = game.build_organization_with_support(origin, target)
            assert result.get('success'), result
        elif kind == 'move_organization':
            player.moves_left = 9
            chain = self.find_move_chain(player)
            player.organizations[chain[0]] = 1
            for origin, step in zip(chain, chain[1:]):
                result = game.move_organization(origin, step, 'road')
                assert result.get('success'), result
        elif kind == 'end_turn_state':
            player.organizations = {self.inside_origin(player): 1}
        else:
            raise AssertionError(f'unsupported trigger type {kind}')
        return True

    def find_build_pair(self, player):
        """An (origin, target) pair of unoccupied 牆內 towns where `player` can really build."""
        game = self.game
        inside = sorted(game._towns_for_region_alias('china'))
        occupied = {town for other in game.players for town in other.organizations}
        for origin in inside:
            if origin in occupied:
                continue
            player.organizations[origin] = 1
            try:
                for target in sorted(game._town_neighbors(origin)):
                    if target in inside and target not in occupied and game._can_player_build_in_town(player, target):
                        return origin, target
            finally:
                del player.organizations[origin]
        raise AssertionError(f'no build pair for {player.name}')

    def inside_origin(self, player):
        """A 牆內 town where `player` can both hold an organization and later build next to it."""
        player_orgs = dict(player.organizations)
        origin, _target = self.find_build_pair(player)
        player.organizations = player_orgs
        return origin

    def find_move_chain(self, player):
        """Four unoccupied towns joined by road links: three real moves for `player`."""
        game = self.game
        occupied = {town for other in game.players for town in other.organizations}
        towns = game.map['towns']

        def hop_is_legal(origin, target):
            had = origin in player.organizations
            player.organizations.setdefault(origin, 1)
            try:
                return bool(game._validate_organization_move(origin, target, 'road').get('success'))
            finally:
                if not had:
                    del player.organizations[origin]

        def extend(path):
            if len(path) == 4:
                return path
            for nxt in sorted(towns[path[-1]].get('road', []) or []):
                if nxt not in path and nxt not in occupied and hop_is_legal(path[-1], nxt):
                    found = extend(path + [nxt])
                    if found:
                        return found
            return None

        for start in sorted(towns):
            if start in occupied:
                continue
            chain = extend([start])
            if chain:
                return chain
        raise AssertionError('no road chain found')

    def red_dissolves(self, defender_name, attacker='Red', hand=True, town=None):
        game = self.game
        attacker_player = self.player(attacker)
        attacker_player.hand = [card('代價手牌')] if hand else []
        defender = self.player(defender_name)
        return game.dissolve_organization(
            attacker_player, defender, town or INSIDE_ORG_TOWNS[defender_name], source='faction_action'
        )

    # ----- running the round -----
    def play_window(self, satisfied=(), red_satisfies=False, red_action=None, peer_attack=None, stop_before_red=False):
        """Run every seat's turn in order: non-Red seats perform their action (if satisfied) and
        end the turn; returns the snapshot taken right after the last non-Red seat's end."""
        game = self.game
        for name in NON_RED:
            assert game.current_player().name == name, (game.current_player().name, name)
            if name in satisfied:
                self.satisfy(name)
            if peer_attack and peer_attack[0] == name:
                result = self.red_dissolves(peer_attack[1], attacker=name)
                assert result.get('success'), result
            game.turn_phase = TurnPhase.ACTION
            result = game.advance_turn_phase()
            assert result == {'success': True}, result
        self.after_last_non_red = self.snapshot()
        self.after_last_non_red_progress = self.progress_summary()
        self.after_last_non_red_state = {
            'settled': self.progress_ref['settled'],
            'started': bool(self.progress_ref.get('settlement_started')),
            'current': game.current_player().name,
            'log_has_outcome': any(
                'Event success' in line or 'Event failure' in line for line in game.action_log
            ),
        }
        if stop_before_red:
            return
        assert game.current_player().name == 'Red'
        if red_satisfies:
            self.satisfy('Red')
        if red_action:
            red_action()

    def end_round_and_resolve(self):
        """End the last seat's turn (the round's final one), answer every pending choice in order. Returns the sequence of
        choice owners (in the order they were asked) and the snapshots around settlement."""
        game = self.game
        self.before_settlement = self.snapshot()
        owners = []
        game.turn_phase = TurnPhase.ACTION
        result = game.advance_turn_phase()
        self.red_end_result = result
        guard = 0
        while game.pending_choice:
            guard += 1
            assert guard < 50, 'pending choice loop'
            owners.append((game.pending_choice['choice_key'], self.resolve_choice()))
        self.owners = owners
        self.after_settlement = self.snapshot()
        return owners


# ---------------------------------------------------------------------------
# Expected per-player effect of one outcome
# ---------------------------------------------------------------------------

def expected_delta(effect, before, after):
    """Return (ok, description) comparing one player's before/after snapshots with the effect
    that player's own outcome should have produced (resolving every choice with its first option)."""
    kind = (effect or {}).get('type', 'none')
    count = int((effect or {}).get('count', 1) or 1)
    delta = {key: after[key] - before[key] for key in ('hand', 'draw', 'discard', 'moves_left', 'orgs')}
    if kind in (None, 'none'):
        return all(v == 0 for v in delta.values()), delta
    if kind == 'draw':
        return delta['hand'] == count and delta['draw'] == -count and delta['discard'] == 0, delta
    if kind == 'gain_card':
        gained = after['discard_names'].count(effect['card']) - before['discard_names'].count(effect['card'])
        return gained == count and delta['hand'] == 0, {**delta, 'gained': gained}
    if kind == 'move':
        return delta['moves_left'] == count and delta['hand'] == 0 and delta['discard'] == 0, delta
    if kind == 'topdeck_from_discard':
        top_ok = after['draw_top'] == before['discard_names'][:1]
        return delta['discard'] == -1 and delta['draw'] == 1 and delta['hand'] == 0 and top_ok, delta
    if kind == 'trash_from_hand_or_discard':
        return delta['hand'] + delta['discard'] == -count and delta['draw'] == 0, delta
    if kind == 'build_organization_near_own':
        return delta['orgs'] == count and delta['hand'] == 0 and delta['discard'] == 0, delta
    if kind in ('discard_self', 'discard_random'):
        return delta['hand'] == -count and delta['discard'] == count and delta['draw'] == 0, delta
    if kind == 'red_dissolve':
        return delta['orgs'] == -count and delta['hand'] == 0 and delta['discard'] == 0, delta
    return False, delta


CHOICE_KEY_FOR_EFFECT = {
    'discard_self': 'event_discard_self',
    'red_dissolve': 'event_red_dissolve',
    'topdeck_from_discard': 'event_topdeck_from_discard',
    'trash_from_hand_or_discard': 'trash_from_hand_or_discard',
    'build_organization_near_own': 'event_build_organization',
}


def verify_outcomes(run, expected_success):
    """Compare every non-Red player's own outcome with `expected_success` (a set of names)."""
    progress = run.progress_summary()
    problems = list(run.definition_problems)
    expected_owner_order = []
    for name in NON_RED:
        should_succeed = name in expected_success
        got = progress[name]['result']
        if got != ('success' if should_succeed else 'failure'):
            problems.append(f'{name} result {got!r} expected {"success" if should_succeed else "failure"}')
        effect = run.success_effect if should_succeed else run.failure_effect
        key = CHOICE_KEY_FOR_EFFECT.get(effect.get('type'))
        if key:
            # Red Army owns the choice for red_dissolve, otherwise the affected player does.
            expected_owner_order.append((key, 'Red' if key == 'event_red_dissolve' else name))
        ok, detail = expected_delta(effect, run.before_settlement[name], run.after_settlement[name])
        if name == 'Angie' and effect.get('type') == 'red_dissolve':
            # Red pays one hand card to bypass 盟旗學校 when dissolving Angie's organization.
            pass
        if not ok:
            problems.append(f'{name} effect {effect.get("type")} delta mismatch: {detail}')
    if run.owners != expected_owner_order:
        problems.append(f'pending choice order {run.owners} != {expected_owner_order}')
    state = run.progress_ref
    if not state.get('settled'):
        problems.append('event not settled after every choice resolved')
    expected_status = (
        'success' if len(expected_success) == len(NON_RED)
        else 'failure' if not expected_success else 'mixed'
    )
    if state.get('status') != expected_status:
        problems.append(f'status {state.get("status")!r} expected {expected_status!r}')
    return problems, progress


def timing_problems(run):
    problems = []
    state = run.after_last_non_red_state
    if state['settled'] or state['started']:
        problems.append(f'settled early before the last seat of the round ended: {state}')
    if state['log_has_outcome']:
        problems.append('an outcome was applied before the full round ended')
    if state['current'] != 'Red':
        problems.append(f'expected Red seat next, got {state["current"]}')
    return problems


def check(name, run_fn):
    try:
        problems, details = run_fn()
    except Exception as exc:  # noqa: BLE001 - audit must record failures, not crash
        problems, details = [f'exception: {type(exc).__name__}: {exc}'], {}
    return {'name': name, 'passed': not problems, 'problems': problems, 'details': details}


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def uses_inside_orgs(event_name):
    event_effects = {'red_dissolve', 'build_organization_near_own'}
    probe = Audit(event_name)
    return (
        probe.failure_effect.get('type') in event_effects
        or probe.success_effect.get('type') in event_effects
        or probe.trigger.get('type') == 'use_faction_ability'
    )


def scenario(event_name, satisfied, label):
    """`satisfied`: names meeting the trigger. Angie's passive 盟旗學校 credit (use_faction_ability
    events) comes from Red Army dissolving her organization during the round."""
    def run():
        run = Audit(event_name, with_inside_orgs=uses_inside_orgs(event_name))
        angie_by_red = (
            run.trigger.get('type') == 'use_faction_ability' and 'Angie' in satisfied
        )
        self_satisfied = [n for n in satisfied if not (angie_by_red and n == 'Angie')]
        if run.trigger.get('type') == 'end_turn_state':
            for name in NON_RED:
                run.player(name).organizations = {OUTSIDE_ORGS[name]: 1}
        run.play_window(satisfied=self_satisfied)
        problems = timing_problems(run)
        if run.trigger.get('type') != 'end_turn_state':
            before = run.progress_summary()
            for name in NON_RED:
                if before[name]['met'] != (name in satisfied and not (angie_by_red and name == 'Angie')):
                    problems.append(f'{name} progress before the round ends is {before[name]}')
        if angie_by_red:
            result = run.red_dissolves('Angie')
            if not result.get('success'):
                problems.append(f'red dissolve of Angie failed: {result}')
            # The Red Army hand card paid for 盟旗學校 is expected; restore a hand for refill checks.
        run.end_round_and_resolve()
        # Red's own payment (盟旗學校) / refill is not part of the per-player delta below.
        found, progress = verify_outcomes(run, set(satisfied))
        problems += found
        return problems, {'progress': progress, 'choice_order': run.owners}
    return check(f'{event_name} {label}', run)


def scenario_red_actions_not_credited(event_name):
    def run():
        run = Audit(event_name, with_inside_orgs=uses_inside_orgs(event_name))
        if run.trigger.get('type') == 'end_turn_state':
            for name in NON_RED:
                run.player(name).organizations = {OUTSIDE_ORGS[name]: 1}
        run.play_window(satisfied=(), red_satisfies=run.trigger.get('type') != 'end_turn_state')
        problems = timing_problems(run)
        run.end_round_and_resolve()
        found, progress = verify_outcomes(run, set())
        problems += found
        return problems, {'progress': progress}
    return check(f'{event_name} red actions never progress a non-Red player', run)


def scenario_red_turn_changes_state_condition(event_name):
    """烏魯木齊七五事件: Red Army dissolving a player's 牆內 organization during the round
    flips that player to failure, because the state is read only when the full round ends."""
    def run():
        run = Audit(event_name)
        origins = {}
        for name in NON_RED:
            origins[name] = run.inside_origin(run.player(name))
            run.player(name).organizations = {origins[name]: 1}
        run.play_window(satisfied=())
        problems = timing_problems(run)
        result = run.red_dissolves('Ben', town=origins['Ben'])
        if not result.get('success'):
            problems.append(f'red dissolve failed: {result}')
        run.end_round_and_resolve()
        found, progress = verify_outcomes(run, {'Angie', 'Cy'})
        problems += found
        return problems, {'progress': progress}
    return check(f'{event_name} in-round Red dissolve flips only that player to failure', run)


def scenario_npc_passive_credit(event_name, label, attacker, hand=True, expect_credit=True):
    """盟旗學校 credit belongs to Angie (the ability owner), never to the attacker, and only when
    the effect is actually carried out (attacker paid the discard)."""
    def run():
        run = Audit(event_name, with_inside_orgs=True)
        peer = (attacker, 'Angie') if attacker != 'Red' else None
        if peer:
            run.play_window(satisfied=(), peer_attack=peer)
        else:
            run.play_window(satisfied=())
        problems = timing_problems(run) + list(run.definition_problems)
        if attacker == 'Red':
            result = run.red_dissolves('Angie', hand=hand)
            succeeded = bool(result.get('success'))
            if succeeded != hand:
                problems.append(f'dissolve outcome {result} unexpected for hand={hand}')
        progress = run.progress_summary()
        want = {'Ben': False, 'Angie': expect_credit, 'Cy': False}
        for name, met in want.items():
            if progress[name]['met'] != met:
                problems.append(f'{name} met={progress[name]["met"]} expected {met} before settlement')
        if attacker != 'Red' and progress[attacker]['met']:
            problems.append('attacker was credited with the defender 盟旗學校 trigger')
        return problems, {'progress': progress}
    return check(f'{event_name} {label}', run)


def scenario_single_dissolve_does_not_double_count(event_name):
    def run():
        run = Audit(event_name, with_inside_orgs=True)
        run.play_window(satisfied=())
        for _ in range(2):
            run.player('Angie').organizations[INSIDE_ORG_TOWNS['Angie']] = 1
            run.red_dissolves('Angie')
        entry = run.progress_ref['player_progress'][run.player('Angie').id]
        problems = []
        if not entry['met']:
            problems.append('Angie not credited')
        if run.progress_ref['count'] != 1:
            problems.append(f'aggregate count {run.progress_ref["count"]} expected 1')
        run.end_round_and_resolve()
        found, progress = verify_outcomes(run, {'Angie'})
        problems += found
        return problems, {'progress': progress}
    return check(f'{event_name} repeated 盟旗學校 triggers still settle Angie once', run)


def scenario_no_target_failure(event_name):
    """red_dissolve failure with no legal 牆內 organization: no pending choice, no penalty."""
    def run():
        run = Audit(event_name, with_inside_orgs=False)
        run.play_window(satisfied=('Ben',))
        run.end_round_and_resolve()
        problems = list(run.definition_problems)
        if run.owners:
            problems.append(f'unexpected pending choices {run.owners}')
        if not run.progress_ref['settled']:
            problems.append('event did not settle with no legal target')
        for name in ('Angie', 'Cy'):
            if run.after_settlement[name]['orgs'] != run.before_settlement[name]['orgs']:
                problems.append(f'{name} lost an organization with no legal target')
        return problems, {'progress': run.progress_summary()}
    return check(f'{event_name} failure with no legal target settles without a choice', run)


def check_definition_matches_oracle():
    """The runtime-loaded definitions must equal the fixed oracle before anything else is trusted."""
    def run():
        probe = Game([('p1', 'P1'), ('p2', 'P2')])
        events = probe.structured_events
        if RUNTIME_EVENT_MUTATOR is not None:
            events = copy.deepcopy(events)
            RUNTIME_EVENT_MUTATOR(events)
        problems = definition_mismatches(events)
        return problems, {'cards': len(ORACLE_BY_NAME)}
    return check('runtime mission definitions equal the fixed oracle (all cards)', run)


def run_all_checks():
    missions = MISSION_ORACLE
    checks = [check_definition_matches_oracle()]
    for event in missions:
        name = event['name']
        checks.append(scenario(name, {'Ben'}, 'success only for Ben, failure for the others'))
        checks.append(scenario(name, {'Ben', 'Angie'}, 'Ben and Angie succeed, Cy fails'))
        checks.append(scenario(name, {'Angie', 'Cy'}, 'Angie and Cy succeed, Ben fails'))
        checks.append(scenario(name, set(NON_RED), 'every non-Red player succeeds'))
        checks.append(scenario(name, set(), 'every non-Red player fails'))
        checks.append(scenario_red_actions_not_credited(name))
        if event['failure']['type'] == 'red_dissolve':
            checks.append(scenario_no_target_failure(name))
        if event['trigger']['type'] == 'use_faction_ability':
            checks.append(scenario_npc_passive_credit(
                name, '盟旗學校 triggered by a Red Army dissolve credits Angie only', 'Red'))
            checks.append(scenario_npc_passive_credit(
                name, '盟旗學校 triggered by a peer dissolve credits Angie, not the attacker', 'Ben'))
            checks.append(scenario_npc_passive_credit(
                name, '盟旗學校 blocked (attacker cannot pay) credits nobody', 'Red', hand=False, expect_credit=False))
            checks.append(scenario_single_dissolve_does_not_double_count(name))
        if event['trigger']['type'] == 'end_turn_state':
            checks.append(scenario_red_turn_changes_state_condition(name))
    checks.append(scenario_red_mid_seat_waits_for_full_round())
    return checks, len(missions)


def scenario_red_mid_seat_waits_for_full_round():
    """[Ben, Red, Angie]: the round opens at the seat after Red, so it runs Angie -> Ben -> Red.
    Angie and Ben each get a full turn, Red acts last, and the outcome is judged only when Red ends."""
    def run():
        problems = []
        event_name = '重大災難'
        game = Game([('ben-id', 'Ben'), ('red-id', 'Red'), ('angie-id', 'Angie')], market_mode='all_cards',
                    factions={'ben-id': 'aomen', 'red-id': 'red_army', 'angie-id': 'mongol'})
        for player in game.players:
            player.base = {'Ben': '澳門', 'Red': '北京', 'Angie': '烏蘭巴托'}[player.name]
            player.organizations = {player.base: 1}
            player.hand = [card(f'{player.name}手牌{i}') for i in range(5)]
            player.deck.draw_pile = [card(f'{player.name}補牌{i}') for i in range(12)]
        game.pending_base_choices = {}
        game.game_phase = GamePhase.MAIN
        game.current_player_index = game.round_start_player_index = 2  # seat after Red, as /start sets it
        game.event_deck.draw_pile = [game._event_by_name('歲月靜好'), game._event_by_name(event_name)]
        game.event_deck.discard_pile = []
        game.current_event = None
        game.pending_choice = None
        game._start_event_phase()
        game.turn_phase = TurnPhase.ACTION
        progress = game.event_progress
        acted = []
        for expected in ('Angie', 'Ben', 'Red'):
            if game.current_player().name != expected:
                problems.append(f'expected {expected} to act, got {game.current_player().name}')
                break
            acted.append(expected)
            if expected == 'Angie':
                angie = game.current_player()
                angie.hand.append(real_card(game, '宣傳家'))
                game.play_card(len(angie.hand) - 1, mode='resource')
            game.turn_phase = TurnPhase.ACTION
            game.advance_turn_phase()
            started = bool(progress.get('settlement_started'))
            if expected != 'Red' and (started or progress['settled']):
                problems.append(f'settled after {expected} ended, before the round was complete')
        if acted != ['Angie', 'Ben', 'Red']:
            problems.append(f'acted sequence {acted}')
        entries = progress.get('player_progress') or {}
        if (entries.get('angie-id') or {}).get('result') != 'success' or (entries.get('ben-id') or {}).get('result') != 'failure':
            problems.append(f'unexpected results {entries}')
        guard = 0
        while game.pending_choice and guard < 10:
            guard += 1
            game.resolve_pending_choice(game.pending_choice['player_id'], [0])
        if not progress['settled']:
            problems.append('not settled after Red and its choices')
        if game.current_player().name != 'Angie':
            problems.append(f'next round should open at Angie, got {game.current_player().name}')
        return problems, {'round_order': ['Angie', 'Ben', 'Red']}
    return check('[Ben, Red, Angie] runs Angie -> Ben -> Red and settles only after Red (Angie acts before judgement)', run)


def main():
    checks, mission_count = run_all_checks()
    summary = {
        'total': len(checks),
        'passed': sum(1 for c in checks if c['passed']),
        'failed': sum(1 for c in checks if not c['passed']),
        'events': mission_count,
    }
    payload = {'summary': summary, 'checks': checks}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# Event outcome timing audit',
        '',
        '每張任務事件卡（含副本）逐位非紅軍玩家驗證：個別追蹤、個別成功／失敗效果、整輪結束（每位玩家各行動一次）才結算、',
        '多人 pending choice 依序處理。座位：Ben(澳門) → Angie(蒙古) → Cy(自由派) → Red(紅軍)。',
        '',
        f"- events: `{summary['events']}`",
        f"- total: `{summary['total']}`",
        f"- passed: `{summary['passed']}`",
        f"- failed: `{summary['failed']}`",
        '',
    ]
    for c in checks:
        mark = '✅' if c['passed'] else '❌'
        lines.append(f"- {mark} {c['name']}")
        for problem in c['problems']:
            lines.append(f"  - {problem}")
    MD_OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    if summary['failed']:
        failed = [c['name'] for c in checks if not c['passed']]
        print(json.dumps({'failed': failed}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
