#!/usr/bin/env python3
"""Browser proof: 情報網 dissolve target can be completed from the map after closing the modal."""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards'
STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
SHOT_DIR = RECORD_DIR / f'intel-network-map-close-{STAMP}'
JSON_OUT = RECORD_DIR / f'INTEL_NETWORK_MAP_CLOSE_BROWSER_{STAMP}.json'
MD_OUT = RECORD_DIR / f'INTEL_NETWORK_MAP_CLOSE_BROWSER_{STAMP}.md'
BASE_URL = 'http://127.0.0.1:8000'


def ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright, expect
        return sync_playwright, expect
    except Exception:
        py = '/usr/bin/python3'
        if Path(py).exists() and Path(sys.executable).resolve() != Path(py).resolve():
            result = subprocess.run([py, str(Path(__file__).resolve())], cwd=str(ROOT))
            raise SystemExit(result.returncode)
        raise


def check(name, passed, details):
    return {'name': name, 'passed': bool(passed), 'details': details}


def main():
    sync_playwright, expect = ensure_playwright()
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    checks = []
    screenshots = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 950}, device_scale_factor=1)
        setup = page.request.post(f'{BASE_URL}/test/setup-intel-network-proof', data={}).json()
        game_id = setup['game_id']
        player_id = setup['player_id']
        page.goto(f'{BASE_URL}/?game_id={game_id}&player_id={player_id}', wait_until='networkidle')
        page.wait_for_function("window.lastGameState && window.lastGameState.players && window.lastGameState.players[0].hand.includes('情報網')")

        page.locator("button.hand-card-action-btn[data-card-name='情報網'][data-card-mode='action']").click()
        page.wait_for_function("window.lastGameState?.pending_choice?.choice_key === 'choose_one'")
        page.get_by_role('button', name='瓦解己方組織1格內的1個對手組織').click()
        page.wait_for_function("window.lastGameState?.pending_choice?.choice_key === 'intel_network_dissolve_target'")
        pending_before_close = page.evaluate("window.lastGameState.pending_choice")
        checks.append(check(
            '情報網瓦解選項建立 target pending choice',
            pending_before_close.get('choice_key') == 'intel_network_dissolve_target' and len(pending_before_close.get('targets') or []) > 0,
            {'pending_choice': pending_before_close},
        ))

        before = SHOT_DIR / 'before_closing_choice_modal.png'
        page.screenshot(path=str(before), full_page=True)
        screenshots.append(str(before))

        page.locator('#closeChoiceModal').click()
        page.wait_for_function("document.querySelector('#choiceModal').style.display === 'none'")
        after_close_choice = page.evaluate("window.lastGameState.pending_choice")
        page.get_by_role('button', name='戰略地圖').click()
        frame_el = page.locator('#strategicMapFrame')
        expect(frame_el).to_be_visible()
        frame_handle = frame_el.element_handle()
        frame = frame_handle.content_frame() if frame_handle else None
        assert frame is not None
        frame.wait_for_function("window.__redlinePlayableMap && window.__lastMapState?.pending_choice?.choice_key === 'intel_network_dissolve_target'")
        # Click the highlighted target by converting its town coordinates to an actual screen point.
        point = frame.evaluate("""
        () => {
          const choice = window.__lastMapState.pending_choice;
          const target = choice.targets.find(t => t.town) || choice.targets[0];
          const town = target.town;
          window.selectTownForCurrentMapAction?.(town, { autoFocus: false });
          const data = MAP_DATA.towns[town];
          const coords = GEO_COORDS[town];
          const pt = window.__redlinePlayableMap.latLngToContainerPoint([coords[1], coords[0]]);
          return { town, x: pt.x, y: pt.y };
        }
        """)
        frame.locator('#dissolveBtn').click()
        page.wait_for_function("!window.lastGameState.pending_choice")
        final_state = page.evaluate("window.lastGameState")
        enemy_a = next(ply for ply in final_state['players'] if ply['name'] == 'enemyA')
        checks.append(check(
            '關閉 modal 後仍可用地圖效果按鈕完成瓦解',
            after_close_choice.get('choice_key') == 'intel_network_dissolve_target' and enemy_a['orgs'].get('天津', 0) == 0,
            {'selected_town': point['town'], 'enemyA_orgs': enemy_a['orgs'], 'pending_after_close': after_close_choice},
        ))
        checks.append(check(
            '瓦解後 pending choice 清除，可繼續流程',
            final_state.get('pending_choice') is None,
            {'turn_phase': final_state.get('turn_phase'), 'log_tail': final_state.get('action_log', [])[-5:]},
        ))
        after = SHOT_DIR / 'after_map_dissolve_modal_closed.png'
        page.screenshot(path=str(after), full_page=True)
        screenshots.append(str(after))
        browser.close()

    payload = {
        'success': all(item['passed'] for item in checks),
        'summary': {'total': len(checks), 'passed': sum(1 for c in checks if c['passed']), 'failed': sum(1 for c in checks if not c['passed'])},
        'checks': checks,
        'screenshots': screenshots,
    }
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    MD_OUT.write_text('# INTEL NETWORK MAP CLOSE BROWSER\n\n' + '\n'.join(f"- {'PASS' if c['passed'] else 'FAIL'} {c['name']}: `{c['details']}`" for c in checks) + '\n', encoding='utf-8')
    print(json.dumps({'success': payload['success'], 'json': str(JSON_OUT), 'md': str(MD_OUT), 'screenshots': screenshots}, ensure_ascii=False))
    if not payload['success']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
