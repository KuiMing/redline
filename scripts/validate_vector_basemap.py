#!/usr/bin/env python3
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "records" / "map-ui" / "vector-basemap"
URL = "http://127.0.0.1:8781/static/leaflet_game_map.html"
VIEWPORTS = ((1280, 720), (1024, 768))


def wait_for_vector_basemap(page) -> None:
    page.wait_for_function("window.__redlineBasemapReady !== undefined")
    page.evaluate("() => window.__redlineBasemapReady")
    page.wait_for_function("document.querySelector('.maplibregl-canvas') !== null")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    checks = []
    screenshots = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for width, height in VIEWPORTS:
            page = browser.new_page(viewport={"width": width, "height": height})
            console_errors = []
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.goto(URL, wait_until="networkidle")
            wait_for_vector_basemap(page)
            state = page.evaluate(
                """async () => {
                    const vectorMap = await window.__redlineBasemapReady;
                    const style = vectorMap.getStyle();
                    return {
                        loaded: vectorMap.loaded(),
                        layerIds: style.layers.map(layer => layer.id),
                        symbolCount: style.layers.filter(layer => layer.type === 'symbol').length,
                        attribution: document.querySelector('.leaflet-control-attribution')?.innerText || '',
                        canvas: !!document.querySelector('.maplibregl-canvas'),
                        overlayCanvasCount: document.querySelectorAll('.leaflet-overlay-pane canvas').length,
                        unavailable: document.getElementById('map').classList.contains('redline-basemap-unavailable'),
                        apiKeyRequired: document.body.innerText.includes('API KEY REQUIRED'),
                    };
                }"""
            )
            prefix = f"{width}x{height}"
            checks.extend(
                [
                    {"name": f"{prefix}: vector basemap loaded", "passed": state["loaded"] and state["canvas"]},
                    {"name": f"{prefix}: all symbol layers removed", "passed": state["symbolCount"] == 0},
                    {"name": f"{prefix}: minimal layer count", "passed": 10 <= len(state["layerIds"]) <= 35},
                    {"name": f"{prefix}: OFM/OSM attribution", "passed": "OpenFreeMap" in state["attribution"] and "OpenStreetMap" in state["attribution"]},
                    {"name": f"{prefix}: Redline overlay canvas", "passed": state["overlayCanvasCount"] >= 1},
                    {"name": f"{prefix}: no API key error", "passed": not state["apiKeyRequired"]},
                    {"name": f"{prefix}: basemap available", "passed": not state["unavailable"]},
                    {"name": f"{prefix}: console clean", "passed": not console_errors, "details": console_errors},
                ]
            )
            screenshot = OUTPUT / f"vector_basemap_{prefix}.png"
            page.screenshot(path=str(screenshot), full_page=True)
            screenshots.append(str(screenshot.relative_to(ROOT)))
            interaction = page.evaluate(
                """() => {
                    const marker = Object.values(window.__redlinePlayableMap._layers)
                        .find(layer => layer.getLatLng?.() && layer._events?.click);
                    if (!marker) return false;
                    marker.fire('click', {latlng: marker.getLatLng()});
                    return (document.getElementById('info')?.innerText || '').includes('座標：');
                }"""
            )
            checks.append({"name": f"{prefix}: town marker interaction", "passed": interaction})
            page.close()

        detail_page = browser.new_page(viewport={"width": 1280, "height": 720})
        detail_console_errors = []
        detail_page.on("console", lambda message: detail_console_errors.append(message.text) if message.type == "error" else None)
        detail_page.goto(URL, wait_until="networkidle")
        wait_for_vector_basemap(detail_page)
        detail_page.evaluate("() => { window.__redlinePlayableMap.setView([22.282, 114.158], 11, {animate:false}); return true; }")
        detail_page.wait_for_timeout(1500)
        detail_page.evaluate("""async () => {
            const vectorMap = await window.__redlineBasemapReady;
            if (!vectorMap.loaded()) await new Promise(resolve => vectorMap.once('idle', resolve));
        }""")
        detail_page.wait_for_function("document.querySelectorAll('.town-label').length >= 5")
        detail_state = detail_page.evaluate(
            """async () => {
                const vectorMap = await window.__redlineBasemapReady;
                return {
                    zoom: window.__redlinePlayableMap.getZoom(),
                    symbolCount: vectorMap.getStyle().layers.filter(layer => layer.type === 'symbol').length,
                    customLabelCount: document.querySelectorAll('.town-label').length,
                    apiKeyRequired: document.body.innerText.includes('API KEY REQUIRED'),
                };
            }"""
        )
        checks.extend(
            [
                {"name": "Hong Kong zoom 11: exact zoom", "passed": detail_state["zoom"] == 11},
                {"name": "Hong Kong zoom 11: no basemap symbols", "passed": detail_state["symbolCount"] == 0},
                {"name": "Hong Kong zoom 11: Redline labels visible", "passed": detail_state["customLabelCount"] >= 5},
                {"name": "Hong Kong zoom 11: no API key error", "passed": not detail_state["apiKeyRequired"]},
                {"name": "Hong Kong zoom 11: console clean", "passed": not detail_console_errors, "details": detail_console_errors},
            ]
        )
        detail_screenshot = OUTPUT / "vector_basemap_hong_kong_zoom11_1280x720.png"
        detail_page.screenshot(path=str(detail_screenshot), full_page=True)
        screenshots.append(str(detail_screenshot.relative_to(ROOT)))
        detail_page.close()

        fallback_page = browser.new_page(viewport={"width": 1280, "height": 720})
        fallback_page.goto(URL, wait_until="networkidle")
        wait_for_vector_basemap(fallback_page)
        fallback_page.evaluate("handleBasemapError()")
        fallback = fallback_page.evaluate(
            """() => ({
                unavailable: document.getElementById('map').classList.contains('redline-basemap-unavailable'),
                vectorCanvasCount: document.querySelectorAll('.maplibregl-canvas').length,
            })"""
        )
        checks.append({"name": "vector error removes basemap and enables dark fallback", "passed": fallback["unavailable"] and fallback["vectorCanvasCount"] == 0})
        fallback_page.close()
        browser.close()

    report = {
        "url": URL,
        "checks": checks,
        "passed": sum(1 for check in checks if check["passed"]),
        "total": len(checks),
        "screenshots": screenshots,
    }
    (OUTPUT / "VECTOR_BASEMAP_VALIDATION.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
