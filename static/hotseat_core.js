/*
 * REDLINE 客廳輪流（hot-seat）— 純邏輯，無 DOM 依賴，可在 node 直接測試。
 *
 * 三個身份彼此分離：
 *   displayed viewer   — 主頁 WebSocket 目前以哪一席位的 resumeToken 連線（伺服器以它做 viewer-scoped state）
 *   controller owner   — bridge 判定本分頁擁有的 Joy-Con（及它綁定的本機席位）
 *   authoritative actor— 伺服器 state 的 pending_choice 擁有者 ▸ 香港免費遷移根據地 ▸ 選基地 ▸ 目前回合玩家
 * 交接只由 authoritative actor 驅動；不讀 DOM。這裡不含任何遊戲規則。
 * 大廳（尚未開局）另有 lobby actor：只讀 server /lobby 的公開資料（陣營、準備、房主），決定本分頁要聽哪一席的 Joy-Con。
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.RedlineHotSeatCore = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // 席位清單（同一瀏覽器共用）：localStorage。目前顯示／已確認的席位（每個分頁各自）：sessionStorage。
  const STORE_KEY = 'redline.hotseat.v1';
  const SESSION_KEY = 'redline.hotseat.session.v1';
  const MAX_SEATS = 12;
  const MASKED_VIEWS = Object.freeze(['loading', 'handoff', 'reconnect', 'waiting']);

  // 與 controller_core.isControllerId 相同格式（這支腳本在 <head> 先載入，不依賴 controller_core）。
  function isControllerId(v) {
    if (typeof v !== 'string' || v.length > 24) return false;
    const m = /^[LR]([1-9][0-9]{0,4})-(?:[0-9a-f]{8}|legacy)$/.exec(v);
    return !!m && Number(m[1]) <= 65535;
  }

  function isId(v) { return typeof v === 'string' && v.length > 0 && v.length <= 128; }

  function normalizeSeat(raw) {
    if (!raw || !isId(raw.player_id) || !isId(raw.resume_token)) return null;
    return {
      player_id: raw.player_id,
      resume_token: raw.resume_token,
      name: typeof raw.name === 'string' ? raw.name.slice(0, 40) : '',
      controller: isControllerId(raw.controller) ? raw.controller : null,
      // 行動代號是系統預設（送出時欄位仍是 HTML 預設值、使用者沒有輸入）；只有明確 true 才算，自訂名稱永遠是 false。
      auto_name: raw.auto_name === true,
    };
  }

  /** storage 內容不可信：格式不合的席位丟棄，整份壞掉就回空 store（fail closed＝不是 hot-seat 遊戲）。 */
  function normalizeStore(raw) {
    const store = { v: 1, enabled: false, games: {} };
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return store;
    store.enabled = raw.enabled === true;
    const games = raw.games && typeof raw.games === 'object' ? raw.games : {};
    for (const [gameId, game] of Object.entries(games)) {
      if (!isId(gameId) || !game || !Array.isArray(game.seats)) continue;
      const seats = [];
      const usedControllers = new Set();
      for (const s of game.seats.slice(0, MAX_SEATS)) {
        const seat = normalizeSeat(s);
        if (!seat || seats.some(x => x.player_id === seat.player_id)) continue;
        if (seat.controller && usedControllers.has(seat.controller)) seat.controller = null;
        if (seat.controller) usedControllers.add(seat.controller);
        seats.push(seat);
      }
      if (seats.length) store.games[gameId] = { seats };
    }
    return store;
  }

  function clone(store) { return normalizeStore(JSON.parse(JSON.stringify(store || {}))); }

  function seatsFor(store, gameId) {
    const game = store && store.games && store.games[gameId];
    return game ? game.seats.map(s => ({ ...s })) : [];
  }

  function findSeat(store, gameId, playerId) { return seatsFor(store, gameId).find(s => s.player_id === playerId) || null; }

  function seatForController(store, gameId, controllerId) {
    if (!controllerId) return null;
    return seatsFor(store, gameId).find(s => s.controller === controllerId) || null;
  }

  /**
   * 新增席位：絕不覆寫其他席位；同一 player_id 只更新 token／名稱，保留它的 Joy-Con 綁定。
   * auto_name 只在呼叫端明確給布林值時才改（未提供＝保留原值）。
   */
  function addSeat(store, gameId, seat) {
    const next = clone(store);
    const clean = normalizeSeat({ ...seat, controller: null });
    if (!isId(gameId) || !clean) return { ok: false, reason: 'invalid-seat', store: next };
    const game = next.games[gameId] || (next.games[gameId] = { seats: [] });
    const existing = game.seats.find(s => s.player_id === clean.player_id);
    if (existing) {
      existing.resume_token = clean.resume_token;
      if (clean.name) existing.name = clean.name;
      if (typeof seat.auto_name === 'boolean') existing.auto_name = seat.auto_name;
      return { ok: true, reason: null, store: next };
    }
    if (game.seats.length >= MAX_SEATS) return { ok: false, reason: 'too-many-seats', store: next };
    game.seats.push(clean);
    return { ok: true, reason: null, store: next };
  }

  function bindController(store, gameId, playerId, controllerId) {
    const next = clone(store);
    const game = next.games[gameId];
    const seat = game && game.seats.find(s => s.player_id === playerId);
    if (!seat) return { ok: false, reason: 'unknown-seat', store: next };
    if (!isControllerId(controllerId)) return { ok: false, reason: 'invalid-controller', store: next };
    if (game.seats.some(s => s.controller === controllerId && s.player_id !== playerId)) {
      return { ok: false, reason: 'controller-taken', store: next };
    }
    seat.controller = controllerId;
    return { ok: true, reason: null, store: next };
  }

  function unbindController(store, gameId, playerId) {
    const next = clone(store);
    const seat = next.games[gameId] && next.games[gameId].seats.find(s => s.player_id === playerId);
    if (seat) seat.controller = null;
    return next;
  }

  /** 啟用、本機至少兩個席位、且目前連線的是其中之一才算 hot-seat 遊戲（只有一席＝一般單席位行為）。 */
  function isHotSeatGame(store, gameId, playerId) {
    return !!(store && store.enabled && seatsFor(store, gameId).length >= 2 && findSeat(store, gameId, playerId));
  }

  function normalizeSession(raw, gameId) {
    if (!raw || raw.gameId !== gameId || !isId(raw.active)) return { gameId, active: null, unlocked: false };
    return { gameId, active: raw.active, unlocked: raw.unlocked === true };
  }

  function confirmSession(gameId, playerId) { return { gameId, active: playerId, unlocked: true }; }

  /**
   * 交接／等待遮罩一出現就鎖住：之後任何解除（含回到同一席位）都要重新以該席位 Joy-Con 確認。
   * reconnect 不鎖：那是剛確認完、正在以該席位 token 重新連線。
   */
  function lockSession(session, verdict) {
    const view = verdict && verdict.view;
    if (!session || (view !== 'handoff' && view !== 'waiting')) return session;
    return { ...session, unlocked: false };
  }

  function phaseOf(state) { return String((state && state.game_phase) || '').toLowerCase(); }

  /**
   * 只讀伺服器 state：pending_choice 擁有者 ▸ 香港抗暴之戰免費遷移根據地（hk_base_relocation_player_id）
   * ▸ 選基地 ▸ 目前回合玩家。缺資料＝none（fail closed）。
   */
  function authoritativeActor(state, localIds = []) {
    const none = { kind: 'none', playerId: null, name: '', faction: null };
    if (!state || typeof state !== 'object' || state.error && !Array.isArray(state.players)) return none;
    if (state.winner || phaseOf(state).includes('finished')) return { ...none, kind: 'finished' };
    const players = Array.isArray(state.players) ? state.players.filter(p => p && isId(p.id)) : [];
    const describe = (kind, p) => (p ? { kind, playerId: p.id, name: String(p.name || ''), faction: p.faction || null } : none);
    const choiceOwner = state.pending_choice && state.pending_choice.player_id;
    if (isId(choiceOwner)) return describe('pending_choice', players.find(p => p.id === choiceOwner));
    // 窗口開啟時伺服器凍結換人（current_player 仍是整輪最後一席），由香港決定遷移／留在。
    // 只認伺服器給的 id，不以陣營猜；旗標關閉時忽略殘留 id；旗標開啟但沒有可辨識的香港玩家＝none。
    if (state.hk_free_base_relocation === true) {
      const hkId = state.hk_base_relocation_player_id;
      return isId(hkId) ? describe('hk_base_relocation', players.find(p => p.id === hkId)) : none;
    }
    if (phaseOf(state).includes('base_selection') && state.pending_base_choices && typeof state.pending_base_choices === 'object') {
      const pending = Object.keys(state.pending_base_choices);
      const pick = pending.find(id => localIds.includes(id)) || pending[0];
      if (pick) return describe('base_selection', players.find(p => p.id === pick));
    }
    if (typeof state.current_player === 'string' && state.current_player) {
      const matches = players.filter(p => p.name === state.current_player);
      if (matches.length === 1) return describe('current_player', matches[0]);
    }
    return none;
  }

  /**
   * view：
   *   inactive  — 不是 hot-seat 遊戲（單席位桌面／客廳行為不變）
   *   open      — 行動者＝已確認的席位，且主頁連線就是該席位：顯示
   *   reconnect — 已確認，但主頁仍以別的席位連線：必須以該席位 token 重新連線
   *   handoff   — 需要交給本機的另一席位（或重新確認）：遮罩＋Joy-Con 確認
   *   waiting   — 行動者不是本機席位或沒有權威狀態：遮罩，不顯示任何席位
   */
  function decide({ state, connectedSeatId, session, store, gameId }) {
    if (!isHotSeatGame(store, gameId, connectedSeatId)) return { view: 'inactive', actor: null, seat: null, needsBinding: false };
    const seats = seatsFor(store, gameId);
    const actor = authoritativeActor(state, seats.map(s => s.player_id));
    if (actor.kind === 'finished') return { view: 'open', actor, seat: findSeat(store, gameId, connectedSeatId), needsBinding: false };
    const seat = actor.playerId ? seats.find(s => s.player_id === actor.playerId) || null : null;
    if (!seat) return { view: 'waiting', actor, seat: null, needsBinding: false };
    const s = normalizeSession(session, gameId);
    if (s.unlocked && s.active === seat.player_id) {
      return { view: connectedSeatId === seat.player_id ? 'open' : 'reconnect', actor, seat, needsBinding: false };
    }
    return { view: 'handoff', actor, seat, needsBinding: !seat.controller };
  }

  function masked(view) { return MASKED_VIEWS.includes(view); }

  /** 交接確認：只有 A，且本分頁（bridge 權威）擁有的正是綁給該席位的那一支。 */
  function confirmVerdict({ verdict, owned, action }) {
    if (!verdict || verdict.view !== 'handoff' || !verdict.seat) return { ok: false, reason: 'not-handoff' };
    if (!verdict.seat.controller) return { ok: false, reason: 'unbound' };
    if (!action || action.type !== 'press' || action.button !== 'A') return { ok: false, reason: 'not-confirm' };
    if (!owned || owned !== verdict.seat.controller) return { ok: false, reason: 'wrong-controller' };
    return { ok: true, reason: null };
  }

  /** 遮罩時所有 Joy-Con 輸入都不穿透；顯示時只有該席位綁定的那一支能操作。 */
  function allowsInput(verdict, owned) {
    if (!verdict || verdict.view === 'inactive') return true;
    if (verdict.view !== 'open') return false;
    if (!verdict.seat || !verdict.seat.controller) return verdict.actor && verdict.actor.kind === 'finished';
    return !!owned && owned === verdict.seat.controller;
  }

  /** 可綁定給這個席位的手把：有訊號、不是其他分頁使用中、沒有綁給其他本機席位。 */
  function bindableControllers(store, gameId, playerId, roster) {
    const taken = new Set(seatsFor(store, gameId).filter(s => s.player_id !== playerId && s.controller).map(s => s.controller));
    return (Array.isArray(roster) ? roster : []).filter(c => c && isControllerId(c.id)
      && c.status === 'active' && c.owner !== 'other' && !taken.has(c.id));
  }

  /** 綁定的手把已不在 bridge 清單，或沒有訊號：才允許更換（避免任何人隨意改綁別人的席位）。 */
  function bindingLost(seat, roster) {
    if (!seat || !seat.controller) return false;
    const c = (Array.isArray(roster) ? roster : []).find(x => x && x.id === seat.controller);
    return !c || c.status !== 'active';
  }

  /**
   * 主連線的 roster 會把本分頁大廳監聽連線擁有的手把標成 owner:'other'（bridge 只知道是另一條連線）。
   * 顯示用：這些精確 id 視為本分頁擁有（'you'），其他真的是別的分頁的維持 'other'。不修改輸入。
   */
  function withLocalOwners(roster, localIds) {
    if (!Array.isArray(roster)) return roster;
    const mine = new Set((Array.isArray(localIds) ? localIds : []).filter(isControllerId));
    return roster.map(c => (c && mine.has(c.id) && c.owner === 'other' ? { ...c, owner: 'you' } : c));
  }

  /** 席位手把狀態（只看 bridge roster 的精確 id，不以左右或名稱猜）：unbound／active／stale／missing／other-tab。 */
  function seatControllerStatus(seat, roster) {
    if (!seat || !seat.controller) return 'unbound';
    const c = (Array.isArray(roster) ? roster : []).find(x => x && x.id === seat.controller);
    if (!c) return 'missing';
    if (c.owner === 'other') return 'other-tab';
    return c.status === 'active' ? 'active' : 'stale';
  }

  // ---------------------------------------------------------------- 玩家看到的手把名稱與狀態
  // 內部 id（左右＋FTCW UDP 埠＋S2N1 名稱指紋）只用於綁定與 claim；玩家只看到左右，同側多支時加本機顯示序號。
  // 不顯示埠號、bridge 回報的名稱（含指紋）或 id。與 controller_core.controllerDisplayNames 同一規則（node 測試比對）。
  const SIDE_TEXT = Object.freeze({ L: '左 Joy-Con', R: '右 Joy-Con' });

  function idPort(id) { return Number(/^[LR](\d+)-/.exec(id)[1]); }

  /** ids → {id: 名稱}。同側只有一支＝「左 Joy-Con」；多支＝依埠號（同埠再依完整 id）排序的「左 Joy-Con 1／2…」。 */
  function controllerDisplayNames(ids) {
    const unique = [...new Set((Array.isArray(ids) ? ids : []).filter(isControllerId))];
    const out = {};
    for (const side of Object.keys(SIDE_TEXT)) {
      const group = unique.filter(id => id[0] === side)
        .sort((a, b) => idPort(a) - idPort(b) || (a < b ? -1 : a > b ? 1 : 0));
      group.forEach((id, i) => { out[id] = group.length > 1 ? `${SIDE_TEXT[side]} ${i + 1}` : SIDE_TEXT[side]; });
    }
    return out;
  }

  /**
   * 名稱函式：序號只依目前 bridge roster 排（與 🎮 HUD 的 controller_core.controllerLabel／bindingBadge 同一規則），
   * 每個分頁與監聽連線看到的相同。不在 roster 的 id（例如綁定但暫時未偵測到）只回左右；不合法 → 'Joy-Con'。永遠不回 id。
   */
  function controllerNames(roster) {
    const names = controllerDisplayNames((Array.isArray(roster) ? roster : []).map(c => c && c.id));
    return id => names[id] || (isControllerId(id) ? SIDE_TEXT[id[0]] : 'Joy-Con');
  }

  // 只有 active 是綠燈（ok）；其他狀態是非綠色色調。已綁定時一律只顯示色燈（text＝''），這裡的文字只進 aria-label／title。
  const JOY_STATUS = Object.freeze({
    active: ['ok', ''], stale: ['warn', '訊號中斷'], missing: ['off', '未偵測到'], 'other-tab': ['error', '其他分頁使用中'],
    'no-bridge': ['off', 'bridge 未連線'], disabled: ['off', '搖桿控制未啟用'],
  });

  /**
   * 席位列的手把狀態燈：{state, tone: ok|warn|error|off|none, name, text, aria}。
   * text＝可見狀態文字：只有未綁定有（「未綁定 Joy-Con」）；已綁定（含異常）一律 ''，完整狀態只在 aria（aria-label／title）。
   */
  function seatJoyStatus(seat, { label, enabled, roster } = {}) {
    if (!seat || !seat.controller) return { state: 'unbound', tone: 'none', name: '', text: '未綁定 Joy-Con', aria: '未綁定 Joy-Con' };
    const name = (typeof label === 'function' ? label : controllerNames(roster))(seat.controller);
    const state = enabled !== true ? 'disabled' : !Array.isArray(roster) ? 'no-bridge' : seatControllerStatus(seat, roster);
    const [tone, full] = JOY_STATUS[state] || ['off', '狀態不明'];
    return { state, tone, name, text: '', aria: `${name}：${full || '連線正常'}` };
  }

  /**
   * 大廳每列的手把下拉選項：bridge roster 的每一支＋這一席目前的綁定（即使暫時不在清單）。
   * 已綁給其他本機席位（taken）、其他分頁使用中（other-tab）、沒有訊號（stale）的不可選；目前綁定永遠可留著。
   * value 用完整 id（綁定／claim 的身份），label 是玩家看到的名稱。
   */
  function controllerChoices(store, gameId, playerId, roster) {
    const seats = seatsFor(store, gameId);
    const mine = seats.find(s => s.player_id === playerId);
    const current = mine ? mine.controller : null;
    const list = (Array.isArray(roster) ? roster : []).filter(c => c && isControllerId(c.id));
    const label = controllerNames(list);
    const out = list.map((c) => {
      const holder = seats.find(s => s.controller === c.id && s.player_id !== playerId) || null;
      const reason = holder ? 'taken' : c.owner === 'other' ? 'other-tab' : c.status !== 'active' ? 'stale' : null;
      return {
        id: c.id, label: label(c.id), selected: c.id === current,
        disabled: reason !== null && c.id !== current, reason, takenBy: holder ? holder.player_id : null,
      };
    });
    if (current && !list.some(c => c.id === current)) {
      out.push({ id: current, label: label(current), selected: true, disabled: false, reason: 'missing', takenBy: null });
    }
    return out;
  }

  // ---------------------------------------------------------------- 大廳：先綁定 Joy-Con，再由各自 Joy-Con 進入自己的選擇
  // bridge v2 一條連線最多擁有一支、且只收得到那一支的 frame：主連線（controller_ui）只 claim 目前席位的那一支；
  // 其他已綁定的本機席位各開一條只 claim 自己那一支的監聽連線，它按 A 才以該席自己的 resumeToken 整頁重新載入進入該席。

  function validLobby(lobby) { return !!lobby && typeof lobby === 'object' && !lobby.error && Array.isArray(lobby.players); }

  /** 本機席位列（server /lobby 的公開資料＋席位綁定），依 server 加入順序；不在 lobby 的本機席位排在最後。 */
  function lobbySeats({ lobby, store, gameId, connectedSeatId }) {
    const seats = seatsFor(store, gameId);
    const players = validLobby(lobby) ? lobby.players.filter(p => Array.isArray(p) && isId(p[0])) : [];
    const factions = (lobby && lobby.factions) || {};
    const bases = (lobby && lobby.bases) || {};
    const ready = (lobby && lobby.ready) || {};
    const row = (seat, name, inLobby) => ({
      player_id: seat.player_id, name: String(name || seat.name || ''),
      faction: (inLobby && factions[seat.player_id]) || null, base: (inLobby && bases[seat.player_id]) || null,
      ready: inLobby && ready[seat.player_id] === true, controller: seat.controller,
      connected: seat.player_id === connectedSeatId, inLobby,
    });
    const rows = [];
    for (const [pid, name] of players) {
      const seat = seats.find(s => s.player_id === pid);
      if (seat) rows.push(row(seat, name, true));
    }
    for (const seat of seats) if (!rows.some(r => r.player_id === seat.player_id)) rows.push(row(seat, seat.name, false));
    return rows;
  }

  // ---------------------------------------------------------------- 行動代號（Joy-Con 玩家不必輸入文字）
  // server /lobby 的 players 是加入順序（只 append，改名不移位）：第 1～4 席＝P1～P4。房間最多 4 位真人（AI 紅軍時 3 位），沒有 P5。
  const CODENAMES = Object.freeze(['P1', 'P2', 'P3', 'P4']);

  function lobbyPlayerIds(lobby) {
    return validLobby(lobby) ? lobby.players.map(p => (Array.isArray(p) && isId(p[0]) ? p[0] : null)) : null;
  }

  /** 這一席在 server lobby 的位置對應的代號；不在 lobby、資料不合或超過 4 席 → null。 */
  function seatCodename(lobby, playerId) {
    const ids = lobbyPlayerIds(lobby);
    const idx = ids ? ids.indexOf(playerId) : -1;
    return idx >= 0 ? CODENAMES[idx] || null : null;
  }

  /** 新增本機席位的暫定代號＝它將 append 進 server lobby 的位置；房間已滿（4 席，AI 紅軍時 3 席）或資料不合 → null。 */
  function nextSeatCodename(lobby) {
    const ids = lobbyPlayerIds(lobby);
    const capacity = lobby && lobby.ai_red_army === true ? 3 : CODENAMES.length;
    return ids && ids.length < capacity ? CODENAMES[ids.length] : null;
  }

  /**
   * 要寫回 server 的改名：hot-seat 啟用、本機至少兩席、尚未開局時，auto_name 的本機席位改成它在 server lobby 位置的代號。
   * 自訂名稱（auto_name false，即使字面是 host）永不覆寫；已正確的不重送。只依 server lobby 與席位資料，與目前顯示哪一席無關。
   */
  function codenameRenames({ lobby, store, gameId }) {
    if (!store || !store.enabled || !validLobby(lobby) || lobby.started === true) return [];
    const seats = seatsFor(store, gameId);
    if (seats.length < 2) return [];
    const out = [];
    for (const p of lobby.players) {
      const seat = Array.isArray(p) ? seats.find(s => s.player_id === p[0]) : null;
      const want = seat && seat.auto_name ? seatCodename(lobby, seat.player_id) : null;
      if (want && p[1] !== want) out.push({ player_id: seat.player_id, resume_token: seat.resume_token, name: want });
    }
    return out;
  }

  /** 目前連線的席位就是大廳行動者（kind 只描述它的進度）；不在 server lobby → none。 */
  function lobbyActor(lobby, rows, connectedSeatId) {
    const me = rows.find(r => r.inLobby && r.player_id === connectedSeatId);
    if (!me) return { kind: 'none', playerId: null, name: '' };
    const kind = !me.faction ? 'lobby_select' : !me.ready ? 'lobby_ready'
      : me.player_id === lobby.host_id ? 'lobby_start' : 'lobby_done';
    return { kind, playerId: me.player_id, name: me.name };
  }

  /**
   * view：
   *   inactive      — 不是 hot-seat 大廳（未啟用、單席位、連線不是本機席位、已開局）：完全不介入
   *   lobby-open    — 目前席位已綁定：主連線只 claim 它那一支，只有它能操作大廳
   *   lobby-bind    — 目前席位未綁定：主連線不 claim，任何 Joy-Con 都不能代替它操作
   *   lobby-waiting — 沒有可信的大廳狀態：fail closed（不 claim、不監聽、不切換）
   * 兩種 view 下，其他已綁定的本機席位都各有自己的監聽（lobbyListeners），按自己 Joy-Con 的 A 就切到自己的席位。
   */
  function decideLobby({ lobby, store, gameId, connectedSeatId }) {
    const base = { actor: null, seat: null, self: false, gameId, rows: [] };
    if (!isHotSeatGame(store, gameId, connectedSeatId)) return { ...base, view: 'inactive' };
    if (validLobby(lobby) && lobby.started === true) return { ...base, view: 'inactive' };
    if (!validLobby(lobby)) return { ...base, view: 'lobby-waiting' };
    const rows = lobbySeats({ lobby, store, gameId, connectedSeatId });
    const actor = lobbyActor(lobby, rows, connectedSeatId);
    const seat = actor.playerId ? findSeat(store, gameId, actor.playerId) : null;
    if (!seat) return { ...base, view: 'lobby-waiting' };
    return { view: seat.controller ? 'lobby-open' : 'lobby-bind', actor, seat, self: true, gameId, rows };
  }

  /** 這支 controller 綁定、在 server lobby 內、且不是目前席位的本機席位（＝它按 A 要切去的席位）；否則 null。 */
  function switchSeatFor(verdict, store, controller) {
    if (!verdict || !['lobby-open', 'lobby-bind'].includes(verdict.view) || !isControllerId(controller)) return null;
    const row = (verdict.rows || []).find(r => r.inLobby && r.controller === controller && !r.connected);
    const seat = row ? findSeat(store, verdict.gameId, row.player_id) : null;
    return seat && seat.controller === controller ? { ...seat } : null;
  }

  /** 要另開監聽連線的 controller：其他已綁定、在 server lobby 內的本機席位，各自只 claim 自己那一支。 */
  function lobbyListeners({ verdict, store, gameId }) {
    if (!verdict || !['lobby-open', 'lobby-bind'].includes(verdict.view) || verdict.gameId !== gameId) return [];
    return (verdict.rows || [])
      .filter(r => r.inLobby && !r.connected && r.controller && switchSeatFor(verdict, store, r.controller))
      .map(r => ({ controller: r.controller, player_id: r.player_id }));
  }

  /** 監聽連線的 reducer actions 裡有 A → 切到這支 controller 綁定的席位；其他鍵、未綁定或目前席位的 controller → null。 */
  function listenerSwitchTarget({ verdict, store, gameId, controller, actions }) {
    if (!verdict || verdict.gameId !== gameId) return null;
    const pressedA = (Array.isArray(actions) ? actions : []).some(a => a && a.type === 'press' && a.button === 'A');
    return pressedA ? switchSeatFor(verdict, store, controller) : null;
  }

  /**
   * 主連線（controller_ui dispatch 第一關）的大廳輸入。pass＝交給既有 focus／modal routing（只有目前席位自己綁定的那一支）；
   * switchTo＝主連線擁有的是其他本機席位綁定的 Joy-Con 且按 A → 切到那一席。未綁定或其他輸入一律攔下。
   */
  function lobbyInput({ verdict, owned, action, store }) {
    const out = (pass, switchTo = null, reason = null) => ({ pass, switchTo, reason });
    if (!verdict || verdict.view === 'inactive') return out(true);
    const isA = !!action && action.type === 'press' && action.button === 'A';
    const seat = verdict.seat;
    if (verdict.view === 'lobby-open' && owned && seat && owned === seat.controller) return out(true);
    if (verdict.view === 'lobby-waiting') return out(false, null, isA ? 'not-ready' : null);
    if (!isA) return out(false);
    const other = owned ? switchSeatFor(verdict, store, owned) : null;
    if (other) return out(false, other);
    if (owned && !seatsFor(store, verdict.gameId).some(s => s.controller === owned)) return out(false, null, 'controller-unbound');
    return out(false, null, 'wrong-controller');
  }

  /**
   * 行動者就是目前席位、尚未選陣營、選擇視窗沒開：它自己的 Joy-Con 按 A＝開啟自己的「選擇陣營與根據地」
   * （呼叫端點既有按鈕；已是自己的 token，不必重新載入）。其他情況交給既有 routing。
   */
  function lobbyEntersSelection({ verdict, owned, action, pickerOpen }) {
    return !!verdict && verdict.view === 'lobby-open' && pickerOpen !== true
      && !!verdict.actor && verdict.actor.kind === 'lobby_select'
      && !!action && action.type === 'press' && action.button === 'A'
      && !!owned && !!verdict.seat && owned === verdict.seat.controller;
  }

  /** 主連線應該 claim 哪一支：交接／顯示中的席位，或大廳目前席位綁定的那一支；其他情況不 claim。 */
  function claimTarget(verdict) {
    if (!verdict || !verdict.seat) return null;
    return ['handoff', 'open', 'lobby-open'].includes(verdict.view) ? verdict.seat.controller || null : null;
  }

  /** 大廳切換只決定「重新載入時恢復哪一席」，不解鎖遊戲：開局後的第一位行動者仍要交接確認。 */
  function switchSession(gameId, playerId) { return { gameId, active: playerId, unlocked: false }; }

  const LOBBY_OPEN_TEXT = Object.freeze({
    lobby_select: '選擇陣營與根據地', lobby_ready: '按下「我已準備」', lobby_start: '已完成，所有玩家準備後可啟動行動', lobby_done: '已完成，等待房主啟動',
  });
  const LOBBY_OTHERS = '其他本機玩家按自己 Joy-Con 的 A 進入自己的席位';

  function lobbyPrompt(verdict, controllerLabel) {
    const label = typeof controllerLabel === 'function' ? controllerLabel : controllerNames([]);
    const v = verdict || {};
    const name = (v.actor && v.actor.name) || (v.seat && v.seat.name) || '本機玩家';
    const kind = v.actor && v.actor.kind;
    if (v.view === 'lobby-open') return `〈${name}〉正在操作（${label(v.seat.controller)}）：${LOBBY_OPEN_TEXT[kind] || ''}。${LOBBY_OTHERS}`;
    if (v.view === 'lobby-bind') return `請先替〈${name}〉綁定一支 Joy-Con，才能用 Joy-Con 操作自己的席位。${LOBBY_OTHERS}`;
    if (v.view === 'lobby-waiting') return '正在讀取作戰室狀態…';
    return '';
  }

  function handoffTitle(actor, factionLabel) {
    const name = (actor && actor.name) || '下一位玩家';
    return `請交給〈${name}${factionLabel ? `／${factionLabel}` : ''}〉`;
  }

  const REASON_TEXT = Object.freeze({
    'wrong-controller': '這支 Joy-Con 不是此席位綁定的手把',
    unbound: '此席位尚未綁定 Joy-Con，請先在下方選擇',
    'controller-taken': '這支 Joy-Con 已綁給其他席位',
    'invalid-controller': '手把代號不正確',
    'unknown-seat': '找不到此席位',
    'not-ready': '正在讀取作戰室狀態，請稍候',
    'controller-unbound': '這支 Joy-Con 尚未綁定任何本機席位',
  });

  function reasonText(reason) { return REASON_TEXT[reason] || ''; }

  return {
    STORE_KEY, SESSION_KEY, MAX_SEATS, CODENAMES, seatCodename, nextSeatCodename, codenameRenames,
    isControllerId, normalizeStore, seatsFor, findSeat, seatForController, addSeat, bindController, unbindController,
    isHotSeatGame, normalizeSession, confirmSession, lockSession, authoritativeActor, decide, masked,
    confirmVerdict, allowsInput, bindableControllers, bindingLost, handoffTitle, reasonText,
    seatControllerStatus, controllerDisplayNames, controllerNames, seatJoyStatus, controllerChoices, withLocalOwners, lobbySeats, decideLobby, lobbyInput, lobbyEntersSelection, lobbyListeners, listenerSwitchTarget, claimTarget, switchSession, lobbyPrompt,
  };
});
