// node --test scripts/tests/js/living_room_core.test.js
const test = require('node:test');
const assert = require('node:assert/strict');
const LR = require('../../../static/living_room_core.js');
const C = require('../../../static/controller_core.js');

const press = button => LR.logicalAction({ type: 'press', button });
const nav = dir => LR.logicalAction({ type: 'nav', dir, repeat: false });
const zoneCtx = (extra = {}) => ({ scopeKind: 'page', view: 'command', layer: 'zone', zone: 'hand', locked: false, choiceLock: false, mapCanCancel: false, item: null, ...extra });
const itemCtx = (item, extra = {}) => zoneCtx({ layer: 'item', item, ...extra });
const handItem = { card: { zone: 'hand', hasToggle: false, hasDiscard: false }, mapRow: false };
const supportItem = { card: { zone: 'hand', hasToggle: false, hasDiscard: true }, mapRow: false };
const buyItem = { card: { zone: 'purchase', hasToggle: true, hasDiscard: false }, mapRow: false };
const rowItem = { card: null, mapRow: true };
const controlItem = { card: null, mapRow: false };
const mapCtx = (extra = {}) => itemCtx(rowItem, { zone: 'maplist', scopeKind: 'map', view: 'map', ...extra });

// ---- display mode ----

test('display mode: URL wins and persists, invalid URL falls back to storage, default desktop', () => {
  assert.deepEqual(LR.resolveDisplayMode('?display=living-room', null), { mode: 'living-room', persist: true });
  assert.deepEqual(LR.resolveDisplayMode('?game_id=1&display=desktop', 'living-room'), { mode: 'desktop', persist: true });
  assert.deepEqual(LR.resolveDisplayMode('?display=tv-hax', 'living-room'), { mode: 'living-room', persist: false });
  assert.deepEqual(LR.resolveDisplayMode('', null), { mode: 'desktop', persist: false });
  assert.deepEqual(LR.resolveDisplayMode('', 'garbage'), { mode: 'desktop', persist: false });
  assert.equal(LR.SAFE_AREA_SCALE, 0.9);
});

// ---- logical actions ----

test('living-room key map: PLUS = faction ability, CAPTURE = end step, STICK = next zone, ZR = zone back', () => {
  assert.deepEqual(press('PLUS'), { name: 'factionAbility' });
  assert.deepEqual(press('CAPTURE'), { name: 'endStep' });
  assert.deepEqual(press('STICK'), { name: 'nextZone' });
  assert.deepEqual(press('ZR'), { name: 'zoneBack' });
  for (const b of ['HOME', 'SL']) assert.equal(press(b), null, b);
  // desktop mapping is untouched: + / CAPTURE / STICK / ZR still do nothing there
  for (const b of ['PLUS', 'CAPTURE', 'STICK', 'ZR', 'HOME', 'SL']) assert.equal(C.logicalAction({ type: 'press', button: b }), null, `desktop ${b}`);
});

// ---- router: global keys (any layer, page or map scope) ----

const allCtxs = () => [
  zoneCtx(), zoneCtx({ zone: null }), itemCtx(handItem), itemCtx(supportItem), itemCtx(buyItem), itemCtx(controlItem, { zone: 'faction' }),
  mapCtx(), zoneCtx({ view: 'map', scopeKind: 'map', zone: 'maplist' }), zoneCtx({ view: 'log', zone: 'view' }),
];

test('Capture always routes to the existing end-step flow (the UI re-validates and confirms)', () => {
  for (const ctx of allCtxs()) assert.deepEqual(LR.routeLivingRoom(ctx, press('CAPTURE')), { cmd: 'endStep' });
});

test('PLUS always routes to the faction ability and never to a focus jump or the end step', () => {
  for (const ctx of allCtxs()) assert.deepEqual(LR.routeLivingRoom(ctx, press('PLUS')), { cmd: 'factionAbility' });
});

test('STICK cycles content zones in every layer (focus only)', () => {
  for (const ctx of allCtxs()) assert.deepEqual(LR.routeLivingRoom(ctx, press('STICK')), { cmd: 'zoneCycle', step: 1 });
});

test('R/SR route to the global section ring from every layer; a pending map choice blocks them on the map', () => {
  for (const ctx of allCtxs()) {
    assert.deepEqual(LR.routeLivingRoom({ ...ctx, choiceLock: false, locked: false }, press('R')), { cmd: 'section', step: 1 });
    assert.deepEqual(LR.routeLivingRoom({ ...ctx, choiceLock: false, locked: false }, press('SR')), { cmd: 'section', step: -1 });
  }
  // choice lock: on the map R/SR do nothing; elsewhere they still route (the ring only offers the map)
  assert.equal(LR.routeLivingRoom(mapCtx({ choiceLock: true, locked: true }), press('R')), null);
  assert.equal(LR.routeLivingRoom(zoneCtx({ view: 'map', scopeKind: 'map', zone: 'maplist', choiceLock: true, locked: true }), press('SR')), null);
  assert.deepEqual(LR.routeLivingRoom(zoneCtx({ choiceLock: true }), press('R')), { cmd: 'section', step: 1 });
});

// ---- router: zone layer ----

test('zone layer: stick moves between content zones, A enters, B and X are no-ops, Y help', () => {
  assert.deepEqual(LR.routeLivingRoom(zoneCtx(), nav('down')), { cmd: 'zoneMove', dir: 'down' });
  assert.deepEqual(LR.routeLivingRoom(zoneCtx(), press('A')), { cmd: 'enterZone' });
  assert.equal(LR.routeLivingRoom(zoneCtx(), press('B')), null);
  assert.equal(LR.routeLivingRoom(zoneCtx(), press('X')), null, 'X no longer jumps to an action bar');
  assert.deepEqual(LR.routeLivingRoom(zoneCtx(), press('Y')), { cmd: 'toggleHelp' });
  assert.equal(LR.routeLivingRoom(zoneCtx({ zone: null }), press('A')), null);
  assert.equal(LR.routeLivingRoom(zoneCtx({ zone: null }), nav('up')), null, 'no zone: the stick has nothing to move');
});

test('zone layer ZR: no-op in command view, returns to command view elsewhere unless the map is locked', () => {
  assert.equal(LR.routeLivingRoom(zoneCtx(), press('ZR')), null);
  assert.deepEqual(LR.routeLivingRoom(zoneCtx({ view: 'log', zone: 'view' }), press('ZR')), { cmd: 'leaveView' });
  assert.deepEqual(LR.routeLivingRoom(zoneCtx({ view: 'map', scopeKind: 'map', zone: 'maplist' }), press('ZR')), { cmd: 'leaveView' });
  assert.equal(LR.routeLivingRoom(zoneCtx({ view: 'map', scopeKind: 'map', zone: 'maplist', locked: true }), press('ZR')), null);
});

// ---- router: item layer cards ----

test('purchase card: A preview, B toggle, X no-op, Y = existing buy flow', () => {
  assert.deepEqual(LR.routeLivingRoom(itemCtx(buyItem), press('A')), { cmd: 'cardPreview' });
  assert.deepEqual(LR.routeLivingRoom(itemCtx(buyItem), press('B')), { cmd: 'cardToggle' });
  assert.equal(LR.routeLivingRoom(itemCtx(buyItem), press('X')), null);
  assert.deepEqual(LR.routeLivingRoom(itemCtx(buyItem), press('Y')), { cmd: 'cardBuy' });
});

test('hand card: A preview, X resource, Y action; B discards only when the card has a discard control', () => {
  for (const item of [handItem, supportItem]) {
    assert.deepEqual(LR.routeLivingRoom(itemCtx(item), press('A')), { cmd: 'cardPreview' });
    assert.deepEqual(LR.routeLivingRoom(itemCtx(item), press('X')), { cmd: 'cardMode', mode: 'resource' });
    assert.deepEqual(LR.routeLivingRoom(itemCtx(item), press('Y')), { cmd: 'cardMode', mode: 'action' });
  }
  assert.equal(LR.routeLivingRoom(itemCtx(handItem), press('B')), null, 'no discard control: keep the legacy B no-op');
  assert.deepEqual(LR.routeLivingRoom(itemCtx(supportItem), press('B')), { cmd: 'cardDiscard' });
});

test('unchanged card semantics still match desktop routing; only purchase Y and hand-discard B are new', () => {
  const changed = new Set(['purchase:Y', 'hand+discard:B']);
  for (const [tag, item] of [['hand', handItem], ['hand+discard', supportItem], ['purchase', buyItem]]) {
    for (const button of ['A', 'B', 'X', 'Y']) {
      const lr = LR.routeLivingRoom(itemCtx(item), press(button));
      const desktop = C.routeAction({ scopeKind: 'page', hasFocus: true, card: item.card, cancelAvailable: false, sectionsLocked: false }, C.logicalAction({ type: 'press', button }));
      if (changed.has(`${tag}:${button}`)) assert.notDeepEqual(lr, desktop, `${tag}:${button}`);
      else assert.deepEqual(lr, desktop, `${tag}:${button}`);
    }
  }
});

test('item layer: stick moves inside the zone, ZR returns to the zone layer', () => {
  assert.deepEqual(LR.routeLivingRoom(itemCtx(handItem), nav('right')), { cmd: 'itemMove', dir: 'right' });
  assert.deepEqual(LR.routeLivingRoom(itemCtx(handItem), press('ZR')), { cmd: 'toZoneLayer' });
  assert.deepEqual(LR.routeLivingRoom(itemCtx(buyItem), press('ZR')), { cmd: 'toZoneLayer' });
});

test('item layer non-card control: A activates, B returns to zone layer, X no-op, Y help', () => {
  const ctrl = itemCtx(controlItem, { zone: 'faction' });
  assert.deepEqual(LR.routeLivingRoom(ctrl, press('A')), { cmd: 'activate' });
  assert.deepEqual(LR.routeLivingRoom(ctrl, press('B')), { cmd: 'toZoneLayer' });
  assert.equal(LR.routeLivingRoom(ctrl, press('X')), null);
  assert.deepEqual(LR.routeLivingRoom(ctrl, press('Y')), { cmd: 'toggleHelp' });
});

test('map list row: A picks, Y runs the target\'s existing map action, B cancels via the existing flow', () => {
  assert.deepEqual(LR.routeLivingRoom(mapCtx(), press('A')), { cmd: 'mapPick' });
  assert.deepEqual(LR.routeLivingRoom(mapCtx(), press('Y')), { cmd: 'mapAct' });
  assert.equal(LR.routeLivingRoom(mapCtx(), press('X')), null);
  assert.deepEqual(LR.routeLivingRoom(mapCtx({ mapCanCancel: true }), press('B')), { cmd: 'mapCancel' });
  assert.deepEqual(LR.routeLivingRoom(mapCtx({}), press('B')), { cmd: 'toZoneLayer' });
  assert.equal(LR.routeLivingRoom(mapCtx({ locked: true }), press('B')), null);
  assert.deepEqual(LR.routeLivingRoom(mapCtx({ locked: true, mapCanCancel: true }), press('B')), { cmd: 'mapCancel' });
  assert.equal(LR.routeLivingRoom(mapCtx({ locked: true }), press('ZR')), null);
  // empty map list (no row focused): A and Y do nothing
  assert.equal(LR.routeLivingRoom(itemCtx(null, { zone: 'maplist', scopeKind: 'map', view: 'map' }), press('A')), null);
  assert.equal(LR.routeLivingRoom(itemCtx(null, { zone: 'maplist', scopeKind: 'map', view: 'map' }), press('Y')), null);
});

// ---- directional focus set ----

test('directional focus excludes hand buttons, end/turn controls, the six global tabs, card checkboxes, ability buttons and the hint bar', () => {
  for (const key of ['handAction', 'cardCheckbox', 'sectionTab', 'turnControl', 'hintBar', 'factionAbility']) {
    assert.equal(LR.isDirectionalExcluded({ [key]: true }), true, key);
  }
  assert.equal(LR.isDirectionalExcluded({}), false, 'plain content control (e.g. base choice) stays');
  assert.equal(LR.isDirectionalExcluded(null), true, 'unknown element fails closed');
});

test('desktop and living-room share one directional exclusion predicate', () => {
  assert.equal(typeof C.isDirectionalExcluded, 'function');
  assert.equal(LR.isDirectionalExcluded, C.isDirectionalExcluded);
});

test('content zones never include the old status / map portal / action bar zones', () => {
  const all = Object.values(LR.CONTENT_ZONES).flat();
  for (const banned of ['status', 'map', 'actionbar']) assert.equal(all.includes(banned), false, banned);
  assert.deepEqual(LR.CONTENT_ZONES.command, ['static', 'random', 'faction', 'hand', 'activity']);
  assert.deepEqual(LR.CONTENT_ZONES.map, ['maplist']);
  assert.deepEqual(LR.CONTENT_ZONES.other, ['view']);
  assert.deepEqual(LR.contentZonesFor('command', { choiceLock: true }), [], 'pending map choice: no command-view content');
  assert.deepEqual(LR.contentZonesFor('log', { choiceLock: true }), []);
  assert.deepEqual(LR.contentZonesFor('map', { choiceLock: true }), ['maplist']);
  assert.deepEqual(LR.contentZonesFor('myFaction', {}), ['view']);
});

// ---- global section ring (R / SR) ----

const stops = (...keys) => keys.map(k => (typeof k === 'string' ? { key: k, usable: true } : k));
const FULL = stops('view:command', 'view:map', 'view:log', 'view:myFaction', 'event', 'era:7', 'era:9');

test('section keys map only to the six global sections', () => {
  assert.equal(LR.sectionOfKey('view:command'), 'command');
  assert.equal(LR.sectionOfKey('view:myFaction'), 'myFaction');
  assert.equal(LR.sectionOfKey('event'), 'event');
  assert.equal(LR.sectionOfKey('era:7'), 'era');
  for (const bad of ['view:hax', 'era:', 'hand', 'advanceStepBtn', null, undefined, 42]) assert.equal(LR.sectionOfKey(bad), null, String(bad));
  assert.deepEqual(Object.keys(LR.SECTION_LABELS), ['command', 'map', 'log', 'myFaction', 'event', 'era']);
});

test('R/SR cycle the six sections in tab order, skipping unavailable stops and wrapping', () => {
  assert.equal(LR.stepSection(FULL, 'view:command', 1), 'view:map');
  assert.equal(LR.stepSection(FULL, 'view:myFaction', 1), 'event');
  assert.equal(LR.stepSection(FULL, 'event', 1), 'era:7');
  assert.equal(LR.stepSection(FULL, 'era:7', 1), 'era:9');
  assert.equal(LR.stepSection(FULL, 'era:9', 1), 'view:command', 'wraps');
  assert.equal(LR.stepSection(FULL, 'view:command', -1), 'era:9');
  const noEvent = stops('view:command', 'view:map', 'view:log', 'view:myFaction', { key: 'event', usable: false });
  assert.equal(LR.stepSection(noEvent, 'view:myFaction', 1), 'view:command', 'hidden event tab is skipped');
  assert.equal(LR.stepSection(noEvent, 'view:command', -1), 'view:myFaction');
  // anything that is not one of the six sections is never a stop
  const polluted = [...stops('view:command'), { key: 'advanceStepBtn', usable: true }, { key: 'hand', usable: true }, ...stops('view:map')];
  assert.equal(LR.stepSection(polluted, 'view:command', 1), 'view:map');
  assert.equal(LR.stepSection(polluted, 'view:map', 1), 'view:command');
  // only the current stop is usable → nothing to switch to
  assert.equal(LR.stepSection(stops('view:command', { key: 'view:map', usable: false }), 'view:command', 1), null);
  assert.equal(LR.stepSection([], 'view:command', 1), null);
  // unknown current: R starts at the first usable stop, SR at the last
  assert.equal(LR.stepSection(FULL, 'gone', 1), 'view:command');
  assert.equal(LR.stepSection(FULL, 'gone', -1), 'era:9');
});

test('section ring scope lock: a pending map choice only offers the strategic map', () => {
  assert.equal(LR.stepSection(FULL, 'view:command', 1, { choiceLock: true, view: 'command' }), 'view:map');
  assert.equal(LR.stepSection(FULL, 'view:log', -1, { choiceLock: true, view: 'log' }), 'view:map');
  assert.equal(LR.stepSection(FULL, 'view:map', 1, { choiceLock: true, view: 'map' }), null);
  assert.equal(LR.stepSection(stops('view:command', { key: 'view:map', usable: false }), 'view:command', 1, { choiceLock: true, view: 'command' }), null);
});

test('only the two read-only section modals let R/SR step out; every other modal keeps its scope lock', () => {
  assert.deepEqual([...LR.SECTION_MODALS.keys()].sort(), ['eraAchievementModal', 'eventRevealModal']);
  for (const id of C.MODAL_SCOPES.map(s => s.id)) {
    if (id === 'eventRevealModal' || id === 'eraAchievementModal') continue;
    assert.equal(LR.SECTION_MODALS.has(id), false, id);
  }
});

// ---- guard ----

test('processing lock blocks submits until the next authoritative state or timeout; focus moves stay allowed', () => {
  let g = LR.lockProcessing(LR.createGuard(), 1000, 7);
  for (const cmd of ['activate', 'cardMode', 'cardToggle', 'cardDiscard', 'cardBuy', 'mapPick', 'mapAct', 'mapCancel', 'endStep', 'factionAbility']) {
    assert.equal(LR.gate(g, 1100, 7, cmd).allowed, false, cmd);
    assert.equal(LR.gate(g, 1100, 7, cmd).reason, 'processing');
  }
  for (const cmd of ['itemMove', 'zoneMove', 'zoneCycle', 'toZoneLayer', 'section', 'cardPreview', 'toggleHelp']) {
    assert.equal(LR.gate(g, 1100, 7, cmd).allowed, true, cmd);
  }
  const after = LR.gate(g, 1100, 8, 'cardMode');
  assert.equal(after.allowed, true);
  assert.equal(after.guard.lockedAt, null);
  assert.equal(LR.gate(g, 1000 + LR.DEFAULT_GUARD_CONFIG.processingTimeoutMs, 7, 'activate').allowed, true);
  g = LR.createGuard();
  assert.equal(LR.processingActive(g, 0, 1), false);
});

test('redraw cooldown ignores focus-dependent A/B/X/Y commands; global Capture / + are not focus-dependent', () => {
  const g = LR.noteRedraw(LR.createGuard(), 5000);
  for (const cmd of ['activate', 'cardMode', 'cardPreview', 'cardDiscard', 'cardBuy', 'enterZone', 'mapPick', 'mapAct']) {
    assert.equal(LR.gate(g, 5100, 1, cmd).reason, 'redraw-cooldown', cmd);
  }
  for (const cmd of ['itemMove', 'endStep', 'factionAbility', 'section', 'zoneCycle']) assert.equal(LR.gate(g, 5100, 1, cmd).allowed, true, cmd);
  assert.equal(LR.gate(g, 5000 + LR.DEFAULT_GUARD_CONFIG.redrawCooldownMs, 1, 'activate').allowed, true);
});

test('safety constants are unchanged', () => {
  assert.deepEqual({ ...LR.DEFAULT_GUARD_CONFIG }, { processingTimeoutMs: 1500, redrawCooldownMs: 300, activationCooldownMs: 250, mapAckTimeoutMs: 1000 });
});

test('post-activation cooldown: every executing command (incl. new shortcuts) waits 250ms after an actual activation', () => {
  const ms = LR.DEFAULT_GUARD_CONFIG.activationCooldownMs;
  const g = LR.noteActivation(LR.createGuard(), 1000);
  for (const cmd of ['activate', 'cardMode', 'cardToggle', 'cardPreview', 'cardDiscard', 'cardBuy', 'enterZone', 'mapPick', 'mapAct', 'mapCancel', 'modalConfirm', 'endStep', 'factionAbility']) {
    const blocked = LR.gate(g, 1000 + ms - 1, 1, cmd);
    assert.equal(blocked.allowed, false, cmd);
    assert.equal(blocked.reason, 'activation-cooldown', cmd);
    assert.equal(LR.gate(g, 1000 + ms, 1, cmd).allowed, true, `${cmd} after cooldown`);
  }
});

test('post-activation cooldown never delays navigation or back/escape keys', () => {
  const g = LR.noteActivation(LR.createGuard(), 1000);
  for (const cmd of ['itemMove', 'zoneMove', 'zoneCycle', 'section', 'toZoneLayer', 'leaveView', 'toggleHelp']) {
    assert.equal(LR.gate(g, 1001, 1, cmd).allowed, true, cmd);
  }
});

test('B double press: a successful cardToggle blocks a second toggle within 250ms', () => {
  let g = LR.createGuard();
  const first = LR.gate(g, 5000, 1, 'cardToggle');
  assert.equal(first.allowed, true);
  g = LR.noteActivation(first.guard, 5000);
  assert.equal(LR.gate(g, 5100, 1, 'cardToggle').reason, 'activation-cooldown');
  assert.equal(LR.gate(g, 5250, 1, 'cardToggle').allowed, true);
});

test('failed (no-op) commands do not start the cooldown: gate alone never records activation', () => {
  for (const cmd of ['cardToggle', 'cardDiscard', 'cardBuy', 'endStep', 'factionAbility']) {
    const first = LR.gate(LR.createGuard(), 5000, 1, cmd);
    assert.equal(first.allowed, true, cmd);
    assert.equal(first.guard.activatedAt, null, `${cmd}: only an actual execution calls noteActivation`);
    assert.equal(LR.gate(first.guard, 5010, 1, cmd).allowed, true, `${cmd}: next legit press 10ms later`);
  }
});

test('enterZone cooldown: entering a zone blocks an immediate pick of its first item', () => {
  let g = LR.createGuard();
  const enter = LR.gate(g, 2000, 1, 'enterZone');
  assert.equal(enter.allowed, true);
  g = LR.noteActivation(enter.guard, 2000);
  assert.equal(LR.gate(g, 2100, 1, 'mapPick').reason, 'activation-cooldown');
  assert.equal(LR.gate(g, 2100, 1, 'mapAct').reason, 'activation-cooldown');
  assert.equal(LR.gate(g, 2100, 1, 'itemMove').allowed, true, 'moving inside the zone stays immediate');
  assert.equal(LR.gate(g, 2250, 1, 'mapPick').allowed, true);
});

test('server-sending mapCancel cannot repeat: processing lock outlasts the 250ms cooldown until new state', () => {
  let g = LR.noteActivation(LR.createGuard(), 3000);
  g = LR.lockProcessing(g, 3000, 4);
  assert.equal(LR.gate(g, 3100, 4, 'mapCancel').reason, 'processing');
  assert.equal(LR.gate(g, 3400, 4, 'mapCancel').reason, 'processing', 'still locked after the cooldown');
  assert.equal(LR.gate(g, 3400, 5, 'mapCancel').allowed, true, 'new authoritative state unlocks');
  const local = LR.noteActivation(LR.createGuard(), 3000);
  assert.equal(LR.gate(local, 3100, 4, 'mapCancel').reason, 'activation-cooldown');
});

test('noteActivation keeps the processing lock and redraw state intact', () => {
  const locked = LR.noteRedraw(LR.lockProcessing(LR.createGuard(), 10, 1), 20);
  const g = LR.noteActivation(locked, 30);
  assert.deepEqual(g, { lockedAt: 10, lockedToken: 1, redrawAt: 20, activatedAt: 30, mapRequest: null });
  assert.equal(LR.noteActivation(null, 7).activatedAt, 7);
});

// ---- map iframe acknowledgment ----

const ack = (req, ok, extra = {}) => C.sanitizeMapResult({ type: 'redline-controller-result', v: 1, cmd: 'act', req, ok, ...extra });

test('map ack: only a matching ok:true result records the cooldown and requested lock', () => {
  let g = LR.beginMapRequest(LR.createGuard(), 1000, 5, { cmd: 'act', lock: true });
  assert.equal(g.activatedAt, null, 'sending alone records nothing');
  assert.equal(g.lockedAt, null, 'sending alone does not lock');
  const out = LR.settleMapResult(g, 1010, ack(5, true, { via: 'confirmMoveBtn' }));
  assert.equal(out.outcome, 'success');
  assert.equal(out.lock, true);
  assert.equal(out.guard.activatedAt, 1010);
  assert.equal(out.guard.mapRequest, null);
  assert.equal(LR.gate(out.guard, 1100, 1, 'mapAct').reason, 'activation-cooldown');
});

test('map ack ok:false fails closed and the next legal action is not blocked by the cooldown', () => {
  const g = LR.beginMapRequest(LR.createGuard(), 1000, 6, { cmd: 'act', lock: true });
  const out = LR.settleMapResult(g, 1010, ack(6, false, { reason: 'button-unavailable' }));
  assert.equal(out.outcome, 'failed');
  assert.equal(out.lock, false);
  assert.equal(out.guard.activatedAt, null);
  assert.equal(out.guard.lockedAt, null);
  assert.equal(out.guard.mapRequest, null);
  for (const cmd of ['mapAct', 'mapPick', 'mapCancel', 'activate', 'cardToggle', 'endStep']) {
    assert.equal(LR.gate(out.guard, 1020, 1, cmd).allowed, true, `${cmd} right after a failed map command`);
  }
});

test('map ack: no reply times out without cooldown or lock; a late reply is stale and ignored', () => {
  const g = LR.beginMapRequest(LR.createGuard(), 1000, 7, { cmd: 'act', lock: true });
  assert.equal(LR.gate(g, 1120, 1, 'mapAct').reason, 'map-pending');
  assert.equal(LR.gate(g, 1120, 1, 'mapPick').reason, 'map-pending');
  for (const cmd of ['zoneMove', 'itemMove', 'toZoneLayer', 'zoneCycle', 'section']) assert.equal(LR.gate(g, 1120, 1, cmd).allowed, true, cmd);
  assert.equal(LR.expireMapRequest(g, 1999).expired, null, 'not yet expired');
  const exp = LR.expireMapRequest(g, 2000);
  assert.equal(exp.expired.req, 7);
  assert.deepEqual(exp.guard, LR.createGuard(), 'timeout leaves no cooldown, lock or pending request');
  assert.equal(LR.gate(g, 2000, 1, 'mapAct').allowed, true, 'gate itself expires the request');
  assert.equal(LR.gate(g, 2000, 1, 'mapAct').guard.mapRequest, null);
  const late = LR.settleMapResult(exp.guard, 2050, ack(7, true));
  assert.equal(late.outcome, 'stale');
  assert.deepEqual(late.guard, LR.createGuard());
  const slow = LR.settleMapResult(g, 2001, ack(7, true));
  assert.equal(slow.outcome, 'timeout');
  assert.equal(slow.guard.activatedAt, null);
  assert.equal(slow.lock, false);
});

test('map ack: mismatched, missing or wrong-command req is stale and keeps the pending request', () => {
  const g = LR.beginMapRequest(LR.createGuard(), 1000, 8, { cmd: 'act', lock: true });
  for (const result of [ack(7, true), ack(9, true), ack(null, true), null,
    C.sanitizeMapResult({ type: 'redline-controller-result', v: 1, cmd: 'activate', req: 8, ok: true })]) {
    const out = LR.settleMapResult(g, 1010, result);
    assert.equal(out.outcome, 'stale');
    assert.equal(out.guard, g, 'guard untouched');
  }
  assert.equal(LR.settleMapResult(LR.createGuard(), 1010, ack(8, true)).outcome, 'stale', 'nothing pending');
});

test('map cancel locks only when the iframe reports the server-sending cancel', () => {
  const meta = { cmd: 'cancel', lockVia: 'cancelDissolveChoiceBtn' };
  const res = (via) => C.sanitizeMapResult({ type: 'redline-controller-result', v: 1, cmd: 'cancel', req: 3, ok: true, via });
  const server = LR.settleMapResult(LR.beginMapRequest(LR.createGuard(), 0, 3, meta), 5, res('cancelDissolveChoiceBtn'));
  assert.equal(server.outcome, 'success');
  assert.equal(server.lock, true);
  const local = LR.settleMapResult(LR.beginMapRequest(LR.createGuard(), 0, 3, meta), 5, res('selection'));
  assert.equal(local.outcome, 'success');
  assert.equal(local.lock, false);
  assert.equal(local.guard.activatedAt, 5, 'selection cancel is still rate-limited');
  const pick = LR.settleMapResult(LR.beginMapRequest(LR.createGuard(), 0, 4, { cmd: 'activate' }),
    5, C.sanitizeMapResult({ type: 'redline-controller-result', v: 1, cmd: 'activate', req: 4, ok: true }));
  assert.equal(pick.lock, false, 'town pick keeps its existing no-lock behaviour');
});

test('map protocol: command req and result fields are strictly validated', () => {
  const cmd = (extra) => C.sanitizeMapCommand({ v: 1, type: 'redline-controller-command', cmd: 'button', id: 'confirmMoveBtn', ...extra });
  assert.equal(cmd({}).req, null);
  assert.equal(cmd({ req: 12 }).req, 12);
  for (const req of [0, -1, 1.5, '3', Number.MAX_SAFE_INTEGER + 2]) assert.equal(cmd({ req }), null, String(req));
  assert.deepEqual(ack(4, true, { via: 'selection' }), { cmd: 'act', ok: true, req: 4, via: 'selection', reason: null });
  assert.equal(ack(4, 'true'), null, 'ok must be boolean');
  assert.equal(ack(0, true), null);
  assert.equal(ack(4, true, { via: 'advanceStepBtn' }), null, 'via must be a map control');
  assert.equal(ack(4, true, { cmd: 'rm' }), null);
  assert.equal(C.sanitizeMapResult({ type: 'redline-controller-result', v: 2, cmd: 'button', req: 4, ok: true }), null);
});

// ---- key-hint bar (not focusable; only mirrors existing visible, enabled controls) ----

const hint = (id, extra = {}) => ({ id, label: id, visible: true, disabled: false, ariaDisabled: false, inert: false, ...extra });

test('hint bar keeps only whitelisted, visible, enabled sources and labels each with its dedicated key', () => {
  const hints = LR.buildKeyHints([
    hint('endStep', { label: '結束行動' }),
    hint('cardBuy', { disabled: true }),
    hint('mapAct', { visible: false }),
    hint('factionAbility', { ariaDisabled: true }),
    hint('cardDiscard', { inert: true }),
    hint('emergencyNewGameBtn'),
    hint('endStep', { label: 'dup' }),
    hint('cardAction', { label: '   ' }),
    null,
  ]);
  assert.deepEqual(hints, [{ id: 'endStep', key: 'Capture', label: '結束行動', danger: true }]);
});

test('hint bar order: Y → X → B → + → Capture; dangerous discard / end step marked', () => {
  const hints = LR.buildKeyHints([
    hint('endStep'), hint('factionAbility'), hint('cardDiscard'), hint('cardResource'), hint('cardAction'), hint('mapCancel'), hint('mapAct'),
  ]);
  assert.deepEqual(hints.map(h => h.id), ['mapAct', 'cardAction', 'cardResource', 'cardDiscard', 'mapCancel', 'factionAbility', 'endStep']);
  assert.deepEqual(hints.map(h => h.key), ['Y', 'Y', 'X', 'B', 'B', '+', 'Capture']);
  assert.deepEqual(hints.filter(h => h.danger).map(h => h.id), ['cardDiscard', 'endStep']);
});

test('exactly one faction ability control is required; zero or several fail closed', () => {
  assert.equal(LR.pickFactionAbility([]), -1);
  assert.equal(LR.pickFactionAbility([{ usable: false }]), -1);
  assert.equal(LR.pickFactionAbility([{ usable: false }, { usable: true }]), 1);
  assert.equal(LR.pickFactionAbility([{ usable: true }, { usable: true }]), -1, 'ambiguous → fail closed');
  assert.equal(LR.pickFactionAbility(null), -1);
});

test('purchase Y needs the focused card checked and the existing buy button enabled', () => {
  const ok = { checked: true, buyUsable: true, cardShown: true };
  assert.equal(LR.purchaseBuyBlocker(ok), null);
  assert.equal(LR.purchaseBuyBlocker({ ...ok, checked: false }), 'not-selected');
  assert.equal(LR.purchaseBuyBlocker({ ...ok, buyUsable: false }), 'buy-unavailable');
  assert.equal(LR.purchaseBuyBlocker({ ...ok, cardShown: false }), 'card-gone');
  assert.equal(LR.purchaseBuyBlocker(null), 'card-gone');
});

test('hand discard needs exactly one existing 棄置 control', () => {
  assert.equal(LR.discardControlIndex([]), -1);
  assert.equal(LR.discardControlIndex(['資源']), -1, 'a resource button is never a discard');
  assert.equal(LR.discardControlIndex(['棄置']), 0);
  assert.equal(LR.discardControlIndex([' 棄置 ']), 0);
  assert.equal(LR.discardControlIndex(['棄置', '棄置']), -1, 'ambiguous → fail closed');
});

// ---- focus model ----

test('reconcile: same key stays, missing key clamps to the same index, avoid set or empty → zone layer', () => {
  assert.equal(LR.reconcileIndex(['a', 'b', 'c'], 'b', 1), 1);
  assert.equal(LR.reconcileIndex(['a', 'c', 'b'], 'b', 1), 2);
  assert.equal(LR.reconcileIndex(['a', 'c'], 'b', 1), 1);
  assert.equal(LR.reconcileIndex(['a'], 'b', 4), 0);
  assert.equal(LR.reconcileIndex([], 'b', 0), -1);
  const avoid = new Set(['x']);
  assert.equal(LR.reconcileIndex(['a', 'x'], 'gone', 1, avoid), -1);
  assert.equal(LR.reconcileIndex(['a', 'x'], 'x', 0, avoid), 1, 'user chose it: keep');
  assert.equal(LR.reconcileIndex(['x'], null, undefined), 0);
});

test('semantic grid navigation: rows, columns, edges stop without wrapping', () => {
  const row = (n) => Array.from({ length: n }, (_, i) => ({ top: 10, left: i * 100 }));
  assert.equal(LR.gridColumns(row(5)), 5);
  assert.equal(LR.gridColumns([{ top: 0 }, { top: 0 }, { top: 200 }]), 2);
  assert.equal(LR.gridColumns([]), 0);
  assert.equal(LR.gridMove(5, 5, 0, 'left'), 0);
  assert.equal(LR.gridMove(5, 5, 0, 'right'), 1);
  assert.equal(LR.gridMove(5, 5, 4, 'right'), 4);
  assert.equal(LR.gridMove(5, 5, 2, 'down'), 2);
  assert.equal(LR.gridMove(5, 2, 1, 'down'), 3);
  assert.equal(LR.gridMove(5, 2, 3, 'down'), 4, 'last partial row keeps reachable');
  assert.equal(LR.gridMove(5, 2, 3, 'up'), 1);
  assert.equal(LR.gridMove(0, 0, 0, 'right'), -1);
  assert.equal(LR.listMove(3, 0, 'up'), 0);
  assert.equal(LR.listMove(3, 0, 'down'), 1);
  assert.equal(LR.listMove(3, 2, 'down'), 2);
  assert.equal(LR.listMove(3, 1, 'left'), 1);
});

test('zones: STICK cycle, direction picks, default prefers memory then hand', () => {
  const ids = ['static', 'random', 'hand'];
  assert.equal(LR.cycleZone(ids, 'hand', 1), 'static');
  assert.equal(LR.cycleZone(ids, 'static', 1), 'random');
  assert.equal(LR.cycleZone(ids, 'gone', 1), 'static');
  assert.equal(LR.cycleZone([], 'hand', 1), null);
  const zones = [
    { id: 'static', rect: { left: 0, top: 100, right: 600, bottom: 300 } },
    { id: 'random', rect: { left: 620, top: 100, right: 1260, bottom: 300 } },
    { id: 'hand', rect: { left: 0, top: 320, right: 1260, bottom: 600 } },
  ];
  assert.equal(LR.pickZone(zones, 'static', 'right'), 'random');
  assert.equal(LR.pickZone(zones, 'random', 'down'), 'hand');
  assert.equal(LR.pickZone(zones, 'hand', 'down'), 'hand', 'nothing below the hand: stay');
  assert.ok(['static', 'random'].includes(LR.pickZone(zones, 'hand', 'up')));
  assert.equal(LR.pickZone(zones, 'static', 'left'), 'static');
  assert.equal(LR.pickZone(zones, 'missing', 'up'), 'static');
  assert.equal(LR.resolveZone(['static', 'hand'], null), 'hand');
  assert.equal(LR.resolveZone(['static', 'hand'], 'static'), 'static');
  assert.equal(LR.resolveZone(['static'], 'actionbar'), 'static');
  assert.equal(LR.resolveZone([], null), null);
});

// ---- map list ----

const snap = (extra) => ({ scope: 'move', targets: [], buttons: [], focusTown: null, canCancel: false, selected: null, pending: null, ...extra });

test('map list fails closed without an authoritative snapshot or targets', () => {
  assert.equal(LR.buildMapList(null).stage, 'none');
  assert.equal(LR.buildMapList(snap({ scope: 'none' })).stage, 'none');
  assert.equal(LR.buildMapList(snap({})).stage, 'none');
  assert.equal(LR.buildMapList({ scope: 'move' }).stage, 'none');
  assert.equal(LR.buildMapList(snap({ scope: 'choice', targets: [{ town: '甲', role: 'origin' }] })).stage, 'none');
});

test('map list stage 1 lists origins; stage 2 lists only server-legal destinations sorted by cost/mode', () => {
  const s1 = LR.buildMapList(snap({ targets: [{ town: '乙', role: 'origin' }, { town: '甲', role: 'origin', act: 'dissolve' }] }));
  assert.equal(s1.stage, 'source');
  assert.deepEqual(s1.rows.map(r => r.town).sort(), ['乙', '甲'].sort());
  assert.equal(s1.rows.find(r => r.town === '甲').act, 'dissolve');
  assert.equal(s1.rows.find(r => r.town === '乙').act, null);
  const s2 = LR.buildMapList(snap({
    selected: '甲', canCancel: true,
    targets: [
      { town: '丙', role: 'move', mode: 'rail', cost: 1, act: 'move' },
      { town: '丁', role: 'move', mode: 'road', cost: 1, act: 'move' },
      { town: '戊', role: 'move', mode: 'road', cost: 0, act: 'move' },
      { town: '甲', role: 'origin' },
    ],
    pending: { from: '甲', to: '丙', mode: 'rail', cost: 1 },
  }));
  assert.equal(s2.stage, 'destination');
  assert.deepEqual(s2.rows.map(r => r.town), ['戊', '丁', '丙']);
  assert.ok(s2.rows.every(r => r.act === 'move'));
  assert.equal(s2.rows[0].cost, 0, 'zero cost is preserved');
  assert.deepEqual(s2.pending, { from: '甲', to: '丙', mode: 'rail', cost: 1 });
  assert.equal(s2.canCancel, true);
  assert.equal(LR.buildMapList(snap({ selected: '甲', targets: [{ town: '丙', role: 'move' }], pending: { from: '乙', to: '丙' } })).pending, null);
  assert.equal(LR.buildMapList(snap({ selected: '甲', targets: [{ town: '丙', role: 'move' }], pending: { from: '甲', to: '庚' } })).pending, null);
  assert.equal(LR.buildMapList(snap({ selected: '甲', targets: [{ town: '甲', role: 'origin' }] })).stage, 'source');
});

test('map list choice stage shows pending-choice targets, their action and the current selection', () => {
  const list = LR.buildMapList(snap({ scope: 'choice', selected: '丁', targets: [{ town: '丁', role: 'choice', act: 'build' }, { town: '戊', role: 'choice', act: 'build' }] }));
  assert.equal(list.stage, 'choice');
  assert.equal(list.selected, '丁');
  assert.deepEqual(list.rows.map(r => r.act), ['build', 'build']);
  assert.equal(LR.buildMapList(snap({ scope: 'choice', selected: '庚', targets: [{ town: '丁', role: 'choice' }] })).selected, null);
});

test('map Y labels and buttons come only from the row action', () => {
  const list = { selected: '甲', pending: null };
  assert.deepEqual(LR.mapActFor({ town: '臺北', act: 'build' }, list), { id: 'directBuildBtn', label: '建立組織 臺北' });
  assert.deepEqual(LR.mapActFor({ town: '乙', act: 'move' }, list), { id: 'confirmMoveBtn', label: '移動 甲→乙' });
  assert.deepEqual(LR.mapActFor({ town: '天津', act: 'dissolve' }, list), { id: 'dissolveBtn', label: '瓦解組織 天津' });
  assert.equal(LR.mapActFor({ town: '乙', act: null }, list), null);
  assert.equal(LR.mapActFor({ town: '乙', act: 'teleport' }, list), null);
  assert.equal(LR.mapActFor(null, list), null);
});

test('confirm dialog defaults to cancel and info lines only reflect client-visible counts', () => {
  assert.equal(LR.CONFIRM_DEFAULT_FOCUS, 'cancel');
  assert.deepEqual(LR.confirmInfoLines({ playableHand: 0, selectedPurchases: 0 }), []);
  assert.equal(LR.confirmInfoLines({ playableHand: 3, selectedPurchases: 2 }).length, 2);
  assert.deepEqual(LR.confirmInfoLines(null), []);
});

// ---- controller_core additions used by living-room ----

test('confirm modal is the top modal scope and declares cancel as initial focus', () => {
  assert.equal(C.MODAL_SCOPES[0].id, 'lrConfirmModal');
  assert.equal(C.MODAL_SCOPES[0].initial, '#lrConfirmCancelBtn');
  assert.deepEqual(C.MODAL_SCOPES[0].cancel, ['#lrConfirmCancelBtn']);
  assert.equal(C.resolveModalScope(['choiceModal', 'lrConfirmModal']).id, 'lrConfirmModal');
});

test('snapshot sanitize: optional move meta / selected / pending / act are validated, zero cost kept', () => {
  const base = { type: 'redline-controller-map-snapshot', v: 1, scope: 'move', buttons: [], targets: [{ town: '乙', role: 'move', x: 1, y: 2, mode: 'road', cost: 0, act: 'move' }] };
  const ok = C.sanitizeMapSnapshot({ ...base, selected: '甲', pending: { from: '甲', to: '乙', mode: 'road', cost: 0 } });
  assert.deepEqual(ok.targets[0], { town: '乙', role: 'move', x: 1, y: 2, mode: 'road', cost: 0, act: 'move' });
  assert.equal(ok.selected, '甲');
  assert.deepEqual(ok.pending, { from: '甲', to: '乙', mode: 'road', cost: 0 });
  assert.equal(C.sanitizeMapSnapshot(base).selected, null);
  assert.equal(C.sanitizeMapSnapshot(base).pending, null);
  assert.equal(C.sanitizeMapSnapshot({ ...base, targets: [{ ...base.targets[0], mode: 'teleport' }] }), null);
  assert.equal(C.sanitizeMapSnapshot({ ...base, targets: [{ ...base.targets[0], cost: -1 }] }), null);
  assert.equal(C.sanitizeMapSnapshot({ ...base, targets: [{ ...base.targets[0], cost: 1.5 }] }), null);
  assert.equal(C.sanitizeMapSnapshot({ ...base, selected: 42 }), null);
  assert.equal(C.sanitizeMapSnapshot({ ...base, pending: { from: '甲' } }), null);
  assert.equal(C.sanitizeMapSnapshot({ ...base, pending: { from: '甲', to: '乙', mode: 'fly' } }), null);
});

test('snapshot sanitize: a target action must be legal for its role and scope', () => {
  const target = (role, act, scope = 'move') => C.sanitizeMapSnapshot({ type: 'redline-controller-map-snapshot', v: 1, scope, buttons: [], targets: [{ town: '乙', role, x: 1, y: 2, act }] });
  assert.equal(target('move', 'move').targets[0].act, 'move');
  assert.equal(target('origin', 'dissolve').targets[0].act, 'dissolve');
  assert.equal(target('choice', 'build', 'choice').targets[0].act, 'build');
  assert.equal(target('choice', 'dissolve', 'choice').targets[0].act, 'dissolve');
  assert.equal(target('origin', undefined).targets[0].act, undefined, 'absent act stays absent');
  for (const [role, act, scope] of [['move', 'build'], ['origin', 'move'], ['choice', 'move', 'choice'], ['move', 'dissolve'], ['origin', 'build'], ['move', 'rm'], ['origin', 'dissolve', 'choice']]) {
    assert.equal(target(role, act, scope), null, `${scope}:${role}:${act}`);
  }
});

test('snapshot model: move meta, selection, pending and target actions come only from authoritative inputs', () => {
  const input = {
    hasState: true, viewerCanAct: true, pendingChoiceBlocksMoves: false, highlight: null,
    visibleTowns: ['甲', '乙', '丙', '丁'], knownTowns: ['甲', '乙', '丙', '丁'],
    moveTargets: [{ town: '乙', mode: 'rail', cost: 0 }, { town: '丙', mode: 'bogus', cost: 'x' }],
    selectedTown: '甲', originTowns: ['甲', '丁'], dissolveOrigins: ['丁', '幽靈'], buttons: [],
    pendingMoveTarget: { from: '甲', to: '乙', mode: 'rail', cost: 0 },
  };
  const m = C.buildMapSnapshotModel(input);
  assert.deepEqual(m.targets, [
    { town: '乙', role: 'move', mode: 'rail', cost: 0, act: 'move' },
    { town: '丙', role: 'move', act: 'move' },
    { town: '甲', role: 'origin' },
    { town: '丁', role: 'origin', act: 'dissolve' },
  ]);
  assert.equal(m.selected, '甲');
  assert.deepEqual(m.pending, { from: '甲', to: '乙', mode: 'rail', cost: 0 });
  assert.equal(C.buildMapSnapshotModel({ ...input, pendingMoveTarget: { from: '甲', to: '不存在' } }).pending, null);
  assert.equal(C.buildMapSnapshotModel({ ...input, pendingMoveTarget: { from: '丙', to: '乙' } }).pending, null);
  assert.equal(C.buildMapSnapshotModel({ ...input, viewerCanAct: false }).selected, null);
  const choice = (actionKind) => C.buildMapSnapshotModel({ ...input, highlight: { towns: [{ town: '丁' }], actionKind } }).targets;
  assert.deepEqual(choice('build'), [{ town: '丁', role: 'choice', act: 'build' }]);
  assert.deepEqual(choice('dissolve'), [{ town: '丁', role: 'choice', act: 'dissolve' }]);
  assert.deepEqual(choice('other'), [{ town: '丁', role: 'choice' }], 'unknown highlight kinds expose no Y action');
});
