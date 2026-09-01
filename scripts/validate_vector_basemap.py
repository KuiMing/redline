#!/usr/bin/env python3
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "records" / "map-ui" / "vector-basemap"
URL = "http://127.0.0.1:8781/static/leaflet_game_map.html"
STYLE_URL = "https://tiles.openfreemap.org/styles/liberty"
VIEWPORTS = ((1280, 720), (1024, 768))


def wait_for_vector_basemap(page) -> None:
    page.wait_for_function("window.__redlineBasemapReady !== undefined")
    page.evaluate("() => window.__redlineBasemapReady")
    page.wait_for_function("document.querySelector('.maplibregl-canvas') !== null")


def wait_for_dark_fallback(page) -> dict:
    page.wait_for_function(
        "document.getElementById('map')?.classList.contains('redline-basemap-unavailable')",
        timeout=20_000,
    )
    return page.evaluate(
        """() => ({
            unavailable: document.getElementById('map').classList.contains('redline-basemap-unavailable'),
            vectorCanvasCount: document.querySelectorAll('.maplibregl-canvas').length,
        })"""
    )


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

        direct_fallback_page = browser.new_page(viewport={"width": 1280, "height": 720})
        direct_fallback_page.goto(URL, wait_until="networkidle")
        wait_for_vector_basemap(direct_fallback_page)
        direct_fallback_page.evaluate("handleBasemapError()")
        direct_fallback = wait_for_dark_fallback(direct_fallback_page)
        checks.append({
            "name": "direct vector error removes basemap and enables dark fallback",
            "passed": direct_fallback["unavailable"] and direct_fallback["vectorCanvasCount"] == 0,
        })
        direct_fallback_page.close()

        style_failure_page = browser.new_page(viewport={"width": 1280, "height": 720})
        style_failure_page.route(STYLE_URL, lambda route: route.abort("failed"))
        style_failure_page.goto(URL, wait_until="domcontentloaded")
        style_failure = wait_for_dark_fallback(style_failure_page)
        checks.append({
            "name": "real style request failure enables dark fallback",
            "passed": style_failure["unavailable"] and style_failure["vectorCanvasCount"] == 0,
        })
        style_failure_page.close()

        style_timeout_page = browser.new_page(viewport={"width": 1280, "height": 720})

        def delay_style_response(route):
            time.sleep(11)
            try:
                route.continue_()
            except Exception:
                pass

        style_timeout_page.route(STYLE_URL, delay_style_response)
        style_timeout_page.goto(URL, wait_until="domcontentloaded")
        style_timeout = wait_for_dark_fallback(style_timeout_page)
        checks.append({
            "name": "pending style request times out into dark fallback",
            "passed": style_timeout["unavailable"] and style_timeout["vectorCanvasCount"] == 0,
        })
        style_timeout_page.close()

        plugin_failure_page = browser.new_page(viewport={"width": 1280, "height": 720})
        plugin_failure_page.route(
            "**/static/vendor/maplibre-gl-leaflet/0.1.3/leaflet-maplibre-gl.js",
            lambda route: route.abort("failed"),
        )
        plugin_failure_page.goto(URL, wait_until="domcontentloaded")
        plugin_failure = wait_for_dark_fallback(plugin_failure_page)
        checks.append({
            "name": "self-hosted plugin load failure enables dark fallback",
            "passed": plugin_failure["unavailable"] and plugin_failure["vectorCanvasCount"] == 0,
        })
        plugin_failure_page.close()

        missing_layer_page = browser.new_page(viewport={"width": 1280, "height": 720})

        def fulfill_style_without_water(route):
            response = route.fetch()
            style = response.json()
            style["layers"] = [layer for layer in style.get("layers", []) if layer.get("id") != "water"]
            route.fulfill(status=200, content_type="application/json", body=json.dumps(style))

        missing_layer_page.route(STYLE_URL, fulfill_style_without_water)
        missing_layer_page.goto(URL, wait_until="domcontentloaded")
        missing_layer = wait_for_dark_fallback(missing_layer_page)
        checks.append({
            "name": "missing required upstream layer enables dark fallback",
            "passed": missing_layer["unavailable"] and missing_layer["vectorCanvasCount"] == 0,
        })
        missing_layer_page.close()

        runtime_failure_page = browser.new_page(viewport={"width": 1280, "height": 720})
        runtime_failure_page.goto(URL, wait_until="networkidle")
        wait_for_vector_basemap(runtime_failure_page)
        runtime_failure_page.route("https://tiles.openfreemap.org/**", lambda route: route.abort("failed"))
        runtime_failure_page.evaluate(
            "() => { window.__redlinePlayableMap.setView([-33.8688, 151.2093], 12, {animate:false}); return true; }"
        )
        runtime_failure = wait_for_dark_fallback(runtime_failure_page)
        checks.append({
            "name": "post-load tile failure removes vector canvas and enables dark fallback",
            "passed": runtime_failure["unavailable"] and runtime_failure["vectorCanvasCount"] == 0,
        })
        runtime_failure_page.close()
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
