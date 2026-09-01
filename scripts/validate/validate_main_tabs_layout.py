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
RECORD_DIR = ROOT / 'docs' / 'records' / 'layout-ui'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'MAIN_TABS_LAYOUT_VALIDATION.json'
OUT_MD = RECORD_DIR / 'MAIN_TABS_LAYOUT_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'main_tabs_layout_validation.png'


def post(path, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def check_page(page):
    setup = post('/test/setup-hand-preview', {
        'hand_names': ['宣傳家', '資助者', '印度奧援', '東洋奧援', '武裝者']
    })
    game_id = setup['game_id']
    player_id = setup['player_id']

    page.goto(BASE_URL + '/', wait_until='networkidle')
    page.evaluate(
        "([gameIdValue, playerIdValue]) => { gameId = gameIdValue; playerId = playerIdValue; connect(); }",
        [game_id, player_id],
    )
    page.wait_for_timeout(1800)

    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    # Command tab should show card zones.
    page.get_by_text('指揮中心', exact=True).click()
    page.wait_for_timeout(300)
    command_visible = page.locator('#commandView').evaluate("el => getComputedStyle(el).display !== 'none'")
    hand_count = page.locator('#hand .card').count()
    static_count = page.locator('#purchaseStatic .card').count()
    random_count = page.locator('#purchaseRandom .card').count()
    record('command_tab_visible', command_visible, {'hand_count': hand_count, 'static_count': static_count, 'random_count': random_count})
    record('command_tab_card_zones_populated', hand_count >= 5 and static_count >= 6 and random_count >= 5, {'hand_count': hand_count, 'static_count': static_count, 'random_count': random_count})

    # Map tab should expose iframe.
    page.get_by_text('戰略地圖', exact=True).click()
    page.wait_for_timeout(800)
    map_visible = page.locator('#mapView').evaluate("el => getComputedStyle(el).display !== 'none'")
    iframe_count = page.locator('iframe[title="Strategic Map"]').count()
    record('map_tab_visible', map_visible and iframe_count == 1, {'iframe_count': iframe_count})

    # Log tab should show player status cards.
    page.get_by_text('戰況紀錄', exact=True).click()
    page.wait_for_timeout(600)
    page.wait_for_selector('#playerStatusOverview .player-status-card', timeout=10000)
    log_visible = page.locator('#logView').evaluate("el => getComputedStyle(el).display !== 'none'")
    card_count = page.locator('#playerStatusOverview .player-status-card').count()
    state = page.evaluate('window.lastGameState || window.state')
    players = state.get('players', []) if state else []
    card_texts = page.locator('#playerStatusOverview .player-status-card').all_inner_texts()
    active_tab = page.locator('.game-tab.active').inner_text() if page.locator('.game-tab.active').count() else ''
    required_labels = ['陣營：', '根據地：', '組織', '資金', '宣傳', '手牌', '移動']
    cards_have_required_labels = all(all(label in text for label in required_labels) for text in card_texts)
    current_badge_present = any('當前玩家' in text for text in card_texts)
    player_names_present = all(any(p.get('name') in text for text in card_texts) for p in players)
    record('battle_log_tab_visible', log_visible and active_tab == '戰況紀錄', {'active_tab': active_tab})
    record('player_status_card_count_matches_players', card_count == len(players) and card_count >= 2, {'card_count': card_count, 'players': [p.get('name') for p in players]})
    record('player_status_cards_have_required_fields', cards_have_required_labels and current_badge_present and player_names_present, {'card_texts': card_texts})

    overflow = page.evaluate("""() => ({
      bodyScrollWidth: document.body.scrollWidth,
      bodyClientWidth: document.body.clientWidth,
      bodyScrollHeight: document.body.scrollHeight,
      bodyClientHeight: document.body.clientHeight,
      hasOverflowX: document.body.scrollWidth > document.body.clientWidth + 1,
      hasOverflowY: document.body.scrollHeight > document.body.clientHeight + 1,
      viewport: {w: innerWidth, h: innerHeight},
    })""")
    record('viewport_1280x720_has_no_body_overflow', not overflow['hasOverflowX'] and not overflow['hasOverflowY'], overflow)

    page.screenshot(path=str(SCREENSHOT), full_page=True)

    return {
        'setup': {'game_id': game_id, 'player_id': player_id},
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
        ctx = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = ctx.new_page()
        payload = check_page(page)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# MAIN TABS LAYOUT VALIDATION', '', '日期：2026-05-09', '', f"summary: {payload['summary']}", '', f"screenshot: {payload['screenshot']}", '']
    for r in payload['results']:
        lines.append(f"## {r['name']}")
        lines.append(f"- result: {'PASS' if r['ok'] else 'FAIL'}")
        lines.append(f"- detail: {json.dumps(r['detail'], ensure_ascii=False)}")
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
