// node --test scripts/tests/js/start_flow_core.test.js
const test = require('node:test');
const assert = require('node:assert/strict');
const S = require('../../../static/start_flow_core.js');

const C1 = 'R24800-3f2a9c1e';
const C2 = 'L24801-0a1b2c3d';
const C3 = 'R24802-11111111';
const C4 = 'L24803-22222222';
const C5 = 'R24804-33333333';
const CHORD = { SL: true, SR: true };
const NONE = {};

// 先 baseline、放開、再按下 SL＋SR
function press(pairing, id, epoch = 1) {
  let r = S.observeFrame(pairing, id, epoch, NONE);
  r = S.observeFrame(r.pairing, id, epoch, CHORD);
  return r;
}

test('只有 SL＋SR 同時按住的按下瞬間才配對；單按 SL 或 SR 不算', () => {
  let p = S.createPairing(4);
  p = S.observeFrame(p, C1, 1, NONE).pairing;
  for (const b of [{ SL: true }, { SR: true }, { A: true }]) {
    const r = S.observeFrame(p, C1, 1, b);
    assert.equal(r.added, null);
    p = S.observeFrame(r.pairing, C1, 1, NONE).pairing;
  }
  const r = S.observeFrame(p, C1, 1, CHORD);
  assert.equal(r.added, C1);
  assert.deepEqual(r.pairing.order, [C1]);
});

test('第一筆 frame 只是 baseline：進來就按著 SL＋SR 要放開再按；epoch 改變（重連）同樣重新 baseline', () => {
  let p = S.createPairing(4);
  let r = S.observeFrame(p, C1, 1, CHORD);
  assert.equal(r.added, null);
  r = S.observeFrame(r.pairing, C1, 1, CHORD);
  assert.equal(r.added, null, '仍按著，沒有新的按下');
  r = S.observeFrame(r.pairing, C1, 1, NONE);
  r = S.observeFrame(r.pairing, C1, 1, CHORD);
  assert.equal(r.added, C1);
  const again = S.observeFrame(S.removeController(r.pairing, C1), C1, 2, CHORD);
  assert.equal(again.added, null, '新 epoch 的第一筆是 baseline');
});

test('依成功配對順序分配 P1～P4；重複按同一支不重複配對', () => {
  let p = S.createPairing(4);
  p = press(p, C3).pairing;
  p = press(p, C1).pairing;
  const dup = press(p, C3, 1); // 已配對
  assert.equal(dup.added, null);
  p = press(dup.pairing, C4).pairing;
  p = press(p, C2).pairing;
  assert.deepEqual(p.order, [C3, C1, C4, C2]);
  assert.deepEqual(S.slots(p).map(s => [s.label, s.controller]), [['P1', C3], ['P2', C1], ['P3', C4], ['P4', C2]]);
});

test('最多四支（AI 紅軍最多三支）：滿了之後的手把不會被收下', () => {
  let p = S.createPairing(4);
  for (const id of [C1, C2, C3, C4]) p = press(p, id).pairing;
  assert.equal(press(p, C5).added, null);
  assert.equal(p.order.length, 4);
  let ai = S.createPairing(S.maxControllers(true));
  for (const id of [C1, C2, C3]) ai = press(ai, id).pairing;
  assert.equal(press(ai, C4).added, null);
  assert.equal(S.slots(ai).length, 3);
  assert.deepEqual(S.setPairingMax(p, 3).order, [C1, C2, C3]);
});

test('不合法的手把 id 不能配對', () => {
  const p = S.createPairing(4);
  assert.equal(S.observeFrame(S.observeFrame(p, 'x', 1, NONE).pairing, 'x', 1, CHORD).added, null);
});

test('完成配對門檻：Joy-Con 至少一支；電腦不需要；超過上限不可', () => {
  const joy = S.normalizeDraft({ controlMode: 'joycon' });
  assert.equal(S.canContinue(joy, S.createPairing(4)), false);
  assert.equal(S.canContinue(joy, press(S.createPairing(4), C1).pairing), true);
  assert.equal(S.canContinue(S.normalizeDraft({ controlMode: 'computer' }), S.createPairing(4)), true);
  assert.equal(S.canContinue(joy, null), false);
  const ai = S.normalizeDraft({ controlMode: 'joycon', aiRedArmy: true });
  let p = S.createPairing(4);
  for (const id of [C1, C2, C3, C4]) p = press(p, id).pairing;
  assert.equal(S.canContinue(ai, p), false, 'AI 紅軍時 4 支超過上限');
});

test('建房設定：兩種紅軍、難度、操作；電腦操作不帶手把數', () => {
  const one = press(S.createPairing(4), C1).pairing;
  assert.deepEqual(S.createSettings({ aiRedArmy: false, marketMode: 'all_cards', controlMode: 'joycon' }, one),
    { ai_red_army: false, market_mode: 'all_cards', control_mode: 'joycon', joycon_count: 1 });
  assert.deepEqual(S.createSettings({ aiRedArmy: true }, one),
    { ai_red_army: true, market_mode: 'sample_53', control_mode: 'computer', joycon_count: null });
  assert.deepEqual(S.normalizeDraft({ marketMode: 'hard', controlMode: 'pad', aiRedArmy: 'yes' }),
    { aiRedArmy: false, marketMode: 'sample_53', controlMode: 'computer' });
});

test('房間代碼：去空白、拒絕空值與含空白', () => {
  assert.equal(S.cleanRoomCode('  abc-123 '), 'abc-123');
  assert.equal(S.cleanRoomCode('   '), null);
  assert.equal(S.cleanRoomCode('a b'), null);
  assert.equal(S.cleanRoomCode(null), null);
});

test('訪客看到的房主設定摘要', () => {
  assert.equal(S.settingsSummary({ ai_red_army: true, market_mode: 'all_cards', control_mode: 'joycon', joycon_count: 2 }).text,
    'AI 紅軍｜一般模式｜操作：Joy-Con ×2');
  assert.equal(S.settingsSummary({ ai_red_army: false, market_mode: 'sample_53', control_mode: 'computer' }).text,
    '真人紅軍｜簡單模式｜操作：電腦');
  assert.equal(S.settingsSummary(null), null);
});
