import json
import os
import sys
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except ModuleNotFoundError:
    system_python = '/usr/bin/python3'
    if sys.executable != system_python and Path(system_python).exists():
        os.execv(system_python, [system_python, __file__, *sys.argv[1:]])
    raise

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = ROOT / 'MULTIPLAYER_LOBBY_FLOW_VALIDATION.json'
OUT_MD = ROOT / 'MULTIPLAYER_LOBBY_FLOW_VALIDATION.md'
HOST_SCREENSHOT = ROOT / 'multiplayer_lobby_flow_host.png'
ALLY_SCREENSHOT = ROOT / 'multiplayer_lobby_flow_ally.png'


def request_json(path, payload=None):
    if payload is None:
        return json.loads(urllib.request.urlopen(BASE_URL + path, timeout=20).read().decode('utf-8'))
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def record(results, name, ok, detail=None):
    results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})


def safe_inner_text(page, selector):
    try:
        return page.locator(selector).inner_text(timeout=3000)
    except Exception as exc:
        return f'<missing {selector}: {exc}>'


def check_flow(browser):
    results = []
    host_ctx = browser.new_context(viewport={'width': 1280, 'height': 720})
    ally_ctx = browser.new_context(viewport={'width': 1280, 'height': 720})
    host = host_ctx.new_page()
    ally = ally_ctx.new_page()

    host.goto(BASE_URL + '/', wait_until='networkidle')
    ally.goto(BASE_URL + '/', wait_until='networkidle')

    # 1. Host creates room.
    host.fill('#playerName', 'host')
    host.click('#createRoomBtn')
    host.wait_for_function("() => document.querySelector('#roomId')?.value?.length > 10", timeout=10000)
    game_id = host.locator('#roomId').input_value()
    host_player_id = host.evaluate('playerId')
    record(results, 'host_created_room', bool(game_id and host_player_id), {'game_id': game_id, 'host_player_id': host_player_id})

    # 2. Ally joins from a separate browser context.
    ally.fill('#roomId', game_id)
    ally.fill('#playerName', 'ally')
    ally.click('#joinRoomBtn')
    ally.wait_for_function("() => typeof playerId !== 'undefined' && playerId && document.querySelector('#factionPicker')?.style.display !== 'none'", timeout=10000)
    ally_player_id = ally.evaluate('playerId')
    host.wait_for_function("() => document.querySelector('#lobbyRoster')?.innerText.includes('ally')", timeout=8000)
    ally.wait_for_function("() => document.querySelector('#lobbyRoster')?.innerText.includes('host')", timeout=8000)
    record(results, 'two_browser_contexts_join_same_lobby', bool(ally_player_id) and 'ally' in safe_inner_text(host, '#lobbyRoster') and 'host' in safe_inner_text(ally, '#lobbyRoster'), {
        'ally_player_id': ally_player_id,
        'host_roster': safe_inner_text(host, '#lobbyRoster'),
        'ally_roster': safe_inner_text(ally, '#lobbyRoster'),
    })

    # 3. Choose factions for both players through the same public endpoints the UI uses.
    choose_host = request_json('/choose-faction', {'game_id': game_id, 'player_id': host_player_id, 'faction_id': 'red_army'})
    choose_ally = request_json('/choose-faction', {
        'game_id': game_id,
        'player_id': ally_player_id,
        'faction_id': 'taiwan_green',
        'base_name': '臺北',
    })
    host.wait_for_function("() => document.querySelector('#lobbyRoster')?.innerText.includes('紅軍')", timeout=8000)
    ally.wait_for_function("() => document.querySelector('#lobbyRoster')?.innerText.includes('臺灣（綠線）')", timeout=8000)
    record(results, 'both_players_show_chosen_factions', choose_host.get('success') and choose_ally.get('success'), {
        'choose_host': choose_host,
        'choose_ally': choose_ally,
        'host_roster': safe_inner_text(host, '#lobbyRoster'),
        'ally_roster': safe_inner_text(ally, '#lobbyRoster'),
    })

    # 4. Both players mark ready.
    host.click('#toggleReadyBtn')
    ally.click('#toggleReadyBtn')
    host.wait_for_function("() => (document.querySelector('#lobbyRoster')?.innerText.match(/已準備/g) || []).length >= 2", timeout=8000)
    ally.wait_for_function("() => (document.querySelector('#lobbyRoster')?.innerText.match(/已準備/g) || []).length >= 2", timeout=8000)
    record(results, 'both_players_ready_plain_text', True, {
        'host_roster': safe_inner_text(host, '#lobbyRoster'),
        'ally_roster': safe_inner_text(ally, '#lobbyRoster'),
    })

    # 5. Non-host cannot start.
    ally_start = ally.evaluate("""() => {
      const btn = document.querySelector('#startGameBtn');
      return {disabled: !!btn?.disabled, title: btn?.title || '', text: btn?.textContent || ''};
    }""")
    record(results, 'non_host_start_button_locked', ally_start['disabled'] and '房主' in ally_start['title'], ally_start)

    # 6. Host starts.
    host_start_before = host.evaluate("""() => {
      const btn = document.querySelector('#startGameBtn');
      return {disabled: !!btn?.disabled, title: btn?.title || '', text: btn?.textContent || ''};
    }""")
    host.click('#startGameBtn')
    host.wait_for_selector('#gameShell', state='visible', timeout=10000)
    host_game_visible = host.locator('#gameShell').is_visible()
    record(results, 'host_can_start_and_enters_game_shell', host_game_visible and not host_start_before['disabled'], {
        'host_start_before': host_start_before,
        'host_body_excerpt': safe_inner_text(host, 'body')[:800],
    })

    # 7. Ally should also enter the game shell after host starts via lobby auto-sync.
    ally_entered = False
    ally_detail = {}
    try:
        ally.wait_for_selector('#gameShell', state='visible', timeout=10000)
        ally_entered = ally.locator('#gameShell').is_visible()
    except PlaywrightTimeoutError:
        ally_detail['timeout'] = 'ally did not enter game shell within 10s after host start'
    ally_detail.update({
        'ally_body_excerpt': safe_inner_text(ally, 'body')[:1000],
        'ally_lobby_display': ally.evaluate("() => getComputedStyle(document.querySelector('#lobby')).display"),
        'ally_game_shell_display': ally.evaluate("() => getComputedStyle(document.querySelector('#gameShell')).display"),
    })
    record(results, 'ally_auto_enters_game_shell_after_host_start', ally_entered, ally_detail)

    # 8. Both game shells show correct players/factions in the battle log overview.
    try:
        host.get_by_text('戰況紀錄').click()
        ally.get_by_text('戰況紀錄').click()
        host.wait_for_selector('#playerStatusOverview .player-status-card', timeout=8000)
        ally.wait_for_selector('#playerStatusOverview .player-status-card', timeout=8000)
    except Exception as exc:
        record(results, 'battle_log_player_cards_available_after_start', False, {'error': str(exc)})
    else:
        record(results, 'battle_log_player_cards_available_after_start', True, {
            'host_cards': safe_inner_text(host, '#playerStatusOverview'),
            'ally_cards': safe_inner_text(ally, '#playerStatusOverview'),
        })

    host_text = safe_inner_text(host, 'body')
    ally_text = safe_inner_text(ally, 'body')
    required_tokens = ['host', 'ally', '紅軍', '臺灣', '臺北']
    record(results, 'game_views_include_both_players_and_factions', all(token in host_text for token in required_tokens) and all(token in ally_text for token in required_tokens), {
        'host_excerpt': host_text[:1200],
        'ally_excerpt': ally_text[:1200],
    })

    host.screenshot(path=str(HOST_SCREENSHOT), full_page=True)
    ally.screenshot(path=str(ALLY_SCREENSHOT), full_page=True)
    host_ctx.close()
    ally_ctx.close()

    return {
        'game_id': game_id,
        'host_player_id': host_player_id,
        'ally_player_id': ally_player_id,
        'summary': {
            'total': len(results),
            'passed': sum(1 for r in results if r['ok']),
            'failed': sum(1 for r in results if not r['ok']),
        },
        'results': results,
        'screenshots': {
            'host': str(HOST_SCREENSHOT),
            'ally': str(ALLY_SCREENSHOT),
        },
    }


def write_reports(payload):
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# MULTIPLAYER LOBBY FLOW VALIDATION',
        '',
        '日期：2026-05-09',
        '',
        f"summary: {payload['summary']}",
        '',
        f"host screenshot: {payload['screenshots']['host']}",
        f"ally screenshot: {payload['screenshots']['ally']}",
        '',
    ]
    for r in payload['results']:
        lines.append(f"## {r['name']}")
        lines.append(f"- result: {'PASS' if r['ok'] else 'FAIL'}")
        lines.append(f"- detail: {json.dumps(r['detail'], ensure_ascii=False)}")
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        payload = check_flow(browser)
        browser.close()
    write_reports(payload)
    print(json.dumps(payload, ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
