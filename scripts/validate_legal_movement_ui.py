import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
RECORD_DIR = ROOT / 'docs' / 'records' / 'map-ui'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'LEGAL_MOVEMENT_UI_VALIDATION.json'
OUT_MD = RECORD_DIR / 'LEGAL_MOVEMENT_UI_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'legal_movement_ui.png'


def post_json(path, payload):
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    return json.loads(urllib.request.urlopen(request, timeout=20).read().decode('utf-8'))


def click_visible_blank_map(page):
    frame = page.frame_locator('#strategicMapFrame')
    point = frame.locator('body').evaluate(
        """() => {
          const map = window.__redlinePlayableMap;
          const size = map.getSize();
          const townPoints = towns.map(town =>
            map.latLngToContainerPoint([town.lat, town.lon])
          );
          let best = {x: 0, y: 0, distance: -1};
          for (let x = 80; x <= size.x - 80; x += 40) {
            for (let y = 80; y <= size.y - 80; y += 40) {
              const distance = Math.min(...townPoints.map(point => Math.hypot(point.x - x, point.y - y)));
              if (distance > best.distance) best = {x, y, distance};
            }
          }
          return best;
        }"""
    )
    page.frame_locator('#strategicMapFrame').locator('#map').click(
        position={'x': point['x'], 'y': point['y']}
    )
    page.wait_for_timeout(200)
    return point


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json('/test/setup-move-confirmation-proof', {
        'mover_faction': 'taiwan_green',
        'mover_base': '新竹',
        'mover_town': '臺北',
        'moves_left': 5,
    })
    results = []
    console_errors = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    record('official_test_setup_succeeded', setup.get('success') is True, setup)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_context(viewport={'width': 1280, 'height': 800}).new_page()
        page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
        page.goto(BASE_URL + setup['url'], wait_until='networkidle')
        page.wait_for_selector('#gameShell', state='visible', timeout=10000)
        page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
        page.click('button.game-tab[data-view="map"]')
        page.wait_for_timeout(2200)

        initial = page.evaluate(
            """() => {
              const frame = document.getElementById('strategicMapFrame');
              const win = frame.contentWindow;
              const doc = frame.contentDocument;
              win.__selectTownForTest('臺北');
              const debug = win.__mapDebugStateForTest();
              const projection = win.lastGameState?.map?.legal_organization_moves?.['臺北'] || {};
              let keelung = null;
              win.__redlinePlayableMap.eachLayer(layer => {
                if (!layer.getLatLng || !layer.options || layer.options.fillColor === undefined) return;
                const ll = layer.getLatLng();
                if (Math.abs(ll.lat - 25.1276) < 0.001 && Math.abs(ll.lng - 121.7392) < 0.001) {
                  keelung = {
                    color: layer.options.color,
                    fillColor: layer.options.fillColor,
                    fillOpacity: layer.options.fillOpacity,
                  };
                }
              });
              const direct = doc.getElementById('directBuildBtn');
              const confirm = doc.getElementById('confirmMoveBtn');
              const cancel = doc.getElementById('cancelMoveBtn');
              const infoText = doc.getElementById('info')?.textContent || '';
              return {
                debug,
                projection,
                keelung,
                directBeforeConfirm: !!(direct.compareDocumentPosition(confirm) & Node.DOCUMENT_POSITION_FOLLOWING),
                cancelText: cancel.textContent,
                infoText,
              };
            }"""
        )
        reachable = set(initial['debug']['reachableFromSelected'])
        projected_towns = {
            entry['town']
            for mode in ('road', 'rail')
            for entry in initial['projection'].get(mode, [])
        }
        record(
            'map_candidates_exactly_match_backend_projection_and_exclude_inapplicable_town',
            reachable == projected_towns and '基隆' in reachable and '觀塘' not in reachable,
            {'reachable': sorted(reachable), 'projected': sorted(projected_towns)},
        )
        record(
            'candidate_uses_neutral_outline_without_overwriting_base_fill',
            initial['keelung']
            and initial['keelung']['color'] == '#e2e8f0'
            and initial['keelung']['fillColor'] == '#6b7280'
            and abs(initial['keelung']['fillOpacity'] - 0.32) < 0.01,
            initial['keelung'],
        )
        record(
            'build_control_precedes_move_confirmation_and_cancel_label_is_explicit',
            initial['directBeforeConfirm'] and initial['cancelText'] == '取消目的地（保留起點）',
            {'directBeforeConfirm': initial['directBeforeConfirm'], 'cancelText': initial['cancelText']},
        )
        record(
            'town_info_uses_presence_not_single_town_organization_count',
            '組織狀態：有組織' in initial['infoText']
            and '當前組織總數' not in initial['infoText']
            and '有組織（1）' not in initial['infoText'],
            {'infoText': initial['infoText']},
        )

        unrelated_click = page.evaluate(
            """() => {
              const win = document.getElementById('strategicMapFrame').contentWindow;
              win.__clickMoveTargetForTest('臺中');
              return win.__mapDebugStateForTest();
            }"""
        )
        record(
            'unrelated_inapplicable_town_is_noninteractive_during_move_selection',
            unrelated_click['selectedTown'] == '臺北'
            and unrelated_click['pendingMoveTarget'] is None
            and '基隆' in unrelated_click['reachableFromSelected'],
            unrelated_click,
        )

        pending = page.evaluate(
            """() => {
              const frame = document.getElementById('strategicMapFrame');
              const win = frame.contentWindow;
              win.__clickMoveTargetForTest('基隆');
              const doc = frame.contentDocument;
              return {
                debug: win.__mapDebugStateForTest(),
                hint: doc.getElementById('confirmMoveHint').textContent,
              };
            }"""
        )
        record(
            'destination_confirmation_shows_backend_cost_before_sending',
            pending['debug']['pendingMoveTarget'] == {'from': '臺北', 'to': '基隆', 'mode': 'rail', 'cost': 1}
            and '消耗 1 次移動' in pending['hint'],
            pending,
        )

        cancelled = page.evaluate(
            """() => {
              const frame = document.getElementById('strategicMapFrame');
              const win = frame.contentWindow;
              win.__cancelPendingMoveForTest();
              return {
                debug: win.__mapDebugStateForTest(),
                hint: frame.contentDocument.getElementById('confirmMoveHint').textContent,
              };
            }"""
        )
        record(
            'cancel_destination_keeps_origin_and_legal_candidates',
            cancelled['debug']['pendingMoveTarget'] is None
            and cancelled['debug']['selectedTown'] == '臺北'
            and '基隆' in cancelled['debug']['reachableFromSelected']
            and '仍以 臺北 為移動起點' in cancelled['hint'],
            cancelled,
        )

        click_visible_blank_map(page)
        blank = page.evaluate(
            """() => {
              const frame = document.getElementById('strategicMapFrame');
              const win = frame.contentWindow;
              return {
                debug: win.__mapDebugStateForTest(),
                info: frame.contentDocument.getElementById('info').textContent,
              };
            }"""
        )
        record(
            'blank_map_click_exits_the_entire_movement_selection',
            blank['debug']['selectedTown'] is None
            and blank['debug']['pendingMoveTarget'] is None
            and blank['debug']['reachableFromSelected'] == []
            and '尚未選取城鎮' in blank['info'],
            blank,
        )

        zero_target_before = page.evaluate(
            """() => {
              const win = document.getElementById('strategicMapFrame').contentWindow;
              win.__selectTownForTest('新竹');
              return win.__mapDebugStateForTest();
            }"""
        )
        click_visible_blank_map(page)
        zero_target_after = page.evaluate(
            "() => document.getElementById('strategicMapFrame').contentWindow.__mapDebugStateForTest()"
        )
        record(
            'blank_map_click_also_exits_an_origin_with_zero_legal_destinations',
            zero_target_before['selectedTown'] == '新竹'
            and zero_target_before['reachableFromSelected'] == []
            and zero_target_after['selectedTown'] is None
            and zero_target_after['pendingMoveTarget'] is None,
            {'before': zero_target_before, 'after': zero_target_after},
        )

        page.evaluate("() => document.getElementById('strategicMapFrame').contentWindow.__selectTownForTest('臺北')")
        page.wait_for_timeout(300)
        page.frame_locator('#strategicMapFrame').locator('#directBuildBtn').scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        page.locator('#strategicMapFrame').screenshot(path=str(SCREENSHOT))
        browser.close()

    record('browser_console_has_no_errors', not console_errors, {'errors': console_errors})
    summary = {
        'total': len(results),
        'passed': sum(1 for result in results if result['ok']),
        'failed': sum(1 for result in results if not result['ok']),
    }
    payload = {'summary': summary, 'results': results, 'screenshot': str(SCREENSHOT.relative_to(ROOT))}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# LEGAL MOVEMENT UI VALIDATION', '', f"結果：{summary['passed']}/{summary['total']} PASS", '', '重跑：`uv run --with playwright python scripts/validate_legal_movement_ui.py`', '']
    for result in results:
        lines.extend([f"- {'PASS' if result['ok'] else 'FAIL'} {result['name']}: `{json.dumps(result['detail'], ensure_ascii=False)}`"])
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    raise SystemExit(1 if summary['failed'] else 0)


if __name__ == '__main__':
    main()
