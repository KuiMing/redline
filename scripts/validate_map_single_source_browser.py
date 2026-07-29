#!/usr/bin/env python3
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = 'http://127.0.0.1:8000/static/leaflet_game_map.html'
OUT_DIR = ROOT / 'docs' / 'records' / 'map-ui'
OUT_JSON = OUT_DIR / 'MAP_SINGLE_SOURCE_VALIDATION.json'
OUT_SCREENSHOT = OUT_DIR / 'MAP_SINGLE_SOURCE_UI.png'


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    console_errors = []
    requested = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)
        page.on('request', lambda request: requested.append(request.url))
        page.goto(URL, wait_until='domcontentloaded')
        page.wait_for_function('window.__redlineMapDataReady !== undefined')
        page.evaluate('() => window.__redlineMapDataReady')
        page.wait_for_timeout(800)
        result = page.evaluate("""() => {
          const counts = { towns: 0, roads: 0, rails: 0 };
          window.__redlinePlayableMap.eachLayer(layer => {
            if (layer instanceof L.CircleMarker) counts.towns += 1;
            else if (layer instanceof L.Polyline && layer.options?.color === '#7a6030') counts.roads += 1;
            else if (layer instanceof L.Polyline && layer.options?.color === '#42667a') counts.rails += 1;
          });
          const bundle = window.__redlineCanonicalMapBundle;
          return {
            counts,
            canonicalTownCount: Object.keys(bundle.mapData.towns).length,
            geoTownCount: Object.keys(bundle.geoCoordinates).length,
            movementRules: bundle.mapData.movement_rules,
          };
        }""")
        page.screenshot(path=str(OUT_SCREENSHOT), full_page=True)

        standalone = browser.new_page(viewport={'width': 1280, 'height': 800})
        standalone.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)
        standalone.on('request', lambda request: requested.append(request.url))
        standalone.goto('http://127.0.0.1:8000/static/leaflet_full_map.html', wait_until='domcontentloaded')
        standalone.wait_for_function('window.__redlineCanonicalMapBundle !== undefined')
        standalone.wait_for_timeout(500)
        result['standaloneFilterOptionCounts'] = standalone.evaluate("""() => ({
          rulers: document.querySelectorAll('#rulerFilter option').length,
          camps: document.querySelectorAll('#campFilter option').length,
          types: document.querySelectorAll('#typeFilter option').length,
        })""")
        browser.close()

    result['requestedMapData'] = any(url.endswith('/map-data') for url in requested)
    result['requestedGeoCoordinates'] = any(url.endswith('/map-geo-coordinates') for url in requested)
    result['consoleErrors'] = console_errors
    checks = {
        'loads_map_data_endpoint': result['requestedMapData'],
        'loads_geo_endpoint': result['requestedGeoCoordinates'],
        'renders_269_towns': result['counts']['towns'] == result['canonicalTownCount'] == result['geoTownCount'] == 269,
        'preserves_185_visual_roads': result['counts']['roads'] == 185,
        'preserves_286_visual_rails': result['counts']['rails'] == 286,
        'movement_schema_matches_rules': result['movementRules'] == {
            'road_range': 1,
            'rail_range': 3,
            'move_cost': 1,
            'wall_crossing_range': 1,
            'wall_crossing_cost': 2,
        },
        'standalone_filters_are_not_duplicated': result['standaloneFilterOptionCounts'] == {
            'rulers': 10,
            'camps': 10,
            'types': 3,
        },
        'console_zero_errors': not console_errors,
    }
    payload = {
        'summary': {
            'total': len(checks),
            'passed': sum(checks.values()),
            'failed': len(checks) - sum(checks.values()),
        },
        'checks': checks,
        'detail': result,
        'screenshot': str(OUT_SCREENSHOT),
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload['summary'], ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
