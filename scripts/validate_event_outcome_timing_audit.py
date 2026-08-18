#!/usr/bin/env python3
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.cards import Card  # noqa: E402
from server.game import Game, GamePhase, TurnPhase  # noqa: E402

RECORD_DIR = ROOT / 'docs' / 'records' / 'event-cards'
JSON_OUT = RECORD_DIR / 'EVENT_OUTCOME_TIMING_AUDIT.json'
MD_OUT = RECORD_DIR / 'EVENT_OUTCOME_TIMING_AUDIT.md'


def card(name):
    return Card(name, 'command', {})


def names(cards):
    return [getattr(c, 'name', str(c)) for c in cards]


def make_game(event_name, succeeded=False, last_actor=True):
    game = Game([('viewer-id', 'viewer'), ('ally-id', 'ally'), ('red-id', 'red')], market_mode='all_cards')
    fixtures = [
        ('liberals', '臺北'),
        ('hong_kong', '香港城'),
        ('red_army', '北京'),
    ]
    for player, (faction, base) in zip(game.players, fixtures):
        player.faction_id = faction
        player.base = base
        player.organizations = {base: 1}
        player.hand = []
        player.deck.draw_pile = [card(f'{player.name}補牌{i + 1}') for i in range(5)]
        player.deck.discard_pile = []
        player.moves_left = 0
    viewer, ally, red = game.players
    game.pending_base_choices = {}
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 1  # ally is final non-red before red
    game.round_start_player_index = 0
    game.turn_phase = TurnPhase.END
    event = game._event_by_name(event_name)
    assert event, f'missing event {event_name}'
    game.current_event = event
    game.event_progress = {
        'count': 999 if succeeded else 0,
        'required': 1,
        'succeeded': succeeded,
        'settled': False,
        'status': 'success_pending' if succeeded else 'active',
    }
    if last_actor:
        game.event_progress['last_actor_id'] = ally.id
        game.event_progress['last_actor_name'] = ally.name
    game.event_notification = game._event_display_payload()
    game.pending_choice = None
    game.action_log = []
    return game, viewer, ally, red


def run_end(game):
    before = snapshot(game)
    result = game.advance_turn_phase()
    after = snapshot(game)
    return {'result': result, 'before': before, 'after': after, 'log': list(game.action_log), 'pending_choice': game.state().get('pending_choice'), 'event_progress': dict(game.event_progress or {}), 'current_player': game.current_player().name, 'phase': str(game.turn_phase)}


def snapshot(game):
    return {
        p.name: {
            'hand': names(p.hand),
            'draw': names(p.deck.draw_pile),
            'discard': names(p.deck.discard_pile),
            'moves_left': p.moves_left,
            'orgs': dict(p.organizations),
        }
        for p in game.players
    }


def check_failure_discard_self(event_name):
    game, viewer, ally, red = make_game(event_name, succeeded=False)
    r = run_end(game)
    choice = r['pending_choice'] or {}
    return {
        'name': f'{event_name} failure discard_self after refill',
        'passed': r['current_player'] == 'red' and choice.get('choice_key') == 'event_discard_self' and choice.get('player_id') == ally.id and len(choice.get('cards') or []) == 5,
        'details': r,
    }


def check_failure_discard_random(event_name):
    game, viewer, ally, red = make_game(event_name, succeeded=False)
    viewer.hand = [card('viewer既有手牌')]
    is_urumqi = '烏魯木齊七五事件' in event_name
    if is_urumqi:
        # Outside-the-wall org (臺北 is 臺灣, not 牆內): the own_organization_in_scope live
        # check fails at settlement -> discard_random failure penalty.
        ally.organizations = {'臺北': 1}
    r = run_end(game)
    if is_urumqi:
        # 烏魯木齊七五事件 is the sole `end_turn_state` (live-state) mission: it settles only
        # at the TRUE round-wrap boundary (after Red Army's own turn too), so after the final
        # non-red player's END it is still UNSETTLED. Drive Red Army's turn + the wrap.
        deferred_ok = r['current_player'] == 'red' and not r['event_progress'].get('settled')
        game.turn_phase = TurnPhase.ACTION
        game.advance_turn_phase()   # 結束行動階段 -> _end_turn wraps round -> deferred settlement
        passed = (
            deferred_ok
            and len(ally.hand) == 4
            and len(ally.deck.discard_pile) == 1
            and any('烏魯木齊七五事件' in line and 'failure' in line for line in game.action_log)
        )
        return {
            'name': f'{event_name} failure discard_random after full round wrap',
            'passed': passed,
            'details': {'deferred_ok': deferred_ok, 'ally_hand': len(ally.hand), 'log': list(game.action_log)},
        }
    return {
        'name': f'{event_name} failure discard_random after refill',
        'passed': r['current_player'] == 'red' and len(game.players[1].hand) == 4 and len(game.players[1].deck.discard_pile) == 1 and len(red.hand) == 0,
        'details': r,
    }


def check_failure_red_dissolve(event_name):
    game, viewer, ally, red = make_game(event_name, succeeded=False)
    viewer.organizations = {'北京': 1}
    ally.organizations = {'上海': 1}
    r = run_end(game)
    choice = r['pending_choice'] or {}
    return {
        'name': f'{event_name} failure red_dissolve after refill',
        'passed': r['current_player'] == 'red' and choice.get('choice_key') == 'event_red_dissolve' and choice.get('player_id') == red.id and len(ally.hand) == 5,
        'details': r,
    }


def check_failure_none(event_name):
    game, viewer, ally, red = make_game(event_name, succeeded=False)
    r = run_end(game)
    return {
        'name': f'{event_name} failure none after refill no-op',
        'passed': r['current_player'] == 'red' and r['pending_choice'] is None and len(ally.hand) == 5 and r['event_progress'].get('settled') is True,
        'details': r,
    }


def check_success_gain_card(event_name):
    game, viewer, ally, red = make_game(event_name, succeeded=True)
    before_supply = game.static_purchase_supply.get('宣傳家', 0)
    r = run_end(game)
    return {
        'name': f'{event_name} success gain_card after refill',
        'passed': r['current_player'] == 'red' and len(ally.hand) == 5 and names(ally.deck.discard_pile).count('宣傳家') >= 1 and game.static_purchase_supply.get('宣傳家', 0) < before_supply,
        'details': r,
    }


def check_success_draw(event_name):
    game, viewer, ally, red = make_game(event_name, succeeded=True)
    ally.deck.draw_pile = [card(f'補牌{i + 1}') for i in range(6)]
    r = run_end(game)
    return {
        'name': f'{event_name} success draw after refill',
        'passed': r['current_player'] == 'red' and len(ally.hand) == 6,
        'details': r,
    }


def check_success_move(event_name):
    game, viewer, ally, red = make_game(event_name, succeeded=True)
    r = run_end(game)
    return {
        'name': f'{event_name} success move after reset/refill',
        'passed': r['current_player'] == 'red' and ally.moves_left == 2 and len(ally.hand) == 5,
        'details': r,
    }


def check_success_topdeck(event_name):
    game, viewer, ally, red = make_game(event_name, succeeded=True)
    ally.deck.discard_pile = [card('可置頂牌')]
    r = run_end(game)
    choice = r['pending_choice'] or {}
    return {
        'name': f'{event_name} success topdeck before refill',
        'passed': r['current_player'] == 'ally' and r['phase'] == 'TurnPhase.END' and choice.get('choice_key') == 'event_topdeck_from_discard' and len(ally.hand) == 0,
        'details': r,
    }


def check_success_trash(event_name):
    game, viewer, ally, red = make_game(event_name, succeeded=True)
    ally.deck.discard_pile = [card('棄牌可移除')]
    r = run_end(game)
    choice = r['pending_choice'] or {}
    return {
        'name': f'{event_name} success trash hand/discard after refill',
        'passed': r['current_player'] == 'red' and choice.get('choice_key') == 'trash_from_hand_or_discard' and choice.get('player_id') == ally.id and len(choice.get('cards') or []) >= 6,
        'details': r,
    }


def check_success_build_near(event_name):
    # 烏魯木齊七五事件 is the sole `end_turn_state` (live-state) mission. Its state check must
    # be judged at the TRUE round-wrap boundary (after Red Army's own turn too), not at the
    # final non-red turn — so unlike count-based missions it stays UNSETTLED after the last
    # non-red player's END and only settles once Red Army has also acted and the round wraps.
    game, viewer, ally, red = make_game(event_name, succeeded=True)
    ally.organizations = {'香港城': 1}
    r = run_end(game)   # ally (final non-red) END -> Red Army seat; must NOT settle yet
    deferred_ok = r['current_player'] == 'red' and not r['event_progress'].get('settled')
    game.turn_phase = TurnPhase.ACTION
    game.advance_turn_phase()   # 結束行動階段 -> _end_turn wraps round -> deferred settlement
    choice = game.pending_choice or {}
    return {
        'name': f'{event_name} success build after full round wrap',
        'passed': deferred_ok and choice.get('choice_key') == 'event_build_organization' and choice.get('player_id') == ally.id and len(ally.hand) == 5,
        'details': {'deferred_ok': deferred_ok, 'pending_choice': choice, 'log': list(game.action_log)},
    }


def main():
    checks = [
        check_success_draw('全國人大召開'),
        check_failure_red_dissolve('全國人大召開'),
        check_success_gain_card('香港抗暴之戰'),
        check_failure_discard_self('香港抗暴之戰'),
        check_success_gain_card('重大災難'),
        check_failure_discard_self('重大災難'),
        check_success_move('藏印邊境軍事對峙'),
        check_failure_none('藏印邊境軍事對峙'),
        check_success_topdeck('貿易戰加劇'),
        check_failure_none('貿易戰加劇'),
        check_success_gain_card('東突厥集中營'),
        check_failure_discard_random('東突厥集中營'),
        check_success_draw('北京政爭'),
        check_failure_none('北京政爭'),
        check_success_trash('紅軍權貴出逃'),
        check_failure_discard_self('紅軍權貴出逃'),
        check_success_build_near('烏魯木齊七五事件'),
        check_failure_discard_random('烏魯木齊七五事件'),
        check_success_gain_card('重大災難（副本）'),
        check_failure_discard_self('重大災難（副本）'),
        check_success_draw('全國人大召開（副本）'),
        check_failure_red_dissolve('全國人大召開（副本）'),
        check_success_topdeck('貿易戰加劇（副本）'),
        check_failure_none('貿易戰加劇（副本）'),
        check_success_move('藏印邊境軍事對峙（副本）'),
        check_failure_none('藏印邊境軍事對峙（副本）'),
        check_success_trash('紅軍權貴出逃（副本）'),
        check_failure_discard_self('紅軍權貴出逃（副本）'),
    ]
    summary = {'total': len(checks), 'passed': sum(1 for c in checks if c['passed']), 'failed': sum(1 for c in checks if not c['passed'])}
    payload = {'summary': summary, 'checks': checks}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# Event outcome timing audit', '', f"- total: `{summary['total']}`", f"- passed: `{summary['passed']}`", f"- failed: `{summary['failed']}`", '']
    for c in checks:
        mark = '✅' if c['passed'] else '❌'
        lines.append(f"- {mark} {c['name']}")
    MD_OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    if summary['failed']:
        failed = [c['name'] for c in checks if not c['passed']]
        print(json.dumps({'failed': failed}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
