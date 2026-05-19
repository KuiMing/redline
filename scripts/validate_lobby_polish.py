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
RECORD_DIR = ROOT / 'docs' / 'records' / 'lobby'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'LOBBY_POLISH_VALIDATION.json'
OUT_MD = RECORD_DIR / 'LOBBY_POLISH_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'lobby_polish_validation.png'


def request_json(path, payload=None):
    if payload is None:
        return json.loads(urllib.request.urlopen(BASE_URL + path, timeout=20).read().decode('utf-8'))
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def check_page(page):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    page.goto(BASE_URL + '/', wait_until='networkidle')
    page.click('#createRoomBtn')
    page.wait_for_function("() => document.querySelector('#roomId')?.value?.length > 10", timeout=10000)
    game_id = page.locator('#roomId').input_value()

    # Simulate a second browser/player entering the same lobby through the public API.
    joined = request_json('/join', {'game_id': game_id, 'name': 'ally'})
    second_player_id = joined.get('player_id')

    # Re-render lobby state from the host page.
    page.evaluate('renderFactionPicker()')
    page.wait_for_timeout(800)

    embedded = page.evaluate("""() => {
      const card = document.querySelector('.lobby-card');
      const picker = document.querySelector('#factionPicker');
      return !!(card && picker && card.contains(picker));
    }""")
    record('faction_picker_embedded_in_lobby_card', embedded, {})

    picker_metrics = page.evaluate("""() => {
      const picker = document.querySelector('#factionPicker');
      const actions = document.querySelector('.lobby-actions');
      const pr = picker?.getBoundingClientRect();
      const ar = actions?.getBoundingClientRect();
      return {
        display: picker ? getComputedStyle(picker).display : 'missing',
        pickerTop: pr?.top ?? null,
        pickerBottom: pr?.bottom ?? null,
        actionsTop: ar?.top ?? null,
        overlapsActions: !!(pr && ar && pr.top < ar.bottom && pr.bottom > ar.top),
      };
    }""")
    record('faction_picker_does_not_overlap_lobby_actions', picker_metrics['display'] != 'none' and not picker_metrics['overlapsActions'], picker_metrics)

    roster_text = page.locator('#lobbyRoster').inner_text()
    cards = page.locator('#lobbyRoster .lobby-player-card').count()
    record('lobby_roster_syncs_all_joined_players', 'host' in roster_text and 'ally' in roster_text and cards >= 3, {
        'roster_text': roster_text,
        'card_count': cards,
        'second_player_id': second_player_id,
    })

    page.screenshot(path=str(SCREENSHOT), full_page=True)
    return {
        'game_id': game_id,
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
    lines = ['# LOBBY POLISH VALIDATION', '', '日期：2026-05-09', '', f"summary: {payload['summary']}", '', f"screenshot: {payload['screenshot']}", '']
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
