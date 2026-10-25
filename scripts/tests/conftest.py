import os

# server/main.py gates /test/* HTTP routes behind ENABLE_TEST_ROUTES (off by
# default so production doesn't expose live-state-mutating endpoints). The
# suite here exercises those routes directly, so opt in before any test
# module imports server.main. setdefault() leaves an explicit env value
# (e.g. a developer forcing it off) untouched.
os.environ.setdefault("ENABLE_TEST_ROUTES", "true")


def host_token(game_id, player_id):
    """resume_token of a seat created through /create or /join (lobby mutations are token-gated)."""
    from server import main

    return main.lobby_player_credentials[game_id][player_id]["resume_token"]


# 起始畫面導覽（static/controller_ui.js setStartNav）在搖桿控制未啟用時也會連 bridge 預設位址 ws://127.0.0.1:8000/ws，
# 而 bridge 接受任何 loopback Origin。測試的 Browser 不可連到開發機上常駐的 Joy-Con bridge（會 claim 使用者的實體手把）：
# 所有 pytest 建立的 Playwright context 一律把 8000 埠的 WebSocket 換成不連到伺服器、也不送任何訊息的 mock
# （handler 內不可呼叫 sync API 的 ws.close()，會卡住 Playwright 事件迴圈）。測試自己的 mock bridge 用隨機埠，不受影響。
_RESIDENT_BRIDGE_WS = __import__("re").compile(r"^wss?://(127\.0\.0\.1|localhost|\[::1\]):8000(/|$)")


def _isolate_resident_bridge():
    try:
        from playwright.sync_api import Browser
    except ImportError:
        return
    if getattr(Browser.new_context, "_redline_isolated", False):
        return
    original = Browser.new_context

    def new_context(self, *args, **kwargs):
        context = original(self, *args, **kwargs)
        context.route_web_socket(_RESIDENT_BRIDGE_WS, lambda ws: None)
        return context

    new_context._redline_isolated = True
    Browser.new_context = new_context


_isolate_resident_bridge()
