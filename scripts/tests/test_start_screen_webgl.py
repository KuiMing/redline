"""開始畫面「戰時指揮中心」WebGL2 特效：靜態契約＋Browser（Playwright／Chromium）驗證。

Browser 測試使用 swiftshader 軟體 WebGL2；若環境沒有 Chromium 或 WebGL2 會 skip（靜態測試仍會跑）。
"""
from __future__ import annotations

import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
FX_JS = (STATIC / "start_screen_fx.js").read_text(encoding="utf-8")
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "style.css").read_text(encoding="utf-8")
ENTRY = '#lobby[data-flow="start"][data-start-step="entry"]'
KEY = "redline.startFx.v1"


# ------------------------------------------------------------------ 靜態契約
def test_no_external_dependencies_or_media():
    assert not re.search(r"https?://|//cdn|unpkg|import\s+|require\(|fetch\(|XMLHttpRequest|WebSocket", FX_JS)
    assert not re.search(r"\b(three|pixi|babylon|regl|twgl)\b", FX_JS, re.I)
    assert 'src="/static/start_screen_fx.js' in HTML
    fx_html = HTML[HTML.index('id="sfFx"'): HTML.index('id="sfSetup"')]
    assert not re.search(r"<(video|img|iframe)|\.gif|\.mp4|\.webm|https?://", fx_html)


def test_native_webgl2_shaders_cover_required_effects():
    assert "getContext('webgl2'" in FX_JS and "#version 300 es" in FX_JS
    for needle in ("fbm", "SPARK_LAYERS", "RADAR_C", "ISLAND", "uMouse", "uPar", "atan(rp.y, rp.x)"):
        assert needle in FX_JS
    # 雷達中心在台灣（設計座標約 x 870–950、y 335–470）
    cx, cy = map(float, re.search(r"RADAR_C = vec2\(([\d.]+), ([\d.]+)\)", FX_JS).groups())
    assert 880 < cx < 940 and 360 < cy < 440


def test_entry_ids_and_controls_preserved_with_labels():
    for i in ("sfCreateHuman", "sfCreateAi", "sfRoomCode", "sfJoinBtn", "sfJoinError"):
        assert HTML.count(f'id="{i}"') == 1
    assert 'id="sfFxMotion"' in HTML and 'role="switch"' in HTML and "動態效果" in HTML
    assert 'aria-label="渲染畫質"' in HTML and 'data-sf-fx-quality="low"' in HTML and 'data-sf-fx-quality="high"' in HTML
    assert 'id="sfFxStatus"' in HTML and 'aria-live="polite"' in HTML
    assert '<fieldset class="sf-path-join" aria-labelledby="sfJoinTitle">' in HTML
    assert '<legend id="sfJoinTitle">加入現有房間</legend>' in HTML
    assert "<select" not in HTML[HTML.index('id="sfFx"'): HTML.index('id="sfSetup"')]  # 既有測試要求入口沒有 select


def test_fx_controls_do_not_take_over_joycon_entry_focus():
    controls = HTML[HTML.index('class="sf-fx-controls"'): HTML.index('id="sfFxStatus"')]
    assert controls.count("data-controller-skip") == 3
    motion_match = re.search(r'<button[^>]*id="sfFxMotion"[^>]*>', controls)
    assert motion_match and "data-controller-skip" in motion_match.group(0)
    for entry_id in ("sfCreateHuman", "sfCreateAi", "sfJoinBtn"):
        entry_match = re.search(rf'<button[^>]*id="{entry_id}"[^>]*>', HTML)
        assert entry_match and "data-controller-skip" not in entry_match.group(0)


def test_fallback_reduced_motion_storage_and_lifecycle_present():
    assert "localStorage" in FX_JS and KEY in FX_JS
    assert "prefers-reduced-motion" in FX_JS and "typeof stored.motion === 'boolean'" in FX_JS
    assert "webglcontextlost" in FX_JS and "webglcontextrestored" in FX_JS and "preventDefault" in FX_JS
    assert "fallback" in FX_JS and "cancelAnimationFrame" in FX_JS and "visibilitychange" in FX_JS


def test_low_quality_really_reduces_load():
    q = {m.group(1): tuple(map(float, m.groups()[1:])) for m in re.finditer(r"(low|high): \{ res: ([\d.]+), octaves: (\d+), sparks: (\d+) \}", FX_JS)}
    assert q["low"][0] < q["high"][0] and q["low"][1] < q["high"][1] and q["low"][2] < q["high"][2]
    assert "MAX_RENDER_SCALE = 1.5" in FX_JS
    assert "TARGET_FRAME_MS = 1000 / 60" in FX_JS


def test_css_is_scoped_to_entry_step():
    start = CSS.index("戰時指揮中心入口")
    block = CSS[start:CSS.index("客廳大螢幕模式")]
    selectors = [s.strip() for chunk in re.findall(r"([^{}]+)\{", block) for s in chunk.split(",")]
    for sel in selectors:
        sel = sel.strip()
        if not sel or sel.startswith(("@", "/*", "*/")) or "：" in sel:
            continue
        assert sel.startswith(ENTRY) or sel in (".sf-fx", ".sf-fx-controls"), sel


def test_protected_files_untouched():
    out = subprocess.run(["git", "status", "--porcelain", "--", "static/card-art", "docs/PLAYER_GUIDE.md", "docs/PLAYER_GUIDE.pdf"],
                         cwd=ROOT, capture_output=True, text=True).stdout
    assert out.strip() == ""


# ------------------------------------------------------------------ Browser
def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def app_url():
    port = _free_port()
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "error"], cwd=ROOT)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if requests.get(url + "/", timeout=1).ok:
                break
        except requests.RequestException:
            time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("server did not start")
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"chromium unavailable: {exc}")
        yield b
        b.close()


def open_page(browser, url, *, init=None, viewport=(1280, 720), reduced=None):
    kw = {"viewport": {"width": viewport[0], "height": viewport[1]}}
    if reduced:
        kw["reduced_motion"] = "reduce"
    ctx = browser.new_context(**kw)
    if init:
        ctx.add_init_script(init)
    page = ctx.new_page()
    page.goto(url + "/")
    page.wait_for_selector("#sfCreateHuman")
    if "getContext = () => null" not in (init or ""):
        page.wait_for_function("window.RedlineStartFx && window.RedlineStartFx.getState().mode !== 'pending'", timeout=5000)
    return page


def need_webgl2(page):
    if page.evaluate("document.createElement('canvas').getContext('webgl2') === null"):
        pytest.skip("WebGL2 unavailable in this Chromium")


def fx(page):
    return page.evaluate("window.RedlineStartFx.getState()")


def test_default_runs_animation_and_buttons_stay_clickable_in_three_viewports(browser, app_url):
    for vp in ((1280, 720), (1440, 900), (1920, 1080)):
        page = open_page(browser, app_url, viewport=vp)
        need_webgl2(page)
        page.wait_for_function("window.RedlineStartFx.getState().frames > 3")
        s = fx(page)
        assert s["motion"] and s["rafActive"] and s["mode"] == "animated" and not s["failed"]
        stage = page.evaluate("(() => { const r = document.getElementById('designStage').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
        for sel in ("#sfCreateHuman", "#sfCreateAi", ".sf-path-join", "#sfFxMotion", ".sf-fx-quality"):
            b = page.locator(sel).bounding_box()
            assert stage[0] - 1 <= b["x"] and b["x"] + b["width"] <= stage[0] + stage[2] + 1, (vp, sel)
            assert stage[1] - 1 <= b["y"] and b["y"] + b["height"] <= stage[1] + stage[3] + 1, (vp, sel)
        # 控制不與三個入口重疊
        c = page.locator(".sf-fx-controls").bounding_box()
        for sel in ("#sfCreateHuman", "#sfCreateAi", ".sf-path-join"):
            b = page.locator(sel).bounding_box()
            assert c["y"] + c["height"] < b["y"]
        # 滑鼠移到按鈕中心後，最上層元素仍是該按鈕（canvas 不攔截）
        for sel in ("#sfCreateHuman", "#sfCreateAi", "#sfJoinBtn"):
            b = page.locator(sel).bounding_box()
            page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
            assert page.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return document.querySelector(s).contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)); }", sel)
        page.context.close()


def test_motion_toggle_stops_raf_persists_and_low_quality_lowers_resolution(browser, app_url):
    page = open_page(browser, app_url)
    need_webgl2(page)
    high = fx(page)
    page.click("#sfFxMotion")
    s = fx(page)
    assert s["motion"] is False and s["rafActive"] is False and s["mode"] == "static"
    frames = s["frames"]
    page.wait_for_timeout(400)
    assert fx(page)["frames"] == frames  # 停止後不再繪製
    assert page.get_attribute("#sfFxMotion", "aria-checked") == "false"
    page.click('[data-sf-fx-quality="low"]')
    low = fx(page)
    assert low["quality"] == "low" and low["renderWidth"] < high["renderWidth"] and low["config"]["octaves"] < high["config"]["octaves"]
    assert page.locator("#sfFxStatus").inner_text() == ""  # 按鈕狀態已足夠，不顯示重複畫質文字
    stored = page.evaluate(f"JSON.parse(localStorage.getItem('{KEY}'))")
    assert stored == {"motion": False, "quality": "low"}
    page.reload()
    page.wait_for_selector("#sfCreateHuman")
    page.wait_for_function("window.RedlineStartFx.getState().mode === 'static'")
    s = fx(page)
    assert s["motion"] is False and s["quality"] == "low" and not s["rafActive"]
    # 鍵盤可操作：聚焦後按 Space 重新開啟動態
    page.focus("#sfFxMotion")
    page.keyboard.press("Space")
    assert fx(page)["motion"] is True
    page.context.close()


def test_reduced_motion_defaults_off_but_explicit_setting_wins(browser, app_url):
    page = open_page(browser, app_url, reduced=True)
    need_webgl2(page)
    s = fx(page)
    assert s["motion"] is False and s["rafActive"] is False and s["mode"] == "static"
    page.click("#sfFxMotion")
    assert fx(page)["motion"] is True
    page.reload()
    page.wait_for_selector("#sfCreateHuman")
    page.wait_for_function("window.RedlineStartFx.getState().mode === 'animated'")
    page.context.close()


def test_setup_step_stops_loop_and_returns(browser, app_url):
    page = open_page(browser, app_url)
    need_webgl2(page)
    page.click("#sfCreateHuman")
    page.wait_for_selector("#sfSetup", state="visible")
    page.wait_for_function("!window.RedlineStartFx.getState().rafActive")
    assert not page.locator("#sfFxCanvas").is_visible()
    assert not page.locator(".sf-fx-controls").is_visible()
    page.click("#sfBackToEntry")
    page.wait_for_function("window.RedlineStartFx.getState().rafActive")
    page.context.close()


def test_no_webgl2_falls_back_and_entries_still_work(browser, app_url):
    init = "HTMLCanvasElement.prototype.getContext = () => null;"
    page = open_page(browser, app_url, init=init)
    page.wait_for_function("window.RedlineStartFx.getState().failed")
    assert fx(page)["mode"] == "fallback" and not fx(page)["rafActive"]
    assert page.is_visible("#sfFxStatus")
    page.fill("#sfRoomCode", "")
    page.click("#sfJoinBtn")
    assert page.inner_text("#sfJoinError").strip() != ""  # 既有流程仍可運作
    page.click("#sfCreateAi")
    page.wait_for_selector("#sfSetup", state="visible")
    page.context.close()


def test_context_lost_falls_back_without_breaking_entries(browser, app_url):
    page = open_page(browser, app_url)
    need_webgl2(page)
    page.evaluate("document.getElementById('sfFxCanvas').getContext('webgl2').getExtension('WEBGL_lose_context').loseContext()")
    page.wait_for_function("window.RedlineStartFx.getState().lost")
    assert fx(page)["mode"] == "fallback" and not fx(page)["rafActive"]
    page.click("#sfCreateHuman")
    page.wait_for_selector("#sfSetup", state="visible")
    page.context.close()
