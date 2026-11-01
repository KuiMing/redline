// node --test scripts/tests/js/controller_game_menu.test.js
// 遊戲選單（遊戲中按住搖桿按鈕 2 秒）：長按門檻、neutral／資格／active controller、release gate、選單內 scope lock，
// 以及整段長按不產生任何個別按鍵命令或遊戲 mutation。
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const C = require('../../../static/controller_core.js');

const ROOT = path.join(__dirname, '..', '..', '..');
const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'fixtures', 'joycon_dual_layout.json'), 'utf8'));
const LOGICAL = Object.fromEntries(Object.entries(FIXTURE.logical_bits).map(([k, [i, m]]) => [k, [i, parseInt(m, 16)]]));
const bytesOf = (...names) => { const b = [0, 0]; for (const n of names) { const [i, m] = LOGICAL[n]; b[i] |= m; } return b; };

const L1 = 'L24801-0a1b2c3d';
const R1 = 'R24800-3f2a9c1e';
const R2 = 'R24802-3f2a9c1e';
const v2frame = (controller, side, buttons = [0, 0], x = 0, y = 0, epoch = 1) => ({ type: 'frame', v: 2, controller, side, epoch, x, y, buttons });

// 可以開啟的情境（gameMenuBlocker → null）。
const OK_CTX = Object.freeze({
  connected: true, owned: true, hidden: false, startFlow: false, inGame: true, hasState: true,
  handoff: false, activeController: true, modal: false, choiceRedirect: false,
});

/**
 * 一個分頁的瀏覽器輸入路徑，與 controller_ui.js 的 ingest → trackStickHold → dispatch 同一順序：
 * classify → 只收綁定的手把 → reducer → release gate → 長按累積（資格＝gameMenuBlocker）→ 剩下的 action 照常 routing。
 * env()：每一筆 frame 當下的情境（覆寫 OK_CTX；key＝長按情境）。menuOpen 由 fire 打開（之後 modal＝true）。
 */
function player(owned, side, env = () => ({})) {
  const p = {
    binding: { mode: 'v2', owned, side }, pad: { input: C.createInputState(), key: null },
    hold: C.createStickHold(), gate: C.createMenuGate(null), menuOpen: false,
    dispatched: [], fired: 0, cancelled: 0, firedAt: null,
  };
  p.deliver = (raw, t) => {
    const msg = C.classifyBridgeMessage(raw, p.binding.mode);
    if (!C.acceptControllerFrame(p.binding, msg)) return false;
    const step = C.stepControllerInput(p.pad, msg, t);
    p.pad = step.pad;
    const held = p.pad.input.held;
    p.gate = C.stepMenuGate(p.gate, held);
    const e = env(t) || {};
    const ctx = { ...OK_CTX, ...e, modal: p.menuOpen || e.modal === true };
    const pressed = step.actions.some(a => a.type === 'press' && a.button === 'STICK');
    const evaluate = held.STICK === true && (pressed || p.hold.since !== null);
    const r = C.stepStickHold(p.hold, {
      pressed, held: held.STICK === true, neutral: p.pad.input.dir === null,
      others: C.BUTTON_NAMES.some(n => n !== 'STICK' && held[n] === true),
      eligible: evaluate && C.gameMenuBlocker(ctx) === null,
      // 與 controller_ui.js stickHoldKey 相同：含 reducer 屬於哪一支手把／epoch（重新連線＝情境改變）。
      key: evaluate ? JSON.stringify([p.pad.key, e.key ?? 'game']) : null,
    }, t);
    p.hold = r.hold;
    if (r.cancelled) p.cancelled += 1;
    if (r.fire) { p.fired += 1; p.firedAt = t; p.menuOpen = true; p.gate = C.createMenuGate(held); }
    p.dispatched.push(...(r.consume ? step.actions.filter(a => !(a.type === 'press' && a.button === 'STICK')) : step.actions));
    return true;
  };
  /** bridge 30Hz：[from, to] 每 33ms 一筆，最後一筆剛好在 to。 */
  p.stream = (from, to, buttons, x = 0, y = 0, controller = owned, frameSide = side) => {
    for (let t = from; t < to; t += 33) p.deliver(v2frame(controller, frameSide, buttons, x, y), t);
    p.deliver(v2frame(controller, frameSide, buttons, x, y), to);
  };
  return p;
}

const STICK = bytesOf('STICK');
const IDLE = [0, 0];

test('fixture: both the left and the right Joy-Con stick click arrive as the same logical STICK', () => {
  const sticks = FIXTURE.inputs.filter(i => i.physical === 'Stick press');
  assert.deepEqual(sticks.map(i => [i.side, i.logical]).sort(), [['left', 'STICK'], ['right', 'STICK']]);
  const decoded = C.decodeButtonBytes(...STICK);
  assert.deepEqual(Object.keys(decoded).filter(k => decoded[k]), ['STICK']);
  assert.equal(C.GAME_MENU_HOLD_MS, 2000);
});

for (const [owned, side] of [[R1, 'right'], [L1, 'left']]) {
  test(`${side} Joy-Con: holding the stick click for 2s at neutral opens the menu exactly once`, () => {
    const p = player(owned, side);
    p.stream(0, 100, IDLE);
    p.stream(133, 133 + 1999, STICK); // 1999ms：還沒到
    assert.equal(p.fired, 0);
    assert.notEqual(p.hold.since, null, 'still accumulating');
    p.stream(133 + 2000, 133 + 4500, STICK); // 到達 2000ms 後繼續按住：只觸發一次
    assert.equal(p.fired, 1);
    assert.equal(p.firedAt, 133 + 2000);
    assert.equal(p.cancelled, 0);
    // 長按本身不產生任何個別按鍵命令（STICK press 被長按吃掉，沒有方向、沒有其他按鍵）。
    assert.deepEqual(p.dispatched, []);
  });
}

test('releasing before 2s never opens; the STICK press of the attempt is not dispatched either', () => {
  for (const ms of [33, 500, 1500, 1966]) {
    const p = player(R1, 'right');
    p.stream(0, 100, IDLE);
    p.stream(133, 133 + ms, STICK);
    p.stream(133 + ms + 33, 133 + ms + 3000, IDLE);
    assert.equal(p.fired, 0, `${ms}ms`);
    assert.equal(p.cancelled, 1, `${ms}ms`);
    assert.deepEqual(p.hold, C.createStickHold(), 'released → fresh');
    assert.deepEqual(p.dispatched, [], `${ms}ms`);
  }
});

test('leaving neutral cancels immediately; re-centering while still held does not resume (release + press again)', () => {
  const p = player(R1, 'right');
  p.stream(0, 100, IDLE);
  p.stream(133, 1133, STICK);
  p.deliver(v2frame(R1, 'right', STICK, 0.9, 0), 1166); // 推離中央
  assert.equal(p.cancelled, 1);
  assert.equal(p.hold.since, null);
  assert.equal(p.hold.latched, true);
  p.stream(1199, 5000, STICK); // 回到中央但一直按住：不重新累積、不觸發
  assert.equal(p.fired, 0);
  // 推離中央那一筆是真正的方向輸入，照常 dispatch（不是長按造成的）
  assert.deepEqual(p.dispatched, [{ type: 'nav', dir: 'right', repeat: false }]);
  p.stream(5033, 5100, IDLE); // 放開 → 重新按下才重新累積
  p.stream(5133, 7133, STICK);
  assert.equal(p.fired, 1);
});

test('a stick deflected when the click starts does not accumulate, and the click is routed as a normal (no-op) press', () => {
  const p = player(R1, 'right');
  p.stream(0, 100, IDLE, 0, 0.8);
  p.stream(133, 3500, STICK, 0, 0.8);
  assert.equal(p.fired, 0);
  assert.equal(p.hold.latched, true);
  const presses = p.dispatched.filter(a => a.type === 'press');
  assert.deepEqual(presses, [{ type: 'press', button: 'STICK' }]);
  assert.equal(C.logicalAction(presses[0]), null, 'desktop STICK has no logical action');
});

test('pressing any other button during the hold cancels it (no chord entry such as X+Y+A+B)', () => {
  for (const other of ['A', 'B', 'X', 'Y', 'R', 'SR', 'SL', 'ZR', 'PLUS', 'CAPTURE', 'HOME']) {
    const p = player(R1, 'right');
    p.stream(0, 100, IDLE);
    p.stream(133, 1000, STICK);
    p.stream(1033, 4000, bytesOf('STICK', other));
    assert.equal(p.fired, 0, other);
    assert.equal(p.cancelled, 1, other);
  }
  // 同時按住 X+Y+A+B 再按搖桿：不合資格，永遠不開
  const p = player(R1, 'right');
  p.stream(0, 100, bytesOf('X', 'Y', 'A', 'B'));
  p.stream(133, 4000, bytesOf('X', 'Y', 'A', 'B', 'STICK'));
  assert.equal(p.fired, 0);
});

test('blockers: pairing／start flow, loading, handoff, any overlay, disconnected, unbound, hidden → never opens', () => {
  const cases = {
    disconnected: { connected: false }, unbound: { owned: false }, hidden: { hidden: true }, 'start-flow': { startFlow: true },
    'not-in-game': { inGame: false }, loading: { hasState: false }, handoff: { handoff: true },
    'not-active-controller': { activeController: false }, overlay: { modal: true }, 'choice-redirect': { choiceRedirect: true },
  };
  assert.equal(C.gameMenuBlocker(OK_CTX), null);
  for (const [reason, override] of Object.entries(cases)) {
    assert.equal(C.gameMenuBlocker({ ...OK_CTX, ...override }), reason, reason);
    const p = player(R1, 'right', () => override);
    p.stream(0, 100, IDLE);
    p.stream(133, 5000, STICK);
    assert.equal(p.fired, 0, reason);
    assert.equal(p.hold.since, null, reason);
    // 不合資格時 STICK 不被長按吃掉，照既有 routing（例如必選地圖目標時先切回戰略地圖）
    assert.deepEqual(p.dispatched, [{ type: 'press', button: 'STICK' }], reason);
  }
  // fail closed：缺欄位一律不開
  assert.notEqual(C.gameMenuBlocker({}), null);
  assert.notEqual(C.gameMenuBlocker(null), null);
  for (const field of ['startFlow', 'handoff', 'modal', 'choiceRedirect']) {
    assert.notEqual(C.gameMenuBlocker({ ...OK_CTX, [field]: undefined }), null, field);
  }
});

test('only the active controller: a non-active seat cannot open it, and frames of another Joy-Con never reach this tab', () => {
  // hot-seat：這支手把不是目前行動席位的 Joy-Con（gate.allowsPage false）
  const seat = player(R1, 'right', () => ({ activeController: false }));
  seat.stream(0, 100, IDLE);
  seat.stream(133, 5000, STICK);
  assert.equal(seat.fired, 0);
  // 本分頁綁定 R1；R2 的 frame（另一位玩家的手把）一律丟棄，長按不會開始
  const p = player(R1, 'right');
  p.stream(0, 100, IDLE);
  p.stream(133, 5000, STICK, 0, 0, R2, 'right');
  assert.equal(p.fired, 0);
  assert.equal(p.hold.since, null);
  assert.equal(p.pad.input.held.STICK, false);
});

test('losing eligibility or a state switch mid-hold cancels immediately', () => {
  for (const [label, at] of [['overlay', { modal: true }], ['handoff', { handoff: true }], ['inactive', { activeController: false }],
    ['disconnect', { connected: false }], ['state', { key: 'next-player' }]]) {
    const p = player(R1, 'right', t => (t >= 1200 ? at : {}));
    p.stream(0, 100, IDLE);
    p.stream(133, 5000, STICK);
    assert.equal(p.fired, 0, label);
    assert.equal(p.cancelled, 1, label);
  }
});

test('reconnecting (new epoch) while holding: the held click is only a baseline and never opens the menu', () => {
  const p = player(R1, 'right');
  p.stream(0, 100, IDLE);
  p.stream(133, 1000, STICK);
  for (let t = 1033; t < 5000; t += 33) p.deliver(v2frame(R1, 'right', STICK, 0, 0, 2), t); // 重新連線：epoch 2，第一筆＝baseline
  assert.equal(p.fired, 0);
  assert.equal(p.cancelled, 1);
  assert.equal(p.hold.latched, true);
  // 從 baseline 起就按住（沒有按下瞬間）：放開前永遠不累積
  const q = player(R1, 'right');
  q.stream(0, 4000, STICK);
  assert.equal(q.fired, 0);
  assert.equal(q.hold.latched, true);
  assert.deepEqual(q.dispatched, []);
});

test('release gate: after opening, nothing works until the stick click is released; held A/B do not leak to the next layer', () => {
  const p = player(R1, 'right');
  p.stream(0, 100, IDLE);
  p.stream(133, 2200, STICK);
  assert.equal(p.fired, 1);
  assert.deepEqual(p.gate.blocked, ['STICK']);
  for (const a of [{ type: 'press', button: 'A' }, { type: 'press', button: 'B' }, { type: 'nav', dir: 'down', repeat: false }, null]) {
    assert.equal(C.menuGateAllows(p.gate, a), false, JSON.stringify(a));
  }
  p.stream(2233, 2300, STICK); // 仍按住
  assert.deepEqual(p.gate.blocked, ['STICK']);
  p.deliver(v2frame(R1, 'right', IDLE), 2333); // 放開
  assert.deepEqual(p.gate.blocked, []);
  assert.equal(C.menuGateAllows(p.gate, { type: 'press', button: 'A' }), true);
  // 選「重新開始」的 A 仍按住時開啟確認層：同一個 A 在放開前不作用
  let gate = C.createMenuGate({ A: true });
  assert.equal(C.menuGateAllows(gate, { type: 'press', button: 'A' }), false);
  assert.equal(C.menuGateAllows(gate, { type: 'press', button: 'B' }), true);
  assert.equal(C.menuGateAllows(gate, { type: 'nav', dir: 'left' }), true);
  gate = C.stepMenuGate(gate, { A: true });
  assert.deepEqual(gate.blocked, ['A']);
  gate = C.stepMenuGate(gate, { A: false });
  assert.equal(C.menuGateAllows(gate, { type: 'press', button: 'A' }), true);
  // 確認層按 B 返回選單：B 仍按住時，選單的 B（返回遊戲）不作用
  gate = C.createMenuGate({ B: true });
  assert.equal(C.menuGateAllows(gate, { type: 'press', button: 'B' }), false);
  // 另外：reducer 只在按下瞬間產生 press，同一個按住的 A 不會連續觸發兩層
  const q = player(R1, 'right');
  q.stream(0, 100, IDLE);
  q.stream(133, 2000, bytesOf('A'));
  assert.deepEqual(q.dispatched.filter(a => a.type === 'press'), [{ type: 'press', button: 'A' }]);
});

test('menu routing: direction, A and B reach the existing modal flow (left/right move between the volume − / + buttons); everything else is swallowed', () => {
  const press = button => C.logicalAction({ type: 'press', button });
  const move = dir => C.logicalAction({ type: 'nav', dir, repeat: false });
  for (const level of ['menu', 'confirm']) for (const dir of ['up', 'down', 'left', 'right']) assert.deepEqual(C.gameMenuCommand(level, move(dir)), { cmd: 'pass' }, `${level} ${dir}`);
  for (const level of ['menu', 'confirm']) {
    assert.deepEqual(C.gameMenuCommand(level, press('A')), { cmd: 'pass' });
    assert.deepEqual(C.gameMenuCommand(level, press('B')), { cmd: 'pass' });
    for (const b of ['X', 'Y', 'R', 'SR', 'SL', 'ZR', 'PLUS', 'CAPTURE', 'STICK', 'HOME']) {
      assert.deepEqual(C.gameMenuCommand(level, press(b)), { cmd: 'none' }, `${level} ${b}`);
    }
  }
  assert.deepEqual(C.gameMenuCommand(null, press('A')), { cmd: 'none' });
});

test('modal scopes: B = 返回遊戲 / 返回遊戲選單, default focus, and the menu outranks server-pushed modals', () => {
  const menu = C.MODAL_SCOPES.find(s => s.id === C.GAME_MENU_MODAL_ID);
  const confirm = C.MODAL_SCOPES.find(s => s.id === C.GAME_MENU_CONFIRM_ID);
  assert.deepEqual(menu.cancel, ['#gameMenuResumeBtn']);
  assert.equal(menu.initial, '#gameMenuResumeBtn');
  assert.deepEqual(confirm.cancel, ['#gameMenuConfirmCancelBtn']);
  assert.equal(confirm.initial, '#gameMenuConfirmOkBtn');
  assert.equal(C.resolveModalScope([C.GAME_MENU_MODAL_ID, C.GAME_MENU_CONFIRM_ID]).id, C.GAME_MENU_CONFIRM_ID);
  for (const other of ['choiceModal', 'peerActionNotice', 'eventRevealModal', 'victoryModal', 'factionPicker', 'cardPreviewModal']) {
    assert.equal(C.resolveModalScope([other, C.GAME_MENU_MODAL_ID]).id, C.GAME_MENU_MODAL_ID, other);
  }
  // 既有危險確認單／SL 聚焦選單的順位不變（它們只能由選單內被吞掉的鍵開啟）
  assert.equal(C.MODAL_SCOPES[0].id, 'lrConfirmModal');
  assert.equal(C.MODAL_SCOPES[1].id, C.FOCUS_MENU_MODAL_ID);
});

test('the browser game-menu code sends no game mutation and only restarts through the confirm layer → /new-game', () => {
  const ui = fs.readFileSync(path.join(ROOT, 'static', 'controller_ui.js'), 'utf8');
  const start = ui.indexOf('// ------------------------------------------------------------ 遊戲選單（遊戲中按住搖桿按鈕 2 秒）');
  const end = ui.indexOf('// ------------------------------------------------------------ dispatch (logical → UI)');
  assert.ok(start > 0 && end > start);
  const section = ui.slice(start, end);
  for (const banned of ['sendAction', 'fetch(', '.send(', 'sendToMap(', 'postMessage', 'WebSocket', 'resolve_pending_choice']) {
    assert.equal(section.includes(banned), false, banned);
  }
  // 長按累積用的就是 Core 的純函式（同一套 reducer／gate／資格）
  for (const call of ['Core.stepStickHold(', 'Core.stepMenuGate(', 'Core.gameMenuBlocker(gameMenuContext())', 'Core.menuGateAllows(', 'Core.gameMenuCommand(']) {
    assert.ok(section.includes(call), call);
  }
  // 重新開始只在確認層執行，且走既有 /new-game 入口；confirmRestart 只綁在確認鈕上。
  const confirmFn = section.slice(section.indexOf('function confirmRestart()'), section.indexOf('function revalidateGameMenu()'));
  assert.ok(confirmFn.includes("if (gameMenuLevel() !== 'confirm') return;"));
  assert.ok(confirmFn.includes("'emergencyNewGameBtn'") && confirmFn.includes("'/new-game'"));
  assert.equal(ui.split('confirmRestart').length - 1, 2, 'defined once + bound once to #gameMenuConfirmOkBtn');
  assert.ok(section.includes("on('gameMenuConfirmOkBtn', confirmRestart);"));
  // Joy-Con 功能表直接重用既有 openJoyconHelp（不複製說明 modal 的邏輯）；導覽列的舊 Joy-Con 說明按鈕已移除。
  assert.ok(section.includes('window.openJoyconHelp'));
  assert.equal(section.includes('HELP_ENTRY_ID'), false);
  // 長按與導覽列按鈕（A／滑鼠）共用同一個 openGameMenu；滑鼠入口不需要 Joy-Con 連線，但仍擋開始流程、交接遮罩與未載入的遊戲。
  assert.ok(ui.includes("case 'openMenu': activated = openGameMenu(); break;"));
  const mouseFn = section.slice(section.indexOf('function openGameMenuByMouse()'), section.indexOf('/** 返回遊戲／B／背景'));
  assert.ok(mouseFn.includes('mouseMenuBlocker') && !mouseFn.includes('connected') && !mouseFn.includes('bridgeConnected'));
  assert.ok(section.includes("$(MENU_ENTRY_ID)?.addEventListener('click'"));
  // ingest 只把長按沒有吃掉的 action 交給 dispatch
  assert.ok(ui.includes('for (const action of trackStickHold(step.actions, now)) dispatch(action);'));
});

test('index.html: the layers exist, the nav button is the game menu (no old help button), the volume control is in the menu, and assets carry a fresh cache tag', () => {
  const html = fs.readFileSync(path.join(ROOT, 'static', 'index.html'), 'utf8');
  for (const id of ['gameMenuModal', 'gameMenuConfirmModal', 'gameMenuResumeBtn', 'gameMenuSettingsBtn', 'gameMenuRestartBtn',
    'gameMenuConfirmCancelBtn', 'gameMenuConfirmOkBtn', 'gameMenuBtn', 'gameMenuVolume', 'gameMenuVolumeDownBtn', 'gameMenuVolumeUpBtn',
    'gameMenuVolumeValue', 'joyconHelpModal']) assert.ok(html.includes(`id="${id}"`), id);
  assert.match(html, /<div id="gameMenuModal"[^>]*aria-hidden="true" style="display:none;">/);
  assert.match(html, /<div id="gameMenuConfirmModal"[^>]*aria-hidden="true" style="display:none;">/);
  assert.ok(html.includes('離開目前遊戲'));
  assert.match(html, /<button id="gameMenuBtn"[^>]*aria-label="遊戲選單"[^>]*aria-controls="gameMenuModal"/);
  assert.ok(!/id="joyconHelpBtn"/.test(html) && !html.includes('openJoyconHelp()"'), 'old help nav button is gone');
  assert.match(html, /id="gameMenuSettingsBtn"[^>]*>Joy-Con 功能表</);
  assert.ok(html.includes('配樂音量'));
  assert.ok(!html.includes('joyconHelpBtn'));
  const tag = 'game-menu-music-flow-20261101';
  for (const f of ['controller_core.js', 'living_room_core.js', 'controller_ui.js', 'controller_living_room.js', 'app.js', 'game_music.js']) {
    assert.ok(html.includes(`/static/${f}?v=${tag}`), f);
  }
  assert.ok(html.includes('/static/style.css?v=joycon-connect-image-20261101'), 'style.css');
  assert.ok(html.includes('/static/start_flow_ui.js?v=joycon-connect-image-20261101'), 'start_flow_ui.js');
  assert.ok(fs.existsSync(path.join(ROOT, 'static', 'audio', 'redline-theme.m4a')));
  assert.ok(!/https?:\/\/[^"']*\.(m4a|mp3|ogg|wav)/i.test(html), 'no remote audio');
});

test('menu row navigation: up/down walk the rows (the − / + volume row is reachable), left/right move inside the volume row only', () => {
  assert.deepEqual(C.GAME_MENU_ROWS.map(r => [...r]), [
    ['gameMenuResumeBtn'], ['gameMenuSettingsBtn'], ['gameMenuVolumeDownBtn', 'gameMenuVolumeUpBtn'], ['gameMenuRestartBtn'],
  ]);
  const walk = (start, dirs) => dirs.reduce((id, dir) => C.gameMenuMove(id, dir), start);
  assert.equal(C.gameMenuMove('gameMenuResumeBtn', 'down'), 'gameMenuSettingsBtn');
  assert.equal(C.gameMenuMove('gameMenuSettingsBtn', 'down'), 'gameMenuVolumeDownBtn', 'entering the volume row lands on −');
  assert.equal(walk('gameMenuSettingsBtn', ['down', 'right']), 'gameMenuVolumeUpBtn');
  assert.equal(walk('gameMenuSettingsBtn', ['down', 'right', 'right']), 'gameMenuVolumeUpBtn', 'no wrap at the right end');
  assert.equal(walk('gameMenuSettingsBtn', ['down', 'left']), 'gameMenuVolumeDownBtn', 'no wrap at the left end');
  assert.equal(walk('gameMenuSettingsBtn', ['down', 'right', 'down']), 'gameMenuRestartBtn');
  assert.equal(walk('gameMenuSettingsBtn', ['down', 'right', 'up']), 'gameMenuSettingsBtn');
  assert.equal(C.gameMenuMove('gameMenuRestartBtn', 'down'), 'gameMenuRestartBtn', 'no wrap at the bottom');
  assert.equal(C.gameMenuMove('gameMenuResumeBtn', 'up'), 'gameMenuResumeBtn', 'no wrap at the top');
  for (const id of ['gameMenuResumeBtn', 'gameMenuSettingsBtn', 'gameMenuRestartBtn']) {
    for (const dir of ['left', 'right']) assert.equal(C.gameMenuMove(id, dir), id, `${id} ${dir}`);
  }
  assert.equal(C.gameMenuMove('somethingElse', 'down'), null);
  assert.equal(C.gameMenuMove(null, 'down'), null);
});

test('the volume buttons are inside the game-menu modal scope (B still returns to the game)', () => {
  const scope = C.MODAL_SCOPES.find(s => s.id === C.GAME_MENU_MODAL_ID);
  assert.deepEqual(scope.cancel, ['#gameMenuResumeBtn']);
  assert.equal(scope.initial, '#gameMenuResumeBtn');
});
