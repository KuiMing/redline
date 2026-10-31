/*
 * REDLINE 遊戲配樂（redline-theme.m4a，同源本機檔）。
 *
 * 只負責配樂的播放與音量：在開始畫面、大廳與實際遊戲畫面持續播放、循環、遵守瀏覽器 autoplay 限制（可信任的使用者互動之後才
 * 呼叫 play()，被拒絕後不重試直到下一次互動）、音量 0 時保持暫停（不呼叫 play()）。音量 0～100%、每次 10%、預設 30%，
 * 存在 localStorage。音樂狀態不讀、也不寫任何遊戲 state：交接遮罩（hot-seat）不會中斷音樂。
 * 純函式與播放器不依賴 DOM（node 可直接測試）；DOM 綁定在最下面的 init()。
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.RedlineGameMusic = api;
  if (typeof document !== 'undefined' && typeof window !== 'undefined' && root === window) api.init();
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  const TRACK_SRC = '/static/audio/redline-theme.m4a';
  const STORAGE_KEY = 'redline.music.volume.v1';
  const DEFAULT_VOLUME = 30;
  const MIN_VOLUME = 0;
  const MAX_VOLUME = 100;
  const VOLUME_STEP = 10;

  /** 任何輸入（localStorage 字串、數字、垃圾值）→ 0..100、10 的倍數的整數；無法解析 → 預設 30。 */
  function normalizeVolume(raw) {
    let n = null;
    if (typeof raw === 'number') n = raw;
    else if (typeof raw === 'string' && /^\s*-?\d+(\.\d+)?\s*$/.test(raw)) n = Number(raw);
    if (n === null || !Number.isFinite(n)) return DEFAULT_VOLUME;
    const snapped = Math.round(n / VOLUME_STEP) * VOLUME_STEP;
    return Math.min(MAX_VOLUME, Math.max(MIN_VOLUME, snapped)) + 0; // +0：-0 → 0
  }

  /** dir＝+1／-1：先正規化目前值，再加減一個 step 並夾在 0..100。 */
  function stepVolume(current, dir) {
    const d = dir > 0 ? 1 : dir < 0 ? -1 : 0;
    return normalizeVolume(normalizeVolume(current) + d * VOLUME_STEP);
  }

  function formatVolume(volume) { return `${normalizeVolume(volume)}%`; }

  function loadVolume(storage) {
    try { return normalizeVolume(storage ? storage.getItem(STORAGE_KEY) : null); } catch { return DEFAULT_VOLUME; }
  }

  /** 寫入正規化後的值並回傳它；儲存失敗（隱私模式等）不丟錯，本次仍使用該值。 */
  function saveVolume(storage, volume) {
    const v = normalizeVolume(volume);
    try { if (storage) storage.setItem(STORAGE_KEY, String(v)); } catch { /* ignore */ }
    return v;
  }

  /** 應該在播放：遊戲介面已顯示、音量 > 0、且已有可信任的使用者互動（autoplay）。 */
  function shouldPlay(s) {
    return !!s && s.surfaceActive === true && normalizeVolume(s.volume) > 0 && s.activated === true;
  }

  /**
   * 是否顯示任何遊戲介面。開始畫面、大廳、實際遊戲三者任一顯示時都播放。
   * 每個參數是 {isConnected, display, rects}；不看 visibility，所以 hot-seat 交接遮罩不會中斷配樂。
   */
  function detectMusicSurface({ gameShell, lobby, startFlow } = {}) {
    const shown = el => !!el && el.isConnected !== false && el.display !== 'none' && el.rects > 0;
    return shown(gameShell) || shown(lobby) || shown(startFlow);
  }

  /**
   * 播放器。audio＝HTMLAudioElement 形狀（paused／volume／loop／play()／pause()）。
   * 不接受任何遊戲 state；只有 setSurfaceActive、activate（可信任互動）、音量三個輸入。
   */
  function createPlayer({ audio, storage = null, activated = false } = {}) {
    const st = { volume: loadVolume(storage), surfaceActive: false, activated: activated === true, pending: false };
    if (audio) audio.loop = true;

    function sync() {
      if (!audio) return;
      audio.volume = st.volume / 100;
      if (!shouldPlay(st)) {
        if (!audio.paused) audio.pause();
        return;
      }
      if (!audio.paused || st.pending) return;
      st.pending = true;
      let result;
      try { result = audio.play(); } catch (err) { result = Promise.reject(err); }
      Promise.resolve(result).then(() => {
        st.pending = false;
        sync();
      }, (err) => {
        st.pending = false;
        const name = err && err.name;
        if (name === 'NotAllowedError') st.activated = false; // 等下一次可信任互動才重試（不重複 play rejection）
        else if (name === 'AbortError') sync(); // play() 途中被 pause()：狀態若又回到該播放就重新嘗試
        // 其他錯誤（檔案無法載入／不支援）不重試。
      });
    }

    sync();
    return {
      sync,
      setSurfaceActive(on) { st.surfaceActive = on === true; sync(); },
      activate() { st.activated = true; sync(); },
      setVolume(v) { st.volume = saveVolume(storage, v); sync(); return st.volume; },
      stepVolume(dir) { return this.setVolume(stepVolume(st.volume, dir)); },
      volume() { return st.volume; },
      state() { return { volume: st.volume, surfaceActive: st.surfaceActive, activated: st.activated, paused: !audio || audio.paused }; },
    };
  }

  // ------------------------------------------------------------ DOM 綁定
  function init() {
    if (typeof document === 'undefined' || typeof Audio === 'undefined') return null;
    let storage = null;
    try { storage = window.localStorage; } catch { storage = null; }
    const audio = new Audio();
    audio.preload = 'none'; // 進入遊戲且可播放前不下載
    audio.src = TRACK_SRC;
    const userActivated = !!(navigator.userActivation && navigator.userActivation.hasBeenActive);
    const player = createPlayer({ audio, storage, activated: userActivated });
    const $ = id => document.getElementById(id);

    function describe(el) {
      if (!el) return null;
      const cs = getComputedStyle(el);
      return { isConnected: el.isConnected, display: cs.display, rects: el.getClientRects().length };
    }
    function musicSurfaceNow() {
      return detectMusicSurface({
        gameShell: describe($('gameShell')), lobby: describe($('lobby')), startFlow: describe($('startFlow')),
      });
    }

    let raf = 0;
    function refreshScreen() {
      raf = 0;
      player.setSurfaceActive(musicSurfaceNow());
    }
    function scheduleRefresh() {
      if (raf) return;
      raf = (window.requestAnimationFrame || setTimeout)(refreshScreen);
    }

    // 音量控制（遊戲選單內的 − / + 按鈕與即時百分比）。Joy-Con 只是點這些既有按鈕。
    function renderVolume() {
      const v = player.volume();
      const value = $('gameMenuVolumeValue');
      if (value) value.textContent = formatVolume(v);
      const down = $('gameMenuVolumeDownBtn');
      const up = $('gameMenuVolumeUpBtn');
      if (down) down.dataset.atLimit = v <= MIN_VOLUME ? 'true' : 'false';
      if (up) up.dataset.atLimit = v >= MAX_VOLUME ? 'true' : 'false';
      const group = $('gameMenuVolume');
      if (group) group.setAttribute('data-volume', String(v));
    }
    function bindVolume() {
      const down = $('gameMenuVolumeDownBtn');
      const up = $('gameMenuVolumeUpBtn');
      if (down) down.addEventListener('click', () => { player.stepVolume(-1); renderVolume(); });
      if (up) up.addEventListener('click', () => { player.stepVolume(1); renderVolume(); });
      renderVolume();
    }

    // 只有可信任的使用者互動（滑鼠／觸控／鍵盤）才解除 autoplay 限制；bridge 的 Joy-Con frame 不算。
    const onGesture = (e) => { if (e && e.isTrusted) player.activate(); };
    // 只聽瀏覽器定義會啟動 user activation 的事件（一次點擊只算 pointerdown 一次；click 另外觸發會讓被拒絕的 play() 立刻重試）。
    for (const type of ['pointerdown', 'keydown', 'touchend']) document.addEventListener(type, onGesture, true);

    new MutationObserver(scheduleRefresh).observe(document.body, {
      subtree: true, childList: true, attributes: true, attributeFilter: ['style', 'class', 'hidden'],
    });
    document.addEventListener('visibilitychange', scheduleRefresh);
    bindVolume();
    refreshScreen();

    const api = { player, audio, renderVolume, refresh: refreshScreen };
    window.__redlineGameMusic = api;
    return api;
  }

  return {
    TRACK_SRC, STORAGE_KEY, DEFAULT_VOLUME, MIN_VOLUME, MAX_VOLUME, VOLUME_STEP,
    normalizeVolume, stepVolume, formatVolume, loadVolume, saveVolume, shouldPlay, detectMusicSurface, createPlayer, init,
  };
});
