#!/usr/bin/env python3
"""Browser proof: 情報網 dissolve target auto-switches to the map and marks legal targets
with a 💀 marker (2026-08-02 playtest 建議). This validator previously tested a "close the
modal, then use the map sidebar button" fallback path; that path no longer exists because
the choice modal is never shown for a dissolve-target step at all — see the
`interaction_kind: 'dissolve_organization'` unification in server/game.py:state(). Clicking
a 💀 marker now only *arms* it (selects the target and enables the sidebar confirm button);
the actual dissolve only fires after an explicit `#dissolveBtn` click — added 2026-08-02 in
response to playtest feedback that a single accidental click on a skull was too easy to
trigger by someone just exploring the map."""
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
        pending_after_choice = page.evaluate("window.lastGameState.pending_choice")
        checks.append(check(
            '情報網瓦解選項建立 target pending choice 並標記 interaction_kind',
            pending_after_choice.get('choice_key') == 'intel_network_dissolve_target'
            and pending_after_choice.get('interaction_kind') == 'dissolve_organization'
            and len(pending_after_choice.get('targets') or []) > 0,
            {'pending_choice': pending_after_choice},
        ))

        # The dissolve-target step now hides the generic choice modal entirely and jumps
        # straight to the strategic map — no modal to close, no side-panel button needed.
        page.wait_for_timeout(400)
        modal_hidden = page.evaluate("document.getElementById('choiceModal').style.display === 'none'")
        active_view = page.evaluate("document.querySelector('.game-view.active')?.id")
        checks.append(check(
            '建立 pending choice 後自動隱藏選擇 modal 並切到戰略地圖',
            modal_hidden and active_view == 'mapView',
            {'modal_hidden': modal_hidden, 'active_view': active_view},
        ))

        before = SHOT_DIR / 'map_with_skull_marker.png'
        page.screenshot(path=str(before), full_page=True)
        screenshots.append(str(before))

        frame_el = page.locator('#strategicMapFrame')
        expect(frame_el).to_be_visible()
        skull = page.frame_locator('#strategicMapFrame').locator('.dissolve-target-badge')
        skull_count = skull.count()
        checks.append(check(
            '合法瓦解目標以 💀 標示，且數量與後端投影的候選一致',
            skull_count == len(pending_after_choice.get('targets') or []),
            {'skull_count': skull_count, 'target_count': len(pending_after_choice.get('targets') or [])},
        ))

        skull.first.click()
        page.wait_for_timeout(400)
        armed_count = page.frame_locator('#strategicMapFrame').locator('.dissolve-target-badge-armed').count()
        still_pending = page.evaluate("window.lastGameState?.pending_choice") is not None
        checks.append(check(
            '點擊 💀 標記僅選取目標並啟用確認按鈕，尚未真正瓦解',
            armed_count == 1 and still_pending,
            {'armed_count': armed_count, 'still_pending': still_pending},
        ))

        page.frame_locator('#strategicMapFrame').locator('#dissolveBtn').click()
        page.wait_for_function("!window.lastGameState.pending_choice")
        final_state = page.evaluate("window.lastGameState")
        enemy_a = next(ply for ply in final_state['players'] if ply['name'] == 'enemyA')
        checks.append(check(
            '按下側欄確認按鈕才真正完成瓦解，pending choice 清除',
            final_state.get('pending_choice') is None and enemy_a['orgs'].get('天津', 0) == 0,
            {'enemyA_orgs': enemy_a['orgs']},
        ))
        after = SHOT_DIR / 'after_skull_click_dissolved.png'
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
