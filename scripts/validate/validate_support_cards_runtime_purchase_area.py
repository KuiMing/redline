import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'support-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    g = Game([('p1', 'Tibet'), ('p2', 'Other')])
    t, o = g.players
    t.faction_id = 'tibet_dehradun'
    t.base = '德拉敦'
    t.organizations = {'德拉敦': 1}
    o.faction_id = 'red_army'
    o.base = '北京'
    o.organizations = {'北京': 1}
    # 2026-06-26 起 buy_card 僅限購買（END）階段；本腳本只驗購買行為，直接設 END。
    g.turn_phase = TurnPhase.END
    g.current_player_index = 0

    purchase_names = [getattr(card, 'name', str(card)) for card in g.purchase_area]
    if '印度奧援' not in purchase_names:
        g.purchase_area.append(g._make_support_card('印度奧援'))
        purchase_names = [getattr(card, 'name', str(card)) for card in g.purchase_area]
    has_india_support = '印度奧援' in purchase_names

    t.resources = {'money': 5, 'propaganda': 5}
    idx_india = purchase_names.index('印度奧援') if has_india_support else -1
    buy_india = g.buy_card(idx_india) if idx_india >= 0 else {'error': '印度奧援 not found'}

    g.purchase_area = [g._make_support_card('英美奧援')]
    buy_anglo = g.buy_card(0)

    payload = {
        'summary': {
            'total': 3,
            'passed': sum([
                has_india_support,
                buy_india.get('success') is True,
                buy_anglo.get('error') == '印度研究分析室：不能持有印度旗幟以外的旗幟卡',
            ]),
            'failed': 3 - sum([
                has_india_support,
                buy_india.get('success') is True,
                buy_anglo.get('error') == '印度研究分析室：不能持有印度旗幟以外的旗幟卡',
            ]),
        },
        'purchase_area': purchase_names,
        'buy_india': buy_india,
        'buy_anglo': buy_anglo,
    }
    (RECORD_DIR / 'SUPPORT_CARDS_RUNTIME_PURCHASE_AREA_VALIDATION.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (RECORD_DIR / 'SUPPORT_CARDS_RUNTIME_PURCHASE_AREA_VALIDATION.md').write_text(
        '# SUPPORT CARDS RUNTIME PURCHASE AREA VALIDATION\n\n'
        f"- purchase_area: {json.dumps(purchase_names, ensure_ascii=False)}\n"
        f"- buy_india: {json.dumps(buy_india, ensure_ascii=False)}\n"
        f"- buy_anglo: {json.dumps(buy_anglo, ensure_ascii=False)}\n",
        encoding='utf-8'
    )
    print(json.dumps(payload, ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
