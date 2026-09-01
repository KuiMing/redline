#!/usr/bin/env python3
import json
import os

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8022').rstrip('/')


def main():
    checks = []
    errors = []

    def record(name, ok, detail=None):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
        page.goto(BASE_URL, wait_until='networkidle')
        page.fill('#playerName', '故障復原測試')
        page.click('#createRoomBtn')
        page.wait_for_function("() => localStorage.getItem('redline.sessions.v1')")
        old_session = page.evaluate("() => Object.values(JSON.parse(localStorage.getItem('redline.sessions.v1')))[0]")
        started = page.evaluate("""async ({gameId, hostId, deviceId}) => {
          await fetch('/choose-faction', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({game_id:gameId, player_id:hostId, faction_id:'red_army', base_name:'北京'})});
          await fetch('/ready', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({game_id:gameId, player_id:hostId, ready:true})});
          const guest = await fetch('/join', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({game_id:gameId, name:'逃生對手', device_id:`${deviceId}-guest`})}).then(r => r.json());
          await fetch('/choose-faction', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({game_id:gameId, player_id:guest.player_id, faction_id:'hong_kong', base_name:'香港城'})});
          await fetch('/ready', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({game_id:gameId, player_id:guest.player_id, ready:true})});
          return fetch('/start', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({game_id:gameId, player_id:hostId})}).then(r => r.json());
        }""", {'gameId': old_session['game_id'], 'hostId': old_session['player_id'], 'deviceId': page.evaluate("() => localStorage.getItem('redline.device_id.v1')")})
        if not started.get('success'):
            raise RuntimeError(started)
        page.reload(wait_until='domcontentloaded')
        page.locator('#gameShell').wait_for(state='visible', timeout=15000)
        page.evaluate("() => window.closeEventReveal?.()")
        geometry = page.evaluate("""() => {
          const faction = document.getElementById('myFactionBtn').getBoundingClientRect();
          const fresh = document.getElementById('emergencyNewGameBtn').getBoundingClientRect();
          const eventPanel = document.getElementById('eventCardPanel').getBoundingClientRect();
          return {faction:{left:faction.left,right:faction.right,top:faction.top,bottom:faction.bottom}, fresh:{left:fresh.left,right:fresh.right,top:fresh.top,bottom:fresh.bottom}, eventPanel:{left:eventPanel.left,right:eventPanel.right,top:eventPanel.top,bottom:eventPanel.bottom}};
        }""")
        record('button_is_right_of_my_faction_and_inside_tab_row', geometry['fresh']['left'] > geometry['faction']['right'] and geometry['fresh']['right'] <= 1280 and abs(geometry['fresh']['top'] - geometry['faction']['top']) <= 1 and abs(geometry['fresh']['bottom'] - geometry['faction']['bottom']) <= 1, geometry)
        record('button_does_not_overlap_event_card', geometry['fresh']['top'] >= geometry['eventPanel']['bottom'] or geometry['fresh']['bottom'] <= geometry['eventPanel']['top'] or geometry['fresh']['left'] >= geometry['eventPanel']['right'] or geometry['fresh']['right'] <= geometry['eventPanel']['left'], geometry)

        page.click('button[data-view="map"]')
        frame = page.frame_locator('#strategicMapFrame')
        frame.locator('.leaflet-control-zoom-in').wait_for(state='visible', timeout=15000)
        for _ in range(3):
            frame.locator('.leaflet-control-zoom-in').click()
        for _ in range(2):
            frame.locator('.leaflet-control-zoom-out').click()
        page.wait_for_timeout(300)
        zoom_geometry = page.evaluate("""() => {
          const faction = document.getElementById('myFactionBtn').getBoundingClientRect();
          const fresh = document.getElementById('emergencyNewGameBtn').getBoundingClientRect();
          return {faction:{top:faction.top,bottom:faction.bottom}, fresh:{top:fresh.top,bottom:fresh.bottom}};
        }""")
        record('button_stays_aligned_after_map_zoom', abs(zoom_geometry['fresh']['top'] - zoom_geometry['faction']['top']) <= 1 and abs(zoom_geometry['fresh']['bottom'] - zoom_geometry['faction']['bottom']) <= 1, zoom_geometry)

        page.evaluate("() => { document.getElementById('gameTabs').style.transform = 'translateY(12px)'; }")
        page.wait_for_timeout(300)
        shifted_geometry = page.evaluate("""() => {
          const faction = document.getElementById('myFactionBtn').getBoundingClientRect();
          const fresh = document.getElementById('emergencyNewGameBtn').getBoundingClientRect();
          return {faction:{top:faction.top,bottom:faction.bottom}, fresh:{top:fresh.top,bottom:fresh.bottom}};
        }""")
        record('button_recovers_after_late_tab_row_shift', abs(shifted_geometry['fresh']['top'] - shifted_geometry['faction']['top']) <= 1 and abs(shifted_geometry['fresh']['bottom'] - shifted_geometry['faction']['bottom']) <= 1, shifted_geometry)
        page.evaluate("() => { document.getElementById('gameTabs').style.transform = ''; }")
        page.wait_for_timeout(200)
        geometry = page.evaluate("""() => {
          const faction = document.getElementById('myFactionBtn').getBoundingClientRect();
          const fresh = document.getElementById('emergencyNewGameBtn').getBoundingClientRect();
          const eventPanel = document.getElementById('eventCardPanel').getBoundingClientRect();
          return {faction:{left:faction.left,right:faction.right,top:faction.top,bottom:faction.bottom}, fresh:{left:fresh.left,right:fresh.right,top:fresh.top,bottom:fresh.bottom}, eventPanel:{left:eventPanel.left,right:eventPanel.right,top:eventPanel.top,bottom:eventPanel.bottom}};
        }""")
        fallback = page.evaluate("""() => ({href: document.getElementById('emergencyNewGameBtn').getAttribute('href'), zIndex: getComputedStyle(document.getElementById('emergencyNewGameBtn')).zIndex})""")
        record('button_has_server_navigation_fallback_and_top_layer', fallback['href'] == '/new-game' and int(fallback['zIndex']) > 50, fallback)
        page.evaluate("""() => { const blocker = document.createElement('div'); blocker.id='simulatedBrokenGameOverlay'; blocker.className='modal-overlay'; document.getElementById('stageViewport').appendChild(blocker); }""")
        click_point = {'x': (geometry['fresh']['left'] + geometry['fresh']['right']) / 2, 'y': (geometry['fresh']['top'] + geometry['fresh']['bottom']) / 2}
        hit_target = page.evaluate("({x,y}) => document.elementFromPoint(x,y)?.id", click_point)
        record('button_remains_clickable_above_broken_game_overlay', hit_target == 'emergencyNewGameBtn', {'hit_target': hit_target, 'point': click_point})

        with page.expect_navigation(wait_until='domcontentloaded', timeout=15000):
            page.mouse.click(click_point['x'], click_point['y'])
        page.wait_for_load_state('networkidle')
        lobby = page.evaluate("""() => ({
          lobby: getComputedStyle(document.getElementById('lobby')).display,
          shell: getComputedStyle(document.getElementById('gameShell')).display,
          room: document.getElementById('roomId').value,
          url: location.href,
        })""")
        record('emergency_link_returns_to_clean_lobby', lobby['lobby'] != 'none' and lobby['shell'] == 'none' and lobby['room'] == '', lobby)
        record('old_session_does_not_auto_resume', old_session['game_id'] not in lobby['url'] and 'new_game' not in lobby['url'], lobby)

        page.fill('#playerName', '新遊戲玩家')
        page.click('#createRoomBtn')
        page.wait_for_function("() => document.getElementById('roomId').value")
        new_room = page.input_value('#roomId')
        record('new_room_can_be_created', bool(new_room) and new_room != old_session['game_id'], {'old_room': old_session['game_id'], 'new_room': new_room})
        record('browser_console_has_no_errors', not errors, errors)
        browser.close()

    result = {'status': 'passed' if all(check['ok'] for check in checks) else 'failed', 'checks': checks}
    print(json.dumps({'status': result['status'], 'checks_passed': sum(c['ok'] for c in checks), 'checks_total': len(checks), 'checks': checks}, ensure_ascii=False))
    if result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
