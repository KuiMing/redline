// node --test scripts/tests/js/living_room_core.test.js
const test = require('node:test');
const assert = require('node:assert/strict');
const LR = require('../../../static/living_room_core.js');
const C = require('../../../static/controller_core.js');

const press = button => LR.logicalAction({ type: 'press', button });
const nav = dir => LR.logicalAction({ type: 'nav', dir, repeat: false });
const zoneCtx = (extra = {}) => ({ scopeKind: 'page', view: 'command', layer: 'zone', zone: 'hand', locked: false, mapCanCancel: false, item: null, ...extra });
const itemCtx = (item, extra = {}) => zoneCtx({ layer: 'item', item, ...extra });
const handItem = { card: { zone: 'hand', hasToggle: false }, slot: false, mapRow: false };
const buyItem = { card: { zone: 'purchase', hasToggle: true }, slot: false, mapRow: false };
const slotItem = { card: null, slot: true, mapRow: false };
const rowItem = { card: null, slot: false, mapRow: true };
const controlItem = { card: null, slot: false, mapRow: false };

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

test('PLUS and ZR are bound only in the living-room mapping; HOME/CAPTURE/STICK/SL stay unbound', () => {
  assert.deepEqual(press('PLUS'), { name: 'focusActionBar' });
  assert.deepEqual(press('ZR'), { name: 'zoneBack' });
  for (const b of ['HOME', 'CAPTURE', 'STICK', 'SL']) assert.equal(press(b), null, b);
  // desktop mapping is untouched: + still does nothing there
  assert.equal(C.logicalAction({ type: 'press', button: 'PLUS' }), null);
  assert.equal(C.logicalAction({ type: 'press', button: 'ZR' }), null);
});

// ---- router: zone layer ----

test('zone layer: stick moves between zones, A enters, B is a no-op, X/PLUS only focus the action bar', () => {
  assert.deepEqual(LR.routeLivingRoom(zoneCtx(), nav('down')), { cmd: 'zoneMove', dir: 'down' });
  assert.deepEqual(LR.routeLivingRoom(zoneCtx(), press('A')), { cmd: 'enterZone' });
  assert.equal(LR.routeLivingRoom(zoneCtx(), press('B')), null);
  assert.deepEqual(LR.routeLivingRoom(zoneCtx(), press('X')), { cmd: 'focusActionBar' });
  assert.deepEqual(LR.routeLivingRoom(zoneCtx(), press('PLUS')), { cmd: 'focusActionBar' });
  assert.deepEqual(LR.routeLivingRoom(zoneCtx(), press('Y')), { cmd: 'toggleHelp' });
  assert.deepEqual(LR.routeLivingRoom(zoneCtx(), press('R')), { cmd: 'ring', step: 1 });
  assert.deepEqual(LR.routeLivingRoom(zoneCtx(), press('SR')), { cmd: 'ring', step: -1 });
  assert.equal(LR.routeLivingRoom(zoneCtx({ zone: null }), press('A')), null);
});

test('zone layer ZR: no-op in command view, returns to command view elsewhere unless the map is locked', () => {
  assert.equal(LR.routeLivingRoom(zoneCtx(), press('ZR')), null);
  assert.deepEqual(LR.routeLivingRoom(zoneCtx({ view: 'log' }), press('ZR')), { cmd: 'leaveView' });
  assert.deepEqual(LR.routeLivingRoom(zoneCtx({ view: 'map', scopeKind: 'map' }), press('ZR')), { cmd: 'leaveView' });
  assert.equal(LR.routeLivingRoom(zoneCtx({ view: 'map', scopeKind: 'map', locked: true }), press('ZR')), null);
});

test('PLUS never maps to an executing command in any layer', () => {
  const ctxs = [zoneCtx(), itemCtx(handItem), itemCtx(buyItem), itemCtx(slotItem, { zone: 'actionbar' }), itemCtx(rowItem, { zone: 'maplist', scopeKind: 'map' })];
  for (const ctx of ctxs) assert.deepEqual(LR.routeLivingRoom(ctx, press('PLUS')), { cmd: 'focusActionBar' });
});

// ---- router: item layer, card semantics identical to desktop ----

test('purchase card: A preview, B toggle, X/Y full no-op (same as controller_core.routeAction)', () => {
  assert.deepEqual(LR.routeLivingRoom(itemCtx(buyItem), press('A')), { cmd: 'cardPreview' });
  assert.deepEqual(LR.routeLivingRoom(itemCtx(buyItem), press('B')), { cmd: 'cardToggle' });
  assert.equal(LR.routeLivingRoom(itemCtx(buyItem), press('X')), null);
  assert.equal(LR.routeLivingRoom(itemCtx(buyItem), press('Y')), null);
});

test('hand card: A preview, B no-op without checkbox, X resource, Y action', () => {
  assert.deepEqual(LR.routeLivingRoom(itemCtx(handItem), press('A')), { cmd: 'cardPreview' });
  assert.equal(LR.routeLivingRoom(itemCtx(handItem), press('B')), null);
  assert.deepEqual(LR.routeLivingRoom(itemCtx(handItem), press('X')), { cmd: 'cardMode', mode: 'resource' });
  assert.deepEqual(LR.routeLivingRoom(itemCtx(handItem), press('Y')), { cmd: 'cardMode', mode: 'action' });
});

test('card semantics are delegated, so they match desktop routing for every button', () => {
  for (const item of [handItem, buyItem]) {
    for (const button of ['A', 'B', 'X', 'Y']) {
      const lr = LR.routeLivingRoom(itemCtx(item), press(button));
      const desktop = C.routeAction({ scopeKind: 'page', hasFocus: true, card: item.card, cancelAvailable: false, sectionsLocked: false }, C.logicalAction({ type: 'press', button }));
      assert.deepEqual(lr, desktop, `${item.card.zone}:${button}`);
    }
  }
});

test('item layer: stick moves inside the zone, ZR returns to the zone layer, R/SR still ring', () => {
  assert.deepEqual(LR.routeLivingRoom(itemCtx(handItem), nav('right')), { cmd: 'itemMove', dir: 'right' });
  assert.deepEqual(LR.routeLivingRoom(itemCtx(handItem), press('ZR')), { cmd: 'toZoneLayer' });
  assert.deepEqual(LR.routeLivingRoom(itemCtx(buyItem), press('ZR')), { cmd: 'toZoneLayer' });
  assert.deepEqual(LR.routeLivingRoom(itemCtx(handItem), press('R')), { cmd: 'ring', step: 1 });
});

test('item layer non-card: A activates existing control / slot / map row; B returns to zone layer', () => {
  assert.deepEqual(LR.routeLivingRoom(itemCtx(controlItem, { zone: 'status' }), press('A')), { cmd: 'activate' });
  assert.deepEqual(LR.routeLivingRoom(itemCtx(slotItem, { zone: 'actionbar' }), press('A')), { cmd: 'slotActivate' });
  assert.deepEqual(LR.routeLivingRoom(itemCtx(rowItem, { zone: 'maplist', scopeKind: 'map' }), press('A')), { cmd: 'mapPick' });
  assert.deepEqual(LR.routeLivingRoom(itemCtx(slotItem, { zone: 'actionbar' }), press('B')), { cmd: 'toZoneLayer' });
  assert.deepEqual(LR.routeLivingRoom(itemCtx(controlItem, { zone: 'status' }), press('X')), { cmd: 'focusActionBar' });
  assert.equal(LR.routeLivingRoom(itemCtx(null, { zone: 'maplist' }), press('A')), null, 'empty map list: A does nothing');
});

test('map list B: existing map cancel when available, else back to zone layer; locked map blocks R/SR/ZR', () => {
  const map = (extra) => itemCtx(rowItem, { zone: 'maplist', scopeKind: 'map', view: 'map', ...extra });
  assert.deepEqual(LR.routeLivingRoom(map({ mapCanCancel: true }), press('B')), { cmd: 'mapCancel' });
  assert.deepEqual(LR.routeLivingRoom(map({}), press('B')), { cmd: 'toZoneLayer' });
  assert.equal(LR.routeLivingRoom(map({ locked: true }), press('B')), null);
  assert.deepEqual(LR.routeLivingRoom(map({ locked: true, mapCanCancel: true }), press('B')), { cmd: 'mapCancel' });
  assert.equal(LR.routeLivingRoom(map({ locked: true }), press('ZR')), null);
  assert.equal(LR.routeLivingRoom(map({ locked: true }), press('R')), null);
  assert.equal(LR.routeLivingRoom(map({ locked: true }), press('SR')), null);
  // map cancel only applies inside the list zone, not from the action bar
  assert.deepEqual(LR.routeLivingRoom(itemCtx(slotItem, { zone: 'actionbar', scopeKind: 'map', mapCanCancel: true }), press('B')), { cmd: 'toZoneLayer' });
});

// ---- guard ----

test('processing lock blocks submits until the next authoritative state or timeout; focus moves stay allowed', () => {
  let g = LR.lockProcessing(LR.createGuard(), 1000, 7);
  for (const cmd of ['activate', 'slotActivate', 'cardMode', 'cardToggle', 'mapPick', 'mapCancel']) {
    assert.equal(LR.gate(g, 1100, 7, cmd).allowed, false, cmd);
    assert.equal(LR.gate(g, 1100, 7, cmd).reason, 'processing');
  }
  for (const cmd of ['itemMove', 'zoneMove', 'focusActionBar', 'toZoneLayer', 'ring', 'cardPreview']) {
    assert.equal(LR.gate(g, 1100, 7, cmd).allowed, true, cmd);
  }
  // new state arrives (token changes) → unlocked
  const after = LR.gate(g, 1100, 8, 'cardMode');
  assert.equal(after.allowed, true);
  assert.equal(after.guard.lockedAt, null);
  // timeout → unlocked
  assert.equal(LR.gate(g, 1000 + LR.DEFAULT_GUARD_CONFIG.processingTimeoutMs, 7, 'activate').allowed, true);
  g = LR.createGuard();
  assert.equal(LR.processingActive(g, 0, 1), false);
});

test('redraw cooldown ignores A/X/Y-type commands shortly after a non-user focus change', () => {
  const g = LR.noteRedraw(LR.createGuard(), 5000);
  for (const cmd of ['activate', 'slotActivate', 'cardMode', 'cardPreview', 'enterZone', 'mapPick']) {
    assert.equal(LR.gate(g, 5100, 1, cmd).reason, 'redraw-cooldown', cmd);
  }
  assert.equal(LR.gate(g, 5100, 1, 'itemMove').allowed, true);
  assert.equal(LR.gate(g, 5000 + LR.DEFAULT_GUARD_CONFIG.redrawCooldownMs, 1, 'activate').allowed, true);
});

test('post-activation cooldown: every executing command waits 250ms after an actual activation', () => {
  const ms = LR.DEFAULT_GUARD_CONFIG.activationCooldownMs;
  assert.equal(ms, 250);
  const g = LR.noteActivation(LR.createGuard(), 1000);
  for (const cmd of ['activate', 'slotActivate', 'cardMode', 'cardToggle', 'cardPreview', 'enterZone', 'mapPick', 'mapCancel', 'modalConfirm']) {
    const blocked = LR.gate(g, 1000 + ms - 1, 1, cmd);
    assert.equal(blocked.allowed, false, cmd);
    assert.equal(blocked.reason, 'activation-cooldown', cmd);
    assert.equal(LR.gate(g, 1000 + ms, 1, cmd).allowed, true, `${cmd} after cooldown`);
  }
});

test('post-activation cooldown never delays navigation or back/escape keys', () => {
  const g = LR.noteActivation(LR.createGuard(), 1000);
  for (const cmd of ['itemMove', 'zoneMove', 'ring', 'focusActionBar', 'toZoneLayer', 'leaveView', 'toggleHelp']) {
    assert.equal(LR.gate(g, 1001, 1, cmd).allowed, true, cmd);
  }
});

test('B double press: a successful cardToggle blocks a second toggle within 250ms', () => {
  // first B: nothing recorded yet → allowed; the UI toggled the checkbox, so it records the activation
  let g = LR.createGuard();
  const first = LR.gate(g, 5000, 1, 'cardToggle');
  assert.equal(first.allowed, true);
  g = LR.noteActivation(first.guard, 5000);
  // second B 100ms later would toggle the same checkbox back off → must be ignored
  assert.equal(LR.gate(g, 5100, 1, 'cardToggle').reason, 'activation-cooldown');
  // a deliberate press after the window works again
  assert.equal(LR.gate(g, 5250, 1, 'cardToggle').allowed, true);
});

test('failed (no-op) cardToggle does not start the cooldown: gate alone never records activation', () => {
  const g = LR.createGuard();
  const first = LR.gate(g, 5000, 1, 'cardToggle');
  assert.equal(first.allowed, true);
  assert.equal(first.guard.activatedAt, null, 'gate must not record; only an actual toggle calls noteActivation');
  // checkbox was hidden/disabled → toggle returned false → no noteActivation → next legit B 10ms later is allowed
  assert.equal(LR.gate(first.guard, 5010, 1, 'cardToggle').allowed, true);
});

test('enterZone cooldown: entering a zone (e.g. the map list) blocks an immediate pick of its first item', () => {
  let g = LR.createGuard();
  const enter = LR.gate(g, 2000, 1, 'enterZone');
  assert.equal(enter.allowed, true);
  g = LR.noteActivation(enter.guard, 2000);
  assert.equal(LR.gate(g, 2100, 1, 'mapPick').reason, 'activation-cooldown');
  assert.equal(LR.gate(g, 2100, 1, 'slotActivate').reason, 'activation-cooldown');
  assert.equal(LR.gate(g, 2100, 1, 'itemMove').allowed, true, 'moving inside the zone stays immediate');
  assert.equal(LR.gate(g, 2250, 1, 'mapPick').allowed, true);
});

test('server-sending mapCancel cannot repeat: processing lock outlasts the 250ms cooldown until new state', () => {
  let g = LR.noteActivation(LR.createGuard(), 3000);
  g = LR.lockProcessing(g, 3000, 4);
  assert.equal(LR.gate(g, 3100, 4, 'mapCancel').reason, 'processing');
  assert.equal(LR.gate(g, 3400, 4, 'mapCancel').reason, 'processing', 'still locked after the cooldown');
  assert.equal(LR.gate(g, 3400, 5, 'mapCancel').allowed, true, 'new authoritative state unlocks');
  // selection-only cancel (no lock) is still rate-limited by the cooldown
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

const ack = (req, ok, extra = {}) => C.sanitizeMapResult({ type: 'redline-controller-result', v: 1, cmd: 'button', req, ok, ...extra });

test('map ack: only a matching ok:true result records the cooldown and requested lock', () => {
  let g = LR.beginMapRequest(LR.createGuard(), 1000, 5, { cmd: 'button', lock: true });
  assert.equal(g.activatedAt, null, 'sending alone records nothing');
  assert.equal(g.lockedAt, null, 'sending alone does not lock');
  const out = LR.settleMapResult(g, 1010, ack(5, true, { via: 'confirmMoveBtn' }));
  assert.equal(out.outcome, 'success');
  assert.equal(out.lock, true);
  assert.equal(out.guard.activatedAt, 1010);
  assert.equal(out.guard.mapRequest, null);
  assert.equal(LR.gate(out.guard, 1100, 1, 'slotActivate').reason, 'activation-cooldown');
});

test('map ack ok:false fails closed and the next legal action is not blocked by the cooldown', () => {
  const g = LR.beginMapRequest(LR.createGuard(), 1000, 6, { cmd: 'button', lock: true });
  const out = LR.settleMapResult(g, 1010, ack(6, false, { reason: 'button-unavailable' }));
  assert.equal(out.outcome, 'failed');
  assert.equal(out.lock, false);
  assert.equal(out.guard.activatedAt, null);
  assert.equal(out.guard.lockedAt, null);
  assert.equal(out.guard.mapRequest, null);
  for (const cmd of ['slotActivate', 'mapPick', 'mapCancel', 'activate', 'cardToggle']) {
    assert.equal(LR.gate(out.guard, 1020, 1, cmd).allowed, true, `${cmd} right after a failed map command`);
  }
});

test('map ack: no reply times out without cooldown or lock; a late reply is stale and ignored', () => {
  const g = LR.beginMapRequest(LR.createGuard(), 1000, 7, { cmd: 'button', lock: true });
  // 等待中：執行型指令一律擋下（不重送），方向與返回不受影響
  assert.equal(LR.gate(g, 1120, 1, 'slotActivate').reason, 'map-pending');
  assert.equal(LR.gate(g, 1120, 1, 'mapPick').reason, 'map-pending');
  for (const cmd of ['zoneMove', 'itemMove', 'toZoneLayer', 'focusActionBar', 'ring']) assert.equal(LR.gate(g, 1120, 1, cmd).allowed, true, cmd);
  assert.equal(LR.expireMapRequest(g, 1999).expired, null, 'not yet expired');
  const exp = LR.expireMapRequest(g, 2000);
  assert.equal(exp.expired.req, 7);
  assert.deepEqual(exp.guard, LR.createGuard(), 'timeout leaves no cooldown, lock or pending request');
  assert.equal(LR.gate(g, 2000, 1, 'slotActivate').allowed, true, 'gate itself expires the request');
  assert.equal(LR.gate(g, 2000, 1, 'slotActivate').guard.mapRequest, null);
  const late = LR.settleMapResult(exp.guard, 2050, ack(7, true));
  assert.equal(late.outcome, 'stale');
  assert.deepEqual(late.guard, LR.createGuard());
  // 回覆在計時器清掉前抵達但已逾時：同樣視為未執行
  const slow = LR.settleMapResult(g, 2001, ack(7, true));
  assert.equal(slow.outcome, 'timeout');
  assert.equal(slow.guard.activatedAt, null);
  assert.equal(slow.lock, false);
});

test('map ack: mismatched, missing or wrong-command req is stale and keeps the pending request', () => {
  const g = LR.beginMapRequest(LR.createGuard(), 1000, 8, { cmd: 'button', lock: true });
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
  assert.deepEqual(ack(4, true, { via: 'selection' }), { cmd: 'button', ok: true, req: 4, via: 'selection', reason: null });
  assert.equal(ack(4, 'true'), null, 'ok must be boolean');
  assert.equal(ack(0, true), null);
  assert.equal(ack(4, true, { via: 'advanceStepBtn' }), null, 'via must be a map control');
  assert.equal(ack(4, true, { cmd: 'rm' }), null);
  assert.equal(C.sanitizeMapResult({ type: 'redline-controller-result', v: 2, cmd: 'button', req: 4, ok: true }), null);
});

// ---- action bar ----

const src = (id, extra = {}) => ({ id, kind: LR.MAP_SLOT_IDS.includes(id) ? 'map' : 'dom', label: id, visible: true, disabled: false, ariaDisabled: false, inert: false, ...extra });

test('action bar aggregates only visible, enabled, whitelisted existing controls', () => {
  const slots = LR.buildActionBar([
    src('advanceStepBtn', { label: '結束行動' }),
    src('openPurchaseConfirmBtn', { disabled: true }),
    src('clearPurchaseSelectionBtn', { visible: false }),
    src('topdeckRightBtn', { ariaDisabled: true }),
    src('redArmyAbilityBtn', { inert: true }),
    src('emergencyNewGameBtn'),
    src('advanceStepBtn', { label: 'dup' }),
    src('confirmMoveBtn', { kind: 'dom' }),          // map id must come from the iframe snapshot
    src('openPurchaseConfirmBtn', { kind: 'map', label: 'x' }),
    src('handDiscard', { label: '   ' }),
    null,
  ]);
  assert.deepEqual(slots, [{ id: 'advanceStepBtn', kind: 'dom', label: '結束行動', danger: true }]);
});

test('action bar order: map confirm → purchase → others → dangerous last; default slot skips danger', () => {
  const slots = LR.buildActionBar([
    src('advanceStepBtn'), src('handDiscard'), src('redArmyAbilityBtn'), src('openPurchaseConfirmBtn'), src('confirmMoveBtn'),
  ]);
  assert.deepEqual(slots.map(s => s.id), ['confirmMoveBtn', 'openPurchaseConfirmBtn', 'redArmyAbilityBtn', 'handDiscard', 'advanceStepBtn']);
  assert.deepEqual(slots.map(s => s.danger), [false, false, false, true, true]);
  assert.equal(LR.defaultSlotIndex(slots), 0);
  assert.equal(LR.defaultSlotIndex(LR.buildActionBar([src('advanceStepBtn')])), 0);
  assert.equal(LR.defaultSlotIndex(LR.buildActionBar([src('redArmyAbilityBtn'), src('advanceStepBtn')])), 0);
  assert.equal(LR.defaultSlotIndex([]), -1);
});

// ---- focus model ----

test('reconcile: same key stays, missing key clamps to the same index, danger or empty → zone layer', () => {
  assert.equal(LR.reconcileIndex(['a', 'b', 'c'], 'b', 1), 1);
  assert.equal(LR.reconcileIndex(['a', 'c', 'b'], 'b', 1), 2);
  assert.equal(LR.reconcileIndex(['a', 'c'], 'b', 1), 1);
  assert.equal(LR.reconcileIndex(['a'], 'b', 4), 0);
  assert.equal(LR.reconcileIndex([], 'b', 0), -1);
  const danger = new Set(['slot:advanceStepBtn']);
  assert.equal(LR.reconcileIndex(['slot:redArmyAbilityBtn', 'slot:advanceStepBtn'], 'slot:openPurchaseConfirmBtn', 1, danger), -1);
  assert.equal(LR.reconcileIndex(['slot:redArmyAbilityBtn', 'slot:advanceStepBtn'], 'slot:advanceStepBtn', 0, danger), 1, 'user chose it: keep');
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

test('zones: ring cycles, direction picks, default never lands on the action bar', () => {
  const ids = ['status', 'static', 'hand', 'actionbar'];
  assert.equal(LR.cycleZone(ids, 'hand', 1), 'actionbar');
  assert.equal(LR.cycleZone(ids, 'actionbar', 1), 'status');
  assert.equal(LR.cycleZone(ids, 'status', -1), 'actionbar');
  assert.equal(LR.cycleZone(ids, 'gone', 1), 'status');
  const zones = [
    { id: 'static', rect: { left: 0, top: 100, right: 600, bottom: 300 } },
    { id: 'random', rect: { left: 620, top: 100, right: 1260, bottom: 300 } },
    { id: 'hand', rect: { left: 0, top: 320, right: 1260, bottom: 600 } },
    { id: 'actionbar', rect: { left: 0, top: 650, right: 1260, bottom: 700 } },
  ];
  assert.equal(LR.pickZone(zones, 'static', 'right'), 'random');
  assert.equal(LR.pickZone(zones, 'random', 'down'), 'hand');
  assert.equal(LR.pickZone(zones, 'hand', 'down'), 'actionbar');
  assert.equal(LR.pickZone(zones, 'static', 'left'), 'static', 'no zone that way: stay');
  // a full-width zone going up prefers the panels directly above over a closer-centred top bar
  const withStatus = [...zones, { id: 'status', rect: { left: 0, top: 0, right: 1280, bottom: 48 } }];
  assert.ok(['static', 'random'].includes(LR.pickZone(withStatus, 'hand', 'up')));
  assert.equal(LR.pickZone(withStatus, 'static', 'up'), 'status');
  assert.equal(LR.pickZone(withStatus, 'missing', 'up'), 'static');
  assert.equal(LR.resolveZone(['actionbar', 'static', 'hand'], null), 'hand');
  assert.equal(LR.resolveZone(['actionbar', 'static', 'hand'], 'static'), 'static');
  assert.equal(LR.resolveZone(['actionbar', 'static'], 'actionbar'), 'static');
  assert.equal(LR.resolveZone(['actionbar'], null), null);
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
  const s1 = LR.buildMapList(snap({ targets: [{ town: '乙', role: 'origin' }, { town: '甲', role: 'origin' }] }));
  assert.equal(s1.stage, 'source');
  assert.deepEqual(s1.rows.map(r => r.town).sort(), ['乙', '甲'].sort());
  const s2 = LR.buildMapList(snap({
    selected: '甲', canCancel: true,
    targets: [
      { town: '丙', role: 'move', mode: 'rail', cost: 1 },
      { town: '丁', role: 'move', mode: 'road', cost: 1 },
      { town: '戊', role: 'move', mode: 'road', cost: 0 },
      { town: '甲', role: 'origin' },
    ],
    pending: { from: '甲', to: '丙', mode: 'rail', cost: 1 },
  }));
  assert.equal(s2.stage, 'destination');
  assert.deepEqual(s2.rows.map(r => r.town), ['戊', '丁', '丙']);
  assert.equal(s2.rows[0].cost, 0, 'zero cost is preserved');
  assert.deepEqual(s2.pending, { from: '甲', to: '丙', mode: 'rail', cost: 1 });
  assert.equal(s2.canCancel, true);
  // pending that does not belong to the selected origin / legal rows is dropped
  assert.equal(LR.buildMapList(snap({ selected: '甲', targets: [{ town: '丙', role: 'move' }], pending: { from: '乙', to: '丙' } })).pending, null);
  assert.equal(LR.buildMapList(snap({ selected: '甲', targets: [{ town: '丙', role: 'move' }], pending: { from: '甲', to: '庚' } })).pending, null);
  // selected without legal destinations stays on the source list
  assert.equal(LR.buildMapList(snap({ selected: '甲', targets: [{ town: '甲', role: 'origin' }] })).stage, 'source');
});

test('map list choice stage shows pending-choice targets and the current selection', () => {
  const list = LR.buildMapList(snap({ scope: 'choice', selected: '丁', targets: [{ town: '丁', role: 'choice' }, { town: '戊', role: 'choice' }] }));
  assert.equal(list.stage, 'choice');
  assert.equal(list.selected, '丁');
  assert.equal(LR.buildMapList(snap({ scope: 'choice', selected: '庚', targets: [{ town: '丁', role: 'choice' }] })).selected, null);
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

test('snapshot sanitize: optional move meta / selected / pending are validated, zero cost kept', () => {
  const base = { type: 'redline-controller-map-snapshot', v: 1, scope: 'move', buttons: [], targets: [{ town: '乙', role: 'move', x: 1, y: 2, mode: 'road', cost: 0 }] };
  const ok = C.sanitizeMapSnapshot({ ...base, selected: '甲', pending: { from: '甲', to: '乙', mode: 'road', cost: 0 } });
  assert.deepEqual(ok.targets[0], { town: '乙', role: 'move', x: 1, y: 2, mode: 'road', cost: 0 });
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

test('snapshot model: move meta, selection and pending come only from authoritative inputs', () => {
  const input = {
    hasState: true, viewerCanAct: true, pendingChoiceBlocksMoves: false, highlight: null,
    visibleTowns: ['甲', '乙', '丙'], knownTowns: ['甲', '乙', '丙'],
    moveTargets: [{ town: '乙', mode: 'rail', cost: 0 }, { town: '丙', mode: 'bogus', cost: 'x' }],
    selectedTown: '甲', originTowns: ['甲'], buttons: [],
    pendingMoveTarget: { from: '甲', to: '乙', mode: 'rail', cost: 0 },
  };
  const m = C.buildMapSnapshotModel(input);
  assert.deepEqual(m.targets, [{ town: '乙', role: 'move', mode: 'rail', cost: 0 }, { town: '丙', role: 'move' }, { town: '甲', role: 'origin' }]);
  assert.equal(m.selected, '甲');
  assert.deepEqual(m.pending, { from: '甲', to: '乙', mode: 'rail', cost: 0 });
  assert.equal(C.buildMapSnapshotModel({ ...input, pendingMoveTarget: { from: '甲', to: '不存在' } }).pending, null);
  assert.equal(C.buildMapSnapshotModel({ ...input, pendingMoveTarget: { from: '丙', to: '乙' } }).pending, null);
  assert.equal(C.buildMapSnapshotModel({ ...input, viewerCanAct: false }).selected, null);
});
