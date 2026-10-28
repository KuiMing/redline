/*
 * REDLINE 事件卡自動揭示（#eventRevealModal）— 純邏輯，無 DOM 依賴，可在 node 直接測試。
 *
 * 2026-10-27 playtest：對手的陣營能力或卡牌觸發取消反應（爆料黑幕／產業滲透／情報網）時，前端會先自動打開
 * 資訊用的事件卡揭示，擋在可操作的取消反應視窗上面（MODAL_SCOPES 中 eventRevealModal 高於 choiceModal）。
 * 根因：揭示只以記憶體中的「本回合事件 key」判斷，客廳輪流換席位會整頁重新載入（記憶體歸零），反應者的分頁、
 * 以及反應結束後交回行動者的分頁，第一次 render 都把同一張事件卡當成新事件再揭示一次。
 *
 * 規則：
 *   - 取消反應視窗開著（state.pending_choice.type === 'reaction_choice'，所有 viewer 都看得到這個公開狀態）時，
 *     一律不自動揭示，並記下「這一次觸發」的 token（回合事件 key＋目前行動玩家）。
 *   - 之後同一 token（同一張事件卡、仍是同一位玩家的回合）的 render——含反應結束後整頁重新載入回行動者——都不再自動揭示。
 *   - 換到下一位玩家或下一張事件卡＝新的 token，維持原本的自動揭示。手動開啟（事件卡分頁）不受影響。
 *   - 遊戲已結束（winner／finished）不再自動揭示：勝利畫面是唯一的結果畫面。
 * token 存在 sessionStorage（同一分頁跨重新載入；換席位的整頁重新載入仍是同一分頁）。內容不可信，一律正規化。
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.RedlineEventRevealCore = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const STORAGE_KEY = 'redline.eventRevealSuppressed.v1';
  const MAX_TOKENS = 16;
  const MAX_TOKEN_LENGTH = 512;

  function isId(v) { return typeof v === 'string' && v.length > 0 && v.length <= 128; }

  /** 與 app.js 既有規則相同：`回合:事件 id（或名稱）`；沒有事件 → null。 */
  function revealKey(state) {
    const event = state && state.current_event;
    if (!event) return null;
    return `${state.turn ?? 0}:${event.id || event.name || 'event'}`;
  }

  /** 取消反應視窗開著（公開狀態：非反應者看到的是遮蔽卡牌後的同一個 pending choice）。 */
  function reactionWindowOpen(state) {
    return !!(state && state.pending_choice && state.pending_choice.type === 'reaction_choice');
  }

  /** 這一次觸發的範圍：同一張事件卡（回合事件 key）且仍是同一位目前行動玩家。 */
  function suppressionToken(state, key) {
    if (!key) return null;
    const current = typeof (state && state.current_player) === 'string' ? state.current_player : '';
    return `${key}|${current}`.slice(0, MAX_TOKEN_LENGTH);
  }

  /** sessionStorage 內容 → 這個遊戲的 token 清單（不同遊戲或格式不合 → 空）。 */
  function normalizeSuppressed(raw, gameId) {
    if (!isId(gameId) || !raw || typeof raw !== 'object' || raw.gameId !== gameId || !Array.isArray(raw.tokens)) return [];
    return raw.tokens.filter(t => typeof t === 'string' && t.length > 0 && t.length <= MAX_TOKEN_LENGTH).slice(-MAX_TOKENS);
  }

  /** 加入一個 token（已存在則不變），回傳要寫回 sessionStorage 的內容；只保留這個遊戲最近的 MAX_TOKENS 個。 */
  function rememberSuppressed(tokens, gameId, token) {
    const list = Array.isArray(tokens) ? tokens.slice() : [];
    if (token && !list.includes(token)) list.push(token);
    return { gameId, tokens: list.slice(-MAX_TOKENS) };
  }

  /**
   * 每次 render 的自動揭示判定。
   *   state       — viewer-scoped state
   *   viewerId    — 目前分頁的 playerId
   *   lastKey     — 這個分頁上一次處理過的事件 key（app.js lastEventRevealKey）
   *   suppressed  — normalizeSuppressed 的 token 清單
   *   lastReactionChoiceId — 這個分頁上一次為取消反應關閉揭示時的 choice_id
   * 回傳：
   *   key        — 本次事件 key（呼叫端記成 lastEventRevealKey；null＝沒有事件）
   *   open       — 是否自動揭示
   *   record     — 要寫入 sessionStorage 的 token（或 null）
   *   closeForReaction — viewer 是反應者且這是新的反應視窗：關閉仍開著的揭示（反應視窗必須是唯一的自動 modal）
   *   reactionChoiceId — 呼叫端記成 lastReactionChoiceId
   */
  function decideAutoReveal({ state, viewerId, lastKey, suppressed, lastReactionChoiceId } = {}) {
    const key = revealKey(state);
    const reaction = reactionWindowOpen(state);
    const choice = reaction ? state.pending_choice : null;
    const ownsReaction = !!choice && isId(viewerId) && choice.player_id === viewerId;
    const choiceId = ownsReaction
      ? String(choice.choice_id ?? `${choice.acting_player_id || ''}|${choice.played_card_name || ''}`)
      : null;
    const closeForReaction = ownsReaction && choiceId !== lastReactionChoiceId;
    const out = { key, open: false, record: null, closeForReaction, reactionChoiceId: ownsReaction ? choiceId : lastReactionChoiceId ?? null };
    if (!key) return out;
    // 遊戲已結束：勝利畫面才是結果，不再自動揭示事件卡（客廳輪流結束時整頁切回 P1 也不會蓋住勝利畫面）。
    if (state.winner || String(state.game_phase || '').toLowerCase().includes('finished')) return out;
    const token = suppressionToken(state, key);
    if (reaction) return { ...out, record: token };
    if (lastKey === key) return out;
    if ((Array.isArray(suppressed) ? suppressed : []).includes(token)) return out;
    return { ...out, open: true };
  }

  return {
    STORAGE_KEY, MAX_TOKENS, revealKey, reactionWindowOpen, suppressionToken, normalizeSuppressed, rememberSuppressed, decideAutoReveal,
  };
});
