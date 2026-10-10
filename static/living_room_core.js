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

  // 只在客廳模式綁定：PLUS＝陣營能力、CAPTURE＝結束行動／步驟（危險確認）、ZR＝回區域層、STICK（按下搖桿）＝下一個內容區。
  const BUTTON_ACTIONS = Object.freeze({
    A: 'confirm', B: 'cancel', X: 'focusTurnBar', Y: 'toggleHelp',
    R: 'nextSection', SR: 'prevSection', PLUS: 'factionAbility', ZR: 'zoneBack', CAPTURE: 'endStep', STICK: 'nextZone',
  });

  /** HOME、SL 仍不綁定。 */
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
   *   locked: boolean,          // 地圖 scope 且 choiceLock：ZR 停用、B 只走既有取消
   *   mapCanCancel: boolean,    // iframe snapshot 回報有可取消的既有流程
   *   item: null | { card: {zone, hasToggle, hasDiscard}|null, mapRow: boolean },
   * }
   * 全域鍵（R/SR、Capture、PLUS、STICK）與焦點無關，任何層都先處理；其餘依區域層／內容層。
   */
  function routeLivingRoom(ctx, logical) {
    if (!logical || !ctx) return null;
    const name = logical.name;
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
        case 'zoneBack': return ctx.view && ctx.view !== 'command' && !ctx.locked ? { cmd: 'leaveView' } : null;
        default: return null; // B、X 在區域層不做事
      }
    }

    const item = ctx.item || null;
    if (name === 'move') return { cmd: 'itemMove', dir: logical.dir };
    if (name === 'zoneBack') return ctx.locked ? null : { cmd: 'toZoneLayer' };
    const card = item && item.card;
    if (card) {
      // 只有兩個新語意取代既有卡牌語意：購買卡 Y＝既有購買流程、可棄置手牌 B＝既有棄置（危險確認）。
      if (card.zone === 'purchase' && name === 'toggleHelp') return { cmd: 'cardBuy' };
      if (card.zone === 'hand' && name === 'cancel' && card.hasDiscard) return { cmd: 'cardDiscard' };
      // 其餘（A 查看、購買卡 B 勾選／X no-op、手牌 X 資源／Y 行動）與桌面 controller_core.routeAction 完全相同。
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
  const COOLDOWN_GATED = Object.freeze(new Set([
    'activate', 'cardMode', 'cardToggle', 'cardPreview', 'cardDiscard', 'cardBuy', 'enterZone', 'mapPick', 'mapAct',
  ]));
  // 執行型按鍵之後 250ms 內不再接受下一個執行型按鍵：防止開啟 modal（購買確認、卡面預覽、危險確認）、
  // 地圖選取／取消或卡牌勾選的那一下連按落到新出現的按鈕上，或把剛勾的 checkbox 又取消。
  // modalConfirm＝客廳模式下 modal 內的 A。只延後輸入、不改變任何遊戲語意；
  // 方向移動、R/SR、STICK、ZR、回區域層與 modal 內的 B（取消／返回）不受影響。
  const ACTIVATION_GATED = Object.freeze(new Set([
    'activate', 'cardMode', 'cardToggle', 'cardPreview', 'cardDiscard', 'cardBuy', 'enterZone',
    'mapPick', 'mapAct', 'mapCancel', 'modalConfirm', 'endStep', 'factionAbility',
  ]));

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

  /** 送出成功後登記唯一一筆等待中的請求。lock：成功後上處理中鎖；lockVia：iframe 回報走該控制時才上鎖。 */
  function beginMapRequest(guard, now, req, meta) {
    const m = meta || {};
    return {
      ...(guard || createGuard()),
      mapRequest: { req, cmd: m.cmd || null, at: now, lock: m.lock === true, lockVia: m.lockVia || null },
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
   *   success — req 對上、未逾時、ok:true → 記錄 250ms 執行冷卻；lock 表示呼叫端要上處理中鎖。
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
    return { guard: noteActivation(cleared, now), outcome: 'success', lock, request: pending };
  }

  /** 回傳 {allowed, reason, guard}；guard 可能被更新（逾時或 state 抵達後解鎖、地圖請求逾時）。 */
  function gate(guard, now, token, cmd, config) {
    const cfg = { ...DEFAULT_GUARD_CONFIG, ...config };
    let next = expireMapRequest(guard || createGuard(), now, cfg).guard;
    if (next.lockedAt !== null && !processingActive(next, now, token, cfg)) next = { ...next, lockedAt: null, lockedToken: null };
    if (PROCESSING_GATED.has(cmd) && next.lockedAt !== null) return { allowed: false, reason: 'processing', guard: next };
    // 地圖指令等待 iframe 確認期間不送出第二個執行型指令（避免同一下連按重送）；確認或逾時後立即解除。
    if (ACTIVATION_GATED.has(cmd) && next.mapRequest) return { allowed: false, reason: 'map-pending', guard: next };
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

  // 提示列只鏡射「目前就能用專用鍵執行」的既有、可見、啟用控制；排序 Y → X → B → PLUS → Capture（危險最右）。
  const HINTS = Object.freeze({
    mapAct: { key: 'Y', danger: false },
    cardBuy: { key: 'Y', danger: false },
    cardAction: { key: 'Y', danger: false },
    cardResource: { key: 'X', danger: false },
    cardToggle: { key: 'B', danger: false },
    cardDiscard: { key: 'B', danger: true },
    mapCancel: { key: 'B', danger: false },
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

  /** 購買卡 Y：焦點卡必須已勾選（在既有購買選取內），且既有「購買所選」按鈕可用；否則回傳阻擋原因。 */
  function purchaseBuyBlocker(s) {
    if (!s || !s.cardShown) return 'card-gone';
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
    PROCESSING_GATED, COOLDOWN_GATED, ACTIVATION_GATED, CONTENT_ZONES, SECTION_LABELS, SECTION_MODALS, HINTS, CONFIRM_DEFAULT_FOCUS,
    normalizeDisplayMode, resolveDisplayMode, logicalAction, routeLivingRoom,
    createGuard, lockProcessing, noteRedraw, noteActivation, processingActive, gate,
    beginMapRequest, expireMapRequest, settleMapResult,
    isDirectionalExcluded, contentZonesFor, reconcileIndex, gridColumns, gridMove, listMove, pickZone, cycleZone, resolveZone,
    sectionOfKey, stepSection, buildKeyHints, pickFactionAbility, purchaseBuyBlocker, discardControlIndex,
    buildMapList, mapActFor, moveModeLabel, confirmInfoLines,
  };
});
