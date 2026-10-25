// node --test scripts/tests/js/controller_dual.test.js
// 獨立左右 Joy-Con（bridge v2）：瀏覽器端只收共用邏輯 layout、只收本分頁綁定的那一支、桌面／客廳 parity、舊版 payload 相容。
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const C = require('../../../static/controller_core.js');
const LR = require('../../../static/living_room_core.js');

// 規格對照表（與 Python bridge 測試共用；逐字取自規格，不由實作推導）。
const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'fixtures', 'joycon_dual_layout.json'), 'utf8'));
const LOGICAL = Object.fromEntries(Object.entries(FIXTURE.logical_bits).map(([k, [i, m]]) => [k, [i, parseInt(m, 16)]]));
const bytesOf = (...names) => { const b = [0, 0]; for (const n of names) { const [i, m] = LOGICAL[n]; b[i] |= m; } return b; };
const pressedNames = (b) => Object.entries(C.decodeButtonBytes(b[0], b[1])).filter(([, v]) => v).map(([k]) => k);

const L1 = 'L24801-0a1b2c3d';
const L2 = 'L24802-0a1b2c3d';
const R1 = 'R24800-3f2a9c1e';
const v2frame = (controller, side, buttons = [0, 0], epoch = 1, x = 0, y = 0) => ({ type: 'frame', v: 2, controller, side, epoch, x, y, buttons });
const roster = (controllers, owned = null) => ({ type: 'roster', v: 2, owned, controllers });
const ctrl = (id, side, status = 'active', owner = null, extra = {}) => ({
  id, side, status, owner, name: side === 'left' ? 'Joy-Con 2 (L)' : 'Joy-Con 2 (R)', endpoint: `127.0.0.1:${id.slice(1, 6)}`, sideSource: 'name', ...extra,
});

/** 一位玩家（一個分頁）的瀏覽器輸入路徑：classify → 只收綁定的手把 → reducer。回傳送進 reducer 與否。 */
function player(owned, side) {
  const p = { binding: { mode: 'v2', owned, side }, pad: { input: C.createInputState(), key: null }, fired: [], guard: LR.createGuard() };
  p.deliver = (raw, t) => {
    const msg = C.classifyBridgeMessage(raw, p.binding.mode);
    if (!C.acceptControllerFrame(p.binding, msg)) return false;
    const step = C.stepControllerInput(p.pad, msg, t);
    p.pad = step.pad;
    p.fired.push(...step.actions);
    return true;
  };
  return p;
}

function pressThrough(side, logicalName) {
  const p = player(side === 'left' ? L1 : R1, side);
  for (const [t, buttons] of [[0, [0, 0]], [16, bytesOf(logicalName)], [33, [0, 0]]]) {
    assert.equal(p.deliver(v2frame(p.binding.owned, side, buttons), t), true);
  }
  return p.fired;
}

test('fixture: the bridge logical layout is exactly the browser BUTTON_BITS; every logical byte decodes to one button', () => {
  assert.deepEqual(Object.keys(LOGICAL).sort(), [...C.BUTTON_NAMES].sort());
  for (const [name, bits] of Object.entries(LOGICAL)) assert.deepEqual(C.BUTTON_BITS[name], bits, name);
  for (const entry of FIXTURE.inputs) assert.deepEqual(pressedNames(bytesOf(entry.logical)), [entry.logical], `${entry.side} ${entry.physical}`);
});

// [桌面 Core.logicalAction, 客廳 LR.logicalAction]（桌面的 + 與 Capture 由 layer.desktopShortcutOf＝LR.logicalAction 處理）。
const EXPECTED_LOGICAL = {
  Up: ['focusTurnBar', 'focusTurnBar'], Right: ['confirm', 'confirm'], Down: ['cancel', 'cancel'], Left: ['toggleHelp', 'toggleHelp'],
  'Stick press': [null, 'nextZone'], L: ['nextSection', 'nextSection'], ZL: ['mapZoom', 'mapZoom'], '-': [null, 'factionAbility'],
  Capture: [null, 'endStep'], SR: ['focusMenu', 'focusMenu'], SL: ['prevSection', 'prevSection'],
};
const DESKTOP_CTX = [
  { scopeKind: 'page', hasFocus: true, card: null, cancelAvailable: false, sectionsLocked: false },
  { scopeKind: 'map', hasFocus: true, mapTarget: true, cancelAvailable: true, sectionsLocked: false },
  { scopeKind: 'map', hasFocus: true, mapTarget: true, cancelAvailable: true, sectionsLocked: true },
  { scopeKind: 'modal', hasFocus: true, cancelAvailable: true },
  { scopeKind: 'modal', hasFocus: true, cancelAvailable: true, focusMenuOpen: true },
  { scopeKind: 'page', hasFocus: true, card: { zone: 'hand', hasToggle: false } },
  { scopeKind: 'page', hasFocus: true, card: { zone: 'hand', hasToggle: false, hasDiscard: true } },
  { scopeKind: 'page', hasFocus: true, card: { zone: 'purchase', hasToggle: true } },
];
const LR_CTX = [
  { scopeKind: 'page', view: 'command', layer: 'zone', zone: 'hand' },
  { scopeKind: 'page', view: 'command', layer: 'item', zone: 'hand', item: { card: { zone: 'hand', hasToggle: false, hasDiscard: true } } },
  { scopeKind: 'page', view: 'command', layer: 'item', zone: 'static', item: { card: { zone: 'purchase', hasToggle: true } } },
  { scopeKind: 'map', view: 'map', layer: 'item', zone: 'maplist', item: { mapRow: true }, mapCanCancel: true },
  { scopeKind: 'map', view: 'map', layer: 'item', zone: 'maplist', choiceLock: true, locked: true, item: { mapRow: true } },
];

test('desktop / living-room parity: every left input routes exactly like its right equivalent in both display modes', () => {
  const right = new Map(FIXTURE.inputs.filter(e => e.side === 'right').map(e => [e.physical, e]));
  const lefts = FIXTURE.inputs.filter(e => e.side === 'left');
  assert.equal(lefts.length, Object.keys(EXPECTED_LOGICAL).length);
  for (const entry of lefts) {
    const twin = right.get(entry.right_equivalent);
    const leftActions = pressThrough('left', entry.logical);
    const rightActions = pressThrough('right', twin.logical);
    assert.deepEqual(leftActions, [{ type: 'press', button: entry.logical }], entry.physical);
    assert.deepEqual(leftActions, rightActions, entry.physical);
    const [desktopName, livingName] = EXPECTED_LOGICAL[entry.physical];
    const desktop = C.logicalAction(leftActions[0]);
    const living = LR.logicalAction(leftActions[0]);
    assert.equal(desktop ? desktop.name : null, desktopName, entry.physical);
    assert.equal(living ? living.name : null, livingName, entry.physical);
    assert.deepEqual(desktop, C.logicalAction(rightActions[0]));
    assert.deepEqual(living, LR.logicalAction(rightActions[0]));
    for (const ctx of DESKTOP_CTX) assert.deepEqual(C.routeAction(ctx, desktop), C.routeAction(ctx, C.logicalAction(rightActions[0])), entry.physical);
    for (const ctx of LR_CTX) assert.deepEqual(LR.routeLivingRoom(ctx, living), LR.routeLivingRoom(ctx, LR.logicalAction(rightActions[0])), entry.physical);
  }
});

test('stick parity: a left stick push navigates exactly like the same right stick push', () => {
  for (const [x, y, dir] of [[0, -0.9, 'up'], [0, 0.9, 'down'], [-0.9, 0, 'left'], [0.9, 0, 'right']]) {
    const out = {};
    for (const [id, side] of [[L1, 'left'], [R1, 'right']]) {
      const p = player(id, side);
      p.deliver(v2frame(id, side, [0, 0], 1, 0, 0), 0);
      p.deliver(v2frame(id, side, [0, 0], 1, x, y), 16);
      out[side] = p.fired;
    }
    assert.deepEqual(out.left, [{ type: 'nav', dir, repeat: false }]);
    assert.deepEqual(out.left, out.right);
  }
});

test('capture and home never mix: left Capture is CAPTURE (end step); right HOME stays HOME (unbound); no left input is HOME', () => {
  assert.deepEqual(pressedNames(bytesOf('CAPTURE')), ['CAPTURE']);
  assert.deepEqual(pressedNames(bytesOf('HOME')), ['HOME']);
  assert.equal(FIXTURE.inputs.find(e => e.side === 'left' && e.physical === 'Capture').logical, 'CAPTURE');
  assert.ok(!FIXTURE.inputs.some(e => e.side === 'left' && e.logical === 'HOME'));
  assert.equal(LR.logicalAction({ type: 'press', button: 'CAPTURE' }).name, 'endStep');
  assert.equal(LR.logicalAction({ type: 'press', button: 'HOME' }), null);
  assert.equal(C.logicalAction({ type: 'press', button: 'HOME' }), null);
});

test('controller ids are per endpoint and strict (never just left/right)', () => {
  for (const ok of [R1, L1, 'R24800-legacy', 'L1-0a1b2c3d', 'R65535-legacy']) assert.equal(C.isControllerId(ok), true, ok);
  for (const bad of ['left', 'right', 'L', 'R24800', 'R0-legacy', 'R65536-legacy', 'R024800-legacy', 'X24800-legacy', 'L24801-0A1B2C3D',
    'L24801-0a1b2c3', `${L1} `, `${L1}\n`, 'legacy', '', null, undefined, 24800, {}, 'L24801-0a1b2c3d'.repeat(2)]) {
    assert.equal(C.isControllerId(bad), false, String(bad));
  }
});

test('roster: schema enforced, ids must match their side, only the owned controller may be "you"; anything else fails closed', () => {
  const good = roster([ctrl(R1, 'right', 'active', 'you'), ctrl(L1, 'left', 'stale', 'other')], R1);
  const s = C.sanitizeRoster(good);
  assert.equal(s.owned, R1);
  assert.deepEqual(s.controllers.map(c => [c.id, c.side, c.status, c.owner, c.name]),
    [[R1, 'right', 'active', 'you', 'Joy-Con 2 (R)'], [L1, 'left', 'stale', 'other', 'Joy-Con 2 (L)']]);
  assert.equal(C.sanitizeRoster(roster([])).owned, null);
  const bad = [
    { ...good, v: 1 }, { ...good, type: 'frame' }, { ...good, controllers: 'x' },
    roster([ctrl('left', 'left')]), roster([ctrl(L1, 'right')]), roster([ctrl(L1, 'left', 'gone')]),
    roster([ctrl(L1, 'left', 'active', 'them')]), roster([ctrl(L1, 'left'), ctrl(L1, 'left')]),
    roster([ctrl(L1, 'left', 'active', 'you')]), roster([ctrl(L1, 'left')], R1), roster([ctrl(L1, 'left', 'active', 'other')], L1),
    roster([ctrl(L1, 'left', 'active', null, { name: 'x'.repeat(65) })]), roster([ctrl(L1, 'left', 'active', null, { sideSource: 'guess' })]),
    roster(Array.from({ length: 17 }, (_, i) => ctrl(`L${24801 + i}-0a1b2c3d`, 'left'))),
    { ...roster([]), lost: { controller: 'left', reason: 'replaced' } }, { ...roster([]), lost: { controller: L1, reason: 'x'.repeat(40) } },
  ];
  for (const b of bad) assert.equal(C.sanitizeRoster(b), null, JSON.stringify(b).slice(0, 160));
  assert.deepEqual(C.sanitizeRoster({ ...roster([]), lost: { controller: L1, reason: 'replaced' } }).lost, { controller: L1, reason: 'replaced' });
});

test('claim results are schema-checked', () => {
  assert.deepEqual(C.sanitizeClaimResult({ type: 'claim-result', v: 2, request: 'claim', ok: false, controller: null, reason: 'claimed' }),
    { request: 'claim', ok: false, controller: null, reason: 'claimed' });
  assert.deepEqual(C.sanitizeClaimResult({ type: 'claim-result', v: 2, request: 'claim-default', ok: true, controller: R1, reason: null }),
    { request: 'claim-default', ok: true, controller: R1, reason: null });
  for (const bad of [{ v: 1 }, { request: 'steal' }, { ok: 'yes' }, { controller: 'left' }, { reason: 'x'.repeat(40) }, { type: 'roster' }]) {
    assert.equal(C.sanitizeClaimResult({ type: 'claim-result', v: 2, request: 'claim', ok: true, controller: null, reason: null, ...bad }), null, JSON.stringify(bad));
  }
});

test('bridge messages: typed v2 frames need a valid id, matching side and epoch; unknown types are dropped', () => {
  assert.deepEqual(C.classifyBridgeMessage(v2frame(L1, 'left', [0x20, 0], 3, 0, -0.9), 'v2'),
    { kind: 'frame', controller: L1, side: 'left', epoch: 3, frame: C.normalizeFrame({ x: 0, y: -0.9, buttons: [0x20, 0] }) });
  const f = v2frame(L1, 'left');
  for (const bad of [{ ...f, controller: 'left' }, { ...f, side: 'middle' }, { ...f, side: 'right' }, { ...f, epoch: -1 }, { ...f, epoch: 1.5 },
    { ...f, epoch: '1' }, { ...f, v: 1 }, { ...f, buttons: [256, 0] }, { ...f, x: NaN }, { ...f, y: 2 }, { type: 'hello', v: 2 }, null, 'x', [1, 2]]) {
    assert.equal(C.classifyBridgeMessage(bad, 'v2'), null, JSON.stringify(bad));
  }
  assert.equal(C.classifyBridgeMessage(roster([]), 'legacy').kind, 'roster'); // roster 讓頁面切到 v2
  assert.equal(C.classifyBridgeMessage({ type: 'claim-result', v: 2, request: 'release', ok: true, controller: null, reason: null }, 'v2').kind, 'claim');
  assert.deepEqual(C.bridgeHello(), { type: 'hello', v: 2 });
});

test('legacy single right Joy-Con payload: old-bridge frames still work before any v2 roster, and only then', () => {
  const raw = { x: 0.5, y: 0.25, buttons: [0x08, 0x00] };
  const msg = C.classifyBridgeMessage(raw, 'legacy');
  assert.deepEqual(msg, { kind: 'frame', controller: C.LEGACY_CONTROLLER_ID, side: 'right', epoch: 0, frame: C.normalizeFrame(raw) });
  const legacy = player(C.LEGACY_CONTROLLER_ID, 'right');
  legacy.binding.mode = 'legacy';
  for (const [t, buttons] of [[0, [0, 0]], [16, [0x08, 0]], [33, [0, 0]], [50, [0, 0x20]], [66, [0, 0]], [83, [0, 0x40]]]) legacy.deliver({ x: 0, y: 0, buttons }, t);
  assert.deepEqual(legacy.fired.map(a => a.button), ['A', 'CAPTURE', 'CAPTURE']); // 舊版 bridge 的上游 capture（b1 0x20）仍是 CAPTURE
  assert.equal(C.logicalAction(legacy.fired[0]).name, 'confirm');
  assert.equal(C.classifyBridgeMessage(raw, 'v2'), null);                         // v2 bridge 不會送無型別 frame
  assert.equal(C.classifyBridgeMessage(v2frame(R1, 'right'), 'legacy'), null);    // 有型別的 frame 要先收到 v2 roster
  assert.equal(C.acceptControllerFrame({ mode: 'v2', owned: R1, side: 'right' }, msg), false);
});

test('only the owned controller reaches the reducer; interleaved frames from other controllers never fire or release held state', () => {
  const p = player(L1, 'left');
  assert.equal(p.deliver(v2frame(L1, 'left'), 0), true);                      // baseline
  assert.equal(p.deliver(v2frame(R1, 'right', bytesOf('A')), 5), false);      // 另一位玩家的 A
  assert.equal(p.deliver(v2frame(L2, 'left', bytesOf('A')), 6), false);       // 另一支左手的 A
  assert.equal(p.deliver(v2frame(L1, 'right', bytesOf('A')), 7), false);      // id 對但左右不符
  assert.deepEqual(p.fired, []);
  assert.equal(p.deliver(v2frame(L1, 'left', bytesOf('A')), 10), true);
  assert.equal(p.deliver(v2frame(R1, 'right'), 12), false);                   // 別人的 neutral 不會放開我的 A
  assert.equal(p.deliver(v2frame(L1, 'left', bytesOf('A')), 20), true);       // 仍按住 → 不重複
  assert.deepEqual(p.fired, [{ type: 'press', button: 'A' }]);
  assert.equal(p.pad.input.held.A, true);
  assert.equal(C.acceptControllerFrame({ mode: 'v2', owned: null, side: null }, C.classifyBridgeMessage(v2frame(L1, 'left'), 'v2')), false); // 未 claim
});

test('switching controllers or a reconnect epoch starts a fresh baseline: a held button never auto-fires', () => {
  const p = player(L1, 'left');
  p.deliver(v2frame(L1, 'left'), 0);
  p.binding = { mode: 'v2', owned: R1, side: 'right' };                       // 換成右手
  p.deliver(v2frame(R1, 'right', bytesOf('A'), 1), 10);                       // 新手把第一筆已按住 → baseline
  p.deliver(v2frame(R1, 'right', bytesOf('A'), 1), 20);
  assert.deepEqual(p.fired, []);
  p.deliver(v2frame(R1, 'right', [0, 0], 1), 30);
  p.deliver(v2frame(R1, 'right', bytesOf('A'), 1), 40);
  assert.deepEqual(p.fired, [{ type: 'press', button: 'A' }]);
  p.deliver(v2frame(R1, 'right', bytesOf('A'), 2), 50);                       // 同一支重新連線（epoch 2）仍按住 → baseline
  p.deliver(v2frame(R1, 'right', [0, 0], 2, 0.9, 0), 60);                    // 重連第一筆已推到底的搖桿也不觸發（第二筆才是 edge）
  assert.deepEqual(p.fired, [{ type: 'press', button: 'A' }, { type: 'nav', dir: 'right', repeat: false }]);
  assert.equal(C.frameInputKey({ controller: R1, epoch: 2 }), `${R1}#2`);
});

test('two players at once: separate pipelines and guards never share edge, cooldown, map-request or processing-lock state', () => {
  const a = player(R1, 'right');
  const b = player(L1, 'left');
  const broadcast = [[0, [0, 0], [0, 0]], [16, bytesOf('A'), bytesOf('A')], [33, bytesOf('A'), [0, 0]], [50, [0, 0], bytesOf('A')]];
  for (const [t, rb, lb] of broadcast) {
    for (const p of [a, b]) { p.deliver(v2frame(R1, 'right', rb), t); p.deliver(v2frame(L1, 'left', lb), t); }
  }
  assert.deepEqual(a.fired, [{ type: 'press', button: 'A' }]);
  assert.deepEqual(b.fired, [{ type: 'press', button: 'A' }, { type: 'press', button: 'A' }]);
  a.guard = LR.lockProcessing(LR.noteActivation(a.guard, 100), 100, 1);
  assert.equal(LR.gate(a.guard, 150, 1, 'activate').allowed, false);
  assert.equal(LR.gate(b.guard, 150, 1, 'activate').allowed, true);
  b.guard = LR.beginMapRequest(b.guard, 160, 7, { cmd: 'act', lock: true });
  assert.equal(LR.gate(b.guard, 170, 1, 'mapAct').reason, 'map-pending');
  assert.equal(a.guard.mapRequest, null);
  assert.equal(LR.gate(a.guard, 2000, 2, 'mapZoom').allowed, true);
});

test('auto-claim: remembered controller or exactly one active unowned controller; never steals or guesses between two', () => {
  const auto = { mode: 'auto' };
  const one = c => C.sanitizeRoster(roster([c], c.owner === 'you' ? c.id : null));
  assert.deepEqual(C.autoClaimDecision(auto, one(ctrl(R1, 'right'))), { type: 'claim', controller: R1 });
  assert.deepEqual(C.autoClaimDecision(auto, one(ctrl(L1, 'left'))), { type: 'claim', controller: L1 });
  assert.equal(C.autoClaimDecision(auto, one(ctrl(R1, 'right', 'stale'))), null);
  assert.equal(C.autoClaimDecision(auto, one(ctrl(R1, 'right', 'active', 'other'))), null);
  assert.equal(C.autoClaimDecision(auto, one(ctrl(R1, 'right', 'active', 'you'))), null);       // 已經有
  assert.equal(C.autoClaimDecision(auto, C.sanitizeRoster(roster([ctrl(R1, 'right'), ctrl(L1, 'left')]))), null); // 兩支：要明確選
  assert.deepEqual(C.autoClaimDecision(auto, C.sanitizeRoster(roster([ctrl(R1, 'right'), ctrl(L1, 'left', 'stale')]))), { type: 'claim', controller: R1 });
  assert.deepEqual(C.autoClaimDecision(auto, C.sanitizeRoster(roster([ctrl(R1, 'right', 'stale'), ctrl(L1, 'left')]))), { type: 'claim', controller: L1 });
  assert.deepEqual(C.autoClaimDecision(auto, C.sanitizeRoster(roster([ctrl(R1, 'right', 'active', 'other'), ctrl(L1, 'left')]))), { type: 'claim', controller: L1 });
  const remembered = { mode: 'id', id: L1 };
  assert.deepEqual(C.autoClaimDecision(remembered, C.sanitizeRoster(roster([ctrl(R1, 'right'), ctrl(L1, 'left')]))), { type: 'claim', controller: L1 });
  assert.equal(C.autoClaimDecision(remembered, C.sanitizeRoster(roster([ctrl(R1, 'right'), ctrl(L1, 'left', 'active', 'other')]))), null);
  assert.equal(C.autoClaimDecision(remembered, C.sanitizeRoster(roster([ctrl(R1, 'right'), ctrl(L1, 'left', 'stale')]))), null);
  assert.equal(C.autoClaimDecision(remembered, one(ctrl(R1, 'right'))), null);   // 記住的那支不在：不會改拿唯一的右手
  assert.equal(C.autoClaimDecision({ mode: 'none' }, one(ctrl(R1, 'right'))), null); // 玩家明確不用手把
  assert.equal(C.autoClaimDecision(auto, null), null);
  assert.deepEqual(C.normalizeClaimPref(null), { mode: 'auto' });
  assert.deepEqual(C.normalizeClaimPref({ mode: 'auto' }), { mode: 'auto' });
  assert.deepEqual(C.normalizeClaimPref({ mode: 'id', id: L1 }), { mode: 'id', id: L1 });
  assert.deepEqual(C.normalizeClaimPref({ mode: 'none' }), { mode: 'none' });
  for (const bad of [{ mode: 'id', id: 'left' }, { mode: 'steal' }, 'garbage', 7]) assert.deepEqual(C.normalizeClaimPref(bad), { mode: 'none' }, JSON.stringify(bad));
});

// 玩家可見文字不得出現 FTCW UDP 埠（4 位數以上）、名稱指紋（8 位 hex）、legacy、內部 id 開頭、bridge name 的 (L)/(R)、endpoint。
const LEAK = /\d{4,}|[0-9a-f]{8}|legacy|[LR]\d|\((?:L|R)\)|127\.0\.0\.1|埠/;

test('HUD names the bound controller by side only, with a stable per-side number from the current roster (no port / id / fingerprint)', () => {
  const one = [ctrl(L1, 'left'), ctrl(R1, 'right')];
  assert.equal(C.controllerLabel(ctrl(L1, 'left'), one), '左 Joy-Con');
  assert.equal(C.controllerLabel(ctrl(R1, 'right'), one), '右 Joy-Con');
  assert.equal(C.controllerLabel(ctrl(L1, 'left')), '左 Joy-Con'); // 沒有 roster 也只回左右
  // 同側多支：依目前 roster 的埠號（同埠依完整 id）排序給序號；與 roster 順序無關
  const two = [ctrl(L2, 'left'), ctrl(R1, 'right'), ctrl(L1, 'left')];
  assert.equal(C.controllerLabel(ctrl(L1, 'left'), two), '左 Joy-Con 1');
  assert.equal(C.controllerLabel(ctrl(L2, 'left'), two), '左 Joy-Con 2');
  assert.equal(C.controllerLabel(ctrl(L2, 'left'), [...two].reverse()), '左 Joy-Con 2');
  assert.equal(C.controllerLabel(ctrl(R1, 'right'), two), '右 Joy-Con');
  assert.equal(C.controllerLabel({ id: 'R24800-legacy', side: 'right', name: null, sideSource: 'legacy-default' }, [{ id: 'R24800-legacy', side: 'right' }]),
    '右 Joy-Con（未回報名稱，預設右手）');
  assert.equal(C.controllerLabel({ id: C.LEGACY_CONTROLLER_ID, side: 'right' }), '右 Joy-Con（舊版 bridge 相容）');
  assert.equal(C.bindingBadge({ owned: L1, side: 'left' }, one), '左 Joy-Con');
  assert.equal(C.bindingBadge({ owned: L2, side: 'left' }, two), '左 Joy-Con 2');
  assert.equal(C.bindingBadge({ owned: R1, side: 'right' }, two), '右 Joy-Con');
  assert.equal(C.bindingBadge({ owned: R1, side: 'right' }), '右 Joy-Con');
  assert.equal(C.bindingBadge({ owned: C.LEGACY_CONTROLLER_ID, side: 'right' }), '右 Joy-Con');
  assert.equal(C.bindingBadge({ owned: null, side: null }), '');
  for (const label of [...two.map(c => C.controllerLabel(c, two)), ...two.map(c => C.bindingBadge({ owned: c.id, side: c.side }, two)),
    C.controllerLabel({ id: 'R24800-legacy', side: 'right', sideSource: 'legacy-default' }), C.lostReasonText('replaced'), C.lostReasonText('unidentified')]) {
    assert.doesNotMatch(label, LEAK, label);
  }
  const legend = C.sideKeyLegend('left');
  for (const pair of ['→＝A', '↓＝B', '↑＝X', '←＝Y', 'L＝R', 'ZL＝ZR', '−＝+', 'SR＝SL', 'SL＝SR']) assert.ok(legend.includes(pair), pair);
  assert.equal(C.sideKeyLegend('right'), null);
  assert.equal(C.claimReasonText('claimed'), '這支手把已被其他玩家使用');
  assert.equal(C.lostReasonText('replaced'), '原本的手把已被另一支裝置取代');
});

test('HUD and hot-seat lobby number the same roster identically (one shared naming rule)', () => {
  const H = require('../../../static/hotseat_core.js');
  const sets = [
    [L1, R1], [L2, L1, R1], ['R9-01234567', R1, 'R24801-aaaabbbb'], ['L24801-ffffffff', L1], ['R24800-legacy', 'R24802-11112222'], [],
  ];
  for (const ids of sets) {
    const controllers = ids.map(id => ({ id, side: id[0] === 'L' ? 'left' : 'right' }));
    assert.deepEqual(C.controllerDisplayNames(ids), H.controllerDisplayNames(ids), ids.join(','));
    const lobbyLabel = H.controllerNames(controllers);
    for (const c of controllers) {
      assert.equal(C.bindingBadge({ owned: c.id, side: c.side }, controllers), lobbyLabel(c.id), c.id);
      assert.equal(C.controllerLabel(c, controllers), lobbyLabel(c.id), c.id);
    }
  }
});

test('unbound (v2 bridge connected, no controller claimed) drops all input and hides shortcuts', () => {
  assert.equal(C.bridgeInputGate({ enabled: true, status: 'unbound', socketOpen: true, fromBridge: true }), 'drop');
  assert.equal(C.bridgeConnected({ enabled: true, status: 'unbound', socketOpen: true }), false);
});

test('start-screen nav: exactly one active controller not used by another tab; otherwise fail closed', () => {
  const sr = (cs, owned = null) => C.sanitizeRoster(roster(cs, owned));
  // 起始畫面 + 恰好一支有訊號：不用 SL＋SR，直接 claim（決策本身不帶席位、不帶 server 操作）。
  assert.equal(C.startNavCandidate(sr([ctrl(L1, 'left')])), L1);
  assert.deepEqual(C.startNavDecision(sr([ctrl(L1, 'left')]), null), { type: 'claim', controller: L1 });
  assert.deepEqual(Object.keys(C.startNavDecision(sr([ctrl(R1, 'right')]), null)).sort(), ['controller', 'type']);
  // 已經是本分頁的：不重送。
  assert.equal(C.startNavDecision(sr([ctrl(L1, 'left', 'active', 'you')], L1), L1), null);
  // 已登錄但 stale 的其他手把不算（與既有單手把自動 claim 相同）。
  assert.equal(C.startNavCandidate(sr([ctrl(L1, 'left'), ctrl(R1, 'right', 'stale')])), L1);
  // 0 支、多支、stale、other-tab、missing（沒有清單）、不合法清單：都不選。
  assert.equal(C.startNavDecision(sr([]), null), null);
  assert.equal(C.startNavDecision(sr([ctrl(L1, 'left'), ctrl(R1, 'right')]), null), null);
  assert.equal(C.startNavDecision(sr([ctrl(L1, 'left'), ctrl(R1, 'right', 'active', 'other')]), null), null);
  assert.equal(C.startNavDecision(sr([ctrl(L1, 'left', 'stale')]), null), null);
  assert.equal(C.startNavDecision(sr([ctrl(L1, 'left', 'active', 'other')]), null), null);
  assert.equal(C.startNavDecision(null, null), null);
  const invalid = C.sanitizeRoster(roster([{ ...ctrl(L1, 'left'), side: 'right' }]));
  assert.equal(invalid, null);
  assert.equal(C.startNavDecision(invalid, null), null);
  assert.equal(C.startNavCandidate({ controllers: [{ id: 'not-an-id', status: 'active', owner: null }] }), null);
  // roster 改變：變成多支、該手把 stale、消失、換成另一支 → 撤銷擁有的那支。
  assert.deepEqual(C.startNavDecision(sr([ctrl(L1, 'left', 'active', 'you'), ctrl(R1, 'right')], L1), L1), { type: 'release' });
  assert.deepEqual(C.startNavDecision(sr([ctrl(L1, 'left', 'stale', 'you')], L1), L1), { type: 'release' });
  assert.deepEqual(C.startNavDecision(sr([]), L1), { type: 'release' });
  assert.deepEqual(C.startNavDecision(sr([ctrl(R1, 'right')]), L1), { type: 'release' });
  assert.deepEqual(C.startNavDecision(null, L1), { type: 'release' });
  // 撤銷後恢復成恰好一支：重新 claim（新連線第一筆 frame 仍只當 baseline，由 stepControllerInput 保證）。
  assert.deepEqual(C.startNavDecision(sr([ctrl(L1, 'left'), ctrl(R1, 'right', 'stale')]), null), { type: 'claim', controller: L1 });
});

test('start-screen nav: newly claimed or reconnected controller treats held A as baseline only', () => {
  const p = player(L1, 'left');
  const A = bytesOf('A');
  assert.equal(p.deliver(v2frame(L1, 'left', A, 1), 0), true);   // 拿到時已按住 A：baseline
  assert.equal(p.deliver(v2frame(L1, 'left', A, 1), 30), true);
  assert.deepEqual(p.fired, []);
  p.deliver(v2frame(L1, 'left', [0, 0], 1), 60);
  p.deliver(v2frame(L1, 'left', A, 1), 90);
  assert.deepEqual(p.fired, [{ type: 'press', button: 'A' }]);
  // bridge 重連（epoch 改變）時仍按著 A：只當 baseline。
  p.deliver(v2frame(L1, 'left', A, 2), 120);
  p.deliver(v2frame(L1, 'left', A, 2), 150);
  assert.deepEqual(p.fired, [{ type: 'press', button: 'A' }]);
});

test('Joy-Con help ring: left L／SL after bridge normalization route exactly like right R／SR (incl. on the help button)', () => {
  const lefts = Object.fromEntries(FIXTURE.inputs.filter(e => e.side === 'left').map(e => [e.physical, e]));
  const HELP_CTX = { scopeKind: 'page', hasFocus: true, helpEntry: true, card: null, cancelAvailable: false, sectionsLocked: false };
  for (const [physical, rightName, step] of [['L', 'R', 1], ['SL', 'SR', -1]]) {
    const left = pressThrough('left', lefts[physical].logical);
    const right = pressThrough('right', rightName);
    assert.deepEqual(left, right, physical);
    assert.deepEqual(C.routeAction(HELP_CTX, C.logicalAction(left[0])), { cmd: 'section', step }, physical);
  }
  // A（左＝→）在說明按鈕上開圖；B（左＝↓）不作用；左 SR（＝右 SL）仍是全域城鎮聚焦。
  assert.deepEqual(C.routeAction(HELP_CTX, C.logicalAction(pressThrough('left', lefts.Right.logical)[0])), { cmd: 'openHelp' });
  assert.equal(C.routeAction(HELP_CTX, C.logicalAction(pressThrough('left', lefts.Down.logical)[0])), null);
  assert.deepEqual(C.routeAction(HELP_CTX, C.logicalAction(pressThrough('left', lefts.SR.logical)[0])), { cmd: 'focusMenu' });
});
