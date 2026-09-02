import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'event-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, EVENT_DECK_SIZE

RUNS = 12


def _pool_counts(game):
    return Counter(card['name'] for card in game._initial_event_cards())


def main():
    results = []
    pool_counts = None
    for i in range(RUNS):
        g = Game([('p1', 'a'), ('p2', 'b')])
        pool_counts = _pool_counts(g)
        # Game.__init__ 若開局即進入 MAIN 會立刻抽出第一張事件（進 discard_pile 成為
        # current_event），所以牌庫總量 = draw_pile + discard_pile。
        all_deck_cards = list(g.event_deck.draw_pile) + list(g.event_deck.discard_pile)
        deck_counts = Counter(card['name'] for card in all_deck_cards)
        checks = {
            'deck_size_is_20': len(all_deck_cards) == EVENT_DECK_SIZE == 20,
            'deck_is_subset_of_pool': all(deck_counts[n] <= pool_counts[n] for n in deck_counts),
            'no_unknown_names': set(deck_counts) <= set(pool_counts),
        }
        results.append({
            'run': i + 1,
            'deck_size': len(all_deck_cards),
            'checks': checks,
            'ok': all(checks.values()),
        })

    pool_total = sum(pool_counts.values())
    # 至少一場的牌庫組成應與其他場不同（抽樣是隨機的；12 場全部同組成的機率趨近 0）
    compositions = set()
    for i in range(RUNS):
        g = Game([('p1', 'a'), ('p2', 'b')])
        cards = list(g.event_deck.draw_pile) + list(g.event_deck.discard_pile)
        compositions.add(tuple(sorted(Counter(c['name'] for c in cards).items())))
    sampling_varies = len(compositions) > 1

    summary = {
        'purpose': (
            'rules.md 步驟⑦: event deck = shuffle full pool then draw 20. Previously '
            '_initial_event_cards() fed the ENTIRE pool (25 copies after expanding '
            '卡牌張數; the second-pass audit initially said 33 but that mistakenly '
            'included era-card copies from the same CSV) into EventDeck. Now '
            '_draw_event_deck_cards() samples EVENT_DECK_SIZE=20 without replacement; '
            '_initial_event_cards() still returns the full declared-count pool so the '
            'existing declared-counts regression test is unaffected.'
        ),
        'pool_total_copies': pool_total,
        'event_deck_size_constant': EVENT_DECK_SIZE,
        'runs': RUNS,
        'sampling_varies_across_games': sampling_varies,
        'pool_composition': dict(sorted(pool_counts.items())),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    ok = summary['failed'] == 0 and pool_total == 25 and sampling_varies
    payload = {'summary': summary, 'results': results, 'ok': ok}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'EVENT_DECK_DRAW_TWENTY_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'EVENT_DECK_DRAW_TWENTY_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 事件牌庫抽出20張驗證\n\n'
        '可重跑指令：`python3 scripts/validate/validate_event_deck_draw_twenty.py`\n\n'
        f"- 全池張數（依卡牌張數展開）: {pool_total}\n"
        f"- 牌庫張數常數 EVENT_DECK_SIZE: {EVENT_DECK_SIZE}\n"
        f"- 驗證場數: {RUNS}（deck_size/subset/unknown-name 檢查全過: {summary['failed'] == 0}）\n"
        f"- 多場之間抽樣組成有變化（證明是隨機抽樣而非固定切片）: {sampling_varies}\n"
        f"- 全池組成: {json.dumps(dict(sorted(pool_counts.items())), ensure_ascii=False)}\n"
        f"- 結果: {'PASS' if ok else 'FAIL'}\n",
        encoding='utf-8',
    )
    print(json.dumps(payload['summary'], ensure_ascii=False))
    if not ok:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
