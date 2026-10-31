"""遊戲配樂的 Browser（Playwright／Chromium）regression，1280×720。

真的 uvicorn＋真實 index.html／game_music.js；Joy-Con 是 mock bridge WebSocket（synthetic frame，不是實體 Joy-Con 驗證）。
Playwright 的 Chromium 不一定帶 AAC 解碼器、headless 也沒有真的音訊輸出，所以 HTMLMediaElement.play／pause／paused 以 init script
換成可觀察的 stub（記錄呼叫次數與播放狀態）；檔案本身另以 HTTP 驗證同源、MIME 與大小。

驗證：預設 30%、遊戲選單 UI（−／＋／即時百分比）、10% step、0／100 邊界、localStorage 持久化與無效值正規化、
只在遊戲畫面播放（大廳不播、離開暫停、回來繼續）、autoplay 限制（可信任互動前不呼叫 play()、被拒絕後不重複）、
音量 0 保持暫停且不呼叫 play()、交接遮罩（舞台 visibility:hidden）不中斷音樂、Joy-Con 方向＋A 調整音量且 B／scope lock 不破壞。
"""
from __future__ import annotations

import json
import time

import requests

from test_game_menu_button_browser import (  # noqa: F401  (app_url／browser 是 pytest fixture)
    MOCK_BRIDGE, activate_pad, app_url, browser, menu_open, open_game, press, ring_to_menu, shown,
)
from test_propagandist_joycon_browser import pad, settle, wait_until
from test_stick_game_menu_browser import stick  # y>0＝畫面向下（controller_core.stickDirection）；propagandist 的 stick 方向表不同

STORAGE_KEY = "redline.music.volume.v1"
TRACK = "/static/audio/redline-theme.m4a"

AUDIO_STUB = """(() => {
  window.__audioLog = { play: 0, pause: 0, reject: null };
  const proto = HTMLMediaElement.prototype;
  proto.play = function () {
    window.__audioLog.play += 1;
    if (window.__audioLog.reject) return Promise.reject(Object.assign(new Error('blocked'), { name: window.__audioLog.reject }));
    this.__playing = true;
    return Promise.resolve();
  };
  proto.pause = function () { window.__audioLog.pause += 1; this.__playing = false; };
  Object.defineProperty(proto, 'paused', { get() { return !this.__playing; }, configurable: true });
})();"""


def storage_init(value):
    return f"try {{ if (!sessionStorage.getItem('__seeded')) {{ localStorage.setItem({json.dumps(STORAGE_KEY)}, {json.dumps(value)}); sessionStorage.setItem('__seeded', '1'); }} }} catch (e) {{}}"


def music(page):
    return page.evaluate("""() => { const m = window.__redlineGameMusic; const a = m.audio;
      return { volume: m.player.volume(), element: a.volume, paused: a.paused, loop: a.loop, src: new URL(a.src).pathname,
               play: window.__audioLog.play, pause: window.__audioLog.pause, state: m.player.state(),
               label: document.getElementById('gameMenuVolumeValue').textContent,
               stored: localStorage.getItem('redline.music.volume.v1') }; }""")


def trusted_click(page):
    page.mouse.click(640, 360)  # 真的滑鼠事件（isTrusted）＝使用者互動
    time.sleep(0.2)


def open_menu_by_mouse(page):
    page.click("#gameMenuBtn")
    assert wait_until(lambda: menu_open(page))


def test_asset_is_local_audio_and_not_remote(app_url):
    r = requests.get(app_url + TRACK, timeout=10)
    assert r.status_code == 200 and r.headers["content-type"].startswith("audio/mp4"), r.headers
    assert len(r.content) > 1_000_000 and r.content[4:8] == b"ftyp"
    html = requests.get(app_url + "/", timeout=10).text
    assert "/static/game_music.js?v=game-menu-music-20261031" in html
    src = requests.get(app_url + "/static/game_music.js", timeout=10).text
    assert "http://" not in src.split("TRACK_SRC")[1].split("\n")[0] and "cdn" not in src.lower()


def test_defaults_menu_ui_steps_bounds_and_persistence(browser, app_url):
    page = open_game(browser, app_url, with_pad=False, extra_init=[AUDIO_STUB])
    try:
        m = music(page)
        assert m["volume"] == 30 and m["label"] == "30%" and abs(m["element"] - 0.3) < 1e-9, m
        assert m["loop"] is True and m["src"] == TRACK, m
        assert m["play"] == 0 and m["paused"] is True, m  # 還沒有可信任互動：不呼叫 play()（autoplay 限制）
        trusted_click(page)
        m = music(page)
        assert m["play"] == 1 and m["paused"] is False, m  # 遊戲畫面＋互動後開始循環播放

        open_menu_by_mouse(page)
        ui = page.evaluate("""() => { const q = id => document.getElementById(id); const r = id => q(id).getBoundingClientRect();
          return { label: q('gameMenuVolumeLabel').textContent, down: q('gameMenuVolumeDownBtn').getAttribute('aria-label'),
                   up: q('gameMenuVolumeUpBtn').getAttribute('aria-label'), value: q('gameMenuVolumeValue').textContent,
                   downR: r('gameMenuVolumeDownBtn').left, upR: r('gameMenuVolumeUpBtn').left, valueR: r('gameMenuVolumeValue').left,
                   glass: r('gameMenuVolume').width, insideStage: r('gameMenuVolume').bottom <= innerHeight && r('gameMenuVolume').top >= 0 }; }""")
        assert ui["label"] == "配樂音量" and "降低" in ui["down"] and "提高" in ui["up"] and ui["value"] == "30%", ui
        assert ui["downR"] < ui["valueR"] < ui["upR"] and ui["insideStage"], ui

        page.click("#gameMenuVolumeUpBtn")
        m = music(page)
        assert (m["volume"], m["label"], m["stored"]) == (40, "40%", "40") and abs(m["element"] - 0.4) < 1e-9, m
        page.click("#gameMenuVolumeDownBtn")
        page.click("#gameMenuVolumeDownBtn")
        assert music(page)["label"] == "20%"
        plays_before = music(page)["play"]
        for _ in range(4):  # 20 → 10 → 0 → 0 → 0
            page.click("#gameMenuVolumeDownBtn")
        m = music(page)
        assert (m["volume"], m["label"], m["stored"], m["paused"]) == (0, "0%", "0", True), m
        assert m["play"] == plays_before, m  # 音量 0：暫停，之後不再呼叫 play()
        page.click("#gameMenuVolumeUpBtn")
        m = music(page)
        assert (m["volume"], m["paused"]) == (10, False) and m["play"] == plays_before + 1, m
        for _ in range(12):
            page.click("#gameMenuVolumeUpBtn")
        m = music(page)
        assert (m["volume"], m["label"], m["stored"], m["element"]) == (100, "100%", "100", 1), m
        page.screenshot(path="/tmp/game_menu_volume_100_1280x720.png")

        # 重新載入：持久化（頁面載入時還在遊戲外，所以 stub 的記數歸零）
        page.evaluate("localStorage.setItem('redline.music.volume.v1', '60')")
        page.reload()
        page.wait_for_function("window.__redlineGameMusic")
        assert music(page)["volume"] == 60 and music(page)["label"] == "60%"
    finally:
        page.context.close()


def test_invalid_stored_values_are_normalized(browser, app_url):
    for raw, expected in [("garbage", 30), ("250", 100), ("-5", 0), ("34", 30), ("", 30), ("NaN", 30)]:
        page = open_game(browser, app_url, with_pad=False, extra_init=[AUDIO_STUB, storage_init(raw)])
        try:
            m = music(page)
            assert (m["volume"], m["label"]) == (expected, f"{expected}%"), (raw, m)
            if expected == 0:
                trusted_click(page)
                assert music(page)["play"] == 0 and music(page)["paused"] is True
        finally:
            page.context.close()


def test_plays_only_in_game_pauses_when_leaving_and_survives_handoff_mask(browser, app_url):
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    ctx.add_init_script(AUDIO_STUB)
    page = ctx.new_page()
    try:
        page.goto(app_url + "/?display=desktop")
        page.wait_for_function("window.__redlineGameMusic")
        trusted_click(page)
        time.sleep(0.3)
        log = page.evaluate("window.__audioLog")
        assert log["play"] == 0, log  # 大廳／開始流程：即使有使用者互動也不播
        assert not shown(page, "gameShell")
        ctx.close()

        page = open_game(browser, app_url, with_pad=False, extra_init=[AUDIO_STUB])
        ctx = page.context
        trusted_click(page)
        assert wait_until(lambda: music(page)["paused"] is False)
        # 交接遮罩（舞台 visibility:hidden）不中斷音樂，音樂也不依賴遊戲 state
        page.evaluate("document.documentElement.dataset.hotseat = 'masked'; document.getElementById('designStage').style.visibility = 'hidden'")
        time.sleep(0.4)
        m = music(page)
        assert m["paused"] is False and m["pause"] == 0, m
        page.evaluate("delete document.documentElement.dataset.hotseat; document.getElementById('designStage').style.visibility = ''")
        # 切回非遊戲畫面 → 暫停；回到遊戲 → 繼續（同一個元素）
        page.evaluate("document.getElementById('gameShell').style.display = 'none'")
        assert wait_until(lambda: music(page)["paused"] is True), music(page)
        plays = music(page)["play"]
        page.evaluate("document.getElementById('gameShell').style.display = ''; document.getElementById('gameShell').style.display = 'block'")
        assert wait_until(lambda: music(page)["paused"] is False), music(page)
        assert music(page)["play"] == plays + 1
        # 開始流程可見時（例如重新開始）：暫停
        page.evaluate("window.__lobbyDisplay = document.getElementById('lobby').style.display; "
                      "document.getElementById('lobby').style.display = 'block'; document.getElementById('startFlow').hidden = false")
        assert wait_until(lambda: music(page)["paused"] is True), music(page)
        page.evaluate("document.getElementById('startFlow').hidden = true; document.getElementById('lobby').style.display = window.__lobbyDisplay")
        assert wait_until(lambda: music(page)["paused"] is False), music(page)
    finally:
        ctx.close()


def test_autoplay_rejection_is_not_retried_until_next_trusted_interaction(browser, app_url):
    page = open_game(browser, app_url, with_pad=False, extra_init=[AUDIO_STUB])
    try:
        page.evaluate("window.__audioLog.reject = 'NotAllowedError'")
        trusted_click(page)
        assert music(page)["play"] == 1 and music(page)["paused"] is True
        for _ in range(5):
            page.evaluate("window.__redlineGameMusic.player.sync(); window.__redlineGameMusic.refresh()")
        page.evaluate("window.__redlineGameMusic.player.stepVolume(1); window.__redlineGameMusic.player.stepVolume(-1)")
        time.sleep(0.3)
        assert music(page)["play"] == 1, music(page)  # 沒有新的使用者互動：不重試
        page.evaluate("window.__audioLog.reject = null")
        trusted_click(page)
        m = music(page)
        assert m["play"] == 2 and m["paused"] is False, m
    finally:
        page.context.close()


def focus_sig(page):
    return pad(page)["focusSig"]


def test_joycon_adjusts_volume_with_direction_and_a_and_keeps_scope_lock(browser, app_url):
    page = open_game(browser, app_url, extra_init=[AUDIO_STUB])
    try:
        trusted_click(page)
        activate_pad(page)
        ring_to_menu(page, "R")
        press(page, "A")
        assert wait_until(lambda: menu_open(page)), pad(page)
        settle(page, "desktop")
        assert pad(page)["scope"] == "gameMenuModal" and focus_sig(page) == "#gameMenuResumeBtn", pad(page)
        stick(page, "down")
        stick(page, "down")
        assert focus_sig(page) == "#gameMenuVolumeDownBtn", focus_sig(page)
        # 左右在 − / + 之間移動（可清楚聚焦）
        stick(page, "left")
        assert focus_sig(page) == "#gameMenuVolumeDownBtn"  # 左端不循環
        stick(page, "right")
        assert focus_sig(page) == "#gameMenuVolumeUpBtn"
        assert page.evaluate("document.activeElement.id") == "gameMenuVolumeUpBtn" or page.evaluate("document.querySelector('.rl-pad-focus')?.id") == "gameMenuVolumeUpBtn"
        assert music(page)["volume"] == 30
        press(page, "A")
        assert music(page)["volume"] == 40 and music(page)["label"] == "40%" and music(page)["stored"] == "40", music(page)
        assert menu_open(page) and focus_sig(page) == "#gameMenuVolumeUpBtn"
        stick(page, "left")
        for expected in (30, 20, 10, 0, 0):  # 到 0% 不再變化，焦點仍在按鈕上
            press(page, "A")
            assert music(page)["volume"] == expected, (expected, music(page))
        m = music(page)
        assert m["paused"] is True and focus_sig(page) == "#gameMenuVolumeDownBtn" and menu_open(page), m
        plays = m["play"]
        stick(page, "right")
        press(page, "A")
        m = music(page)
        assert m["volume"] == 10 and m["paused"] is False and m["play"] == plays + 1, m
        # scope lock 不被破壞：R／SR／SL／X／Y 都被吞掉；選單仍開著
        for key in ("R", "SR", "SL"):
            press(page, key)
            assert menu_open(page) and pad(page)["scope"] == "gameMenuModal", key
        assert music(page)["volume"] == 10
        # 上下仍可離開音量列；B 返回遊戲並回到導覽列按鈕焦點
        stick(page, "down")
        assert focus_sig(page) == "#gameMenuRestartBtn", focus_sig(page)
        press(page, "B")
        assert wait_until(lambda: not menu_open(page))
        settle(page, "desktop")
        assert pad(page)["focusKind"] == "menuEntry", pad(page)
        assert music(page)["volume"] == 10 and music(page)["stored"] == "10"
    finally:
        page.context.close()
