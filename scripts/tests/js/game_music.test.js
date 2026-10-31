// node --test scripts/tests/js/game_music.test.js
// 遊戲配樂：音量預設／正規化／持久化、0..100 邊界與 10% step、只在遊戲畫面播放、autoplay 限制、音量 0 不重複 play。
const test = require('node:test');
const assert = require('node:assert/strict');
const M = require('../../../static/game_music.js');

function fakeStorage(initial) {
  const data = new Map(Object.entries(initial || {}));
  return {
    getItem: k => (data.has(k) ? data.get(k) : null),
    setItem: (k, v) => { data.set(k, String(v)); },
    data,
  };
}

function fakeAudio({ rejectWith = null } = {}) {
  const a = {
    paused: true, volume: 1, loop: false, playCalls: 0, pauseCalls: 0, rejectWith,
    play() {
      this.playCalls += 1;
      if (this.rejectWith) return Promise.reject(Object.assign(new Error('x'), { name: this.rejectWith }));
      this.paused = false;
      return Promise.resolve();
    },
    pause() { this.pauseCalls += 1; this.paused = true; },
  };
  return a;
}
const tick = () => new Promise(r => setImmediate(r));

test('defaults and constants: 30% default, 10% step, 0..100 range, local same-origin asset', () => {
  assert.equal(M.DEFAULT_VOLUME, 30);
  assert.equal(M.VOLUME_STEP, 10);
  assert.equal(M.MIN_VOLUME, 0);
  assert.equal(M.MAX_VOLUME, 100);
  assert.equal(M.TRACK_SRC, '/static/audio/redline-theme.m4a');
  assert.ok(!/^[a-z]+:\/\//i.test(M.TRACK_SRC) && !M.TRACK_SRC.startsWith('//'), 'no CDN／remote audio');
});

test('normalizeVolume: invalid stored values fall back to the default, numeric values clamp and snap to 10%', () => {
  for (const bad of [null, undefined, '', '  ', 'abc', 'NaN', 'Infinity', '-Infinity', {}, [], NaN, Infinity, true, '1e999x']) {
    assert.equal(M.normalizeVolume(bad), 30, String(bad));
  }
  assert.equal(M.normalizeVolume('0'), 0);
  assert.equal(M.normalizeVolume(0), 0);
  assert.equal(M.normalizeVolume('100'), 100);
  assert.equal(M.normalizeVolume('250'), 100);
  assert.equal(M.normalizeVolume('-40'), 0);
  assert.equal(M.normalizeVolume('34'), 30);
  assert.equal(M.normalizeVolume('35'), 40);
  assert.equal(M.normalizeVolume(' 70 '), 70);
  assert.equal(M.normalizeVolume(0.5), 10 * Math.round(0.5 / 10));
  for (let v = 0; v <= 100; v += 10) assert.equal(M.normalizeVolume(v), v);
});

test('stepVolume: 10% steps, clamped at both ends, never leaves the grid', () => {
  assert.equal(M.stepVolume(30, 1), 40);
  assert.equal(M.stepVolume(30, -1), 20);
  assert.equal(M.stepVolume(100, 1), 100);
  assert.equal(M.stepVolume(0, -1), 0);
  assert.equal(M.stepVolume(0, 1), 10);
  assert.equal(M.stepVolume(10, -1), 0);
  assert.equal(M.stepVolume(90, 1), 100);
  assert.equal(M.stepVolume('garbage', 1), 40, 'invalid current value normalizes to 30 first');
  assert.equal(M.stepVolume(34, 1), 40, 'off-grid current value snaps first');
  assert.equal(M.stepVolume(30, 0), 30);
  const seen = [];
  let v = 0;
  for (let i = 0; i < 14; i += 1) { seen.push(v); v = M.stepVolume(v, 1); }
  assert.deepEqual(seen, [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 100, 100, 100]);
});

test('formatVolume shows the live percentage', () => {
  assert.equal(M.formatVolume(30), '30%');
  assert.equal(M.formatVolume(0), '0%');
  assert.equal(M.formatVolume('bad'), '30%');
});

test('persistence: load normalizes, save writes the normalized value, broken storage never throws', () => {
  assert.equal(M.loadVolume(fakeStorage()), 30);
  assert.equal(M.loadVolume(fakeStorage({ [M.STORAGE_KEY]: '70' })), 70);
  assert.equal(M.loadVolume(fakeStorage({ [M.STORAGE_KEY]: 'loud' })), 30);
  assert.equal(M.loadVolume(fakeStorage({ [M.STORAGE_KEY]: '999' })), 100);
  const s = fakeStorage();
  assert.equal(M.saveVolume(s, 40), 40);
  assert.equal(s.data.get(M.STORAGE_KEY), '40');
  assert.equal(M.saveVolume(s, 47), 50);
  assert.equal(s.data.get(M.STORAGE_KEY), '50');
  const throwing = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } };
  assert.equal(M.loadVolume(throwing), 30);
  assert.equal(M.saveVolume(throwing, 60), 60);
  assert.equal(M.loadVolume(null), 30);
  assert.equal(M.saveVolume(null, 60), 60);
});

test('shouldPlay: needs the game screen, volume > 0 and a trusted user activation', () => {
  const ok = { inGame: true, volume: 30, activated: true };
  assert.equal(M.shouldPlay(ok), true);
  assert.equal(M.shouldPlay({ ...ok, inGame: false }), false);
  assert.equal(M.shouldPlay({ ...ok, volume: 0 }), false);
  assert.equal(M.shouldPlay({ ...ok, activated: false }), false);
  assert.equal(M.shouldPlay(null), false);
  assert.equal(M.shouldPlay({}), false);
});

test('player: loops, applies volume, plays only in game after a trusted activation, pauses when leaving the game', async () => {
  const audio = fakeAudio();
  const p = M.createPlayer({ audio, storage: fakeStorage() });
  assert.equal(audio.loop, true);
  assert.equal(audio.volume, 0.3);
  p.setInGame(true);
  await tick();
  assert.equal(audio.playCalls, 0, 'no play() before a user activation (autoplay policy)');
  p.activate();
  await tick();
  assert.equal(audio.playCalls, 1);
  assert.equal(audio.paused, false);
  p.setInGame(true); p.setInGame(true); p.sync();
  assert.equal(audio.playCalls, 1, 'already playing: no duplicate play()');
  p.setInGame(false);
  assert.equal(audio.paused, true);
  p.setInGame(true);
  await tick();
  assert.equal(audio.playCalls, 2, 'returns to the game: resumes (same element, same position)');
  assert.equal(audio.paused, false);
});

test('player: never plays in the lobby／start flow even after an activation', async () => {
  const audio = fakeAudio();
  const p = M.createPlayer({ audio, storage: fakeStorage() });
  p.activate();
  p.setInGame(false);
  p.sync();
  await tick();
  assert.equal(audio.playCalls, 0);
  assert.equal(audio.paused, true);
});

test('player: volume 0 stays paused without calling play(); raising it again resumes; steps persist', async () => {
  const storage = fakeStorage({ [M.STORAGE_KEY]: '10' });
  const audio = fakeAudio();
  const p = M.createPlayer({ audio, storage });
  assert.equal(p.volume(), 10);
  p.activate(); p.setInGame(true);
  await tick();
  assert.equal(audio.playCalls, 1);
  p.stepVolume(-1);
  assert.equal(p.volume(), 0);
  assert.equal(storage.data.get(M.STORAGE_KEY), '0');
  assert.equal(audio.paused, true);
  assert.equal(audio.volume, 0);
  for (let i = 0; i < 5; i += 1) { p.sync(); p.setInGame(true); p.activate(); p.stepVolume(-1); }
  await tick();
  assert.equal(audio.playCalls, 1, 'volume 0: play() is never retried');
  p.stepVolume(1);
  await tick();
  assert.equal(p.volume(), 10);
  assert.equal(audio.playCalls, 2);
  assert.equal(audio.paused, false);
  assert.equal(audio.volume, 0.1);
  for (let i = 0; i < 20; i += 1) p.stepVolume(1);
  assert.equal(p.volume(), 100);
  assert.equal(audio.volume, 1);
  assert.equal(storage.data.get(M.STORAGE_KEY), '100');
});

test('player: starting at stored volume 0 never calls play()', async () => {
  const audio = fakeAudio();
  const p = M.createPlayer({ audio, storage: fakeStorage({ [M.STORAGE_KEY]: '0' }), activated: true });
  p.setInGame(true);
  await tick();
  assert.equal(audio.playCalls, 0);
  assert.equal(audio.paused, true);
});

test('player: an autoplay rejection is not retried until the next trusted activation', async () => {
  const audio = fakeAudio({ rejectWith: 'NotAllowedError' });
  const p = M.createPlayer({ audio, storage: fakeStorage(), activated: true });
  p.setInGame(true);
  await tick();
  assert.equal(audio.playCalls, 1);
  for (let i = 0; i < 10; i += 1) { p.sync(); p.setInGame(true); p.stepVolume(1); }
  await tick();
  assert.equal(audio.playCalls, 1, 'no play() spam after NotAllowedError');
  audio.rejectWith = null;
  p.activate();
  await tick();
  assert.equal(audio.playCalls, 2);
  assert.equal(audio.paused, false);
});

test('player: music state is independent of game state (handoff mask etc. do not pause it)', async () => {
  const audio = fakeAudio();
  const p = M.createPlayer({ audio, storage: fakeStorage(), activated: true });
  p.setInGame(true);
  await tick();
  assert.equal(audio.paused, false);
  // 交接遮罩只是 DOM 遮蔽：播放器沒有任何 handoff／遊戲 state 輸入，連續 sync 不影響播放。
  p.sync(); p.sync();
  assert.equal(audio.paused, false);
  assert.equal(audio.pauseCalls, 0);
  assert.deepEqual(Object.keys(p.state()).sort(), ['activated', 'inGame', 'paused', 'volume'].sort());
});

test('detectInGame: game shell shown, lobby／start flow hidden (visibility:hidden handoff mask still counts as in game)', () => {
  const shown = { isConnected: true, display: 'block', rects: 1 };
  const hidden = { isConnected: true, display: 'none', rects: 0 };
  assert.equal(M.detectInGame({ gameShell: shown, lobby: hidden, startFlow: hidden, autoSetup: false }), true);
  assert.equal(M.detectInGame({ gameShell: hidden, lobby: shown, startFlow: shown, autoSetup: false }), false);
  assert.equal(M.detectInGame({ gameShell: shown, lobby: shown, startFlow: hidden, autoSetup: false }), false);
  assert.equal(M.detectInGame({ gameShell: shown, lobby: hidden, startFlow: shown, autoSetup: false }), false);
  assert.equal(M.detectInGame({ gameShell: shown, lobby: hidden, startFlow: hidden, autoSetup: true }), false);
  assert.equal(M.detectInGame({ gameShell: null, lobby: null, startFlow: null, autoSetup: false }), false);
});
