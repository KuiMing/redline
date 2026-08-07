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
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards'
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
OUT_JSON = RECORD_DIR / 'SUPPORT_CARD_DETAIL_BUTTON_VALIDATION.json'
OUT_MD = RECORD_DIR / 'SUPPORT_CARD_DETAIL_BUTTON_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'support_card_detail_button.png'


def post_json(path, payload=None):
    data = json.dumps(payload or {}).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def hand_card_buttons(page, card_name):
    return page.evaluate(
        """(name) => {
          const action = [...document.querySelectorAll('#hand .hand-card .hand-card-action-btn')]
            .find(button => button.dataset.cardName === name);
          const card = action?.closest('.hand-card');
          if (!card) return null;
          return [...card.querySelectorAll('.hand-card-action-btn')].map(b => ({
            text: b.textContent.trim(), mode: b.dataset.cardMode, disabled: b.disabled,
          }));
        }""",
        card_name,
    )


def check(browser):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    # 歷程：奧援卡原本有「資源」按鈕（誤導，實際不給資源），2026-07-16 曾改為「詳情」＋
    # 「棄置」；卡面完整顯示 I/II/III 級文字後「詳情」已無存在意義（只做閃爍聚焦），
    # 2026-07-17 移除。最終狀態：奧援卡＝棄置／行動 兩顆按鈕，非奧援卡＝資源／行動。

    # --- Case 1: 一般奧援卡（臺灣奧援）顯示 棄置＋行動，沒有 資源、沒有 詳情 ---
    page = browser.new_context(viewport={'width': 1280, 'height': 900}).new_page()
    setup = post_json('/test/setup-support-proof', {'support_name': '臺灣奧援', 'tier': 2})
    page.goto(f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}", wait_until='networkidle')
    page.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page.wait_for_timeout(900)
    page.evaluate("""() => {
      document.getElementById('closeFactionActionModal')?.click();
      if (typeof closeEventReveal === 'function') closeEventReveal();
      if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
    }""")
    page.wait_for_timeout(300)

    buttons = hand_card_buttons(page, '臺灣奧援')
    record(
        'support_card_shows_discard_and_action_only',
        buttons is not None
        and [b['text'] for b in buttons] == ['棄置', '行動']
        and any(b['mode'] == 'resource' and b['text'] == '棄置' for b in buttons),
        {'buttons': buttons},
    )

    page.screenshot(path=str(SCREENSHOT))

    # 完整卡面圖片直接顯示；隱藏 fallback 仍須保留三級文字。幾何檢查改驗證實際圖片已載入且
    # 完整落在 card-art-face 內，不能再用 display:none 的 fallback clientHeight=0 假通過。
    face_text = page.text_content('#hand .hand-card .playable-card-art-fallback .card-effect-block') or ''
    face_metrics = page.eval_on_selector(
        '#hand .hand-card .playable-card-art-image',
        """img => {
          const image = img.getBoundingClientRect();
          const face = img.closest('.card-art-face')?.getBoundingClientRect();
          return {
            naturalW: img.naturalWidth,
            naturalH: img.naturalHeight,
            imageW: image.width,
            imageH: image.height,
            faceW: face?.width || 0,
            faceH: face?.height || 0,
            contained: !!face
              && image.left >= face.left - 1
              && image.top >= face.top - 1
              && image.right <= face.right + 1
              && image.bottom <= face.bottom + 1,
          };
        }""",
    )
    record(
        'card_face_shows_all_three_tier_effect_lines',
        all(tier in face_text for tier in ('III級', 'II級', 'I級')),
        {'face_text': face_text.strip()},
    )
    record(
        'card_face_art_is_loaded_and_contained',
        face_metrics['naturalW'] > 0
        and face_metrics['naturalH'] > 0
        and face_metrics['imageW'] > 0
        and face_metrics['imageH'] > 0
        and face_metrics['contained'] is True,
        face_metrics,
    )

    # --- Case 2: 棄置按鈕把卡送進棄牌堆、不給任何資源 ---
    before_hand = page.evaluate(
        "(id) => window.lastGameState?.players?.find(p => p.id === id)?.hand || []", setup['player_id']
    )
    before_resources = page.evaluate(
        "(id) => window.lastGameState?.players?.find(p => p.id === id)?.resources || {}", setup['player_id']
    )
    page.click("#hand .hand-card [data-card-mode='resource']")
    page.wait_for_timeout(500)
    after_hand = page.evaluate(
        "(id) => window.lastGameState?.players?.find(p => p.id === id)?.hand || []", setup['player_id']
    )
    after_resources = page.evaluate(
        "(id) => window.lastGameState?.players?.find(p => p.id === id)?.resources || {}", setup['player_id']
    )
    after_discard = page.evaluate(
        "(id) => window.lastGameState?.players?.find(p => p.id === id)?.discard_pile || []", setup['player_id']
    )
    record(
        'discard_button_discards_with_no_resource_gain',
        before_hand == ['臺灣奧援'] and after_hand == [] and after_discard == ['臺灣奧援']
        and before_resources == after_resources,
        {'before_hand': before_hand, 'after_hand': after_hand, 'after_discard': after_discard,
         'before_resources': before_resources, 'after_resources': after_resources},
    )
    page.close()

    # --- Case 3: 紅軍奧援是唯一可用資源模式的奧援，顯示 資源＋行動 ---
    page2 = browser.new_context(viewport={'width': 1280, 'height': 900}).new_page()
    setup2 = post_json('/test/setup-support-proof', {'support_name': '紅軍奧援', 'tier': 1})
    page2.goto(f"{BASE_URL}/?game_id={setup2['game_id']}&player_id={setup2['player_id']}", wait_until='networkidle')
    page2.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page2.wait_for_timeout(900)
    page2.evaluate("() => { const b = document.getElementById('closeFactionActionModal'); if (b) b.click(); }")
    page2.wait_for_timeout(300)
    buttons2 = hand_card_buttons(page2, '紅軍奧援')
    record(
        'red_army_support_card_shows_resource_and_action',
        buttons2 is not None and [b['text'] for b in buttons2] == ['資源', '行動'],
        {'buttons': buttons2},
    )
    page2.close()

    # --- Case 4: 非奧援卡（宣傳家）維持 資源／行動 ---
    page3 = browser.new_context(viewport={'width': 1280, 'height': 900}).new_page()
    setup3 = post_json('/test/setup-move-confirmation-proof', {'mover_faction': 'liberals', 'mover_base': '臺北', 'mover_town': '臺北', 'moves_left': 0})
    post_json('/test/setup-card-scenario', {'game_id': setup3['game_id'], 'player_id': setup3['player_id'], 'card_name': '宣傳家'})
    page3.goto(f"{BASE_URL}/?game_id={setup3['game_id']}&player_id={setup3['player_id']}", wait_until='networkidle')
    page3.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page3.wait_for_timeout(900)
    page3.evaluate("() => { const b = document.getElementById('closeFactionActionModal'); if (b) b.click(); }")
    page3.wait_for_timeout(300)
    buttons3 = hand_card_buttons(page3, '宣傳家')
    record(
        'non_support_card_keeps_the_resource_button',
        buttons3 is not None and any(b['mode'] == 'resource' and b['text'] == '資源' for b in buttons3)
        and not any(b['text'] in ('詳情', '棄置') for b in buttons3),
        {'buttons': buttons3},
    )
    page3.close()

    return {
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
        payload = check(browser)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 奧援卡手牌按鈕（棄置／行動）驗證',
        '',
        '可重跑指令：`python3 scripts/validate_support_card_detail_button.py`',
        '',
        f"- total: {payload['summary']['total']} / passed: {payload['summary']['passed']} / failed: {payload['summary']['failed']}",
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
