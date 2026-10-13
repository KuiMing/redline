/*
 * REDLINE 客廳大螢幕模式（living-room）— 純邏輯，無 DOM 依賴，可在 node 直接測試。
 *
 * 只負責導航語意（方向鍵只在內容資料間；六個全域區段只由 R／SR 循環）、專用快捷鍵的路由、
 * 按鍵提示列的聚合規則、防誤觸閘門與地圖兩段式清單模型。這裡不含任何遊戲規則：
 * 快捷鍵只描述「要鏡射哪一個既有控制」，是否可用由呼叫端讀既有 DOM／iframe 權威 snapshot 當下重驗。
 */
(function (root, factory) {
  const isNode = typeof module === 'object' && module.exports;
  const core = isNode ? require('./controller_core.js') : root.RedlineControllerCore;
  const api = factory(core);
  if (isNode) module.exports = api;
  else root.RedlineLivingRoomCore = api;
})(typeof self !== 'undefined' ? self : this, function (Core) {
  'use strict';

  // ---------------------------------------------------------------- display mode

  const DISPLAY_STORAGE_KEY = 'redline.display.v1';
  const DISPLAY_MODES = Object.freeze(['desktop', 'living-room']);
  // title-safe：舞台等比縮放後再留 5% 邊界（左右上下各 5%），與解析度無關。
  const SAFE_AREA_SCALE = 0.9;

  function normalizeDisplayMode(value) {
    return value === 'living-room' ? 'living-room' : 'desktop';
  }

  /** URL `?display=` 合法時優先並寫回儲存（kiosk 書籤）；不合法或沒有時用儲存值；預設桌面。 */
  function resolveDisplayMode(search, stored) {
    let fromUrl = null;
    try {
      const params = new URLSearchParams(search || '');
      if (params.has('display')) fromUrl = params.get('display');
    } catch { fromUrl = null; }
    if (fromUrl !== null && DISPLAY_MODES.includes(fromUrl)) return { mode: fromUrl, persist: true };
    return { mode: normalizeDisplayMode(stored), persist: false };
  }

  // ---------------------------------------------------------------- logical actions

  // 只在客廳模式綁定：PLUS＝陣營能力、CAPTURE＝結束行動／步驟（危險確認）、STICK（按下搖桿）＝下一個內容區。
  // SL＝聚焦選單、ZR＝戰略地圖縮放循環（兩者與桌面模式相同）。
  const BUTTON_ACTIONS = Object.freeze({
    A: 'confirm', B: 'cancel', X: 'focusTurnBar', Y: 'toggleHelp',
    R: 'nextSection', SR: 'prevSection', PLUS: 'factionAbility', ZR: 'mapZoom', CAPTURE: 'endStep', STICK: 'nextZone',
    SL: 'focusMenu',
  });

  /** HOME 仍不綁定。 */
  function logicalAction(action) {
    if (!action) return null;
    if (action.type === 'nav') return { name: 'move', dir: action.dir };
    const name = BUTTON_ACTIONS[action.button];
    return name ? { name } : null;
  }

  // ---------------------------------------------------------------- router

  /**
   * 客廳模式 router（只處理 page／map scope；modal 一律交回既有 routeAction）。
   * ctx: {
   *   scopeKind: 'page'|'map', view: 'command'|'map'|..., layer: 'zone'|'item', zone: string|null,
   *   choiceLock: boolean,      // 有必選地圖目標（pending choice 的地圖 highlight）
   *   locked: boolean,          // 地圖 scope 且 choiceLock：B 只走既有取消
   *   mapCanCancel: boolean,    // iframe snapshot 回報有可取消的既有流程
   *   item: null | { card: {zone, hasToggle, hasDiscard}|null, mapRow: boolean },
   * }
   * 全域鍵（R/SR、Capture、PLUS、STICK、SL、ZR）與焦點無關，任何層都先處理；其餘依區域層／內容層。
   * ZR 只在戰略地圖（map scope 且分頁＝戰略地圖）縮放，必選地圖目標時也可用；其他分頁一律 null（不回區域層、不切分頁）。
   */
  function routeLivingRoom(ctx, logical) {
    if (!logical || !ctx) return null;
    const name = logical.name;
    if (name === 'focusMenu') return { cmd: 'focusMenu' }; // 只移焦點；必選地圖目標時也可用（選定後回到戰略地圖）
    if (name === 'mapZoom') return ctx.scopeKind === 'map' && ctx.view === 'map' ? { cmd: 'mapZoom' } : null;
    if (name === 'nextSection' || name === 'prevSection') {
      if (ctx.choiceLock && ctx.view === 'map') return null; // 必選地圖目標：留在地圖
      return { cmd: 'section', step: name === 'nextSection' ? 1 : -1 };
    }
    if (name === 'endStep') return { cmd: 'endStep' };
    if (name === 'factionAbility') return { cmd: 'factionAbility' };
    if (name === 'nextZone') return { cmd: 'zoneCycle', step: 1 };

    if (ctx.layer !== 'item') {
      switch (name) {
        case 'move': return ctx.zone ? { cmd: 'zoneMove', dir: logical.dir } : null;
        case 'confirm': return ctx.zone ? { cmd: 'enterZone' } : null;
        case 'toggleHelp': return { cmd: 'toggleHelp' };
        default: return null; // B、X 在區域層不做事
      }
    }

    const item = ctx.item || null;
    if (name === 'move') return { cmd: 'itemMove', dir: logical.dir };
    const card = item && item.card;
    if (card) {
      // 只有一個客廳模式專屬語意：可棄置手牌 B＝既有棄置（危險確認）。
      if (card.zone === 'hand' && name === 'cancel' && card.hasDiscard) return { cmd: 'cardDiscard' };
      // 其餘（A 查看、購買卡 B 勾選／X no-op／Y 購買所選、手牌 X 資源／Y 行動）與桌面 controller_core.routeAction 完全相同。
      return Core.routeAction(
        { scopeKind: 'page', hasFocus: true, card: { zone: card.zone, hasToggle: !!card.hasToggle }, cancelAvailable: false, sectionsLocked: false },
        logical,
      );
    }
    if (item && item.mapRow) {
      switch (name) {
        case 'confirm': return { cmd: 'mapPick' };
        case 'toggleHelp': return { cmd: 'mapAct' };
        case 'cancel':
          if (ctx.mapCanCancel) return { cmd: 'mapCancel' };
          return ctx.locked ? null : { cmd: 'toZoneLayer' };
        default: return null;
      }
    }
    switch (name) {
      case 'confirm':
        if (!item) return null;
        return { cmd: 'activate' };
      case 'cancel':
        if (ctx.zone === 'maplist' && ctx.mapCanCancel) return { cmd: 'mapCancel' };
        return ctx.locked ? null : { cmd: 'toZoneLayer' };
      case 'toggleHelp': return item ? { cmd: 'toggleHelp' } : null;
      default: return null;
    }
  }

  // ---------------------------------------------------------------- input guard

  const DEFAULT_GUARD_CONFIG = Object.freeze({
    processingTimeoutMs: 1500, redrawCooldownMs: 300, activationCooldownMs: 250, mapAckTimeoutMs: 1000,
  });
  // 會送出（或可能送出）遊戲動作、或開啟送出用確認單的指令：處理中鎖期間一律不執行。
  const PROCESSING_GATED = Object.freeze(new Set([
    'activate', 'cardMode', 'cardToggle', 'cardDiscard', 'cardBuy', 'mapPick', 'mapAct', 'mapCancel', 'endStep', 'factionAbility',
  ]));
  // 與焦點有關的 A／B／X／Y 類指令：非使用者造成的焦點變更（重繪、分頁切換、STICK 跳區）之後短時間內忽略。
  // 全域的 Capture／PLUS 不依賴焦點，不受此冷卻影響。
  // focusMenuPick＝聚焦選單內選定一個選項（選單在游標下刷新後 300ms 內忽略）。
  const COOLDOWN_GATED = Object.freeze(new Set([
    'activate', 'cardMode', 'cardToggle', 'cardPreview', 'cardDiscard', 'cardBuy', 'enterZone', 'mapPick', 'mapAct', 'focusMenuPick',
  ]));
  // 執行型按鍵之後 250ms 內不再接受下一個執行型按鍵：防止開啟 modal（購買確認、卡面預覽、危險確認）、
  // 地圖選取／取消或卡牌勾選的那一下連按落到新出現的按鈕上，或把剛勾的 checkbox 又取消。
  // modalConfirm＝客廳模式下 modal 內的 A。只延後輸入、不改變任何遊戲語意；
  // 方向移動、R/SR、STICK、回區域層與 modal 內的 B（取消／返回）不受影響。
  // focusMenu（SL 開啟聚焦選單）／focusMenuPick（選定選項）只移焦點，不受處理中鎖限制，但同樣等待地圖確認與執行冷卻。
  const ACTIVATION_GATED = Object.freeze(new Set([
    'activate', 'cardMode', 'cardToggle', 'cardPreview', 'cardDiscard', 'cardBuy', 'enterZone',
    'mapPick', 'mapAct', 'mapCancel', 'modalConfirm', 'endStep', 'factionAbility', 'focusMenu', 'focusMenuPick',
  ]));
  // 只改地圖視角的 iframe 指令（ZR 縮放）：不受處理中鎖、重繪冷卻與執行冷卻限制（連按時每一下都前進一級），
  // 但與執行型指令共用「同時只有一筆地圖等待」，不會覆蓋等待中的其他請求。確認成功仍記錄執行冷卻（擋下緊接的 A／Y 等）。
  const MAP_VIEW_COMMANDS = Object.freeze(new Set(['mapZoom']));

  function createGuard() { return { lockedAt: null, lockedToken: null, redrawAt: null, activatedAt: null, mapRequest: null }; }

  /** 執行型指令實際被接受後記錄時間；下一個執行型指令需間隔 activationCooldownMs。 */
  function noteActivation(guard, now) { return { ...(guard || createGuard()), activatedAt: now }; }

  /** token：呼叫端「最新權威 state」的序號；state 換了就解鎖。 */
  function lockProcessing(guard, now, token) { return { ...guard, lockedAt: now, lockedToken: token }; }

  function noteRedraw(guard, now) { return { ...guard, redrawAt: now }; }

  function processingActive(guard, now, token, config) {
    const cfg = { ...DEFAULT_GUARD_CONFIG, ...config };
    if (!guard || guard.lockedAt === null) return false;
    if (token !== guard.lockedToken) return false;
    return now - guard.lockedAt < cfg.processingTimeoutMs;
  }

  // ---------------------------------------------------------------- map iframe acknowledgment
  // 地圖 iframe 的執行型指令（Y 地圖操作、選取城鎮、取消）只有在 iframe 以同一個 req 回覆 ok:true
  // （執行前已用權威資料重驗）時才算執行；送出後到回覆前為「等待確認」，不記錄冷卻、不上處理中鎖。
  // ok:false、逾時、沒有 iframe、對不上的 req（過期或偽造）一律 fail closed，不污染冷卻與處理中鎖。

  /**
   * 送出成功後登記唯一一筆等待中的請求。lock：成功後上處理中鎖；lockVia：iframe 回報走該控制時才上鎖；
   * noActivation：確認成功也不記錄 250ms 執行冷卻（SL 聚焦選單的 snapshot 請求：真的開啟／移焦點後才由呼叫端記錄）。
   */
  function beginMapRequest(guard, now, req, meta) {
    const m = meta || {};
    return {
      ...(guard || createGuard()),
      mapRequest: { req, cmd: m.cmd || null, at: now, lock: m.lock === true, lockVia: m.lockVia || null, noActivation: m.noActivation === true },
    };
  }

  function mapRequestExpired(request, now, config) {
    const cfg = { ...DEFAULT_GUARD_CONFIG, ...config };
    return !!request && now - request.at >= cfg.mapAckTimeoutMs;
  }

  /** 逾時就清掉等待中的請求（不記錄冷卻、不上鎖）。回傳 {guard, expired: 被清掉的請求或 null}。 */
  function expireMapRequest(guard, now, config) {
    const g = guard || createGuard();
    if (!mapRequestExpired(g.mapRequest, now, config)) return { guard: g, expired: null };
    return { guard: { ...g, mapRequest: null }, expired: g.mapRequest };
  }

  /**
   * 處理一筆（已 sanitize 的）iframe 回覆。outcome：
   *   success — req 對上、未逾時、ok:true → 記錄 250ms 執行冷卻（noActivation 的請求除外）；lock 表示呼叫端要上處理中鎖。
   *   failed  — req 對上、ok:false → 清掉等待，不記錄冷卻、不上鎖（下一個合法操作立即可用）。
   *   timeout — req 對上但已逾時 → 清掉等待，視為未執行。
   *   stale   — 沒有等待中的請求、沒有 req、req 或 cmd 對不上 → 完全忽略。
   */
  function settleMapResult(guard, now, result, config) {
    const g = guard || createGuard();
    const pending = g.mapRequest;
    if (!result || result.req === null || result.req === undefined || !pending
      || result.req !== pending.req || (pending.cmd !== null && result.cmd !== pending.cmd)) {
      return { guard: g, outcome: 'stale', lock: false, request: null };
    }
    const cleared = { ...g, mapRequest: null };
    if (mapRequestExpired(pending, now, config)) return { guard: cleared, outcome: 'timeout', lock: false, request: pending };
    if (result.ok !== true) return { guard: cleared, outcome: 'failed', lock: false, request: pending };
    const lock = pending.lock || (pending.lockVia !== null && result.via === pending.lockVia);
    return { guard: pending.noActivation ? cleared : noteActivation(cleared, now), outcome: 'success', lock, request: pending };
  }

  /**
   * ZR 地圖縮放的前置條件（送出前與 iframe 確認到達時都重驗）。s = {connected（啟用＋connected＋socket 開著）, gameShown,
   * scopeKind, view, frameReady（戰略地圖 iframe 仍掛在頁面上、可見且有 contentWindow）}。
   * 縮放與焦點無關：不需要已放過焦點（戰略地圖上第一下 ZR 就執行）。回傳阻擋原因或 null；任何一項不明一律視為不符（fail closed）。
   */
  function mapZoomBlocker(s) {
    if (!s || s.connected !== true) return 'disconnected';
    if (s.gameShown !== true) return 'no-game';
    if (s.scopeKind === 'modal') return 'modal';
    if (s.scopeKind !== 'map' || s.view !== 'map') return 'not-map';
    if (s.frameReady !== true) return 'no-frame';
    return null;
  }

  /** 回傳 {allowed, reason, guard}；guard 可能被更新（逾時或 state 抵達後解鎖、地圖請求逾時）。 */
  function gate(guard, now, token, cmd, config) {
    const cfg = { ...DEFAULT_GUARD_CONFIG, ...config };
    let next = expireMapRequest(guard || createGuard(), now, cfg).guard;
    if (next.lockedAt !== null && !processingActive(next, now, token, cfg)) next = { ...next, lockedAt: null, lockedToken: null };
    if (PROCESSING_GATED.has(cmd) && next.lockedAt !== null) return { allowed: false, reason: 'processing', guard: next };
    // 地圖指令等待 iframe 確認期間不送出第二個執行型或地圖視角指令（避免同一下連按重送、不覆蓋等待中的請求）；確認或逾時後立即解除。
    if ((ACTIVATION_GATED.has(cmd) || MAP_VIEW_COMMANDS.has(cmd)) && next.mapRequest) return { allowed: false, reason: 'map-pending', guard: next };
    if (COOLDOWN_GATED.has(cmd) && next.redrawAt !== null && now - next.redrawAt < cfg.redrawCooldownMs) {
      return { allowed: false, reason: 'redraw-cooldown', guard: next };
    }
    if (ACTIVATION_GATED.has(cmd) && next.activatedAt !== null && now - next.activatedAt < cfg.activationCooldownMs) {
      return { allowed: false, reason: 'activation-cooldown', guard: next };
    }
    return { allowed: true, reason: null, guard: next };
  }

  // ---------------------------------------------------------------- directional focus set / zones

  // 方向焦點排除規則與桌面模式共用同一個判斷（Core.isDirectionalExcluded）：手牌內按鈕、卡牌勾選框、六個全域分頁、
  // 回合列、按鍵提示列、陣營能力發動鈕一律不是方向焦點；描述不明 → 排除（fail-closed）。
  const isDirectionalExcluded = Core.isDirectionalExcluded;

  // 每個分頁可用的內容區（依序也是 STICK 循環順序）。舊的玩家狀態列／地圖入口／動作列都不再是方向焦點。
  const CONTENT_ZONES = Object.freeze({
    command: Object.freeze(['static', 'random', 'faction', 'hand', 'activity']),
    map: Object.freeze(['maplist']),
    other: Object.freeze(['view']),
  });

  /** 必選地圖目標時，戰略地圖以外的分頁沒有任何內容區（只剩 R／SR 回地圖）。 */
  function contentZonesFor(view, opts) {
    const o = opts || {};
    const ids = CONTENT_ZONES[view] || CONTENT_ZONES.other;
    if (o.choiceLock && view !== 'map') return [];
    return [...ids];
  }

  /**
   * 重繪後的內容層焦點：同 key 仍在 → 原位；key 消失 → 同索引（夾在範圍內）；
   * 夾到的項目在 avoid 內或區域已空 → -1（回該區域的區域層）。
   */
  function reconcileIndex(keys, prevKey, prevIndex, avoid) {
    if (!keys || !keys.length) return -1;
    const same = prevKey === null || prevKey === undefined ? -1 : keys.indexOf(prevKey);
    if (same >= 0) return same;
    const base = Number.isInteger(prevIndex) ? prevIndex : 0;
    const index = Math.max(0, Math.min(keys.length - 1, base));
    if (avoid && avoid.has(keys[index])) return -1;
    return index;
  }

  /** 由項目 rect 推算每列欄數（與第一個項目同一列的數量）；單列水平捲動時＝全部數量。 */
  function gridColumns(rects) {
    if (!rects || !rects.length) return 0;
    const top = rects[0].top;
    let count = 0;
    for (const r of rects) {
      if (Math.abs(r.top - top) <= 4) count += 1;
      else break;
    }
    return Math.max(1, count);
  }

  /** 語意格狀導航：左右在列內、上下換列（保持欄位）；到邊界停住，不循環、不跳出區域。 */
  function gridMove(count, cols, index, dir) {
    if (!count || count <= 0) return -1;
    const c = Math.max(1, Math.min(cols || count, count));
    let i = Math.max(0, Math.min(count - 1, Number.isInteger(index) ? index : 0));
    if (dir === 'left') { if (i % c > 0) i -= 1; }
    else if (dir === 'right') { if (i % c < c - 1 && i + 1 < count) i += 1; }
    else if (dir === 'up') { if (i - c >= 0) i -= c; }
    else if (dir === 'down') {
      if (i + c < count) i += c;
      else if (Math.floor(i / c) < Math.floor((count - 1) / c)) i = count - 1;
    }
    return i;
  }

  /** 線性清單（地圖目標清單）：上下移動，左右不動；到邊界停住。 */
  function listMove(count, index, dir) {
    if (!count || count <= 0) return -1;
    const i = Math.max(0, Math.min(count - 1, Number.isInteger(index) ? index : 0));
    if (dir === 'up') return Math.max(0, i - 1);
    if (dir === 'down') return Math.min(count - 1, i + 1);
    return i;
  }

  function intervalGap(a1, a2, b1, b2) { return Math.max(0, Math.max(a1, b1) - Math.min(a2, b2)); }

  /**
   * 區域層方向移動：區域是少數大矩形，用「邊緣距離＋交錯軸是否重疊」挑選，
   * 例如橫跨整列的手牌往上會到正上方的購買區。該方向沒有區域就不動；同分時取中心較近者，結果是確定的。
   */
  function pickZone(zones, currentId, dir) {
    const list = zones || [];
    const current = list.find(z => z.id === currentId);
    if (!current) return list.length ? list[0].id : null;
    const c = current.rect;
    const horizontal = dir === 'left' || dir === 'right';
    let best = null;
    let bestScore = Infinity;
    let bestTie = Infinity;
    for (const z of list) {
      if (z.id === currentId) continue;
      const r = z.rect;
      let gap;
      if (dir === 'up') gap = c.top - r.bottom;
      else if (dir === 'down') gap = r.top - c.bottom;
      else if (dir === 'left') gap = c.left - r.right;
      else gap = r.left - c.right;
      if (gap < -4) continue; // 不在該方向（允許少量重疊誤差）
      const ortho = horizontal ? intervalGap(c.top, c.bottom, r.top, r.bottom) : intervalGap(c.left, c.right, r.left, r.right);
      const score = Math.max(0, gap) + ortho * 3;
      const tie = horizontal
        ? Math.abs((r.top + r.bottom) / 2 - (c.top + c.bottom) / 2)
        : Math.abs((r.left + r.right) / 2 - (c.left + c.right) / 2);
      if (score < bestScore || (score === bestScore && tie < bestTie)) { best = z; bestScore = score; bestTie = tie; }
    }
    return best ? best.id : currentId;
  }

  /** STICK：在可用內容區之間循環（找不到目前區域時從第一個開始）。 */
  function cycleZone(ids, currentId, step) {
    if (!ids || !ids.length) return null;
    const index = ids.indexOf(currentId);
    if (index < 0) return ids[step < 0 ? ids.length - 1 : 0];
    return ids[Core.cycleIndex(ids.length, index, step)];
  }

  /** 預設區域：偏好（記憶）→ 手牌 → 第一個可用區域。 */
  function resolveZone(ids, preferred) {
    const usable = ids || [];
    if (preferred && usable.includes(preferred)) return preferred;
    if (usable.includes('hand')) return 'hand';
    return usable[0] || null;
  }

  // ---------------------------------------------------------------- global sections (R / SR)

  // 六個全域區段（分頁列順序）。只有 R／SR 會選取它們；方向鍵永遠不會落在上面。
  const SECTION_LABELS = Object.freeze({
    command: '指揮中心', map: '戰略地圖', log: '戰況紀錄', myFaction: '我的陣營', event: '事件卡', era: '時代關卡',
  });
  const VIEW_SECTIONS = Object.freeze(['command', 'map', 'log', 'myFaction']);
  // 由 R／SR 開啟的唯讀說明 modal：在其中按 R／SR 會以既有關閉控制收起並前往下一個區段。其他 modal 一律維持 scope lock。
  const SECTION_MODALS = Object.freeze(new Map([['eventRevealModal', 'event'], ['eraAchievementModal', 'era']]));

  /** stop key：'view:<分頁>'、'event'、'era:<時代 id>'；其他任何字串都不是區段。 */
  function sectionOfKey(key) {
    if (typeof key !== 'string') return null;
    if (key === 'event') return 'event';
    if (key.startsWith('view:')) {
      const view = key.slice(5);
      return VIEW_SECTIONS.includes(view) ? view : null;
    }
    if (key.startsWith('era:') && key.length > 4) return 'era';
    return null;
  }

  /**
   * R／SR：stops＝分頁列順序的 [{key, usable}]（呼叫端讀既有分頁是否可見、啟用）。
   * 跳過不可用與非區段的項目、循環；只剩目前一個可用時回傳 null。
   * opts.choiceLock：必選地圖目標時只提供「戰略地圖」（已在地圖則 null）。
   */
  function stepSection(stops, currentKey, step, opts) {
    const o = opts || {};
    const list = (stops || []).filter(s => s && sectionOfKey(s.key));
    if (o.choiceLock) {
      if (o.view === 'map') return null;
      return list.some(s => s.key === 'view:map' && s.usable) ? 'view:map' : null;
    }
    if (!list.length) return null;
    const dir = step < 0 ? -1 : 1;
    let index = list.findIndex(s => s.key === currentKey);
    if (index < 0) index = dir > 0 ? -1 : list.length;
    for (let i = 1; i <= list.length; i += 1) {
      const candidate = list[((index + dir * i) % list.length + list.length) % list.length];
      if (candidate.key === currentKey) break;
      if (candidate.usable) return candidate.key;
    }
    return null;
  }

  // ---------------------------------------------------------------- dedicated-key hints（不可聚焦）

  // 提示列只鏡射「目前就能用專用鍵執行」的既有、可見、啟用控制（SL 聚焦選單只在有可分組的合法建立目標時出現）；
  // 排序 Y → X → B → SL → PLUS → Capture（危險最右）。
  const HINTS = Object.freeze({
    mapAct: { key: 'Y', danger: false },
    cardBuy: { key: 'Y', danger: false },
    cardAction: { key: 'Y', danger: false },
    cardResource: { key: 'X', danger: false },
    cardToggle: { key: 'B', danger: false },
    cardDiscard: { key: 'B', danger: true },
    mapCancel: { key: 'B', danger: false },
    focusMenu: { key: 'SL', danger: false },
    factionAbility: { key: '+', danger: false },
    endStep: { key: 'Capture', danger: true },
  });
  const HINT_ORDER = Object.freeze(Object.keys(HINTS));

  /** sources: [{id, label, visible, disabled, ariaDisabled, inert}]（呼叫端讀既有控制）。 */
  function buildKeyHints(sources) {
    const seen = new Set();
    const hints = [];
    for (const s of sources || []) {
      if (!s || !HINTS[s.id] || seen.has(s.id)) continue;
      if (s.visible !== true || s.disabled || s.ariaDisabled || s.inert) continue;
      const label = typeof s.label === 'string' ? s.label.replace(/\s+/g, ' ').trim().slice(0, 40) : '';
      if (!label) continue;
      seen.add(s.id);
      hints.push({ id: s.id, key: HINTS[s.id].key, label, danger: HINTS[s.id].danger });
    }
    return hints.sort((a, b) => HINT_ORDER.indexOf(a.id) - HINT_ORDER.indexOf(b.id));
  }

  /** PLUS：候選陣營能力控制中恰好一個可用才執行；沒有或多於一個（不明確）一律 fail closed。 */
  function pickFactionAbility(candidates) {
    if (!Array.isArray(candidates)) return -1;
    const usable = candidates.map((c, i) => (c && c.usable ? i : -1)).filter(i => i >= 0);
    return usable.length === 1 ? usable[0] : -1;
  }

  /**
   * 購買卡 Y：焦點卡必須是有效的已勾選卡（先用 B 勾選、勾選框仍可見可用，即仍在既有購買選取內且可購買），
   * 且既有「購買所選」按鈕可用；否則回傳阻擋原因。Y 本身永遠不勾選任何卡。selectable 不明視為不可（fail closed）。
   */
  function purchaseBuyBlocker(s) {
    if (!s || !s.cardShown || s.selectable !== true) return 'card-gone';
    if (!s.checked) return 'not-selected';
    if (!s.buyUsable) return 'buy-unavailable';
    return null;
  }

  /** 手牌 B：該卡第一顆按鈕標示為「棄置」的既有控制必須恰好一顆（資源鈕永遠不是棄置）。 */
  function discardControlIndex(labels) {
    if (!Array.isArray(labels)) return -1;
    const hits = labels.map((t, i) => (typeof t === 'string' && t.trim() === '棄置' ? i : -1)).filter(i => i >= 0);
    return hits.length === 1 ? hits[0] : -1;
  }

  // ---------------------------------------------------------------- map two-stage list

  const zhCollator = (() => {
    try { return new Intl.Collator('zh-Hant'); } catch { return null; }
  })();
  function byTown(a, b) {
    return zhCollator ? zhCollator.compare(a.town, b.town) : (a.town < b.town ? -1 : a.town > b.town ? 1 : 0);
  }
  function actOf(t) { return Object.prototype.hasOwnProperty.call(Core.MAP_ACTS, t.act) ? t.act : null; }

  /**
   * 由 sanitize 過的 snapshot 建立控制器清單：
   *   choice      → pending choice 目標（伺服器候選）
   *   source      → 可行動來源城鎮
   *   destination → 已選來源的伺服器合法目的地（依消耗、道路先於鐵路、名稱排序）
   * 每列帶 iframe 計算的 act（Y 操作）；缺 snapshot、scope none 或沒有目標 → stage 'none'（fail-closed）。
   */
  function buildMapList(snap) {
    const empty = { stage: 'none', rows: [], selected: null, pending: null, canCancel: false };
    if (!snap || !Array.isArray(snap.targets)) return empty;
    const canCancel = snap.canCancel === true;
    const selected = typeof snap.selected === 'string' ? snap.selected : null;
    if (snap.scope === 'choice') {
      const rows = snap.targets.filter(t => t.role === 'choice').map(t => ({ town: t.town, role: 'choice', act: actOf(t) })).sort(byTown);
      if (!rows.length) return { ...empty, canCancel };
      return { stage: 'choice', rows, selected: rows.some(r => r.town === selected) ? selected : null, pending: null, canCancel };
    }
    if (snap.scope === 'move') {
      const moves = snap.targets.filter(t => t.role === 'move');
      if (selected && moves.length) {
        const rows = moves
          .map(t => ({ town: t.town, role: 'move', act: actOf(t), mode: t.mode === 'rail' ? 'rail' : t.mode === 'road' ? 'road' : null, cost: Number.isInteger(t.cost) ? t.cost : null }))
          .sort((a, b) => ((a.cost ?? 99) - (b.cost ?? 99)) || ((a.mode === 'rail') - (b.mode === 'rail')) || byTown(a, b));
        const p = snap.pending;
        const pending = p && p.from === selected && rows.some(r => r.town === p.to)
          ? { from: p.from, to: p.to, mode: p.mode ?? null, cost: p.cost ?? null } : null;
        return { stage: 'destination', rows, selected, pending, canCancel };
      }
      const rows = snap.targets.filter(t => t.role === 'origin').map(t => ({ town: t.town, role: 'origin', act: actOf(t) })).sort(byTown);
      if (!rows.length) return { ...empty, canCancel };
      return { stage: 'source', rows, selected: null, pending: null, canCancel };
    }
    return { ...empty, canCancel };
  }

  /**
   * 清單「換了一份」的判斷 key：stage 改變（來源 ↔ 目的地、有／無目標）或目的地清單換了來源才算，焦點此時回第一列。
   * pending choice 的 A 選取只改 selected、列不變：不算換段，焦點留在剛選的那一列（Y 才會作用在它）。
   */
  function mapStageKey(list) {
    const l = list || {};
    const stage = l.stage || 'none';
    return `${stage}|${stage === 'destination' ? l.selected || '' : ''}`;
  }

  /** 地圖 Y：清單列的 act → 要按的既有按鈕與提示文字；沒有 act → null（fail-closed）。 */
  function mapActFor(row, list) {
    if (!row || typeof row.town !== 'string') return null;
    const act = actOf(row);
    if (!act) return null;
    const id = Core.MAP_ACTS[act];
    if (act === 'build') return { id, label: `建立組織 ${row.town}` };
    if (act === 'dissolve') return { id, label: `瓦解組織 ${row.town}` };
    const from = list && list.selected ? list.selected : '';
    return { id, label: from ? `移動 ${from}→${row.town}` : `移動 →${row.town}` };
  }

  function moveModeLabel(mode) { return mode === 'rail' ? '鐵路' : mode === 'road' ? '道路' : ''; }

  // ---------------------------------------------------------------- SL focus menu（統治者／陣營區域 → 合法地圖城鎮）

  // fail-closed 的短原因（兩種顯示模式的提示膠囊／提示列狀態欄）。
  const FOCUS_MENU_REASONS = Object.freeze({
    'no-snapshot': '地圖尚未載入：先用 R 切到戰略地圖',
    'no-targets': '目前沒有可聚焦的地圖目標',
    'no-group-data': '地圖資料不足，無法分組',
    stale: '地圖沒有回應，請再試一次',
    gone: '此範圍已沒有合法目標',
    changed: '地圖狀態已改變，請重新選擇',
    'no-game': '遊戲尚未開始',
    'map-unavailable': '戰略地圖目前不可用',
  });
  const FOCUS_MENU_SECTIONS = Object.freeze([['ruler', '統治者'], ['camp', '陣營區域']]);

  function focusMenuFail(reason) { return { ok: false, reason, stage: 'none', selected: null, total: 0, sections: [] }; }

  /**
   * SL 聚焦選單模型（純函式）。候選＝目前 pending choice 的合法「建立組織」目標（地圖清單 choice 段，每列 act＝build，
   * 之後 Y＝directBuildBtn）；移動來源、移動目的地、瓦解或沒有 act 的 choice 都不是候選（no-targets）。
   * 分組資料只取 snapshot 內 iframe 由 canonical 地圖資料帶來的 ruler／camp（groupMeta 版本必須相符）；
   * 任一候選缺少分組資料或格式不合 → 整份 fail closed（no-group-data），不過濾、不補值。
   * 每區只列出至少含 1 個合法目標的項目；城鎮與成員資格都去重。分組依城鎮數多→少、同數依名稱；分組內城鎮依清單順序。
   * 缺 snapshot、沒有合法建立目標、沒有版本化分組資料或分不出任何組 → {ok:false, reason}（fail closed）。
   */
  function buildFocusMenu(snap) {
    if (!snap || typeof snap !== 'object') return focusMenuFail('no-snapshot');
    const list = buildMapList(snap);
    if (list.stage !== 'choice' || !list.rows.length || !list.rows.every(r => r.act === 'build')) return focusMenuFail('no-targets');
    if (snap.groupMeta !== Core.MAP_GROUP_META_VERSION) return focusMenuFail('no-group-data');
    const order = [];
    for (const row of list.rows) if (!order.includes(row.town)) order.push(row.town);
    const meta = new Map(order.map(town => [town, { ruler: new Set(), camp: new Set() }]));
    for (const t of snap.targets) {
      const m = t && t.role === 'choice' ? meta.get(t.town) : null;
      if (!m) continue; // 不是 pending choice 目標（例如 choice scope 裡的來源）
      for (const [kind] of FOCUS_MENU_SECTIONS) {
        const names = Core.sanitizeGroupNames(t[kind], kind);
        if (!names) return focusMenuFail('no-group-data');
        for (const name of names) m[kind].add(name);
      }
    }
    const sections = FOCUS_MENU_SECTIONS.map(([kind, label]) => {
      const groups = new Map();
      for (const town of order) {
        for (const name of meta.get(town)[kind]) {
          if (!groups.has(name)) groups.set(name, []);
          groups.get(name).push(town);
        }
      }
      const items = [...groups].map(([name, towns]) => ({
        key: `${kind}:${name}`, kind, name, count: towns.length, towns,
        // rules.md：統治者清單含紅軍的城鎮＝牆內城鎮。
        note: kind === 'ruler' && name === '紅軍' ? '牆內' : null,
      })).sort((a, b) => (b.count - a.count) || byTown({ town: a.name }, { town: b.name }));
      return { kind, label, groups: items };
    });
    if (!sections.some(s => s.groups.length)) return focusMenuFail('no-group-data');
    return { ok: true, reason: null, stage: list.stage, selected: list.selected, total: order.length, sections };
  }

  /**
   * 選定當下的新模型與畫面上的選單（開啟或上次以 req 綁定 snapshot 重畫時的模型）相比：清單段或 pending choice 的
   * 已選城鎮變了 → true（不移焦點，改為刷新選單）。只有候選變少由各分組自己判斷（gone）。
   */
  function focusMenuDrift(shown, fresh) {
    if (!shown || !fresh) return true;
    return shown.stage !== fresh.stage || (shown.selected || null) !== (fresh.selected || null);
  }

  function findFocusMenuGroup(menu, key) {
    if (!menu || !menu.ok || typeof key !== 'string') return null;
    for (const section of menu.sections) {
      const group = section.groups.find(g => g.key === key);
      if (group) return group;
    }
    return null;
  }

  /** 選定分組後的焦點城鎮：目前焦點在該組內就保留，否則取清單順序第一個；沒有 → null（fail closed）。 */
  function pickFocusMenuTown(group, preferred) {
    const towns = group && Array.isArray(group.towns) ? group.towns : [];
    if (typeof preferred === 'string' && towns.includes(preferred)) return preferred;
    return towns[0] || null;
  }

  /** 聚焦選單只採用回應自己 snapshot 請求（同一個 req）的 snapshot；一般推送或過期回覆不算。 */
  function matchesMenuRequest(pending, snap) {
    return !!pending && !!snap && Core.isRequestId(pending.req) && snap.req === pending.req;
  }

  /**
   * 等待中的聚焦選單請求 pending = {req, at（送出時間）, acked（已收到同一個 req 的 ok:true）} 收到一份 snapshot
   * （已 sanitize；不合 schema 為 null）時的判定：
   *   accept  — req 相同、已收到 ok:true，且在 mapAckTimeoutMs（1000ms）之內到達；
   *   stale   — req 相同但還沒有 ok:true，或已到逾時（不開啟、不選定）；
   *   invalid — 等待中收到不合 schema 的 snapshot（fail closed）；
   *   ignore  — 沒有等待中的請求、一般推送（沒有 req）或其他 req（繼續等；逾時 fail closed）。
   */
  function menuSnapshotVerdict(pending, snap, now, config) {
    const cfg = { ...DEFAULT_GUARD_CONFIG, ...config };
    if (!pending) return 'ignore';
    if (!snap) return 'invalid';
    if (!matchesMenuRequest(pending, snap)) return 'ignore';
    if (pending.acked !== true || !Number.isFinite(pending.at) || !Number.isFinite(now)) return 'stale';
    return now - pending.at < cfg.mapAckTimeoutMs ? 'accept' : 'stale';
  }

  // ---------------------------------------------------------------- dangerous confirm

  // 確認單預設焦點永遠是「返回」。
  const CONFIRM_DEFAULT_FOCUS = 'cancel';

  /** 只讀用戶端既有 DOM 狀態的資訊性提醒，不做規則判斷。 */
  function confirmInfoLines(info) {
    const lines = [];
    const playable = Number(info && info.playableHand) || 0;
    const selected = Number(info && info.selectedPurchases) || 0;
    if (playable > 0) lines.push(`尚有 ${playable} 張手牌的「行動」按鈕可用`);
    if (selected > 0) lines.push(`已勾選 ${selected} 張購買卡但尚未購買`);
    return lines;
  }

  return {
    DISPLAY_STORAGE_KEY, DISPLAY_MODES, SAFE_AREA_SCALE, BUTTON_ACTIONS, DEFAULT_GUARD_CONFIG,
    PROCESSING_GATED, COOLDOWN_GATED, ACTIVATION_GATED, MAP_VIEW_COMMANDS, CONTENT_ZONES, SECTION_LABELS, SECTION_MODALS, HINTS, CONFIRM_DEFAULT_FOCUS,
    normalizeDisplayMode, resolveDisplayMode, logicalAction, routeLivingRoom,
    createGuard, lockProcessing, noteRedraw, noteActivation, processingActive, gate,
    beginMapRequest, expireMapRequest, settleMapResult, mapZoomBlocker,
    isDirectionalExcluded, contentZonesFor, reconcileIndex, gridColumns, gridMove, listMove, pickZone, cycleZone, resolveZone,
    sectionOfKey, stepSection, buildKeyHints, pickFactionAbility, purchaseBuyBlocker, discardControlIndex,
    buildMapList, mapStageKey, mapActFor, moveModeLabel, confirmInfoLines,
    FOCUS_MENU_REASONS, buildFocusMenu, focusMenuDrift, findFocusMenuGroup, pickFocusMenuTown, matchesMenuRequest, menuSnapshotVerdict,
  };
});
