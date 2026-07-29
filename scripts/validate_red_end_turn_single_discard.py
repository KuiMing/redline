#!/usr/bin/env python3
import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = 'http://127.0.0.1:8000'
OUT_DIR = ROOT / 'docs' / 'records' / 'deck-lifecycle'
OUT_JSON = OUT_DIR / 'RED_END_TURN_SINGLE_DISCARD_VALIDATION.json'
OUT_MD = OUT_DIR / 'RED_END_TURN_SINGLE_DISCARD_VALIDATION.md'


def post_json(path, payload):
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    return json.loads(urllib.request.urlopen(request, timeout=20).read().decode('utf-8'))


def player_snapshot(state, player_id):
    player = next(item for item in state['players'] if item['id'] == player_id)
    return {
        'hand': list(player.get('hand') or []),
        'deck_count': player.get('deck_count'),
        'discard_count': player.get('discard_count'),
        'discard_pile': list(player.get('discard_pile') or []),
    }


def run_scenario(browser, scenario):
    fixture = post_json('/test/setup-discard-reshuffle-proof', {'scenario': scenario})
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    page = context.new_page()
    console_errors = []
    page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
    page.goto(
        f"{BASE_URL}/?game_id={fixture['game_id']}&player_id={fixture['player_id']}",
        wait_until='networkidle',
    )
    page.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page.wait_for_function('window.lastGameState && window.lastGameState.turn_phase === "end"')
    page.evaluate("""() => {
      if (typeof closeEventReveal === 'function') closeEventReveal();
      const factionClose = document.getElementById('closeFactionActionModal');
      if (factionClose) factionClose.click();
    }""")
    before_state = page.evaluate('() => window.lastGameState')
    before = player_snapshot(before_state, fixture['player_id'])
    button_text = page.locator('#advanceStepBtn').inner_text()
    button_enabled = page.locator('#advanceStepBtn').is_enabled()
    page.click('#advanceStepBtn')
    page.wait_for_function(
        '() => window.lastGameState && window.lastGameState.current_player === "對手"',
        timeout=10000,
    )
    page.wait_for_timeout(500)
    after_state = page.evaluate('() => window.lastGameState')
    after = player_snapshot(after_state, fixture['player_id'])
    action_log = list(after_state.get('action_log') or [])
    page.click('button.game-tab[data-view="log"]')
    page.wait_for_timeout(300)
    status_text = page.locator('#playerStatusOverview').inner_text()
    screenshot = OUT_DIR / f'RED_END_TURN_SINGLE_DISCARD_{scenario.upper()}.png'
    page.screenshot(path=str(screenshot), full_page=True)
    context.close()

    total_before = len(before['hand']) + before['deck_count'] + before['discard_count']
    total_after = len(after['hand']) + after['deck_count'] + after['discard_count']
    base_ok = (
        button_text == '結束回合'
        and button_enabled
        and before['discard_count'] == 1
        and before['discard_pile'] == ['棄牌唯一一張']
        and len(before['hand']) == 4
        and len(after['hand']) == 5
        and total_before == total_after
        and not console_errors
    )
    if scenario == 'sufficient':
        behavior_ok = (
            before['deck_count'] == 1
            and after['deck_count'] == 0
            and after['discard_count'] == 1
            and after['discard_pile'] == ['棄牌唯一一張']
            and '牌庫保留牌' in after['hand']
            and '棄牌唯一一張' not in after['hand']
            and not any('牌庫用盡' in line and '洗成新牌庫' in line for line in action_log)
        )
    else:
        behavior_ok = (
            before['deck_count'] == 0
            and after['deck_count'] == 0
            and after['discard_count'] == 0
            and after['discard_pile'] == []
            and '棄牌唯一一張' in after['hand']
            and any('牌庫用盡' in line and '將棄牌堆 1 張牌洗成新牌庫' in line for line in action_log)
        )
    return {
        'name': scenario,
        'ok': base_ok and behavior_ok,
        'button_text': button_text,
        'button_enabled': button_enabled,
        'before': before,
        'after': after,
        'total_before': total_before,
        'total_after': total_after,
        'status_text': status_text,
        'action_log': action_log,
        'console_errors': console_errors,
        'screenshot': str(screenshot),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        results = [run_scenario(browser, 'sufficient'), run_scenario(browser, 'exhausted')]
        browser.close()
    payload = {
        'summary': {
            'total': len(results),
            'passed': sum(item['ok'] for item in results),
            'failed': sum(not item['ok'] for item in results),
        },
        'results': results,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 紅軍結束回合：單張棄牌洗牌驗證',
        '',
        f"- 結果：{payload['summary']['passed']}/{payload['summary']['total']} passed",
        '- 規則：只有補牌過程耗盡牌庫時，才將棄牌堆洗成新牌庫。',
        '',
    ]
    for result in results:
        lines.extend([
            f"## {result['name']}",
            f"- PASS：{result['ok']}",
            f"- Before：`{result['before']}`",
            f"- After：`{result['after']}`",
            f"- Screenshot：`{result['screenshot']}`",
            '',
        ])
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(payload['summary'], ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
