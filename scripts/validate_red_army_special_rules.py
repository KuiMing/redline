import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'event-cards'
sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, TurnPhase


def ok(name, condition, detail=''):
    return {'name': name, 'ok': bool(condition), 'detail': detail}


def make_red_game():
    game = Game([('red', 'Red'), ('a', 'A'), ('b', 'B')], market_mode='all_cards')
    red, a, b = game.players
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    a.faction_id = 'liberals'
    a.base = '香港城'
    a.organizations = {'香港城': 1}
    b.faction_id = 'hong_kong'
    b.base = '香港城'
    b.organizations = {'上海': 1}
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.turn_log = game._new_turn_log()
    return game, red, a, b


def test_red_army_faction_action_can_be_reaction_canceled_before_effect():
    game, red, a, b = make_red_game()
    red.hand = []
    red.deck.draw_pile = [Card('補牌1', 'money', {'money': 1})]
    a.hand = [Card('爆料黑幕', 'command', {})]

    start = game._activated_faction_action(red, '統戰部')
    choice = game.state().get('pending_choice') or {}
    resolved = game.resolve_pending_choice(a.id, 1)

    return ok(
        'red_army_faction_action_can_be_reaction_canceled_before_effect',
        start.get('pending_choice')
        and choice.get('type') == 'reaction_choice'
        and choice.get('choice_key') == 'cancel_other_player_action'
        and choice.get('played_card_name') == '統戰部'
        and resolved.get('success')
        and resolved.get('reaction_card') == '爆料黑幕'
        and resolved.get('canceled_card') == '統戰部'
        and len(red.hand) == 0
        and game.turn_log.get('red_army_action_count', 0) == 0
        and [c.name for c in a.deck.discard_pile][-1:] == ['爆料黑幕'],
        f'start={start}, choice={choice}, resolved={resolved}, red_hand={[c.name for c in red.hand]}, turn_log={game.turn_log}, a_discard={[c.name for c in a.deck.discard_pile]}',
    )


def test_red_army_faction_action_resolves_after_reaction_skip():
    game, red, a, b = make_red_game()
    red.hand = []
    red.deck.draw_pile = [Card('補牌1', 'money', {'money': 1})]
    a.hand = [Card('情報網', 'command', {})]

    start = game._activated_faction_action(red, '統戰部')
    resolved = game.resolve_pending_choice(a.id, 0)

    return ok(
        'red_army_faction_action_resolves_after_reaction_skip',
        start.get('pending_choice')
        and resolved.get('success')
        and resolved.get('skipped_reaction')
        and len(red.hand) == 1
        and game.turn_log.get('red_army_action_count') == 1
        and len(a.hand) == 1,
        f'start={start}, resolved={resolved}, red_hand={[c.name for c in red.hand]}, a_hand={[c.name for c in a.hand]}, turn_log={game.turn_log}',
    )


def test_non_red_base_is_not_a_legal_dissolve_target():
    game, red, a, b = make_red_game()
    b.faction_id = 'taiwan_green'
    b.base = '臺北'
    b.organizations = {'臺北': 1, '大阪': 1}
    rejected = game.dissolve_organization(a, b, '臺北', source='card')
    targets = game._interactive_support_dissolve_targets(a, max_steps=99, target_players=[red, b])
    pairs = {(entry.get('player_id'), entry.get('town')) for entry in targets}

    return ok(
        'non_red_base_is_not_a_legal_dissolve_target',
        rejected.get('error') == 'Non-Red-Army bases cannot be dissolved'
        and b.organizations.get('臺北') == 1
        and (b.id, '臺北') not in pairs
        and (b.id, '大阪') in pairs
        and (red.id, '北京') in pairs,
        f'rejected={rejected}, pairs={sorted(pairs)}, b_orgs={b.organizations}',
    )


def test_one_player_two_successful_dissolves_disable_red_base_build_only_this_turn():
    game, red, a, b = make_red_game()
    red.organizations = {'北京': 1}
    first = game.dissolve_organization(a, red, '北京', source='card')
    second = game.dissolve_organization(a, red, '北京', source='card')
    blocked = '北京' in set(game.turn_log.get('red_army_base_build_blocks', []) or [])
    blocked_placement = game._place_organization(red, '北京', require_development=False)
    game.turn_log = game._new_turn_log()
    next_turn_placement = game._place_organization(red, '北京')

    return ok(
        'one_player_two_successful_dissolves_disable_red_base_build_only_this_turn',
        first.get('success')
        and second.get('success')
        and blocked
        and red.base == '北京'
        and not blocked_placement
        and next_turn_placement
        and red.organizations.get('北京') == 1,
        f'first={first}, second={second}, blocked={blocked}, base={red.base}, blocked_placement={blocked_placement}, next_turn_placement={next_turn_placement}, red_orgs={red.organizations}',
    )


def test_red_base_dissolve_counter_is_per_attacker_and_resets_each_turn():
    game, red, a, b = make_red_game()
    red.organizations = {'北京': 1}
    first = game.dissolve_organization(a, red, '北京', source='card')
    game.turn_log = game._new_turn_log()
    second = game.dissolve_organization(a, red, '北京', source='card')
    b_dissolve = game.dissolve_organization(b, red, '北京', source='card')
    blocked = bool(game.turn_log.get('red_army_base_build_blocks'))

    return ok(
        'red_base_dissolve_counter_is_per_attacker_and_resets_each_turn',
        first.get('success') and second.get('success') and b_dissolve.get('success') and not blocked and red.base == '北京',
        f'first={first}, second={second}, b_dissolve={b_dissolve}, blocked={blocked}, turn_log={game.turn_log}, base={red.base}',
    )


def test_red_army_organization_cannot_move_outside_red_development_space():
    game, red, a, b = make_red_game()
    red.organizations = {'北京': 1, '沖繩': 1}
    red.moves_left = 1
    result = game.move_organization('沖繩', '福岡', mode='road')

    return ok(
        'red_army_organization_cannot_move_outside_red_development_space',
        result.get('error') and 'development space' in result.get('error', '') and red.organizations.get('沖繩') == 1 and red.organizations.get('福岡', 0) == 0 and red.moves_left == 1,
        f'result={result}, red_orgs={red.organizations}, moves_left={red.moves_left}',
    )


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        test_red_army_faction_action_can_be_reaction_canceled_before_effect(),
        test_red_army_faction_action_resolves_after_reaction_skip(),
        test_non_red_base_is_not_a_legal_dissolve_target(),
        test_one_player_two_successful_dissolves_disable_red_base_build_only_this_turn(),
        test_red_base_dissolve_counter_is_per_attacker_and_resets_each_turn(),
        test_red_army_organization_cannot_move_outside_red_development_space(),
    ]
    summary = {
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    out = {'summary': summary, 'results': results}
    with open(RECORD_DIR / 'RED_ARMY_SPECIAL_RULES_RUNTIME_VALIDATION.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(RECORD_DIR / 'RED_ARMY_SPECIAL_RULES_RUNTIME_VALIDATION.md', 'w', encoding='utf-8') as f:
        f.write('# RED ARMY SPECIAL RULES RUNTIME VALIDATION\n\n')
        f.write(f"- total: {summary['total']}\n")
        f.write(f"- passed: {summary['passed']}\n")
        f.write(f"- failed: {summary['failed']}\n\n")
        for r in results:
            mark = 'PASS' if r['ok'] else 'FAIL'
            f.write(f"- {mark} {r['name']}: {r['detail']}\n")
    print(json.dumps(out, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
