import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = 'http://127.0.0.1:8000'
OUT_DIR = ROOT / 'docs' / 'records' / 'playtest-20260729'
OUT_JSON = OUT_DIR / 'CURRENT_PLAYTEST_UI_VALIDATION.json'
EAST_SCREENSHOT = OUT_DIR / 'east_support_map_build.png'
DISCARD_SCREENSHOT = OUT_DIR / 'discard_card_preview.png'


def post_json(path, payload):
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def open_fixture(page, support_name, tier):
    setup = post_json('/test/setup-support-proof', {'support_name': support_name, 'tier': tier})
    page.goto(
        f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
        wait_until='networkidle',
    )
    page.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page.wait_for_timeout(800)
    page.evaluate("""() => {
      if (typeof closeEventReveal === 'function') closeEventReveal();
      const factionClose = document.getElementById('closeFactionActionModal');
      if (factionClose) factionClose.click();
    }""")
    page.wait_for_timeout(200)
    return setup


def validate_east_support(browser):
    page = browser.new_context(viewport={'width': 1440, 'height': 1000}).new_page()
    open_fixture(page, '東洋奧援', 3)
    page.click('button.hand-card-action-btn[data-card-name="東洋奧援"][data-card-mode="action"]')
    page.wait_for_timeout(900)
    state = page.evaluate('() => window.lastGameState')
    page.click('button.game-tab[data-view="map"]')
    page.wait_for_timeout(1300)
    map_frame = page.frame_locator('#strategicMapFrame')
    hint_text = map_frame.locator('#interactionHint').inner_text()
    candidate_count = page.locator('#strategicMapFrame').element_handle().content_frame().evaluate("""() => {
      let neutral = 0;
      window.__redlinePlayableMap.eachLayer(layer => {
        if (layer instanceof L.CircleMarker && layer.options?.color === '#cbd5e1') neutral += 1;
      });
      return neutral;
    }""")
    modal_display = page.locator('#choiceModal').evaluate('(node) => getComputedStyle(node).display')
    page.screenshot(path=str(EAST_SCREENSHOT), full_page=True)
    detail = {
        'choice_key': state.get('pending_choice', {}).get('choice_key'),
        'interaction_kind': state.get('pending_choice', {}).get('interaction_kind'),
        'remaining_builds': state.get('pending_choice', {}).get('remaining_builds'),
        'server_town_count': len(state.get('pending_choice', {}).get('towns') or []),
        'candidate_marker_count': candidate_count,
        'hint': hint_text,
        'choice_modal_display': modal_display,
    }
    ok = (
        detail['choice_key'] == 'support_interaction'
        and detail['interaction_kind'] == 'build_organization'
        and detail['remaining_builds'] == 1
        and detail['server_town_count'] == candidate_count
        and candidate_count > 0
        and '尚可建立組織：1 個' in hint_text
        and modal_display == 'none'
    )
    page.close()
    return {'name': 'east_support_uses_map_and_shows_remaining_builds', 'ok': ok, 'detail': detail, 'screenshot': str(EAST_SCREENSHOT)}


def validate_discard_preview(browser):
    page = browser.new_context(viewport={'width': 1440, 'height': 1000}).new_page()
    open_fixture(page, '北國奧援', 1)
    page.click('button.hand-card-action-btn[data-card-name="北國奧援"][data-card-mode="resource"]')
    page.wait_for_timeout(700)
    page.evaluate("""() => {
      if (typeof closeEventReveal === 'function') closeEventReveal();
      const factionClose = document.getElementById('closeFactionActionModal');
      if (factionClose) factionClose.click();
    }""")
    page.click('button.game-tab[data-view="log"]')
    page.wait_for_timeout(500)
    discard_button = page.locator('.player-status-discard-card[data-card-name="北國奧援"]').first
    discard_button.click()
    page.wait_for_timeout(400)
    modal_display = page.locator('#cardPreviewModal').evaluate('(node) => getComputedStyle(node).display')
    preview_label = page.locator('#cardPreviewModal').get_attribute('aria-label')
    preview_image_src = page.locator('#cardPreviewContent .playable-card-art-image').first.get_attribute('src')
    preview_variant = discard_button.get_attribute('data-card-variant-index')
    page.screenshot(path=str(DISCARD_SCREENSHOT), full_page=True)
    detail = {
        'modal_display': modal_display,
        'preview_label': preview_label,
        'preview_image_src': preview_image_src,
        'discard_variant_index': preview_variant,
    }
    ok = modal_display != 'none' and preview_label == '北國奧援 放大檢視' and preview_variant == '0' and bool(preview_image_src)
    page.close()
    return {'name': 'discard_card_opens_exact_full_card_preview', 'ok': ok, 'detail': detail, 'screenshot': str(DISCARD_SCREENSHOT)}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        results = [validate_east_support(browser), validate_discard_preview(browser)]
        browser.close()
    payload = {
        'summary': {
            'total': len(results),
            'passed': sum(1 for item in results if item['ok']),
            'failed': sum(1 for item in results if not item['ok']),
        },
        'results': results,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload['summary'], ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
