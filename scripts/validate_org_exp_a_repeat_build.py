import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card

CARD = '組織經驗甲'


def _new_game(hand_extra=None, faction_id='liberals'):
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = faction_id
    b.faction_id = 'red_army'
    a.organizations = {'上海': 1}
    b.organizations = {}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    a.hand = [Card(CARD, 'organization', {})] + list(hand_extra or [])
    a.resources = {'money': 0, 'propaganda': 0}
    return g, a, b


def _pick_town(g, player, town):
    pending = g.pending_choice or {}
    towns = [t.get('town') for t in (pending.get('towns') or [])]
    return g.resolve_pending_choice(player.id, towns.index(town)), towns


def case_full_repeat_loop():
    # 手上有 1 張 4 點以上（地下黨 2+4=6）與 1 張不合格（領導 0+1=1）
    g, a, b = _new_game(hand_extra=[Card('地下黨', 'spy', {}), Card('領導', 'command', {})])
    played = g.play_card(0, mode='action')
    first_build, towns_offered = _pick_town(g, a, '北京')
    pending = g.pending_choice or {}
    checks = {
        'build_choice_opened': played.get('pending_choice') is True,
        'first_build_done': a.organizations.get('北京', 0) == 1,
        'repeat_prompt_opened': pending.get('choice_key') == 'org_exp_repeat_prompt',
    }
    # 選「棄牌再建立」
    labels = [o.get('label') for o in pending.get('options') or []]
    accepted = g.resolve_pending_choice(a.id, labels.index('棄1張購買費用4點以上的牌，再建立1次'))
    pending = g.pending_choice or {}
    offered_cards = [getattr(c, 'name', str(c)) for c in (pending.get('cards') or [])]
    checks.update({
        'discard_choice_opened': pending.get('choice_key') == 'org_exp_repeat_discard',
        'only_qualifying_cards_offered': offered_cards == ['地下黨'],  # 領導不合格不應出現
    })
    discarded = g.resolve_pending_choice(a.id, 0)
    pending = g.pending_choice or {}
    checks.update({
        'card_discarded': any(getattr(c, 'name', str(c)) == '地下黨' for c in a.deck.discard_pile),
        'second_build_choice_opened': pending.get('choice_key') == 'card_build_organization',
    })
    second_build, _ = _pick_town(g, a, '天津')
    checks.update({
        'second_build_done': a.organizations.get('天津', 0) == 1,
        'loop_ends_without_qualifying_cards': not g.pending_choice,  # 沒有4點以上手牌了，不再詢問
    })
    return {'name': 'full_repeat_loop_build_discard_build', 'checks': checks, 'ok': all(checks.values())}


def case_decline_keeps_hand():
    g, a, b = _new_game(hand_extra=[Card('地下黨', 'spy', {})])
    g.play_card(0, mode='action')
    _pick_town(g, a, '北京')
    pending = g.pending_choice or {}
    labels = [o.get('label') for o in pending.get('options') or []]
    declined = g.resolve_pending_choice(a.id, labels.index('不再建立'))
    checks = {
        'declined_ok': declined.get('success') is True and declined.get('declined') is True,
        'no_pending_after_decline': not g.pending_choice,
        'qualifying_card_kept_in_hand': any(getattr(c, 'name', str(c)) == '地下黨' for c in a.hand),
        'only_one_build': a.organizations.get('北京', 0) == 1 and a.total_organizations() == 2,
    }
    return {'name': 'decline_keeps_hand_and_ends_flow', 'checks': checks, 'ok': all(checks.values())}


def case_no_qualifying_cards_no_prompt():
    g, a, b = _new_game(hand_extra=[Card('領導', 'command', {})])  # 只有1點的牌
    g.play_card(0, mode='action')
    result, _ = _pick_town(g, a, '北京')
    checks = {
        'build_done': a.organizations.get('北京', 0) == 1,
        'no_repeat_prompt': not g.pending_choice,
    }
    return {'name': 'no_qualifying_cards_no_prompt', 'checks': checks, 'ok': all(checks.values())}


def case_multi_repeat_two_qualifying():
    g, a, b = _new_game(hand_extra=[Card('地下黨', 'spy', {}), Card('擴大戰果', 'command', {})])  # 6點與4點
    g.play_card(0, mode='action')
    _pick_town(g, a, '北京')
    for town in ('天津', '上海'):
        pending = g.pending_choice or {}
        labels = [o.get('label') for o in pending.get('options') or []]
        g.resolve_pending_choice(a.id, labels.index('棄1張購買費用4點以上的牌，再建立1次'))
        g.resolve_pending_choice(a.id, 0)  # 棄第一張合格牌
        pending = g.pending_choice or {}
        towns = [t.get('town') for t in (pending.get('towns') or [])]
        g.resolve_pending_choice(a.id, towns.index(town))
    checks = {
        'three_builds_total': a.total_organizations() == 4,  # 起始1 + 建立3
        'loop_ended': not g.pending_choice,
        'both_cards_discarded': sorted(
            getattr(c, 'name', str(c)) for c in a.deck.discard_pile
            if getattr(c, 'name', str(c)) in {'地下黨', '擴大戰果'}
        ) == ['地下黨', '擴大戰果'],
    }
    return {'name': 'two_repeats_with_two_qualifying_cards', 'checks': checks, 'ok': all(checks.values())}


def case_restricted_faction_repeat_respects_distance():
    # 維吾爾（受新疆社會管控）：重複建立的城鎮清單也要遵守「牆內限1格」降級
    g, a, b = _new_game(hand_extra=[Card('地下黨', 'spy', {})], faction_id='uyghur_munich')
    a.organizations = {'喀什': 1}
    inner = set(g._towns_for_region_alias('china'))
    near = g._towns_within_steps(['喀什'], max_steps=1)
    g.play_card(0, mode='action')
    pending = g.pending_choice or {}
    towns1 = {t.get('town') for t in (pending.get('towns') or [])}
    checks = {'first_list_inner_limited_to_1_step': not ((towns1 & inner) - near)}
    first_inner = sorted(towns1 & inner)[0]
    towns_list = [t.get('town') for t in (pending.get('towns') or [])]
    g.resolve_pending_choice(a.id, towns_list.index(first_inner))
    pending = g.pending_choice or {}
    if pending.get('choice_key') == 'org_exp_repeat_prompt':
        labels = [o.get('label') for o in pending.get('options') or []]
        g.resolve_pending_choice(a.id, labels.index('棄1張購買費用4點以上的牌，再建立1次'))
        g.resolve_pending_choice(a.id, 0)
        pending = g.pending_choice or {}
        towns2 = {t.get('town') for t in (pending.get('towns') or [])}
        near2 = g._towns_within_steps([t for t, c in a.organizations.items() if c > 0], max_steps=1)
        checks['repeat_list_inner_limited_to_1_step'] = not ((towns2 & inner) - near2)
    else:
        checks['repeat_list_inner_limited_to_1_step'] = False
    return {'name': 'restricted_faction_repeat_respects_inner_distance', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_full_repeat_loop(),
        case_decline_keeps_hand(),
        case_no_qualifying_cards_no_prompt(),
        case_multi_repeat_two_qualifying(),
        case_restricted_faction_repeat_respects_distance(),
    ]
    summary = {
        'scope': [CARD],
        'purpose': (
            'B3 remainder + P1 playtest item: 組織經驗甲\'s printed clause "每從手上棄掉1張'
            '購買費用4點以上的牌，可重複上述動作1次" had no implementation, and playtest '
            'reported the missing confirmation flow. Now after each build resolves, if the '
            'hand holds any card whose purchase cost totals >=4 AND a legal build town exists '
            '(supply limit / distance restrictions included), an explicit confirm prompt '
            'opens (不再建立 / 棄1張再建立1次); accepting opens a card choice limited to '
            'qualifying cards, discarding reopens the build town choice with the same effect '
            'context (so 新疆社會管控\'s inner 1-step downgrade carries through), looping '
            'until the player declines or runs out of qualifying cards/towns. Declining or '
            'lacking qualifiers never auto-consumes anything.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'ORG_EXP_A_REPEAT_BUILD_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'ORG_EXP_A_REPEAT_BUILD_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 組織經驗甲 重複建立子句驗證\n\n'
        '可重跑指令：`python3 scripts/validate_org_exp_a_repeat_build.py`\n\n'
        f"- total: {summary['total']} / passed: {summary['passed']} / failed: {summary['failed']}\n\n"
        '## Results\n\n'
        + '\n'.join(
            f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: checks={json.dumps(r['checks'], ensure_ascii=False)}"
            for r in results
        )
        + '\n',
        encoding='utf-8',
    )
    print(json.dumps(payload, ensure_ascii=False, default=str))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
