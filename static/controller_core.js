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
  // CAPTURE 主位元是 b1 0x40（上游 switch2mac 的 `c` = 0x4000）：只接右 Joy-Con 2 時，實機按「Capture」送出的就是它
  // （2026-10-10 bridge 實錄 buttons:[0,64]）。SL＝b0 0x20（聚焦選單）：使用者提供的實機按鍵區 capture 為 `20 00`。
  const BUTTON_BITS = Object.freeze({
    A: [0, 0x08], B: [0, 0x04], X: [0, 0x02], Y: [0, 0x01],
    SL: [0, 0x20], SR: [0, 0x10], R: [0, 0x40], ZR: [0, 0x80],
    PLUS: [1, 0x02], STICK: [1, 0x04], HOME: [1, 0x10], CAPTURE: [1, 0x40],
  });
  // 同一個邏輯鍵的相容位元：上游 `capture` = 0x2000（b1 0x20，左 Joy-Con 2／Pro 手把的截圖鍵）仍算 CAPTURE。
  // 兩個位元都沒有其他已知用途；同時或交替按住仍是同一個按鍵（只在第一次按下觸發）。
  const BUTTON_ALT_BITS = Object.freeze({ CAPTURE: Object.freeze([Object.freeze([1, 0x20])]) });
  const BUTTON_NAMES = Object.freeze(Object.keys(BUTTON_BITS));

  // ---------------------------------------------------------------- frame

  function bitSet(b0, b1, [index, mask]) { return ((index === 0 ? b0 : b1) & mask) !== 0; }

  function decodeButtonBytes(b0, b1) {
    const out = {};
    for (const name of BUTTON_NAMES) {
      out[name] = bitSet(b0, b1, BUTTON_BITS[name]) || (BUTTON_ALT_BITS[name] || []).some(bits => bitSet(b0, b1, bits));
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

  // SL＝全域地圖聚焦選單（兩種顯示模式相同；只改地圖相機與焦點標示，不執行任何遊戲操作）。
  // ZR＝戰略地圖放大一級、最大後回到最小（兩種顯示模式相同；只改地圖視角，其他 scope 完全 no-op）。
  const BUTTON_ACTIONS = Object.freeze({
    A: 'confirm', B: 'cancel', R: 'nextSection', SR: 'prevSection', X: 'focusTurnBar', Y: 'toggleHelp', SL: 'focusMenu', ZR: 'mapZoom',
  });

  /** 未對應的按鍵（含 `+`、HOME、CAPTURE、STICK）一律不產生動作。 */
  function logicalAction(action) {
    if (action.type === 'nav') return { name: 'move', dir: action.dir };
    const name = BUTTON_ACTIONS[action.button];
    return name ? { name } : null;
  }

  /**
   * context router。ctx: {scopeKind:'modal'|'map'|'page', hasFocus, cancelAvailable, sectionsLocked,
   *   card?: {zone, hasToggle, hasDiscard?} | null,   // 焦點位於卡牌元素內時的描述；hasDiscard＝手牌有既有「棄置」控制（一般奧援）
   *   mapTarget?: boolean,               // 焦點是地圖 snapshot 的城鎮目標（不是地圖按鈕）
   *   browseFocus?: boolean,             // 焦點是 SL 聚焦的只看城鎮（map scope 的 A = townDetail，重新開啟城鎮說明）
   *   focusMenuOpen?: boolean}           // 目前的 modal 就是 SL 聚焦選單
   * 卡牌焦點：A = 查看預覽（絕不執行／選擇／購買）；B = 切換選擇（僅有選擇控制的卡牌，否則維持原本取消）；
   * 手牌焦點：X = 資源（一般奧援＝既有「棄置」→ 危險確認；紅軍奧援的按鈕是「資源」，仍＝資源）、Y = 行動；B 與其他牌相同（不棄置）；購買卡 Y = 既有「購買所選」→ 購買確認單（UI 要求焦點卡已用 B 選擇，不自動選擇）；
   * 其他卡牌焦點的 X/Y 完全 no-op。地圖城鎮目標的 Y = 該目標的既有地圖操作（建立組織／確認移動／瓦解組織）。
   * helpEntry（焦點在導覽列「Joy-Con 說明」按鈕）：A = openHelp（開啟說明圖）、B = null；其餘鍵照非卡牌焦點。
   * SL = 開啟聚焦選單（page／map scope；不需要 pending choice 或焦點）；選單開著時 SL = 關閉（同 B）；其他 modal 內 SL 不作用（scope lock）。
   * 聚焦選單內只有方向、A（選取選項）、B（關閉）與 SL 有作用。
   * ZR = 戰略地圖縮放循環：只在 map scope（與焦點無關）；page、任何 modal（含聚焦選單）一律 null。
   * 其餘非卡牌焦點的 X/Y 維持原行為。回傳要執行的 command 或 null（null = 靜默忽略）。
   */
  function routeAction(ctx, logical) {
    if (!logical) return null;
    const modal = ctx.scopeKind === 'modal';
    const card = ctx.card || null;
    const onHand = !!card && card.zone === 'hand';
    switch (logical.name) {
      case 'focusMenu':
        if (modal) return ctx.focusMenuOpen ? { cmd: 'focusMenu' } : null;
        return { cmd: 'focusMenu' };
      case 'mapZoom': return ctx.scopeKind === 'map' && !ctx.focusMenuOpen ? { cmd: 'mapZoom' } : null;
      case 'move': return { cmd: 'move', dir: logical.dir };
      case 'confirm':
        // 焦點停在「Joy-Con 說明」按鈕（ctx.helpEntry，R／SR 環的額外焦點）：A 才開啟說明圖。
        if (ctx.helpEntry && !modal) return { cmd: 'openHelp' };
        // SL 聚焦的只看城鎮（ctx.browseFocus，不在 action 焦點集合內）：A＝重新開啟該城鎮說明（唯讀，不選取）。
        if (ctx.browseFocus && ctx.scopeKind === 'map') return { cmd: 'townDetail' };
        if (!ctx.hasFocus) return null;
        return card ? { cmd: 'cardPreview' } : { cmd: 'activate' };
      case 'cancel':
        if (ctx.helpEntry && !modal) return null; // 說明按鈕上的 B 不作用（不取消地圖選取等其他流程）
        if (ctx.hasFocus && card && card.hasToggle) return { cmd: 'cardToggle' };
        return ctx.cancelAvailable ? { cmd: 'cancel' } : null;
      case 'nextSection': return modal || ctx.sectionsLocked ? null : { cmd: 'section', step: 1 };
      case 'prevSection': return modal || ctx.sectionsLocked ? null : { cmd: 'section', step: -1 };
      case 'focusTurnBar':
        if (card) {
          if (!onHand || !ctx.hasFocus || modal) return null;
          return card.hasDiscard === true ? { cmd: 'cardDiscard' } : { cmd: 'cardMode', mode: 'resource' };
        }
        return modal || ctx.sectionsLocked ? null : { cmd: 'focusTurnBar' };
      case 'toggleHelp':
        if (ctx.focusMenuOpen) return null;
        if (card) {
          if (!ctx.hasFocus || modal) return null;
          if (onHand) return { cmd: 'cardMode', mode: 'action' };
          return card.zone === 'purchase' ? { cmd: 'cardBuy' } : null;
        }
        if (ctx.mapTarget && ctx.hasFocus && ctx.scopeKind === 'map') return { cmd: 'mapAct' };
        return { cmd: 'toggleHelp' };
      default: return null;
    }
  }

  // ---------------------------------------------------------------- 陣營／根據地選擇（factionPicker modal）的 Joy-Con 階段
  // faction（陣營）→ variant（mode≠direct 類別的既有具體陣營，例如反賊、臺灣）→ base（根據地）→ read（閱讀陣營資訊）。
  // 方向焦點只在目前階段的選項間移動（app.js 以 data-controller-skip 標記其他階段的按鈕）；滑鼠／鍵盤流程不經過這裡。
  const FACTION_PICKER_PHASES = Object.freeze(['faction', 'variant', 'base', 'read']);

  /**
   * factionPicker 內一個邏輯動作的指令（純函式）：
   *   {cmd:'pass'}           交回既有 modal 流程（階段內方向焦點、陣營階段 B＝既有「返回作戰室」、Y 說明等）；
   *   {cmd:'none'}           吃掉、不作用（閱讀階段的左右）；
   *   {cmd:'scroll', step}   閱讀階段搖桿上下：只捲動右側陣營資訊（-1 上、1 下），不改陣營／根據地焦點；
   *   {cmd:'pick'}           選定焦點中的陣營／具體陣營／根據地，並自動交接到下一階段；
   *   {cmd:'confirm'}        閱讀階段 A：最終確認（既有「確認陣營與根據地」）；
   *   {cmd:'back'}           B：read→base（取消已選根據地）、base→variant 或 faction、variant→faction。
   * 未知階段一律 pass（維持既有行為）。
   */
  function factionPickerCommand(phase, logical) {
    if (!logical || !FACTION_PICKER_PHASES.includes(phase)) return { cmd: 'pass' };
    switch (logical.name) {
      case 'move':
        if (phase !== 'read') return { cmd: 'pass' };
        if (logical.dir === 'up') return { cmd: 'scroll', step: -1 };
        if (logical.dir === 'down') return { cmd: 'scroll', step: 1 };
        return { cmd: 'none' };
      case 'confirm': return phase === 'read' ? { cmd: 'confirm' } : { cmd: 'pick' };
      case 'cancel': return phase === 'faction' ? { cmd: 'pass' } : { cmd: 'back' };
      default: return { cmd: 'pass' };
    }
  }

  /**
   * 底部 Joy-Con 提示（依階段）。opts：backTo（base 階段 B 回到 'variant'｜'faction'）、
   * canConfirm（閱讀階段既有確認鈕可用）、hasBase（閱讀階段有已選根據地可取消）。
   */
  function factionPickerHint(phase, opts) {
    const o = opts || {};
    switch (phase) {
      case 'faction': return '搖桿 選擇陣營　A 選定　B 返回作戰室';
      case 'variant': return '搖桿 選擇具體陣營　A 選定　B 返回陣營';
      case 'base': return `搖桿 選擇根據地　A 選定　B 返回${o.backTo === 'variant' ? '具體陣營' : '陣營'}`;
      case 'read': return `搖桿上下 捲動　${o.canConfirm ? 'A 確認　' : ''}B ${o.hasBase ? '取消根據地／返回' : '返回'}`;
      default: return null;
    }
  }

  // ---------------------------------------------------------------- scope / focus set

  // 由高到低：同時可見多個時，只有第一個取得輸入。cancel = B 可點的既有取消／關閉元素 selector。
  // initial = 開啟時的預設焦點（客廳模式危險操作確認單：永遠預設「返回」）。
  // SL 聚焦選單（兩種顯示模式共用）：B 點既有關閉 ×；預設焦點＝第一個選項。
  const FOCUS_MENU_MODAL_ID = 'lrFocusMenu';
  const MODAL_SCOPES = Object.freeze([
    { id: 'lrConfirmModal', cancel: ['#lrConfirmCancelBtn'], initial: '#lrConfirmCancelBtn' },
    { id: FOCUS_MENU_MODAL_ID, cancel: ['#lrFocusMenuClose'], initial: '.lr-focus-option' },
    { id: 'victoryArtViewer', cancel: ['#victoryArtViewerClose'] },
    // Joy-Con 說明圖：scope lock（R／SR、SL、ZR、X、Capture、+ 都不穿透）；B 點既有關閉 ×，焦點由 controller_ui 還原到說明按鈕。
    { id: 'joyconHelpModal', cancel: ['#joyconHelpCloseBtn'], initial: '#joyconHelpCloseBtn' },
    { id: 'cardPreviewModal', cancel: ['self'] },
    { id: 'eventRevealModal', cancel: ['self'] },
    { id: 'unavailableActionModal', cancel: ['#closeUnavailableActionModalBtn'] },
    { id: 'peerActionNotice', cancel: ['#peerActionNoticeMinimizeBtn'] },
    { id: 'purchaseConfirmModal', cancel: ['.modal-cancel-btn'] },
    { id: 'factionActionModal', cancel: ['#closeFactionActionModal'] },
    { id: 'choiceModal', cancel: ['#closeChoiceModal'] },
    { id: 'eraAchievementModal', cancel: ['#eraAchievementMinimizeBtn'] },
    { id: 'victoryModal', cancel: [] },
    { id: 'factionPicker', cancel: ['#closeFactionPickerBtn'], initial: '#factionList .faction-choice-btn' },
  ]);

  /** visibleIds：目前可見的 modal id 集合。回傳最高優先權的 scope 定義，或 null。 */
  function resolveModalScope(visibleIds) {
    const visible = new Set(visibleIds || []);
    return MODAL_SCOPES.find(scope => visible.has(scope.id)) || null;
  }

  /**
   * 方向焦點只停在內容資料（桌面與客廳兩種顯示模式相同）。下列既有控制一律排除，改由專用鍵或 R／SR 操作（滑鼠照常可用）：
   * 手牌內的資源／行動／棄置鈕（整張手牌 X／Y；一般奧援的棄置＝X）、購買卡選擇控制（B）、六個全域分頁（R／SR）、
   * 回合列：結束行動／紅軍能力（Capture）、按鍵提示列、陣營能力發動鈕（PLUS）。描述不明 → 排除（fail-closed）。
   */
  function isDirectionalExcluded(d) {
    if (!d || typeof d !== 'object') return true;
    // helpEntry＝導覽列「Joy-Con 說明」按鈕：只由 R／SR 環聚焦（額外焦點，不是區段），方向鍵不會落在上面。
    return !!(d.handAction || d.cardCheckbox || d.sectionTab || d.turnControl || d.hintBar || d.factionAbility || d.helpEntry);
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
  // detail＝重新開啟目前 map focus 城鎮的說明 popup（唯讀；SL 瀏覽焦點上的 A）。
  const MAP_COMMANDS = Object.freeze(['snapshot', 'focus', 'focusTown', 'clearFocus', 'activate', 'button', 'cancel', 'act', 'zoom', 'detail']);
  // 一律要帶合法 req 的指令（指令與 result 都是）：地圖 Y（act）、ZR 縮放（zoom）與 SL 全域聚焦（focusTown）
  // 只在對上 req 的 ok:true 後才算執行。
  const MAP_REQ_REQUIRED = Object.freeze(['act', 'zoom', 'focusTown']);
  // 客廳模式地圖 Y：目標的既有主要操作 → 執行它的既有按鈕（建立組織／確認移動／瓦解組織）。
  const MAP_ACTS = Object.freeze({ build: 'directBuildBtn', move: 'confirmMoveBtn', dissolve: 'dissolveBtn' });
  const MAP_ACT_BUTTON_IDS = Object.freeze(Object.values(MAP_ACTS));

  // ZR 縮放循環的整數層級範圍；實際範圍＝它與 Leaflet map.getMinZoom()／getMaxZoom() 的交集
  // （戰略地圖沒有設定 minZoom／maxZoom，Leaflet 回傳 0／Infinity；之後地圖若設得更窄，循環跟著 Leaflet）。
  //   min 2：整個遊戲範圍（溫哥華～奧克蘭）在戰略地圖內可見的最遠層級，也是地圖樣式 zoomProgress 的起點；
  //   max 10：陣營標籤開始顯示的層級（leaflet_game_map_logic.js FACTION_LABEL_MIN_ZOOM），最密集的城鎮也能分辨。
  const MAP_ZOOM_CYCLE = Object.freeze({ min: 2, max: 10 });
  // SL 全域地圖聚焦的固定近景層級：9（使用者決定；比 ZR 循環最大層級 10 低一級，與開局根據地視角同級，陣營標籤仍是短標籤）。
  // 與 MAP_ZOOM_CYCLE 互相獨立：之後按 ZR 從 9 放大一級到 10，再一次回到最小層級。
  const MAP_FOCUS_ZOOM = 9;

  /**
   * SL 聚焦要套用的整數層級：固定 MAP_FOCUS_ZOOM，Leaflet maxZoom 較小時取 maxZoom（向下取整，絕不超過）。
   * 不是數字、上限低於下限，或下限高於聚焦層級（無法同時滿足）→ null（fail closed，不動相機）。
   */
  function mapFocusZoom(leafletMin, leafletMax, preferred = MAP_FOCUS_ZOOM) {
    if (![leafletMin, leafletMax, preferred].every(v => typeof v === 'number' && !Number.isNaN(v))) return null;
    if (!Number.isInteger(preferred) || preferred < 0) return null;
    const min = Math.ceil(Math.max(0, leafletMin));
    const zoom = Math.min(preferred, Math.floor(leafletMax));
    if (!Number.isFinite(min) || !Number.isFinite(zoom) || zoom < min) return null;
    return zoom;
  }

  /** Leaflet min／max 與循環範圍的交集（只取整數層級）；不是數字、沒有交集或不足兩級 → null（fail closed）。 */
  function mapZoomBounds(leafletMin, leafletMax, range = MAP_ZOOM_CYCLE) {
    if (typeof leafletMin !== 'number' || typeof leafletMax !== 'number' || Number.isNaN(leafletMin) || Number.isNaN(leafletMax)) return null;
    const min = Math.ceil(Math.max(leafletMin, range.min));
    const max = Math.floor(Math.min(leafletMax, range.max));
    if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) return null;
    return { min, max };
  }

  /**
   * ZR 的下一個層級：min → min+1 → … → max → min（單向循環，每次只前進一級）。已在 max、超出範圍或低於 min → min；
   * 小數層級（滑鼠縮放或 flyTo 中途）前進到下一個整數層級。current 不是有限數或 bounds 不合法 → null。
   */
  function nextMapZoom(current, bounds) {
    if (!bounds || !Number.isInteger(bounds.min) || !Number.isInteger(bounds.max) || bounds.max <= bounds.min) return null;
    if (typeof current !== 'number' || !Number.isFinite(current)) return null;
    const eps = 1e-6;
    if (current < bounds.min - eps || current >= bounds.max - eps) return bounds.min;
    return Math.min(bounds.max, Math.floor(current + eps) + 1);
  }

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
  // 地圖目標的座標是 iframe 內的 Leaflet container 座標，畫面外的目標可以離中心很遠：思想家（無視距離建立）的候選遍布全圖
  // （含沒有陣營標籤的北美城鎮）：SL 聚焦利雅德（MAP_FOCUS_ZOOM 9）時北美目標約 6 萬 px，之後 ZR 放大到循環最大層級 10 約 12 萬 px。
  // 沿用按鈕的 10 萬上限會讓整份 snapshot 作廢、parent 失去全部地圖目標（控制器完全不能操作）。上限＝256px 圖磚在 zoom 22 的世界寬度，只擋 NaN／Infinity 與不可能的值。
  const MAP_POINT_LIMIT = 256 * 2 ** 22;
  function isMapPoint(v) { return typeof v === 'number' && Number.isFinite(v) && Math.abs(v) < MAP_POINT_LIMIT; }
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

  // 目標分組資料（snapshot 選用欄位 groupMeta 的版本）：每個目標帶 canonical 地圖資料的
  // 統治者（ruler，至少 1 個）與陣營區域（camp，即發展空間標籤，可為空）清單。版本不符、缺欄位或格式不合一律整份作廢。
  const MAP_GROUP_META_VERSION = 1;
  // SL 全域聚焦選單的完整 canonical 城鎮清單（snapshot 選用欄位 browseMeta 的版本＋browseTowns）：與 action targets 分離，
  // 每個城鎮同樣帶 ruler／camp。宣告版本卻缺清單、沒宣告卻帶清單、重複城鎮或任一城鎮資料不合 → 整份 snapshot 作廢。
  const MAP_BROWSE_META_VERSION = 1;
  const GROUP_LIMITS = Object.freeze({ ruler: { min: 1, max: 8 }, camp: { min: 0, max: 16 } });

  /**
   * 分組名稱清單（kind＝ruler｜camp）：陣列、數量在上下限內、每項為 1–16 字的字串；重複名稱只算一次（同一份成員資格）。
   * 不合法回傳 null：不過濾不合法項目、不截斷、不補值。
   */
  function sanitizeGroupNames(list, kind) {
    const limit = Object.prototype.hasOwnProperty.call(GROUP_LIMITS, kind) ? GROUP_LIMITS[kind] : null;
    if (!limit || !Array.isArray(list) || list.length < limit.min || list.length > limit.max) return null;
    const out = [];
    for (const name of list) {
      if (!isShortString(name, 16)) return null;
      if (!out.includes(name)) out.push(name);
    }
    return out;
  }

  /**
   * iframe 端：從 canonical 地圖資料（/map-data 的 towns[name]）取出統治者／陣營區域。
   * 任一欄位缺少、不是陣列、數量不合或含不合法名稱 → null（snapshot 因此不宣告 groupMeta，parent 顯示資料不足）。
   */
  function townGroupMeta(raw) {
    if (!raw || typeof raw !== 'object') return null;
    const ruler = sanitizeGroupNames(raw.ruler, 'ruler');
    const camp = sanitizeGroupNames(raw.camp, 'camp');
    return ruler && camp ? { ruler, camp } : null;
  }

  /** parent 端收到的 snapshot：不符 schema 一律回傳 null（視為沒有地圖目標）。 */
  function sanitizeMapSnapshot(data) {
    if (!data || data.type !== 'redline-controller-map-snapshot' || data.v !== MAP_MESSAGE_VERSION) return null;
    if (!MAP_SCOPES.includes(data.scope)) return null;
    if (!Array.isArray(data.targets) || data.targets.length > 400) return null;
    if (!Array.isArray(data.buttons) || data.buttons.length > MAP_BUTTON_IDS.length) return null;
    if (isPresent(data.groupMeta) && data.groupMeta !== MAP_GROUP_META_VERSION) return null;
    if (isPresent(data.browseMeta) && data.browseMeta !== MAP_BROWSE_META_VERSION) return null;
    const groupMeta = data.groupMeta === MAP_GROUP_META_VERSION;
    const browseMeta = data.browseMeta === MAP_BROWSE_META_VERSION;
    if (browseMeta !== Array.isArray(data.browseTowns)) return null;
    if (browseMeta && (data.browseTowns.length < 1 || data.browseTowns.length > 400)) return null;
    if (isPresent(data.req) && !isRequestId(data.req)) return null;
    const targets = [];
    for (const t of data.targets) {
      if (!t || !isShortString(t.town) || !MAP_ROLES.includes(t.role) || !isMapPoint(t.x) || !isMapPoint(t.y)) return null;
      const target = { town: t.town, role: t.role, x: t.x, y: t.y };
      if (t.role === 'move' && !sanitizeMoveMeta(t, target)) return null;
      if (isPresent(t.act)) {
        if (!isActLegalFor(data.scope, t.role, t.act)) return null;
        target.act = t.act;
      }
      if (groupMeta) {
        const ruler = sanitizeGroupNames(t.ruler, 'ruler');
        const camp = sanitizeGroupNames(t.camp, 'camp');
        if (!ruler || !camp) return null;
        target.ruler = ruler;
        target.camp = camp;
      } else if (isPresent(t.ruler) || isPresent(t.camp)) {
        return null; // 沒有宣告版本的分組資料不可信
      }
      targets.push(target);
    }
    const buttons = [];
    for (const b of data.buttons) {
      if (!b || !MAP_BUTTON_IDS.includes(b.id) || !isShortString(b.label, 80) || !isCoord(b.x) || !isCoord(b.y)
        || !isCoord(b.w) || !isCoord(b.h)) return null;
      buttons.push({ id: b.id, label: b.label, x: b.x, y: b.y, w: b.w, h: b.h });
    }
    const browseTowns = [];
    const browseNames = new Set();
    if (browseMeta) {
      for (const t of data.browseTowns) {
        if (!t || !isShortString(t.town) || browseNames.has(t.town)) return null;
        const meta = townGroupMeta(t);
        if (!meta) return null;
        browseNames.add(t.town);
        browseTowns.push({ town: t.town, ruler: meta.ruler, camp: meta.camp });
      }
    }
    const focusTown = data.focusTown === null || data.focusTown === undefined ? null : data.focusTown;
    if (focusTown !== null && !isShortString(focusTown)) return null;
    const selected = isPresent(data.selected) ? data.selected : null;
    if (selected !== null && !isShortString(selected)) return null;
    // detail＝iframe 目前開著標準說明 popup 的城鎮（B 的第一下只關閉它；canCancel 同時為 true）。
    const detail = isPresent(data.detail) ? data.detail : null;
    if (detail !== null && !isShortString(detail)) return null;
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
      canCancel: data.canCancel === true || detail !== null,
      detail,
      selected,
      pending,
      groupMeta: groupMeta ? MAP_GROUP_META_VERSION : null,
      browseMeta: browseMeta ? MAP_BROWSE_META_VERSION : null,
      browseTowns,
      // 回應帶 req 的 snapshot 指令時原樣帶回（聚焦選單只用對上自己 req 的那一份）；一般推送為 null。
      req: isPresent(data.req) ? data.req : null,
    };
  }

  /**
   * snapshot 的地圖目標集合簽章（scope＋每個目標的 role／town；不含隨相機改變的座標）。SL 瀏覽焦點只在簽章不變時保留：
   * 目標改變（例如新的 pending choice 或換人行動）就交回既有規則，把焦點放到地圖目標。沒有 snapshot → null。
   */
  function mapTargetsSig(snap) {
    if (!snap || !Array.isArray(snap.targets)) return null;
    return JSON.stringify([snap.scope, snap.targets.map(t => [t.role, t.town])]);
  }

  // 執行型指令的 request id：parent 產生、iframe 原樣回傳，用來把 result 對應回唯一一次送出。
  function isRequestId(v) { return Number.isSafeInteger(v) && v > 0; }
  // 'popup'＝B 的第一下只關閉了開著的城鎮說明 popup（選取、預備移動與 pending choice 都保留）。
  const MAP_RESULT_VIA = Object.freeze([...MAP_BUTTON_IDS, 'selection', 'popup']);

  function sanitizeMapCommand(data) {
    if (!data || data.v !== MAP_MESSAGE_VERSION || data.type !== 'redline-controller-command') return null;
    if (!MAP_COMMANDS.includes(data.cmd)) return null;
    if (['focus', 'focusTown', 'activate', 'act', 'detail'].includes(data.cmd) && !isShortString(data.town)) return null;
    if (data.cmd === 'button' && !MAP_BUTTON_IDS.includes(data.id)) return null;
    if (data.cmd === 'act' && !MAP_ACT_BUTTON_IDS.includes(data.id)) return null;
    // act／zoom 一律等 correlated ack；沒有合法 req 的 act／zoom 不可執行（parent 會把 req:null 視為 stale）。
    // 桌面模式不帶 req 的 snapshot／focus／clearFocus／activate／button／cancel 行為不變。
    if (MAP_REQ_REQUIRED.includes(data.cmd) && !isRequestId(data.req)) return null;
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
    if (MAP_REQ_REQUIRED.includes(data.cmd) && !isRequestId(data.req)) return null;
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

  // ---------------------------------------------------------------- per-controller binding（bridge v2）

  // bridge v2：每支實體 Joy-Con 有自己的身份（左右＋FTCW UDP 埠＋S2N1 名稱指紋，例如 `L24801-3f2a9c1e`；主埠沒有名稱時的
  // 舊版預設身份為 `R24800-legacy`）。每個分頁（玩家）最多擁有一支，bridge 只送它的 frame。左 Joy-Con 的實體按鍵已在 bridge
  // 正規化成右 Joy-Con 的邏輯位元，這裡與之後的 action routing 只看共用邏輯 layout。
  const BRIDGE_PROTOCOL_VERSION = 2;
  const CONTROLLER_SIDES = Object.freeze(['left', 'right']);
  const CONTROLLER_STATUSES = Object.freeze(['active', 'stale']);
  const CONTROLLER_OWNERS = Object.freeze(['you', 'other']);
  const SIDE_SOURCES = Object.freeze(['name', 'legacy-default']);
  const CLAIM_REQUESTS = Object.freeze(['claim', 'claim-default', 'release']);
  const ROSTER_MAX_CONTROLLERS = 16;
  // 舊版 bridge（只送無型別的 {x, y, buttons}）的相容身份：唯一一支、視為右 Joy-Con。
  const LEGACY_CONTROLLER_ID = 'legacy';

  function isControllerId(v) {
    if (typeof v !== 'string' || v.length > 24) return false;
    const m = /^[LR]([1-9][0-9]{0,4})-(?:[0-9a-f]{8}|legacy)$/.exec(v);
    return !!m && Number(m[1]) <= 65535;
  }

  function sideMatchesId(id, side) { return (id[0] === 'L') === (side === 'left'); }

  /** bridge 的手把清單：不符 schema 一律整份作廢（null）；只有自己擁有的那一支可以是 you。 */
  function sanitizeRoster(data) {
    if (!data || data.type !== 'roster' || data.v !== BRIDGE_PROTOCOL_VERSION || !Array.isArray(data.controllers)) return null;
    if (data.controllers.length > ROSTER_MAX_CONTROLLERS) return null;
    const controllers = [];
    for (const c of data.controllers) {
      if (!c || !isControllerId(c.id) || !CONTROLLER_SIDES.includes(c.side) || !sideMatchesId(c.id, c.side)) return null;
      if (!CONTROLLER_STATUSES.includes(c.status) || controllers.some(x => x.id === c.id)) return null;
      if (isPresent(c.owner) && !CONTROLLER_OWNERS.includes(c.owner)) return null;
      if (isPresent(c.name) && !isShortString(c.name, 64)) return null;
      if (isPresent(c.endpoint) && !isShortString(c.endpoint, 64)) return null;
      if (isPresent(c.sideSource) && !SIDE_SOURCES.includes(c.sideSource)) return null;
      controllers.push({ id: c.id, side: c.side, status: c.status, owner: c.owner ?? null, name: c.name ?? null,
        endpoint: c.endpoint ?? null, sideSource: c.sideSource ?? null });
    }
    const owned = isPresent(data.owned) ? data.owned : null;
    if (owned !== null && !(controllers.find(c => c.id === owned) || {}).owner) return null;
    if (controllers.some(c => (c.owner === 'you') !== (c.id === owned))) return null;
    let lost = null;
    if (isPresent(data.lost)) {
      if (!data.lost || !isControllerId(data.lost.controller) || !isShortString(data.lost.reason, 32)) return null;
      lost = { controller: data.lost.controller, reason: data.lost.reason };
    }
    return { owned, controllers, lost };
  }

  function sanitizeClaimResult(data) {
    if (!data || data.type !== 'claim-result' || data.v !== BRIDGE_PROTOCOL_VERSION || !CLAIM_REQUESTS.includes(data.request)) return null;
    if (typeof data.ok !== 'boolean') return null;
    if (isPresent(data.controller) && !isControllerId(data.controller)) return null;
    if (isPresent(data.reason) && !isShortString(data.reason, 32)) return null;
    return { request: data.request, ok: data.ok, controller: data.controller ?? null, reason: data.reason ?? null };
  }

  /**
   * bridge 訊息分類（compatibility adapter）。mode＝'legacy'（還沒收到 v2 roster）｜'v2'。
   *   無型別 {x, y, buttons} → 只在 legacy 接受，視為舊版 bridge 的唯一一支右 Joy-Con；
   *   roster／claim-result → 分類後交給呼叫端（roster 讓頁面切到 v2）；
   *   v2 frame → 只在 v2 接受，必須有合法 id、與 id 相符的左右、非負整數 epoch。其他一律 null（丟棄）。
   */
  function classifyBridgeMessage(data, mode) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
    if (!Object.prototype.hasOwnProperty.call(data, 'type')) {
      if (mode !== 'legacy') return null;
      const frame = normalizeFrame(data);
      return frame ? { kind: 'frame', controller: LEGACY_CONTROLLER_ID, side: 'right', epoch: 0, frame } : null;
    }
    if (data.v !== BRIDGE_PROTOCOL_VERSION) return null;
    if (data.type === 'roster') {
      const roster = sanitizeRoster(data);
      return roster ? { kind: 'roster', roster } : null;
    }
    if (data.type === 'claim-result') {
      const result = sanitizeClaimResult(data);
      return result ? { kind: 'claim', ...result } : null;
    }
    if (data.type !== 'frame' || mode !== 'v2') return null;
    if (!isControllerId(data.controller) || !CONTROLLER_SIDES.includes(data.side) || !sideMatchesId(data.controller, data.side)) return null;
    if (!Number.isSafeInteger(data.epoch) || data.epoch < 0) return null;
    const frame = normalizeFrame(data);
    return frame ? { kind: 'frame', controller: data.controller, side: data.side, epoch: data.epoch, frame } : null;
  }

  /** 只有本分頁綁定的那一支手把（id 與左右都相符）可以進 reducer；未綁定一律丟棄。 */
  function acceptControllerFrame(binding, msg) {
    if (!binding || !binding.owned || !msg || msg.kind !== 'frame') return false;
    return msg.controller === binding.owned && msg.side === binding.side;
  }

  function frameInputKey(msg) { return `${msg.controller}#${msg.epoch}`; }

  /**
   * 一筆已接受的 frame 進本分頁的 reducer。pad＝{input, key}：換了手把或同一支重新連線（epoch 改變）時先清空，
   * 這一筆只當 baseline（已按住的鍵與已推到底的搖桿都不觸發）。
   */
  function stepControllerInput(pad, msg, now, config) {
    const key = frameInputKey(msg);
    const base = pad && pad.key === key ? pad.input : createInputState();
    const r = reduceFrame(base, msg.frame, now, config);
    return { pad: { input: r.state, key }, actions: r.actions };
  }

  /** 分頁的手把偏好（sessionStorage）：沒有存值＝auto；記住的 id；none＝玩家明確不用。不合法的存值 fail closed 為 none。 */
  function normalizeClaimPref(raw) {
    if (raw === null || raw === undefined) return { mode: 'auto' };
    if (raw && raw.mode === 'auto') return { mode: 'auto' };
    if (raw && raw.mode === 'id' && isControllerId(raw.id)) return { mode: 'id', id: raw.id };
    return { mode: 'none' };
  }

  /**
   * 自動 claim（bridge 仍是最終權威）：已擁有、玩家選了 none 或沒有清單 → 不送。
   * 記住的 id 有訊號且沒人用 → claim 它（不會改拿別支）；auto 在清單中恰好一支有訊號且沒人用時 claim 它。
   * 這保留單手把即拿即用，也讓另一支已登錄但 stale 時不會阻止目前手把。兩支同時可用時仍要求玩家明確選擇。
   */
  function autoClaimDecision(pref, roster) {
    const p = normalizeClaimPref(pref);
    if (!roster || roster.owned || p.mode === 'none') return null;
    if (p.mode === 'id') {
      const c = roster.controllers.find(x => x.id === p.id);
      return c && c.status === 'active' && !c.owner ? { type: 'claim', controller: c.id } : null;
    }
    const available = roster.controllers.filter(c => c.status === 'active' && !c.owner);
    return available.length === 1 ? { type: 'claim', controller: available[0].id } : null;
  }

  /**
   * 起始畫面的導覽手把（只控制開始流程的既有按鈕；不是玩家席位、不存成手把偏好）。roster＝已通過 sanitizeRoster 的清單。
   * 有訊號的手把恰好一支、且沒有其他分頁使用（未被擁有或就是本分頁）→ 它的 id。沒有清單、沒有或超過一支有訊號、
   * 唯一那支被其他分頁使用 → null（fail closed，不猜）。已登錄但 stale 的手把不算（與 autoClaimDecision 相同）。
   */
  function startNavCandidate(roster) {
    if (!roster || !Array.isArray(roster.controllers)) return null;
    const active = roster.controllers.filter(c => c && c.status === 'active');
    if (active.length !== 1) return null;
    const c = active[0];
    return isControllerId(c.id) && (c.owner === null || c.owner === 'you') ? c.id : null;
  }

  /**
   * 起始畫面導覽的 claim 決策。owned＝本分頁目前擁有的手把 id（或 null）。
   * 擁有的不是候選（多支、stale、消失、清單變了）→ release；沒有擁有且有候選 → claim；其餘 null。
   */
  function startNavDecision(roster, owned) {
    const want = startNavCandidate(roster);
    if (owned && owned !== want) return { type: 'release' };
    if (!owned && want) return { type: 'claim', controller: want };
    return null;
  }

  function bridgeHello() { return { type: 'hello', v: BRIDGE_PROTOCOL_VERSION }; }

  const SIDE_LABELS = Object.freeze({ left: '左 Joy-Con', right: '右 Joy-Con' });

  // ---- 玩家可見的手把名稱：只有左右；同側多支時加「目前 roster」內的顯示序號（依埠號、同埠依完整 id 排序）。
  // 永遠不顯示 FTCW UDP 埠、S2N1 名稱（指紋）、endpoint 或 id；identity／claim／binding 一律仍用完整 id。
  // static/hotseat_core.js 的 controllerDisplayNames 是同一規則（它在 <head> 先載入，不依賴這支；node 測試比對兩者）。
  function idPort(id) { return Number(/^[LR](\d+)-/.exec(id)[1]); }

  /** ids → {id: 名稱}。同側只有一支＝「左 Joy-Con」；多支＝「左 Joy-Con 1／2…」。不合法 id 忽略。 */
  function controllerDisplayNames(ids) {
    const unique = [...new Set((Array.isArray(ids) ? ids : []).filter(isControllerId))];
    const out = {};
    for (const [prefix, label] of [['L', SIDE_LABELS.left], ['R', SIDE_LABELS.right]]) {
      const group = unique.filter(id => id[0] === prefix)
        .sort((a, b) => idPort(a) - idPort(b) || (a < b ? -1 : a > b ? 1 : 0));
      group.forEach((id, i) => { out[id] = group.length > 1 ? `${label} ${i + 1}` : label; });
    }
    return out;
  }

  /** 一支手把的玩家名稱；controllers＝目前 roster（沒有或不在其中 → 只回左右）。 */
  function controllerDisplayName(id, controllers) {
    if (id === LEGACY_CONTROLLER_ID) return SIDE_LABELS.right;
    if (!isControllerId(id)) return 'Joy-Con';
    const names = controllerDisplayNames((Array.isArray(controllers) ? controllers : []).map(c => c && c.id));
    return names[id] || (id[0] === 'L' ? SIDE_LABELS.left : SIDE_LABELS.right);
  }

  /** HUD（我的手把、選擇手把）：玩家名稱；controllers＝目前 roster。 */
  function controllerLabel(c, controllers) {
    if (!c) return '';
    if (c.id === LEGACY_CONTROLLER_ID) return `${SIDE_LABELS.right}（舊版 bridge 相容）`;
    const note = c.sideSource === 'legacy-default' ? '（未回報名稱，預設右手）' : '';
    return `${controllerDisplayName(c.id, controllers)}${note}`;
  }

  /** 提示膠囊／客廳狀態列的前綴：本分頁手把的玩家名稱（同側多支時帶序號，分得出是哪一支）。 */
  function bindingBadge(binding, controllers) {
    if (!binding || !binding.owned || !CONTROLLER_SIDES.includes(binding.side)) return '';
    return controllerDisplayName(binding.owned, controllers);
  }

  // 左 Joy-Con 玩家的實體鍵對照（提示文字沿用右 Joy-Con 的邏輯鍵名）。
  const SIDE_KEY_LEGEND = Object.freeze({
    left: '左 Joy-Con：→＝A　↓＝B　↑＝X　←＝Y　L＝R　ZL＝ZR　−＝+　SR＝SL　SL＝SR　按下搖桿＝STICK　Capture＝Capture（沒有 HOME）',
  });
  function sideKeyLegend(side) { return SIDE_KEY_LEGEND[side] || null; }

  const CLAIM_REASON_TEXT = Object.freeze({
    claimed: '這支手把已被其他玩家使用', 'not-active': '這支手把目前沒有訊號', 'unknown-controller': '找不到這支手把',
    'invalid-controller': '手把 ID 不合法', 'no-default': '沒有唯一的右 Joy-Con，請手動選擇', 'already-owned': '已綁定手把',
  });
  const LOST_REASON_TEXT = Object.freeze({
    replaced: '原本的手把已被另一支裝置取代', unidentified: '原本的手把無法辨識左右',
  });
  function claimReasonText(reason) { return CLAIM_REASON_TEXT[reason] || '無法綁定這支手把'; }
  function lostReasonText(reason) { return LOST_REASON_TEXT[reason] || '原本的手把已無法使用'; }

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
    DEFAULT_BRIDGE_URL, DEFAULT_CONFIG, BUTTON_BITS, BUTTON_ALT_BITS, BUTTON_NAMES, BUTTON_ACTIONS, MODAL_SCOPES, FOCUS_MENU_MODAL_ID,
    MAP_MESSAGE_VERSION, MAP_GROUP_META_VERSION, MAP_BROWSE_META_VERSION, MAP_BUTTON_IDS, MAP_COMMANDS, MAP_RESULT_VIA, MAP_ACTS, mapTargetAct, townGroupMeta, sanitizeGroupNames, isRequestId,
    MAP_ZOOM_CYCLE, MAP_FOCUS_ZOOM, MAP_POINT_LIMIT, mapZoomBounds, nextMapZoom, mapFocusZoom, mapTargetsSig,
    decodeButtonBytes, parseButtons, normalizeFrame,
    createInputState, resetInputState, reduceFrame, stickDirection, isStale, bridgeInputGate, bridgeConnected,
    logicalAction, routeAction, FACTION_PICKER_PHASES, factionPickerCommand, factionPickerHint,
    resolveModalScope, isDirectionalExcluded, isFocusableCandidate, buildFocusSet, pickInitial, pickDirectional, cycleIndex,
    isTrustedMessage, sanitizeMapSnapshot, sanitizeMapCommand, sanitizeMapResult, buildMapSnapshotModel,
    validateBridgeUrl, normalizeSettings, mixedContentRisk, reconnectDelayMs,
    BRIDGE_PROTOCOL_VERSION, LEGACY_CONTROLLER_ID, isControllerId, sanitizeRoster, sanitizeClaimResult, classifyBridgeMessage,
    acceptControllerFrame, frameInputKey, stepControllerInput, normalizeClaimPref, autoClaimDecision, startNavCandidate, startNavDecision, bridgeHello,
    controllerDisplayNames, controllerDisplayName, controllerLabel, bindingBadge, sideKeyLegend, claimReasonText, lostReasonText,
  };
});
