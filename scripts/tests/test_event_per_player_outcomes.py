"""Per-player mission-event outcomes, settled when the Red Army turn ends.

Every mission event is tracked, judged and rewarded/penalised per non-Red player; no outcome may
be applied at a non-Red seat's own turn end (Red Army's actions in the window can still change a
player's progress); several players' different outcomes (and their pending choices) are queued
and processed one at a time. See rules.md「任務事件：每位非紅軍玩家個別判定」.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts' / 'validate'))

import pytest

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase

INSIDE = {'Ben': '成都', 'Angie': '西安', 'Cy': '武漢'}


def card(name):
    return Card(name, 'command', {})


def names(cards):
    return [getattr(c, 'name', str(c)) for c in cards]


def real_card(game, name):
    definition = next(c for c in game.structured_cards if c['name'] == name)
    return Card(definition['name'], definition['type'], definition.get('resources', {}))


def make_game(event_name, seats=('Ben', 'Angie', 'Red'), inside_orgs=True):
    """Seats in turn order. Ben=澳門(aomen), Angie=蒙古(mongol), Cy=自由派, Red=紅軍 (last)."""
    table = {
        'Ben': ('aomen', '澳門'),
        'Angie': ('mongol', '烏蘭巴托'),
        'Cy': ('liberals', '臺北'),
        'Red': ('red_army', '北京'),
    }
    game = Game([(f'{n.lower()}-id', n) for n in seats], market_mode='all_cards')
    for player in game.players:
        faction, base = table[player.name]
        player.faction_id = faction
        player.base = base
        player.organizations = {base: 1}
        if inside_orgs and player.name in INSIDE:
            player.organizations[INSIDE[player.name]] = 1
        player.resources = {'money': 0, 'propaganda': 0}
        player.moves_left = 0
        player.hand = [card(f'{player.name}手牌{i}') for i in range(5)]
        player.deck.draw_pile = [card(f'{player.name}補牌{i}') for i in range(12)]
        player.deck.discard_pile = [card(f'{player.name}棄牌{i}') for i in range(3)]
    game.pending_base_choices = {}
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.round_start_player_index = 0
    game.event_deck.draw_pile = [game._event_by_name(event_name)]
    game.event_deck.discard_pile = []
    game.current_event = None
    game.pending_choice = None
    game.turn_log = game._new_turn_log()
    game.action_log = []
    game._start_event_phase()
    game.turn_phase = TurnPhase.ACTION
    return game


def by_name(game, name):
    return next(p for p in game.players if p.name == name)


def end_turn(game):
    game.turn_phase = TurnPhase.ACTION
    return game.advance_turn_phase()


def use_ability(game, name):
    player = by_name(game, name)
    result = game._activated_faction_action(player, '賭徒耳語', guess='odd')
    assert not result.get('error'), result
    if game.pending_choice:
        assert game.resolve_pending_choice(player.id, 0).get('success')


def outcome_lines(game):
    return [line for line in game.action_log if 'Event success' in line or 'Event failure' in line]


# ---------------------------------------------------------------------------
# 全國人大召開: 澳門 / 蒙古 (the reported playtest)
# ---------------------------------------------------------------------------

def test_npc_macau_succeeds_and_mongolia_fails_individually():
    game = make_game('全國人大召開')
    ben, angie, red = game.players
    progress = game.event_progress                # (the next round's event replaces it at the wrap)
    use_ability(game, 'Ben')                      # 賭徒耳語 on Ben's own turn
    assert end_turn(game) == {'success': True}    # Ben ends
    assert end_turn(game) == {'success': True}    # Angie (the final non-Red seat) ends

    # Nothing settles at the last non-Red seat: Red Army can still act in the window.
    assert game.current_player() is red
    assert game.event_progress['settled'] is False
    assert not game.event_progress.get('settlement_started')
    assert outcome_lines(game) == []
    ben_hand = len(ben.hand)

    result = end_turn(game)                        # the Red Army turn ends -> settlement

    entries = progress['player_progress']
    assert (entries[ben.id]['result'], entries[angie.id]['result']) == ('success', 'failure')
    # Ben's own success: he draws; Angie's failure: Red picks one of ANGIE's 牆內 organizations.
    assert len(ben.hand) == ben_hand + 1
    assert result.get('pending_choice') is True
    choice = game.pending_choice
    assert (choice['choice_key'], choice['player_id']) == ('event_red_dissolve', red.id)
    assert {t['player_id'] for t in choice['targets']} == {angie.id}
    assert game.resolve_pending_choice(red.id, 0).get('success')

    assert angie.organizations == {'烏蘭巴托': 1}
    assert ben.organizations == {'澳門': 1, '成都': 1}            # Ben is never penalised
    assert progress['status'] == 'mixed' and progress['settled'] is True
    assert game.current_player() is ben                           # new round started
    # Red paid 盟旗學校 for dissolving Angie's organization, but the result was already locked:
    # the 盟旗學校 trigger during settlement must not flip Angie to success.
    assert entries[angie.id]['result'] == 'failure'


def test_npc_macau_and_mongolia_both_succeed_when_red_dissolve_triggers_mongolian_school():
    game = make_game('全國人大召開')
    ben, angie, red = game.players
    progress = game.event_progress
    use_ability(game, 'Ben')
    end_turn(game)
    end_turn(game)
    ben_hand, angie_hand = len(ben.hand), len(angie.hand)

    # Red Army's own turn: dissolving Angie's organization triggers HER 盟旗學校 (Red pays).
    red.hand = [card('紅軍代價手牌')]
    result = game.dissolve_organization(red, angie, '西安', source='faction_action')
    assert result.get('success') is True
    assert red.hand == []
    entries = progress['player_progress']
    assert entries[angie.id]['met'] is True and entries[ben.id]['met'] is True
    assert red.id not in entries                                 # Red is not a mission participant
    assert progress['settled'] is False                           # still nothing settled early
    assert len(angie.hand) == angie_hand

    assert end_turn(game) == {'success': True}                    # nobody failed -> no pending choice
    assert len(ben.hand) == ben_hand + 1
    assert len(angie.hand) == angie_hand + 1
    assert game.pending_choice is None
    assert progress['status'] == 'success'


def test_npc_mongolian_school_credit_goes_to_the_defender_not_the_attacker():
    game = make_game('全國人大召開', seats=('Ben', 'Angie', 'Red'))
    ben, angie, red = game.players
    ben.hand = [card('Ben的代價手牌')]
    result = game.dissolve_organization(ben, angie, '西安', source='card')   # a peer attacks Angie
    assert result.get('success') is True
    entries = game.event_progress['player_progress']
    assert entries[angie.id]['met'] is True
    assert entries[ben.id]['met'] is False


def test_npc_mongolian_school_only_counts_when_the_effect_really_runs():
    game = make_game('全國人大召開')
    ben, angie, red = game.players
    entries = game.event_progress['player_progress']

    # (1) the attacker cannot pay the discard -> the dissolve is blocked, nothing triggered
    red.hand = []
    blocked = game.dissolve_organization(red, angie, '西安', source='faction_action')
    assert '盟旗學校' in blocked.get('error', '')
    assert entries[angie.id]['met'] is False
    assert angie.organizations.get('西安') == 1

    # (2) stale target: the town no longer holds an organization -> no shield, no credit
    red.hand = [card('代價')]
    stale = game.dissolve_organization(red, angie, '長沙', source='faction_action')
    assert stale.get('error')
    assert entries[angie.id]['met'] is False
    assert [c.name for c in red.hand] == ['代價']

    # (3) dissolving one's own organization is not an attack by someone else
    angie.hand = [card('蒙古自己的手牌')]
    own = game.dissolve_organization(angie, angie, '西安', source='card')
    assert own.get('success') is True
    assert entries[angie.id]['met'] is False
    assert [c.name for c in angie.hand] == ['蒙古自己的手牌']


def test_npc_mongolian_school_via_red_state_security_pending_choice():
    game = make_game('全國人大召開')
    ben, angie, red = game.players
    end_turn(game)
    end_turn(game)
    red.organizations['鄭州'] = 1
    red.hand = [card('國安部代價手牌')]
    started = game._activated_faction_action(red, '國安部')
    assert started.get('pending_choice') is True
    entries = game.event_progress['player_progress']
    assert entries[angie.id]['met'] is False                 # choosing a target is not the effect
    index = next(i for i, t in enumerate(game.pending_choice['targets']) if t['player_id'] == angie.id)
    assert game.resolve_pending_choice(red.id, index).get('success')
    assert entries[angie.id]['met'] is True                  # credited once the dissolve ran
    assert entries[ben.id]['met'] is False


def test_npc_cancelled_dissolve_card_does_not_credit_mongolian_school():
    game = make_game('全國人大召開')
    ben, angie, red = game.players
    end_turn(game)
    end_turn(game)
    red.organizations['鄭州'] = 1
    red.hand = [real_card(game, '內應間諜'), card('代價')]
    played = game.play_card(0, mode='action')
    assert played.get('pending_choice') is True, played
    entries = game.event_progress['player_progress']
    assert game.cancel_pending_choice(red.id).get('success')
    assert entries[angie.id]['met'] is False
    assert angie.organizations.get('西安') == 1


# ---------------------------------------------------------------------------
# Timing: nothing settles before the Red Army turn ends
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('seats', [('Ben', 'Angie', 'Red'), ('Ben', 'Angie', 'Cy', 'Red')])
def test_no_outcome_before_red_army_turn_ends(seats):
    game = make_game('重大災難', seats=seats)
    hands = {p.name: len(p.hand) for p in game.players}
    for name in seats[:-1]:
        assert game.current_player().name == name
        assert end_turn(game) == {'success': True}
        assert game.event_progress['settled'] is False
        assert not game.event_progress.get('settlement_started')
        assert game.pending_choice is None
        assert outcome_lines(game) == []
        # each seat only refilled its own hand to 5; nobody has been penalised/rewarded
        assert len(by_name(game, name).hand) == hands[name]
    assert game.current_player().name == 'Red'
    result = end_turn(game)
    assert result.get('pending_choice') is True                  # everyone failed: first discard asked
    assert game.event_progress['settlement_started'] is True


def test_red_actions_never_progress_a_non_red_player_but_can_change_a_state_condition():
    game = make_game('烏魯木齊七五事件', inside_orgs=False)
    ben, angie, red = game.players
    progress = game.event_progress
    angie.organizations = {'烏蘭巴托': 1}            # outside the wall: fails
    ben.organizations = {'成都': 1}                  # inside: succeeds ... unless Red removes it
    end_turn(game)
    end_turn(game)
    assert progress['settled'] is False
    red.hand = [card('代價')]
    assert game.dissolve_organization(red, ben, '成都', source='faction_action').get('success')
    end_turn(game)
    entries = progress['player_progress']
    assert entries[ben.id]['result'] == 'failure'
    assert entries[angie.id]['result'] == 'failure'


# ---------------------------------------------------------------------------
# Mixed outcomes and the reentrant pending queue
# ---------------------------------------------------------------------------

def test_mixed_outcomes_are_queued_in_seat_order_without_overwriting_pending_choices():
    game = make_game('重大災難', seats=('Ben', 'Angie', 'Cy', 'Red'))
    ben, angie, cy, red = game.players
    progress = game.event_progress
    end_turn(game)                                   # Ben: no trigger -> failure
    angie.hand.append(real_card(game, '宣傳家'))
    assert game.current_player() is angie
    assert game.play_card(len(angie.hand) - 1, mode='resource').get('success')  # Angie: propaganda card
    end_turn(game)
    end_turn(game)                                   # Cy: no trigger -> failure
    assert end_turn(game).get('pending_choice') is True

    entries = progress['player_progress']
    assert [entries[p.id]['result'] for p in (ben, angie, cy)] == ['failure', 'success', 'failure']
    # Ben's discard is first; Angie's reward and Cy's discard wait, in order, in the queue.
    assert (game.pending_choice['choice_key'], game.pending_choice['player_id']) == ('event_discard_self', ben.id)
    assert [(q['player_id'], q['outcome']) for q in progress['settlement_queue']] == [
        (angie.id, 'success'), (cy.id, 'failure'),
    ]
    gained_before = names(angie.deck.discard_pile).count('宣傳家')
    assert game.advance_turn_phase() == {'error': 'Resolve pending choice before advancing phase'}
    assert progress['settled'] is False

    cy_hand = len(cy.hand)
    ben_hand = len(ben.hand)
    assert game.resolve_pending_choice(ben.id, [0]).get('pending_choice') is True
    # Ben's penalty applied only to Ben; Angie's reward is now applied; Cy is asked next.
    assert len(ben.hand) == ben_hand - 1
    assert names(angie.deck.discard_pile).count('宣傳家') == gained_before + 1
    assert (game.pending_choice['choice_key'], game.pending_choice['player_id']) == ('event_discard_self', cy.id)
    assert len(cy.hand) == cy_hand
    assert progress['settled'] is False

    assert game.resolve_pending_choice(cy.id, [0]).get('success')
    assert len(cy.hand) == cy_hand - 1
    assert progress['settled'] is True
    assert progress['status'] == 'mixed'
    assert game.pending_choice is None
    assert game.current_player() is ben                           # only now does the seat move on


def test_every_failed_player_gets_their_own_red_dissolve_choice():
    game = make_game('全國人大召開', seats=('Ben', 'Angie', 'Cy', 'Red'))
    ben, angie, cy, red = game.players
    progress = game.event_progress
    for _ in range(3):
        end_turn(game)
    red.hand = [card(f'紅軍手牌{i}') for i in range(5)]
    seen = []
    result = end_turn(game)
    while game.pending_choice:
        choice = game.pending_choice
        assert (choice['choice_key'], choice['player_id']) == ('event_red_dissolve', red.id)
        owners = {t['player_id'] for t in choice['targets']}
        assert len(owners) == 1                       # one failed player's organizations at a time
        seen.append(owners.pop())
        assert game.resolve_pending_choice(red.id, 0).get('success')
    assert result.get('pending_choice') is True
    assert seen == [ben.id, angie.id, cy.id]
    for player in (ben, angie, cy):
        assert INSIDE[player.name] not in player.organizations
        assert player.base in player.organizations    # the base itself can never be dissolved
    assert progress['status'] == 'failure'


def test_failed_player_without_a_legal_red_dissolve_target_is_skipped_not_stuck():
    game = make_game('全國人大召開', seats=('Ben', 'Angie', 'Red'), inside_orgs=False)
    ben, angie, red = game.players
    progress = game.event_progress
    angie.organizations = {'烏蘭巴托': 1, '西安': 1}       # only Angie has a dissolvable 牆內 org
    end_turn(game)
    end_turn(game)
    red.hand = [card('代價')]
    result = end_turn(game)
    assert result.get('pending_choice') is True
    assert {t['player_id'] for t in game.pending_choice['targets']} == {angie.id}
    assert game.resolve_pending_choice(red.id, 0).get('success')
    assert progress['settled'] is True
    assert ben.organizations == {'澳門': 1}


def test_mongolian_school_without_red_hand_is_not_a_legal_event_dissolve_target():
    game = make_game('全國人大召開', seats=('Ben', 'Angie', 'Red'), inside_orgs=False)
    ben, angie, red = game.players
    angie.organizations = {'烏蘭巴托': 1, '西安': 1}
    assert game._event_red_dissolve_targets(angie, '牆內') != []
    red.hand = []
    assert game._event_red_dissolve_targets(angie, '牆內') == []


# ---------------------------------------------------------------------------
# Trigger attribution per trigger type
# ---------------------------------------------------------------------------

def test_trigger_progress_is_attributed_per_player_for_every_trigger_type():
    from validate_event_outcome_timing_audit import Audit

    triggers = {
        '重大災難': 'play_card_with_propaganda',
        '香港抗暴之戰': 'play_card_with_money',
        '貿易戰加劇': 'buy_card',
        '藏印邊境軍事對峙': 'build_organization',
        '紅軍權貴出逃': 'move_organization',
        '北京政爭': 'draw',
        '全國人大召開': 'use_faction_ability',
    }
    for event_name, trigger in triggers.items():
        run = Audit(event_name, with_inside_orgs=True)
        assert run.trigger['type'] == trigger
        end_turn(run.game)                       # Ben's turn, then Angie's: only Cy acts
        end_turn(run.game)
        assert run.game.current_player().name == 'Cy'
        assert run.satisfy('Cy') is True
        entries = run.progress_summary()
        assert entries['Cy']['met'] is True, (event_name, entries)
        assert entries['Ben']['met'] is False and entries['Angie']['met'] is False, (event_name, entries)
        assert 'Red' not in entries


def test_red_army_is_never_a_mission_participant():
    game = make_game('全國人大召開', seats=('Ben', 'Angie', 'Red'))
    red = by_name(game, 'Red')
    game._track_event_progress('use_faction_ability', player=red)
    game._track_event_progress('use_faction_ability')
    assert red.id not in game.event_progress['player_progress']
    assert game.event_progress['count'] == 0


def test_each_event_effect_applies_only_to_its_own_player_with_audit_harness():
    """The full per-card / per-player matrix lives in the audit validator; keep it green."""
    from validate_event_outcome_timing_audit import run_all_checks

    checks, mission_count = run_all_checks()
    failed = [c['name'] + ': ' + '; '.join(c['problems']) for c in checks if not c['passed']]
    assert mission_count == 14
    assert failed == []


# ---------------------------------------------------------------------------
# Data / non-mission events / state projection
# ---------------------------------------------------------------------------

def test_mission_cards_and_their_copies_are_all_per_player_and_identical():
    game = Game([('a', 'A'), ('b', 'B')])
    events = {e['name']: e for e in game.structured_events}
    missions = [e for e in events.values() if e.get('type') == 'mission']
    assert len(missions) == 14
    for event in missions:
        assert event['trigger'].get('each_non_red_player') is True, event['name']
        if event['name'].endswith('（副本）'):
            main = events[event['name'][:-len('（副本）')]]
            for key in ('type', 'trigger', 'success', 'failure'):
                assert event[key] == main[key], (event['name'], key)


def test_idle_and_auto_events_have_no_personal_outcomes():
    for event_name in ('歲月靜好', '上海合作組織'):
        game = make_game(event_name, seats=('Ben', 'Angie', 'Red'))
        assert 'player_progress' not in game.event_progress
        assert game._begin_event_settlement() is False
        before = {p.name: len(p.hand) for p in game.players}
        assert end_turn(game) == {'success': True}
        assert {p.name: len(p.hand) for p in game.players} == before


def test_event_notification_shows_each_players_own_progress_and_result():
    game = make_game('全國人大召開')
    use_ability(game, 'Ben')
    payload = game.state()['current_event']
    results = {entry['player_name']: entry for entry in payload['player_results']}
    assert set(results) == {'Ben', 'Angie'}
    assert results['Ben']['met'] is True and results['Angie']['met'] is False
    assert results['Ben']['result'] is None


def test_end_turn_topdeck_choice_still_settles_the_event_at_the_red_turn_end():
    game = make_game('重大災難', seats=('Ben', 'Angie', 'Red'))
    ben, angie, red = game.players
    end_turn(game)
    end_turn(game)
    first, second = card('頂牌甲'), card('頂牌乙')
    red.deck.discard_pile = [first, second]
    game.turn_log['pending_topdeck_uses'] = 1
    game.turn_log['purchased_cards_this_turn'] = [first, second]

    result = end_turn(game)
    assert result.get('pending_choice') is True
    assert game.pending_choice['choice_key'] == 'topdeck_purchased_choice'
    assert game.event_progress['settled'] is False

    resolved = game.resolve_pending_choice(red.id, 0)
    assert resolved.get('success')
    # The topdeck decision finished the Red turn, which is the settlement boundary.
    assert game.event_progress['settlement_started'] is True
    assert (game.pending_choice['choice_key'], game.pending_choice['player_id']) == ('event_discard_self', ben.id)
