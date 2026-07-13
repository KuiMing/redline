import json
import os
import sys
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    system_python = '/usr/bin/python3'
    if sys.executable != system_python and Path(system_python).exists():
        os.execv(system_python, [system_python, __file__, *sys.argv[1:]])
    raise

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'playtest-flow'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'DISCARD_CHOICE_SCROLL_VALIDATION.json'
OUT_MD = RECORD_DIR / 'DISCARD_CHOICE_SCROLL_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'discard_choice_scroll_validation.png'
DISCARD_COUNT = 18


def post_json(path, payload=None):
    data = json.dumps(payload or {}).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def check(page):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    setup = post_json('/test/setup-discard-topdeck-choice', {'discard_count': DISCARD_COUNT})
    record('setup_succeeded', setup.get('success') and setup.get('discard_count') == DISCARD_COUNT, {'discard_count': setup.get('discard_count')})

    page.goto(BASE_URL + setup['url'], wait_until='networkidle')
    page.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page.wait_for_selector('#choiceModal', state='visible', timeout=10000)
    page.wait_for_timeout(400)

    metrics = page.evaluate(
        """() => {
          const overlay = document.getElementById('choiceModal');
          const grid = document.getElementById('choiceModalCards');
          const closeBtn = document.getElementById('closeChoiceModal');
          const cs = getComputedStyle(grid);
          const overlayRect = overlay.getBoundingClientRect();
          const closeRect = closeBtn.getBoundingClientRect();
          return {
            cardCount: grid.querySelectorAll('.choice-card-btn, .choice-card-btn-multi, button, .modal-choice-btn').length,
            overflowY: cs.overflowY,
            scrollHeight: grid.scrollHeight,
            clientHeight: grid.clientHeight,
            overlayBottom: overlayRect.bottom,
            closeBtnBottom: closeRect.bottom,
            closeBtnVisible: closeRect.bottom <= overlayRect.bottom + 1 && closeRect.top >= overlayRect.top - 1,
          };
        }"""
    )
    record('modal_lists_all_discard_cards', metrics['cardCount'] >= DISCARD_COUNT, {'cardCount': metrics['cardCount'], 'expected_min': DISCARD_COUNT})
    record('card_grid_is_scrollable_overflow_auto', metrics['overflowY'] in ('auto', 'scroll'), {'overflowY': metrics['overflowY']})
    record(
        'content_overflows_so_the_grid_actually_scrolls',
        metrics['scrollHeight'] > metrics['clientHeight'] + 1,
        {'scrollHeight': metrics['scrollHeight'], 'clientHeight': metrics['clientHeight']},
    )
    record(
        'close_button_stays_within_modal_bounds_not_cut_off',
        metrics['closeBtnVisible'],
        {'overlayBottom': metrics['overlayBottom'], 'closeBtnBottom': metrics['closeBtnBottom']},
    )

    # Confirm the last card can actually be reached by scrolling the grid to the bottom.
    scrolled = page.evaluate(
        """() => {
          const grid = document.getElementById('choiceModalCards');
          grid.scrollTop = grid.scrollHeight;
          return { scrollTop: grid.scrollTop, maxScroll: grid.scrollHeight - grid.clientHeight };
        }"""
    )
    record(
        'grid_can_scroll_to_reveal_the_last_cards',
        scrolled['scrollTop'] >= scrolled['maxScroll'] - 1 and scrolled['maxScroll'] > 0,
        scrolled,
    )

    page.evaluate("() => { document.getElementById('choiceModalCards').scrollTop = 0; }")
    page.wait_for_timeout(200)
    page.screenshot(path=str(SCREENSHOT))
    return {
        'game_id': setup['game_id'],
        'summary': {
            'total': len(results),
            'passed': sum(1 for r in results if r['ok']),
            'failed': sum(1 for r in results if not r['ok']),
        },
        'results': results,
        'screenshot': str(SCREENSHOT),
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={'width': 1280, 'height': 800}).new_page()
        payload = check(page)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# Discard choice grid scroll validation',
        '',
        f"- game_id: {payload['game_id']}",
        f"- total: {payload['summary']['total']}",
        f"- passed: {payload['summary']['passed']}",
        f"- failed: {payload['summary']['failed']}",
        f"- screenshot: {payload['screenshot']}",
        '',
        '## Results',
    ]
    for r in payload['results']:
        lines.append(f"- {'✅' if r['ok'] else '❌'} `{r['name']}` — {json.dumps(r['detail'], ensure_ascii=False)}")
    lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(payload['summary'], ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
