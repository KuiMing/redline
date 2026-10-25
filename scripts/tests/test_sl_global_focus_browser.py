"""SL 全域地圖聚焦的 Browser（Playwright／Chromium）regression。

不啟動任何伺服器：以 page.route 在合成的 origin（http://redline.test）上提供兩個最小頁面——
parent 頁載入真實的 controller_core.js／living_room_core.js／controller_ui.js／controller_living_room.js，
戰略地圖 iframe 載入真實的 controller_core.js／controller_map_adapter.js 與 leaflet_game_map_logic.js 的
townDisplayLatLng，canonical 城鎮來自 data/map.json。Leaflet 換成可驗證的假地圖（不連 unpkg）；
bridge 是 mock WebSocket（不是實體 Joy-Con）。

驗證：沒有 pending choice 時 SL 也能開啟並列出全部 canonical 城鎮；選定城鎮後 iframe 精確置中並放大到固定層級，
不點任何按鈕、不觸發 marker click、不改遊戲狀態；剛好是合法目標的城鎮綁到既有目標焦點（Y 仍走既有建立流程）；
新的 pending choice 讓只看的瀏覽焦點交回地圖目標；客廳模式的 ring 不會被 reconcile 清掉；iframe ok:false 時 fail closed；
戰略地圖從未載入時 SL 先切到地圖、載入後自動開啟。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
ORIGIN = "http://redline.test"
MAP_TOWNS = json.loads((ROOT / "data" / "map.json").read_text(encoding="utf-8"))["towns"]
GEO = json.loads((ROOT / "data" / "map_geo_coordinates.v1.json").read_text(encoding="utf-8"))
DISPLAY_SRC = re.search(
    r"function townDisplayLatLng\(town\) \{[\s\S]*?\n\}\n",
    (STATIC / "leaflet_game_map_logic.js").read_text(encoding="utf-8"),
).group(0)
BIT = {"A": (0, 0x08), "B": (0, 0x04), "Y": (0, 0x01), "SL": (0, 0x20)}

MOCK_WS = """
(() => {
  const RealWS = window.WebSocket;
  window.__mockBridges = [];
  class MockBridge {
    constructor(url) {
      this.url = url; this.readyState = 0; this.onopen = this.onmessage = this.onclose = this.onerror = null;
      window.__mockBridges.push(this);
      setTimeout(() => { if (this.readyState === 0) { this.readyState = 1; this.onopen && this.onopen({}); } }, 20);
    }
    send() {}
    close() { if (this.readyState === 3) return; this.readyState = 3; setTimeout(() => this.onclose && this.onclose({}), 0); }
  }
  window.WebSocket = function (url, protocols) {
    if (String(url) === 'ws://127.0.0.1:8000/ws') return new MockBridge(url);
    return protocols === undefined ? new RealWS(url) : new RealWS(url, protocols);
  };
  Object.assign(window.WebSocket, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });
  window.__padLast = [0, 0, 0, 0];
  const emit = () => {
    const live = window.__mockBridges.filter(b => b.readyState === 1).pop();
    if (!live || !live.onmessage) return false;
    const [x, y, b0, b1] = window.__padLast;
    live.onmessage({ data: JSON.stringify({ x, y, buttons: [b0, b1] }) });
    return true;
  };
  window.__padSend = (x, y, b0, b1) => { window.__padLast = [x, y, b0, b1]; return emit(); };
  setInterval(emit, 33);
})();
"""

PARENT_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>sl</title>
<style>.game-view{display:none}.game-view.active{display:block}#strategicMapFrame{width:900px;height:560px;border:0}</style>
</head><body>
<div id="designStage" style="position:relative;width:1280px;height:720px">
  <div id="gameShell">
    <div id="gameTabs">
      <button class="game-tab active" data-view="command" type="button">指揮中心</button>
      <button class="game-tab" data-view="map" type="button">戰略地圖</button>
    </div>
    <div id="commandView" class="game-view active">
      <div id="handPanel"><div id="hand"><div class="card" data-card-zone="hand" data-card-name="測試牌" tabindex="0">測試牌</div></div></div>
    </div>
    <div id="mapView" class="game-view"><iframe id="strategicMapFrame" __SRC__></iframe></div>
  </div>
</div>
<script>
  // 與 app.js 的 setActiveGameView 相同：切分頁 class；戰略地圖第一次顯示時才掛載 iframe。
  document.querySelectorAll('.game-tab').forEach(tab => tab.addEventListener('click', () => {
    document.querySelectorAll('.game-tab').forEach(t => t.classList.toggle('active', t === tab));
    document.querySelectorAll('.game-view').forEach(v => v.classList.toggle('active', v.id === `${tab.dataset.view}View`));
    const frame = document.getElementById('strategicMapFrame');
    if (tab.dataset.view === 'map' && !frame.getAttribute('src')) frame.src = '/map.html';
  }));
</script>
<script src="/static/controller_core.js"></script>
<script src="/static/living_room_core.js"></script>
<script src="/static/controller_ui.js"></script>
<script src="/static/controller_living_room.js"></script>
</body></html>"""

MAP_HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;width:100%;height:100%}#map{width:100%;height:100%}</style></head><body>
<div id="map"></div>
<button id="directBuildBtn" type="button">建立組織</button>
<script>
window.__clicks = [];
window.__markerClicks = [];
window.__layers = [];
document.getElementById('directBuildBtn').addEventListener('click', () => window.__clicks.push('directBuildBtn'));
const MAP_DATA = __MAP_DATA__;
const GEO = __GEO__;
function latLng(lat, lng) { return { lat, lng, equals(o, m = 1e-9) { return !!o && Math.abs(o.lat - lat) <= m && Math.abs(o.lng - lng) <= m; } }; }
const point = (x, y) => ({ x, y });
const project = (ll, z) => point(((ll.lng + 180) / 360) * 256 * 2 ** z, ((90 - ll.lat) / 180) * 256 * 2 ** z);
const unproject = (p, z) => latLng(90 - (p.y / (256 * 2 ** z)) * 180, (p.x / (256 * 2 ** z)) * 360 - 180);
function group() { const g = { items: [], addTo() { return g; }, clearLayers() { g.items.length = 0; } }; window.__layers.push(g); return g; }
const L = {
  latLng, point, layerGroup: group, divIcon: () => ({}),
  circleMarker: (ll) => ({ addTo(g) { g.items.push({ kind: 'ring', lat: ll.lat, lng: ll.lng }); return this; } }),
  marker: (ll) => ({ addTo(g) { g.items.push({ kind: 'label', lat: ll.lat, lng: ll.lng }); return this; } }),
};
const container = document.getElementById('map');
const handlers = {};
const map = {
  _loaded: true, center: latLng(30, 110), zoom: 4, minZoom: 0, maxZoom: Infinity, setViews: 0, pans: 0,
  size: point(container.clientWidth, container.clientHeight),
  on(names, fn) { for (const n of names.split(' ')) (handlers[n] = handlers[n] || []).push(fn); return map; },
  getContainer: () => container,
  getMinZoom: () => map.minZoom,
  getMaxZoom: () => map.maxZoom,
  invalidateSize() { map.size = point(container.clientWidth, container.clientHeight); return map; },
  setView(ll, zoom) {
    map.setViews += 1;
    map.center = latLng(ll.lat, ll.lng);
    map.zoom = Math.max(map.minZoom, Math.min(map.maxZoom, zoom));
    (handlers.zoomend || []).forEach(f => f());
    (handlers.moveend || []).forEach(f => f());
    return map;
  },
  getCenter: () => latLng(map.center.lat, map.center.lng),
  getZoom: () => map.zoom,
  getSize: () => point(map.size.x, map.size.y),
  latLngToContainerPoint(ll) {
    const p = project(ll, map.zoom); const c = project(map.center, map.zoom);
    return point(p.x - c.x + map.size.x / 2, p.y - c.y + map.size.y / 2);
  },
  latLngToLayerPoint(ll) { return map.latLngToContainerPoint(ll); },
  layerPointToLatLng(p) {
    const c = project(map.center, map.zoom);
    return unproject(point(p.x + c.x - map.size.x / 2, p.y + c.y - map.size.y / 2), map.zoom);
  },
  getBounds: () => ({ pad: () => ({ contains(ll) {
    const p = map.latLngToContainerPoint(ll);
    return p.x >= map.size.x * 0.1 && p.x <= map.size.x * 0.9 && p.y >= map.size.y * 0.1 && p.y <= map.size.y * 0.9;
  } }) }),
  panInside() { map.pans += 1; },
};
let towns = Object.entries(MAP_DATA).map(([name, raw]) => ({ name, ...raw, lon: GEO[name][0], lat: GEO[name][1] }));
let byName = new Map(towns.map(t => [t.name, t]));
let lastGameState = { map: { towns: {} }, players: [{ id: 'p1', name: 'A' }] };
let mapPlayerId = 'p1';
let supportChoiceHighlight = null;
let currentVisible = towns.map(t => t.name);
let selectedTown = null;
let selectedMoveTargets = [];
let pendingMoveTarget = null;
const currentMarkers = new Map(towns.map(t => [t.name, { fire() { window.__markerClicks.push(t.name); if (supportChoiceHighlight) selectedTown = t.name; } }]));
function currentPlayerName() { return 'B'; }
function canActFromTown() { return false; }
function sharedDissolveTargetForTown() { return null; }
function markerRadius() { return 8; }
function escapeHtml(s) { return String(s); }
function exitMovementSelection() { window.__clicks.push('exitMovementSelection'); selectedTown = null; }
function applySupportChoiceHighlight(payload) { supportChoiceHighlight = payload || null; selectedTown = null; }
function applyGameStateToMap() {}
__DISPLAY_SRC__
window.__mapProbe = (name) => {
  const town = byName.get(name);
  const p = map.latLngToContainerPoint(townDisplayLatLng(town));
  const ring = window.__layers.flatMap(g => g.items).filter(i => i.kind === 'ring');
  const at = townDisplayLatLng(town);
  return {
    zoom: map.getZoom(), dx: p.x - map.size.x / 2, dy: p.y - map.size.y / 2, setViews: map.setViews, pans: map.pans,
    ringAtTown: ring.length > 0 && ring.every(r => Math.abs(r.lat - at.lat) < 1e-9 && Math.abs(r.lng - at.lng) < 1e-9),
    clicks: [...window.__clicks], markerClicks: [...window.__markerClicks], state: JSON.stringify(lastGameState),
  };
};
window.__setChoice = (names) => {
  applySupportChoiceHighlight(names ? { mode: 'support-targets', actionKind: 'build', towns: names.map(town => ({ town })) } : null);
};
</script>
<script src="/static/controller_core.js"></script>
<script src="/static/controller_map_adapter.js"></script>
</body></html>"""


@pytest.fixture(scope="module")
def browser():
    with playwright_sync.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def open_page(browser, *, mounted=True):
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    map_html = (MAP_HTML.replace("__MAP_DATA__", json.dumps(MAP_TOWNS, ensure_ascii=False))
                .replace("__GEO__", json.dumps(GEO, ensure_ascii=False)).replace("__DISPLAY_SRC__", DISPLAY_SRC))
    parent_html = PARENT_HTML.replace("__SRC__", 'src="/map.html"' if mounted else "")

    def handle(route):
        path = route.request.url[len(ORIGIN):].split("?", 1)[0]
        if path == "/game.html":
            return route.fulfill(body=parent_html, content_type="text/html; charset=utf-8")
        if path == "/map.html":
            return route.fulfill(body=map_html, content_type="text/html; charset=utf-8")
        if path.startswith("/static/") and (STATIC / path[len("/static/"):]).is_file():
            return route.fulfill(path=str(STATIC / path[len("/static/"):]))
        return route.fulfill(status=404, body="")

    context.route(f"{ORIGIN}/**", handle)
    context.add_init_script(MOCK_WS)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{ORIGIN}/game.html")
    page.wait_for_function("!!window.RedlineController && !!window.RedlineDisplayMode")
    if mounted:
        # iframe 可能比 parent 的 controller 腳本先載入（真實 app 只在切到戰略地圖時才掛載）：載入後再推一份 snapshot。
        frame_of(page).wait_for_function("!!window.__redlineControllerAdapter")
        frame_of(page).evaluate("applyGameStateToMap()")
        page.wait_for_timeout(100)
    page.evaluate("RedlineController.setEnabled(true)")
    page.wait_for_function("RedlineController.getState().status === 'connected'")
    # 連線（或換手把）後的第一筆 frame 只當 baseline：先送一筆放開的 frame，之後的按鍵才是「按下」。
    page.evaluate("() => window.__padSend(0, 0, 0, 0)")
    page.wait_for_timeout(100)
    page.__errors = errors
    return page


def frame_of(page):
    return page.query_selector("#strategicMapFrame").content_frame()


def tap(page, name):
    i, m = BIT[name]
    b = [0, 0]
    b[i] |= m
    page.evaluate("([b0, b1]) => window.__padSend(0, 0, b0, b1)", b)
    page.wait_for_timeout(40)
    page.evaluate("() => window.__padSend(0, 0, 0, 0)")
    page.wait_for_timeout(140)


def state(page):
    return page.evaluate("RedlineController.getState()")


def gate(page):
    s = state(page)
    return s["livingRoom"] or s["shortcuts"] or {}


def menu_open(page):
    return page.evaluate("(() => { const m = document.getElementById('lrFocusMenu'); return !!m && m.style.display !== 'none'; })()")


def open_menu(page):
    tap(page, "SL")
    page.wait_for_function("(() => { const m = document.getElementById('lrFocusMenu'); return !!m && m.style.display !== 'none'; })()")
    page.wait_for_timeout(280)  # 開啟後 250ms 執行冷卻


def pick(page, element_id):
    assert page.evaluate("(id) => RedlineController.focusElement(id)", element_id), element_id
    tap(page, "A")
    page.wait_for_timeout(280)  # 換層後 250ms 執行冷卻


def probe(page, town):
    return frame_of(page).evaluate("(t) => window.__mapProbe(t)", town)


def wait_ack(page, outcome="success"):
    page.wait_for_function(
        "(o) => { const s = RedlineController.getState(); const g = s.livingRoom || s.shortcuts || {};"
        " return !!g.lastMapAck && g.lastMapAck.cmd === 'focusTown' && g.lastMapAck.outcome === o; }", arg=outcome)


def group_keys(kind):
    names = set()
    for raw in MAP_TOWNS.values():
        names.update(raw.get(kind) or [])
    return names


def test_desktop_sl_without_pending_choice_lists_all_towns_and_centers_exactly(browser):
    page = open_page(browser)
    before = probe(page, "曼谷")
    tap(page, "A")  # 第一下只放焦點（手牌）
    open_menu(page)
    title = page.text_content("#lrFocusMenuTitle")
    assert f"{len(MAP_TOWNS)} 座" in title, title
    keys = page.eval_on_selector_all("#lrFocusMenu .lr-focus-option", "els => els.map(e => e.dataset.key)")
    assert set(keys) == {f"ruler:{n}" for n in group_keys("ruler")} | {f"camp:{n}" for n in group_keys("camp")}
    pick(page, "lrFocusOpt-ruler-南洋")
    assert "南洋" in page.text_content("#lrFocusMenuTitle")
    towns = page.eval_on_selector_all("#lrFocusMenu .lr-focus-town", "els => els.map(e => e.dataset.town)")
    assert set(towns) == {t for t, raw in MAP_TOWNS.items() if "南洋" in (raw.get("ruler") or [])}
    assert page.evaluate("document.querySelector('#lrFocusMenu .rl-pad-focus').dataset.town") == towns[0], "town level focuses its first town"
    assert page.eval_on_selector_all("#lrFocusMenu .lr-focus-town[data-target]", "els => els.length") == 0, "no targets to tag"
    pick(page, "lrFocusTown-曼谷")
    wait_ack(page)
    assert not menu_open(page)
    assert page.evaluate("document.querySelector('.game-tab.active').dataset.view") == "map", "switched with the existing tab"
    s = state(page)
    assert (s["focusKind"], s["focusTown"], s["scope"]) == ("browse", "曼谷", "map")
    after = probe(page, "曼谷")
    assert after["zoom"] == 9
    assert abs(after["dx"]) <= 1 and abs(after["dy"]) <= 1, after
    assert after["ringAtTown"]
    assert (after["clicks"], after["markerClicks"], after["pans"]) == ([], [], 0)
    assert after["state"] == before["state"], "authoritative game state untouched"
    # 之後的 reconcile 不會把 ring 清掉；只看的瀏覽焦點上 A 不作用。
    page.wait_for_timeout(300)
    tap(page, "A")
    s = state(page)
    assert (s["focusKind"], s["focusTown"]) == ("browse", "曼谷")
    later = probe(page, "曼谷")
    assert later["ringAtTown"] and (later["clicks"], later["markerClicks"]) == ([], [])
    assert page.__errors == []


def test_desktop_sl_target_town_keeps_existing_y_path_and_new_choice_reclaims_browse_focus(browser):
    page = open_page(browser)
    frame_of(page).evaluate("window.__setChoice(['新北', '基隆'])")
    page.click(".game-tab[data-view='map']")
    page.wait_for_timeout(200)
    tap(page, "A")  # 第一下只放焦點（地圖目標）
    open_menu(page)
    pick(page, "lrFocusOpt-ruler-臺灣")
    tagged = page.eval_on_selector_all("#lrFocusMenu .lr-focus-town[data-target='true']", "els => els.map(e => e.dataset.town)")
    assert sorted(tagged) == sorted(["新北", "基隆"])
    pans = probe(page, "基隆")["pans"]  # 第一下 A 放到既有目標時的 panInside 已算在內
    pick(page, "lrFocusTown-基隆")
    wait_ack(page)
    page.wait_for_timeout(200)
    s = state(page)
    assert (s["focusKind"], s["focusSig"]) == ("map", "town:基隆"), "a legal target binds to the existing target focus"
    p = probe(page, "基隆")
    assert p["zoom"] == 9 and abs(p["dx"]) <= 1 and abs(p["dy"]) <= 1 and p["pans"] == pans, p
    assert (p["clicks"], p["markerClicks"]) == ([], []), "focusing itself selects / builds nothing"
    page.wait_for_timeout(280)
    tap(page, "Y")  # 既有地圖操作：iframe act → marker click → directBuildBtn
    frame_of(page).wait_for_function("window.__clicks.includes('directBuildBtn')")
    assert probe(page, "基隆")["markerClicks"] == ["基隆"]
    # 瀏覽到非目標城鎮，之後換了一份 pending choice：瀏覽焦點交回地圖目標。
    frame_of(page).evaluate("window.__setChoice(['新北', '基隆'])")
    page.wait_for_timeout(300)
    open_menu(page)
    pick(page, "lrFocusOpt-ruler-南洋")
    pick(page, "lrFocusTown-曼谷")
    page.wait_for_function("RedlineController.getState().focusKind === 'browse'")
    frame_of(page).evaluate("window.__setChoice(['臺北'])")
    page.wait_for_function("(() => { const s = RedlineController.getState(); return s.focusKind === 'map' && s.focusSig === 'town:臺北'; })()")
    assert page.__errors == []


def test_sl_focus_uses_the_whole_leaflet_max_zoom_when_it_is_below_9(browser):
    page = open_page(browser)
    frame_of(page).evaluate("map.maxZoom = 7.5")  # 低於固定聚焦層級 9 → 取合法的最大整數層級 7
    tap(page, "A")
    open_menu(page)
    pick(page, "lrFocusOpt-ruler-南洋")
    pick(page, "lrFocusTown-曼谷")
    wait_ack(page)
    s = state(page)
    assert (s["focusKind"], s["focusTown"]) == ("browse", "曼谷")
    p = probe(page, "曼谷")
    assert p["zoom"] == 7 and abs(p["dx"]) <= 1 and abs(p["dy"]) <= 1, p
    assert (p["clicks"], p["markerClicks"]) == ([], [])
    assert page.__errors == []


def test_sl_focus_fails_closed_when_the_iframe_refuses(browser):
    page = open_page(browser)
    frame_of(page).evaluate("map.minZoom = 10")  # 聚焦層級（9）無法滿足 → iframe ok:false zoom-unavailable
    tap(page, "A")
    open_menu(page)
    pick(page, "lrFocusOpt-ruler-南洋")
    pick(page, "lrFocusTown-曼谷")
    wait_ack(page, "failed")
    s = state(page)
    assert s["focusKind"] != "browse"
    assert s["shortcuts"]["notice"] == "地圖無法聚焦這座城鎮"
    p = probe(page, "曼谷")
    assert (p["setViews"], p["clicks"], p["markerClicks"]) == (0, [], []), "camera never moved"
    assert not p["ringAtTown"]
    assert page.__errors == []


def test_sl_before_the_map_ever_loaded_switches_to_the_map_and_opens_when_ready(browser):
    page = open_page(browser, mounted=False)
    tap(page, "A")
    tap(page, "SL")
    page.wait_for_function("(() => { const m = document.getElementById('lrFocusMenu'); return !!m && m.style.display !== 'none'; })()", timeout=5000)
    assert page.evaluate("document.querySelector('.game-tab.active').dataset.view") == "map"
    assert f"{len(MAP_TOWNS)} 座" in page.text_content("#lrFocusMenuTitle")
    tap(page, "B")  # B 關閉
    assert not menu_open(page)
    assert page.__errors == []
