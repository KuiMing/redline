/* 開始畫面「戰時指揮中心」特效（原生 WebGL2，無任何外部依賴）。
 *
 * 只作用在 #sfEntry（開始流程的最初入口）；setup／lobby／遊戲內畫面不會跑 requestAnimationFrame。
 * 一個全螢幕 fragment shader 在 1280×720 設計座標上同時畫出：紅色戰爭迷霧、底部火星、台灣雷達（掃描＋擴散波紋＋島形輪廓）、
 * 滑鼠局部光暈與微幅視差。輸出為 premultiplied alpha，疊在既有 war_background.jpg 之上，不取代主視覺。
 *
 * 設定（localStorage "redline.startFx.v1"）：{ motion: boolean, quality: "low" | "high" }
 *   - 沒有已存 motion 設定時，預設跟隨 prefers-reduced-motion（reduce → 關閉動態）；使用者明確切換後以已存設定為準。
 *   - low：渲染解析度 0.5×、雲霧 3 層迭代、火星 2 層；high：以舞台縮放×DPR（1～2×）渲染、5 層迭代、火星 4 層。
 * 動態關閉：取消 requestAnimationFrame，只畫一張固定時間的靜態影格。
 * WebGL2 不可用或 context lost：data-fx="fallback"，顯示 CSS 靜態背景，三個入口完全不受影響。
 */
(function () {
  'use strict';

  const STORAGE_KEY = 'redline.startFx.v1';
  const DESIGN_W = 1280;
  const DESIGN_H = 720;
  const STATIC_TIME = 5.3; // 靜態背景使用的固定時間（秒）
  const MAX_RENDER_SCALE = 1.5;
  const TARGET_FRAME_MS = 1000 / 60;
  // 品質只能在這裡調整：res＝渲染解析度倍率（相對 1280×720）；octaves＝雲霧 fbm 迭代；sparks＝火星層數
  const QUALITY = {
    low: { res: 0.5, octaves: 3, sparks: 2 },
    high: { res: 1, octaves: 5, sparks: 4 },
  };

  const VERT = `#version 300 es
in vec2 aPos;
out vec2 vUv;
void main() {
  vUv = aPos * 0.5 + 0.5;
  gl_Position = vec4(aPos, 0.0, 1.0);
}`;

  // 台灣島外形（設計座標，約略對齊 war_background.jpg 的島嶼位置）。
  const FRAG = `#version 300 es
precision highp float;
in vec2 vUv;
out vec4 outColor;
uniform float uTime;
uniform vec2 uMouse;   // 設計座標；uMouseA＝0 表示沒有指標
uniform float uMouseA;
uniform vec2 uPar;     // -1..1（已平滑）

const vec2 RADAR_C = vec2(908.0, 402.0);
const float RADAR_R = 150.0;
const float TAU = 6.2831853;
const int N_PT = 17;
const vec2 ISLAND[N_PT] = vec2[N_PT](
  vec2(936.0, 339.0), vec2(947.0, 349.0), vec2(945.0, 368.0), vec2(938.0, 388.0),
  vec2(931.0, 410.0), vec2(925.0, 432.0), vec2(918.0, 452.0), vec2(913.0, 468.0),
  vec2(904.0, 460.0), vec2(895.0, 440.0), vec2(883.0, 418.0), vec2(874.0, 396.0),
  vec2(877.0, 374.0), vec2(889.0, 358.0), vec2(904.0, 347.0), vec2(918.0, 340.0),
  vec2(928.0, 337.0)
);

float h11(float n) { return fract(sin(n * 127.1 + 311.7) * 43758.5453); }
float h21(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

float vnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(h21(i), h21(i + vec2(1.0, 0.0)), u.x),
             mix(h21(i + vec2(0.0, 1.0)), h21(i + vec2(1.0, 1.0)), u.x), u.y);
}

float fbm(vec2 p) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < OCTAVES; i++) {
    v += a * vnoise(p);
    p = p * 2.03 + vec2(17.1, 9.2);
    a *= 0.5;
  }
  return v;
}

float softBox(vec2 p, vec2 lo, vec2 hi, float feather) {
  vec2 a = smoothstep(lo - feather, lo + feather, p);
  vec2 b = 1.0 - smoothstep(hi - feather, hi + feather, p);
  return a.x * a.y * b.x * b.y;
}

void main() {
  vec2 p = vec2(vUv.x * 1280.0, (1.0 - vUv.y) * 720.0);
  float t = uTime;

  // ---- 戰爭迷霧：domain-warped fbm，往右上緩流 ----
  vec2 sp = (p + uPar * 6.0) / 720.0;
  float tt = t * 0.045;
  vec2 q = vec2(fbm(sp * 1.8 + vec2(tt * 1.3, -tt)), fbm(sp * 1.8 + vec2(5.2, 1.3) - tt));
  float f = fbm(sp * 2.1 + 2.2 * q + vec2(tt * 2.0, -tt * 1.4));
  float smoke = smoothstep(0.32, 0.82, f);
  float lower = 0.28 + 0.72 * smoothstep(0.30, 1.0, p.y / 720.0);
  float titleKeep = 1.0 - 0.7 * softBox(p, vec2(70.0, 215.0), vec2(800.0, 530.0), 70.0);
  vec2 mv = p - uMouse;
  float glow = exp(-dot(mv, mv) / (2.0 * 130.0 * 130.0)) * uMouseA;
  float sa = smoke * lower * titleKeep * 0.46 * (1.0 + glow * 1.2);
  vec3 col = mix(vec3(0.34, 0.03, 0.04), vec3(0.88, 0.20, 0.08), f * f) * sa;

  // ---- 火星：每層一排欄位，各自向上飄升並左右擺動 ----
  vec3 sparkCol = vec3(0.0);
  for (int i = 0; i < SPARK_LAYERS; i++) {
    float fi = float(i);
    float cols = 24.0 + fi * 10.0;
    vec2 pp = p + vec2(uPar.x * (3.0 + fi * 2.5), uPar.y * (2.0 + fi * 1.5));
    float id = floor(pp.x / 1280.0 * cols);
    for (int k = -1; k <= 1; k++) {
      float cid = id + float(k);
      float r1 = h11(cid * 1.7 + fi * 31.3);
      float r2 = h11(cid * 3.1 + fi * 7.7);
      float r3 = h11(cid * 5.3 + fi * 13.1);
      float speed = 20.0 + r2 * 44.0 + fi * 5.0;
      float life = 240.0 + r3 * 280.0;
      float rise = mod(t * speed + r1 * 1000.0, life);
      float yy = 730.0 - rise;
      float sx = (cid + 0.5 + (r3 - 0.5) * 0.8) / cols * 1280.0
               + sin(t * (0.7 + r2) + r1 * TAU) * (8.0 + r3 * 16.0);
      float size = 1.1 + r2 * 1.5;
      vec2 dv = pp - vec2(sx, yy);
      float fade = 1.0 - rise / life;
      float flick = 0.65 + 0.35 * sin(t * (5.0 + r1 * 8.0) + r2 * 20.0);
      float b = (exp(-dot(dv, dv) / (size * size)) + 0.12 * exp(-length(dv) / (size * 4.0))) * fade * flick;
      sparkCol += mix(vec3(1.0, 0.22, 0.05), vec3(1.0, 0.62, 0.16), fade) * b;
    }
  }
  col += sparkCol * 0.9;

  // ---- 台灣雷達 ----
  vec2 rc = RADAR_C + uPar * 3.0;
  vec2 rp = p - rc;
  float d = length(rp);
  float ang = atan(rp.y, rp.x);
  float inDisc = 1.0 - smoothstep(RADAR_R - 1.0, RADAR_R + 1.0, d);
  float head = t * 1.05;
  float diff = mod(head - ang, TAU);
  float trail = exp(-diff * 1.5) * inDisc;
  float sweepLine = exp(-diff * 70.0) * inDisc;
  float rings = 0.0;
  for (int r = 1; r <= 3; r++) {
    float rr = RADAR_R * float(r) / 3.0;
    rings += exp(-pow((d - rr) / 0.9, 2.0)) * (r == 3 ? 0.55 : 0.28);
  }
  float rip = 0.0;
  for (int k = 0; k < 3; k++) {
    float ph = fract(t * 0.2 + float(k) / 3.0);
    float rr = ph * RADAR_R * 1.12;
    rip += exp(-pow((d - rr) / 1.7, 2.0)) * (1.0 - ph) * 0.9;
  }
  float tickA = ang / TAU * 72.0;
  float rim = 1.0 - smoothstep(RADAR_R, RADAR_R + 1.0, d);
  float tick = step(0.82, fract(tickA)) * smoothstep(RADAR_R - 5.0, RADAR_R - 4.0, d) * rim;
  float longTick = step(0.9, fract(tickA / 3.0)) * smoothstep(RADAR_R - 10.0, RADAR_R - 9.0, d) * rim;
  float cross = (exp(-pow(rp.x / 0.7, 2.0)) + exp(-pow(rp.y / 0.7, 2.0))) * inDisc * 0.16;

  // 島形：point-in-polygon＋到輪廓最短距離
  vec2 ip = p - uPar * 3.0;
  bool inside = false;
  float minD = 1e4;
  for (int i = 0; i < N_PT; i++) {
    vec2 a = ISLAND[i];
    vec2 b = ISLAND[(i + 1) % N_PT];
    if (((a.y > ip.y) != (b.y > ip.y)) && (ip.x < (b.x - a.x) * (ip.y - a.y) / (b.y - a.y) + a.x)) inside = !inside;
    vec2 ab = b - a;
    float h = clamp(dot(ip - a, ab) / dot(ab, ab), 0.0, 1.0);
    minD = min(minD, length(ip - a - ab * h));
  }
  float edge = exp(-pow(minD / 1.5, 2.0));
  float islandFill = inside ? 1.0 : 0.0;
  // 掃描線經過島嶼時整座島亮起
  float islandLit = islandFill * (0.07 + trail * 0.55) + edge * (0.30 + trail * 0.9);

  vec3 teal = vec3(0.10, 0.88, 0.72);
  float radar = (rings + rip + tick * 0.7 + longTick * 0.9 + cross) * 0.55 + trail * 0.30 + sweepLine * 0.8 + islandLit;
  col += teal * radar * 0.8;

  // ---- 滑鼠局部光暈（暖色，幅度小） ----
  col += vec3(1.0, 0.42, 0.18) * glow * 0.16;

  float a = clamp(max(sa, max(col.r, max(col.g, col.b))), 0.0, 1.0);
  col = min(col, vec3(a));
  outColor = vec4(col, a);
}`;

  function fragmentFor(q) {
    return FRAG.replace('#version 300 es', '#version 300 es\n#define OCTAVES ' + q.octaves + '\n#define SPARK_LAYERS ' + q.sparks);
  }

  function readSettings(reducedMotion) {
    let stored = {};
    try { stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') || {}; } catch (e) { stored = {}; }
    return {
      // 明確儲存的設定優先；否則 reduced-motion 預設關閉動態
      motion: typeof stored.motion === 'boolean' ? stored.motion : !reducedMotion,
      quality: stored.quality === 'low' || stored.quality === 'high' ? stored.quality : 'high',
    };
  }

  function writeSettings(s) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ motion: s.motion, quality: s.quality })); } catch (e) { /* 私密模式：只在本次有效 */ }
  }

  function init() {
    const lobby = document.getElementById('lobby');
    const entry = document.getElementById('sfEntry');
    const canvas = document.getElementById('sfFxCanvas');
    const motionBtn = document.getElementById('sfFxMotion');
    const qualityBtns = Array.prototype.slice.call(document.querySelectorAll('[data-sf-fx-quality]'));
    const statusEl = document.getElementById('sfFxStatus');
    if (!lobby || !entry || !canvas) return;

    const mq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
    const settings = readSettings(mq.matches);

    let gl = null;
    let program = null;
    let programKey = '';
    let uniforms = {};
    let raf = 0;
    let lost = false;
    let failed = false;
    let frames = 0;
    let startMs = 0;
    let lastDrawMs = 0;
    const pointer = { x: 0, y: 0, active: false, px: 0, py: 0, parX: 0, parY: 0 };
    const state = { renderW: 0, renderH: 0 };

    const isActive = () => {
      const flow = document.getElementById('startFlow');
      return !!flow && !flow.hidden && !entry.hidden && lobby.dataset.flow === 'start'
        && lobby.dataset.startStep === 'entry' && !document.hidden;
    };

    function setStatus(text) { if (statusEl) statusEl.textContent = text || ''; }
    function setMode(mode) { canvas.parentNode.setAttribute('data-fx', mode); }

    function compile(type, src) {
      const sh = gl.createShader(type);
      gl.shaderSource(sh, src);
      gl.compileShader(sh);
      if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
        const log = gl.getShaderInfoLog(sh);
        gl.deleteShader(sh);
        throw new Error(log || 'shader compile failed');
      }
      return sh;
    }

    function buildProgram() {
      const key = settings.quality;
      if (program && programKey === key) return;
      if (program) gl.deleteProgram(program);
      program = null;
      const vs = compile(gl.VERTEX_SHADER, VERT);
      const fs = compile(gl.FRAGMENT_SHADER, fragmentFor(QUALITY[key]));
      const prog = gl.createProgram();
      gl.attachShader(prog, vs);
      gl.attachShader(prog, fs);
      gl.bindAttribLocation(prog, 0, 'aPos');
      gl.linkProgram(prog);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog) || 'link failed');
      program = prog;
      programKey = key;
      uniforms = {
        time: gl.getUniformLocation(prog, 'uTime'),
        mouse: gl.getUniformLocation(prog, 'uMouse'),
        mouseA: gl.getUniformLocation(prog, 'uMouseA'),
        par: gl.getUniformLocation(prog, 'uPar'),
      };
    }

    function setupGl() {
      gl = canvas.getContext('webgl2', { alpha: true, premultipliedAlpha: true, antialias: false, depth: false, stencil: false, powerPreference: 'low-power' });
      if (!gl) return false;
      const buffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
      gl.enableVertexAttribArray(0);
      gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
      gl.disable(gl.BLEND);
      program = null; programKey = '';
      return true;
    }

    function stageScale() {
      const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--stage-scale'));
      return v > 0 ? v : 1;
    }

    function resize() {
      // low：固定 0.5×；high：跟隨舞台縮放與 DPR，但最高 1.5×，避免高 DPI 螢幕過載。
      const res = settings.quality === 'low'
        ? QUALITY.low.res
        : Math.min(MAX_RENDER_SCALE, Math.max(QUALITY.high.res, stageScale() * (window.devicePixelRatio || 1)));
      const w = Math.round(DESIGN_W * res);
      const h = Math.round(DESIGN_H * res);
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
      state.renderW = w; state.renderH = h;
      if (gl) gl.viewport(0, 0, w, h);
    }

    function draw(timeSec) {
      if (!gl || lost || failed || !program) return;
      gl.useProgram(program);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform1f(uniforms.time, timeSec);
      gl.uniform2f(uniforms.mouse, pointer.px, pointer.py);
      gl.uniform1f(uniforms.mouseA, pointer.active ? 1 : 0);
      gl.uniform2f(uniforms.par, pointer.parX, pointer.parY);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      frames += 1;
    }

    function stopLoop() { if (raf) { cancelAnimationFrame(raf); raf = 0; } }

    function tick(now) {
      raf = 0;
      if (!settings.motion || !isActive() || lost || failed) return;
      // 高更新率螢幕仍限制為最多 60 FPS，避免 shader 在 120／144 Hz 重複執行。
      if (lastDrawMs && now - lastDrawMs < TARGET_FRAME_MS) {
        raf = requestAnimationFrame(tick);
        return;
      }
      lastDrawMs = now;
      // 指標平滑：視差（≤ 1 單位 × shader 內的小係數）與光暈只追蹤小幅位移
      pointer.px += (pointer.x - pointer.px) * 0.12;
      pointer.py += (pointer.y - pointer.py) * 0.12;
      const tx = pointer.active ? (pointer.px / DESIGN_W - 0.5) * 2 : 0;
      const ty = pointer.active ? (pointer.py / DESIGN_H - 0.5) * 2 : 0;
      pointer.parX += (tx - pointer.parX) * 0.06;
      pointer.parY += (ty - pointer.parY) * 0.06;
      draw((now - startMs) / 1000);
      raf = requestAnimationFrame(tick);
    }

    function fail(reason) {
      failed = true;
      stopLoop();
      setMode('fallback');
      setStatus('WebGL2 無法使用（' + reason + '），已改用靜態背景；三個入口不受影響。');
      if (motionBtn) motionBtn.disabled = true;
      qualityBtns.forEach(function (b) { b.disabled = true; });
    }

    function ensureGl() {
      try {
        if (!setupGl()) { fail('不支援'); return false; }
      } catch (e) { fail('初始化失敗'); return false; }
      return true;
    }

    /** 依目前設定與可見性，決定要跑動畫、畫一張靜態影格，或完全停止。 */
    function sync() {
      stopLoop();
      if (failed || lost) return;
      canvas.parentNode.setAttribute('data-fx-motion', settings.motion ? 'on' : 'off');
      if (!isActive()) return;
      if (!gl && !ensureGl()) return;
      try { buildProgram(); } catch (e) { fail('shader'); return; }
      resize();
      if (settings.motion) {
        setMode('animated');
        if (!startMs) startMs = performance.now();
        lastDrawMs = 0;
        raf = requestAnimationFrame(tick);
      } else {
        pointer.parX = 0; pointer.parY = 0;
        setMode('static');
        draw(STATIC_TIME);
      }
    }

    function renderControls() {
      if (motionBtn) {
        motionBtn.setAttribute('aria-checked', String(settings.motion));
        const label = motionBtn.querySelector('.sf-fx-state');
        if (label) label.textContent = settings.motion ? '開' : '關';
      }
      qualityBtns.forEach(function (b) {
        const on = b.dataset.sfFxQuality === settings.quality;
        b.setAttribute('aria-pressed', String(on));
        b.classList.toggle('active', on);
      });
    }

    if (motionBtn) {
      motionBtn.addEventListener('click', function () {
        settings.motion = !settings.motion;
        writeSettings(settings);
        renderControls();
        setStatus('');
        sync();
      });
    }
    qualityBtns.forEach(function (b) {
      b.addEventListener('click', function () {
        const q = b.dataset.sfFxQuality;
        if (q !== 'low' && q !== 'high') return;
        settings.quality = q;
        writeSettings(settings);
        renderControls();
        setStatus('');
        sync();
      });
    });

    // 指標：只記錄位置；canvas 本身 pointer-events:none，所以不會攔截任何按鈕點擊
    lobby.addEventListener('pointermove', function (ev) {
      const r = canvas.getBoundingClientRect();
      if (!r.width) return;
      pointer.x = Math.max(0, Math.min(DESIGN_W, (ev.clientX - r.left) / r.width * DESIGN_W));
      pointer.y = Math.max(0, Math.min(DESIGN_H, (ev.clientY - r.top) / r.height * DESIGN_H));
      if (!pointer.active) { pointer.active = true; pointer.px = pointer.x; pointer.py = pointer.y; }
    });
    lobby.addEventListener('pointerleave', function () { pointer.active = false; });

    canvas.addEventListener('webglcontextlost', function (ev) {
      ev.preventDefault();
      lost = true;
      stopLoop();
      setMode('fallback');
      setStatus('繪圖內容已中斷，暫時使用靜態背景；入口仍可使用。');
    });
    canvas.addEventListener('webglcontextrestored', function () {
      lost = false;
      gl = null;
      setStatus('');
      sync();
    });

    document.addEventListener('visibilitychange', sync);
    window.addEventListener('resize', function () {
      if (!gl || !isActive() || lost || failed) return;
      resize();
      if (!settings.motion) draw(STATIC_TIME);
    });
    if (window.MutationObserver) {
      const mo = new MutationObserver(sync);
      mo.observe(lobby, { attributes: true, attributeFilter: ['data-flow', 'data-start-step'] });
      mo.observe(entry, { attributes: true, attributeFilter: ['hidden'] });
      const flow = document.getElementById('startFlow');
      if (flow) mo.observe(flow, { attributes: true, attributeFilter: ['hidden'] });
    }
    // 使用者沒有明確設定時，作業系統的 reduced-motion 偏好改變也要跟上
    if (mq.addEventListener) {
      mq.addEventListener('change', function () {
        let stored = {};
        try { stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') || {}; } catch (e) { stored = {}; }
        if (typeof stored.motion !== 'boolean') { settings.motion = !mq.matches; renderControls(); sync(); }
      });
    }

    window.RedlineStartFx = {
      getState: function () {
        return {
          motion: settings.motion, quality: settings.quality, mode: canvas.parentNode.getAttribute('data-fx') || '',
          rafActive: raf !== 0, frames: frames, renderWidth: state.renderW, renderHeight: state.renderH,
          failed: failed, lost: lost, config: QUALITY[settings.quality],
        };
      },
    };

    renderControls();
    sync();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
