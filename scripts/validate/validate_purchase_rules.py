import json
import random
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.game import Game, GamePhase, TurnPhase

OUT_JSON = BASE / 'docs' / 'records' / 'purchase' / 'PURCHASE_RULES_VALIDATION.json'
OUT_MD = BASE / 'docs' / 'records' / 'purchase' / 'PURCHASE_RULES_VALIDATION.md'


def card_names(cards):
    return [getattr(c, 'name', str(c)) for c in cards]


def make_game():
    random.seed(20260510)
    game = Game([('p1', 'actor'), ('p2', 'red')])
    actor = game.players[0]
    actor.id = 'p1'
    actor.name = 'actor'
    actor.faction_id = 'hong_kong'
    actor.base = '香港城'
    actor.organizations = {'香港城': 1}
    actor.resources = {'money': 0, 'propaganda': 0}
    actor.moves_left = 0

    other = game.players[1]
    other.id = 'p2'
    other.name = 'red'
    other.faction_id = 'red_army'
    other.base = '北京'
    other.organizations = {'北京': 1}

    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.END
    game.winner = None
    return game, actor


def check(name, passed, details):
    return {'name': name, 'passed': bool(passed), 'details': details}


def run_checks():
    checks = []

    # 1. Permanent/static purchase cards should be purchasable from the static area.
    game, actor = make_game()
    actor.resources = {'money': 0, 'propaganda': 3}
    static_index = 0  # 宣傳家: cost 0 money + 3 propaganda
    before_area_names = card_names(game.purchase_area)
    before_supply = game.static_purchase_supply.get('宣傳家')
    before_discard = card_names(actor.deck.discard_pile)
    result = game.buy_card(static_index)
    after_area_names = card_names(game.purchase_area)
    after_supply = game.static_purchase_supply.get('宣傳家')
    after_discard = card_names(actor.deck.discard_pile)
    checks.append(check(
        'static_purchase_card_can_be_bought_and_decrements_supply',
        result.get('success') is True
        and actor.resources == {'money': 0, 'propaganda': 0}
        and after_supply == before_supply - 1
        and after_area_names == before_area_names
        and after_discard == before_discard + ['宣傳家'],
        {
            'rule': '常設購買區的卡可被購買；購買後扣費、進玩家棄牌堆、常設庫存 -1，常設 slot 不消失。',
            'result': result,
            'resources_after': dict(actor.resources),
            'supply_before': before_supply,
            'supply_after': after_supply,
            'area_before': before_area_names,
            'area_after': after_area_names,
            'discard_before': before_discard,
            'discard_after': after_discard,
        }
    ))

    # 2. Permanent/static purchase cards should fail when stock is empty and preserve state.
    game, actor = make_game()
    actor.resources = {'money': 0, 'propaganda': 3}
    game.static_purchase_supply['宣傳家'] = 0
    before_resources = dict(actor.resources)
    before_discard = card_names(actor.deck.discard_pile)
    result = game.buy_card(static_index)
    checks.append(check(
        'static_purchase_card_cannot_be_bought_when_supply_empty',
        'error' in result
        and actor.resources == before_resources
        and game.static_purchase_supply.get('宣傳家') == 0
        and card_names(actor.deck.discard_pile) == before_discard,
        {
            'rule': '常設庫存為 0 時不可購買，且不扣費、不加牌。',
            'result': result,
            'resources_before': before_resources,
            'resources_after': dict(actor.resources),
            'discard_before': before_discard,
            'discard_after': card_names(actor.deck.discard_pile),
        }
    ))

    # 3. Support cards should charge their taxonomy cost (1 money + 2 propaganda).
    game, actor = make_game()
    static_count = len(game._static_purchase_cards())
    support_card = game._make_support_card('英美奧援')
    game.purchase_area = game._static_purchase_cards() + [support_card]
    actor.resources = {'money': 1, 'propaganda': 2}
    before_area_len = len(game.purchase_area)
    before_discard = card_names(actor.deck.discard_pile)
    result = game.buy_card(static_count)
    checks.append(check(
        'support_card_purchase_deducts_taxonomy_cost',
        result.get('success') is True
        and actor.resources == {'money': 0, 'propaganda': 0}
        and len(game.purchase_area) == before_area_len - 1
        and card_names(actor.deck.discard_pile) == before_discard + ['英美奧援'],
        {
            'rule': '奧援卡購買費用依 taxonomy：1 資金 + 2 宣傳；購買後進玩家棄牌堆並移出購買區。',
            'result': result,
            'resources_after': dict(actor.resources),
            'area_len_before': before_area_len,
            'area_len_after': len(game.purchase_area),
            'discard_before': before_discard,
            'discard_after': card_names(actor.deck.discard_pile),
        }
    ))

    # 4. Support cards should reject insufficient resources.
    game, actor = make_game()
    static_count = len(game._static_purchase_cards())
    game.purchase_area = game._static_purchase_cards() + [game._make_support_card('英美奧援')]
    actor.resources = {'money': 1, 'propaganda': 1}
    before_resources = dict(actor.resources)
    before_area_names = card_names(game.purchase_area)
    before_discard = card_names(actor.deck.discard_pile)
    result = game.buy_card(static_count)
    checks.append(check(
        'support_card_purchase_requires_taxonomy_cost',
        'error' in result
        and actor.resources == before_resources
        and card_names(game.purchase_area) == before_area_names
        and card_names(actor.deck.discard_pile) == before_discard,
        {
            'rule': '資源不足時不可購買奧援卡，且狀態不可改變。',
            'result': result,
            'resources_before': before_resources,
            'resources_after': dict(actor.resources),
            'area_before': before_area_names,
            'area_after': card_names(game.purchase_area),
            'discard_before': before_discard,
            'discard_after': card_names(actor.deck.discard_pile),
        }
    ))

    return checks


def write_reports(checks):
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        'total': len(checks),
        'passed': sum(1 for c in checks if c['passed']),
        'failed': sum(1 for c in checks if not c['passed']),
    }
    payload = {
        'generated_at': date.today().isoformat(),
        'rule_area': 'purchase_rules',
        'summary': summary,
        'checks': checks,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = [
        '# Purchase Rules Validation',
        '',
        f"Generated: {payload['generated_at']}",
        '',
        f"Summary: {summary['passed']}/{summary['total']} passed",
        '',
    ]
    for c in checks:
        status = 'PASS' if c['passed'] else 'FAIL'
        lines.append(f"## {status} — {c['name']}")
        lines.append('')
        lines.append('```json')
        lines.append(json.dumps(c['details'], ensure_ascii=False, indent=2))
        lines.append('```')
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    return summary


def main():
    checks = run_checks()
    summary = write_reports(checks)
    print(json.dumps({'summary': summary}, ensure_ascii=False))
    return 0 if summary['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
