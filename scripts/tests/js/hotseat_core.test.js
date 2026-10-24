// node --test scripts/tests/js/hotseat_core.test.js
// 客廳輪流（hot-seat）：多席位保存、權威行動者、交接遮罩判定、只接受綁定 Joy-Con 的確認。
const test = require('node:test');
const assert = require('node:assert/strict');
const H = require('../../../static/hotseat_core.js');

const G = 'game-1';
const TW = { player_id: 'p-tw', resume_token: 'tok-tw', name: '臺灣玩家' };
const HK = { player_id: 'p-hk', resume_token: 'tok-hk', name: '香港玩家' };
const RED = { player_id: 'p-red', resume_token: 'tok-red', name: '紅軍' };
const L1 = 'L24801-0a1b2c3d';
const R1 = 'R24800-3f2a9c1e';
const A = { type: 'press', button: 'A' };

function storeWith(...seats) {
  let store = H.normalizeStore({ enabled: true });
  for (const seat of seats) store = H.addSeat(store, G, seat).store;
  return store;
}

function state(extra = {}) {
  return {
    game_phase: 'main',
    current_player: '臺灣玩家',
    pending_choice: null,
    winner: null,
    players: [
      { id: 'p-tw', name: '臺灣玩家', faction: 'taiwan_green' },
      { id: 'p-hk', name: '香港玩家', faction: 'hong_kong' },
      { id: 'p-red', name: '紅軍', faction: 'red_army' },
    ],
    ...extra,
  };
}

// ---- 行動代號：Joy-Con 玩家不必輸入文字；本機席位的系統預設代號依 server /lobby players 順序＝P1～P4
const lobbyOf = (...players) => ({ players, host_id: players[0] && players[0][0], factions: {}, ready: {}, started: false });

test('行動代號依 server lobby 順序：第 1～4 席＝P1～P4；沒有 P5；不在 lobby 或資料不合 → null', () => {
  const lobby = lobbyOf(['p-tw', 'host'], ['p-hk', 'host'], ['p-red', 'host'], ['p-4', 'host']);
  assert.deepEqual(['p-tw', 'p-hk', 'p-red', 'p-4'].map(id => H.seatCodename(lobby, id)), ['P1', 'P2', 'P3', 'P4']);
  assert.equal(H.seatCodename(lobbyOf(...Array.from({ length: 5 }, (_, i) => [`p${i}`, 'x'])), 'p4'), null);
  assert.equal(H.seatCodename(lobby, 'p-none'), null);
  assert.equal(H.seatCodename(null, 'p-tw'), null);
  assert.equal(H.seatCodename({ error: 'Game not found' }, 'p-tw'), null);
  assert.deepEqual(H.CODENAMES, ['P1', 'P2', 'P3', 'P4']);
  // 新增本機席位時的暫定代號＝它將加入的位置（server append）；滿 4 席沒有代號
  assert.equal(H.nextSeatCodename(lobbyOf(['p-tw', 'P1'])), 'P2');
  assert.equal(H.nextSeatCodename(lobbyOf(['a', '1'], ['b', '2'], ['c', '3'])), 'P4');
  assert.equal(H.nextSeatCodename(lobbyOf(['a', '1'], ['b', '2'], ['c', '3'], ['d', '4'])), null);
  assert.equal(H.nextSeatCodename(null), null);
  // AI 紅軍：房間最多 3 位真人（server _max_human_players）→ 第四席沒有代號
  assert.equal(H.nextSeatCodename({ ...lobbyOf(['a', '1'], ['b', '2']), ai_red_army: true }), 'P3');
  assert.equal(H.nextSeatCodename({ ...lobbyOf(['a', '1'], ['b', '2'], ['c', '3']), ai_red_army: true }), null);
});

test('orphanSeatId：lobby 有預期代號、本機席位表沒有它 → 回傳該公開 player_id（/join 回應遺失的恢復依據）', () => {
  const store = storeWith(TW);
  const lobby = lobbyOf([TW.player_id, 'P1'], ['orphan-2', 'P2']);
  assert.equal(H.orphanSeatId(lobby, store, G, 'P2'), 'orphan-2');
  assert.equal(H.orphanSeatId(lobby, store, G, 'P3'), null);
  assert.equal(H.orphanSeatId(lobby, store, G, 'P1'), null); // 本機已有的席位不是孤兒
  assert.equal(H.orphanSeatId(null, store, G, 'P2'), null);
  assert.equal(H.orphanSeatId(lobby, store, G, ''), null);
});

test('席位的 auto_name：只有明確 true 才是系統預設代號；未提供時保留原值，不把自訂名稱變成預設', () => {
  let store = storeWith({ ...TW, auto_name: true }, HK);
  const seat = id => H.findSeat(store, G, id);
  assert.equal(seat('p-tw').auto_name, true);
  assert.equal(seat('p-hk').auto_name, false);
  store = H.addSeat(store, G, { ...TW, name: 'P1' }).store; // 更新 token／名稱（例如改名成功後）不改旗標
  assert.equal(seat('p-tw').auto_name, true);
  assert.equal(seat('p-tw').name, 'P1');
  store = H.addSeat(store, G, { ...TW, name: 'Alice', auto_name: false }).store; // 使用者自行輸入 → 自訂
  assert.equal(seat('p-tw').auto_name, false);
  assert.equal(H.normalizeStore({ enabled: true, games: { [G]: { seats: [{ ...HK, auto_name: 'yes' }] } } }).games[G].seats[0].auto_name, false);
});

test('codenameRenames：只改「系統預設代號」的本機席位成它在 server lobby 的位置；自訂名稱保留；已正確不重送', () => {
  const store = storeWith({ ...TW, auto_name: true }, { ...HK, auto_name: true }, { ...RED, name: 'Alice', auto_name: false });
  const lobby = lobbyOf(['p-tw', 'host'], ['p-hk', 'P2'], ['p-red', 'Alice']);
  assert.deepEqual(H.codenameRenames({ lobby, store, gameId: G }), [{ player_id: 'p-tw', resume_token: 'tok-tw', name: 'P1' }]);
  // 遠端玩家佔了 lobby 的位置：本機席位用自己在 server lobby 的位置（穩定，不依本機清單）
  const mixed = lobbyOf(['p-tw', 'host'], ['remote', '遠端'], ['p-hk', 'host']);
  assert.deepEqual(H.codenameRenames({ lobby: mixed, store, gameId: G }).map(r => [r.player_id, r.name]), [['p-tw', 'P1'], ['p-hk', 'P3']]);
  // 自訂名稱（即使字面是 host）永不覆寫
  const typedHost = storeWith({ ...TW, name: 'host', auto_name: false }, { ...HK, auto_name: true });
  assert.deepEqual(H.codenameRenames({ lobby: lobbyOf(['p-tw', 'host'], ['p-hk', 'host']), store: typedHost, gameId: G }).map(r => r.player_id), ['p-hk']);
});

test('codenameRenames 穩定：與目前顯示的席位、本機清單順序、重載無關；同一份 lobby 永遠得到同一組代號', () => {
  const a = storeWith({ ...TW, auto_name: true }, { ...HK, auto_name: true }, { ...RED, auto_name: true });
  const b = storeWith({ ...RED, auto_name: true }, { ...TW, auto_name: true }, { ...HK, auto_name: true }); // 本機清單順序不同
  const lobby = lobbyOf(['p-tw', 'host'], ['p-hk', 'host'], ['p-red', 'host']);
  const names = s => H.codenameRenames({ lobby, store: s, gameId: G }).map(r => [r.player_id, r.name]);
  assert.deepEqual(names(a), [['p-tw', 'P1'], ['p-hk', 'P2'], ['p-red', 'P3']]);
  assert.deepEqual(names(b), names(a));
  assert.deepEqual(H.codenameRenames({ lobby: lobbyOf(['p-tw', 'P1'], ['p-hk', 'P2'], ['p-red', 'P3']), store: a, gameId: G }), []);
});

test('codenameRenames 不介入：未啟用 hot-seat、本機只有一席、已開局、缺／錯 lobby（單席位與一般流程不變）', () => {
  const store = storeWith({ ...TW, auto_name: true }, { ...HK, auto_name: true });
  const lobby = lobbyOf(['p-tw', 'host'], ['p-hk', 'host']);
  assert.deepEqual(H.codenameRenames({ lobby, store: { ...store, enabled: false }, gameId: G }), []);
  assert.deepEqual(H.codenameRenames({ lobby, store: storeWith({ ...TW, auto_name: true }), gameId: G }), []);
  assert.deepEqual(H.codenameRenames({ lobby: { ...lobby, started: true }, store, gameId: G }), []);
  assert.deepEqual(H.codenameRenames({ lobby: null, store, gameId: G }), []);
  assert.deepEqual(H.codenameRenames({ lobby: { error: 'Game not found' }, store, gameId: G }), []);
  assert.deepEqual(H.codenameRenames({ lobby, store, gameId: 'other-game' }), []);
});

test('同一 gameId 的第二席不覆寫第一席；同 player_id 只更新 token／名稱且保留綁定', () => {
  let store = storeWith(TW);
  store = H.bindController(store, G, 'p-tw', L1).store;
  const added = H.addSeat(store, G, HK);
  assert.equal(added.ok, true);
  const seats = H.seatsFor(added.store, G);
  assert.deepEqual(seats.map(s => [s.player_id, s.resume_token, s.controller]), [
    ['p-tw', 'tok-tw', L1], ['p-hk', 'tok-hk', null],
  ]);
  const again = H.addSeat(added.store, G, { ...TW, resume_token: 'tok-tw-2', name: '臺灣' });
  const tw = H.seatsFor(again.store, G).find(s => s.player_id === 'p-tw');
  assert.equal(tw.resume_token, 'tok-tw-2');
  assert.equal(tw.controller, L1);
  assert.equal(H.seatsFor(again.store, G).length, 2);
  assert.equal(H.addSeat(again.store, G, { player_id: '', resume_token: 'x' }).ok, false);
  assert.equal(H.addSeat(again.store, G, { player_id: 'p-x', resume_token: '' }).ok, false);
});

test('storage 損壞或格式不合時 fail closed 為空；未啟用時不是 hot-seat 遊戲', () => {
  assert.deepEqual(H.normalizeStore('garbage'), { v: 1, enabled: false, games: {} });
  assert.deepEqual(H.normalizeStore({ games: { [G]: { seats: [{ player_id: 1 }] } } }).games, {});
  const store = storeWith(TW, HK);
  assert.equal(H.isHotSeatGame(store, G, 'p-tw'), true);
  assert.equal(H.isHotSeatGame(store, G, 'p-other'), false);
  assert.equal(H.isHotSeatGame({ ...store, enabled: false }, G, 'p-tw'), false);
  assert.equal(H.isHotSeatGame(store, 'game-2', 'p-tw'), false);
  // 只有一個本機席位（例如啟用後加入別人的房間）＝一般單席位行為
  assert.equal(H.isHotSeatGame(storeWith(TW), G, 'p-tw'), false);
});

test('一支 Joy-Con 只能綁一個本機席位；不合法 id 拒絕', () => {
  let store = storeWith(TW, HK);
  store = H.bindController(store, G, 'p-tw', L1).store;
  assert.equal(H.bindController(store, G, 'p-hk', L1).ok, false);
  assert.equal(H.bindController(store, G, 'p-hk', L1).reason, 'controller-taken');
  assert.equal(H.bindController(store, G, 'p-hk', 'not-an-id').reason, 'invalid-controller');
  assert.equal(H.bindController(store, G, 'p-none', R1).reason, 'unknown-seat');
  const ok = H.bindController(store, G, 'p-hk', R1);
  assert.equal(ok.ok, true);
  assert.equal(H.seatForController(ok.store, G, R1).player_id, 'p-hk');
  assert.equal(H.seatsFor(H.unbindController(ok.store, G, 'p-hk'), G)[1].controller, null);
});

test('權威行動者：pending_choice 擁有者優先於目前回合玩家；只用 server state', () => {
  assert.deepEqual(H.authoritativeActor(state(), ['p-tw', 'p-hk']), { kind: 'current_player', playerId: 'p-tw', name: '臺灣玩家', faction: 'taiwan_green' });
  const choice = state({ current_player: '臺灣玩家', pending_choice: { player_id: 'p-hk', choice_id: 'c1' } });
  assert.equal(H.authoritativeActor(choice, ['p-tw', 'p-hk']).playerId, 'p-hk');
  assert.equal(H.authoritativeActor(choice, ['p-tw', 'p-hk']).kind, 'pending_choice');
  assert.equal(H.authoritativeActor(state({ winner: '香港玩家' }), []).kind, 'finished');
  assert.equal(H.authoritativeActor(state({ game_phase: 'finished' }), []).kind, 'finished');
  assert.equal(H.authoritativeActor({ error: 'Game not ready' }, []).kind, 'none');
  assert.equal(H.authoritativeActor(state({ current_player: '不存在' }), []).kind, 'none');
  // 選基地：伺服器 pending_base_choices 的本機席位優先
  const base = state({ game_phase: 'base_selection', pending_base_choices: { 'p-red': {}, 'p-hk': {} } });
  assert.equal(H.authoritativeActor(base, ['p-tw', 'p-hk']).playerId, 'p-hk');
  assert.equal(H.authoritativeActor(base, ['p-tw']).playerId, 'p-red');
});

test('香港抗暴之戰免費遷移根據地：只認伺服器 hk_base_relocation_player_id，且旗標須同時開啟', () => {
  const local = ['p-tw', 'p-hk'];
  // 窗口開啟時 current_player 仍是整輪最後一席；由伺服器明確給出的香港 player_id 決定
  const open = state({ current_player: '臺灣玩家', hk_free_base_relocation: true, hk_base_relocation_player_id: 'p-hk' });
  assert.deepEqual(H.authoritativeActor(open, local), { kind: 'hk_base_relocation', playerId: 'p-hk', name: '香港玩家', faction: 'hong_kong' });
  // 真正待決的 pending_choice 仍優先
  assert.equal(H.authoritativeActor({ ...open, pending_choice: { player_id: 'p-tw' } }, local).playerId, 'p-tw');
  // 旗標關閉時忽略殘留 id → 回到 current_player
  const stale = state({ hk_free_base_relocation: false, hk_base_relocation_player_id: 'p-hk' });
  assert.equal(H.authoritativeActor(stale, local).kind, 'current_player');
  assert.equal(H.authoritativeActor(stale, local).playerId, 'p-tw');
  // 旗標開啟但缺少（或不存在的）香港玩家 → fail closed，不落回 current_player
  assert.equal(H.authoritativeActor(state({ hk_free_base_relocation: true, hk_base_relocation_player_id: null }), local).kind, 'none');
  assert.equal(H.authoritativeActor(state({ hk_free_base_relocation: true }), local).kind, 'none');
  assert.equal(H.authoritativeActor(state({ hk_free_base_relocation: true, hk_base_relocation_player_id: 'p-gone' }), local).kind, 'none');
  // 不靠陣營名稱猜：沒有伺服器 id 時即使有 hong_kong 陣營玩家也不交給他
  assert.notEqual(H.authoritativeActor(state({ hk_free_base_relocation: true }), local).playerId, 'p-hk');
});

test('香港遷移窗口：交給本機香港席位，確認後 reconnect → open；非本機或缺香港玩家 → waiting', () => {
  let store = storeWith(TW, HK);
  store = H.bindController(store, G, 'p-tw', L1).store;
  store = H.bindController(store, G, 'p-hk', R1).store;
  const hkWindow = state({ hk_free_base_relocation: true, hk_base_relocation_player_id: 'p-hk' });
  const twSession = { gameId: G, active: 'p-tw', unlocked: true };
  const v = H.decide({ state: hkWindow, connectedSeatId: 'p-tw', session: twSession, store, gameId: G });
  assert.equal(v.view, 'handoff');
  assert.equal(v.actor.kind, 'hk_base_relocation');
  assert.equal(v.seat.player_id, 'p-hk');
  assert.equal(H.handoffTitle(v.actor, '香港'), '請交給〈香港玩家／香港〉');
  assert.equal(H.allowsInput(v, R1), false);
  assert.equal(H.confirmVerdict({ verdict: v, owned: L1, action: A }).reason, 'wrong-controller');
  assert.equal(H.confirmVerdict({ verdict: v, owned: R1, action: A }).ok, true);
  const hkSession = H.confirmSession(G, 'p-hk');
  assert.equal(H.decide({ state: hkWindow, connectedSeatId: 'p-tw', session: hkSession, store, gameId: G }).view, 'reconnect');
  const opened = H.decide({ state: hkWindow, connectedSeatId: 'p-hk', session: hkSession, store, gameId: G });
  assert.equal(opened.view, 'open');
  assert.equal(H.allowsInput(opened, R1), true);
  assert.equal(H.allowsInput(opened, L1), false);
  // 香港決定後窗口關閉、殘留 id 被忽略：依新 state 交給下一位
  const after = H.decide({ state: state({ hk_free_base_relocation: false, hk_base_relocation_player_id: 'p-hk' }), connectedSeatId: 'p-hk', session: hkSession, store, gameId: G });
  assert.equal(after.view, 'handoff');
  assert.equal(after.seat.player_id, 'p-tw');
  // 香港不是本機席位 → waiting，不顯示任何席位
  const remote = H.decide({ state: hkWindow, connectedSeatId: 'p-tw', session: twSession, store: storeWith(TW, RED), gameId: G });
  assert.equal(remote.view, 'waiting');
  assert.equal(remote.seat, null);
  // 旗標開啟但沒有香港玩家 id → waiting（fail closed）
  const missing = H.decide({ state: state({ hk_free_base_relocation: true, hk_base_relocation_player_id: null }), connectedSeatId: 'p-tw', session: twSession, store, gameId: G });
  assert.equal(missing.view, 'waiting');
});

test('臺灣結束行動 → 權威轉到香港：遮罩交接給香港，不會依舊顯示臺灣畫面', () => {
  const store = storeWith(TW, HK);
  const session = { gameId: G, active: 'p-tw', unlocked: true };
  const open = H.decide({ state: state(), connectedSeatId: 'p-tw', session, store, gameId: G });
  assert.equal(open.view, 'open');
  const next = H.decide({ state: state({ current_player: '香港玩家' }), connectedSeatId: 'p-tw', session, store, gameId: G });
  assert.equal(next.view, 'handoff');
  assert.equal(next.seat.player_id, 'p-hk');
  assert.equal(next.needsBinding, true);
  assert.equal(H.handoffTitle(next.actor, '香港'), '請交給〈香港玩家／香港〉');
  // 一旦交接開始就鎖住：即使權威又回到臺灣，也要重新以臺灣 Joy-Con 確認
  const locked = H.lockSession(session, next);
  assert.equal(locked.unlocked, false);
  assert.equal(H.lockSession(H.confirmSession(G, 'p-hk'), { view: 'reconnect' }).unlocked, true);
  const back = H.decide({ state: state(), connectedSeatId: 'p-tw', session: locked, store, gameId: G });
  assert.equal(back.view, 'handoff');
  assert.equal(back.seat.player_id, 'p-tw');
});

test('已確認的席位但連線仍是別人的 viewer → 不解除遮罩（必須以該席位 token 重新連線）', () => {
  const store = storeWith(TW, HK);
  const session = { gameId: G, active: 'p-hk', unlocked: true };
  const v = H.decide({ state: state({ current_player: '香港玩家' }), connectedSeatId: 'p-tw', session, store, gameId: G });
  assert.equal(v.view, 'reconnect');
  assert.equal(v.seat.player_id, 'p-hk');
  const ok = H.decide({ state: state({ current_player: '香港玩家' }), connectedSeatId: 'p-hk', session, store, gameId: G });
  assert.equal(ok.view, 'open');
});

test('非本回合玩家的 pending_choice 交接給 choice owner，解決後依新 state 交回', () => {
  const store = storeWith(TW, HK);
  const session = { gameId: G, active: 'p-tw', unlocked: true };
  const choice = H.decide({ state: state({ pending_choice: { player_id: 'p-hk' } }), connectedSeatId: 'p-tw', session, store, gameId: G });
  assert.equal(choice.view, 'handoff');
  assert.equal(choice.actor.kind, 'pending_choice');
  assert.equal(choice.seat.player_id, 'p-hk');
  const hkSession = H.confirmSession(G, 'p-hk');
  assert.equal(H.decide({ state: state({ pending_choice: { player_id: 'p-hk' } }), connectedSeatId: 'p-hk', session: hkSession, store, gameId: G }).view, 'open');
  const resolved = H.decide({ state: state(), connectedSeatId: 'p-hk', session: hkSession, store, gameId: G });
  assert.equal(resolved.view, 'handoff');
  assert.equal(resolved.seat.player_id, 'p-tw');
});

test('行動者不是本機席位（遠端玩家／AI 紅軍）或沒有權威狀態 → 等待遮罩，不顯示任何席位私密畫面', () => {
  const store = storeWith(TW, HK);
  const session = { gameId: G, active: 'p-tw', unlocked: true };
  assert.equal(H.decide({ state: state({ current_player: '紅軍' }), connectedSeatId: 'p-tw', session, store, gameId: G }).view, 'waiting');
  assert.equal(H.decide({ state: { error: 'x' }, connectedSeatId: 'p-tw', session, store, gameId: G }).view, 'waiting');
  assert.equal(H.decide({ state: state({ winner: '香港玩家' }), connectedSeatId: 'p-tw', session, store, gameId: G }).view, 'open');
  assert.equal(H.masked('waiting') && H.masked('handoff') && H.masked('reconnect') && H.masked('loading'), true);
  assert.equal(H.masked('open') || H.masked('inactive'), false);
});

test('非 hot-seat 遊戲（單席位）維持原行為：inactive，不遮罩', () => {
  const store = storeWith(TW);
  const v = H.decide({ state: state({ current_player: '香港玩家' }), connectedSeatId: 'p-solo', session: null, store, gameId: G });
  assert.equal(v.view, 'inactive');
});

test('只有綁定給該席位、且目前由本分頁擁有的 Joy-Con 按 A 才能確認', () => {
  let store = storeWith(TW, HK);
  store = H.bindController(store, G, 'p-tw', L1).store;
  store = H.bindController(store, G, 'p-hk', R1).store;
  const session = { gameId: G, active: 'p-tw', unlocked: false };
  const v = H.decide({ state: state({ current_player: '香港玩家' }), connectedSeatId: 'p-tw', session, store, gameId: G });
  assert.equal(v.needsBinding, false);
  assert.deepEqual(H.confirmVerdict({ verdict: v, owned: R1, action: A }), { ok: true, reason: null });
  assert.equal(H.confirmVerdict({ verdict: v, owned: L1, action: A }).reason, 'wrong-controller');
  assert.equal(H.confirmVerdict({ verdict: v, owned: null, action: A }).reason, 'wrong-controller');
  assert.equal(H.confirmVerdict({ verdict: v, owned: R1, action: { type: 'press', button: 'B' } }).reason, 'not-confirm');
  assert.equal(H.confirmVerdict({ verdict: v, owned: R1, action: { type: 'nav', dir: 'up' } }).reason, 'not-confirm');
  const unbound = H.decide({ state: state({ current_player: '香港玩家' }), connectedSeatId: 'p-tw', session, store: H.unbindController(store, G, 'p-hk'), gameId: G });
  assert.equal(H.confirmVerdict({ verdict: unbound, owned: R1, action: A }).reason, 'unbound');
  const waiting = H.decide({ state: state({ current_player: '紅軍' }), connectedSeatId: 'p-tw', session, store, gameId: G });
  assert.equal(H.confirmVerdict({ verdict: waiting, owned: R1, action: A }).reason, 'not-handoff');
});

test('開啟狀態下，非該席位綁定的 Joy-Con 輸入一律攔下', () => {
  let store = storeWith(TW, HK);
  store = H.bindController(store, G, 'p-tw', L1).store;
  const v = H.decide({ state: state(), connectedSeatId: 'p-tw', session: H.confirmSession(G, 'p-tw'), store, gameId: G });
  assert.equal(v.view, 'open');
  assert.equal(H.allowsInput(v, L1), true);
  assert.equal(H.allowsInput(v, R1), false);
  assert.equal(H.allowsInput(v, null), false);
  assert.equal(H.allowsInput({ view: 'inactive' }, R1), true);
  assert.equal(H.allowsInput({ view: 'handoff', seat: { controller: R1 } }, R1), false);
});

// ---------------------------------------------------------------- 大廳：先綁定 Joy-Con，再由各自 Joy-Con 進入自己的選擇
const R2 = 'R24801-aaaabbbb';
const NAV = { type: 'nav', dir: 'down', repeat: false };

function lobby(extra = {}) {
  return {
    players: [['p-tw', '臺灣玩家'], ['p-hk', '香港玩家'], ['p-remote', '遠端玩家']],
    host_id: 'p-tw', factions: {}, bases: {}, ready: {}, started: false,
    ...extra,
  };
}

function boundStore() {
  let store = storeWith(TW, HK);
  store = H.bindController(store, G, 'p-tw', L1).store;
  return H.bindController(store, G, 'p-hk', R1).store;
}

test('大廳席位列：只列本機席位，名稱／陣營／根據地／準備／Joy-Con 都來自 server lobby 與席位綁定', () => {
  const lob = lobby({ factions: { 'p-tw': 'taiwan_green', 'p-remote': 'red_army' }, bases: { 'p-tw': '臺北' }, ready: { 'p-tw': true } });
  const rows = H.lobbySeats({ lobby: lob, store: boundStore(), gameId: G, connectedSeatId: 'p-tw' });
  assert.deepEqual(rows.map(r => [r.player_id, r.name, r.faction, r.base, r.ready, r.controller, r.connected, r.inLobby]), [
    ['p-tw', '臺灣玩家', 'taiwan_green', '臺北', true, L1, true, true],
    ['p-hk', '香港玩家', null, null, false, R1, false, true],
  ]);
  // 本機席位不在 server lobby（例如被移除）仍列出但標示 inLobby=false，不會成為行動者
  const gone = H.lobbySeats({ lobby: lobby({ players: [['p-tw', '臺灣玩家']] }), store: boundStore(), gameId: G, connectedSeatId: 'p-tw' });
  assert.deepEqual(gone.map(r => [r.player_id, r.inLobby]), [['p-tw', true], ['p-hk', false]]);
});

test('大廳兩席兩 controller：主連線只 claim 目前席位那一支；其他已綁定席位各自有自己 controller 的監聽', () => {
  const store = boundStore();
  for (const lob of [lobby(), lobby({ factions: { 'p-tw': 'taiwan_green' } }), lobby({ factions: { 'p-tw': 'taiwan_green' }, ready: { 'p-tw': true } })]) {
    // 目前席位永遠是自己的行動者（完成與否都不會把畫面交給別席）
    const v = H.decideLobby({ lobby: lob, store, gameId: G, connectedSeatId: 'p-tw' });
    assert.equal(v.view, 'lobby-open');
    assert.equal(v.seat.player_id, 'p-tw');
    assert.equal(H.claimTarget(v), L1);
    assert.deepEqual(H.lobbyListeners({ verdict: v, store, gameId: G }), [{ controller: R1, player_id: 'p-hk' }]);
  }
  assert.equal(H.decideLobby({ lobby: lobby(), store, gameId: G, connectedSeatId: 'p-tw' }).actor.kind, 'lobby_select');
  assert.equal(H.decideLobby({ lobby: lobby({ factions: { 'p-tw': 'x' } }), store, gameId: G, connectedSeatId: 'p-tw' }).actor.kind, 'lobby_ready');
  // 從香港席位看：監聽的是臺灣那一支
  const hkView = H.decideLobby({ lobby: lobby(), store, gameId: G, connectedSeatId: 'p-hk' });
  assert.equal(H.claimTarget(hkView), R1);
  assert.deepEqual(H.lobbyListeners({ verdict: hkView, store, gameId: G }), [{ controller: L1, player_id: 'p-tw' }]);
  const v = H.decideLobby({ lobby: lobby(), store, gameId: G, connectedSeatId: 'p-tw' });
  assert.deepEqual(H.lobbyInput({ verdict: v, owned: L1, action: NAV, store, gameId: G }), { pass: true, switchTo: null, reason: null });
});

test('大廳任一已綁定席位按自己 Joy-Con 的 A → 切到自己的席位（不論輪次、完成與否）；其他鍵不穿透到目前席位', () => {
  const store = boundStore();
  const all = lobby({ factions: { 'p-tw': 'taiwan_green', 'p-hk': 'hong_kong' }, ready: { 'p-tw': true, 'p-hk': true } });
  for (const lob of [lobby(), all]) {
    const v = H.decideLobby({ lobby: lob, store, gameId: G, connectedSeatId: 'p-tw' });
    // 監聽連線收到香港 R1 的 A（只看該 controller 的 reducer actions）
    const t = H.listenerSwitchTarget({ verdict: v, store, gameId: G, controller: R1, actions: [NAV, A] });
    assert.equal(t.player_id, 'p-hk');
    assert.equal(t.resume_token, 'tok-hk');
    // 主連線若擁有香港的 R1（例如手動選了它）：A 一樣切到香港
    const ok = H.lobbyInput({ verdict: v, owned: R1, action: A, store, gameId: G });
    assert.equal(ok.pass, false);
    assert.equal(ok.switchTo.player_id, 'p-hk');
    // 香港 R1 的其他鍵不能操作臺灣席位的大廳
    assert.deepEqual(H.lobbyInput({ verdict: v, owned: R1, action: NAV, store, gameId: G }), { pass: false, switchTo: null, reason: null });
    assert.deepEqual(H.lobbyInput({ verdict: v, owned: R1, action: { type: 'press', button: 'B' }, store, gameId: G }), { pass: false, switchTo: null, reason: null });
    assert.equal(H.listenerSwitchTarget({ verdict: v, store, gameId: G, controller: R1, actions: [NAV, { type: 'press', button: 'B' }] }), null);
  }
  // 反方向：以香港連線時，臺灣的 L1 按 A 切到臺灣
  const hkView = H.decideLobby({ lobby: all, store, gameId: G, connectedSeatId: 'p-hk' });
  assert.equal(H.listenerSwitchTarget({ verdict: hkView, store, gameId: G, controller: L1, actions: [A] }).player_id, 'p-tw');
  // 目前席位自己的 Joy-Con 不會「切換」到自己
  const v = H.decideLobby({ lobby: lobby(), store, gameId: G, connectedSeatId: 'p-tw' });
  assert.equal(H.listenerSwitchTarget({ verdict: v, store, gameId: G, controller: L1, actions: [A] }), null);
  assert.equal(H.lobbyInput({ verdict: v, owned: L1, action: A, store, gameId: G }).switchTo, null);
  assert.deepEqual(H.lobbyInput({ verdict: v, owned: null, action: A, store, gameId: G }), { pass: false, switchTo: null, reason: 'wrong-controller' });
});

test('目前席位尚未選陣營：自己的 Joy-Con 按 A＝開啟自己的選擇視窗（點既有按鈕）；其他情況照既有 routing', () => {
  const store = boundStore();
  const v = H.decideLobby({ lobby: lobby(), store, gameId: G, connectedSeatId: 'p-tw' });
  assert.equal(H.lobbyEntersSelection({ verdict: v, owned: L1, action: A, pickerOpen: false }), true);
  // 視窗已開（A 交給視窗內焦點）、不是 A、不是自己的 Joy-Con、已選陣營、或是要切換的別席 → false
  assert.equal(H.lobbyEntersSelection({ verdict: v, owned: L1, action: A, pickerOpen: true }), false);
  assert.equal(H.lobbyEntersSelection({ verdict: v, owned: L1, action: NAV, pickerOpen: false }), false);
  assert.equal(H.lobbyEntersSelection({ verdict: v, owned: R1, action: A, pickerOpen: false }), false);
  const chose = H.decideLobby({ lobby: lobby({ factions: { 'p-tw': 'taiwan_green' } }), store, gameId: G, connectedSeatId: 'p-tw' });
  assert.equal(H.lobbyEntersSelection({ verdict: chose, owned: L1, action: A, pickerOpen: false }), false);
  // 香港的 R1 不能替臺灣開啟臺灣的選擇視窗
  assert.equal(H.lobbyEntersSelection({ verdict: v, owned: R1, action: A, pickerOpen: false }), false);
  assert.equal(H.lobbyEntersSelection({ verdict: { view: 'inactive' }, owned: R1, action: A, pickerOpen: false }), false);
});

test('大廳未綁定 Joy-Con fail closed：沒有監聽、不能切換、不能代替目前席位操作', () => {
  let store = storeWith(TW, HK);
  store = H.bindController(store, G, 'p-tw', L1).store; // 香港尚未綁定
  const v = H.decideLobby({ lobby: lobby(), store, gameId: G, connectedSeatId: 'p-tw' });
  assert.equal(v.view, 'lobby-open');
  assert.deepEqual(H.lobbyListeners({ verdict: v, store, gameId: G }), []);
  // 未綁定任何席位的 R1：主連線擁有它時，A／方向都攔下，也不切到香港
  assert.deepEqual(H.lobbyInput({ verdict: v, owned: R1, action: A, store, gameId: G }), { pass: false, switchTo: null, reason: 'controller-unbound' });
  assert.deepEqual(H.lobbyInput({ verdict: v, owned: R1, action: NAV, store, gameId: G }), { pass: false, switchTo: null, reason: null });
  assert.equal(H.listenerSwitchTarget({ verdict: v, store, gameId: G, controller: R1, actions: [A] }), null);
  assert.equal(H.listenerSwitchTarget({ verdict: v, store, gameId: G, controller: 'garbage', actions: [A] }), null);
  // 目前席位自己未綁定：lobby-bind，主連線不 claim；任何未綁定 Joy-Con 都不能代替它操作
  const self = H.decideLobby({ lobby: lobby(), store: H.unbindController(store, G, 'p-tw'), gameId: G, connectedSeatId: 'p-tw' });
  assert.equal(self.view, 'lobby-bind');
  assert.equal(H.claimTarget(self), null);
  assert.equal(H.lobbyInput({ verdict: self, owned: L1, action: NAV, store: H.unbindController(store, G, 'p-tw'), gameId: G }).pass, false);
  // 但已綁定的其他席位仍可用自己的 Joy-Con 進入自己的席位
  const hkBound = H.bindController(H.unbindController(store, G, 'p-tw'), G, 'p-hk', R1).store;
  const selfHk = H.decideLobby({ lobby: lobby(), store: hkBound, gameId: G, connectedSeatId: 'p-tw' });
  assert.equal(selfHk.view, 'lobby-bind');
  assert.deepEqual(H.lobbyListeners({ verdict: selfHk, store: hkBound, gameId: G }), [{ controller: R1, player_id: 'p-hk' }]);
  assert.equal(H.listenerSwitchTarget({ verdict: selfHk, store: hkBound, gameId: G, controller: R1, actions: [A] }).player_id, 'p-hk');
});

test('監聽只屬於本機、在 server lobby 內、已綁定的其他席位；不在 lobby 的席位不切換', () => {
  const store = boundStore();
  const gone = lobby({ players: [['p-tw', '臺灣玩家']] });
  const v = H.decideLobby({ lobby: gone, store, gameId: G, connectedSeatId: 'p-tw' });
  assert.deepEqual(H.lobbyListeners({ verdict: v, store, gameId: G }), []);
  assert.equal(H.listenerSwitchTarget({ verdict: v, store, gameId: G, controller: R1, actions: [A] }), null);
  assert.equal(H.lobbyInput({ verdict: v, owned: R1, action: A, store, gameId: G }).switchTo, null);
});

test('大廳不介入：未啟用、單席位、目前連線不是本機席位、已開局；缺 lobby 狀態 fail closed', () => {
  const store = boundStore();
  for (const args of [
    { lobby: lobby(), store: { ...store, enabled: false }, connectedSeatId: 'p-tw' },
    { lobby: lobby(), store: storeWith(TW), connectedSeatId: 'p-tw' },
    { lobby: lobby(), store, connectedSeatId: 'p-remote' },
    { lobby: lobby({ started: true }), store, connectedSeatId: 'p-tw' },
  ]) {
    const v = H.decideLobby({ ...args, gameId: G });
    assert.equal(v.view, 'inactive');
    assert.deepEqual(H.lobbyInput({ verdict: v, owned: R1, action: A, store, gameId: G }), { pass: true, switchTo: null, reason: null });
    assert.equal(H.claimTarget(v), null);
    assert.deepEqual(H.lobbyListeners({ verdict: v, store, gameId: G }), []);
    assert.equal(H.listenerSwitchTarget({ verdict: v, store, gameId: G, controller: R1, actions: [A] }), null);
  }
  for (const missing of [null, { error: 'Game not found' }, lobby({ players: [['p-hk', '香港玩家']] })]) {
    const v = H.decideLobby({ lobby: missing, store, gameId: G, connectedSeatId: 'p-tw' });
    assert.equal(v.view, 'lobby-waiting');
    assert.equal(H.claimTarget(v), null);
    assert.equal(H.lobbyInput({ verdict: v, owned: R1, action: A, store, gameId: G }).pass, false);
    assert.equal(H.lobbyInput({ verdict: v, owned: R1, action: A, store, gameId: G }).switchTo, null);
    assert.deepEqual(H.lobbyListeners({ verdict: v, store, gameId: G }), []);
  }
});

test('重複綁定拒絕；改綁（rebind）釋出原手把；解除後可給另一席，結果明確', () => {
  let store = boundStore();
  // 同一支不能同時綁兩席：拒絕且 store 不變
  const dup = H.bindController(store, G, 'p-hk', L1);
  assert.deepEqual([dup.ok, dup.reason], [false, 'controller-taken']);
  assert.deepEqual(H.seatsFor(dup.store, G).map(s => s.controller), [L1, R1]);
  // 臺灣改綁 R2：L1 釋出，香港改綁 L1 → 各自唯一
  store = H.bindController(store, G, 'p-tw', R2).store;
  assert.equal(H.seatForController(store, G, L1), null);
  store = H.bindController(store, G, 'p-hk', L1).store;
  assert.deepEqual(H.seatsFor(store, G).map(s => [s.player_id, s.controller]), [['p-tw', R2], ['p-hk', L1]]);
  assert.equal(H.seatForController(store, G, R1), null);
  // 重複綁同一支給同一席是冪等
  assert.equal(H.bindController(store, G, 'p-hk', L1).ok, true);
  // 解除綁定
  store = H.unbindController(store, G, 'p-hk');
  assert.equal(H.seatForController(store, G, L1), null);
  assert.deepEqual(H.seatsFor(store, G).map(s => s.controller), [R2, null]);
});

test('大廳手把下拉：列出 bridge 手把與目前綁定；已綁給其他席位／其他分頁使用中／沒有訊號的不可選並註明原因', () => {
  let store = storeWith(TW, HK);
  store = H.bindController(store, G, 'p-tw', L1).store;
  store = H.bindController(store, G, 'p-hk', 'R24803-99998888').store; // 綁定的手把目前不在 bridge 清單
  const roster = [
    { id: L1, side: 'left', status: 'active', owner: 'you' },
    { id: R1, side: 'right', status: 'active', owner: null },
    { id: R2, side: 'right', status: 'active', owner: 'other' },
    { id: 'L24802-33334444', side: 'left', status: 'stale', owner: null },
  ];
  const opts = H.controllerChoices(store, G, 'p-hk', roster);
  assert.deepEqual(opts.map(o => [o.id, o.selected, o.disabled, o.reason, o.takenBy]), [
    [L1, false, true, 'taken', 'p-tw'],
    [R1, false, false, null, null],
    [R2, false, true, 'other-tab', null],
    ['L24802-33334444', false, true, 'stale', null],
    ['R24803-99998888', true, false, 'missing', null],
  ]);
  // 左右同為右手、不同埠：依 bridge identity 分開，不退化成 side
  let same = storeWith(TW, HK);
  same = H.bindController(same, G, 'p-tw', R1).store;
  same = H.bindController(same, G, 'p-hk', R2).store;
  assert.deepEqual([H.seatForController(same, G, R1).player_id, H.seatForController(same, G, R2).player_id], ['p-tw', 'p-hk']);
});

test('席位 Joy-Con 狀態：unbound／active／stale／missing／other-tab；stale 或暫時離線不清除綁定', () => {
  const store = boundStore();
  const [tw, hk] = H.seatsFor(store, G);
  const roster = [{ id: L1, side: 'left', status: 'stale', owner: null }];
  assert.equal(H.seatControllerStatus(tw, roster), 'stale');
  assert.equal(H.seatControllerStatus(hk, roster), 'missing');
  assert.equal(H.seatControllerStatus(hk, [{ id: R1, side: 'right', status: 'active', owner: 'other' }]), 'other-tab');
  assert.equal(H.seatControllerStatus(hk, [{ id: R1, side: 'right', status: 'active', owner: 'you' }]), 'active');
  assert.equal(H.seatControllerStatus({ ...hk, controller: null }, roster), 'unbound');
  assert.equal(H.seatControllerStatus(hk, null), 'missing');
  // 綁定在 reload（storage round-trip）後完全相同；暫時離線時行動者仍是該席（等它恢復，不改綁別支）
  const reloaded = H.normalizeStore(JSON.parse(JSON.stringify(store)));
  assert.deepEqual(H.seatsFor(reloaded, G), H.seatsFor(store, G));
  const v = H.decideLobby({ lobby: lobby(), store: reloaded, gameId: G, connectedSeatId: 'p-tw' });
  assert.equal(H.claimTarget(v), L1);
  assert.deepEqual(H.lobbyListeners({ verdict: v, store: reloaded, gameId: G }), [{ controller: R1, player_id: 'p-hk' }]);
  // storage 被竄改成同一支綁兩席：第二席的綁定作廢，不會讓一支手把代表兩席
  const tampered = H.normalizeStore({ enabled: true, games: { [G]: { seats: [{ ...TW, controller: R1 }, { ...HK, controller: R1 }] } } });
  assert.deepEqual(H.seatsFor(tampered, G).map(s => s.controller), [R1, null]);
});

test('本分頁監聽連線持有的手把不算「其他分頁使用中」：狀態仍是連線正常（active）／訊號中斷（stale）', () => {
  const store = boundStore();
  const hk = H.seatsFor(store, G)[1];
  // 主連線看到的 roster：R1 由另一條連線（本分頁的監聽）擁有 → owner 'other'
  const roster = [
    { id: L1, side: 'left', status: 'active', owner: 'you' },
    { id: R1, side: 'right', status: 'stale', owner: 'other' },
    { id: R2, side: 'right', status: 'active', owner: 'other' },
  ];
  const local = H.withLocalOwners(roster, [R1]);
  assert.equal(H.seatControllerStatus(hk, local), 'stale');
  assert.equal(H.seatControllerStatus(hk, H.withLocalOwners(roster.map(c => ({ ...c, status: 'active' })), [R1])), 'active');
  // 真的是其他分頁的 R2 仍標示 other-tab；不在清單的 id 不新增
  assert.deepEqual(local.map(c => [c.id, c.owner]), [[L1, 'you'], [R1, 'you'], [R2, 'other']]);
  const choices = H.controllerChoices(store, G, 'p-hk', H.withLocalOwners(roster, [R1]));
  assert.deepEqual(choices.find(c => c.id === R1).reason, 'stale');
  assert.equal(choices.find(c => c.id === R2).reason, 'other-tab');
  // 不修改輸入
  assert.equal(roster[1].owner, 'other');
  assert.deepEqual(H.withLocalOwners(null, [R1]), null);
});

test('大廳切換的 session 不解鎖遊戲：開局後第一位行動者仍要交接確認', () => {
  const s = H.switchSession(G, 'p-hk');
  assert.deepEqual(H.normalizeSession(s, G), { gameId: G, active: 'p-hk', unlocked: false });
  const v = H.decide({ state: state({ current_player: '香港玩家' }), connectedSeatId: 'p-hk', session: s, store: boundStore(), gameId: G });
  assert.equal(v.view, 'handoff');
  assert.equal(v.seat.player_id, 'p-hk');
});

test('大廳提示文字：誰、用哪一支、按 A 做什麼', () => {
  const store = boundStore();
  const done = lobby({ factions: { 'p-tw': 'taiwan_green' }, ready: { 'p-tw': true } });
  const label = H.controllerNames([]);
  assert.equal(H.lobbyPrompt(H.decideLobby({ lobby: lobby(), store, gameId: G, connectedSeatId: 'p-tw' }), label),
    '〈臺灣玩家〉正在操作（左 Joy-Con）：選擇陣營與根據地。其他本機玩家按自己 Joy-Con 的 A 進入自己的席位');
  assert.equal(H.lobbyPrompt(H.decideLobby({ lobby: done, store, gameId: G, connectedSeatId: 'p-tw' }), label),
    '〈臺灣玩家〉正在操作（左 Joy-Con）：已完成，所有玩家準備後可啟動行動。其他本機玩家按自己 Joy-Con 的 A 進入自己的席位');
  // 非房主完成後
  assert.equal(H.lobbyPrompt(H.decideLobby({ lobby: lobby({ factions: { 'p-hk': 'hong_kong' }, ready: { 'p-hk': true } }), store, gameId: G, connectedSeatId: 'p-hk' }), label),
    '〈香港玩家〉正在操作（右 Joy-Con）：已完成，等待房主啟動。其他本機玩家按自己 Joy-Con 的 A 進入自己的席位');
  // 沒有給名稱函式時也不洩漏內部 id
  assert.equal(H.lobbyPrompt(H.decideLobby({ lobby: lobby(), store, gameId: G, connectedSeatId: 'p-tw' })),
    '〈臺灣玩家〉正在操作（左 Joy-Con）：選擇陣營與根據地。其他本機玩家按自己 Joy-Con 的 A 進入自己的席位');
  const unbound = H.unbindController(store, G, 'p-tw');
  assert.equal(H.lobbyPrompt(H.decideLobby({ lobby: lobby(), store: unbound, gameId: G, connectedSeatId: 'p-tw' }), label),
    '請先替〈臺灣玩家〉綁定一支 Joy-Con，才能用 Joy-Con 操作自己的席位。其他本機玩家按自己 Joy-Con 的 A 進入自己的席位');
  assert.equal(H.lobbyPrompt({ view: 'inactive' }, label), '');
});

test('可綁定手把清單：排除其他本機席位已綁、其他分頁使用中、沒有訊號者', () => {
  let store = storeWith(TW, HK);
  store = H.bindController(store, G, 'p-tw', L1).store;
  const roster = [
    { id: L1, side: 'left', status: 'active', owner: 'you' },
    { id: R1, side: 'right', status: 'active', owner: null },
    { id: 'R24802-11112222', side: 'right', status: 'active', owner: 'other' },
    { id: 'L24803-33334444', side: 'left', status: 'stale', owner: null },
  ];
  assert.deepEqual(H.bindableControllers(store, G, 'p-hk', roster).map(c => c.id), [R1]);
  assert.deepEqual(H.bindableControllers(store, G, 'p-tw', roster).map(c => c.id), [L1, R1]);
  assert.equal(H.bindingLost(H.seatsFor(store, G)[0], roster), false);
  assert.equal(H.bindingLost(H.seatsFor(store, G)[0], roster.slice(1)), true);
});

// ---------------------------------------------------------------- 玩家看到的手把名稱與狀態（不含 UDP 埠、名稱指紋或內部 id）
// 任何玩家可見文字都不能出現埠號（4–5 位數）、8 位 hex 指紋、legacy 或完整 id。
const LEAK = /\d{3,}|[0-9a-f]{8}|legacy|[LR]\d/;

test('手把顯示名稱：每側只有一支＝左／右 Joy-Con；同側多支依埠號排序給本機序號；不含埠、指紋或 id', () => {
  assert.deepEqual(H.controllerDisplayNames([L1, R1]), { [L1]: '左 Joy-Con', [R1]: '右 Joy-Con' });
  // 同側兩支：依埠號（數值）排序，與輸入順序無關；重複與不合法 id 忽略
  const R9 = 'R9-01234567';
  const names = H.controllerDisplayNames([R2, 'garbage', R1, R9, R1, L1]);
  assert.deepEqual(names, { [R9]: '右 Joy-Con 1', [R1]: '右 Joy-Con 2', [R2]: '右 Joy-Con 3', [L1]: '左 Joy-Con' });
  assert.deepEqual(H.controllerDisplayNames([L1, R1, R2, R9].reverse()), names);
  // 同埠不同指紋（重新配對）：依完整 id 決定先後，仍各自唯一
  const twin = H.controllerDisplayNames(['L24801-ffffffff', L1]);
  assert.deepEqual(twin, { [L1]: '左 Joy-Con 1', 'L24801-ffffffff': '左 Joy-Con 2' });
  assert.deepEqual(H.controllerDisplayNames(['R24800-legacy']), { 'R24800-legacy': '右 Joy-Con' });
  for (const label of [...Object.values(names), ...Object.values(twin)]) assert.doesNotMatch(label, LEAK);
  assert.deepEqual(H.controllerDisplayNames(null), {});
});

test('controllerNames：序號只依目前 bridge roster（與 🎮 HUD 同一規則）；不在 roster 的 id 只回左右，不回 id', () => {
  const both = [{ id: R2, side: 'right', status: 'active', owner: null }, { id: R1, side: 'right', status: 'active', owner: 'you' }];
  const label = H.controllerNames(both);
  assert.equal(label(R1), '右 Joy-Con 1');
  assert.equal(label(R2), '右 Joy-Con 2');
  // R2 暫時不在 roster：R1 是同側唯一一支 → 「右 Joy-Con」；R2 只回左右
  const one = H.controllerNames([both[1]]);
  assert.equal(one(R1), '右 Joy-Con');
  assert.equal(one(R2), '右 Joy-Con');
  assert.equal(label('L24809-12345678'), '左 Joy-Con');
  assert.equal(label(null), 'Joy-Con');
  assert.equal(label('garbage'), 'Joy-Con');
  // 每個分頁／每條連線看到同一份 roster → 同一個名稱（序號不依賴誰擁有）
  const other = H.controllerNames(both.map(c => ({ ...c, owner: 'other' })));
  assert.equal(other(R1), label(R1));
  assert.equal(other(R2), label(R2));
});

test('大廳手把下拉選項帶玩家名稱 label（不帶 bridge name 指紋），身份仍是完整 id', () => {
  let store = storeWith(TW, HK);
  store = H.bindController(store, G, 'p-tw', L1).store;
  const roster = [
    { id: L1, side: 'left', status: 'active', owner: 'you', name: 'Joy-Con (L) 3f2a9c1e' },
    { id: R1, side: 'right', status: 'active', owner: null, name: 'Joy-Con (R) 0a1b2c3d' },
    { id: R2, side: 'right', status: 'stale', owner: null, name: 'Joy-Con (R) aaaabbbb' },
  ];
  const opts = H.controllerChoices(store, G, 'p-hk', roster);
  assert.deepEqual(opts.map(o => [o.id, o.label]), [[L1, '左 Joy-Con'], [R1, '右 Joy-Con 1'], [R2, '右 Joy-Con 2']]);
  for (const o of opts) {
    assert.equal(H.isControllerId(o.id), true);
    assert.doesNotMatch(o.label, LEAK);
    assert.equal('name' in o, false);
  }
  // 綁定但不在清單的那一支也有 label（只有左右，不佔 roster 序號）
  const missing = H.controllerChoices(H.bindController(store, G, 'p-hk', 'R24803-99998888').store, G, 'p-hk', roster);
  assert.equal(missing.find(o => o.id === 'R24803-99998888').label, '右 Joy-Con');
  assert.equal(missing.find(o => o.id === R1).label, '右 Joy-Con 1');
});

test('席位 Joy-Con 狀態燈：已綁定一律只顯示色燈（無可見狀態文字）；只有連線正常是綠燈；aria／title 保留完整狀態；未綁定保留文字', () => {
  const store = boundStore();
  const tw = H.seatsFor(store, G)[0];
  const label = H.controllerNames([]);
  const roster = (c) => [{ id: L1, side: 'left', ...c }];
  const view = (seat, opts) => H.seatJoyStatus(seat, { label, enabled: true, ...opts });
  const ok = view(tw, { roster: roster({ status: 'active', owner: 'you' }) });
  assert.deepEqual(ok, { state: 'active', tone: 'ok', name: '左 Joy-Con', text: '', aria: '左 Joy-Con：連線正常' });
  const cases = {
    stale: [view(tw, { roster: roster({ status: 'stale', owner: 'you' }) }), 'warn', '訊號中斷'],
    missing: [view(tw, { roster: [] }), 'off', '未偵測到'],
    'other-tab': [view(tw, { roster: roster({ status: 'active', owner: 'other' }) }), 'error', '其他分頁使用中'],
    'no-bridge': [view(tw, { roster: null }), 'off', 'bridge 未連線'],
    disabled: [view(tw, { roster: roster({ status: 'active' }), enabled: false }), 'off', '搖桿控制未啟用'],
  };
  for (const [state, [v, tone, full]] of Object.entries(cases)) {
    // 已綁定的異常：只有對應色燈，沒有可見文字；完整狀態只在 aria-label／title
    assert.deepEqual([v.state, v.tone, v.text], [state, tone, ''], state);
    assert.notEqual(v.tone, 'ok', state); // 錯誤不偽裝成綠燈
    assert.equal(v.aria, `左 Joy-Con：${full}`, state);
  }
  // other-tab 但是本分頁的監聽連線 → withLocalOwners 後為連線正常
  const local = H.withLocalOwners(roster({ status: 'active', owner: 'other' }), [L1]);
  assert.equal(view(tw, { roster: local }).tone, 'ok');
  const unbound = view({ ...tw, controller: null }, { roster: [] });
  assert.deepEqual(unbound, { state: 'unbound', tone: 'none', name: '', text: '未綁定 Joy-Con', aria: '未綁定 Joy-Con' });
  for (const v of [ok, unbound, ...Object.values(cases).map(c => c[0])]) {
    assert.doesNotMatch(`${v.name}${v.text}${v.aria}`, LEAK);
    assert.doesNotMatch(`${v.text}${v.aria}`, /有訊號/);
  }
});

// ---- AI 紅軍公開行動視窗：只在目前行動的玩家（current player）是 AI 紅軍（waiting 遮罩）時有內容；內容欄位固定、大小有上限
const AI_ID = 'ai-red-1';
const aiState = (extra = {}) => state({
  turn: 3,
  current_player: 'AI 紅軍',
  players: [
    { id: 'p-tw', name: '臺灣玩家', faction: 'taiwan_green' },
    { id: 'p-hk', name: '香港玩家', faction: 'hong_kong' },
    { id: AI_ID, name: 'AI 紅軍', faction: 'red_army' },
  ],
  ai_red_army: {
    enabled: true, player_id: AI_ID, status: { state: 'idle' },
    public_report: {
      turn: 3, actor_name: 'AI 紅軍', next_seq: 3,
      steps: [
        { seq: 1, lines: ['[Turn 3] AI 紅軍 bought 宣傳家'], resources: { money: 1, propaganda: 0 }, delta: { money: -2, propaganda: 0 } },
        { seq: 2, lines: ['[Turn 3] AI 紅軍 played 追隨者 as resource'], resources: { money: 2, propaganda: 1 }, delta: { money: 1, propaganda: 1 } },
      ],
    },
  },
  ...extra,
});
const aiVerdict = (s) => H.decide({ state: s, connectedSeatId: 'p-tw', session: { gameId: G, active: 'p-tw', unlocked: true }, store: storeWith(TW, HK), gameId: G });

test('AI 紅軍是目前行動的玩家（faction red_army）：waiting 遮罩帶出公開行動（步驟、公開資源與變化）', () => {
  const s = aiState();
  const verdict = aiVerdict(s);
  assert.equal(verdict.view, 'waiting');
  assert.equal(verdict.actor.playerId, AI_ID);
  const view = H.aiPublicView(s, verdict);
  assert.equal(view.actorName, 'AI 紅軍');
  assert.equal(view.turn, 3);
  assert.deepEqual(view.steps.map(x => x.seq), [1, 2]);
  assert.deepEqual(view.steps[1].delta, { money: 1, propaganda: 1 });
  assert.deepEqual(view.steps[1].resources, { money: 2, propaganda: 1 });
  assert.deepEqual(Object.keys(view.steps[0]).sort(), ['delta', 'lines', 'resources', 'seq']);
});

test('只在紅軍是目前行動的玩家時有內容：行動者是本機真人、不是 waiting 遮罩、沒有 AI、行動者不是紅軍 → null（結束時機由 UI 決定，不在這裡）', () => {
  const ai = aiState();
  assert.ok(H.aiPublicView(ai, aiVerdict(ai)));
  // 下一位真人成為行動者：交接遮罩（handoff），AI 視窗關閉
  const next = aiState({ current_player: '香港玩家' });
  const handoff = aiVerdict(next);
  assert.equal(handoff.view, 'handoff');
  assert.equal(H.aiPublicView(next, handoff), null);
  // pending_choice 交給真人（例如反應視窗）也是換人
  const choice = aiState({ pending_choice: { player_id: 'p-hk' } });
  assert.equal(H.aiPublicView(choice, aiVerdict(choice)), null);
  // 沒有啟用 AI／不是 AI 的席位／沒有 verdict
  assert.equal(H.aiPublicView(state(), H.decide({ state: state(), connectedSeatId: 'p-tw', session: { gameId: G, active: 'p-tw', unlocked: true }, store: storeWith(TW, HK), gameId: G })), null);
  const off = aiState(); off.ai_red_army.enabled = false;
  assert.equal(H.aiPublicView(off, aiVerdict(off)), null);
  assert.equal(H.aiPublicView(ai, null), null);
  // 紅軍仍是 current player 才有內容：actor 不是紅軍陣營 → null
  const notRed = aiState(); notRed.players[2].faction = 'taiwan_green';
  assert.equal(H.aiPublicView(notRed, aiVerdict(notRed)), null);
  assert.equal(H.aiPublicView(null, aiVerdict(ai)), null);
});

test('舊回合的摘要不顯示：AI 回合剛開始、還沒有任何公開行動時是空步驟', () => {
  const s = aiState({ turn: 4 });
  const view = H.aiPublicView(s, aiVerdict(s));
  assert.deepEqual(view.steps, []);
  assert.equal(view.turn, 4);
});

test('摘要大小有上限：最多 6 步、每步 12 行、每行 200 字；非字串行丟棄', () => {
  const s = aiState();
  s.ai_red_army.public_report.steps = Array.from({ length: 10 }, (_, i) => ({
    seq: i + 1, lines: [...Array.from({ length: 20 }, (_, n) => `AI 紅軍 line ${n}`), 42, null, '  ', 'x'.repeat(500)],
    resources: { money: 'bad', propaganda: 2.9 }, delta: null,
  }));
  const view = H.aiPublicView(s, aiVerdict(s));
  assert.equal(view.steps.length, 6);
  assert.equal(view.steps[0].seq, 5);
  assert.ok(view.steps.every(x => x.lines.length <= 12 && x.lines.every(l => typeof l === 'string' && l.length <= 200)));
  assert.deepEqual(view.steps[0].resources, { money: 0, propaganda: 2 });
  assert.deepEqual(view.steps[0].delta, { money: 0, propaganda: 0 });
});

test('AI 回合常見英文 log 句型轉成繁體中文；沒有對應的回傳 null（不露出英文）', () => {
  assert.equal(H.aiLineText('[Turn 1] End of turn for AI 紅軍'), 'AI 紅軍 結束回合');
  assert.equal(H.aiLineText('[Turn 2] Event drawn: 歲月靜好 (no-op)'), '抽出事件：歲月靜好');
  assert.equal(H.aiLineText('[Turn 3] Event failure: 單人房主 must discard 1 hand card(s)'), '事件失敗：單人房主須棄 1 張手牌');
  assert.equal(H.aiLineText("[Turn 1] AI 紅軍 triggered 政工部 and placed 內鬥 on 單人房主's deck"), 'AI 紅軍 發動政工部，將內鬥放到單人房主的牌庫上');
  assert.equal(H.aiLineText('[Turn 1] AI 紅軍 bought 宣傳家'), null);
  assert.equal(H.aiLineText(undefined), null);
});

test('回合結束的等待確認來自伺服器 awaiting_ack：current player 仍是紅軍時 ended＝true；沒有（或舊回合）則 false', () => {
  const s = aiState();
  assert.equal(H.aiPublicView(s, aiVerdict(s)).ended, false);
  s.ai_red_army.awaiting_ack = { turn: 3, timeout_seconds: 10 };
  const view = H.aiPublicView(s, aiVerdict(s));
  assert.equal(s.current_player, 'AI 紅軍'); // 權威欄位：仍輪到紅軍
  assert.deepEqual([view.ended, view.timeoutSeconds], [true, 10]);
  s.ai_red_army.awaiting_ack = { turn: 2, timeout_seconds: 10 }; // 舊回合的等待不算
  assert.equal(H.aiPublicView(s, aiVerdict(s)).ended, false);
  // 伺服器放行（awaiting_ack 清除並輪到下一位）：不再有 AI 視窗內容
  const next = aiState({ current_player: '香港玩家' });
  assert.equal(H.aiPublicView(next, aiVerdict(next)), null);
});
