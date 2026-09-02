import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    system_python = '/usr/bin/python3'
    if sys.executable != system_python and Path(system_python).exists():
        os.execv(system_python, [system_python, __file__, *sys.argv[1:]])
    raise

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'playtest-flow'
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
OUT_JSON = RECORD_DIR / 'LAN_INFO_DISPLAY_VALIDATION.json'
OUT_MD = RECORD_DIR / 'LAN_INFO_DISPLAY_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'lan_info_display.png'
DOMAIN_SCREENSHOT = RECORD_DIR / 'lan_info_domain_without_internal_port.png'


def check(browser):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    # --- 1. /server-info 回傳區網 IP 與 port ---
    info = json.loads(urllib.request.urlopen(BASE_URL + '/server-info', timeout=10).read().decode('utf-8'))
    ip_ok = bool(info.get('lan_ip')) and re.match(r'^\d+\.\d+\.\d+\.\d+$', info['lan_ip']) and not info['lan_ip'].startswith('127.')
    expected_service_port = urllib.parse.urlsplit(BASE_URL).port or 8000
    record('server_info_returns_lan_ip_and_port', bool(ip_ok) and info.get('port') == expected_service_port, {'info': info})

    # --- 2. lobby 顯示 IP 連線網址，複製按鈕可複製 ---
    console_errors = []
    page = browser.new_context(viewport={'width': 1440, 'height': 900}).new_page()
    page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)
    page.on('pageerror', lambda error: console_errors.append(str(error)))
    page.goto(BASE_URL + '/', wait_until='networkidle')
    page.wait_for_timeout(600)
    lan_url = page.evaluate("() => document.getElementById('lanUrl')?.value")
    expected_url = f"http://{info.get('lan_ip')}:{info.get('port')}"
    record('lobby_shows_lan_url', lan_url == expected_url, {'lan_url': lan_url, 'expected': expected_url})

    page.click('#copyLanUrlBtn')
    page.wait_for_timeout(300)
    status = page.evaluate("() => document.getElementById('lobbyStatusHint')?.textContent")
    record('copy_button_reports_copied', '已複製' in (status or ''), {'status': status})
    page.screenshot(path=str(SCREENSHOT))
    page.context.close()

    # --- 3. 公開網域不得附加容器內部的 :8000 ---
    domain_request = urllib.request.Request(
        BASE_URL + '/server-info',
        headers={
            'Host': 'redline.example.com',
            'X-Forwarded-Proto': 'https',
        },
    )
    domain_info = json.loads(urllib.request.urlopen(domain_request, timeout=10).read().decode('utf-8'))
    expected_domain_url = 'https://redline.example.com'
    record(
        'server_info_domain_omits_internal_port',
        domain_info.get('base_url') == expected_domain_url and domain_info.get('port') is None,
        {'info': domain_info, 'expected': expected_domain_url},
    )

    domain_context = browser.new_context(viewport={'width': 1440, 'height': 900})
    domain_page = domain_context.new_page()
    domain_page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)
    domain_page.on('pageerror', lambda error: console_errors.append(str(error)))
    domain_page.route(
        '**/server-info',
        lambda route: route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps(domain_info),
        ),
    )
    domain_page.goto(BASE_URL + '/', wait_until='networkidle')
    domain_page.wait_for_timeout(600)
    displayed_domain_url = domain_page.evaluate("() => document.getElementById('lanUrl')?.value")
    record(
        'lobby_shows_domain_without_internal_port',
        displayed_domain_url == expected_domain_url,
        {'lan_url': displayed_domain_url, 'expected': expected_domain_url},
    )
    domain_page.screenshot(path=str(DOMAIN_SCREENSHOT))
    domain_context.close()

    record('browser_console_has_no_errors', not console_errors, {'errors': console_errors})

    return {
        'summary': {
            'total': len(results),
            'passed': sum(1 for r in results if r['ok']),
            'failed': sum(1 for r in results if not r['ok']),
        },
        'results': results,
        'screenshots': [str(path.relative_to(ROOT)) for path in (SCREENSHOT, DOMAIN_SCREENSHOT)],
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        payload = check(browser)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 區網連線資訊顯示 驗證',
        '',
        '可重跑指令：`uv run --with playwright python scripts/validate/validate_lan_info_display.py`',
        '',
        f"- total: {payload['summary']['total']} / passed: {payload['summary']['passed']} / failed: {payload['summary']['failed']}",
        f"- screenshots: {', '.join(payload['screenshots'])}",
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
