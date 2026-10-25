// node --test scripts/tests/js/controller_map_adapter.test.js
// 戰略地圖 iframe 端 controller adapter（static/controller_map_adapter.js）的 SL 全域地圖聚焦：
// 以 vm 載入真實 adapter、真實 townDisplayLatLng 與 canonical data/map.json，Leaflet 換成可驗證的假地圖。
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const C = require('../../../static/controller_core.js');
const LR = require('../../../static/living_room_core.js');

const ROOT = path.join(__dirname, '../../..');
const ADAPTER_SRC = fs.readFileSync(path.join(ROOT, 'static/controller_map_adapter.js'), 'utf8');
const MAP_LOGIC = fs.readFileSync(path.join(ROOT, 'static/leaflet_game_map_logic.js'), 'utf8');
const DISPLAY_SRC = MAP_LOGIC.match(/function townDisplayLatLng\(town\) \{[\s\S]*?\n\}\n/)[0];
const MAP_DATA = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/map.json'), 'utf8'));
const GEO = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/map_geo_coordinates.v1.json'), 'utf8'));
const ORIGIN = 'http://redline.test';
const SIZE = { x: 800, y: 600 };

function latLng(lat, lng) {
  return {
    lat, lng,
    equals(o, margin = 1e-9) { return !!o && Math.abs(o.lat - lat) <= margin && Math.abs(o.lng - lng) <= margin; },
  };
}
const point = (x, y) => ({ x, y });
// 等距圓柱投影（256px × 2^zoom）：只需要可逆、與層級相關，足以驗證置中與依層級的像素偏移。
const project = (ll, zoom) => point(((ll.lng + 180) / 360) * 256 * 2 ** zoom, ((90 - ll.lat) / 180) * 256 * 2 ** zoom);
const unproject = (p, zoom) => latLng(90 - (p.y / (256 * 2 ** zoom)) * 180, (p.x / (256 * 2 ** zoom)) * 360 - 180);

function fakeMap({ minZoom = 0, maxZoom = Infinity, visible = true } = {}) {
  const handlers = {};
  const m = {
    _loaded: true, center: latLng(30, 110), zoom: 4, minZoom, maxZoom, setViews: [], pans: 0, invalidations: 0,
    container: { isConnected: true, clientWidth: visible ? SIZE.x : 0, clientHeight: visible ? SIZE.y : 0, getClientRects: () => (visible ? [1] : []) },
    on(names, fn) { for (const n of names.split(' ')) (handlers[n] = handlers[n] || []).push(fn); return m; },
    fire(name) { (handlers[name] || []).forEach(fn => fn()); },
    getContainer: () => m.container,
    getMinZoom: () => m.minZoom,
    getMaxZoom: () => m.maxZoom,
    invalidateSize() { m.invalidations += 1; return m; },
    setView(ll, zoom) {
      m.setViews.push({ lat: ll.lat, lng: ll.lng, zoom });
      m.center = latLng(ll.lat, ll.lng);
      m.zoom = Math.max(m.minZoom, Math.min(m.maxZoom, zoom));
      m.fire('zoomend');
      m.fire('moveend');
      return m;
    },
    getCenter: () => latLng(m.center.lat, m.center.lng),
    getZoom: () => m.zoom,
    getSize: () => point(SIZE.x, SIZE.y),
    latLngToContainerPoint(ll) {
      const p = project(ll, m.zoom);
      const c = project(m.center, m.zoom);
      return point(p.x - c.x + SIZE.x / 2, p.y - c.y + SIZE.y / 2);
    },
    latLngToLayerPoint(ll) { return m.latLngToContainerPoint(ll); },
    layerPointToLatLng(p) {
      const c = project(m.center, m.zoom);
      return unproject(point(p.x + c.x - SIZE.x / 2, p.y + c.y - SIZE.y / 2), m.zoom);
    },
    getBounds: () => ({ pad: () => ({ contains: () => true }) }),
    panInside() { m.pans += 1; },
  };
  return m;
}

const layer = () => ({ addTo() { return this; }, clearLayers() {} });

/** 載入真實 adapter。opts.choice＝pending choice 的地圖候選；opts.origins＝可行動來源（沒有＝不是自己的回合）。 */
function loadAdapter(opts = {}) {
  const map = fakeMap(opts.map);
  const towns = Object.entries(opts.mapData || MAP_DATA.towns).map(([name, raw]) => {
    const c = GEO[name];
    return { name, ...raw, lon: c[0], lat: c[1] };
  });
  const byName = new Map(towns.map(t => [t.name, t]));
  const clicks = [];
  const markerClicks = [];
  const parentMessages = [];
  const listeners = {};
  const buttons = new Map(C.MAP_BUTTON_IDS.map(id => [id, {
    id, disabled: false, isConnected: true, textContent: id,
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 10, height: 10 }), getClientRects: () => [1],
    click() { clicks.push(id); },
  }]));
  // postMessage 會 structured-clone：測試端同樣複製一份（也避開 vm realm 之間的原型差異）。
  const parent = { postMessage(message, origin) { parentMessages.push({ message: JSON.parse(JSON.stringify(message)), origin }); } };
  const L = {
    latLng, point,
    layerGroup: layer, circleMarker: () => layer(), marker: () => layer(), divIcon: () => ({}),
  };
  const ctx = {
    L, map, towns, byName, Core: undefined,
    lastGameState: { map: { towns: {} }, players: [{ id: 'p1', name: 'A' }] },
    mapPlayerId: 'p1',
    currentPlayerName: () => (opts.origins ? 'A' : 'B'),
    supportChoiceHighlight: opts.choice ? { mode: 'support-targets', actionKind: 'build', towns: opts.choice.map(town => ({ town })) } : null,
    currentVisible: towns.map(t => t.name),
    canActFromTown: name => (opts.origins || []).includes(name),
    sharedDissolveTargetForTown: () => null,
    selectedTown: null, selectedMoveTargets: [], pendingMoveTarget: null,
    currentMarkers: new Map(towns.map(t => [t.name, { fire: (ev) => markerClicks.push([t.name, ev]) }])),
    markerRadius: () => 8,
    escapeHtml: s => String(s),
    exitMovementSelection: () => clicks.push('exitMovementSelection'),
    getComputedStyle: () => ({ visibility: 'visible' }),
    setTimeout: (fn) => { fn(); return 1; },
    console,
    document: {
      hidden: false,
      getElementById: id => (id === 'map' ? { getBoundingClientRect: () => ({ left: 0, top: 0 }) } : buttons.get(id) || null),
    },
  };
  ctx.window = ctx;
  ctx.globalThis = ctx;
  ctx.window.parent = parent;
  ctx.window.location = { origin: ORIGIN };
  ctx.window.RedlineControllerCore = C;
  ctx.window.addEventListener = (type, fn) => { (listeners[type] = listeners[type] || []).push(fn); };
  vm.createContext(ctx);
  vm.runInContext(`${DISPLAY_SRC}\nthis.townDisplayLatLng = townDisplayLatLng;`, ctx);
  vm.runInContext(ADAPTER_SRC, ctx);
  const send = (data, source = parent) => {
    parentMessages.length = 0;
    for (const fn of listeners.message || []) fn({ origin: ORIGIN, source, data: { type: 'redline-controller-command', v: 1, ...data } });
    return {
      result: parentMessages.map(m => m.message).find(m => m.type === 'redline-controller-result') || null,
      snapshot: parentMessages.map(m => m.message).find(m => m.type === 'redline-controller-map-snapshot') || null,
    };
  };
  const centered = (town) => {
    const p = map.latLngToContainerPoint(ctx.townDisplayLatLng(byName.get(town)));
    return Math.abs(p.x - SIZE.x / 2) <= 1 && Math.abs(p.y - SIZE.y / 2) <= 1;
  };
  return { ctx, map, byName, clicks, markerClicks, send, centered, parent };
}

const canonicalNames = Object.keys(MAP_DATA.towns);

test('no pending choice: the snapshot still carries every canonical town, grouped data intact and separate from targets', () => {
  const a = loadAdapter();
  const { snapshot } = a.send({ cmd: 'snapshot', req: 3 });
  assert.equal(snapshot.scope, 'none');
  assert.deepEqual(snapshot.targets, [], 'not my turn, no pending choice: no action targets at all');
  assert.equal(snapshot.req, 3);
  const snap = C.sanitizeMapSnapshot(snapshot);
  assert.ok(snap, 'the parent sanitizer accepts the real canonical list');
  assert.equal(snap.browseMeta, C.MAP_BROWSE_META_VERSION);
  assert.deepEqual(snap.browseTowns.map(t => t.town).sort(), [...canonicalNames].sort());
  for (const t of snap.browseTowns) {
    assert.deepEqual(t.ruler, [...new Set(MAP_DATA.towns[t.town].ruler)], t.town);
    assert.deepEqual(t.camp, [...new Set(MAP_DATA.towns[t.town].camp)], t.town);
  }
  const menu = LR.buildFocusMenu(snap);
  assert.equal(menu.ok, true);
  assert.equal(menu.total, canonicalNames.length);
  assert.deepEqual(menu.targets, []);
});

test('focusTown centers a non-target canonical town exactly at the fixed zoom and triggers no action', () => {
  const a = loadAdapter({ origins: ['北京'] });
  const before = JSON.stringify(a.ctx.lastGameState);
  const { result, snapshot } = a.send({ cmd: 'focusTown', town: '曼谷', req: 7 });
  assert.deepEqual(result, { type: 'redline-controller-result', v: 1, cmd: 'focusTown', req: 7, ok: true, reason: null, via: null });
  assert.equal(a.map.getZoom(), C.MAP_FOCUS_ZOOM);
  assert.equal(a.map.getZoom(), 9);
  assert.ok(a.map.getCenter().equals(latLng(GEO['曼谷'][1], GEO['曼谷'][0])), 'exact center, not just panned inside the bounds');
  assert.ok(a.centered('曼谷'));
  assert.equal(a.map.pans, 0, 'no panInside');
  assert.deepEqual(a.clicks, [], 'no existing button pressed, selection not exited');
  assert.deepEqual(a.markerClicks, [], 'no marker click (no selection / pending move / choice resolution)');
  assert.equal(JSON.stringify(a.ctx.lastGameState), before, 'authoritative game state untouched');
  assert.equal(a.ctx.selectedTown, null);
  assert.equal(a.ctx.pendingMoveTarget, null);
  assert.deepEqual(snapshot.targets.map(t => [t.town, t.role]), [['北京', 'origin']], 'action targets unchanged by focusing');
  assert.equal(snapshot.focusTown, null, 'a browse town is never reported as the action focus');
});

test('思想家 global targets: focusTown 利雅德 at the focus zoom keeps a snapshot the parent accepts, with the same action targets', () => {
  // 無視距離建立（思想家）的候選：沒有陣營標籤的城鎮（含北美）＋維吾爾陣營城鎮，扣掉已有組織的根據地伊斯坦堡。
  const choice = canonicalNames.filter(n => n !== '伊斯坦堡'
    && (!(MAP_DATA.towns[n].camp || []).length || MAP_DATA.towns[n].camp.includes('維吾爾')));
  assert.ok(choice.includes('利雅德') && choice.includes('溫哥華') && choice.includes('奧克蘭'), 'fixture spans the whole map');
  const a = loadAdapter({ choice });
  const before = C.sanitizeMapSnapshot(a.send({ cmd: 'snapshot', req: 1 }).snapshot);
  assert.ok(before);
  assert.equal(a.send({ cmd: 'focusTown', town: '利雅德', req: 2 }).result.ok, true);
  assert.equal(a.map.getZoom(), C.MAP_FOCUS_ZOOM);
  assert.ok(a.centered('利雅德'));
  assert.equal(a.map.getZoom(), 9);
  // 假地圖的 setTimeout 是同步的（moveend 推送早於 focusTown 設定）：結果之後再要一份，等同瀏覽器裡結果後的推送。
  const check = (snapshot, label) => {
    const after = C.sanitizeMapSnapshot(snapshot);
    assert.ok(after, `${label}: the zoomed snapshot is not discarded (otherwise the parent loses every map target)`);
    assert.equal(after.scope, 'choice');
    assert.equal(after.focusTown, '利雅德', `${label}: the focused legal target is the action focus`);
    assert.equal(C.mapTargetsSig(after), C.mapTargetsSig(before), `${label}: same action targets as before focusing`);
    const list = LR.buildMapList(after);
    assert.equal(list.stage, 'choice');
    assert.deepEqual(list.rows.find(r => r.town === '利雅德'), { town: '利雅德', role: 'choice', act: 'build' });
    return snapshot.targets.find(t => t.town === '溫哥華');
  };
  const vancouver9 = check(a.send({ cmd: 'snapshot', req: 3 }).snapshot, 'SL zoom 9');
  assert.ok(Math.abs(vancouver9.x) > 50000, `溫哥華 is far off-screen at the SL focus zoom: ${vancouver9.x}`);
  // 之後 ZR 放大到循環最大層級 10（中心仍是利雅德）：北美目標超過舊的 10 萬上限，snapshot 仍必須被接受。
  assert.equal(a.send({ cmd: 'zoom', req: 4 }).result.ok, true);
  assert.equal(a.map.getZoom(), C.MAP_ZOOM_CYCLE.max);
  assert.ok(a.centered('利雅德'));
  const vancouver10 = check(a.send({ cmd: 'snapshot', req: 5 }).snapshot, 'ZR zoom 10');
  assert.ok(Math.abs(vancouver10.x) >= 100000, `the regression needs targets beyond the old 100000px bound: ${vancouver10.x}`);
  assert.deepEqual([a.clicks, a.markerClicks], [[], []], 'focusing / zooming selected / built nothing');
  assert.equal(a.ctx.selectedTown, null);
});

test('focusTown centers the zoom-dependent display position (黑河／海蘭泡／臥龍 pixel offsets)', () => {
  for (const town of ['黑河', '海蘭泡', '臥龍']) {
    const a = loadAdapter();
    const { result } = a.send({ cmd: 'focusTown', town, req: 1 });
    assert.equal(result.ok, true, town);
    assert.equal(a.map.getZoom(), C.MAP_FOCUS_ZOOM, town);
    assert.ok(a.centered(town), `${town}: the marker position at the focus zoom is at the container center`);
    const raw = a.map.latLngToContainerPoint(latLng(GEO[town][1], GEO[town][0]));
    assert.ok(Math.abs(raw.y - SIZE.y / 2) > 5, `${town}: the raw coordinate is offset, so centering it would be wrong`);
  }
});

test('focus zoom never exceeds Leaflet maxZoom, uses whole levels, and fails closed when min/max cannot be met', () => {
  const roomy = loadAdapter({ map: { maxZoom: 10 } });
  assert.equal(roomy.send({ cmd: 'focusTown', town: '臺北', req: 1 }).result.ok, true);
  assert.equal(roomy.map.getZoom(), 9, 'maxZoom above the focus level: still exactly 9, not the max');
  const capped = loadAdapter({ map: { maxZoom: 8 } });
  assert.equal(capped.send({ cmd: 'focusTown', town: '臺北', req: 1 }).result.ok, true);
  assert.equal(capped.map.getZoom(), 8);
  assert.ok(capped.centered('臺北'));
  const fractional = loadAdapter({ map: { maxZoom: 7.5 } });
  assert.equal(fractional.send({ cmd: 'focusTown', town: '臺北', req: 1 }).result.ok, true);
  assert.equal(fractional.map.getZoom(), 7);
  const impossible = loadAdapter({ map: { minZoom: 11, maxZoom: 18 } });
  const r = impossible.send({ cmd: 'focusTown', town: '臺北', req: 1 }).result;
  assert.deepEqual([r.ok, r.reason], [false, 'zoom-unavailable']);
  assert.deepEqual(impossible.map.setViews, [], 'camera untouched');
});

test('focusTown fails closed: unknown town, hidden map, missing coordinates, missing req, untrusted source', () => {
  const a = loadAdapter();
  let r = a.send({ cmd: 'focusTown', town: '不存在的城', req: 2 }).result;
  assert.deepEqual([r.ok, r.reason], [false, 'unknown-town']);
  assert.deepEqual(a.map.setViews, []);
  assert.equal(a.send({ cmd: 'focusTown', town: '臺北' }).result, null, 'no req: dropped before running, no result');
  assert.equal(a.send({ cmd: 'focusTown', town: '臺北', req: 0 }).result, null, 'invalid req');
  assert.equal(a.send({ cmd: 'focusTown', req: 3 }).result, null, 'no town');
  assert.equal(a.send({ cmd: 'focusTown', town: '臺北', req: 3 }, { postMessage() {} }).result, null, 'not from window.parent');
  assert.deepEqual(a.map.setViews, [], 'none of the rejected commands moved the camera');
  const hidden = loadAdapter({ map: { visible: false } });
  r = hidden.send({ cmd: 'focusTown', town: '臺北', req: 4 }).result;
  assert.deepEqual([r.ok, r.reason], [false, 'map-hidden']);
  assert.deepEqual(hidden.map.setViews, []);
  const broken = loadAdapter();
  broken.byName.get('臺北').lat = NaN;
  r = broken.send({ cmd: 'focusTown', town: '臺北', req: 5 }).result;
  assert.deepEqual([r.ok, r.reason], [false, 'town-position-missing']);
});

test('canonical data with a malformed town: no browse list at all (parent fails closed), action targets still flow', () => {
  const data = { ...MAP_DATA.towns, 臺北: { ...MAP_DATA.towns['臺北'], ruler: [] } };
  const a = loadAdapter({ mapData: data, choice: ['新北', '基隆'] });
  const { snapshot } = a.send({ cmd: 'snapshot', req: 9 });
  assert.equal(snapshot.browseMeta, undefined);
  assert.equal(snapshot.browseTowns, undefined);
  const snap = C.sanitizeMapSnapshot(snapshot);
  assert.deepEqual(snap.targets.map(t => t.town), ['新北', '基隆'], 'pending choice targets are unaffected');
  assert.equal(LR.buildFocusMenu(snap).reason, 'no-group-data');
});

test('pending target paths are unchanged: focus/activate/act still accept only legal targets', () => {
  const a = loadAdapter({ choice: ['新北', '基隆'] });
  const { snapshot } = a.send({ cmd: 'snapshot', req: 1 });
  assert.equal(snapshot.scope, 'choice');
  assert.deepEqual(snapshot.targets.map(t => [t.town, t.role, t.act]), [['新北', 'choice', 'build'], ['基隆', 'choice', 'build']]);
  assert.equal(snapshot.groupMeta, C.MAP_GROUP_META_VERSION);
  assert.equal(snapshot.browseTowns.length, canonicalNames.length, 'browse list is separate and complete');
  assert.deepEqual(a.send({ cmd: 'focus', town: '曼谷' }).result.reason, 'not-a-target');
  assert.deepEqual(a.send({ cmd: 'activate', town: '曼谷' }).result.reason, 'not-a-target');
  assert.deepEqual(a.send({ cmd: 'act', town: '曼谷', id: 'directBuildBtn', req: 2 }).result.reason, 'not-a-target');
  assert.deepEqual(a.markerClicks, []);
  // 瀏覽到非目標城鎮之後，既有目標的 A（marker click）照舊。
  assert.equal(a.send({ cmd: 'focusTown', town: '曼谷', req: 3 }).result.ok, true);
  assert.equal(a.send({ cmd: 'activate', town: '新北' }).result.ok, true);
  assert.deepEqual(JSON.parse(JSON.stringify(a.markerClicks)), [['新北', 'click']]);
  // 瀏覽到的城鎮剛好是合法目標：focusTown 本身仍不選取、不建立。
  const b = loadAdapter({ choice: ['新北', '基隆'] });
  assert.equal(b.send({ cmd: 'focusTown', town: '基隆', req: 4 }).result.ok, true);
  assert.deepEqual([b.clicks.length, b.markerClicks.length], [0, 0]);
  assert.ok(b.centered('基隆'));
  assert.equal(b.send({ cmd: 'focus', town: '基隆' }).result.ok, true, 'binding the browse town to its target focus is the existing focus');
  assert.equal(b.map.pans, 0, 'already centered: no pan');
});
