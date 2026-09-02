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

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'support-cards'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'SUPPORT_CARD_VARIANT_AND_DISCARD_VALIDATION.json'
OUT_MD = RECORD_DIR / 'SUPPORT_CARD_VARIANT_AND_DISCARD_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'support_card_variant_and_discard.png'


def post_json(path, payload=None):
    data = json.dumps(payload or {}).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


# 2026-07-16 使用者裁決：奧援卡實體上一張只印一組 II 級門檻地區（見 support_cards.csv
# 兩列）；同名卡的兩種變體不應互相干擾——手上這張牌只看自己印的那組地區。
# 英美奧援 own region (III 級) = 英美；variant 0 印 歐洲/天方；variant 1 印 東洋/臺灣。
VARIANT_TIER_CASES = [
    {'name': 'variant0_matches_own_pair', 'variant_index': 0, 'orgs': {'伊斯坦堡': 1}, 'expected_tier': 2},
    {'name': 'variant0_ignores_other_variant_pair', 'variant_index': 0, 'orgs': {'東京': 1}, 'expected_tier': 1},
    {'name': 'variant1_matches_own_pair', 'variant_index': 1, 'orgs': {'東京': 1}, 'expected_tier': 2},
    {'name': 'variant1_ignores_other_variant_pair', 'variant_index': 1, 'orgs': {'伊斯坦堡': 1}, 'expected_tier': 1},
]


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

    # --- Part 1: direct-HTTP proof that tier gating only checks THIS card's own printed variant ---
    for case in VARIANT_TIER_CASES:
        setup = post_json('/test/setup-support-card-play', {
            'support_name': '英美奧援', 'variant_index': case['variant_index'], 'orgs': case['orgs'],
        })
        record(
            case['name'],
            setup.get('support_tier') == case['expected_tier'],
            {'variant_index': case['variant_index'], 'orgs': case['orgs'],
             'expected_tier': case['expected_tier'], 'actual_tier': setup.get('support_tier')},
        )

    # --- Part 2: card face in the browser shows only the ONE variant this specific card
    # instance is printed with, not both variants merged together ---
    setup_v1 = post_json('/test/setup-support-card-play', {
        'support_name': '英美奧援', 'variant_index': 1, 'orgs': {'東京': 1},
    })
    page = browser.new_context(viewport={'width': 1280, 'height': 900}).new_page()
    page.goto(f"{BASE_URL}/?game_id={setup_v1['game_id']}&player_id={setup_v1['player_id']}", wait_until='networkidle')
    page.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page.wait_for_timeout(900)
    page.evaluate("() => { const b = document.getElementById('closeFactionActionModal'); if (b) b.click(); }")
    page.wait_for_timeout(300)
    face_text = page.inner_text('#hand .hand-card .card-effect-block')
    record(
        'card_face_shows_only_this_cards_own_printed_variant_regions',
        ('東洋' in face_text and '臺灣' in face_text) and ('歐洲' not in face_text and '天方' not in face_text),
        {'face_text': face_text},
    )
    page.screenshot(path=str(SCREENSHOT))

    # --- Part 3: 棄置 button discards the support card with zero resource gain (reuses the
    # existing play_card(mode='resource') no-op path for support cards) ---
    before_hand = page.evaluate(
        "(id) => window.lastGameState?.players?.find(p => p.id === id)?.hand || []", setup_v1['player_id']
    )
    before_resources = page.evaluate(
        "(id) => window.lastGameState?.players?.find(p => p.id === id)?.resources || {}", setup_v1['player_id']
    )
    page.click("#hand .hand-card [data-card-mode='resource']")
    page.wait_for_timeout(500)
    after_hand = page.evaluate(
        "(id) => window.lastGameState?.players?.find(p => p.id === id)?.hand || []", setup_v1['player_id']
    )
    after_resources = page.evaluate(
        "(id) => window.lastGameState?.players?.find(p => p.id === id)?.resources || {}", setup_v1['player_id']
    )
    after_discard = page.evaluate(
        "(id) => window.lastGameState?.players?.find(p => p.id === id)?.discard_pile || []", setup_v1['player_id']
    )
    record(
        'discard_button_removes_card_from_hand_with_no_resource_gain',
        before_hand == ['英美奧援'] and after_hand == [] and after_discard == ['英美奧援']
        and before_resources == after_resources,
        {'before_hand': before_hand, 'after_hand': after_hand, 'after_discard': after_discard,
         'before_resources': before_resources, 'after_resources': after_resources},
    )
    page.close()

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
        '# 奧援卡「單一變體地區判定」與「棄置」驗證',
        '',
        '可重跑指令：`python3 scripts/validate/validate_support_card_variant_and_discard.py`',
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
