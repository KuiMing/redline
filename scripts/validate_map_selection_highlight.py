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
OUT_JSON = RECORD_DIR / 'MAP_SELECTION_HIGHLIGHT_VALIDATION.json'
OUT_MD = RECORD_DIR / 'MAP_SELECTION_HIGHLIGHT_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'map_selection_highlight_validation.png'

COORDS = {
    '臺北': [25.033, 121.5654],
    '基隆': [25.1276, 121.7392],
    '高雄': [22.6273, 120.3014],
    '臺中': [24.1477, 120.6736],
}


def post_json(path, payload=None):
    data = json.dumps(payload or {}).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def marker_at(page, lat, lon):
    return page.evaluate(
        """([lat, lon]) => {
          const m = document.getElementById('strategicMapFrame').contentWindow.__redlinePlayableMap;
          let found = null;
          m.eachLayer(l => {
            if (l.getLatLng && l.options && l.options.fillColor !== undefined) {
              const ll = l.getLatLng();
              if (Math.abs(ll.lat - lat) < 0.001 && Math.abs(ll.lng - lon) < 0.001) {
                found = { fill: l.options.fillColor, fillOpacity: l.options.fillOpacity, color: l.options.color };
              }
            }
          });
          return found;
        }""",
        [lat, lon],
    )


def select_town(page, name):
    page.evaluate("(name) => { document.getElementById('strategicMapFrame').contentWindow.__selectTownForTest(name); }", name)
    page.wait_for_timeout(400)


def check_flow(page):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    setup = post_json('/test/setup-move-confirmation-proof', {
        'mover_faction': 'taiwan_green',
        'mover_base': '新竹',
        'mover_town': '臺北',
        'moves_left': 5,
    })
    page.goto(BASE_URL + setup['url'], wait_until='networkidle')
    page.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page.click('button.game-tab[data-view="map"]')
    page.wait_for_timeout(2000)
    page.evaluate("() => { document.getElementById('strategicMapFrame').contentWindow.__redlinePlayableMap.setView([24.6, 121.2], 8, {animate:false}); }")
    page.wait_for_timeout(500)

    base_taipei = marker_at(page, *COORDS['臺北'])
    record(
        'green_line_org_town_is_green_before_selection',
        base_taipei and base_taipei['fill'] == '#22c55e' and base_taipei['fillOpacity'] >= 0.9,
        {'臺北': base_taipei},
    )

    select_town(page, '臺北')
    sel_taipei = marker_at(page, *COORDS['臺北'])
    record(
        'selecting_org_town_keeps_solid_faction_fill',
        sel_taipei and sel_taipei['fill'] == '#22c55e' and sel_taipei['fillOpacity'] >= 0.9 and sel_taipei['color'] == '#ffffff',
        {'臺北': sel_taipei},
    )

    target = marker_at(page, *COORDS['基隆'])
    record(
        'reachable_move_target_is_solid_white_highlight',
        target and target['fill'] == '#f8fafc' and target['fillOpacity'] == 1 and target['color'] in ('#67e8f9', '#ffd166'),
        {'基隆': target},
    )

    unrelated = marker_at(page, *COORDS['臺中'])
    record(
        'unrelated_town_keeps_base_style_not_dimmed',
        unrelated and unrelated['fill'] == '#6b7280' and abs(unrelated['fillOpacity'] - 0.32) < 0.01,
        {'臺中': unrelated},
    )

    select_town(page, '高雄')
    empty_sel = marker_at(page, *COORDS['高雄'])
    record(
        'selecting_empty_town_is_solid_white',
        empty_sel and empty_sel['fill'] == '#f8fafc' and empty_sel['fillOpacity'] == 1,
        {'高雄': empty_sel},
    )
    taipei_after = marker_at(page, *COORDS['臺北'])
    record(
        'other_org_town_returns_to_solid_green_after_reselect',
        taipei_after and taipei_after['fill'] == '#22c55e' and taipei_after['fillOpacity'] >= 0.9,
        {'臺北': taipei_after},
    )

    select_town(page, '臺北')
    page.evaluate("() => { document.getElementById('strategicMapFrame').contentWindow.__redlinePlayableMap.setView([24.6, 121.2], 8, {animate:false}); }")
    page.wait_for_timeout(400)
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
        payload = check_flow(page)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# Map selection highlight validation',
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
