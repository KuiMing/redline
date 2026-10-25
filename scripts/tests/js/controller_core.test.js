// node --test scripts/tests/js/controller_core.test.js
const test = require('node:test');
const assert = require('node:assert/strict');
const C = require('../../../static/controller_core.js');

const frame = (x = 0, y = 0, pressed = []) => {
  const b = [0, 0];
  for (const name of pressed) { const [i, m] = C.BUTTON_BITS[name]; b[i] |= m; }
  return C.normalizeFrame({ x, y, buttons: b });
};
const run = (steps, cfg) => {
  let state = C.createInputState();
  const out = [];
  for (const [t, f] of steps) {
    const r = C.reduceFrame(state, f, t, cfg);
    state = r.state;
    out.push(r.actions);
  }
  return { out, state };
};

test('button bit mapping decodes every documented bit', () => {
  const all = C.decodeButtonBytes(0xff, 0xff);
  for (const n of C.BUTTON_NAMES) assert.equal(all[n], true);
  assert.deepEqual(Object.keys(C.decodeButtonBytes(0, 0)).filter(k => C.decodeButtonBytes(0, 0)[k]), []);
  assert.equal(C.decodeButtonBytes(0x08, 0).A, true);
  assert.equal(C.decodeButtonBytes(0x08, 0).B, false);
  assert.equal(C.decodeButtonBytes(0, 0x02).PLUS, true);
  assert.equal(C.decodeButtonBytes(0x80, 0).ZR, true);
});

test('capture: the physical key (b1 0x40) and upstream capture (b1 0x20) both decode to CAPTURE only', () => {
  // literals, not from BUTTON_BITS. A live bridge subscriber recorded the physical Capture press on the
  // right-Joy-Con-2 setup as buttons:[0,64] (switch2mac `c` = 0x0000_4000); `capture` = 0x0000_2000 stays accepted.
  const pressed = (b0, b1) => Object.entries(C.decodeButtonBytes(b0, b1)).filter(([, v]) => v).map(([k]) => k);
  assert.deepEqual(pressed(0x00, 0x40), ['CAPTURE'], 'observed physical Capture');
  assert.deepEqual(pressed(0x00, 0x20), ['CAPTURE'], 'upstream capture bit (compat)');
  assert.deepEqual(pressed(0x00, 0x60), ['CAPTURE']);
  assert.deepEqual(pressed(0x01, 0x00), ['Y'], 'observed physical Y');
  // neighbouring bits keep their own meaning (or none); nothing known is remapped
  assert.deepEqual(pressed(0x00, 0x02), ['PLUS']);
  assert.deepEqual(pressed(0x00, 0x04), ['STICK']);
  assert.deepEqual(pressed(0x00, 0x10), ['HOME']);
  for (const b1 of [0x01, 0x08, 0x80]) assert.deepEqual(pressed(0x00, b1), [], `b1 0x${b1.toString(16)}`);
  assert.deepEqual(pressed(0x40, 0x00), ['R'], 'b0 0x40 is R, not Capture');
  assert.deepEqual(pressed(0x20, 0x00), ['SL'], 'b0 0x20 is SL, not Capture');
  assert.equal(C.normalizeFrame({ x: 0, y: 0, buttons: [0x00, 0x40] }).buttons.CAPTURE, true);
  assert.equal(C.normalizeFrame({ x: 0, y: 0, buttons: 0x4000 }).buttons.CAPTURE, true);
  assert.equal(C.normalizeFrame({ x: 0, y: 0, buttons: [0x00, 0x20] }).buttons.CAPTURE, true);
});

test('capture: the recorded physical sequence fires one Y and one CAPTURE; reconnect hold stays a baseline', () => {
  const raw = (b) => C.normalizeFrame({ x: -0.0098, y: 0.0256, buttons: b });
  const presses = (steps) => {
    let state = C.createInputState();
    const out = [];
    for (const [t, b] of steps) {
      const r = C.reduceFrame(state, raw(b), t);
      state = r.state;
      out.push(...r.actions.filter(a => a.type === 'press').map(a => a.button));
    }
    return out;
  };
  // bridge subscriber: neutral → [1,0] → neutral → [0,64] (held a few frames) → neutral → [0,64] → neutral
  assert.deepEqual(presses([[0, [0, 0]], [33, [1, 0]], [66, [0, 0]], [100, [0, 64]], [133, [0, 64]], [166, [0, 0]], [200, [0, 64]], [233, [0, 0]]]),
    ['Y', 'CAPTURE', 'CAPTURE']);
  // one logical key: moving between its two bits while held never re-fires
  assert.deepEqual(presses([[0, [0, 0]], [33, [0, 0x20]], [66, [0, 0x60]], [100, [0, 0x40]], [133, [0, 0]], [166, [0, 0x40]]]), ['CAPTURE', 'CAPTURE']);
  // first frame after (re)connect holding the physical Capture key is only a baseline
  assert.deepEqual(presses([[0, [0, 64]], [33, [0, 64]], [66, [0, 0]], [100, [0, 64]]]), ['CAPTURE']);
});

test('normalizeFrame rejects NaN, out-of-range and malformed input', () => {
  assert.equal(C.normalizeFrame({ x: NaN, y: 0, buttons: [0, 0] }), null);
  assert.equal(C.normalizeFrame({ x: 0, y: Infinity, buttons: [0, 0] }), null);
  assert.equal(C.normalizeFrame({ x: 2, y: 0, buttons: [0, 0] }), null);
  assert.equal(C.normalizeFrame({ x: '0', y: 0, buttons: [0, 0] }), null);
  assert.equal(C.normalizeFrame({ x: 0, y: 0, buttons: [256, 0] }), null);
  assert.equal(C.normalizeFrame({ x: 0, y: 0, buttons: 'A' }), null);
  assert.equal(C.normalizeFrame(null), null);
  assert.equal(C.normalizeFrame({ x: 0, y: 0, buttons: [8, 0] }).buttons.A, true);
  assert.equal(C.normalizeFrame({ x: 0, y: 0, buttons: 0x0208 }).buttons.PLUS, true);
});

test('deadzone: small deflection yields no direction; dominant axis wins', () => {
  assert.equal(C.stickDirection(0.3, 0.3), null);
  assert.equal(C.stickDirection(0.49, 0), null);
  assert.equal(C.stickDirection(0.6, 0.2), 'right');
  assert.equal(C.stickDirection(-0.6, 0.2), 'left');
  assert.equal(C.stickDirection(0.1, 0.9), 'down');
  assert.equal(C.stickDirection(0.1, -0.9), 'up');
});

test('rising edge: a held button fires exactly once', () => {
  const { out } = run([[0, frame()], [10, frame(0, 0, ['A'])], [20, frame(0, 0, ['A'])], [30, frame(0, 0, ['A'])], [40, frame()], [50, frame(0, 0, ['A'])]]);
  const presses = out.flat().filter(a => a.type === 'press');
  assert.equal(presses.length, 2);
  assert.deepEqual(out[1], [{ type: 'press', button: 'A' }]);
  assert.deepEqual(out[2], []);
});

test('held stick: immediate edge, delay, then throttled repeat', () => {
  const steps = [[0, frame()]];
  for (let t = 33; t <= 1000; t += 33) steps.push([t, frame(1, 0)]);
  const navs = run(steps).out.flat().filter(a => a.type === 'nav');
  assert.equal(navs[0].repeat, false);
  assert.ok(navs.slice(1).every(n => n.repeat === true && n.dir === 'right'));
  // 1s hold with 380ms delay + 140ms interval → 1 edge + about 4–5 repeats, never one per frame
  assert.ok(navs.length >= 4 && navs.length <= 7, `got ${navs.length}`);
});

test('changing direction fires immediately; returning to neutral stops repeats', () => {
  const { out } = run([[0, frame()], [10, frame(1, 0)], [20, frame(-1, 0)], [30, frame(0, 0)], [40, frame(0, 1)]]);
  assert.deepEqual(out[1], [{ type: 'nav', dir: 'right', repeat: false }]);
  assert.deepEqual(out[2], [{ type: 'nav', dir: 'left', repeat: false }]);
  assert.deepEqual(out[3], []);
  assert.deepEqual(out[4], [{ type: 'nav', dir: 'down', repeat: false }]);
});

test('reconnect: first frame is only a baseline — held buttons and deflected stick never auto-fire', () => {
  let state = C.createInputState();
  let r = C.reduceFrame(state, frame(1, 0, ['A', 'B']), 0);
  assert.deepEqual(r.actions, []);
  state = r.state;
  r = C.reduceFrame(state, frame(1, 0, ['A', 'B']), 600);
  assert.deepEqual(r.actions, [], 'still-held inputs after reconnect stay silent');
  state = r.state;
  r = C.reduceFrame(state, frame(0, 0, []), 700);
  r = C.reduceFrame(r.state, frame(0, 0, ['A']), 710);
  assert.deepEqual(r.actions, [{ type: 'press', button: 'A' }]);
});

test('disconnect clears held state; a button held across the gap does not re-fire', () => {
  let r = C.reduceFrame(C.createInputState(), frame(), 0);
  r = C.reduceFrame(r.state, frame(0, 0, ['A']), 10);
  assert.equal(r.state.held.A, true);
  const cleared = C.resetInputState();
  assert.deepEqual(cleared.held, {});
  assert.equal(cleared.armed, false);
  const after = C.reduceFrame(cleared, frame(0, 0, ['A']), 5000);
  assert.deepEqual(after.actions, []);
});

test('bridge input gate: only an enabled, connected, open bridge feeds reduceFrame', () => {
  const g = (o) => C.bridgeInputGate({ enabled: true, status: 'connected', socketOpen: true, fromBridge: true, ...o });
  assert.equal(g({}), 'accept');
  assert.equal(g({ fromBridge: false }), 'accept', 'public feed() while connected takes the same path as the bridge');
  for (const status of ['off', 'connecting', 'error', 'bogus', undefined]) {
    for (const fromBridge of [true, false]) assert.equal(g({ status, fromBridge }), 'drop', `${status}/${fromBridge}`);
  }
  assert.equal(g({ socketOpen: false }), 'drop', 'closing / closed socket while status still says connected');
  assert.equal(g({ enabled: false }), 'drop');
  assert.equal(g({ status: 'stale' }), 'recover', "the live bridge's own frame recovers from stale (as a baseline)");
  assert.equal(g({ status: 'stale', fromBridge: false }), 'drop', 'public feed() cannot revive a stale bridge');
  assert.equal(g({ status: 'stale', socketOpen: false }), 'drop');
  assert.equal(C.bridgeInputGate(), 'drop');
});

test('bridge connected: shortcut hints require enabled + connected + open socket', () => {
  const c = (o) => C.bridgeConnected({ enabled: true, status: 'connected', socketOpen: true, ...o });
  assert.equal(c({}), true);
  for (const status of ['off', 'connecting', 'error', 'stale']) assert.equal(c({ status }), false, status);
  assert.equal(c({ socketOpen: false }), false);
  assert.equal(c({ enabled: false }), false);
  assert.equal(C.bridgeConnected(), false);
});

test('recover then reduce: a button held across the outage is only a baseline; a fresh press after release fires', () => {
  assert.equal(C.bridgeInputGate({ enabled: true, status: 'stale', socketOpen: true, fromBridge: true }), 'recover');
  let state = C.resetInputState();
  let r = C.reduceFrame(state, frame(0, 0, ['X']), 5000);
  assert.deepEqual(r.actions, [], 'first frame after recover/reconnect is a baseline');
  r = C.reduceFrame(r.state, frame(0, 0, ['X']), 5033);
  assert.deepEqual(r.actions, [], 'still held');
  r = C.reduceFrame(r.state, frame(0, 0, []), 5066);
  r = C.reduceFrame(r.state, frame(0, 0, ['X']), 5100);
  assert.deepEqual(r.actions, [{ type: 'press', button: 'X' }]);
});

test('stale detection', () => {
  let r = C.reduceFrame(C.createInputState(), frame(), 1000);
  assert.equal(C.isStale(r.state, 1500), false);
  assert.equal(C.isStale(r.state, 2600), true);
  assert.equal(C.isStale(C.createInputState(), 0), true);
});

test('logical mapping: + / HOME / CAPTURE / STICK never produce desktop actions; ZR = map zoom; SL opens the focus menu', () => {
  for (const b of ['PLUS', 'HOME', 'CAPTURE', 'STICK']) {
    assert.equal(C.logicalAction({ type: 'press', button: b }), null, b);
  }
  assert.deepEqual(C.logicalAction({ type: 'press', button: 'ZR' }), { name: 'mapZoom' });
  assert.deepEqual(C.logicalAction({ type: 'press', button: 'SL' }), { name: 'focusMenu' });
  assert.deepEqual(C.logicalAction({ type: 'press', button: 'A' }), { name: 'confirm' });
  assert.deepEqual(C.logicalAction({ type: 'press', button: 'R' }), { name: 'nextSection' });
  assert.deepEqual(C.logicalAction({ type: 'press', button: 'SR' }), { name: 'prevSection' });
});

// ---- SL 聚焦選單 ----

test('SL: the existing b0 0x20 mapping is kept and decodes to SL only (no new raw bit)', () => {
  assert.deepEqual(C.BUTTON_BITS.SL, [0, 0x20]);
  assert.equal(C.BUTTON_ALT_BITS.SL, undefined, 'no alternate bit invented for SL');
  const pressed = (b0, b1) => Object.entries(C.decodeButtonBytes(b0, b1)).filter(([, v]) => v).map(([k]) => k);
  assert.deepEqual(pressed(0x20, 0x00), ['SL']);
  assert.deepEqual(pressed(0x30, 0x00), ['SL', 'SR'], 'SL with SR held: two distinct keys');
  assert.deepEqual(pressed(0x00, 0x20), ['CAPTURE'], 'b1 0x20 stays CAPTURE, never SL');
  assert.equal(C.normalizeFrame({ x: 0, y: 0, buttons: 0x0020 }).buttons.SL, true);
});

test('SL: physical byte → one logical focusMenu per press; held and reconnect-held never re-fire', () => {
  const raw = (b0) => C.normalizeFrame({ x: 0.01, y: -0.02, buttons: [b0, 0] });
  const logical = (steps) => {
    let state = C.createInputState();
    const out = [];
    for (const [t, b0] of steps) {
      const r = C.reduceFrame(state, raw(b0), t);
      state = r.state;
      out.push(...r.actions.map(a => C.logicalAction(a)).filter(Boolean).map(l => l.name));
    }
    return out;
  };
  // neutral → SL held for several frames → release → SL again
  assert.deepEqual(logical([[0, 0], [33, 0x20], [66, 0x20], [100, 0x20], [133, 0], [166, 0x20], [200, 0]]), ['focusMenu', 'focusMenu']);
  // (re)connect while SL is already held: baseline only; fires again only after a release
  assert.deepEqual(logical([[0, 0x20], [33, 0x20], [66, 0x20]]), []);
  assert.deepEqual(logical([[0, 0x20], [33, 0x20], [66, 0], [100, 0x20]]), ['focusMenu']);
  // SR pressed while SL stays held: SR fires, SL does not repeat
  assert.deepEqual(logical([[0, 0], [33, 0x20], [66, 0x30], [100, 0x20]]), ['focusMenu', 'prevSection']);
});

const FOCUS_MENU_ID = 'lrFocusMenu';
test('SL routing: opens from page / map scope, toggles the open menu closed, and is scope-locked in every other modal', () => {
  const SL = { name: 'focusMenu' };
  for (const scopeKind of ['page', 'map']) {
    for (const extra of [{}, { hasFocus: false }, { sectionsLocked: true }, { card: { zone: 'hand', hasToggle: false } }]) {
      assert.deepEqual(C.routeAction({ scopeKind, hasFocus: true, cancelAvailable: false, sectionsLocked: false, ...extra }, SL), { cmd: 'focusMenu' }, scopeKind);
    }
  }
  assert.equal(C.routeAction({ scopeKind: 'modal', hasFocus: true, cancelAvailable: true, sectionsLocked: false }, SL), null, 'other modal: scope lock');
  assert.deepEqual(C.routeAction({ scopeKind: 'modal', hasFocus: true, cancelAvailable: true, sectionsLocked: false, focusMenuOpen: true }, SL), { cmd: 'focusMenu' }, 'SL again = close');
  assert.equal(C.FOCUS_MENU_MODAL_ID, FOCUS_MENU_ID);
});

test('focus menu modal: background keys are inert; A picks the focused option, B cancels via the existing close', () => {
  const menu = { scopeKind: 'modal', hasFocus: true, cancelAvailable: true, sectionsLocked: false, focusMenuOpen: true, card: null };
  for (const name of ['nextSection', 'prevSection', 'focusTurnBar', 'toggleHelp', 'mapZoom']) assert.equal(C.routeAction(menu, { name }), null, name);
  assert.deepEqual(C.routeAction(menu, { name: 'confirm' }), { cmd: 'activate' });
  assert.deepEqual(C.routeAction(menu, { name: 'cancel' }), { cmd: 'cancel' });
  assert.deepEqual(C.routeAction(menu, { name: 'move', dir: 'down' }), { cmd: 'move', dir: 'down' });
  assert.equal(C.routeAction({ ...menu, hasFocus: false }, { name: 'confirm' }), null);
  // + / Capture / STICK / HOME have no desktop logical action at all (ZR = map zoom is inert in the menu, above)
  for (const b of ['PLUS', 'CAPTURE', 'STICK', 'HOME']) assert.equal(C.logicalAction({ type: 'press', button: b }), null, b);
});

// ---- ZR 戰略地圖縮放循環 ----

test('ZR: the physical b0 0x80 byte decodes to ZR only; one press = one mapZoom, held and reconnect-held never re-fire', () => {
  assert.deepEqual(C.BUTTON_BITS.ZR, [0, 0x80]);
  assert.equal(C.BUTTON_ALT_BITS.ZR, undefined, 'no alternate bit invented for ZR');
  const pressed = (b0, b1) => Object.entries(C.decodeButtonBytes(b0, b1)).filter(([, v]) => v).map(([k]) => k);
  assert.deepEqual(pressed(0x80, 0x00), ['ZR'], 'user BUTTON AREA record: ZR = 80 00');
  assert.deepEqual(pressed(0x00, 0x80), [], 'b1 0x80 is not ZR');
  assert.deepEqual(pressed(0xc0, 0x00), ['R', 'ZR'], 'R with ZR held: two distinct keys');
  assert.equal(C.normalizeFrame({ x: 0, y: 0, buttons: 0x0080 }).buttons.ZR, true);
  assert.equal(C.normalizeFrame({ x: 0, y: 0, buttons: { b0: 0x80 } }).buttons.ZR, true);
  const logical = (steps) => {
    let state = C.createInputState();
    const out = [];
    for (const [t, b0] of steps) {
      const r = C.reduceFrame(state, C.normalizeFrame({ x: 0.01, y: -0.02, buttons: [b0, 0] }), t);
      state = r.state;
      out.push(...r.actions.map(a => C.logicalAction(a)).filter(Boolean).map(l => l.name));
    }
    return out;
  };
  assert.deepEqual(logical([[0, 0], [33, 0x80], [66, 0x80], [100, 0x80], [133, 0], [166, 0x80], [200, 0]]), ['mapZoom', 'mapZoom']);
  assert.deepEqual(logical([[0, 0x80], [33, 0x80], [66, 0x80]]), [], '(re)connect with ZR held is only a baseline');
  assert.deepEqual(logical([[0, 0x80], [33, 0], [66, 0x80]]), ['mapZoom']);
});

test('ZR routing: only the strategic-map scope zooms (any focus, choice lock); page, modal and the focus menu are inert', () => {
  const ZR = { name: 'mapZoom' };
  const map = { scopeKind: 'map', hasFocus: true, cancelAvailable: false, sectionsLocked: false, card: null };
  for (const extra of [{}, { hasFocus: false }, { sectionsLocked: true }, { mapTarget: true }, { cancelAvailable: true }]) {
    assert.deepEqual(C.routeAction({ ...map, ...extra }, ZR), { cmd: 'mapZoom' }, JSON.stringify(extra));
  }
  for (const ctx of [
    { ...map, scopeKind: 'page' },
    { ...map, scopeKind: 'page', card: { zone: 'hand', hasToggle: false } },
    { ...map, scopeKind: 'modal', cancelAvailable: true },
    { ...map, scopeKind: 'modal', cancelAvailable: true, focusMenuOpen: true },
    { ...map, scopeKind: 'map', focusMenuOpen: true },
  ]) assert.equal(C.routeAction(ctx, ZR), null, JSON.stringify(ctx));
});

test('zoom command / result: a correlated request id is mandatory', () => {
  const cmd = (extra) => C.sanitizeMapCommand({ v: 1, type: 'redline-controller-command', cmd: 'zoom', ...extra });
  assert.ok(C.MAP_COMMANDS.includes('zoom'));
  assert.deepEqual(cmd({ req: 4 }), { cmd: 'zoom', town: undefined, id: undefined, req: 4 });
  assert.equal(cmd({}), null, 'req absent');
  for (const req of [null, 0, -1, 1.5, '3', NaN, Infinity, Number.MAX_SAFE_INTEGER + 2, true, {}, [7]]) assert.equal(cmd({ req }), null, `req=${String(req)}`);
  const result = (extra) => C.sanitizeMapResult({ type: 'redline-controller-result', v: 1, cmd: 'zoom', ok: true, ...extra });
  assert.deepEqual(result({ req: 9 }), { cmd: 'zoom', ok: true, req: 9, via: null, reason: null });
  assert.equal(result({ req: 9, ok: false, reason: 'map-hidden' }).reason, 'map-hidden');
  for (const extra of [{}, { req: null }, { req: 0 }, { req: '9' }, { req: 9, ok: 'yes' }, { req: 9, via: 'directBuildBtnX' }]) {
    assert.equal(result(extra), null, JSON.stringify(extra));
  }
});

// ---- SL 全域地圖聚焦（focusTown／browseTowns） ----

test('focusTown command / result: town and a correlated request id are mandatory', () => {
  const cmd = (extra) => C.sanitizeMapCommand({ v: 1, type: 'redline-controller-command', cmd: 'focusTown', ...extra });
  assert.ok(C.MAP_COMMANDS.includes('focusTown'));
  assert.deepEqual(cmd({ town: '曼谷', req: 5 }), { cmd: 'focusTown', town: '曼谷', id: undefined, req: 5 });
  assert.equal(cmd({ town: '曼谷' }), null, 'req absent');
  for (const req of [null, 0, -1, 1.5, '3', NaN, true, {}]) assert.equal(cmd({ town: '曼谷', req }), null, `req=${String(req)}`);
  for (const town of [undefined, '', 7, '名'.repeat(65)]) assert.equal(cmd({ town, req: 5 }), null, `town=${String(town)}`);
  const result = (extra) => C.sanitizeMapResult({ type: 'redline-controller-result', v: 1, cmd: 'focusTown', ok: true, ...extra });
  assert.deepEqual(result({ req: 5 }), { cmd: 'focusTown', ok: true, req: 5, via: null, reason: null });
  assert.equal(result({ req: 5, ok: false, reason: 'unknown-town' }).reason, 'unknown-town');
  for (const extra of [{}, { req: null }, { req: 0 }, { req: 5, via: 'directBuildBtn2' }]) assert.equal(result(extra), null, JSON.stringify(extra));
  // 既有不帶 req 的桌面模式指令行為不變
  assert.deepEqual(C.sanitizeMapCommand({ v: 1, type: 'redline-controller-command', cmd: 'focus', town: '臺北' }), { cmd: 'focus', town: '臺北', id: undefined, req: null });
});

test('focus zoom: fixed level, never above Leaflet maxZoom, whole levels only, fails closed when min/max cannot be met', () => {
  assert.equal(C.MAP_FOCUS_ZOOM, 9, 'canonical SL focus level is 9 (not the ZR cycle max 10)');
  assert.equal(C.MAP_ZOOM_CYCLE.max, 10, 'the ZR cycle keeps its own max');
  assert.equal(C.mapFocusZoom(0, Infinity), C.MAP_FOCUS_ZOOM, 'the strategic map sets no min/max');
  assert.equal(C.mapFocusZoom(0, 18), 9);
  assert.equal(C.mapFocusZoom(0, 10), 9);
  assert.equal(C.mapFocusZoom(0, 9), 9);
  assert.equal(C.mapFocusZoom(2, 8), 8, 'capped by maxZoom');
  assert.equal(C.mapFocusZoom(0, 7.5), 7, 'whole level not above maxZoom');
  assert.equal(C.mapFocusZoom(-3, Infinity), C.MAP_FOCUS_ZOOM);
  assert.equal(C.mapFocusZoom(9, 9), 9);
  assert.equal(C.mapFocusZoom(0, 8.9), 8, 'maxZoom below 9 → its whole level');
  assert.equal(C.mapFocusZoom(0, Infinity, 12), 12);
  for (const [min, max] of [[10, 18], [11, 18], [8.5, 8.7], [NaN, 18], [0, NaN], ['0', 18], [0, '18'], [undefined, 18], [0, null], [0, -Infinity]]) {
    assert.equal(C.mapFocusZoom(min, max), null, `${String(min)}..${String(max)}`);
  }
  for (const preferred of [NaN, 9.5, -1, '10']) assert.equal(C.mapFocusZoom(0, 18, preferred), null, String(preferred));
});

const BROWSE = [
  { town: '臺北', ruler: ['臺灣'], camp: ['臺灣', '紅軍'] },
  { town: '曼谷', ruler: ['南洋'], camp: [] },
];
const browseSnap = (extra = {}) => ({
  type: 'redline-controller-map-snapshot', v: 1, seq: 2, scope: 'none', targets: [], buttons: [], focusTown: null, canCancel: false,
  browseMeta: 1, browseTowns: BROWSE, ...extra,
});

test('snapshot browse list (browseMeta v1): the full canonical list is accepted without any pending choice or target', () => {
  const snap = C.sanitizeMapSnapshot(browseSnap());
  assert.equal(C.MAP_BROWSE_META_VERSION, 1);
  assert.equal(snap.browseMeta, 1);
  assert.deepEqual(snap.browseTowns, BROWSE);
  assert.deepEqual(snap.targets, [], 'browse towns never become action targets');
  assert.equal(snap.groupMeta, null);
  const dup = C.sanitizeMapSnapshot(browseSnap({ browseTowns: [{ town: '臺北', ruler: ['臺灣'], camp: ['臺灣', '臺灣'] }] }));
  assert.deepEqual(dup.browseTowns[0].camp, ['臺灣'], 'duplicate membership counts once');
  // 與 pending choice 並存：目標與分組資料各自驗證，互不改寫。
  const withChoice = C.sanitizeMapSnapshot(browseSnap({
    scope: 'choice', groupMeta: 1, targets: [{ town: '臺北', role: 'choice', x: 1, y: 2, act: 'build', ruler: ['臺灣'], camp: ['臺灣'] }],
  }));
  assert.deepEqual(withChoice.targets.map(t => t.town), ['臺北']);
  assert.deepEqual(withChoice.browseTowns.map(t => t.town), ['臺北', '曼谷']);
  // 舊版 iframe（沒有 browseMeta）：snapshot 仍有效但沒有瀏覽清單。
  const legacy = C.sanitizeMapSnapshot(browseSnap({ browseMeta: undefined, browseTowns: undefined }));
  assert.deepEqual([legacy.browseMeta, legacy.browseTowns], [null, []]);
});

test('snapshot browse list fails closed as a whole: version, missing list, duplicates, malformed towns, size', () => {
  for (const [label, extra] of [
    ['unknown version', { browseMeta: 2 }],
    ['string version', { browseMeta: '1' }],
    ['version without list', { browseTowns: undefined }],
    ['list without version', { browseMeta: undefined }],
    ['list not an array', { browseTowns: { 臺北: {} } }],
    ['empty list', { browseTowns: [] }],
    ['duplicate town', { browseTowns: [...BROWSE, BROWSE[0]] }],
    ['town missing', { browseTowns: [{ ruler: ['臺灣'], camp: [] }] }],
    ['empty ruler', { browseTowns: [{ town: '臺北', ruler: [], camp: [] }] }],
    ['camp missing', { browseTowns: [{ town: '臺北', ruler: ['臺灣'] }] }],
    ['invalid camp entry', { browseTowns: [{ town: '臺北', ruler: ['臺灣'], camp: ['臺灣', 3] }] }],
    ['null entry', { browseTowns: [null] }],
    ['too many towns', { browseTowns: Array.from({ length: 401 }, (_, i) => ({ town: `T${i}`, ruler: ['R'], camp: [] })) }],
  ]) assert.equal(C.sanitizeMapSnapshot(browseSnap(extra)), null, label);
});

test('map target signature: scope + role/town only (camera moves keep it), any target change alters it', () => {
  const base = { scope: 'move', targets: [{ town: '北京', role: 'origin', x: 1, y: 2 }] };
  const sig = C.mapTargetsSig(base);
  assert.equal(typeof sig, 'string');
  assert.equal(C.mapTargetsSig({ ...base, targets: [{ town: '北京', role: 'origin', x: 400, y: -20 }] }), sig, 'coordinates ignored');
  assert.equal(C.mapTargetsSig({ ...base, browseTowns: BROWSE, seq: 99, focusTown: '北京' }), sig);
  assert.notEqual(C.mapTargetsSig({ ...base, scope: 'choice', targets: [{ town: '北京', role: 'choice' }] }), sig, 'new pending choice');
  assert.notEqual(C.mapTargetsSig({ ...base, targets: [...base.targets, { town: '天津', role: 'origin' }] }), sig);
  assert.notEqual(C.mapTargetsSig({ scope: 'none', targets: [] }), sig);
  assert.equal(C.mapTargetsSig(null), null);
  assert.equal(C.mapTargetsSig({ scope: 'none' }), null);
});

test('zoom bounds: Leaflet getMinZoom/getMaxZoom intersected with MAP_ZOOM_CYCLE; unusable ranges fail closed', () => {
  const { min, max } = C.MAP_ZOOM_CYCLE;
  assert.ok(Number.isInteger(min) && Number.isInteger(max) && max > min, 'integer levels, at least two');
  assert.ok(Object.isFrozen(C.MAP_ZOOM_CYCLE));
  // the strategic map sets no maxZoom: Leaflet reports 0 / Infinity → the cycle constant decides
  assert.deepEqual(C.mapZoomBounds(0, Infinity), { min, max });
  // a map configured tighter than the cycle wins on both ends (Leaflet stays authoritative)
  assert.deepEqual(C.mapZoomBounds(min + 1, max - 2), { min: min + 1, max: max - 2 });
  assert.deepEqual(C.mapZoomBounds(min + 0.5, max - 0.5), { min: min + 1, max: max - 1 }, 'whole levels only');
  assert.deepEqual(C.mapZoomBounds(3, 7, { min: 1, max: 18 }), { min: 3, max: 7 });
  for (const [a, b] of [[NaN, 18], [0, NaN], ['0', 18], [0, undefined], [null, 18], [max, max], [max + 1, max + 5], [min - 5, min]]) {
    assert.equal(C.mapZoomBounds(a, b), null, `${a}..${b}`);
  }
});

test('zoom step: min → min+1, middle → next, max → min; outside the range → min; fractional → next level; invalid → null', () => {
  const b = { min: 2, max: 10 };
  assert.equal(C.nextMapZoom(2, b), 3, 'min → min+1');
  assert.equal(C.nextMapZoom(6, b), 7, 'middle level → next');
  assert.equal(C.nextMapZoom(9, b), 10, 'one below max → max');
  assert.equal(C.nextMapZoom(10, b), 2, 'max → min (single direction cycle)');
  assert.equal(C.nextMapZoom(13, b), 2, 'zoomed past the cycle with the mouse → back to min');
  assert.equal(C.nextMapZoom(0, b), 2, 'below the cycle → min');
  assert.equal(C.nextMapZoom(1.4, b), 2);
  assert.equal(C.nextMapZoom(6.4, b), 7, 'fractional level advances to the next whole level');
  assert.equal(C.nextMapZoom(9.9999999, b), 2, 'float noise at max still wraps');
  assert.equal(C.nextMapZoom(5.9999999, b), 7, 'float noise at a level still advances exactly one level');
  // a full cycle visits every level exactly once
  const seen = [];
  let z = b.min;
  for (let i = 0; i <= b.max - b.min + 1; i += 1) { seen.push(z); z = C.nextMapZoom(z, b); }
  assert.deepEqual(seen, [2, 3, 4, 5, 6, 7, 8, 9, 10, 2]);
  for (const cur of [NaN, Infinity, -Infinity, '5', null, undefined]) assert.equal(C.nextMapZoom(cur, b), null, String(cur));
  for (const bad of [null, {}, { min: 2 }, { min: 2, max: 2 }, { min: 5, max: 3 }, { min: 2.5, max: 9 }]) assert.equal(C.nextMapZoom(4, bad), null, JSON.stringify(bad));
  assert.equal(C.nextMapZoom(C.MAP_ZOOM_CYCLE.max, C.mapZoomBounds(0, Infinity)), C.MAP_ZOOM_CYCLE.min);
});

test('focus menu modal sits right under the danger confirm and has a mouse-closable cancel', () => {
  assert.equal(C.MODAL_SCOPES[0].id, 'lrConfirmModal');
  const scope = C.MODAL_SCOPES[1];
  assert.equal(scope.id, FOCUS_MENU_ID);
  assert.deepEqual(scope.cancel, ['#lrFocusMenuClose']);
  assert.equal(typeof scope.initial, 'string');
  assert.equal(C.resolveModalScope(['choiceModal', 'peerActionNotice', FOCUS_MENU_ID]).id, FOCUS_MENU_ID);
  assert.equal(C.resolveModalScope([FOCUS_MENU_ID, 'lrConfirmModal']).id, 'lrConfirmModal');
});

const groupSnap = (extra = {}, target = {}) => ({
  type: 'redline-controller-map-snapshot', v: 1, seq: 4, scope: 'choice', buttons: [], focusTown: null, canCancel: false,
  groupMeta: 1,
  targets: [{ town: '臺北', role: 'choice', x: 1, y: 2, act: 'build', ruler: ['臺灣'], camp: ['臺灣', '紅軍'], ...target }],
  ...extra,
});

test('snapshot group metadata (groupMeta v1): canonical ruler / camp lists are validated and de-duplicated', () => {
  const ok = C.sanitizeMapSnapshot(groupSnap({}, { camp: ['臺灣', '紅軍', '臺灣'] }));
  assert.equal(ok.groupMeta, 1);
  assert.deepEqual(ok.targets[0], { town: '臺北', role: 'choice', x: 1, y: 2, act: 'build', ruler: ['臺灣'], camp: ['臺灣', '紅軍'] });
  assert.deepEqual(C.sanitizeMapSnapshot(groupSnap({}, { camp: [] })).targets[0].camp, [], 'a town without camp tags is valid');
  assert.equal(C.MAP_GROUP_META_VERSION, 1);
  for (const [label, extra, target] of [
    ['unknown group schema version', { groupMeta: 2 }, {}],
    ['non-integer version', { groupMeta: '1' }, {}],
    ['ruler not an array', {}, { ruler: '臺灣' }],
    ['camp missing', {}, { camp: undefined }],
    ['ruler missing', {}, { ruler: undefined }],
    ['empty ruler list', {}, { ruler: [] }],
    ['camp not an array', {}, { camp: '臺灣' }],
    ['empty name', {}, { camp: [''] }],
    ['non-string name', {}, { ruler: [7] }],
    ['overlong name', {}, { camp: ['名'.repeat(17)] }],
    ['too many rulers', {}, { ruler: Array.from({ length: 9 }, (_, i) => `R${i}`) }],
    ['too many camps', {}, { camp: Array.from({ length: 17 }, (_, i) => `C${i}`) }],
  ]) assert.equal(C.sanitizeMapSnapshot(groupSnap(extra, target)), null, label);
  // metadata without the version flag is not trusted: the whole snapshot is rejected (fail closed)
  assert.equal(C.sanitizeMapSnapshot(groupSnap({ groupMeta: undefined })), null);
  // legacy snapshots without any group metadata stay valid but carry none
  const legacy = C.sanitizeMapSnapshot(groupSnap({ groupMeta: undefined }, { ruler: undefined, camp: undefined }));
  assert.equal(legacy.groupMeta, null);
  assert.equal(legacy.targets[0].ruler, undefined);
});

test('snapshot req: a snapshot answering a snapshot request echoes a valid request id; anything else is rejected', () => {
  assert.equal(C.sanitizeMapSnapshot(groupSnap({ req: 12 })).req, 12);
  assert.equal(C.sanitizeMapSnapshot(groupSnap()).req, null);
  for (const req of [0, -1, 1.5, '3', true, {}, Number.MAX_SAFE_INTEGER + 2]) assert.equal(C.sanitizeMapSnapshot(groupSnap({ req })), null, String(req));
  assert.deepEqual(C.sanitizeMapCommand({ v: 1, type: 'redline-controller-command', cmd: 'snapshot', req: 9 }), { cmd: 'snapshot', town: undefined, id: undefined, req: 9 });
  assert.equal(C.isRequestId(9), true);
  assert.equal(C.isRequestId(0), false);
});

test('town group metadata: canonical ruler / camp are taken whole or rejected (never filtered, truncated or guessed)', () => {
  assert.deepEqual(C.townGroupMeta({ ruler: ['臺灣'], camp: ['臺灣', '紅軍', '臺灣'] }), { ruler: ['臺灣'], camp: ['臺灣', '紅軍'] },
    'duplicate membership counts once');
  assert.deepEqual(C.townGroupMeta({ ruler: ['紅軍'], camp: [] }), { ruler: ['紅軍'], camp: [] }, 'a town without camp tags is valid');
  for (const [label, raw] of [
    ['no map data', null],
    ['not an object', '臺北'],
    ['ruler missing', { camp: [] }],
    ['camp missing', { ruler: ['紅軍'] }],
    ['empty ruler list', { ruler: [], camp: [] }],
    ['ruler not an array', { ruler: '臺灣', camp: [] }],
    ['camp not an array', { ruler: ['臺灣'], camp: '香港' }],
    ['invalid camp entry is not filtered out', { ruler: ['臺灣'], camp: ['臺灣', '紅軍', 3] }],
    ['empty ruler name', { ruler: [''], camp: [] }],
    ['null camp entry', { ruler: ['臺灣'], camp: [null] }],
    ['overlong name', { ruler: ['名'.repeat(17)], camp: [] }],
    ['too many rulers is not truncated', { ruler: Array.from({ length: 9 }, (_, i) => `R${i}`), camp: [] }],
    ['too many camps is not truncated', { ruler: ['臺灣'], camp: Array.from({ length: 17 }, (_, i) => `C${i}`) }],
  ]) assert.equal(C.townGroupMeta(raw), null, label);
});

test('B does nothing when no cancel exists; A needs a focus', () => {
  const page = { scopeKind: 'page', hasFocus: true, cancelAvailable: false, sectionsLocked: false };
  assert.equal(C.routeAction(page, { name: 'cancel' }), null);
  assert.deepEqual(C.routeAction({ ...page, cancelAvailable: true }, { name: 'cancel' }), { cmd: 'cancel' });
  assert.equal(C.routeAction({ ...page, hasFocus: false }, { name: 'confirm' }), null);
  assert.deepEqual(C.routeAction(page, { name: 'confirm' }), { cmd: 'activate' });
});

test('modal and required-choice scopes block section switching', () => {
  const modal = { scopeKind: 'modal', hasFocus: true, cancelAvailable: true, sectionsLocked: false };
  assert.equal(C.routeAction(modal, { name: 'nextSection' }), null);
  assert.equal(C.routeAction(modal, { name: 'focusTurnBar' }), null);
  const locked = { scopeKind: 'map', hasFocus: true, cancelAvailable: false, sectionsLocked: true };
  assert.equal(C.routeAction(locked, { name: 'prevSection' }), null);
  assert.deepEqual(C.routeAction({ ...locked, sectionsLocked: false }, { name: 'prevSection' }), { cmd: 'section', step: -1 });
});

test('modal scope: highest-priority visible dialog wins and background candidates are excluded', () => {
  assert.equal(C.resolveModalScope([]), null);
  assert.equal(C.resolveModalScope(['victoryModal', 'choiceModal']).id, 'choiceModal');
  assert.equal(C.resolveModalScope(['choiceModal', 'unavailableActionModal']).id, 'unavailableActionModal');
  assert.equal(C.resolveModalScope(['choiceModal', 'cardPreviewModal']).id, 'cardPreviewModal');
  const rect = { left: 0, top: 0, right: 10, bottom: 10, visible: true };
  const candidates = [
    { key: 'bg', scope: 'page', ...rect },
    { key: 'dlg', scope: 'choiceModal', ...rect },
  ];
  assert.deepEqual(C.buildFocusSet(candidates, 'choiceModal').map(c => c.key), ['dlg']);
  assert.deepEqual(C.buildFocusSet(candidates, 'page').map(c => c.key), ['bg']);
});

test('disabled / hidden / aria-disabled / skipped controls are never focusable', () => {
  const base = { scope: 'page', visible: true, left: 0, top: 0, right: 1, bottom: 1 };
  const set = C.buildFocusSet([
    { key: 'ok', ...base },
    { key: 'disabled', ...base, disabled: true },
    { key: 'hidden', ...base, visible: false },
    { key: 'aria', ...base, ariaDisabled: true },
    { key: 'skip', ...base, skip: true },
  ], 'page');
  assert.deepEqual(set.map(c => c.key), ['ok']);
});

test('directional navigation picks the nearest in direction and never wraps', () => {
  const at = (key, x, y) => ({ key, left: x, right: x + 10, top: y, bottom: y + 10 });
  const items = [at('a', 0, 0), at('b', 100, 0), at('c', 0, 100), at('d', 200, 5)];
  assert.equal(C.pickDirectional(items, 'a', 'right').key, 'b');
  assert.equal(C.pickDirectional(items, 'b', 'right').key, 'd');
  assert.equal(C.pickDirectional(items, 'a', 'down').key, 'c');
  assert.equal(C.pickDirectional(items, 'a', 'left').key, 'a');
  assert.equal(C.pickDirectional(items, 'a', 'up').key, 'a');
  assert.equal(C.pickDirectional(items, null, 'right').key, 'a');
  assert.equal(C.pickDirectional([], null, 'right'), null);
  assert.equal(C.cycleIndex(4, 3, 1), 0);
  assert.equal(C.cycleIndex(4, 0, -1), 3);
});

const ORIGIN = 'http://127.0.0.1:8100';
const SRC = {};
test('iframe message validation: origin, source, version, schema', () => {
  const data = { v: 1, type: 'redline-controller-command', cmd: 'cancel' };
  assert.equal(C.isTrustedMessage({ origin: ORIGIN, source: SRC, data }, ORIGIN, SRC), true);
  assert.equal(C.isTrustedMessage({ origin: 'http://evil.example', source: SRC, data }, ORIGIN, SRC), false);
  assert.equal(C.isTrustedMessage({ origin: ORIGIN, source: {}, data }, ORIGIN, SRC), false);
  assert.equal(C.isTrustedMessage({ origin: ORIGIN, source: SRC, data: { ...data, v: 2 } }, ORIGIN, SRC), false);
  assert.equal(C.isTrustedMessage({ origin: ORIGIN, source: SRC, data: null }, ORIGIN, SRC), false);
  assert.equal(C.isTrustedMessage({ origin: ORIGIN, source: SRC, data }, ORIGIN, null), false);

  assert.equal(C.sanitizeMapCommand({ v: 1, type: 'redline-controller-command', cmd: 'activate' }), null);
  assert.equal(C.sanitizeMapCommand({ v: 1, type: 'redline-controller-command', cmd: 'rm -rf' }), null);
  assert.equal(C.sanitizeMapCommand({ v: 1, type: 'redline-controller-command', cmd: 'button', id: 'advanceStepBtn' }), null);
  assert.equal(C.sanitizeMapCommand({ v: 1, type: 'redline-controller-command', cmd: 'act', id: 'directBuildBtn' }), null, 'act needs a town');
  assert.deepEqual(C.sanitizeMapCommand({ v: 1, type: 'redline-controller-command', cmd: 'activate', town: '臺北' }).town, '臺北');
  assert.ok(C.sanitizeMapCommand({ v: 1, type: 'redline-controller-command', cmd: 'button', id: 'confirmMoveBtn' }));

  const snap = {
    type: 'redline-controller-map-snapshot', v: 1, seq: 3, scope: 'move',
    targets: [{ town: '臺北', role: 'origin', x: 1, y: 2 }],
    buttons: [{ id: 'confirmMoveBtn', label: '確認移動', x: 0, y: 0, w: 10, h: 10 }], focusTown: null, canCancel: true,
  };
  assert.equal(C.sanitizeMapSnapshot(snap).targets.length, 1);
  assert.equal(C.sanitizeMapSnapshot({ ...snap, scope: 'hax' }), null);
  assert.equal(C.sanitizeMapSnapshot({ ...snap, targets: [{ town: '臺北', role: 'origin', x: NaN, y: 0 }] }), null);
  assert.equal(C.sanitizeMapSnapshot({ ...snap, targets: [{ town: '', role: 'origin', x: 0, y: 0 }] }), null);
  assert.equal(C.sanitizeMapSnapshot({ ...snap, buttons: [{ id: 'advanceStepBtn', label: 'x', x: 0, y: 0, w: 1, h: 1 }] }), null);
  assert.equal(C.sanitizeMapSnapshot({ ...snap, v: 9 }), null);
  assert.equal(C.sanitizeMapSnapshot({ ...snap, targets: new Array(401).fill(snap.targets[0]) }), null);
});

test('map targets far off-screen (思想家 global targets after SL focus + ZR to zoom 10) stay valid; absurd points and button rects still fail closed', () => {
  // 思想家 → SL 聚焦利雅德（zoom 9）後再按 ZR 放大到 zoom 10 時，溫哥華等北美目標的 container x 約 −12 萬 px：舊的 10 萬上限讓整份 snapshot 作廢。
  const snap = {
    type: 'redline-controller-map-snapshot', v: 1, seq: 4, scope: 'choice', focusTown: '利雅德', canCancel: false, buttons: [],
    targets: [
      { town: '利雅德', role: 'choice', act: 'build', x: 450, y: 280 },
      { town: '溫哥華', role: 'choice', act: 'build', x: -123642, y: -22779 },
      { town: '奧克蘭', role: 'choice', act: 'build', x: 93271, y: 47481 },
    ],
  };
  const ok = C.sanitizeMapSnapshot(snap);
  assert.ok(ok, 'off-screen targets keep the whole snapshot (and the controller focus set) alive');
  assert.deepEqual(ok.targets.map(t => [t.town, t.x, t.y]), [['利雅德', 450, 280], ['溫哥華', -123642, -22779], ['奧克蘭', 93271, 47481]]);
  assert.equal(ok.focusTown, '利雅德');
  // 256px 圖磚在 zoom 22 的世界寬度以內都接受（戰略地圖 ZR 最大 10、SL 固定 9、fitBounds 最大 9）。
  const far = C.MAP_POINT_LIMIT - 1;
  assert.ok(C.sanitizeMapSnapshot({ ...snap, targets: [{ town: '溫哥華', role: 'choice', x: -far, y: far }] }));
  for (const bad of [NaN, Infinity, -Infinity, C.MAP_POINT_LIMIT, -C.MAP_POINT_LIMIT, '1', null]) {
    assert.equal(C.sanitizeMapSnapshot({ ...snap, targets: [{ town: '溫哥華', role: 'choice', x: bad, y: 0 }] }), null, `x=${bad}`);
    assert.equal(C.sanitizeMapSnapshot({ ...snap, targets: [{ town: '溫哥華', role: 'choice', x: 0, y: bad }] }), null, `y=${bad}`);
  }
  // 按鈕外框是 iframe 視窗內的 DOM rect：維持原本的上限。
  assert.equal(C.sanitizeMapSnapshot({ ...snap, buttons: [{ id: 'directBuildBtn', label: '建立組織', x: -123642, y: 0, w: 10, h: 10 }] }), null);
});

const mapInput = (over = {}) => ({
  hasState: true, viewerCanAct: true, pendingChoiceBlocksMoves: false, highlight: null,
  visibleTowns: ['甲', '乙', '丙', '丁'], knownTowns: ['甲', '乙', '丙', '丁', '戊'],
  moveTargets: [{ town: '乙' }], selectedTown: '甲', originTowns: ['甲', '丙'], buttons: [], ...over,
});

test('map fail-closed: no state / not my turn / pending choice without highlight → no targets', () => {
  assert.equal(C.buildMapSnapshotModel(mapInput({ hasState: false })).targets.length, 0);
  assert.equal(C.buildMapSnapshotModel(mapInput({ viewerCanAct: false })).targets.length, 0);
  assert.equal(C.buildMapSnapshotModel(mapInput({ pendingChoiceBlocksMoves: true })).scope, 'none');
  assert.equal(C.buildMapSnapshotModel(null).scope, 'none');
});

test('map targets come only from authoritative lists; unknown / filtered-out towns are dropped', () => {
  const m = C.buildMapSnapshotModel(mapInput({ moveTargets: [{ town: '乙' }, { town: '不存在' }, { town: '戊' }] }));
  assert.equal(m.scope, 'move');
  assert.deepEqual(m.targets.map(t => `${t.town}:${t.role}`), ['乙:move', '甲:origin', '丙:origin']);
  assert.equal(m.focusTown, '甲');
});

test('pending-choice highlight replaces move/origin targets and is filtered to visible, known towns', () => {
  const m = C.buildMapSnapshotModel(mapInput({
    highlight: { towns: [{ town: '丁' }, { town: '戊' }, { town: '幽靈' }, { town: '丁' }], focusTown: '丁' },
  }));
  assert.equal(m.scope, 'choice');
  assert.deepEqual(m.targets, [{ town: '丁', role: 'choice' }]);
  assert.equal(m.focusTown, '丁');
  // choice highlight still works when the viewer is not otherwise able to act, but still needs state
  assert.equal(C.buildMapSnapshotModel(mapInput({ viewerCanAct: false, highlight: { towns: [{ town: '丁' }] } })).scope, 'choice');
  assert.equal(C.buildMapSnapshotModel(mapInput({ hasState: false, highlight: { towns: [{ town: '丁' }] } })).scope, 'none');
});

test('map act command: requires a town and one of the three existing Y buttons', () => {
  const act = (extra) => C.sanitizeMapCommand({ v: 1, type: 'redline-controller-command', cmd: 'act', town: '臺北', id: 'directBuildBtn', req: 3, ...extra });
  assert.deepEqual(act({}), { cmd: 'act', town: '臺北', id: 'directBuildBtn', req: 3 });
  for (const id of ['confirmMoveBtn', 'dissolveBtn']) assert.equal(act({ id }).id, id);
  for (const id of ['cancelDissolveChoiceBtn', 'advanceStepBtn', 'openPurchaseConfirmBtn', undefined]) assert.equal(act({ id }), null, String(id));
  assert.equal(act({ town: '' }), null);
  assert.equal(act({ town: undefined }), null);
  assert.deepEqual(C.MAP_ACTS, { build: 'directBuildBtn', move: 'confirmMoveBtn', dissolve: 'dissolveBtn' });
});

test('map act command: a correlated request id is mandatory (absent or invalid req is rejected)', () => {
  const base = { v: 1, type: 'redline-controller-command', cmd: 'act', town: '臺北', id: 'confirmMoveBtn' };
  assert.equal(C.sanitizeMapCommand(base), null, 'req absent');
  for (const req of [null, undefined, 0, -1, 1.5, '3', NaN, Infinity, Number.MAX_SAFE_INTEGER + 2, true, {}, [7]]) {
    assert.equal(C.sanitizeMapCommand({ ...base, req }), null, `req=${String(req)}`);
  }
  assert.equal(C.sanitizeMapCommand({ ...base, req: 1 }).req, 1);
  assert.equal(C.sanitizeMapCommand({ ...base, req: Number.MAX_SAFE_INTEGER }).req, Number.MAX_SAFE_INTEGER);
  // the iframe's act result must carry the same correlation; a req-less act result is not an acknowledgment
  const result = (extra) => C.sanitizeMapResult({ type: 'redline-controller-result', v: 1, cmd: 'act', ok: true, ...extra });
  assert.equal(result({}), null);
  assert.equal(result({ req: null }), null);
  assert.equal(result({ req: 0 }), null);
  assert.equal(result({ req: 9 }).req, 9);
});

test('desktop map commands that intentionally omit req are unchanged', () => {
  const cmd = (extra) => C.sanitizeMapCommand({ v: 1, type: 'redline-controller-command', ...extra });
  assert.deepEqual(cmd({ cmd: 'snapshot' }), { cmd: 'snapshot', town: undefined, id: undefined, req: null });
  assert.deepEqual(cmd({ cmd: 'clearFocus' }), { cmd: 'clearFocus', town: undefined, id: undefined, req: null });
  assert.deepEqual(cmd({ cmd: 'focus', town: '臺北' }), { cmd: 'focus', town: '臺北', id: undefined, req: null });
  assert.deepEqual(cmd({ cmd: 'activate', town: '臺北' }), { cmd: 'activate', town: '臺北', id: undefined, req: null });
  assert.deepEqual(cmd({ cmd: 'button', id: 'directBuildBtn' }), { cmd: 'button', town: undefined, id: 'directBuildBtn', req: null });
  assert.deepEqual(cmd({ cmd: 'cancel' }), { cmd: 'cancel', town: undefined, id: undefined, req: null });
  // living-room requests on those commands keep their optional req
  assert.equal(cmd({ cmd: 'activate', town: '臺北', req: 4 }).req, 4);
  assert.equal(cmd({ cmd: 'cancel', req: 5 }).req, 5);
  // results for req-less commands also stay accepted (req:null)
  assert.equal(C.sanitizeMapResult({ type: 'redline-controller-result', v: 1, cmd: 'button', ok: true }).req, null);
});

test('map target action is derived only from scope, role and authoritative flags', () => {
  assert.equal(C.mapTargetAct('choice', 'choice', { choiceKind: 'build' }), 'build');
  assert.equal(C.mapTargetAct('choice', 'choice', { choiceKind: 'dissolve' }), 'dissolve');
  assert.equal(C.mapTargetAct('choice', 'choice', { choiceKind: 'other' }), null);
  assert.equal(C.mapTargetAct('move', 'move', {}), 'move');
  assert.equal(C.mapTargetAct('move', 'origin', { dissolveOrigin: true }), 'dissolve');
  assert.equal(C.mapTargetAct('move', 'origin', {}), null);
  assert.equal(C.mapTargetAct('none', 'move', {}), null);
  assert.equal(C.mapTargetAct('move', 'choice', { choiceKind: 'build' }), null);
});

test('map buttons: only whitelisted, visible and enabled existing buttons', () => {
  const m = C.buildMapSnapshotModel(mapInput({ buttons: [
    { id: 'confirmMoveBtn', visible: true, disabled: false, label: '確認移動' },
    { id: 'directBuildBtn', visible: true, disabled: true, label: '建立組織' },
    { id: 'dissolveBtn', visible: false, disabled: false, label: '瓦解' },
    { id: 'advanceStepBtn', visible: true, disabled: false, label: '結束' },
  ] }));
  assert.deepEqual(m.buttons.map(b => b.id), ['confirmMoveBtn']);
});

test('bridge URL settings: loopback only, defaults, persistence shape', () => {
  assert.equal(C.validateBridgeUrl('ws://127.0.0.1:8000/ws'), 'ws://127.0.0.1:8000/ws');
  assert.equal(C.validateBridgeUrl('ws://localhost:9000/ws'), 'ws://localhost:9000/ws');
  assert.equal(C.validateBridgeUrl('ws://192.168.1.5:8000/ws'), null);
  assert.equal(C.validateBridgeUrl('http://127.0.0.1:8000'), null);
  assert.equal(C.validateBridgeUrl('ws://evil.com/ws'), null);
  assert.equal(C.validateBridgeUrl('ws://u:p@127.0.0.1/ws'), null);
  assert.equal(C.validateBridgeUrl(42), null);
  assert.deepEqual(C.normalizeSettings(null), { enabled: false, url: C.DEFAULT_BRIDGE_URL });
  assert.deepEqual(C.normalizeSettings({ enabled: 'yes', url: 'ws://x.example/ws' }), { enabled: false, url: C.DEFAULT_BRIDGE_URL });
  assert.deepEqual(C.normalizeSettings({ enabled: true, url: 'ws://127.0.0.1:8123/ws' }), { enabled: true, url: 'ws://127.0.0.1:8123/ws' });
  assert.equal(C.mixedContentRisk('https:', 'ws://127.0.0.1:8000/ws'), true);
  assert.equal(C.mixedContentRisk('http:', 'ws://127.0.0.1:8000/ws'), false);
  assert.equal(C.reconnectDelayMs(0), 1000);
  assert.equal(C.reconnectDelayMs(99), 8000);
});

// ---- 卡牌 scope：A 查看 / B 勾選 / 手牌 X 資源 / 手牌 Y 行動 ----
const cardCtx = (card, extra = {}) => ({ scopeKind: 'page', hasFocus: true, cancelAvailable: false, sectionsLocked: false, card, ...extra });
const handCard = { zone: 'hand', hasToggle: false };
const buyCard = { zone: 'purchase', hasToggle: true };
const X = { name: 'focusTurnBar' };
const Y = { name: 'toggleHelp' };

test('card focus: A previews and never activates/toggles/buys', () => {
  for (const card of [handCard, buyCard, { zone: 'discard', hasToggle: false }]) {
    assert.deepEqual(C.routeAction(cardCtx(card), { name: 'confirm' }), { cmd: 'cardPreview' }, card.zone);
  }
  assert.equal(C.routeAction(cardCtx(handCard, { hasFocus: false }), { name: 'confirm' }), null);
  assert.deepEqual(C.routeAction(cardCtx(null), { name: 'confirm' }), { cmd: 'activate' });
});

test('card focus: B toggles only on checkable cards, otherwise keeps legacy cancel', () => {
  assert.deepEqual(C.routeAction(cardCtx(buyCard), { name: 'cancel' }), { cmd: 'cardToggle' });
  assert.equal(C.routeAction(cardCtx(handCard), { name: 'cancel' }), null);
  assert.deepEqual(C.routeAction(cardCtx(handCard, { cancelAvailable: true }), { name: 'cancel' }), { cmd: 'cancel' });
  assert.deepEqual(C.routeAction(cardCtx(null, { cancelAvailable: true }), { name: 'cancel' }), { cmd: 'cancel' });
  assert.deepEqual(C.routeAction(cardCtx(null, { scopeKind: 'modal', cancelAvailable: true }), { name: 'cancel' }), { cmd: 'cancel' });
});

test('hand card focus: X = resource, Y = action', () => {
  assert.deepEqual(C.routeAction(cardCtx(handCard), X), { cmd: 'cardMode', mode: 'resource' });
  assert.deepEqual(C.routeAction(cardCtx(handCard), Y), { cmd: 'cardMode', mode: 'action' });
});

test('hand card X: ordinary support card with an existing 棄置 control = cardDiscard (confirm flow); others keep resource', () => {
  const aid = { zone: 'hand', hasToggle: false, hasDiscard: true };
  assert.deepEqual(C.routeAction(cardCtx(aid), X), { cmd: 'cardDiscard' });
  assert.deepEqual(C.routeAction(cardCtx(aid, { sectionsLocked: true }), X), { cmd: 'cardDiscard' });
  assert.deepEqual(C.routeAction(cardCtx(aid), Y), { cmd: 'cardMode', mode: 'action' }, 'Y stays action');
  // 紅軍奧援的既有按鈕是「資源」→ hasDiscard false → X 仍＝資源；未帶 hasDiscard（或非 true）一律不視為可棄置。
  for (const card of [handCard, { zone: 'hand', hasToggle: false, hasDiscard: false }, { zone: 'hand', hasToggle: false, hasDiscard: 'yes' }]) {
    assert.deepEqual(C.routeAction(cardCtx(card), X), { cmd: 'cardMode', mode: 'resource' });
  }
  assert.equal(C.routeAction(cardCtx({ zone: 'purchase', hasToggle: true, hasDiscard: true }), X), null, 'never outside the hand');
  assert.equal(C.routeAction(cardCtx(aid, { hasFocus: false }), X), null);
  assert.equal(C.routeAction(cardCtx(aid, { scopeKind: 'modal' }), X), null, 'never from inside a modal');
});

test('hand card B never discards: support cards keep the generic cancel semantics', () => {
  const aid = { zone: 'hand', hasToggle: false, hasDiscard: true };
  assert.equal(C.routeAction(cardCtx(aid), { name: 'cancel' }), null);
  assert.deepEqual(C.routeAction(cardCtx(aid, { cancelAvailable: true }), { name: 'cancel' }), { cmd: 'cancel' });
  assert.deepEqual(C.routeAction(cardCtx(aid, { scopeKind: 'modal', cancelAvailable: true }), { name: 'cancel' }), { cmd: 'cancel' });
});

test('non-hand card focus: X is a full no-op; Y is a no-op except the purchase-card buy flow', () => {
  for (const card of [buyCard, { zone: 'discard', hasToggle: false }]) assert.equal(C.routeAction(cardCtx(card), X), null, card.zone);
  assert.equal(C.routeAction(cardCtx({ zone: 'discard', hasToggle: false }), Y), null);
  assert.equal(C.routeAction(cardCtx(buyCard, { sectionsLocked: true }), X), null);
});

test('purchase card focus: B checks, Y opens the existing buy flow (the UI requires a B-checked card)', () => {
  assert.deepEqual(C.routeAction(cardCtx(buyCard), { name: 'cancel' }), { cmd: 'cardToggle' }, 'B stays the checkbox toggle');
  assert.deepEqual(C.routeAction(cardCtx(buyCard), Y), { cmd: 'cardBuy' });
  assert.deepEqual(C.routeAction(cardCtx(buyCard, { sectionsLocked: true }), Y), { cmd: 'cardBuy' });
  assert.equal(C.routeAction(cardCtx(buyCard, { hasFocus: false }), Y), null);
  assert.equal(C.routeAction(cardCtx(buyCard, { scopeKind: 'modal' }), Y), null, 'never from inside a modal');
});

test('map target focus: Y = the focused target\'s existing map action; other focus keeps legacy Y', () => {
  const map = { scopeKind: 'map', hasFocus: true, cancelAvailable: false, sectionsLocked: true, card: null };
  assert.deepEqual(C.routeAction({ ...map, mapTarget: true }, Y), { cmd: 'mapAct' }, 'pending build choice');
  assert.deepEqual(C.routeAction({ ...map, sectionsLocked: false, mapTarget: true }, Y), { cmd: 'mapAct' });
  assert.deepEqual(C.routeAction({ ...map, mapTarget: false }, Y), { cmd: 'toggleHelp' }, 'map button ring');
  assert.deepEqual(C.routeAction({ ...map, mapTarget: true, hasFocus: false }, Y), { cmd: 'toggleHelp' });
  assert.deepEqual(C.routeAction({ ...cardCtx(null), mapTarget: true }, Y), { cmd: 'toggleHelp' }, 'only the map scope');
  assert.deepEqual(C.routeAction({ ...map, mapTarget: true }, { name: 'confirm' }), { cmd: 'activate' }, 'A still only selects / arms');
  assert.equal(C.routeAction({ ...map, mapTarget: true }, X)?.cmd, undefined, 'X is unchanged (locked map: no turn bar)');
});

test('non-card focus keeps legacy X/Y', () => {
  assert.deepEqual(C.routeAction(cardCtx(null), X), { cmd: 'focusTurnBar' });
  assert.deepEqual(C.routeAction(cardCtx(null), Y), { cmd: 'toggleHelp' });
});

test('hand card X/Y never map to card modes without focus or inside a modal scope', () => {
  assert.equal(C.routeAction(cardCtx(handCard, { hasFocus: false }), X), null);
  assert.equal(C.routeAction(cardCtx(handCard, { hasFocus: false }), Y), null);
  assert.equal(C.routeAction(cardCtx(handCard, { scopeKind: 'modal' }), X), null);
  assert.equal(C.routeAction(cardCtx(handCard, { scopeKind: 'modal' }), Y), null);
  assert.equal(C.routeAction(cardCtx(handCard, { sectionsLocked: true }), X)?.cmd, 'cardMode');
});

test('A/B on non-card scopes are unchanged (map, modal, notices, plain buttons)', () => {
  for (const scopeKind of ['modal', 'map', 'page']) {
    const ctx = { scopeKind, hasFocus: true, cancelAvailable: true, sectionsLocked: false, card: null };
    assert.deepEqual(C.routeAction(ctx, { name: 'confirm' }), { cmd: 'activate' });
    assert.deepEqual(C.routeAction(ctx, { name: 'cancel' }), { cmd: 'cancel' });
  }
});

test('card context is optional: legacy ctx without card behaves as before', () => {
  const legacy = { scopeKind: 'page', hasFocus: true, cancelAvailable: false, sectionsLocked: false };
  assert.deepEqual(C.routeAction(legacy, X), { cmd: 'focusTurnBar' });
  assert.deepEqual(C.routeAction(legacy, { name: 'confirm' }), { cmd: 'activate' });
});

test('B cancel does not require focus (focus-less modals such as card preview still close)', () => {
  const ctx = { scopeKind: 'modal', hasFocus: false, cancelAvailable: true, sectionsLocked: false, card: null };
  assert.deepEqual(C.routeAction(ctx, { name: 'cancel' }), { cmd: 'cancel' });
});

test('card checkboxes are never directional focus targets; the whole card is', () => {
  const base = { scope: 'page', visible: true, disabled: false, ariaDisabled: false, skip: false, left: 0, top: 0, right: 10, bottom: 10 };
  const items = [
    { ...base, key: 'static-card' },
    { ...base, key: 'static-checkbox', cardCheckbox: true },
    { ...base, key: 'random-card' },
    { ...base, key: 'random-checkbox', cardCheckbox: true },
    { ...base, key: 'plain-checkbox' },
  ];
  assert.deepEqual(C.buildFocusSet(items, 'page').map(i => i.key), ['static-card', 'random-card', 'plain-checkbox']);
  assert.equal(C.isFocusableCandidate({ ...base, cardCheckbox: true }), false);
  assert.equal(C.isFocusableCandidate({ ...base, cardCheckbox: false }), true);
});

test('directional set holds only allowed content: six section tabs and end-step never enter it (R/SR and Capture only)', () => {
  const base = { scope: 'page', visible: true, disabled: false, ariaDisabled: false, skip: false };
  const items = [
    ...['command', 'map', 'log', 'myFaction', 'event', 'era'].map((k, i) => ({
      ...base, key: `tab-${k}`, sectionTab: true, top: 0, bottom: 10, left: i * 20, right: i * 20 + 10 })),
    { ...base, key: 'end-step', turnControl: true, top: 0, bottom: 10, left: 200, right: 210 },
    { ...base, key: 'hand-card', top: 50, bottom: 60, left: 0, right: 10 },
  ];
  const set = C.buildFocusSet(items, 'page');
  assert.deepEqual(set.map(i => i.key), ['hand-card']);
  assert.equal(C.pickInitial(set).key, 'hand-card');
  // existing contract: no candidate in that direction → stay on the current item
  for (const dir of ['up', 'down', 'left', 'right']) assert.equal(C.pickDirectional(set, 'hand-card', dir).key, 'hand-card', dir);
});

test('hand-card 資源/行動/棄置, hint bar, faction ability and card checkboxes never enter the directional set', () => {
  const base = { scope: 'page', visible: true, disabled: false, ariaDisabled: false, skip: false, left: 0, right: 10 };
  const items = [
    { ...base, key: 'hand-card-0', top: 0, bottom: 10 },
    { ...base, key: 'hand-0-resource', handAction: true, top: 20, bottom: 30 },
    { ...base, key: 'hand-0-action', handAction: true, top: 20, bottom: 30, left: 12, right: 22 },
    { ...base, key: 'hand-card-1', top: 40, bottom: 50 },
    { ...base, key: 'hand-1-discard', handAction: true, top: 60, bottom: 70 },
    { ...base, key: 'hint-bar', hintBar: true, top: 80, bottom: 90 },
    { ...base, key: 'faction-ability', factionAbility: true, top: 100, bottom: 110 },
    { ...base, key: 'purchase-checkbox', cardCheckbox: true, top: 120, bottom: 130 },
  ];
  const set = C.buildFocusSet(items, 'page');
  assert.deepEqual(set.map(i => i.key), ['hand-card-0', 'hand-card-1']);
  assert.equal(C.pickDirectional(set, 'hand-card-0', 'down').key, 'hand-card-1', 'down from a hand card skips its buttons');
  assert.equal(C.pickDirectional(set, 'hand-card-1', 'down').key, 'hand-card-1', 'nothing allowed below → stays');
  for (const flag of ['sectionTab', 'turnControl', 'handAction', 'hintBar', 'factionAbility', 'cardCheckbox']) {
    assert.equal(C.isDirectionalExcluded({ [flag]: true }), true, flag);
    assert.equal(C.isFocusableCandidate({ ...base, top: 0, bottom: 1, [flag]: true }), false, flag);
  }
  assert.equal(C.isDirectionalExcluded({}), false);
  assert.equal(C.isDirectionalExcluded(null), true, 'unknown descriptor fails closed');
});

test('B on a focused purchase card toggles; disabled-checkbox handling stays in the UI (core still routes cardToggle)', () => {
  assert.deepEqual(C.routeAction(cardCtx({ zone: 'purchase', hasToggle: true }), { name: 'cancel' }), { cmd: 'cardToggle' });
});

test('Joy-Con help button focus: A opens the help image, B does nothing, R/SR keep cycling, SL still opens the focus menu', () => {
  for (const scopeKind of ['page', 'map']) {
    const ctx = { scopeKind, hasFocus: true, helpEntry: true, card: null, cancelAvailable: scopeKind === 'map', sectionsLocked: false };
    assert.deepEqual(C.routeAction(ctx, { name: 'confirm' }), { cmd: 'openHelp' }, scopeKind);
    assert.equal(C.routeAction(ctx, { name: 'cancel' }), null, `${scopeKind}: B never cancels a map flow from the help button`);
    assert.deepEqual(C.routeAction(ctx, { name: 'nextSection' }), { cmd: 'section', step: 1 });
    assert.deepEqual(C.routeAction(ctx, { name: 'prevSection' }), { cmd: 'section', step: -1 });
    assert.deepEqual(C.routeAction(ctx, { name: 'focusMenu' }), { cmd: 'focusMenu' }, 'global SL town focus unchanged');
    assert.deepEqual(C.routeAction(ctx, { name: 'move', dir: 'down' }), { cmd: 'move', dir: 'down' });
  }
  // 沒有 helpEntry 時一般焦點不變。
  assert.deepEqual(C.routeAction({ scopeKind: 'page', hasFocus: true }, { name: 'confirm' }), { cmd: 'activate' });
  // 方向焦點永遠不落在說明按鈕上（只由 R／SR 環到達）。
  assert.equal(C.isDirectionalExcluded({ helpEntry: true }), true);
  assert.equal(C.buildFocusSet([{ key: 'h', scope: 'page', visible: true, helpEntry: true }], 'page').length, 0);
});

test('Joy-Con help image modal is a scope lock: B closes via the close button; R/SR, SL, ZR, X never pass through', () => {
  const scope = C.MODAL_SCOPES.find(s => s.id === 'joyconHelpModal');
  assert.ok(scope);
  assert.deepEqual(scope.cancel, ['#joyconHelpCloseBtn']);
  assert.equal(C.resolveModalScope(['joyconHelpModal']).id, 'joyconHelpModal');
  // 說明圖蓋在一般頁面上：它優先於事件卡／時代關卡等（R／SR 可離開的）說明 modal。
  assert.equal(C.resolveModalScope(['eraAchievementModal', 'joyconHelpModal']).id, 'joyconHelpModal');
  const ctx = { scopeKind: 'modal', hasFocus: true, cancelAvailable: true, helpEntry: false };
  assert.deepEqual(C.routeAction(ctx, { name: 'cancel' }), { cmd: 'cancel' });
  for (const name of ['nextSection', 'prevSection', 'focusMenu', 'mapZoom', 'focusTurnBar']) {
    assert.equal(C.routeAction(ctx, { name }), null, name);
  }
  // 即使 helpEntry 旗標殘留，modal 內 A 也不會再開一次（照一般 modal 的 activate）。
  assert.deepEqual(C.routeAction({ ...ctx, helpEntry: true }, { name: 'confirm' }), { cmd: 'activate' });
});
