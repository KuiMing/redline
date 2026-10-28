// node --test scripts/tests/js/event_reveal_core.test.js
// 事件卡自動揭示：取消反應（爆料黑幕／產業滲透／情報網）視窗不可自動揭示事件卡，且同一次觸發結束後（含整頁重新載入）也不補開。
const test = require('node:test');
const assert = require('node:assert/strict');
const E = require('../../../static/event_reveal_core.js');

const G = 'game-1';
const EVENT = { id: 'ev-7', name: '歲月靜好', type: 'noop' };

function state(extra = {}) {
  return { turn: 3, current_player: 'P1', current_event: EVENT, pending_choice: null, ...extra };
}

function reaction(playerId, extra = {}) {
  return {
    type: 'reaction_choice', choice_key: 'cancel_other_player_action', choice_id: 'c-1', player_id: playerId,
    acting_player_id: 'p1', acting_player_name: 'P1', played_card_name: '領導', ...extra,
  };
}

/** 模擬一個分頁：lastKey／lastReactionChoiceId 在記憶體（重新載入歸零），suppressed 在 sessionStorage（重新載入保留）。 */
function tab(storage = { raw: null }) {
  const mem = { lastKey: null, lastReactionChoiceId: null, opened: 0, closed: 0 };
  return {
    storage,
    mem,
    reload() { mem.lastKey = null; mem.lastReactionChoiceId = null; },
    render(s, viewerId) {
      const d = E.decideAutoReveal({
        state: s, viewerId, lastKey: mem.lastKey, suppressed: E.normalizeSuppressed(storage.raw, G),
        lastReactionChoiceId: mem.lastReactionChoiceId,
      });
      mem.lastReactionChoiceId = d.reactionChoiceId;
      if (d.record) storage.raw = E.rememberSuppressed(E.normalizeSuppressed(storage.raw, G), G, d.record);
      if (d.closeForReaction) mem.closed += 1;
      mem.lastKey = d.key;
      if (d.open) mem.opened += 1;
      return d;
    },
  };
}

test('一般流程：新事件第一次 render 自動揭示一次，之後同一事件不再揭示；沒有事件 → 不揭示', () => {
  const t = tab();
  assert.equal(t.render(state(), 'p1').open, true);
  assert.equal(t.render(state(), 'p1').open, false);
  assert.equal(t.render(state({ current_event: null }), 'p1').open, false);
  assert.equal(E.revealKey(state()), '3:ev-7');
  assert.equal(E.revealKey(state({ current_event: { name: '只有名稱' } })), '3:只有名稱');
  assert.equal(E.revealKey(null), null);
});

for (const card of ['爆料黑幕', '產業滲透', '情報網']) {
  for (const [path, played] of [['card', '領導'], ['ability', '統戰部']]) {
    for (const outcome of ['decline', 'cancel']) {
      test(`取消反應（${card}／${path}：${played}／${outcome}）：反應者重新載入不揭示，結束後交回行動者重新載入也不揭示`, () => {
        const storage = { raw: null };
        const t = tab(storage);
        // 行動者自己的回合：事件已正常揭示過。
        assert.equal(t.render(state(), 'p1').open, true);
        // 行動者打出可被取消的卡／能力：反應視窗出現（行動者這一頁正在被交接遮罩蓋住）。
        const pending = state({ pending_choice: reaction('p2', { played_card_name: played, cards: [{ name: card }] }) });
        assert.equal(t.render(pending, 'p1').open, false);
        // 客廳輪流：整頁重新載入成反應者（記憶體歸零）。反應視窗必須是唯一的自動 modal。
        t.reload();
        const asReactor = t.render(pending, 'p2');
        assert.equal(asReactor.open, false);
        assert.equal(asReactor.closeForReaction, true, '反應者：關閉任何仍開著的事件揭示');
        assert.equal(t.render(pending, 'p2').closeForReaction, false, '同一個反應視窗只關一次（之後手動開啟不會被關掉）');
        // 反應者決定（不取消或取消）後反應視窗結束：同一頁不補開。
        const after = state({ action_log: [outcome] });
        assert.equal(t.render(after, 'p2').open, false);
        // 交回行動者：整頁重新載入（記憶體歸零），同一張事件、同一位行動玩家 → 不補開。
        t.reload();
        assert.equal(t.render(after, 'p1').open, false);
        assert.equal(t.mem.opened, 1);
      });
    }
  }
}

test('非反應者（旁觀）看到反應視窗：不自動揭示、不強制關閉，也不洩漏反應卡（只看公開的 type）', () => {
  const t = tab();
  const pending = state({ pending_choice: { type: 'reaction_choice', player_id: 'p2', choice_id: 'c-1', cards: [] } });
  const d = t.render(pending, 'p3');
  assert.equal(d.open, false);
  assert.equal(d.closeForReaction, false);
  assert.ok(d.record);
});

test('觸發範圍：換到下一位玩家（同一張事件）或下一張事件 → 恢復既有自動揭示', () => {
  const storage = { raw: null };
  const t = tab(storage);
  t.render(state({ pending_choice: reaction('p2') }), 'p2');
  t.reload();
  assert.equal(t.render(state(), 'p1').open, false);
  // P1 結束回合 → P2 的回合（同一回合同一事件）：客廳輪流整頁重新載入成 P2，照既有行為揭示。
  t.reload();
  assert.equal(t.render(state({ current_player: 'P2' }), 'p2').open, true);
  // 下一回合新事件：照常揭示。
  t.reload();
  assert.equal(t.render(state({ turn: 4, current_event: { id: 'ev-8', name: '新事件' } }), 'p1').open, true);
});

test('其他 pending choice（不是取消反應）不影響既有自動揭示', () => {
  const t = tab();
  assert.equal(t.render(state({ pending_choice: { type: 'card_choice', player_id: 'p1', choice_id: 'x' } }), 'p1').open, true);
});

test('sessionStorage 內容不可信：其他遊戲、格式不合、超長 token 一律忽略；最多保留最近 16 個', () => {
  assert.deepEqual(E.normalizeSuppressed(null, G), []);
  assert.deepEqual(E.normalizeSuppressed({ gameId: 'other', tokens: ['a'] }, G), []);
  assert.deepEqual(E.normalizeSuppressed({ gameId: G, tokens: 'a' }, G), []);
  assert.deepEqual(E.normalizeSuppressed({ gameId: G, tokens: ['ok', 3, '', 'x'.repeat(600)] }, G), ['ok']);
  assert.deepEqual(E.normalizeSuppressed({ gameId: G, tokens: ['a'] }, ''), []);
  let saved = { gameId: G, tokens: [] };
  for (let i = 0; i < 20; i += 1) saved = E.rememberSuppressed(saved.tokens, G, `t${i}`);
  assert.equal(saved.tokens.length, E.MAX_TOKENS);
  assert.equal(saved.tokens[0], 't4');
  assert.deepEqual(E.rememberSuppressed(['a'], G, 'a').tokens, ['a']);
  assert.equal(E.suppressionToken(state(), '3:ev-7'), '3:ev-7|P1');
  assert.equal(E.reactionWindowOpen(state({ pending_choice: { type: 'reaction_choice' } })), true);
  assert.equal(E.reactionWindowOpen(state()), false);
});

test('遊戲已結束（winner／finished）：不再自動揭示事件卡（勝利畫面是唯一結果畫面），手動開啟不受影響', () => {
  const t = tab();
  assert.equal(t.render(state({ winner: 'P2' }), 'p1').open, false);
  t.reload();
  assert.equal(t.render(state({ game_phase: 'finished' }), 'p1').open, false);
  t.reload();
  assert.equal(t.render(state({ game_phase: 'GamePhase.FINISHED' }), 'p1').open, false);
});
