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

test('stale detection', () => {
  let r = C.reduceFrame(C.createInputState(), frame(), 1000);
  assert.equal(C.isStale(r.state, 1500), false);
  assert.equal(C.isStale(r.state, 2600), true);
  assert.equal(C.isStale(C.createInputState(), 0), true);
});

test('logical mapping: + / HOME / CAPTURE / ZR / STICK / SL never produce actions', () => {
  for (const b of ['PLUS', 'HOME', 'CAPTURE', 'ZR', 'STICK', 'SL']) {
    assert.equal(C.logicalAction({ type: 'press', button: b }), null, b);
  }
  assert.deepEqual(C.logicalAction({ type: 'press', button: 'A' }), { name: 'confirm' });
  assert.deepEqual(C.logicalAction({ type: 'press', button: 'R' }), { name: 'nextSection' });
  assert.deepEqual(C.logicalAction({ type: 'press', button: 'SR' }), { name: 'prevSection' });
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
