/*
 * REDLINE controller core — 純邏輯，無 DOM 依賴，可在 node 直接測試。
 *
 * 分層：physical input（bridge frame）→ logical actions（nav/press）→ context router
 * （modal / map / page）→ 由 controller_ui.js 呼叫既有 UI click handler。
 * 這裡不含遊戲規則；地圖目標只從呼叫端傳入的「伺服器權威資料」整理而來，缺資料即 fail-closed。
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.RedlineControllerCore = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const DEFAULT_BRIDGE_URL = 'ws://127.0.0.1:8000/ws';
  const DEFAULT_CONFIG = Object.freeze({
    deadzone: 0.5,
    repeatDelayMs: 380,
    repeatIntervalMs: 140,
    staleMs: 1500,
  });

  // bridge 的 S2B1 位元定義：b0 / b1 兩個 byte。
  const BUTTON_BITS = Object.freeze({
    A: [0, 0x08], B: [0, 0x04], X: [0, 0x02], Y: [0, 0x01],
    SL: [0, 0x20], SR: [0, 0x10], R: [0, 0x40], ZR: [0, 0x80],
    PLUS: [1, 0x02], STICK: [1, 0x04], HOME: [1, 0x10], CAPTURE: [1, 0x20],
  });
  const BUTTON_NAMES = Object.freeze(Object.keys(BUTTON_BITS));

  // ---------------------------------------------------------------- frame

  function decodeButtonBytes(b0, b1) {
    const out = {};
    for (const name of BUTTON_NAMES) {
      const [index, mask] = BUTTON_BITS[name];
      out[name] = ((index === 0 ? b0 : b1) & mask) !== 0;
    }
    return out;
  }

  function isByte(v) { return Number.isInteger(v) && v >= 0 && v <= 255; }

  /** 解析 buttons：[b0,b1]、{b0,b1}、單一整數（b0 | b1<<8）或 {A:true,...}。非法回傳 null。 */
  function parseButtons(raw) {
    if (Array.isArray(raw)) {
      if (raw.length < 1 || raw.length > 2) return null;
      const [b0, b1 = 0] = raw;
      return isByte(b0) && isByte(b1) ? decodeButtonBytes(b0, b1) : null;
    }
    if (typeof raw === 'number') {
      if (!Number.isInteger(raw) || raw < 0 || raw > 0xffff) return null;
      return decodeButtonBytes(raw & 0xff, (raw >> 8) & 0xff);
    }
    if (raw && typeof raw === 'object') {
      if ('b0' in raw || 'b1' in raw) {
        const b0 = raw.b0 ?? 0;
        const b1 = raw.b1 ?? 0;
        return isByte(b0) && isByte(b1) ? decodeButtonBytes(b0, b1) : null;
      }
      const out = {};
      for (const name of BUTTON_NAMES) out[name] = raw[name] === true;
      return out;
    }
    return null;
  }

  /** 驗證並正規化 bridge frame。x/y 必須是有限數且在 [-1.01, 1.01]；超出範圍整筆丟棄。 */
  function normalizeFrame(raw) {
    if (!raw || typeof raw !== 'object') return null;
    const { x, y } = raw;
    if (typeof x !== 'number' || typeof y !== 'number') return null;
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
    if (Math.abs(x) > 1.01 || Math.abs(y) > 1.01) return null;
    const buttons = parseButtons(raw.buttons);
    if (!buttons) return null;
    return { x: Math.max(-1, Math.min(1, x)), y: Math.max(-1, Math.min(1, y)), buttons };
  }

  // ---------------------------------------------------------------- reducer

  function createInputState() {
    return { armed: false, held: {}, dir: null, dirSince: 0, lastRepeat: 0, latched: false, lastFrameAt: null };
  }

  /** 方向：超過 deadzone 後取主軸（y>0 為畫面向下）。 */
  function stickDirection(x, y, deadzone = DEFAULT_CONFIG.deadzone) {
    const ax = Math.abs(x);
    const ay = Math.abs(y);
    if (Math.max(ax, ay) < deadzone) return null;
    if (ax >= ay) return x > 0 ? 'right' : 'left';
    return y > 0 ? 'down' : 'up';
  }

  /**
   * 餵入一筆 frame，回傳 {state, actions}。
   * 第一筆 frame（或 reset 後第一筆）只建立 baseline：已按住的按鈕不會觸發、已偏轉的搖桿要先回中，
   * 因此重新連線絕不會自動觸發按鈕。
   */
  function reduceFrame(prev, frame, now, config = DEFAULT_CONFIG) {
    const cfg = { ...DEFAULT_CONFIG, ...config };
    const dir = stickDirection(frame.x, frame.y, cfg.deadzone);
    const held = { ...frame.buttons };
    if (!prev.armed) {
      return {
        state: { armed: true, held, dir, dirSince: now, lastRepeat: now, latched: dir !== null, lastFrameAt: now },
        actions: [],
      };
    }
    const actions = [];
    for (const name of BUTTON_NAMES) {
      if (held[name] && !prev.held[name]) actions.push({ type: 'press', button: name });
    }
    let { dirSince, lastRepeat, latched } = prev;
    if (dir === null) {
      latched = false;
    } else if (!latched) {
      if (dir !== prev.dir) {
        actions.push({ type: 'nav', dir, repeat: false });
        dirSince = now;
        lastRepeat = now;
      } else if (now - dirSince >= cfg.repeatDelayMs && now - lastRepeat >= cfg.repeatIntervalMs) {
        actions.push({ type: 'nav', dir, repeat: true });
        lastRepeat = now;
      }
    }
    return { state: { armed: true, held, dir, dirSince, lastRepeat, latched, lastFrameAt: now }, actions };
  }

  /** 斷線／stale／停用：清空所有 held state，下一筆 frame 重新 baseline。 */
  function resetInputState() { return createInputState(); }

  function isStale(state, now, config = DEFAULT_CONFIG) {
    const cfg = { ...DEFAULT_CONFIG, ...config };
    return state.lastFrameAt === null || now - state.lastFrameAt > cfg.staleMs;
  }

  // ---------------------------------------------------------------- logical actions / router

  const BUTTON_ACTIONS = Object.freeze({
    A: 'confirm', B: 'cancel', R: 'nextSection', SR: 'prevSection', X: 'focusTurnBar', Y: 'toggleHelp',
  });

  /** 未對應的按鍵（含 `+`、HOME、CAPTURE、ZR、STICK、SL）一律不產生動作。 */
  function logicalAction(action) {
    if (action.type === 'nav') return { name: 'move', dir: action.dir };
    const name = BUTTON_ACTIONS[action.button];
    return name ? { name } : null;
  }

  /**
   * context router。ctx: {scopeKind:'modal'|'map'|'page', hasFocus, cancelAvailable, sectionsLocked,
   *   card?: {zone, hasToggle} | null}（card = 焦點位於卡牌元素內時的描述）。
   * 卡牌焦點：A = 查看預覽（絕不執行／勾選／購買）；B = 切換勾選（僅有勾選控制的卡牌，否則維持原本取消）；
   * 手牌焦點：X = 資源、Y = 行動。非手牌焦點的 X/Y 維持原行為。
   * 回傳要執行的 command 或 null（null = 靜默忽略）。
   */
  function routeAction(ctx, logical) {
    if (!logical) return null;
    const modal = ctx.scopeKind === 'modal';
    const card = ctx.card || null;
    const onHand = !!card && card.zone === 'hand';
    switch (logical.name) {
      case 'move': return { cmd: 'move', dir: logical.dir };
      case 'confirm':
        if (!ctx.hasFocus) return null;
        return card ? { cmd: 'cardPreview' } : { cmd: 'activate' };
      case 'cancel':
        if (ctx.hasFocus && card && card.hasToggle) return { cmd: 'cardToggle' };
        return ctx.cancelAvailable ? { cmd: 'cancel' } : null;
      case 'nextSection': return modal || ctx.sectionsLocked ? null : { cmd: 'section', step: 1 };
      case 'prevSection': return modal || ctx.sectionsLocked ? null : { cmd: 'section', step: -1 };
      case 'focusTurnBar':
        if (onHand && ctx.hasFocus && !modal) return { cmd: 'cardMode', mode: 'resource' };
        return modal || ctx.sectionsLocked ? null : { cmd: 'focusTurnBar' };
      case 'toggleHelp':
        if (onHand && ctx.hasFocus && !modal) return { cmd: 'cardMode', mode: 'action' };
        return { cmd: 'toggleHelp' };
      default: return null;
    }
  }

  // ---------------------------------------------------------------- scope / focus set

  // 由高到低：同時可見多個時，只有第一個取得輸入。cancel = B 可點的既有取消／關閉元素 selector。
  const MODAL_SCOPES = Object.freeze([
    { id: 'victoryArtViewer', cancel: ['#victoryArtViewerClose'] },
    { id: 'cardPreviewModal', cancel: ['self'] },
    { id: 'eventRevealModal', cancel: ['self'] },
    { id: 'unavailableActionModal', cancel: ['#closeUnavailableActionModalBtn'] },
    { id: 'peerActionNotice', cancel: ['#peerActionNoticeMinimizeBtn'] },
    { id: 'purchaseConfirmModal', cancel: ['.modal-cancel-btn'] },
    { id: 'factionActionModal', cancel: ['#closeFactionActionModal'] },
    { id: 'choiceModal', cancel: ['#closeChoiceModal'] },
    { id: 'eraAchievementModal', cancel: ['#eraAchievementMinimizeBtn'] },
    { id: 'victoryModal', cancel: [] },
    { id: 'factionPicker', cancel: ['#closeFactionPickerBtn'] },
  ]);

  /** visibleIds：目前可見的 modal id 集合。回傳最高優先權的 scope 定義，或 null。 */
  function resolveModalScope(visibleIds) {
    const visible = new Set(visibleIds || []);
    return MODAL_SCOPES.find(scope => visible.has(scope.id)) || null;
  }

  function isFocusableCandidate(c) {
    return !!c && c.visible === true && !c.disabled && !c.ariaDisabled && !c.skip;
  }

  /** candidates: [{key, scope, visible, disabled, ariaDisabled, skip, left, top, right, bottom}]。 */
  function buildFocusSet(candidates, activeScope) {
    return (candidates || []).filter(c => isFocusableCandidate(c) && c.scope === activeScope);
  }

  function center(item) {
    return { x: (item.left + item.right) / 2, y: (item.top + item.bottom) / 2 };
  }

  function readingOrder(a, b) {
    const ca = center(a);
    const cb = center(b);
    return (Math.round(ca.y / 8) - Math.round(cb.y / 8)) || (ca.x - cb.x);
  }

  function pickInitial(items) {
    return items.length ? [...items].sort(readingOrder)[0] : null;
  }

  /** 方向導航：回傳下一個 item；該方向沒有候選則回傳 current（不循環、不跳區）。 */
  function pickDirectional(items, currentKey, dir) {
    const current = items.find(i => i.key === currentKey);
    if (!current) return pickInitial(items);
    const c = center(current);
    let best = null;
    let bestScore = Infinity;
    for (const item of items) {
      if (item.key === currentKey) continue;
      const p = center(item);
      const dx = p.x - c.x;
      const dy = p.y - c.y;
      const primary = dir === 'right' ? dx : dir === 'left' ? -dx : dir === 'down' ? dy : -dy;
      const ortho = dir === 'left' || dir === 'right' ? Math.abs(dy) : Math.abs(dx);
      if (primary <= 1) continue;
      // 偏離主軸太多的目標只在沒有更好選擇時才採用（score 懲罰）。
      const score = primary + ortho * (ortho > primary * 1.5 ? 6 : 2);
      if (score < bestScore) { best = item; bestScore = score; }
    }
    return best || current;
  }

  function cycleIndex(length, index, step) {
    if (length <= 0) return -1;
    return ((index + step) % length + length) % length;
  }

  // ---------------------------------------------------------------- map protocol

  const MAP_MESSAGE_VERSION = 1;
  const MAP_SCOPES = Object.freeze(['none', 'choice', 'move']);
  const MAP_ROLES = Object.freeze(['choice', 'move', 'origin']);
  const MAP_BUTTON_IDS = Object.freeze(['directBuildBtn', 'confirmMoveBtn', 'dissolveBtn', 'cancelDissolveChoiceBtn']);
  const MAP_COMMANDS = Object.freeze(['snapshot', 'focus', 'clearFocus', 'activate', 'button', 'cancel']);

  /** parent↔iframe 訊息一律驗證 origin 與 source；缺一即拒絕。 */
  function isTrustedMessage(event, expectedOrigin, expectedSource) {
    if (!event || !expectedOrigin || !expectedSource) return false;
    if (event.origin !== expectedOrigin) return false;
    if (event.source !== expectedSource) return false;
    const data = event.data;
    return !!data && typeof data === 'object' && data.v === MAP_MESSAGE_VERSION && typeof data.type === 'string';
  }

  function isShortString(v, max = 64) { return typeof v === 'string' && v.length > 0 && v.length <= max; }
  function isCoord(v) { return typeof v === 'number' && Number.isFinite(v) && Math.abs(v) < 100000; }

  /** parent 端收到的 snapshot：不符 schema 一律回傳 null（視為沒有地圖目標）。 */
  function sanitizeMapSnapshot(data) {
    if (!data || data.type !== 'redline-controller-map-snapshot' || data.v !== MAP_MESSAGE_VERSION) return null;
    if (!MAP_SCOPES.includes(data.scope)) return null;
    if (!Array.isArray(data.targets) || data.targets.length > 400) return null;
    if (!Array.isArray(data.buttons) || data.buttons.length > MAP_BUTTON_IDS.length) return null;
    const targets = [];
    for (const t of data.targets) {
      if (!t || !isShortString(t.town) || !MAP_ROLES.includes(t.role) || !isCoord(t.x) || !isCoord(t.y)) return null;
      targets.push({ town: t.town, role: t.role, x: t.x, y: t.y });
    }
    const buttons = [];
    for (const b of data.buttons) {
      if (!b || !MAP_BUTTON_IDS.includes(b.id) || !isShortString(b.label, 80) || !isCoord(b.x) || !isCoord(b.y)
        || !isCoord(b.w) || !isCoord(b.h)) return null;
      buttons.push({ id: b.id, label: b.label, x: b.x, y: b.y, w: b.w, h: b.h });
    }
    const focusTown = data.focusTown === null || data.focusTown === undefined ? null : data.focusTown;
    if (focusTown !== null && !isShortString(focusTown)) return null;
    return {
      scope: data.scope,
      seq: Number.isInteger(data.seq) ? data.seq : 0,
      targets,
      buttons,
      focusTown,
      canCancel: data.canCancel === true,
    };
  }

  function sanitizeMapCommand(data) {
    if (!data || data.v !== MAP_MESSAGE_VERSION || data.type !== 'redline-controller-command') return null;
    if (!MAP_COMMANDS.includes(data.cmd)) return null;
    if (['focus', 'activate'].includes(data.cmd) && !isShortString(data.town)) return null;
    if (data.cmd === 'button' && !MAP_BUTTON_IDS.includes(data.id)) return null;
    return { cmd: data.cmd, town: data.town, id: data.id };
  }

  /**
   * 由伺服器權威資料整理地圖焦點集合（純函式）。
   * input: {
   *   hasState, viewerCanAct, pendingChoiceBlocksMoves,
   *   highlight: {towns:[{town}]} | null,   // 來自 pending choice
   *   visibleTowns: string[], knownTowns: string[],
   *   moveTargets: [{town}], selectedTown, originTowns: string[],
   *   buttons: [{id, visible, disabled, label}],
   * }
   * 缺少狀態／非自己回合／不在可見或已知城鎮 → 不產生目標（fail-closed）。
   */
  function buildMapSnapshotModel(input) {
    const empty = { scope: 'none', targets: [], buttons: [], focusTown: null };
    if (!input || !input.hasState) return empty;
    const visible = new Set(input.visibleTowns || []);
    const known = new Set(input.knownTowns || []);
    const ok = name => typeof name === 'string' && visible.has(name) && known.has(name);
    const seen = new Set();
    const targets = [];
    const add = (town, role) => {
      if (!ok(town) || seen.has(town)) return;
      seen.add(town);
      targets.push({ town, role });
    };

    let scope = 'none';
    let focusTown = null;
    if (input.highlight && Array.isArray(input.highlight.towns)) {
      scope = 'choice';
      input.highlight.towns.forEach(entry => add(entry && entry.town, 'choice'));
      if (ok(input.highlight.focusTown)) focusTown = input.highlight.focusTown;
    } else if (input.viewerCanAct && !input.pendingChoiceBlocksMoves) {
      scope = 'move';
      (input.moveTargets || []).forEach(entry => add(entry && entry.town, 'move'));
      (input.originTowns || []).forEach(town => add(town, 'origin'));
      if (ok(input.selectedTown)) focusTown = input.selectedTown;
    }
    if (scope === 'none') return empty;

    const buttons = (input.buttons || [])
      .filter(b => b && MAP_BUTTON_IDS.includes(b.id) && b.visible === true && !b.disabled)
      .map(b => ({ id: b.id, label: String(b.label || '').slice(0, 80) }));
    return { scope, targets, buttons, focusTown };
  }

  // ---------------------------------------------------------------- settings

  const LOCAL_HOSTS = new Set(['127.0.0.1', 'localhost', '[::1]']);

  /** bridge 在玩家自己的 Mac：只接受 ws(s)://loopback，避免頁面被導去連任意主機。 */
  function validateBridgeUrl(value) {
    if (typeof value !== 'string') return null;
    let url;
    try { url = new URL(value.trim()); } catch { return null; }
    if (url.protocol !== 'ws:' && url.protocol !== 'wss:') return null;
    if (!LOCAL_HOSTS.has(url.hostname)) return null;
    if (url.username || url.password) return null;
    return url.toString();
  }

  function normalizeSettings(raw) {
    const url = raw && validateBridgeUrl(raw.url);
    return { enabled: !!(raw && raw.enabled === true), url: url || DEFAULT_BRIDGE_URL };
  }

  /** https 頁面連 ws:// 會被部分瀏覽器擋（mixed content）；只回傳風險提示，不假裝已解決。 */
  function mixedContentRisk(pageProtocol, bridgeUrl) {
    return pageProtocol === 'https:' && /^ws:/i.test(bridgeUrl || '');
  }

  function reconnectDelayMs(attempt) {
    return Math.min(8000, 1000 * (2 ** Math.min(Math.max(attempt, 0), 3)));
  }

  return {
    DEFAULT_BRIDGE_URL, DEFAULT_CONFIG, BUTTON_BITS, BUTTON_NAMES, BUTTON_ACTIONS, MODAL_SCOPES,
    MAP_MESSAGE_VERSION, MAP_BUTTON_IDS, MAP_COMMANDS,
    decodeButtonBytes, parseButtons, normalizeFrame,
    createInputState, resetInputState, reduceFrame, stickDirection, isStale,
    logicalAction, routeAction,
    resolveModalScope, isFocusableCandidate, buildFocusSet, pickInitial, pickDirectional, cycleIndex,
    isTrustedMessage, sanitizeMapSnapshot, sanitizeMapCommand, buildMapSnapshotModel,
    validateBridgeUrl, normalizeSettings, mixedContentRisk, reconnectDelayMs,
  };
});
