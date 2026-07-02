#!/usr/bin/env python3
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8766')
RECORD_DIR = BASE / 'docs' / 'records' / 'phase-flow'


def post_json(path, payload=None):
    data = json.dumps(payload or {}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode('utf-8'))


def make_formal_game():
    create = post_json('/create')
    game_id = create['game_id']
    host_id = create['host_id']
    players = [
        ('host', host_id, 'red_army', '北京'),
        ('hk', post_json('/join', {'game_id': game_id, 'name': 'hk'})['player_id'], 'hong_kong', '香港城'),
    ]
    for name, pid, faction_id, base_name in players:
        chosen = post_json('/choose-faction', {'game_id': game_id, 'player_id': pid, 'faction_id': faction_id, 'base_name': base_name})
        if chosen.get('error'):
            raise AssertionError(f'choose {name}: {chosen}')
        ready = post_json('/ready', {'game_id': game_id, 'player_id': pid, 'ready': True})
        if ready.get('error'):
            raise AssertionError(f'ready {name}: {ready}')
    started = post_json('/start', {'game_id': game_id, 'player_id': host_id, 'market_mode': 'sample_53'})
    if started.get('error'):
        raise AssertionError(started)
    return game_id, {name: pid for name, pid, *_ in players}


def wait_state(page):
    page.wait_for_function('window.lastGameState && window.lastGameState.players && document.querySelectorAll(".hand-card").length > 0', timeout=15000)
    page.wait_for_timeout(350)
    return page.evaluate('window.lastGameState')


def event_panel_snapshot(page):
    panel = page.locator('#eventCardPanel')
    return {
        'visible': panel.is_visible(timeout=5000),
        'text': panel.inner_text(timeout=5000) if panel.is_visible(timeout=5000) else '',
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    screenshot_dir = RECORD_DIR / f'action-first-phase-{stamp}'
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    game_id, ids = make_formal_game()
    prepared = post_json('/test/set-hand', {
        'game_id': game_id,
        'player_id': ids['hk'],
        'cards': ['追隨者', '追隨者', '追隨者'],
        'turn_phase': 'action',
        'set_current_player': True,
    })
    if prepared.get('error'):
        raise AssertionError(prepared)

    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        url = f'{BASE_URL}/?game_id={game_id}&player_id={ids["hk"]}&v=action-first-phase-{stamp}'
        page.goto(url, wait_until='domcontentloaded')
        state = wait_state(page)
        meta = page.locator('#phaseActionMeta').inner_text(timeout=5000)
        advance_text = page.locator('#advanceStepBtn').inner_text(timeout=5000)
        event_panel = event_panel_snapshot(page)
        resource_disabled = page.locator(".hand-card").filter(has_text='追隨者').locator("button[data-card-mode='resource']").first.is_disabled()
        action_disabled = page.locator(".hand-card").filter(has_text='追隨者').locator("button[data-card-mode='action']").first.is_disabled()
        buy_disabled_action = page.locator('#purchaseStatic .purchase-card-buy-btn').first.is_disabled()
        shot1 = screenshot_dir / '01_initial_action_phase_cards_enabled_buy_disabled.png'
        page.screenshot(path=str(shot1), full_page=True)
        checks.append({'name': 'starts_in_action_phase', 'passed': state.get('turn_phase') == 'action' and '目前：行動｜下一步：開始購買階段' in meta and advance_text == '開始購買階段'})
        checks.append({'name': 'current_event_visible_at_action_start', 'passed': bool(state.get('current_event')) and event_panel['visible'] and (state.get('current_event') or {}).get('name', '') in event_panel['text'], 'details': {'current_event': state.get('current_event'), 'event_panel': event_panel}})
        checks.append({'name': 'hand_actions_enabled_initially', 'passed': not resource_disabled and not action_disabled})
        checks.append({'name': 'purchase_disabled_before_purchase_phase', 'passed': buy_disabled_action})

        for _ in range(3):
            page.locator(".hand-card").filter(has_text='追隨者').locator("button[data-card-mode='resource']").first.click(timeout=5000)
            page.wait_for_timeout(250)

        page.locator('#advanceStepBtn').click(timeout=5000)
        page.wait_for_function('window.lastGameState && window.lastGameState.turn_phase === "end"', timeout=10000)
        page.wait_for_timeout(350)
        state2 = page.evaluate('window.lastGameState')
        meta2 = page.locator('#phaseActionMeta').inner_text(timeout=5000)
        advance_text2 = page.locator('#advanceStepBtn').inner_text(timeout=5000)
        hand_resource_count_after_purchase = page.locator(".hand-card button[data-card-mode='resource']").count()
        resource_disabled2 = hand_resource_count_after_purchase == 0 or page.locator(".hand-card button[data-card-mode='resource']").first.is_disabled()
        buy_disabled_purchase = page.locator('#purchaseStatic .purchase-card-buy-btn').first.is_disabled()
        shot2 = screenshot_dir / '02_purchase_phase_hand_disabled_buy_enabled.png'
        page.screenshot(path=str(shot2), full_page=True)
        checks.append({'name': 'advance_enters_purchase_phase', 'passed': state2.get('turn_phase') == 'end' and '目前：購買｜下一步：結束回合' in meta2 and advance_text2 == '結束回合'})
        checks.append({'name': 'purchase_phase_disables_hand_enables_buy', 'passed': resource_disabled2 and not buy_disabled_purchase})
        browser.close()

    summary = {'total': len(checks), 'passed': sum(1 for c in checks if c['passed']), 'failed': sum(1 for c in checks if not c['passed'])}
    report = {'summary': summary, 'checks': checks, 'screenshots': [str(p.relative_to(BASE)) for p in sorted(screenshot_dir.glob('*.png'))]}
    json_path = RECORD_DIR / f'ACTION_FIRST_PHASE_BROWSER_{stamp}.json'
    md_path = RECORD_DIR / f'ACTION_FIRST_PHASE_BROWSER_{stamp}.md'
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    md_path.write_text('# Action-first phase browser validation\n\n```json\n' + json.dumps(report, ensure_ascii=False, indent=2) + '\n```\n', encoding='utf-8')
    print(json.dumps({'summary': summary, 'reports': [str(json_path), str(md_path)], 'screenshots': [str(BASE / p) for p in report['screenshots']]}, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
