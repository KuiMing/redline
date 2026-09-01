import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
checks = []


def record(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})


def api(page, path, payload=None):
    return page.evaluate("""async ({path, payload}) => {
      const response = await fetch(path, payload === null ? {} : {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
      });
      return response.json();
    }""", {'path': path, 'payload': payload})


def main():
    console_errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)
        page.goto(BASE_URL, wait_until='networkidle')

        created = api(page, '/create', {'name': 'Host', 'device_id': 'proof-host'})
        game_id = created['game_id']
        player_ids = [created['host_id']]
        for index in range(1, 3):
            joined = api(page, '/join', {'game_id': game_id, 'name': f'Player {index + 1}', 'device_id': f'proof-{index}'})
            player_ids.append(joined['player_id'])
        for pid, faction, base in zip(player_ids, ['taiwan_green', 'hong_kong', 'manchuria'], ['臺北', '香港城', '東京']):
            # Base uniqueness is irrelevant until start; choose-faction accepts canonical faction bases.
            result = api(page, '/choose-faction', {'game_id': game_id, 'player_id': pid, 'faction_id': faction, 'base_name': base})
            if result.get('error'):
                raise RuntimeError(result)

        joined_last = api(page, '/join', {'game_id': game_id, 'name': 'Final Player', 'device_id': 'proof-final'})
        last_id = joined_last['player_id']
        page.evaluate("""({gameId, playerId, token}) => {
          localStorage.setItem('redline.sessions.v1', JSON.stringify({[gameId]: {game_id:gameId, player_id:playerId, resume_token:token, name:'Final Player', saved_at:Date.now()}}));
        }""", {'gameId': game_id, 'playerId': last_id, 'token': joined_last['resume_token']})
        page.reload(wait_until='networkidle')
        page.locator('#factionPicker').wait_for(state='visible', timeout=15000)
        page.wait_for_timeout(300)
        picker = page.evaluate("""() => ({
          info: document.getElementById('factionPickerInfo').textContent,
          buttons: [...document.querySelectorAll('#factionList button')].map(b => ({text:b.textContent, disabled:b.disabled, title:b.title}))
        })""")
        red = next(button for button in picker['buttons'] if button['text'] == '紅軍')
        non_red = [button for button in picker['buttons'] if button['text'] != '紅軍']
        record('last_seat_ui_only_enables_red_army', not red['disabled'] and all(button['disabled'] for button in non_red), picker)
        record('last_seat_ui_explains_forced_red_army', '最後一個席位' in picker['info'] and '只能選擇紅軍' in picker['info'], picker['info'])

        rejected = api(page, '/choose-faction', {'game_id': game_id, 'player_id': last_id, 'faction_id': 'mongol', 'base_name': '烏蘭巴托'})
        record('server_rejects_non_red_for_last_seat', rejected.get('error') == '房間尚無紅軍；最後一個席位只能選擇紅軍', rejected)
        accepted = api(page, '/choose-faction', {'game_id': game_id, 'player_id': last_id, 'faction_id': 'red_army', 'base_name': '北京'})
        record('last_seat_can_choose_red_army', accepted.get('success') is True, accepted)

        created2 = api(page, '/create', {'name': 'Host2', 'device_id': 'proof-host-2'})
        game2 = created2['game_id']; host2 = created2['host_id']
        guest2 = api(page, '/join', {'game_id': game2, 'name': 'Guest2', 'device_id': 'proof-guest-2'})['player_id']
        api(page, '/choose-faction', {'game_id': game2, 'player_id': host2, 'faction_id': 'taiwan_green', 'base_name': '臺北'})
        api(page, '/choose-faction', {'game_id': game2, 'player_id': guest2, 'faction_id': 'hong_kong', 'base_name': '香港城'})
        api(page, '/ready', {'game_id': game2, 'player_id': host2, 'ready': True})
        api(page, '/ready', {'game_id': game2, 'player_id': guest2, 'ready': True})
        state2 = api(page, f'/lobby/{game2}')
        page.evaluate("""({gameId, playerId, token}) => {
          localStorage.setItem('redline.sessions.v1', JSON.stringify({[gameId]: {game_id:gameId, player_id:playerId, resume_token:token, name:'Host2', saved_at:Date.now()}}));
        }""", {'gameId': game2, 'playerId': host2, 'token': created2['resume_token']})
        page.reload(wait_until='networkidle')
        page.wait_for_function("() => document.getElementById('startGameBtn')?.title.includes('紅軍')", timeout=15000)
        control = page.evaluate("() => ({disabled:startGameBtn.disabled, title:startGameBtn.title})")
        record('host_start_button_disabled_without_red_army', control['disabled'] and '紅軍' in control['title'], control)
        start_result = api(page, '/start', {'game_id': game2, 'player_id': host2})
        record('server_rejects_start_without_red_army', start_result.get('error') == '必須有且只能有一名玩家選擇紅軍，才能啟動行動', start_result)
        record('browser_console_has_no_errors', not console_errors, console_errors)
        browser.close()

    result = {'status': 'passed' if all(item['ok'] for item in checks) else 'failed', 'checks_passed': sum(item['ok'] for item in checks), 'checks_total': len(checks), 'checks': checks}
    print(json.dumps(result, ensure_ascii=False))
    if result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
