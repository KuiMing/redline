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

  /**
   * 所有輸入（bridge 訊息與公開 feed()）進 reduceFrame 前的連線閘門：
   *   'accept'  啟用、connected 且目前 socket 開著；
   *   'recover' stale 時由目前 bridge socket 自己的 frame 恢復（呼叫端先 reset，這筆只當 baseline）；
   *   'drop'    其他一律丟棄：停用、off、connecting、error、socket 不在或未開啟、stale 時非 bridge 來源。
   */
  function bridgeInputGate({ enabled, status, socketOpen, fromBridge } = {}) {
    if (enabled !== true || socketOpen !== true) return 'drop';
    if (status === 'connected') return 'accept';
    if (status === 'stale' && fromBridge === true) return 'recover';
    return 'drop';
  }

  /** 快捷鍵提示與執行的必要條件：啟用、connected 且目前 socket 開著。 */
  function bridgeConnected({ enabled, status, socketOpen } = {}) {
    return enabled === true && status === 'connected' && socketOpen === true;
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
   * 手牌焦點：X = 資源、Y = 行動；其他任何卡牌焦點的 X/Y 完全 no-op。非卡牌焦點的 X/Y 維持原行為。
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
        if (card) return onHand && ctx.hasFocus && !modal ? { cmd: 'cardMode', mode: 'resource' } : null;
        return modal || ctx.sectionsLocked ? null : { cmd: 'focusTurnBar' };
      case 'toggleHelp':
        if (card) return onHand && ctx.hasFocus && !modal ? { cmd: 'cardMode', mode: 'action' } : null;
        return { cmd: 'toggleHelp' };
      default: return null;
    }
  }

  // ---------------------------------------------------------------- scope / focus set

  // 由高到低：同時可見多個時，只有第一個取得輸入。cancel = B 可點的既有取消／關閉元素 selector。
  // initial = 開啟時的預設焦點（客廳模式危險操作確認單：永遠預設「返回」）。
  const MODAL_SCOPES = Object.freeze([
    { id: 'lrConfirmModal', cancel: ['#lrConfirmCancelBtn'], initial: '#lrConfirmCancelBtn' },
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

  /**
   * 方向焦點只停在內容資料（桌面與客廳兩種顯示模式相同）。下列既有控制一律排除，改由專用鍵或 R／SR 操作（滑鼠照常可用）：
   * 手牌內的資源／行動／棄置鈕（整張手牌 X／Y／B）、卡牌勾選框（B）、六個全域分頁（R／SR）、
   * 回合列：結束行動／紅軍能力（Capture）、按鍵提示列、陣營能力發動鈕（PLUS）。描述不明 → 排除（fail-closed）。
   */
  function isDirectionalExcluded(d) {
    if (!d || typeof d !== 'object') return true;
    return !!(d.handAction || d.cardCheckbox || d.sectionTab || d.turnControl || d.hintBar || d.factionAbility);
  }

  function isFocusableCandidate(c) {
    return !!c && c.visible === true && !c.disabled && !c.ariaDisabled && !c.skip && !isDirectionalExcluded(c);
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
  const MAP_COMMANDS = Object.freeze(['snapshot', 'focus', 'clearFocus', 'activate', 'button', 'cancel', 'act']);
  // 客廳模式地圖 Y：目標的既有主要操作 → 執行它的既有按鈕（建立組織／確認移動／瓦解組織）。
  const MAP_ACTS = Object.freeze({ build: 'directBuildBtn', move: 'confirmMoveBtn', dissolve: 'dissolveBtn' });
  const MAP_ACT_BUTTON_IDS = Object.freeze(Object.values(MAP_ACTS));

  /**
   * 目標的 Y 操作只由 scope／role 與 iframe 讀到的權威旗標決定：
   *   choice 目標 → pending choice 的建立（build）或瓦解（dissolve）；
   *   move 目標（已選來源的伺服器合法目的地）→ 移動；
   *   origin 目標 → 只有可瓦解共享組織（dissolveOrigin）時才是瓦解。其餘一律沒有 Y 操作。
   */
  function mapTargetAct(scope, role, flags) {
    const f = flags || {};
    if (scope === 'choice' && role === 'choice') return f.choiceKind === 'build' || f.choiceKind === 'dissolve' ? f.choiceKind : null;
    if (scope === 'move' && role === 'move') return 'move';
    if (scope === 'move' && role === 'origin') return f.dissolveOrigin === true ? 'dissolve' : null;
    return null;
  }

  /** snapshot 內的 act 必須與 scope／role 相容（例如 origin 不可能是 move）。 */
  function isActLegalFor(scope, role, act) {
    if (scope === 'choice') return role === 'choice' && (act === 'build' || act === 'dissolve');
    if (scope === 'move') return (role === 'move' && act === 'move') || (role === 'origin' && act === 'dissolve');
    return false;
  }

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
  const MOVE_MODES = Object.freeze(['road', 'rail']);
  // 以存在與否判斷而非 truthiness：0 視為合法值保留，只排除負數、非整數與不合理大值。
  function isMoveCost(v) { return Number.isInteger(v) && v >= 0 && v <= 20; }
  function isPresent(v) { return v !== undefined && v !== null; }

  /** 移動目標的選用欄位（客廳模式清單排序用）：有給就必須合法，否則整份 snapshot 作廢。 */
  function sanitizeMoveMeta(src, out) {
    if (isPresent(src.mode)) {
      if (!MOVE_MODES.includes(src.mode)) return false;
      out.mode = src.mode;
    }
    if (isPresent(src.cost)) {
      if (!isMoveCost(src.cost)) return false;
      out.cost = src.cost;
    }
    return true;
  }

  /** parent 端收到的 snapshot：不符 schema 一律回傳 null（視為沒有地圖目標）。 */
  function sanitizeMapSnapshot(data) {
    if (!data || data.type !== 'redline-controller-map-snapshot' || data.v !== MAP_MESSAGE_VERSION) return null;
    if (!MAP_SCOPES.includes(data.scope)) return null;
    if (!Array.isArray(data.targets) || data.targets.length > 400) return null;
    if (!Array.isArray(data.buttons) || data.buttons.length > MAP_BUTTON_IDS.length) return null;
    const targets = [];
    for (const t of data.targets) {
      if (!t || !isShortString(t.town) || !MAP_ROLES.includes(t.role) || !isCoord(t.x) || !isCoord(t.y)) return null;
      const target = { town: t.town, role: t.role, x: t.x, y: t.y };
      if (t.role === 'move' && !sanitizeMoveMeta(t, target)) return null;
      if (isPresent(t.act)) {
        if (!isActLegalFor(data.scope, t.role, t.act)) return null;
        target.act = t.act;
      }
      targets.push(target);
    }
    const buttons = [];
    for (const b of data.buttons) {
      if (!b || !MAP_BUTTON_IDS.includes(b.id) || !isShortString(b.label, 80) || !isCoord(b.x) || !isCoord(b.y)
        || !isCoord(b.w) || !isCoord(b.h)) return null;
      buttons.push({ id: b.id, label: b.label, x: b.x, y: b.y, w: b.w, h: b.h });
    }
    const focusTown = data.focusTown === null || data.focusTown === undefined ? null : data.focusTown;
    if (focusTown !== null && !isShortString(focusTown)) return null;
    const selected = isPresent(data.selected) ? data.selected : null;
    if (selected !== null && !isShortString(selected)) return null;
    let pending = null;
    if (isPresent(data.pending)) {
      const p = data.pending;
      if (!p || typeof p !== 'object' || !isShortString(p.from) || !isShortString(p.to)) return null;
      pending = { from: p.from, to: p.to };
      if (!sanitizeMoveMeta(p, pending)) return null;
    }
    return {
      scope: data.scope,
      seq: Number.isInteger(data.seq) ? data.seq : 0,
      targets,
      buttons,
      focusTown,
      canCancel: data.canCancel === true,
      selected,
      pending,
    };
  }

  // 執行型指令的 request id：parent 產生、iframe 原樣回傳，用來把 result 對應回唯一一次送出。
  function isRequestId(v) { return Number.isSafeInteger(v) && v > 0; }
  const MAP_RESULT_VIA = Object.freeze([...MAP_BUTTON_IDS, 'selection']);

  function sanitizeMapCommand(data) {
    if (!data || data.v !== MAP_MESSAGE_VERSION || data.type !== 'redline-controller-command') return null;
    if (!MAP_COMMANDS.includes(data.cmd)) return null;
    if (['focus', 'activate', 'act'].includes(data.cmd) && !isShortString(data.town)) return null;
    if (data.cmd === 'button' && !MAP_BUTTON_IDS.includes(data.id)) return null;
    if (data.cmd === 'act' && !MAP_ACT_BUTTON_IDS.includes(data.id)) return null;
    // act 只由客廳模式送出且一律等 correlated ack；沒有合法 req 的 act 不可執行（parent 會把 req:null 視為 stale）。
    // 桌面模式不帶 req 的 snapshot／focus／clearFocus／activate／button／cancel 行為不變。
    if (data.cmd === 'act' && !isRequestId(data.req)) return null;
    if (isPresent(data.req) && !isRequestId(data.req)) return null;
    return { cmd: data.cmd, town: data.town, id: data.id, req: isPresent(data.req) ? data.req : null };
  }

  /**
   * parent 端收到的 iframe 執行結果：不符 schema 回傳 null（呼叫端視為沒有收到確認）。
   * req＝對應的 request id（沒有帶 req 的指令為 null）；via＝iframe 實際走的既有控制（例如取消瓦解或取消選取）。
   */
  function sanitizeMapResult(data) {
    if (!data || data.type !== 'redline-controller-result' || data.v !== MAP_MESSAGE_VERSION) return null;
    if (!MAP_COMMANDS.includes(data.cmd) || typeof data.ok !== 'boolean') return null;
    if (data.cmd === 'act' && !isRequestId(data.req)) return null;
    if (isPresent(data.req) && !isRequestId(data.req)) return null;
    if (isPresent(data.via) && !MAP_RESULT_VIA.includes(data.via)) return null;
    if (isPresent(data.reason) && !isShortString(data.reason)) return null;
    return {
      cmd: data.cmd,
      ok: data.ok,
      req: isPresent(data.req) ? data.req : null,
      via: isPresent(data.via) ? data.via : null,
      reason: isPresent(data.reason) ? data.reason : null,
    };
  }

  /**
   * 由伺服器權威資料整理地圖焦點集合（純函式）。
   * input: {
   *   hasState, viewerCanAct, pendingChoiceBlocksMoves,
   *   highlight: {towns:[{town}]} | null,   // 來自 pending choice
   *   visibleTowns: string[], knownTowns: string[],
   *   moveTargets: [{town, mode?, cost?}], selectedTown, originTowns: string[],
   *   pendingMoveTarget: {from, to, mode?, cost?} | null,   // 既有「已點選待確認」的目的地
   *   dissolveOrigins: string[],   // 可對實際擁有者瓦解共享組織的來源城鎮（既有「瓦解組織」按鈕的判定）
   *   buttons: [{id, visible, disabled, label}],
   * }
   * highlight.actionKind（'build'|'dissolve'）決定 choice 目標的 Y 操作。
   * 缺少狀態／非自己回合／不在可見或已知城鎮 → 不產生目標（fail-closed）。
   */
  function buildMapSnapshotModel(input) {
    const empty = { scope: 'none', targets: [], buttons: [], focusTown: null, selected: null, pending: null };
    if (!input || !input.hasState) return empty;
    const visible = new Set(input.visibleTowns || []);
    const known = new Set(input.knownTowns || []);
    const dissolveOrigins = new Set(input.dissolveOrigins || []);
    const ok = name => typeof name === 'string' && visible.has(name) && known.has(name);
    const seen = new Set();
    const targets = [];
    let scope = 'none';
    const add = (town, role, meta) => {
      if (!ok(town) || seen.has(town)) return;
      seen.add(town);
      const target = { town, role };
      if (meta && MOVE_MODES.includes(meta.mode)) target.mode = meta.mode;
      if (meta && isMoveCost(meta.cost)) target.cost = meta.cost;
      const act = mapTargetAct(scope, role, {
        choiceKind: input.highlight && input.highlight.actionKind,
        dissolveOrigin: dissolveOrigins.has(town),
      });
      if (act) target.act = act;
      targets.push(target);
    };

    let focusTown = null;
    let selected = null;
    let pending = null;
    if (input.highlight && Array.isArray(input.highlight.towns)) {
      scope = 'choice';
      input.highlight.towns.forEach(entry => add(entry && entry.town, 'choice'));
      if (ok(input.highlight.focusTown)) focusTown = input.highlight.focusTown;
      if (ok(input.selectedTown) && targets.some(t => t.town === input.selectedTown)) selected = input.selectedTown;
    } else if (input.viewerCanAct && !input.pendingChoiceBlocksMoves) {
      scope = 'move';
      (input.moveTargets || []).forEach(entry => add(entry && entry.town, 'move', entry));
      (input.originTowns || []).forEach(town => add(town, 'origin'));
      if (ok(input.selectedTown)) {
        focusTown = input.selectedTown;
        selected = input.selectedTown;
      }
      const p = input.pendingMoveTarget;
      if (p && selected && p.from === selected && targets.some(t => t.role === 'move' && t.town === p.to)) {
        pending = { from: p.from, to: p.to };
        if (MOVE_MODES.includes(p.mode)) pending.mode = p.mode;
        if (isMoveCost(p.cost)) pending.cost = p.cost;
      }
    }
    if (scope === 'none') return empty;

    const buttons = (input.buttons || [])
      .filter(b => b && MAP_BUTTON_IDS.includes(b.id) && b.visible === true && !b.disabled)
      .map(b => ({ id: b.id, label: String(b.label || '').slice(0, 80) }));
    return { scope, targets, buttons, focusTown, selected, pending };
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
    MAP_MESSAGE_VERSION, MAP_BUTTON_IDS, MAP_COMMANDS, MAP_RESULT_VIA, MAP_ACTS, mapTargetAct,
    decodeButtonBytes, parseButtons, normalizeFrame,
    createInputState, resetInputState, reduceFrame, stickDirection, isStale, bridgeInputGate, bridgeConnected,
    logicalAction, routeAction,
    resolveModalScope, isDirectionalExcluded, isFocusableCandidate, buildFocusSet, pickInitial, pickDirectional, cycleIndex,
    isTrustedMessage, sanitizeMapSnapshot, sanitizeMapCommand, sanitizeMapResult, buildMapSnapshotModel,
    validateBridgeUrl, normalizeSettings, mixedContentRisk, reconnectDelayMs,
  };
});
