/*
 * REDLINE 開始遊戲前流程 — 純邏輯，無 DOM 依賴，可在 node 直接測試。
 *
 * 初始畫面三條路徑：建立真人紅軍／建立 AI 紅軍／輸入房間代碼加入。建立者不選人數；
 * 選難度與操作方式，Joy-Con 以 SL＋SR 同時按下依成功順序配成 P1～P4，按「完成配對」才繼續。
 * 設定在建房時送給伺服器（/create），之後以 /lobby 的伺服器資料為準；這裡不含任何遊戲規則。
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.RedlineStartFlowCore = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const MARKET_MODES = Object.freeze({ sample_53: '簡單模式', all_cards: '一般模式' });
  const CONTROL_MODES = Object.freeze({ joycon: 'Joy-Con', computer: '電腦' });
  const MAX_CONTROLLERS = 4;
  const MIN_CONTROLLERS = 1;

  function isControllerId(v) {
    if (typeof v !== 'string' || v.length > 24) return false;
    const m = /^[LR]([1-9][0-9]{0,4})-(?:[0-9a-f]{8}|legacy)$/.exec(v);
    return !!m && Number(m[1]) <= 65535;
  }

  /** AI 紅軍佔用一個席位，本機最多 3 支；真人紅軍最多 4 支（與伺服器 /create 驗證相同）。 */
  function maxControllers(aiRedArmy) { return aiRedArmy ? MAX_CONTROLLERS - 1 : MAX_CONTROLLERS; }

  /** 草稿：紅軍類型由入口按鈕決定；難度預設簡單、操作預設電腦。不合法值一律回預設。 */
  function normalizeDraft(raw) {
    const r = raw && typeof raw === 'object' ? raw : {};
    return {
      aiRedArmy: r.aiRedArmy === true,
      marketMode: Object.prototype.hasOwnProperty.call(MARKET_MODES, r.marketMode) ? r.marketMode : 'sample_53',
      controlMode: r.controlMode === 'joycon' ? 'joycon' : 'computer',
    };
  }

  function createPairing(max) {
    const cap = Number.isInteger(max) ? Math.min(Math.max(max, MIN_CONTROLLERS), MAX_CONTROLLERS) : MAX_CONTROLLERS;
    return { max: cap, order: [], down: {}, epochs: {} };
  }

  /** 把上限收緊（例如改選 AI 紅軍）：超過的後配對者移除。 */
  function setPairingMax(pairing, max) {
    const next = createPairing(max);
    return { ...pairing, max: next.max, order: pairing.order.slice(0, next.max) };
  }

  const chordHeld = buttons => !!(buttons && buttons.SL && buttons.SR);

  /**
   * 一筆手把 frame：SL＋SR 同時按住的「按下瞬間」才配對。每支手把（或同一支重新連線／epoch 改變）的第一筆只當 baseline，
   * 進來就已按住的組合要先放開再按。已配對的不重複、滿了不再收。回傳 {pairing, added}（added＝剛配對的 id 或 null）。
   */
  function observeFrame(pairing, controller, epoch, buttons) {
    if (!isControllerId(controller)) return { pairing, added: null };
    const both = chordHeld(buttons);
    const next = { ...pairing, down: { ...pairing.down, [controller]: both }, epochs: { ...pairing.epochs, [controller]: epoch } };
    if (pairing.epochs[controller] !== epoch) return { pairing: next, added: null }; // baseline
    if (!both || pairing.down[controller]) return { pairing: next, added: null }; // 沒按或仍按著
    if (pairing.order.includes(controller) || pairing.order.length >= pairing.max) return { pairing: next, added: null };
    return { pairing: { ...next, order: [...pairing.order, controller] }, added: controller };
  }

  function removeController(pairing, controller) {
    return { ...pairing, order: pairing.order.filter(id => id !== controller) };
  }

  /** 顯示用席位：P1～P(max)，依配對順序填入；其餘為待配對。 */
  function slots(pairing) {
    return Array.from({ length: pairing.max }, (_, i) => ({
      label: `P${i + 1}`, controller: pairing.order[i] || null, paired: i < pairing.order.length,
    }));
  }

  /** 可以繼續？電腦操作直接可繼續；Joy-Con 至少配對一支（最多 max 支）才可繼續。 */
  function canContinue(draft, pairing) {
    const d = normalizeDraft(draft);
    if (d.controlMode !== 'joycon') return true;
    const n = pairing ? pairing.order.length : 0;
    return n >= MIN_CONTROLLERS && n <= maxControllers(d.aiRedArmy);
  }

  /** 送給 /create 的房主設定（伺服器會再驗證一次）。 */
  function createSettings(draft, pairing) {
    const d = normalizeDraft(draft);
    const joycon = d.controlMode === 'joycon';
    return {
      ai_red_army: d.aiRedArmy,
      market_mode: d.marketMode,
      control_mode: d.controlMode,
      joycon_count: joycon ? (pairing ? pairing.order.length : 0) : null,
    };
  }

  function cleanRoomCode(value) {
    const code = String(value == null ? '' : value).trim();
    return code && code.length <= 64 && !/\s/.test(code) ? code : null;
  }

  /** 伺服器 /lobby 的房主設定 → 顯示用文字（訪客唯讀）。 */
  function settingsSummary(lobby) {
    if (!lobby || typeof lobby !== 'object') return null;
    const mode = lobby.control_mode === 'joycon' ? `Joy-Con${Number.isInteger(lobby.joycon_count) ? ` ×${lobby.joycon_count}` : ''}` : CONTROL_MODES.computer;
    return {
      redArmy: lobby.ai_red_army ? 'AI 紅軍' : '真人紅軍',
      difficulty: MARKET_MODES[lobby.market_mode] || MARKET_MODES.sample_53,
      control: mode,
      text: `${lobby.ai_red_army ? 'AI 紅軍' : '真人紅軍'}｜${MARKET_MODES[lobby.market_mode] || MARKET_MODES.sample_53}｜操作：${mode}`,
    };
  }

  // ---------------------------------------------------------------- 重新開始沿用的 Joy-Con 配對
  // 上一局（客廳輪流，每一席都綁了手把）經既有 /new-game 重新開始時，hotseat_ui 在導向前把既有座位順序的手把寫進
  // sessionStorage（同一分頁）。新的開始流程：起始導覽只交給 P1 那一支、選 Joy-Con 時直接帶入 P1～Pn，不必再按 SL＋SR。
  // 內容不可信：格式不合、過期或不是 2～4 支不重複的合法 id → null（照常配對）。
  const CARRYOVER_KEY = 'redline.startflow.carryover.v1';
  const CARRYOVER_TTL_MS = 30 * 60 * 1000;

  function normalizeCarryover(raw, now) {
    if (!raw || typeof raw !== 'object' || raw.v !== 1 || !Array.isArray(raw.controllers)) return null;
    const at = Number(raw.at);
    const t = Number(now);
    if (!Number.isFinite(at) || !Number.isFinite(t) || at > t || t - at > CARRYOVER_TTL_MS) return null;
    const controllers = raw.controllers;
    if (controllers.length < 2 || controllers.length > MAX_CONTROLLERS) return null;
    if (!controllers.every(isControllerId) || new Set(controllers).size !== controllers.length) return null;
    return { controllers: controllers.slice() };
  }

  /** 沿用的配對（依上限截斷：AI 紅軍只能 3 支）；沒有沿用 → 空的新配對。 */
  function carryoverPairing(carry, max) {
    const pairing = createPairing(max);
    if (!carry || !Array.isArray(carry.controllers)) return pairing;
    return { ...pairing, order: carry.controllers.filter(isControllerId).slice(0, pairing.max) };
  }

  return {
    MARKET_MODES, CONTROL_MODES, MAX_CONTROLLERS, MIN_CONTROLLERS, CARRYOVER_KEY, CARRYOVER_TTL_MS,
    isControllerId, maxControllers, normalizeDraft, createPairing, setPairingMax, observeFrame, removeController,
    slots, canContinue, createSettings, cleanRoomCode, settingsSummary, normalizeCarryover, carryoverPairing,
  };
});
