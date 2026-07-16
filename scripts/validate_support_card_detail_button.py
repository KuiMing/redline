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
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'SUPPORT_CARD_DETAIL_BUTTON_VALIDATION.json'
OUT_MD = RECORD_DIR / 'SUPPORT_CARD_DETAIL_BUTTON_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'support_card_detail_button.png'


def post_json(path, payload=None):
    data = json.dumps(payload or {}).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def hand_card_buttons(page, card_name):
    return page.evaluate(
        """(name) => {
          const card = [...document.querySelectorAll('#hand .hand-card')].find(c => c.innerText.includes(name));
          if (!card) return null;
          return [...card.querySelectorAll('.hand-card-action-btn')].map(b => ({
            text: b.textContent.trim(), mode: b.dataset.cardMode, disabled: b.disabled,
          }));
        }""",
        card_name,
    )


def check(browser):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    # --- Case 1: a regular support card (臺灣奧援) shows 詳情 instead of 資源 ---
    page = browser.new_context(viewport={'width': 1280, 'height': 900}).new_page()
    setup = post_json('/test/setup-support-proof', {'support_name': '臺灣奧援', 'tier': 2})
    page.goto(f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}", wait_until='networkidle')
    page.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page.wait_for_timeout(900)
    page.evaluate("() => { const b = document.getElementById('closeFactionActionModal'); if (b) b.click(); }")
    page.wait_for_timeout(300)

    buttons = hand_card_buttons(page, '臺灣奧援')
    record(
        'support_card_shows_detail_and_discard_not_labeled_resource',
        buttons is not None and any(b['mode'] == 'detail' and b['text'] == '詳情' for b in buttons)
        and any(b['mode'] == 'resource' and b['text'] == '棄置' for b in buttons)
        and not any(b['text'] == '資源' for b in buttons),
        {'buttons': buttons},
    )
    detail_disabled = next((b['disabled'] for b in (buttons or []) if b['mode'] == 'detail'), None)
    record('detail_button_is_never_disabled', detail_disabled is False, {'detail_disabled': detail_disabled})

    before_hand = page.evaluate(
        "(id) => window.lastGameState?.players?.find(p => p.id === id)?.hand || []", setup['player_id']
    )
    page.click("#hand .hand-card-detail-btn")
    page.wait_for_timeout(400)
    after_hand = page.evaluate(
        "(id) => window.lastGameState?.players?.find(p => p.id === id)?.hand || []", setup['player_id']
    )
    flash_applied = page.evaluate(
        "() => document.querySelector('#hand .hand-card')?.classList.contains('hand-card-detail-flash')"
    )
    record(
        'clicking_detail_does_not_consume_or_play_the_card',
        before_hand == ['臺灣奧援'] and after_hand == ['臺灣奧援'],
        {'before_hand': before_hand, 'after_hand': after_hand},
    )
    record('clicking_detail_flashes_the_card_for_feedback', flash_applied is True, {'flash_applied': flash_applied})

    page.screenshot(path=str(SCREENSHOT))

    # Full I/II/III effect text is already on the card face (no separate modal needed).
    face_text = page.inner_text('#hand .hand-card .card-effect-block')
    record(
        'card_face_already_shows_all_three_tier_effect_lines',
        all(tier in face_text for tier in ('III級', 'II級', 'I級')),
        {'face_text': face_text},
    )
    page.close()

    # --- Case 2: 紅軍奧援 (special support card) also gets 詳情, not 資源 ---
    page2 = browser.new_context(viewport={'width': 1280, 'height': 900}).new_page()
    setup2 = post_json('/test/setup-support-proof', {'support_name': '紅軍奧援', 'tier': 1})
    page2.goto(f"{BASE_URL}/?game_id={setup2['game_id']}&player_id={setup2['player_id']}", wait_until='networkidle')
    page2.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page2.wait_for_timeout(900)
    page2.evaluate("() => { const b = document.getElementById('closeFactionActionModal'); if (b) b.click(); }")
    page2.wait_for_timeout(300)
    buttons2 = hand_card_buttons(page2, '紅軍奧援')
    record(
        'red_army_support_card_also_shows_detail_and_discard_not_labeled_resource',
        buttons2 is not None and any(b['mode'] == 'detail' for b in buttons2)
        and any(b['mode'] == 'resource' and b['text'] == '棄置' for b in buttons2)
        and not any(b['text'] == '資源' for b in buttons2),
        {'buttons': buttons2},
    )
    page2.close()

    # --- Case 3: a non-support card (regular action card) keeps its normal 資源 button ---
    page3 = browser.new_context(viewport={'width': 1280, 'height': 900}).new_page()
    setup3 = post_json('/test/setup-move-confirmation-proof', {'mover_faction': 'liberals', 'mover_base': '臺北', 'mover_town': '臺北', 'moves_left': 0})
    post_json('/test/setup-card-scenario', {'game_id': setup3['game_id'], 'player_id': setup3['player_id'], 'card_name': '宣傳家'})
    page3.goto(f"{BASE_URL}/?game_id={setup3['game_id']}&player_id={setup3['player_id']}", wait_until='networkidle')
    page3.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page3.wait_for_timeout(900)
    page3.evaluate("() => { const b = document.getElementById('closeFactionActionModal'); if (b) b.click(); }")
    page3.wait_for_timeout(300)
    buttons3 = hand_card_buttons(page3, '宣傳家')
    record(
        'non_support_card_keeps_the_resource_button',
        buttons3 is not None and any(b['mode'] == 'resource' and b['text'] == '資源' for b in buttons3)
        and not any(b['mode'] == 'detail' for b in buttons3),
        {'buttons': buttons3},
    )
    page3.close()

    return {
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
        payload = check(browser)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 奧援卡「資源」按鈕改「詳情」驗證',
        '',
        '可重跑指令：`python3 scripts/validate_support_card_detail_button.py`',
        '',
        f"- total: {payload['summary']['total']} / passed: {payload['summary']['passed']} / failed: {payload['summary']['failed']}",
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
