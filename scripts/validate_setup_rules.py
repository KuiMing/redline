import json
import os
import sys
from pathlib import Path
import urllib.request
import websocket

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    system_python = '/usr/bin/python3'
    if sys.executable != system_python and Path(system_python).exists():
        os.execv(system_python, [system_python, __file__, *sys.argv[1:]])
    raise

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'setup-ui'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'SETUP_RULES_VALIDATION.json'
OUT_MD = RECORD_DIR / 'SETUP_RULES_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'setup_rules_validation.png'


def request_json(path, payload=None):
    if payload is None:
        return json.loads(urllib.request.urlopen(BASE_URL + path, timeout=20).read().decode('utf-8'))
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def record(results, name, ok, detail=None):
    results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})


def player_by_name(state, name):
    return next((p for p in state.get('players', []) if p.get('name') == name), None)


def websocket_initial_state(game_id, player_id):
    ws = websocket.create_connection(f'ws://127.0.0.1:8000/ws/{game_id}/{player_id}', timeout=10)
    try:
        return json.loads(ws.recv())
    finally:
        ws.close()


def check_setup(browser):
    results = []
    create = request_json('/create', {'name': 'host', 'market_mode': 'sample_53'})
    game_id = create.get('game_id')
    host_id = create.get('host_id')

    join = request_json('/join', {'game_id': game_id, 'name': 'ally'})
    ally_id = join.get('player_id')
    request_json('/choose-faction', {'game_id': game_id, 'player_id': host_id, 'faction_id': 'red_army'})
    request_json('/choose-faction', {'game_id': game_id, 'player_id': ally_id, 'faction_id': 'taiwan_green', 'base_name': '臺北'})
    request_json('/ready', {'game_id': game_id, 'player_id': host_id, 'ready': True})
    request_json('/ready', {'game_id': game_id, 'player_id': ally_id, 'ready': True})

    start = request_json('/start', {'game_id': game_id, 'player_id': host_id})
    record(results, 'start_endpoint_accepts_ready_setup', start.get('success') is True, start)
    state = websocket_initial_state(game_id, host_id)

    host = player_by_name(state, 'host')
    ally = player_by_name(state, 'ally')

    record(results, 'setup_enters_main_event_phase',
           state.get('game_phase') == 'main' and state.get('turn_phase') == 'event' and state.get('turn') == 1 and state.get('winner') is None,
           {'game_phase': state.get('game_phase'), 'turn_phase': state.get('turn_phase'), 'turn': state.get('turn'), 'winner': state.get('winner')})

    record(results, 'starting_player_is_first_non_red',
           state.get('current_player') == 'ally',
           {'current_player': state.get('current_player'), 'expected': 'ally'})

    expected_players = {
        'host': {'faction': 'red_army', 'base': '北京'},
        'ally': {'faction': 'taiwan_green', 'base': '臺北'},
    }
    for name, expected in expected_players.items():
        p = player_by_name(state, name)
        record(results, f'{name}_faction_and_base_initialized',
               bool(p) and p.get('faction') == expected['faction'] and p.get('base') == expected['base'] and p.get('orgs', {}).get(expected['base']) == 1,
               {'player': p, 'expected': expected})

    for p in [host, ally]:
        name = p.get('name') if p else '<missing>'
        record(results, f'{name}_starter_hand_resources_and_moves',
               bool(p)
               and len(p.get('hand', [])) == 5
               and p.get('deck_count') == 5
               and p.get('discard_count') == 0
               and p.get('resources') == {'money': 0, 'propaganda': 0}
               and p.get('moves_left') == 0,
               {'player': p})

    purchase_area = state.get('purchase_area') or []
    static_supply = state.get('static_purchase_supply') or {}
    expected_static = ['宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥']
    record(results, 'purchase_area_setup_matches_rules',
           len(purchase_area) == 11 and all(name in purchase_area for name in expected_static) and all(static_supply.get(name) == 1 for name in expected_static),
           {'purchase_area_count': len(purchase_area), 'purchase_area': purchase_area, 'static_supply': static_supply})

    ctx = browser.new_context(viewport={'width': 1280, 'height': 720})
    page = ctx.new_page()
    page.goto(BASE_URL + '/', wait_until='networkidle')
    page.evaluate(f"""
      gameId = {json.dumps(game_id)};
      playerId = {json.dumps(host_id)};
      connect();
    """)
    page.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page.get_by_text('戰況紀錄').click()
    page.wait_for_selector('#playerStatusOverview .player-status-card', timeout=8000)
    page.screenshot(path=str(SCREENSHOT), full_page=True)
    ctx.close()

    return {
        'game_id': game_id,
        'host_player_id': host_id,
        'ally_player_id': ally_id,
        'summary': {
            'total': len(results),
            'passed': sum(1 for r in results if r['ok']),
            'failed': sum(1 for r in results if not r['ok']),
        },
        'results': results,
        'screenshot': str(SCREENSHOT),
    }


def write_reports(payload):
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# SETUP RULES VALIDATION',
        '',
        '日期：2026-05-09',
        '',
        f"summary: {payload['summary']}",
        '',
        f"screenshot: {payload['screenshot']}",
        '',
    ]
    for result in payload['results']:
        lines.append(f"## {result['name']}")
        lines.append(f"- result: {'PASS' if result['ok'] else 'FAIL'}")
        lines.append(f"- detail: {json.dumps(result['detail'], ensure_ascii=False)}")
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        payload = check_setup(browser)
        browser.close()
    write_reports(payload)
    print(json.dumps(payload, ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
