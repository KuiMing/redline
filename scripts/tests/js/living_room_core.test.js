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

test('living-room key map: PLUS = faction ability, CAPTURE = end step, STICK = next zone, ZR = map zoom', () => {
  assert.deepEqual(press('PLUS'), { name: 'factionAbility' });
  assert.deepEqual(press('CAPTURE'), { name: 'endStep' });
  assert.deepEqual(press('STICK'), { name: 'nextZone' });
  assert.deepEqual(press('ZR'), { name: 'mapZoom' });
  assert.deepEqual(press('SL'), { name: 'focusMenu' }, 'SL = focus menu (same as desktop)');
  assert.equal(press('HOME'), null);
  assert.equal(Object.values(LR.BUTTON_ACTIONS).includes('zoneBack'), false, 'ZR no longer goes back a layer / view');
  // desktop: + / CAPTURE / STICK still do nothing there; SL (focus menu) and ZR (map zoom) are shared
  for (const b of ['PLUS', 'CAPTURE', 'STICK', 'HOME']) assert.equal(C.logicalAction({ type: 'press', button: b }), null, `desktop ${b}`);
  assert.deepEqual(C.logicalAction({ type: 'press', button: 'SL' }), press('SL'));
  assert.deepEqual(C.logicalAction({ type: 'press', button: 'ZR' }), press('ZR'));
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

test('SL routes to the focus menu from every layer and view, including a pending map choice', () => {
  for (const ctx of allCtxs()) {
    for (const lock of [{}, { choiceLock: true }, { choiceLock: true, locked: true }]) {
      assert.deepEqual(LR.routeLivingRoom({ ...ctx, ...lock }, press('SL')), { cmd: 'focusMenu' });
    }
  }
});

test('focus menu gating: opening is focus-only (no processing lock) but waits out map requests and the 250ms activation cooldown', () => {
  const locked = LR.lockProcessing(LR.createGuard(), 1000, 7);
  assert.equal(LR.gate(locked, 1100, 7, 'focusMenu').allowed, true, 'only moves focus: allowed while a game action is processing');
  assert.equal(LR.gate(locked, 1100, 7, 'focusMenuPick').allowed, true);
  const pending = LR.beginMapRequest(LR.createGuard(), 1000, 3, { cmd: 'act', lock: true });
  assert.equal(LR.gate(pending, 1100, 1, 'focusMenu').reason, 'map-pending');
  assert.equal(LR.gate(pending, 1100, 1, 'focusMenuPick').reason, 'map-pending');
  const activated = LR.noteActivation(LR.createGuard(), 1000);
  assert.equal(LR.gate(activated, 1100, 1, 'focusMenu').reason, 'activation-cooldown');
  assert.equal(LR.gate(activated, 1100, 1, 'focusMenuPick').reason, 'activation-cooldown', 'A right after the menu opened is ignored');
  assert.equal(LR.gate(activated, 1250, 1, 'focusMenuPick').allowed, true);
  const redrawn = LR.noteRedraw(LR.createGuard(), 1000);
  assert.equal(LR.gate(redrawn, 1100, 1, 'focusMenuPick').reason, 'redraw-cooldown', 'menu refreshed under the cursor: ignore A for 300ms');
  assert.equal(LR.gate(redrawn, 1100, 1, 'focusMenu').allowed, true, 'opening does not depend on the current focus item');
  for (const cmd of ['focusMenu', 'focusMenuPick']) assert.equal(LR.PROCESSING_GATED.has(cmd), false, cmd);
  assert.deepEqual({ ...LR.DEFAULT_GUARD_CONFIG }, { processingTimeoutMs: 1500, redrawCooldownMs: 300, activationCooldownMs: 250, mapAckTimeoutMs: 1000 });
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

test('ZR zooms the strategic map from either layer (pending map choice included) and is a full no-op on every other view', () => {
  const ZOOM = { cmd: 'mapZoom' };
  const onMap = [
    zoneCtx({ view: 'map', scopeKind: 'map', zone: 'maplist' }), zoneCtx({ view: 'map', scopeKind: 'map', zone: null }), mapCtx(),
    itemCtx(null, { zone: 'maplist', scopeKind: 'map', view: 'map' }),
  ];
  for (const ctx of onMap) {
    for (const lock of [{}, { choiceLock: true, locked: true }, { mapCanCancel: true }]) {
      assert.deepEqual(LR.routeLivingRoom({ ...ctx, ...lock }, press('ZR')), ZOOM, JSON.stringify({ ...ctx, ...lock }));
    }
  }
  const offMap = [
    zoneCtx(), zoneCtx({ zone: null }), zoneCtx({ view: 'log', zone: 'view' }), zoneCtx({ view: 'myFaction', zone: 'view' }),
    itemCtx(handItem), itemCtx(supportItem), itemCtx(buyItem), itemCtx(controlItem, { zone: 'faction' }), itemCtx(controlItem, { view: 'log', zone: 'view' }),
    zoneCtx({ choiceLock: true, zone: null }),
    // the map tab without the map scope (e.g. the iframe is hidden) or the map scope reported for another tab: fail closed
    zoneCtx({ view: 'map', scopeKind: 'page', zone: 'maplist' }), zoneCtx({ view: 'command', scopeKind: 'map' }),
  ];
  for (const ctx of offMap) assert.equal(LR.routeLivingRoom(ctx, press('ZR')), null, JSON.stringify(ctx));
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

test('card semantics match desktop routing (purchase Y included); only hand-discard B is living-room only', () => {
  const changed = new Set(['hand+discard:B']);
  for (const [tag, item] of [['hand', handItem], ['hand+discard', supportItem], ['purchase', buyItem]]) {
    for (const button of ['A', 'B', 'X', 'Y']) {
      const lr = LR.routeLivingRoom(itemCtx(item), press(button));
      const desktop = C.routeAction({ scopeKind: 'page', hasFocus: true, card: item.card, cancelAvailable: false, sectionsLocked: false }, C.logicalAction({ type: 'press', button }));
      if (changed.has(`${tag}:${button}`)) assert.notDeepEqual(lr, desktop, `${tag}:${button}`);
      else assert.deepEqual(lr, desktop, `${tag}:${button}`);
    }
  }
});

test('item layer: stick moves inside the zone; ZR off the map never leaves the layer', () => {
  assert.deepEqual(LR.routeLivingRoom(itemCtx(handItem), nav('right')), { cmd: 'itemMove', dir: 'right' });
  assert.equal(LR.routeLivingRoom(itemCtx(handItem), press('ZR')), null);
  assert.equal(LR.routeLivingRoom(itemCtx(buyItem), press('ZR')), null);
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
  assert.deepEqual(LR.routeLivingRoom(mapCtx({ locked: true }), press('ZR')), { cmd: 'mapZoom' }, 'zoom never touches the pending choice');
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
  for (const cmd of ['itemMove', 'zoneMove', 'zoneCycle', 'section', 'toZoneLayer', 'toggleHelp']) {
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

// ---- ZR 地圖縮放：閘門、確認與前置條件 ----

const zoomAck = (req, ok, extra = {}) => C.sanitizeMapResult({ type: 'redline-controller-result', v: 1, cmd: 'zoom', req, ok, ...extra });

test('ZR gating: one pending map request at a time; never the processing lock, redraw cooldown or activation cooldown', () => {
  assert.equal(LR.MAP_VIEW_COMMANDS.has('mapZoom'), true);
  assert.equal(LR.ACTIVATION_GATED.has('mapZoom'), false, 'a quick second ZR press still zooms one more level');
  assert.equal(LR.PROCESSING_GATED.has('mapZoom'), false, 'zoom is not a game action');
  assert.equal(LR.COOLDOWN_GATED.has('mapZoom'), false, 'zoom does not depend on the focused item');
  assert.equal(LR.gate(LR.lockProcessing(LR.createGuard(), 1000, 7), 1100, 7, 'mapZoom').allowed, true, 'allowed while a game action is processing');
  assert.equal(LR.gate(LR.noteRedraw(LR.createGuard(), 1000), 1100, 1, 'mapZoom').allowed, true);
  assert.equal(LR.gate(LR.noteActivation(LR.createGuard(), 1000), 1001, 1, 'mapZoom').allowed, true);
  for (const cmd of ['act', 'activate', 'cancel', 'snapshot', 'zoom']) {
    assert.equal(LR.gate(LR.beginMapRequest(LR.createGuard(), 1000, 3, { cmd }), 1100, 1, 'mapZoom').reason, 'map-pending', `pending ${cmd}`);
  }
  // a pending zoom also holds back every other executing key (no second request can overwrite the single slot)
  const zooming = LR.beginMapRequest(LR.createGuard(), 1000, 4, { cmd: 'zoom' });
  for (const cmd of ['mapAct', 'mapPick', 'mapCancel', 'focusMenu', 'endStep', 'mapZoom']) assert.equal(LR.gate(zooming, 1100, 1, cmd).reason, 'map-pending', cmd);
  for (const cmd of ['itemMove', 'zoneMove', 'zoneCycle', 'section', 'toZoneLayer']) assert.equal(LR.gate(zooming, 1100, 1, cmd).allowed, true, cmd);
  assert.equal(LR.gate(zooming, 2000, 1, 'mapZoom').allowed, true, 'an expired zoom request no longer blocks');
});

test('ZR ack: sending alone records nothing; only the matching, timely ok:true records success and the cooldown (never a lock)', () => {
  const g = LR.beginMapRequest(LR.createGuard(), 1000, 11, { cmd: 'zoom' });
  assert.deepEqual({ ...g, mapRequest: null }, LR.createGuard(), 'postMessage alone: no success, cooldown or lock');
  const ok = LR.settleMapResult(g, 1010, zoomAck(11, true));
  assert.equal(ok.outcome, 'success');
  assert.equal(ok.lock, false);
  assert.equal(ok.guard.activatedAt, 1010);
  assert.equal(ok.guard.lockedAt, null);
  assert.equal(ok.guard.mapRequest, null);
  assert.equal(LR.gate(ok.guard, 1100, 1, 'mapAct').reason, 'activation-cooldown', 'the next executing key waits 250ms');
  assert.equal(LR.gate(ok.guard, 1100, 1, 'mapZoom').allowed, true, 'the next ZR press is not delayed');
  // duplicate ack of the same req after success: stale, nothing recorded again
  const dup = LR.settleMapResult(ok.guard, 1300, zoomAck(11, true));
  assert.equal(dup.outcome, 'stale');
  assert.equal(dup.guard, ok.guard);
  // ok:false → failed without cooldown; the next legal key is not blocked
  const refused = LR.settleMapResult(g, 1010, zoomAck(11, false, { reason: 'map-hidden' }));
  assert.equal(refused.outcome, 'failed');
  assert.equal(refused.guard.activatedAt, null);
  assert.equal(LR.gate(refused.guard, 1020, 1, 'mapZoom').allowed, true);
  // late ack (at / after the 1000ms timeout) → timeout, nothing recorded; after expiry it is stale
  const late = LR.settleMapResult(g, 2000, zoomAck(11, true));
  assert.equal(late.outcome, 'timeout');
  assert.equal(late.guard.activatedAt, null);
  const expired = LR.expireMapRequest(g, 2000);
  assert.equal(expired.expired.cmd, 'zoom');
  assert.equal(LR.settleMapResult(expired.guard, 2100, zoomAck(11, true)).outcome, 'stale');
  // wrong req, missing req (rejected by the sanitizer), malformed reply or another command's result → stale, keep waiting
  for (const result of [zoomAck(12, true), zoomAck(10, true), zoomAck(null, true), zoomAck(11, 'yes'), null,
    C.sanitizeMapResult({ type: 'redline-controller-result', v: 1, cmd: 'act', req: 11, ok: true })]) {
    const out = LR.settleMapResult(g, 1010, result);
    assert.equal(out.outcome, 'stale');
    assert.equal(out.guard, g);
  }
});

test('ZR preconditions: connected bridge, game screen, strategic-map scope and a ready iframe (no focus needed) — anything else fails closed', () => {
  const ok = { connected: true, gameShown: true, scopeKind: 'map', view: 'map', frameReady: true };
  assert.equal(LR.mapZoomBlocker(ok), null);
  assert.equal(LR.mapZoomBlocker({ ...ok, padActive: false }), null, 'the first ZR press on the map zooms without a placed focus');
  assert.equal(LR.mapZoomBlocker({ ...ok, connected: false }), 'disconnected', 'disabled / connecting / error / stale / socket closed');
  assert.equal(LR.mapZoomBlocker({ ...ok, gameShown: false }), 'no-game');
  assert.equal(LR.mapZoomBlocker({ ...ok, scopeKind: 'modal' }), 'modal');
  assert.equal(LR.mapZoomBlocker({ ...ok, scopeKind: 'page' }), 'not-map');
  assert.equal(LR.mapZoomBlocker({ ...ok, view: 'command' }), 'not-map');
  assert.equal(LR.mapZoomBlocker({ ...ok, frameReady: false }), 'no-frame');
  assert.equal(LR.mapZoomBlocker({ ...ok, connected: 'yes' }), 'disconnected', 'only an explicit true counts');
  assert.equal(LR.mapZoomBlocker(null), 'disconnected');
  assert.equal(LR.mapZoomBlocker(undefined), 'disconnected');
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

test('purchase Y needs the focused card validly checked (via B) and the existing buy button enabled', () => {
  const ok = { checked: true, selectable: true, buyUsable: true, cardShown: true };
  assert.equal(LR.purchaseBuyBlocker(ok), null);
  assert.equal(LR.purchaseBuyBlocker({ ...ok, checked: false }), 'not-selected', 'Y never checks an unselected card');
  assert.equal(LR.purchaseBuyBlocker({ ...ok, buyUsable: false }), 'buy-unavailable');
  assert.equal(LR.purchaseBuyBlocker({ ...ok, cardShown: false }), 'card-gone');
  // a card that stays checked after it stopped being purchasable (sold out / disabled / hidden checkbox) is not a valid selection
  assert.equal(LR.purchaseBuyBlocker({ ...ok, selectable: false }), 'card-gone');
  assert.equal(LR.purchaseBuyBlocker({ checked: true, buyUsable: true, cardShown: true }), 'card-gone', 'unknown selectability fails closed');
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

test('map list stage key: selecting a pending-choice row (A) keeps the stage, so focus stays on that row for Y', () => {
  const choice = (selected) => LR.buildMapList(snap({ scope: 'choice', selected,
    targets: ['丁', '戊', '己'].map(town => ({ town, role: 'choice', act: 'build' })) }));
  assert.equal(choice('己').selected, '己');
  assert.equal(LR.mapStageKey(choice(null)), LR.mapStageKey(choice('己')), 'A on a choice row is not a new list');
  assert.equal(LR.mapStageKey(choice('丁')), LR.mapStageKey(choice('己')));
  // a different list still resets: source → destination, a different source, destination → source, any stage → none
  const source = LR.buildMapList(snap({ targets: [{ town: '甲', role: 'origin' }, { town: '乙', role: 'origin' }] }));
  const dest = (from) => LR.buildMapList(snap({ selected: from, targets: [{ town: '丙', role: 'move', act: 'move' }] }));
  assert.notEqual(LR.mapStageKey(source), LR.mapStageKey(dest('甲')));
  assert.notEqual(LR.mapStageKey(dest('甲')), LR.mapStageKey(dest('乙')));
  assert.notEqual(LR.mapStageKey(choice('丁')), LR.mapStageKey(LR.buildMapList(null)));
  assert.equal(LR.mapStageKey(LR.buildMapList(null)), LR.mapStageKey(null));
  // arming a destination only changes `pending`, never the stage
  const armed = LR.buildMapList(snap({ selected: '甲', targets: [{ town: '丙', role: 'move', act: 'move' }], pending: { from: '甲', to: '丙' } }));
  assert.equal(LR.mapStageKey(armed), LR.mapStageKey(dest('甲')));
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

// ---- SL 聚焦選單：只由目前合法地圖目標（iframe 權威 snapshot＋canonical 統治者／陣營區域）建立分組 ----

const zh = new Intl.Collator('zh-Hant');
const sortZh = (arr) => [...arr].sort(zh.compare);
const metaTarget = (town, ruler, camp, extra = {}) => ({ town, role: 'choice', x: 1, y: 1, act: 'build', ruler, camp, ...extra });
const groupSnapshot = (targets, extra = {}) => C.sanitizeMapSnapshot({
  type: 'redline-controller-map-snapshot', v: 1, seq: 1, scope: 'choice', buttons: [], groupMeta: 1, targets, ...extra,
});
const CHOICE_TARGETS = [
  metaTarget('臺北', ['臺灣'], ['臺灣', '紅軍']),
  metaTarget('新北', ['臺灣'], ['臺灣', '紅軍', '臺灣']),
  metaTarget('沖繩', ['東洋'], ['臺灣']),
  metaTarget('香港城', ['紅軍'], ['香港', '紅軍']),
  metaTarget('曼谷', ['南洋'], []),
  metaTarget('臺北', ['臺灣'], ['臺灣', '紅軍']),
  // 不是目前合法目標（choice scope 裡的來源）：不得計入任何分組
  { town: '北京', role: 'origin', x: 1, y: 1, ruler: ['紅軍'], camp: ['紅軍'] },
];
const groupsOf = (menu, kind) => menu.sections.find(s => s.kind === kind).groups.map(g => [g.name, g.count, g.towns]);

test('focus menu groups only current legal map targets by 統治者 and 陣營區域, de-duplicated, with counts', () => {
  const menu = LR.buildFocusMenu(groupSnapshot(CHOICE_TARGETS));
  assert.equal(menu.ok, true);
  assert.equal(menu.reason, null);
  assert.equal(menu.stage, 'choice');
  assert.equal(menu.total, 5, '臺北 listed twice still counts once; the origin 北京 is not a legal target here');
  assert.deepEqual(menu.sections.map(s => [s.kind, s.label]), [['ruler', '統治者'], ['camp', '陣營區域']]);
  const ties = sortZh(['東洋', '紅軍', '南洋']);
  assert.deepEqual(groupsOf(menu, 'ruler'), [
    ['臺灣', 2, sortZh(['臺北', '新北'])],
    ...ties.map(name => [name, 1, [{ 東洋: '沖繩', 紅軍: '香港城', 南洋: '曼谷' }[name]]]),
  ]);
  const camps = sortZh(['臺灣', '紅軍']);
  assert.deepEqual(groupsOf(menu, 'camp'), [
    ...camps.map(name => [name, 3, sortZh(name === '臺灣' ? ['臺北', '新北', '沖繩'] : ['臺北', '新北', '香港城'])]),
    ['香港', 1, ['香港城']],
  ], 'every listed region holds >=1 legal target; 曼谷 (no camp tag) is in no region; 紅軍 excludes the non-target 北京');
  const red = menu.sections[0].groups.find(g => g.name === '紅軍');
  assert.equal(red.key, 'ruler:紅軍');
  assert.equal(red.note, '牆內', 'rules.md: a town whose ruler list contains 紅軍 is inside the wall');
  assert.equal(menu.sections[1].groups.find(g => g.name === '紅軍').note, null);
});

test('focus menu ordering and counts are deterministic regardless of snapshot order', () => {
  const a = LR.buildFocusMenu(groupSnapshot(CHOICE_TARGETS));
  const b = LR.buildFocusMenu(groupSnapshot([...CHOICE_TARGETS].reverse()));
  const c = LR.buildFocusMenu(groupSnapshot([CHOICE_TARGETS[3], CHOICE_TARGETS[0], CHOICE_TARGETS[6], CHOICE_TARGETS[4], CHOICE_TARGETS[2], CHOICE_TARGETS[1]]));
  assert.deepEqual(b, a);
  assert.deepEqual(c, a);
  // groups: more matching towns first, then name; towns: the map list order
  for (const section of a.sections) {
    for (let i = 1; i < section.groups.length; i += 1) {
      const [p, q] = [section.groups[i - 1], section.groups[i]];
      assert.ok(p.count > q.count || (p.count === q.count && zh.compare(p.name, q.name) <= 0), `${p.name} before ${q.name}`);
    }
  }
});

test('focus menu lists only legal build targets: move sources, move destinations, dissolve and act-less choices fail closed', () => {
  const destination = groupSnapshot([
    { town: '桃園', role: 'move', x: 1, y: 1, mode: 'rail', cost: 1, act: 'move', ruler: ['臺灣'], camp: ['臺灣'] },
    { town: '基隆', role: 'move', x: 1, y: 1, mode: 'road', cost: 1, act: 'move', ruler: ['臺灣'], camp: ['臺灣', '紅軍'] },
    { town: '臺北', role: 'origin', x: 1, y: 1, ruler: ['臺灣'], camp: ['臺灣', '紅軍', '香港'] },
  ], { scope: 'move', selected: '臺北' });
  assert.equal(LR.buildMapList(destination).stage, 'destination', 'the map list itself still shows the destinations');
  const source = groupSnapshot([
    { town: '臺北', role: 'origin', x: 1, y: 1, ruler: ['臺灣'], camp: [] },
    { town: '天津', role: 'origin', x: 1, y: 1, act: 'dissolve', ruler: ['紅軍'], camp: ['紅軍'] },
  ], { scope: 'move' });
  assert.equal(LR.buildMapList(source).stage, 'source');
  const dissolve = groupSnapshot(CHOICE_TARGETS.filter(t => t.role === 'choice').map(t => ({ ...t, act: 'dissolve' })));
  const noAct = groupSnapshot(CHOICE_TARGETS.filter(t => t.role === 'choice').map(t => ({ ...t, act: undefined })));
  const mixed = groupSnapshot([metaTarget('臺北', ['臺灣'], []), metaTarget('天津', ['紅軍'], [], { act: 'dissolve' })]);
  for (const [label, snap] of [['move destination', destination], ['move source', source], ['dissolve choice', dissolve],
    ['choice without an action', noAct], ['choice mixing build and dissolve', mixed]]) {
    assert.ok(snap, `${label}: the snapshot itself is valid`);
    const menu = LR.buildFocusMenu(snap);
    assert.deepEqual([menu.ok, menu.reason, menu.sections], [false, 'no-targets', []], label);
  }
  // 只有建立組織的 pending choice：之後 Y＝directBuildBtn。
  const build = LR.buildFocusMenu(groupSnapshot(CHOICE_TARGETS));
  assert.equal(build.ok, true);
  for (const town of build.sections.flatMap(s => s.groups.flatMap(g => g.towns))) {
    assert.equal(LR.mapActFor(LR.buildMapList(groupSnapshot(CHOICE_TARGETS)).rows.find(r => r.town === town), null).id, 'directBuildBtn', town);
  }
});

test('focus menu fails closed: missing snapshot, no legal targets, missing or empty group data', () => {
  assert.deepEqual([LR.buildFocusMenu(null).ok, LR.buildFocusMenu(null).reason], [false, 'no-snapshot']);
  assert.equal(LR.buildFocusMenu(groupSnapshot([], { scope: 'none' })).reason, 'no-targets');
  assert.equal(LR.buildFocusMenu(groupSnapshot([])).reason, 'no-targets');
  assert.equal(LR.buildFocusMenu(groupSnapshot([{ town: '北京', role: 'origin', x: 1, y: 1, ruler: ['紅軍'], camp: [] }])).reason, 'no-targets',
    'choice scope without choice targets has nothing legal to focus');
  const legacy = C.sanitizeMapSnapshot({ type: 'redline-controller-map-snapshot', v: 1, scope: 'choice', buttons: [], targets: [{ town: '臺北', role: 'choice', x: 1, y: 1, act: 'build' }] });
  assert.equal(LR.buildFocusMenu(legacy).reason, 'no-group-data', 'an iframe without versioned group metadata never guesses');
  assert.equal(groupSnapshot([metaTarget('無名', [], [])]), null, 'the parent sanitizer rejects an empty ruler list');
  for (const bad of [LR.buildFocusMenu(null), LR.buildFocusMenu(legacy)]) assert.deepEqual(bad.sections, []);
  for (const code of ['no-snapshot', 'no-targets', 'no-group-data', 'stale', 'gone', 'changed', 'no-game', 'map-unavailable']) {
    const textValue = LR.FOCUS_MENU_REASONS[code];
    assert.ok(typeof textValue === 'string' && textValue.length > 0 && textValue.length <= 24, code);
  }
});

test('focus menu: any candidate with missing or invalid group data fails the whole menu closed (nothing filtered or coerced)', () => {
  // buildFocusMenu 也直接驗證（不只依賴 parent sanitizer）：每個候選都要有非空 ruler 陣列與 camp 陣列。
  const raw = (targets) => ({ scope: 'choice', groupMeta: 1, selected: null, targets });
  const good = metaTarget('臺北', ['臺灣'], ['臺灣']);
  assert.equal(LR.buildFocusMenu(raw([good])).ok, true);
  for (const [label, bad] of [
    ['ruler missing', metaTarget('新北', undefined, ['臺灣'])],
    ['empty ruler list', metaTarget('新北', [], ['臺灣'])],
    ['ruler not an array', metaTarget('新北', '臺灣', ['臺灣'])],
    ['camp missing', metaTarget('新北', ['臺灣'], undefined)],
    ['camp not an array', metaTarget('新北', ['臺灣'], '臺灣')],
    ['invalid camp entry', metaTarget('新北', ['臺灣'], ['臺灣', 3])],
    ['empty ruler name', metaTarget('新北', [''], [])],
  ]) {
    const menu = LR.buildFocusMenu(raw([good, bad]));
    assert.deepEqual([menu.ok, menu.reason, menu.total, menu.sections], [false, 'no-group-data', 0, []], label);
  }
});

test('focus menu context: stage or pending-choice selection drift between open and pick is detected', () => {
  const shown = LR.buildFocusMenu(groupSnapshot(CHOICE_TARGETS));
  assert.equal(shown.selected, null);
  assert.equal(LR.focusMenuDrift(shown, LR.buildFocusMenu(groupSnapshot([...CHOICE_TARGETS].reverse()))), false, 'same state, any order');
  const fewer = LR.buildFocusMenu(groupSnapshot(CHOICE_TARGETS.slice(1)));
  assert.equal(LR.focusMenuDrift(shown, fewer), false, 'candidates shrinking is handled per group (gone), not as drift');
  const picked = LR.buildFocusMenu(groupSnapshot(CHOICE_TARGETS, { selected: '沖繩' }));
  assert.equal(picked.selected, '沖繩');
  assert.equal(LR.focusMenuDrift(shown, picked), true, 'the pending-choice selection changed');
  assert.equal(LR.focusMenuDrift(picked, LR.buildFocusMenu(groupSnapshot(CHOICE_TARGETS, { selected: '曼谷' }))), true);
  assert.equal(LR.focusMenuDrift(shown, { ...shown, stage: 'destination' }), true, 'stage changed');
  assert.equal(LR.focusMenuDrift(shown, null), true);
  assert.equal(LR.focusMenuDrift(null, shown), true);
});

test('focus menu pick: keep the current focus when it matches, otherwise the first town in list order; unknown groups fail closed', () => {
  const menu = LR.buildFocusMenu(groupSnapshot(CHOICE_TARGETS));
  const taiwan = LR.findFocusMenuGroup(menu, 'camp:臺灣');
  assert.deepEqual(taiwan.towns, sortZh(['臺北', '新北', '沖繩']));
  assert.equal(LR.pickFocusMenuTown(taiwan, '沖繩'), '沖繩', 'current focus is in the chosen group: stay');
  assert.equal(LR.pickFocusMenuTown(taiwan, '香港城'), taiwan.towns[0], 'not in the group: first town in list order');
  assert.equal(LR.pickFocusMenuTown(taiwan, null), taiwan.towns[0]);
  assert.equal(LR.findFocusMenuGroup(menu, 'ruler:不存在'), null);
  assert.equal(LR.findFocusMenuGroup(menu, 'bogus'), null);
  assert.equal(LR.findFocusMenuGroup(LR.buildFocusMenu(null), 'ruler:臺灣'), null);
  assert.equal(LR.pickFocusMenuTown(null, '臺北'), null);
  assert.equal(LR.pickFocusMenuTown({ towns: [] }, '臺北'), null);
});

test('focus menu opens / picks only from the snapshot answering its own request (stale or foreign snapshots never count)', () => {
  const snap = (req) => groupSnapshot(CHOICE_TARGETS, req === undefined ? {} : { req });
  assert.equal(LR.matchesMenuRequest({ req: 5 }, snap(5)), true);
  assert.equal(LR.matchesMenuRequest({ req: 5 }, snap(6)), false);
  assert.equal(LR.matchesMenuRequest({ req: 5 }, snap()), false, 'a routine push without req is not the answer');
  assert.equal(LR.matchesMenuRequest(null, snap(5)), false);
  assert.equal(LR.matchesMenuRequest({ req: 5 }, null), false);
});

test('focus menu snapshot verdict: needs the matching req, a prior timely ok:true and arrival before the 1000 ms timeout', () => {
  const snap = (req) => groupSnapshot(CHOICE_TARGETS, req === undefined ? {} : { req });
  const pending = { req: 5, at: 1000, acked: true };
  assert.equal(LR.DEFAULT_GUARD_CONFIG.mapAckTimeoutMs, 1000);
  assert.equal(LR.menuSnapshotVerdict(pending, snap(5), 1010), 'accept');
  assert.equal(LR.menuSnapshotVerdict(pending, snap(5), 1999), 'accept', 'last millisecond before the timeout');
  assert.equal(LR.menuSnapshotVerdict(pending, snap(5), 2000), 'stale', 'at the timeout: never opens or selects');
  assert.equal(LR.menuSnapshotVerdict(pending, snap(5), 2600), 'stale');
  assert.equal(LR.menuSnapshotVerdict({ ...pending, acked: false }, snap(5), 1010), 'stale', 'no matching ok:true yet');
  assert.equal(LR.menuSnapshotVerdict({ req: 5, at: 1000 }, snap(5), 1010), 'stale', 'ack flag missing');
  assert.equal(LR.menuSnapshotVerdict(pending, snap(6), 1010), 'ignore', 'another request: wait for ours (times out)');
  assert.equal(LR.menuSnapshotVerdict(pending, snap(), 1010), 'ignore', 'routine push without req');
  assert.equal(LR.menuSnapshotVerdict(pending, null, 1010), 'invalid', 'a schema-invalid snapshot while waiting fails closed');
  assert.equal(LR.menuSnapshotVerdict(null, snap(5), 1010), 'ignore', 'nothing pending');
  assert.equal(LR.menuSnapshotVerdict(null, null, 1010), 'ignore');
  assert.equal(LR.menuSnapshotVerdict({ req: 5, at: 'x', acked: true }, snap(5), 1010), 'stale', 'unknown send time');
});

test('focus menu snapshot request: a successful ack starts no activation cooldown; only the caller does after opening or focusing', () => {
  const g = LR.beginMapRequest(LR.createGuard(), 1000, 4, { cmd: 'snapshot', noActivation: true });
  assert.equal(g.mapRequest.noActivation, true);
  const res = C.sanitizeMapResult({ type: 'redline-controller-result', v: 1, cmd: 'snapshot', req: 4, ok: true });
  const out = LR.settleMapResult(g, 1010, res);
  assert.equal(out.outcome, 'success');
  assert.equal(out.lock, false);
  assert.equal(out.guard.activatedAt, null, 'a fail-closed open / pick must not block the next executing key');
  assert.equal(out.guard.mapRequest, null);
  for (const cmd of ['mapAct', 'focusMenuPick', 'endStep', 'factionAbility']) assert.equal(LR.gate(out.guard, 1020, 1, cmd).allowed, true, cmd);
  // 其他地圖指令照舊：成功確認才記錄 250ms 冷卻
  const act = LR.settleMapResult(LR.beginMapRequest(LR.createGuard(), 1000, 5, { cmd: 'act', lock: true }), 1010,
    C.sanitizeMapResult({ type: 'redline-controller-result', v: 1, cmd: 'act', req: 5, ok: true }));
  assert.equal(act.guard.activatedAt, 1010);
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
