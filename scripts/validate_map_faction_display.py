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
RECORD_DIR = ROOT / 'docs' / 'records' / 'map-ui'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'MAP_FACTION_DISPLAY_VALIDATION.json'
OUT_MD = RECORD_DIR / 'MAP_FACTION_DISPLAY_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'map_faction_display_validation.png'


def request_json(path, payload=None):
    if payload is None:
        return json.loads(urllib.request.urlopen(BASE_URL + path, timeout=20).read().decode('utf-8'))
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def dismiss_event_reveal(page):
    reveal = page.locator('#eventRevealModal')
    if reveal.is_visible():
        reveal.click(position={'x': 8, 'y': 8})
        reveal.wait_for(state='hidden')


# 2026-07-18 起陣營標籤有 zoom 門檻（FACTION_LABEL_MIN_ZOOM=10），本腳本驗證完整標籤時視角需 zoom 10。
def check_page(host, ally):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    host.goto(BASE_URL + '/', wait_until='networkidle')
    ally.goto(BASE_URL + '/', wait_until='networkidle')

    host.fill('#playerName', 'host')
    host.click('#createRoomBtn')
    host.wait_for_function("() => document.querySelector('#roomId')?.value?.length > 10", timeout=10000)
    game_id = host.locator('#roomId').input_value()
    host_player_id = host.evaluate('playerId')

    ally.fill('#roomId', game_id)
    ally.fill('#playerName', 'ally')
    ally.click('#joinRoomBtn')
    ally.wait_for_function("() => typeof playerId !== 'undefined' && playerId", timeout=10000)
    ally_player_id = ally.evaluate('playerId')

    choose_host = request_json('/choose-faction', {'game_id': game_id, 'player_id': host_player_id, 'faction_id': 'red_army'})
    choose_ally = request_json('/choose-faction', {'game_id': game_id, 'player_id': ally_player_id, 'faction_id': 'taiwan_green', 'base_name': '臺北'})
    record('faction_selection_succeeded', choose_host.get('success') and choose_ally.get('success'), {'choose_host': choose_host, 'choose_ally': choose_ally})

    host.click('#toggleReadyBtn')
    ally.click('#toggleReadyBtn')
    host.wait_for_timeout(400)
    host.click('#startGameBtn')
    host.wait_for_selector('#gameShell', state='visible', timeout=10000)
    ally.wait_for_selector('#gameShell', state='visible', timeout=10000)
    dismiss_event_reveal(host)
    dismiss_event_reveal(ally)
    host.click('button.game-tab[data-view="map"]')
    host.wait_for_timeout(2500)  # let the map iframe's own WS connect and /factions resolve

    host.evaluate("() => { const f = document.getElementById('strategicMapFrame'); f.contentWindow.__redlinePlayableMap.setView([25.033, 121.5654], 10, {animate:false}); }")
    host.wait_for_timeout(800)

    near_taipei = host.evaluate(
        """() => {
          const f = document.getElementById('strategicMapFrame');
          const win = f.contentWindow;
          const m = win.__redlinePlayableMap;
          const out = [];
          m.eachLayer(layer => {
            if (layer.getTooltip && layer.getTooltip()) {
              const ll = layer.getLatLng ? layer.getLatLng() : null;
              out.push({
                latlng: ll ? [ll.lat, ll.lng] : null,
                content: layer.getTooltip().getContent(),
                fillColor: layer.options ? layer.options.fillColor : null,
              });
            }
          });
          return out.filter(o => o.latlng && Math.abs(o.latlng[0] - 25.033) < 0.3 && Math.abs(o.latlng[1] - 121.5654) < 0.3);
        }"""
    )
    taipei = next((o for o in near_taipei if abs(o['latlng'][0] - 25.033) < 0.001), None)
    expected_taipei_label = '臺北（臺灣（綠線））'
    record(
        'taipei_label_shows_owner_faction_without_redundant_count',
        bool(taipei) and taipei['content'] == expected_taipei_label,
        {'taipei': taipei, 'near_taipei': near_taipei, 'expected': expected_taipei_label},
    )
    record(
        'taipei_marker_uses_green_line_color_not_gray_fallback',
        bool(taipei) and taipei['fillColor'] == '#4ade80',
        {'fillColor': taipei['fillColor'] if taipei else None},
    )
    empty_neighbor = next((o for o in near_taipei if o['content'] == '新北'), None)
    record(
        'unowned_neighbor_town_keeps_plain_label_and_gray_fill',
        bool(empty_neighbor) and empty_neighbor['fillColor'] == '#6b7280',
        {'empty_neighbor': empty_neighbor},
    )

    host.evaluate("() => { const f = document.getElementById('strategicMapFrame'); f.contentWindow.__redlinePlayableMap.setView([39.9042, 116.4074], 10, {animate:false}); }")
    host.wait_for_timeout(800)
    near_beijing = host.evaluate(
        """() => {
          const f = document.getElementById('strategicMapFrame');
          const win = f.contentWindow;
          const m = win.__redlinePlayableMap;
          const out = [];
          m.eachLayer(layer => {
            if (layer.getTooltip && layer.getTooltip()) {
              const ll = layer.getLatLng ? layer.getLatLng() : null;
              out.push({
                latlng: ll ? [ll.lat, ll.lng] : null,
                content: layer.getTooltip().getContent(),
                fillColor: layer.options ? layer.options.fillColor : null,
              });
            }
          });
          return out.filter(o => o.latlng && Math.abs(o.latlng[0] - 39.9042) < 0.3 && Math.abs(o.latlng[1] - 116.4074) < 0.3);
        }"""
    )
    beijing = next((o for o in near_beijing if abs(o['latlng'][0] - 39.9042) < 0.001), None)
    record(
        'beijing_label_shows_red_army_owner_without_redundant_count',
        bool(beijing) and beijing['content'] == '北京（紅軍）',
        {'beijing': beijing},
    )
    record(
        'beijing_marker_uses_red_army_camp_color_not_gray_fallback',
        bool(beijing) and beijing['fillColor'] == '#f04f56',
        {'fillColor': beijing['fillColor'] if beijing else None},
    )

    host.screenshot(path=str(SCREENSHOT))
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
        host = browser.new_context(viewport={'width': 1280, 'height': 800}).new_page()
        ally = browser.new_context(viewport={'width': 1280, 'height': 800}).new_page()
        payload = check_page(host, ally)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# Map town/base faction display validation',
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
