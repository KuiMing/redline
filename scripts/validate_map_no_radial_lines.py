#!/usr/bin/env python3
"""Validate that Redline map selection no longer draws extra radial highlight lines.

This opens the official Leaflet map page, injects a minimal game state where the
current player owns 臺北, selects 臺北 through the map's test helper, and asserts
that selecting the town does not add temporary bright L.polyline layers. The
normal road/rail network should remain present.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "records" / "map-ui"
URL = "http://127.0.0.1:8000/static/leaflet_game_map.html"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot = OUT_DIR / f"MAP_NO_RADIAL_LINES_{stamp}.png"
    json_path = OUT_DIR / f"MAP_NO_RADIAL_LINES_{stamp}.json"
    md_path = OUT_DIR / f"MAP_NO_RADIAL_LINES_{stamp}.md"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        page.goto(URL, wait_until="networkidle")
        result = page.evaluate(
            """
            async () => {
              window.connectGameMap({gameId:'proof-no-radial-lines', playerId:'p1'});
              const countPolylines = () => {
                let total = 0;
                let bright = 0;
                const samples = [];
                window.__redlinePlayableMap.eachLayer(layer => {
                  if (layer instanceof L.Polyline && !(layer instanceof L.Polygon)) {
                    total += 1;
                    const opt = layer.options || {};
                    if ((opt.color === '#ffd166' && opt.weight === 6) || (opt.color === '#67e8f9' && opt.weight === 7)) {
                      bright += 1;
                    }
                    if (samples.length < 8) {
                      samples.push({color: opt.color, weight: opt.weight, opacity: opt.opacity, dashArray: opt.dashArray || ''});
                    }
                  }
                });
                return { total, bright, samples };
              };
              const before = countPolylines();
              window.dispatchEvent(new MessageEvent('message', { origin: window.location.origin, data: { type: 'redline-state', state: {
                current_player: 'host',
                players: [{id:'p1', name:'host', faction:'臺灣', orgs:{'臺北':1}}],
                map: { towns: {'臺北': [{player:'host', count:1}]}, shared_access:{} }
              }}}));
              const selected = window.__selectTownForTest('臺北');
              await new Promise(resolve => setTimeout(resolve, 250));
              const after = countPolylines();
              const script = [...document.scripts].map(s => s.src).filter(src => src.includes('leaflet_game_map_logic'))[0];
              return {
                before,
                selected,
                after,
                no_new_radial_polylines: after.total === before.total && after.bright === 0,
                cache_busted_script: script,
                status_selected_town: document.getElementById('statusSelectedTown')?.textContent || '',
                direct_build_button_text: document.getElementById('directBuildBtn')?.textContent || '',
                direct_build_disabled: document.getElementById('directBuildBtn')?.disabled ?? null,
              };
            }
            """
        )
        page.screenshot(path=str(screenshot), full_page=True)
        browser.close()

    result["screenshot"] = str(screenshot)
    result["passed"] = bool(result["no_new_radial_polylines"] and result["selected"].get("highlighted"))
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        "# Map no-radial-lines validation\n\n"
        f"- URL: `{URL}`\n"
        f"- Selected town: `{result['selected'].get('town')}`\n"
        f"- Highlighted: `{result['selected'].get('highlighted')}`\n"
        f"- Before polyline count: `{result['before']['total']}`\n"
        f"- After polyline count: `{result['after']['total']}`\n"
        f"- Bright temporary radial polylines after select: `{result['after']['bright']}`\n"
        f"- Cache-busted script: `{result['cache_busted_script']}`\n"
        f"- Screenshot: `{screenshot}`\n"
        f"- Result: `{'PASS' if result['passed'] else 'FAIL'}`\n",
        encoding="utf-8",
    )
    print(json.dumps({"passed": result["passed"], "json": str(json_path), "markdown": str(md_path), "screenshot": str(screenshot)}, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
