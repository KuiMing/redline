"""macOS App launcher 的關鍵行為：選埠、health wait、子行程清理、單一實例、test routes 關閉。

全部在 POSIX 上可跑，不需要 pywebview／PyInstaller（launcher 只在開視窗時才 import webview）。
"""

import asyncio
import http.client
import importlib.util
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.macos_app import launcher, security, settings  # noqa: E402


@pytest.fixture
def paths(tmp_path):
    return launcher.AppPaths.resolve({"REDLINE_APP_STATE_DIR": str(tmp_path)})


@pytest.fixture
def listener():
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    yield sock
    sock.close()


def free_port():
    return launcher.ephemeral_port()


def serve(status=200, body=b"{}", port=0):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def pid_gone(pid, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


# ---------------------------------------------------------------- ports


def test_port_with_listener_is_not_available(listener):
    port = listener.getsockname()[1]
    assert not launcher.is_port_available(port)
    listener.close()
    assert launcher.is_port_available(port)


def test_wildcard_listener_counts_as_occupied():
    # macOS 上 SO_REUSEADDR 可以再綁 127.0.0.1:port，只測 bind 會把 *:port 的服務蓋掉。
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", 0))
        sock.listen()
        assert not launcher.is_port_available(sock.getsockname()[1])


def test_choose_port_skips_occupied_and_excluded(listener):
    occupied = listener.getsockname()[1]
    excluded, expected = free_port(), free_port()
    assert launcher.choose_port([occupied, excluded, expected], exclude=[excluded]) == expected


def test_choose_port_falls_back_to_ephemeral(listener):
    occupied = listener.getsockname()[1]
    chosen = launcher.choose_port([occupied])
    assert chosen != occupied and launcher.is_port_available(chosen)


# ---------------------------------------------------------------- health wait


def test_wait_for_http_waits_for_late_server():
    port = free_port()
    servers = []
    timer = threading.Timer(0.3, lambda: servers.append(serve(port=port)))
    timer.start()
    try:
        launcher.wait_for_http(f"http://127.0.0.1:{port}/", timeout=5.0)
        assert servers
    finally:
        timer.join()
        for server in servers:
            server.shutdown()


def test_wait_for_http_raises_when_child_exits():
    with pytest.raises(launcher.ChildExited):
        launcher.wait_for_http(f"http://127.0.0.1:{free_port()}/", timeout=5.0, is_alive=lambda: False)


def test_wait_for_http_does_not_accept_error_status():
    server = serve(status=500)
    try:
        with pytest.raises(launcher.HealthTimeout):
            launcher.wait_for_http(f"http://127.0.0.1:{server.server_port}/", timeout=0.4)
    finally:
        server.shutdown()


# ---------------------------------------------------------------- process cleanup


def spawn_python(code, log_path):
    return launcher.ManagedProcess("test", [sys.executable, "-c", code], log_path)


def test_stop_terminates_child(tmp_path):
    child = spawn_python("import time; time.sleep(60)", tmp_path / "c.log")
    child.stop()
    assert not child.alive() and child.process.returncode == -signal.SIGTERM


def test_stop_escalates_to_sigkill(tmp_path):
    code = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('up', flush=True); time.sleep(60)"
    child = spawn_python(code, tmp_path / "c.log")
    deadline = time.monotonic() + 10
    while b"up" not in (tmp_path / "c.log").read_bytes() and time.monotonic() < deadline:
        time.sleep(0.02)
    child.stop(grace=0.2)
    assert child.process.returncode == -signal.SIGKILL


def test_stop_cleans_process_group(tmp_path):
    code = (
        "import subprocess,sys,time;"
        "p=subprocess.Popen([sys.executable,'-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)']);"
        "print(p.pid,flush=True);time.sleep(60)"
    )
    child = spawn_python(code, tmp_path / "c.log")
    deadline = time.monotonic() + 10
    while not (tmp_path / "c.log").read_text().strip() and time.monotonic() < deadline:
        time.sleep(0.02)
    grandchild = int((tmp_path / "c.log").read_text().strip())
    time.sleep(0.3)
    child.stop()
    assert pid_gone(grandchild)


def test_watchdog_stops_child_when_launcher_is_killed():
    # launcher 被 SIGKILL 時 NSApp／finally 都不會執行，只能靠 child 自己發現。
    child_code = (
        "import os,time;"
        "from tools.macos_app.launcher import start_parent_watchdog;"
        "print(os.getpid(),flush=True);start_parent_watchdog(os.getppid(),0.05);time.sleep(60)"
    )
    parent_code = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{child_code!r}],cwd={str(REPO_ROOT)!r});time.sleep(60)"
    )
    parent = subprocess.Popen([sys.executable, "-c", parent_code], stdout=subprocess.PIPE, text=True)
    child_pid = int(parent.stdout.readline())
    parent.kill()
    parent.wait()
    parent.stdout.close()
    assert pid_gone(child_pid)


# ---------------------------------------------------------------- supervisor


FAKE_CHILD = """
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
port, bad = int(sys.argv[1]), [int(p) for p in sys.argv[2].split(",") if p]
if port in bad:
    sys.exit(1)
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"{}")
    def log_message(self, *a): pass
HTTPServer(("127.0.0.1", port), H).serve_forever()
"""


def use_fake_children(monkeypatch, candidates, failing=()):
    monkeypatch.setattr(launcher, "GAME_PORT_CANDIDATES", tuple(candidates))
    bad = ",".join(str(p) for p in failing)
    monkeypatch.setattr(launcher, "child_command", lambda role, port, host, pid: [sys.executable, "-c", FAKE_CHILD, str(port), bad])


def test_server_retries_on_next_port_when_child_cannot_bind(monkeypatch, paths):
    first, second = free_port(), free_port()
    use_fake_children(monkeypatch, [first, second], failing=[first])
    supervisor = launcher.Supervisor(paths)
    try:
        assert supervisor.start_server() == second
        assert supervisor.server.alive()
    finally:
        supervisor.stop()
    assert not supervisor.server.alive()
    assert launcher.is_port_available(second)


def test_server_gives_up_with_visible_error(monkeypatch, paths):
    ports = [free_port() for _ in range(launcher.SERVER_START_ATTEMPTS)]
    use_fake_children(monkeypatch, ports, failing=ports)
    # 候選耗盡前就達到重試上限，不會無限重啟。
    with pytest.raises(launcher.StartupError):
        launcher.Supervisor(paths).start_server()


def test_stop_during_startup_is_not_reported_as_failure(monkeypatch, paths):
    port = free_port()
    use_fake_children(monkeypatch, [port], failing=[port])
    supervisor = launcher.Supervisor(paths)
    supervisor.stopping.set()
    with pytest.raises(launcher.ShutdownRequested):
        supervisor.start_server()


def test_stop_is_idempotent(monkeypatch, paths):
    port = free_port()
    use_fake_children(monkeypatch, [port])
    supervisor = launcher.Supervisor(paths)
    supervisor.start_server()
    supervisor.stop()
    supervisor.stop()
    assert not supervisor.server.alive()


def test_existing_joycon_bridge_is_reused_and_left_alone(paths):
    server = serve(body=json.dumps({"ok": True, "packets": 0}).encode())
    try:
        env = {"REDLINE_APP_BRIDGE_PORT": str(server.server_port)}
        supervisor = launcher.Supervisor(paths, env=env)
        bridge = supervisor.spawn_bridge()
        assert (bridge.mode, bridge.port, bridge.process) == ("reused", server.server_port, None)
        supervisor.stop()
        assert launcher.is_joycon_bridge(server.server_port)
    finally:
        server.shutdown()


def test_bridge_moves_when_port_is_taken_by_another_program(monkeypatch, paths):
    server = serve(body=b"not a bridge")
    fallback = free_port()
    monkeypatch.setattr(launcher, "BRIDGE_FALLBACK_PORTS", (fallback,))
    use_fake_children(monkeypatch, [])
    supervisor = launcher.Supervisor(paths, env={**os.environ, "REDLINE_APP_BRIDGE_PORT": str(server.server_port)})
    try:
        bridge = supervisor.spawn_bridge()
        assert (bridge.mode, bridge.port) == ("spawned", fallback)
        supervisor.wait_for_bridge()
        assert supervisor.bridge.mode == "spawned"
    finally:
        supervisor.stop()
        server.shutdown()


def test_bridge_failure_does_not_stop_the_game(monkeypatch, paths):
    port = free_port()
    use_fake_children(monkeypatch, [], failing=[port])
    supervisor = launcher.Supervisor(paths, env={**os.environ, "REDLINE_APP_BRIDGE_PORT": str(port)})
    supervisor.spawn_bridge()
    supervisor.wait_for_bridge()
    assert supervisor.bridge.mode == "failed" and supervisor.bridge.url is None


# ---------------------------------------------------------------- single instance


def test_instance_lock_is_exclusive_and_released(paths):
    first, second = launcher.InstanceLock(paths), launcher.InstanceLock(paths)
    assert first.acquire()
    first.publish({"pid": 123})
    assert not second.acquire()
    assert second.read_info() == {"pid": 123}
    first.release()
    assert not paths.instance_file.exists()
    assert second.acquire()
    second.release()


# ---------------------------------------------------------------- production settings


def test_child_env_forces_test_routes_off():
    assert launcher.child_env({"ENABLE_TEST_ROUTES": "true"})["ENABLE_TEST_ROUTES"] == "false"


def test_real_server_child_serves_health_without_test_routes(tmp_path):
    port = free_port()
    env = {**os.environ, "ENABLE_TEST_ROUTES": "true"}
    command = [sys.executable, "-m", "tools.macos_app", "--redline-child", "server", "--port", str(port)]
    child = launcher.ManagedProcess("server", command, tmp_path / "server.log", env=env, cwd=REPO_ROOT)
    try:
        launcher.wait_for_http(f"http://127.0.0.1:{port}/server-info", 60.0, child.alive)
        status, body = launcher.http_request(f"http://127.0.0.1:{port}/openapi.json")
        assert status == 200
        assert not [path for path in json.loads(body)["paths"] if path.startswith("/test")]
        assert launcher.http_request(f"http://127.0.0.1:{port}/static/app.js")[0] == 200
    finally:
        child.stop()
    assert launcher.is_port_available(port)


# ---------------------------------------------------------------- misc


def test_parser_tolerates_launchservices_arguments():
    args, _ = launcher.build_parser().parse_known_args(["-psn_0_12345"])
    assert not args.smoke and not args.smoke_gui and args.redline_child is None


# ---------------------------------------------------------------- Host / Origin guard


PORT = 18100
GOOD_HOST = f"127.0.0.1:{PORT}"


@pytest.mark.parametrize(
    "hosts,origins",
    [
        ([GOOD_HOST], []),
        ([f"localhost:{PORT}"], []),
        ([f"LOCALHOST:{PORT}"], []),
        ([GOOD_HOST], [f"http://127.0.0.1:{PORT}"]),
        ([f"localhost:{PORT}"], [f"http://localhost:{PORT}"]),
    ],
)
def test_guard_allows_loopback_clients_and_same_origin_pages(hosts, origins):
    assert security.rejection_reason(hosts, origins, PORT) is None


@pytest.mark.parametrize(
    "hosts,origins",
    [
        (["evil.example"], []),  # DNS rebinding
        ([f"evil.example:{PORT}"], []),
        ([f"127.0.0.1.evil.example:{PORT}"], []),
        (["127.0.0.1"], []),  # 預設埠不是這個 server
        ([f"127.0.0.1:{PORT + 1}"], []),
        ([f"192.168.1.20:{PORT}"], []),
        ([], []),
        ([GOOD_HOST, "evil.example"], []),
        ([GOOD_HOST], ["https://evil.example"]),
        ([GOOD_HOST], ["null"]),
        ([GOOD_HOST], [f"http://127.0.0.1:{PORT + 1}"]),  # 本機其他服務的網頁
        ([GOOD_HOST], [f"https://127.0.0.1:{PORT}"]),
        ([GOOD_HOST], [f"http://127.0.0.1:{PORT}.evil.example"]),
        ([GOOD_HOST], [f"http://localhost:{PORT}"]),  # 跨 origin
        ([GOOD_HOST], [f"http://127.0.0.1:{PORT}", "https://evil.example"]),
    ],
)
def test_guard_rejects_hostile_host_and_origin(hosts, origins):
    assert security.rejection_reason(hosts, origins, PORT) is not None


@pytest.mark.parametrize(
    "host",
    ["192.168.1.20:18100", "10.0.0.5:18100", "127.0.0.1:18100", "localhost:18100", "[fe80::1]:18100", "[2001:db8::1]:18100", "[::1]:18100"],
)
def test_guard_lan_mode_accepts_ip_literals_with_same_origin(host):
    assert security.rejection_reason([host], [], PORT, loopback_only=False) is None
    assert security.rejection_reason([host], [f"http://{host}"], PORT, loopback_only=False) is None


@pytest.mark.parametrize(
    "host",
    [
        "evil.example:18100",  # DNS rebinding：Host 與 Origin 都是攻擊者的網域
        "192.168.1.20.evil.example:18100",
        "foo.localhost:18100",
        "192.168.1.20:18101",
        "192.168.1.20",
        "192.168.1.20:018100",
        "2130706433:18100",  # 整數形式的 IP
        "0x7f.0.0.1:18100",
        "127.1:18100",
        "192.168.001.020:18100",
        "::1:18100",  # IPv6 必須加方括號
        "[192.168.1.20]:18100",  # IPv4 不能加方括號
        "[fe80::1%en0]:18100",
        "0.0.0.0:18100",
        "[::]:18100",
        "224.0.0.1:18100",
        ":18100",
        "",
    ],
)
def test_guard_lan_mode_rejects_dns_names_and_malformed_hosts(host):
    # 同源也不行：這正是 DNS rebinding 的樣子。
    assert security.rejection_reason([host], [f"http://{host}"], PORT, loopback_only=False) is not None
    assert security.rejection_reason([host], [], PORT, loopback_only=False) is not None


def test_guard_lan_mode_requires_exact_same_origin():
    host = "192.168.1.20:18100"
    for origin in ("https://evil.example", "null", "https://192.168.1.20:18100", "http://192.168.1.21:18100", "http://192.168.1.20:18101"):
        assert security.rejection_reason([host], [origin], PORT, loopback_only=False) is not None


def test_loopback_mode_still_rejects_lan_ip_literals():
    assert security.rejection_reason(["192.168.1.20:18100"], [], PORT) is not None


def run_guard(scope_type, headers):
    calls, sent = [], []

    async def app(scope, receive, send):
        calls.append(scope["type"])

    async def receive():
        return {"type": f"{scope_type}.connect"}

    async def send(message):
        sent.append(message)

    guard = security.HostOriginGuard(app, port=PORT)
    asyncio.run(guard({"type": scope_type, "headers": headers}, receive, send))
    return calls, sent


def test_guard_never_reaches_the_app_for_hostile_requests():
    calls, sent = run_guard("http", [(b"host", b"evil.example")])
    assert not calls and sent[0]["status"] == 403
    calls, sent = run_guard("websocket", [(b"host", GOOD_HOST.encode()), (b"origin", b"https://evil.example")])
    assert not calls and sent == [{"type": "websocket.close", "code": 1008}]


def test_guard_passes_allowed_requests_and_lifespan():
    assert run_guard("http", [(b"host", GOOD_HOST.encode())])[0] == ["http"]
    assert run_guard("lifespan", [])[0] == ["lifespan"]


def raw_websocket_status(port, host, origin=None):
    request = [
        "GET /ws/nonexistent/nobody HTTP/1.1", f"Host: {host}", "Upgrade: websocket", "Connection: Upgrade",
        "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==", "Sec-WebSocket-Version: 13",
    ]
    if origin:
        request.append(f"Origin: {origin}")
    with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
        sock.sendall(("\r\n".join(request) + "\r\n\r\n").encode())
        return int(sock.makefile("rb").readline().split()[1])


def raw_http_status(port, host, origin=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Host": host}
    if origin:
        headers["Origin"] = origin
    connection.request("GET", "/server-info", headers=headers)
    status = connection.getresponse().status
    connection.close()
    return status


def test_real_server_child_rejects_hostile_host_and_origin(tmp_path):
    port = free_port()
    command = [sys.executable, "-m", "tools.macos_app", "--redline-child", "server", "--port", str(port)]
    child = launcher.ManagedProcess("server", command, tmp_path / "server.log", env=dict(os.environ), cwd=REPO_ROOT)
    good = f"127.0.0.1:{port}"
    try:
        launcher.wait_for_http(f"http://{good}/server-info", 60.0, child.alive)
        assert raw_http_status(port, good) == 200
        assert raw_http_status(port, f"localhost:{port}", f"http://localhost:{port}") == 200
        assert raw_http_status(port, good, f"http://{good}") == 200
        assert raw_http_status(port, "evil.example") == 403
        assert raw_http_status(port, good, "https://evil.example") == 403
        assert raw_websocket_status(port, good) == 101
        assert raw_websocket_status(port, good, f"http://{good}") == 101
        assert raw_websocket_status(port, "evil.example") == 403
        assert raw_websocket_status(port, good, "https://evil.example") == 403
    finally:
        child.stop()
    log_text = (tmp_path / "server.log").read_text()
    assert "evil.example" not in log_text and "/ws/nonexistent" not in log_text


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "packaging/macos" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_real_server_child_lan_mode_rejects_rebinding_over_http_and_websocket(tmp_path):
    # 跑 smoke_test 實際使用的檢查，確保它與 guard 的行為一致。
    smoke_test = load_script("smoke_test")
    port = free_port()
    command = [sys.executable, "-m", "tools.macos_app", "--redline-child", "server", "--port", str(port), "--bind-host", "0.0.0.0"]
    child = launcher.ManagedProcess("server", command, tmp_path / "server.log", env=dict(os.environ), cwd=REPO_ROOT)
    try:
        launcher.wait_for_http(f"http://127.0.0.1:{port}/server-info", 60.0, child.alive)
        smoke_test.assert_lan_guard(port)
    finally:
        child.stop()


# ---------------------------------------------------------------- third-party notices


def test_nested_notices_finds_vendored_licenses_and_ignores_binaries():
    notices = load_script("generate_third_party_notices")
    paths = [
        ("setuptools-1.0.dist-info", "licenses", "LICENSE"),
        ("setuptools", "_vendor", "jaraco.text-4.0.0.dist-info", "LICENSE"),
        ("setuptools", "_vendor", "tomli-2.4.0.dist-info", "licenses", "LICENSE"),
        ("setuptools", "_vendor", "tomli-2.4.0.dist-info", "METADATA"),
        ("setuptools", "config", "NOTICE"),
        ("setuptools", "license.py"),
        ("PyObjCTest", "copying.cpython-311-darwin.so"),
        ("PyObjCTest", "copying.cpython-311-darwin.so.dSYM", "Contents", "Resources", "DWARF", "copying.cpython-311-darwin.so"),
    ]
    vendored, embedded = notices.nested_notices(paths)
    assert [(name, version) for name, version, _ in vendored] == [("jaraco.text", "4.0.0"), ("tomli", "2.4.0")]
    assert embedded == [("setuptools", "config", "NOTICE")]


def test_bundled_vendor_modules_are_matched_to_notices():
    notices = load_script("generate_third_party_notices")
    toc = "('setuptools._vendor.jaraco.text', 'x', 'PYMODULE'), ('setuptools._vendor.tomli', 'x', 'PYMODULE'), ('tomllib', 'x', 'PYMODULE')"
    assert notices.bundled_vendor_modules(toc) == {"jaraco", "tomli"}
    listed = "--- vendored: jaraco.text 4.0.0 (setuptools/_vendor/x) ---\n--- vendored: tomli 2.4.0 (y) ---\n"
    assert notices.missing_vendor_notices({"jaraco", "tomli"}, listed) == []
    assert notices.missing_vendor_notices({"jaraco", "tomli", "zipp"}, listed) == ["zipp"]
    # 只出現在正文或路徑中不算。
    assert notices.missing_vendor_notices({"tomli"}, "see tomli and setuptools/_vendor/tomli\n") == ["tomli"]


def test_committed_notices_cover_setuptools_vendors_with_attribution():
    notices = load_script("generate_third_party_notices")
    text = (REPO_ROOT / "packaging/macos/THIRD-PARTY-NOTICES.txt").read_text(encoding="utf-8")
    modules = {"autocommand", "backports", "importlib_metadata", "jaraco", "more_itertools", "packaging", "platformdirs", "tomli", "wheel", "zipp"}
    assert notices.missing_vendor_notices(modules, text) == []
    for module in ("jaraco.text", "jaraco_context", "jaraco_functools", "backports.tarfile"):
        assert f"--- vendored: {module} " in text
    assert "(setuptools/_vendor/packaging-" in text and "setuptools/config/NOTICE" in text


# ---------------------------------------------------------------- bundle structure


def test_card_art_assertion_detects_missing_files(tmp_path):
    smoke_test = load_script("smoke_test")
    source, resources = tmp_path / "source", tmp_path / "Resources"
    for root in (source, resources / "static/card-art"):
        for name in smoke_test.CARD_ART_DIRS:
            (root / name).mkdir(parents=True)
            (root / name / "a.png").write_bytes(b"x")
    smoke_test.assert_card_art_bundled(resources, source)
    (resources / "static/card-art/actions/a.png").unlink()
    with pytest.raises(smoke_test.Failure):
        smoke_test.assert_card_art_bundled(resources, source)


def test_spec_bundles_the_whole_static_tree():
    spec = (REPO_ROOT / "packaging/macos/REDLINE.spec").read_text(encoding="utf-8")
    assert '(str(ROOT / "static"), "static")' in spec and "card-art" not in spec


# ---------------------------------------------------------------- settings across port fallback


VOLUME_KEY = "redline.music.volume.v1"


def test_settings_store_round_trip_keeps_only_allowlisted_values(tmp_path):
    store = settings.SettingsStore(tmp_path / "settings.json")
    saved = {
        VOLUME_KEY: "70",
        "redline.sessions.v1": '{"g":{"resume_token":"SECRET"}}',
        "redline.hotseat.v1": "SECRET",
        "redline.device_id.v1": "SECRET",
        "redline.display.v1": 5,
    }
    assert store.save(saved) is True
    assert store.load() == {VOLUME_KEY: "70"}
    assert "SECRET" not in store.path.read_text()
    assert store.save({VOLUME_KEY: "70"}) is False
    assert store.path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "content", ["not json", "[]", '{"version": 999, "settings": {"redline.music.volume.v1": "70"}}', '{"version": 1, "settings": 5}']
)
def test_settings_store_ignores_corrupt_or_unknown_files(tmp_path, content):
    path = tmp_path / "settings.json"
    path.write_text(content)
    assert settings.SettingsStore(path).load() == {}


def test_settings_store_drops_oversized_values(tmp_path):
    store = settings.SettingsStore(tmp_path / "settings.json")
    store.save({VOLUME_KEY: "x" * (settings.MAX_VALUE_LENGTH + 1)})
    assert store.load() == {}


class FakeWindow:
    """記錄 evaluate_js；回傳值由測試設定。"""

    def __init__(self, results):
        self.results = list(results)
        self.scripts = []

    def evaluate_js(self, script):
        self.scripts.append(script)
        return self.results.pop(0)


def make_session(tmp_path, results):
    window = FakeWindow(results)
    store = settings.SettingsStore(tmp_path / "settings.json")
    return launcher.WebSession(window, store, None, "http://127.0.0.1:18101"), window, store


def test_failed_import_never_overwrites_the_settings_file(tmp_path):
    session, window, store = make_session(tmp_path, [None])
    store.save({VOLUME_KEY: "70"})
    session.on_loaded()
    assert not session.ready.is_set()
    session.snapshot()  # 尚未匯入：不可讀頁面，也不可覆寫
    assert len(window.scripts) == 1 and store.load() == {VOLUME_KEY: "70"}


def test_settings_are_imported_only_once_per_launch(tmp_path):
    session, window, store = make_session(tmp_path, ["reload", "ready", json.dumps({VOLUME_KEY: "70"}), "ready", json.dumps({VOLUME_KEY: "40"})])
    store.save({VOLUME_KEY: "70"})
    session.on_loaded()
    assert not session.ready.is_set() and '"70"' in window.scripts[0]
    session.on_loaded()  # reload 後：snapshot 並就緒
    assert session.ready.is_set()
    session.on_loaded()  # 遊戲內換頁：不能把舊值寫回，玩家剛改的 40 要留下
    assert '"70"' not in window.scripts[3]
    assert store.load() == {VOLUME_KEY: "40"}


NODE_HARNESS = """
(function () {
  const script = require('fs').readFileSync(0, 'utf8');
  const [origin, stored] = JSON.parse(process.argv[1]);
  const data = new Map(Object.entries(stored));
  const localStorage = {getItem: k => data.has(k) ? data.get(k) : null, setItem: (k, v) => data.set(k, String(v))};
  let reloads = 0;
  const location = {origin, reload: () => { reloads += 1; }};
  const setTimeout = fn => fn();
  const result = eval(script);
  console.log(JSON.stringify({result, reloads, data: Object.fromEntries(data)}));
})();
"""


def run_page_script(script, origin, stored):
    done = subprocess.run(
        ["node", "-e", NODE_HARNESS, json.dumps([origin, stored])], input=script, capture_output=True, text=True, check=True
    )
    return json.loads(done.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node to run the generated page scripts")
def test_settings_survive_relaunch_on_fallback_port(tmp_path):
    first_origin, fallback_origin = "http://127.0.0.1:18100", "http://127.0.0.1:18101"
    bridge = launcher.DEFAULT_BRIDGE_URL
    secret = '{"g":{"resume_token":"SECRET"}}'
    first_page = {VOLUME_KEY: "70", "redline.display.v1": "living-room", "redline.sessions.v1": secret}
    store = settings.SettingsStore(tmp_path / "settings.json")

    # 第一次啟動（18100）：玩家的設定存進檔案；憑證不會跟著進去。
    snapshot = run_page_script(settings.snapshot_js(first_origin), first_origin, first_page)["result"]
    store.save(json.loads(snapshot))
    assert "SECRET" not in store.path.read_text()

    # 重開後 18100 被佔用（18101，localStorage 全空）：設定回來、重新載入一次，憑證不會憑空出現。
    relaunched = run_page_script(settings.bootstrap_js(store.load(), bridge, bridge), fallback_origin, {})
    assert relaunched["result"] == "reload" and relaunched["reloads"] == 1
    assert relaunched["data"] == {VOLUME_KEY: "70", "redline.display.v1": "living-room"}

    # 重新載入後值已一致：不會無限重新載入。
    again = run_page_script(settings.bootstrap_js(store.load(), bridge, bridge), fallback_origin, relaunched["data"])
    assert again["result"] == "ready" and again["reloads"] == 0

    # 在 18101 改了音量，再回到 18100：檔案較新，要蓋過 18100 留下的舊值。
    store.save({VOLUME_KEY: "30"})
    back = run_page_script(settings.bootstrap_js(store.load(), bridge, bridge), first_origin, first_page)
    assert back["data"][VOLUME_KEY] == "30" and back["reloads"] == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node to run the generated page scripts")
def test_bootstrap_points_page_at_actual_bridge_and_keeps_enabled_flag():
    actual = "ws://127.0.0.1:18800/ws"
    stored = {settings.CONTROLLER_KEY: json.dumps({"enabled": True, "url": launcher.DEFAULT_BRIDGE_URL})}
    done = run_page_script(settings.bootstrap_js({}, actual, launcher.DEFAULT_BRIDGE_URL), "http://127.0.0.1:18100", stored)
    assert done["reloads"] == 1
    assert json.loads(done["data"][settings.CONTROLLER_KEY]) == {"enabled": True, "url": actual}


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node to run the generated page scripts")
def test_snapshot_refuses_other_origins():
    done = run_page_script(settings.snapshot_js("http://127.0.0.1:18100"), "null", {VOLUME_KEY: "70"})
    assert done["result"] is None


def test_clear_info_removes_instance_state_but_keeps_lock(paths):
    lock = launcher.InstanceLock(paths)
    assert lock.acquire()
    lock.publish({"pid": 1})
    lock.clear_info()
    assert not paths.instance_file.exists()
    assert not launcher.InstanceLock(paths).acquire()
    lock.release()
