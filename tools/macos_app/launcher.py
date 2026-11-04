"""REDLINE.app 的 launcher。

同一個執行檔依參數扮演三種角色，因此 App 內不需要 Python、uv 或 Docker：

- 預設：GUI launcher（單一實例鎖 → 啟動 child → 等 health → 開視窗 → 關閉時清理）。
- ``--redline-child server|bridge``：遊戲 server／Joy-Con bridge 子行程。
- ``--smoke``／``--smoke-gui``：只供打包驗證，檢查後自動關閉，不會跳對話框。

子行程各自獨立於自己的 process group，由 launcher 以 SIGTERM → SIGKILL 停止；另有
parent watchdog，launcher 被 SIGKILL 或當掉時子行程也會自行結束。
"""

from __future__ import annotations

import argparse
import fcntl
import importlib
import json
import logging
import logging.handlers
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from tools.macos_app.settings import PRESERVED_KEYS, SettingsStore, bootstrap_js, sanitize, snapshot_js

APP_NAME = "REDLINE"
LOOPBACK = "127.0.0.1"

# 固定優先埠讓 WebView 的 origin 穩定（localStorage 內的音量、手把設定與重連憑證都綁 origin）。
# 刻意避開 repo 其他啟動方式常用的 8000／8100／8765。
GAME_PORT_CANDIDATES = tuple(range(18100, 18110))
# static/controller_core.js 的 DEFAULT_BRIDGE_URL 就是這個埠。
BRIDGE_DEFAULT_PORT = 8000
BRIDGE_FALLBACK_PORTS = tuple(range(18800, 18810))
DEFAULT_BRIDGE_URL = f"ws://{LOOPBACK}:{BRIDGE_DEFAULT_PORT}/ws"

SERVER_HEALTH_PATH = "/server-info"
BRIDGE_HEALTH_PATH = "/health"
SERVER_START_ATTEMPTS = 3
SERVER_HEALTH_TIMEOUT_S = 60.0
BRIDGE_HEALTH_TIMEOUT_S = 20.0
STOP_GRACE_S = 5.0
WATCHDOG_INTERVAL_S = 0.5
LOG_MAX_BYTES = 5 * 1024 * 1024
SETTINGS_SYNC_INTERVAL_S = 2.0

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_ALREADY_RUNNING = 3

log = logging.getLogger("redline.app")


class StartupError(Exception):
    """無法繼續執行（啟動失敗或 server 意外結束）；訊息會顯示給玩家。"""


class ChildExited(Exception):
    """等待 health 時子行程已結束。"""


class HealthTimeout(Exception):
    """在期限內沒有等到 health 成功。"""


class ShutdownRequested(Exception):
    """啟動途中收到結束信號；不是錯誤。"""


# ---------------------------------------------------------------- paths


def resource_root() -> Path:
    """static/、data/ 所在目錄。server 以相對 cwd 讀 static/，子行程必須 chdir 到這裡。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppPaths:
    state_dir: Path
    log_dir: Path

    @property
    def lock_file(self) -> Path:
        return self.state_dir / "instance.lock"

    @property
    def instance_file(self) -> Path:
        return self.state_dir / "instance.json"

    @property
    def settings_file(self) -> Path:
        return self.state_dir / "settings.json"

    @classmethod
    def resolve(cls, env=os.environ) -> "AppPaths":
        # App 本體可能在唯讀的 DMG 或 App Translocation 路徑，狀態一律寫到使用者目錄。
        override = env.get("REDLINE_APP_STATE_DIR")
        if override:
            root = Path(override)
            paths = cls(root, root / "logs")
        else:
            home = Path.home()
            paths = cls(home / "Library/Application Support" / APP_NAME, home / "Library/Logs" / APP_NAME)
        paths.state_dir.mkdir(parents=True, exist_ok=True)
        paths.log_dir.mkdir(parents=True, exist_ok=True)
        return paths


def setup_logging(paths: AppPaths) -> None:
    handler = logging.handlers.RotatingFileHandler(
        paths.log_dir / "launcher.log", maxBytes=LOG_MAX_BYTES, backupCount=1, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


# ---------------------------------------------------------------- ports & health


def is_port_available(port: int, bind_host: str = LOOPBACK) -> bool:
    """連得上就是有人在聽；否則再實際 bind 一次。

    只測 bind 不夠：macOS 上 SO_REUSEADDR（uvicorn 會設）允許在 `*:port` 已有 listener 時再綁
    `127.0.0.1:port`，結果會把別的服務（例如 Docker 發布的埠）蓋掉。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        if probe.connect_ex((LOOPBACK, port)) == 0:
            return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((bind_host, port))
        except OSError:
            return False
    return True


def ephemeral_port(bind_host: str = LOOPBACK) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((bind_host, 0))
        return sock.getsockname()[1]


def choose_port(candidates: Iterable[int], bind_host: str = LOOPBACK, exclude: Iterable[int] = ()) -> int:
    """回傳第一個可用的候選埠；全部被佔用時退回系統分配的埠。"""
    excluded = set(exclude)
    for port in candidates:
        if port not in excluded and is_port_available(port, bind_host):
            return port
    return ephemeral_port(bind_host)


# 不走系統 proxy：macOS 的 urllib 會讀系統 proxy 設定，loopback 請求不該經過它。
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_request(url: str, timeout: float = 2.0, data: bytes | None = None) -> tuple[int, bytes]:
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with _opener.open(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def wait_for_http(url: str, timeout: float, is_alive: Callable[[], bool] = lambda: True, interval: float = 0.1) -> None:
    """等到 URL 回 200。子行程先結束 → ChildExited；逾時 → HealthTimeout。"""
    deadline = time.monotonic() + timeout
    while True:
        if not is_alive():
            raise ChildExited(url)
        try:
            if http_request(url, timeout=2.0)[0] == 200:
                return
        except (OSError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise HealthTimeout(url)
        time.sleep(interval)


def is_joycon_bridge(port: int) -> bool:
    """這個埠上是否已經是 REDLINE Joy-Con bridge（例如 Docker Compose 或 run_mac.sh 啟動的）。"""
    try:
        status, body = http_request(f"http://{LOOPBACK}:{port}{BRIDGE_HEALTH_PATH}", timeout=1.0)
        payload = json.loads(body)
    except (OSError, ValueError):
        return False
    return status == 200 and isinstance(payload, dict) and payload.get("ok") is True and "packets" in payload


# ---------------------------------------------------------------- child processes


def child_command(role: str, port: int, bind_host: str, parent_pid: int) -> list[str]:
    prefix = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-m", "tools.macos_app"]
    return [*prefix, "--redline-child", role, "--port", str(port), "--bind-host", bind_host, "--parent-pid", str(parent_pid)]


def child_env(base=os.environ) -> dict[str, str]:
    """生產環境不得啟用 test routes，即使使用者環境設了 ENABLE_TEST_ROUTES 也一樣。"""
    return {**base, "ENABLE_TEST_ROUTES": "false", "PYTHONUNBUFFERED": "1"}


def _rotate_if_large(path: Path) -> None:
    try:
        if path.stat().st_size > LOG_MAX_BYTES:
            path.replace(path.with_name(path.name + ".1"))
    except OSError:
        pass


class ManagedProcess:
    """放在獨立 process group 的子行程，stdout/stderr 寫入 log。"""

    def __init__(self, name: str, command: list[str], log_path: Path, env: dict[str, str] | None = None, cwd: Path | None = None) -> None:
        self.name = name
        self.log_path = log_path
        _rotate_if_large(log_path)
        with open(log_path, "ab") as sink:
            self.process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=sink, stderr=subprocess.STDOUT,
                env=env, cwd=cwd, start_new_session=True,
            )
        log.info("started %s pid=%s: %s", name, self.process.pid, " ".join(command))

    @property
    def pid(self) -> int:
        return self.process.pid

    def alive(self) -> bool:
        return self.process.poll() is None

    def stop(self, grace: float = STOP_GRACE_S) -> None:
        """SIGTERM → 等待 → SIGKILL。一定會 wait，不留 zombie；也清掉同 group 的殘留。"""
        if self.alive():
            self._signal_group(signal.SIGTERM)
            try:
                self.process.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                log.warning("%s did not exit in %.1fs; sending SIGKILL", self.name, grace)
                self._signal_group(signal.SIGKILL)
                self.process.wait()
        self._signal_group(signal.SIGKILL)
        log.info("stopped %s pid=%s rc=%s", self.name, self.pid, self.process.returncode)

    def _signal_group(self, signum: int) -> None:
        try:
            os.killpg(self.process.pid, signum)
        except (ProcessLookupError, PermissionError):
            pass


@dataclass
class BridgeInfo:
    mode: str  # spawned｜reused｜failed
    port: int | None = None
    process: ManagedProcess | None = None

    @property
    def url(self) -> str | None:
        return f"ws://{LOOPBACK}:{self.port}/ws" if self.port is not None else None


class Supervisor:
    """擁有子行程的生命週期。stop() 可重複呼叫，也可從任何執行緒呼叫。"""

    def __init__(self, paths: AppPaths, bind_host: str = LOOPBACK, env=os.environ) -> None:
        self.paths = paths
        self.bind_host = bind_host
        self.env = env
        self.server: ManagedProcess | None = None
        self.server_port: int | None = None
        self.bridge = BridgeInfo("failed")
        self.stopping = threading.Event()
        self._stop_lock = threading.Lock()

    def _spawn(self, role: str, port: int, bind_host: str) -> ManagedProcess:
        return ManagedProcess(
            role, child_command(role, port, bind_host, os.getpid()), self.paths.log_dir / f"{role}.log",
            env=child_env(self.env), cwd=resource_root(),
        )

    def start_server(self) -> int:
        """選埠、啟動並等 health。選埠到 bind 之間被搶走時，child 會 bind 失敗退出，換下一個埠重試。"""
        tried: list[int] = []
        for attempt in range(1, SERVER_START_ATTEMPTS + 1):
            port = choose_port(GAME_PORT_CANDIDATES, self.bind_host, exclude=tried)
            tried.append(port)
            server = self._spawn("server", port, self.bind_host)
            self.server = server
            try:
                wait_for_http(f"http://{LOOPBACK}:{port}{SERVER_HEALTH_PATH}", SERVER_HEALTH_TIMEOUT_S, server.alive)
            except ChildExited:
                if self.stopping.is_set():
                    raise ShutdownRequested() from None
                log.warning("server exited during startup on port %s (attempt %s)", port, attempt)
                server.stop()
                continue
            except HealthTimeout as exc:
                server.stop()
                raise StartupError(f"遊戲伺服器在 {SERVER_HEALTH_TIMEOUT_S:.0f} 秒內沒有回應。") from exc
            self.server_port = port
            log.info("server healthy on port %s", port)
            return port
        raise StartupError(f"遊戲伺服器無法啟動（已嘗試連接埠 {tried}）。")

    def spawn_bridge(self) -> BridgeInfo:
        """決定 bridge 來源並啟動（不等 health）。Joy-Con 是選用功能，失敗不阻止遊戲啟動。"""
        preferred = int(self.env.get("REDLINE_APP_BRIDGE_PORT") or BRIDGE_DEFAULT_PORT)
        if is_joycon_bridge(preferred):
            # 既有 bridge 接受任何 loopback Origin；它不屬於 App，關閉時也不碰它。
            log.info("reusing existing Joy-Con bridge on port %s", preferred)
            self.bridge = BridgeInfo("reused", preferred)
            return self.bridge
        port = preferred if is_port_available(preferred) else choose_port(BRIDGE_FALLBACK_PORTS, exclude=[preferred])
        if port != preferred:
            log.warning("port %s is occupied by another program; Joy-Con bridge uses %s", preferred, port)
        try:
            self.bridge = BridgeInfo("spawned", port, self._spawn("bridge", port, LOOPBACK))
        except OSError:
            log.exception("could not start Joy-Con bridge")
            self.bridge = BridgeInfo("failed")
        return self.bridge

    def wait_for_bridge(self) -> None:
        process = self.bridge.process
        if process is None:
            return
        try:
            wait_for_http(f"http://{LOOPBACK}:{self.bridge.port}{BRIDGE_HEALTH_PATH}", BRIDGE_HEALTH_TIMEOUT_S, process.alive)
            log.info("Joy-Con bridge healthy on port %s", self.bridge.port)
        except (ChildExited, HealthTimeout):
            log.error("Joy-Con bridge failed to start; the game continues without it. See %s", process.log_path)
            process.stop()
            self.bridge = BridgeInfo("failed")

    def stop(self) -> None:
        with self._stop_lock:
            self.stopping.set()
            for child in (self.server, self.bridge.process):
                if child is not None:
                    child.stop()


# ---------------------------------------------------------------- child roles


def start_parent_watchdog(parent_pid: int, interval: float = WATCHDOG_INTERVAL_S) -> threading.Thread:
    """launcher 消失（被 SIGKILL、當掉、NSApp 直接 exit）時結束自己，避免遺留佔埠的行程。"""

    def watch() -> None:
        while os.getppid() == parent_pid:
            time.sleep(interval)
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(STOP_GRACE_S)
        os._exit(EXIT_FAILURE)

    thread = threading.Thread(target=watch, name="parent-watchdog", daemon=True)
    thread.start()
    return thread


def run_server_child(port: int, bind_host: str) -> int:
    # 在 import server.main 之前強制關閉：/test/* 是在 import 時決定是否註冊。
    os.environ["ENABLE_TEST_ROUTES"] = "false"
    os.chdir(resource_root())
    import uvicorn

    from server.main import app
    from tools.macos_app.security import HostOriginGuard

    guarded = HostOriginGuard(app, port=port, loopback_only=bind_host == LOOPBACK)
    # 房間狀態在單一 process 記憶體中，只能單一 worker；WebSocket 不無限期阻擋關閉。
    # log_level=warning、不留 access log：請求路徑含房間與玩家 id，不該進記錄檔。
    # 前面沒有反向代理，不採信 X-Forwarded-*。
    uvicorn.run(
        guarded, host=bind_host, port=port, log_level="warning", access_log=False,
        proxy_headers=False, timeout_graceful_shutdown=3,
    )
    return EXIT_OK


def run_bridge_child(port: int) -> int:
    os.chdir(resource_root())
    from tools.joycon_bridge.__main__ import main as bridge_main

    bridge_main(["--port", str(port)])
    return EXIT_OK


def run_child(args: argparse.Namespace) -> int:
    if args.parent_pid:
        start_parent_watchdog(args.parent_pid)
    if args.redline_child == "server":
        return run_server_child(args.port, args.bind_host)
    return run_bridge_child(args.port)


# ---------------------------------------------------------------- single instance


class InstanceLock:
    """flock：行程一結束（包含被 SIGKILL）就自動釋放，不會留下過期的鎖。"""

    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths
        self._fd: int | None = None

    def acquire(self) -> bool:
        fd = os.open(self.paths.lock_file, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        self._fd = fd
        return True

    def publish(self, info: dict) -> None:
        temp = self.paths.instance_file.with_suffix(".tmp")
        temp.write_text(json.dumps(info), encoding="utf-8")
        temp.replace(self.paths.instance_file)

    def read_info(self) -> dict:
        try:
            info = json.loads(self.paths.instance_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return info if isinstance(info, dict) else {}

    def clear_info(self) -> None:
        self.paths.instance_file.unlink(missing_ok=True)

    def release(self) -> None:
        if self._fd is not None:
            self.clear_info()
            os.close(self._fd)
            self._fd = None


def activate_running_instance(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        from AppKit import NSApplicationActivateIgnoringOtherApps, NSRunningApplication

        running = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        return bool(running and running.activateWithOptions_(NSApplicationActivateIgnoringOtherApps))
    except Exception:
        log.exception("could not activate running instance pid=%s", pid)
        return False


# ---------------------------------------------------------------- user-visible errors & signals


def show_error(message: str, paths: AppPaths) -> None:
    """用 osascript 顯示錯誤（不依賴 WebView 是否可用）。內容以 argv 傳入，不需跳脫。"""
    detail = f"{message}\n\n診斷記錄：{paths.log_dir}"
    script = ["-e", "on run argv", "-e", "display alert (item 1 of argv) message (item 2 of argv) as critical", "-e", "end run"]
    try:
        subprocess.run(["osascript", *script, f"{APP_NAME} 發生錯誤", detail], check=False, timeout=600)
    except (OSError, subprocess.SubprocessError):
        log.exception("could not show error dialog")


def install_shutdown_signals(callback: Callable[[], None]) -> None:
    """SIGTERM／SIGINT／SIGHUP → callback（在背景執行緒）。

    主執行緒停在 NSApp 事件迴圈時 Python 層的 signal handler 不會執行，所以用 wakeup fd：
    C 層 handler 會直接寫 pipe，由這裡的執行緒收到。
    """
    read_fd, write_fd = os.pipe()
    os.set_blocking(write_fd, False)
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, lambda *_: None)
    signal.set_wakeup_fd(write_fd, warn_on_full_buffer=False)

    def wait_for_signal() -> None:
        received = os.read(read_fd, 1)
        log.info("received signal %s; shutting down", received[0] if received else "?")
        callback()

    threading.Thread(target=wait_for_signal, name="signal-watcher", daemon=True).start()


# ---------------------------------------------------------------- GUI


class WebSession:
    """視窗與設定檔之間的同步。只有第一次載入會把檔案寫回頁面，之後都是頁面寫回檔案。"""

    def __init__(self, window, store: SettingsStore, bridge_url: str | None, base_url: str, on_ready: Callable[[], None] = lambda: None) -> None:
        self.window = window
        self.store = store
        self.bridge_url = bridge_url
        self.base_url = base_url
        self.on_ready = on_ready
        self.ready = threading.Event()
        self._imported = False

    def on_loaded(self) -> None:
        self.ready.clear()
        settings = self.store.load() if not self._imported else {}
        try:
            result = self.window.evaluate_js(bootstrap_js(settings, self.bridge_url, DEFAULT_BRIDGE_URL))
        except Exception:
            log.exception("could not apply settings to the page")
            return
        if result not in ("ready", "reload"):
            log.warning("unexpected settings bootstrap result")
            return
        # 匯入成功前絕不 snapshot，否則空的 localStorage 會蓋掉設定檔。
        self._imported = True
        if result == "ready":
            self.snapshot()
            self.ready.set()
            self.on_ready()

    def snapshot(self) -> None:
        if not self._imported:
            return
        result = self.window.evaluate_js(snapshot_js(self.base_url))
        if not isinstance(result, str):
            return
        try:
            self.store.save(json.loads(result))
        except (OSError, ValueError):
            log.exception("could not save settings")

    def sync_until(self, stopping: threading.Event, interval: float = SETTINGS_SYNC_INTERVAL_S) -> None:
        while not stopping.wait(interval):
            if self.ready.is_set():
                try:
                    self.snapshot()
                except Exception as exc:  # 頁面重新載入或視窗正在關閉
                    log.info("settings sync skipped: %s", type(exc).__name__)


def run_window(
    url: str,
    supervisor: Supervisor,
    request_close: list,
    on_close: Callable[[], None],
    on_ready: Callable[[], None] = lambda: None,
    worker: Callable[[object, WebSession], None] | None = None,
) -> None:
    """建立視窗並阻塞到關閉。server 意外結束時關閉視窗並回報錯誤。"""
    import webview

    window = webview.create_window(APP_NAME, url, width=1440, height=900, min_size=(1024, 700), text_select=True)
    session = WebSession(window, SettingsStore(supervisor.paths.settings_file), supervisor.bridge.url, url, on_ready)

    def on_closing() -> None:
        # Cmd-Q 時 NSApp 會直接 exit，webview.start() 不會返回，必須在這裡清理。
        on_close()

    window.events.loaded += session.on_loaded
    window.events.closing += on_closing
    request_close.append(window.destroy)

    crashed = threading.Event()

    def monitor_server() -> None:
        while not supervisor.stopping.is_set():
            if supervisor.server is not None and not supervisor.server.alive():
                if not supervisor.stopping.is_set():
                    log.error("server exited unexpectedly (rc=%s)", supervisor.server.process.returncode)
                    crashed.set()
                    window.destroy()
                return
            time.sleep(0.5)

    threading.Thread(target=monitor_server, name="server-monitor", daemon=True).start()
    threading.Thread(target=session.sync_until, args=(supervisor.stopping,), name="settings-sync", daemon=True).start()
    args = (window, session) if worker else None
    # private_mode=False：True 會在啟動時清空整個預設 data store。
    webview.start(worker, args, private_mode=False, debug=False)
    if crashed.is_set():
        raise StartupError("遊戲伺服器意外結束。")


# ---------------------------------------------------------------- smoke mode


SMOKE_IMPORTS = ("server.main", "red_army_policy.policy", "tools.joycon_bridge.bridge")
SMOKE_GUI_IMPORTS = ("webview", "AppKit", "WebKit")


def smoke_checks(base_url: str) -> dict:
    """打包內容的檢查：資源可讀、核心 API 可用、test routes 確實不存在、GUI 相依已打包。"""
    results: dict[str, object] = {}
    for path in (SERVER_HEALTH_PATH, "/", "/static/app.js", "/map-data", "/factions", "/card-presentation"):
        results[path] = http_request(base_url + path, timeout=10.0)[0]
    status, body = http_request(base_url + "/openapi.json", timeout=10.0)
    results["test_routes"] = sorted(p for p in json.loads(body).get("paths", {}) if p.startswith("/test")) if status == 200 else "unknown"
    status, body = http_request(base_url + "/create", timeout=10.0, data=json.dumps({"name": "smoke", "ai_red_army": True}).encode())
    created = json.loads(body) if status == 200 else {}
    results["create_room"] = bool(created.get("game_id"))
    for module in SMOKE_GUI_IMPORTS:
        importlib.import_module(module)
    results["gui_imports"] = list(SMOKE_GUI_IMPORTS)
    # server.main 以相對路徑掛載 static/；此處只確認模組都已打包。
    os.chdir(resource_root())
    for module in SMOKE_IMPORTS:
        importlib.import_module(module)
    results["imports"] = list(SMOKE_IMPORTS)
    return results


def smoke_failures(checks: dict) -> list[str]:
    failures = [f"{key}={value}" for key, value in checks.items() if key.startswith("/") and value != 200]
    if checks.get("test_routes") != []:
        failures.append(f"test_routes={checks.get('test_routes')}")
    if checks.get("create_room") is not True:
        failures.append("create_room failed")
    return failures


# 在真實頁面用同源 fetch 與 WebSocket 走一次遊戲流程，證明 Host／Origin 防護沒有擋到 WebView。
_SMOKE_GAMEPLAY_JS = """
window.__redlineSmoke='pending';
fetch('/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'smoke',device_id:'smoke-gui'})})
.then(function(r){return r.json()}).then(function(c){
var w=new WebSocket(location.origin.replace('http','ws')+'/ws/'+c.game_id+'/'+c.host_id,[c.resume_token]);
// 尚未開始的房間會送出 "Game not ready" 後斷線，所以只採用第一個事件。
w.onmessage=function(){if(window.__redlineSmoke==='pending')window.__redlineSmoke='ok';w.close()};
w.onerror=function(){if(window.__redlineSmoke==='pending')window.__redlineSmoke='ws-error'};
}).catch(function(){window.__redlineSmoke='fetch-error'});
"""
_SMOKE_BRIDGE_JS = """
window.__redlineBridge='pending';
var b=new WebSocket(%s);
b.onopen=function(){window.__redlineBridge='ok';b.close()};
b.onerror=function(){window.__redlineBridge='ws-error'};
"""


def _smoke_wait_js(window, variable: str, timeout: float = 15.0) -> object:
    deadline = time.monotonic() + timeout
    value = None
    while time.monotonic() < deadline:
        value = window.evaluate_js(f"window.{variable}")
        if value != "pending":
            return value
        time.sleep(0.1)
    return value


def smoke_gui_worker(bridge_url: str | None, write_settings: dict[str, str], result: dict) -> Callable[[object, WebSession], None]:
    """真實 WKWebView：確認頁面、同源遊戲流程與 bridge 連線都可用，然後關閉視窗。"""

    def worker(window, session: WebSession) -> None:
        try:
            result["page_loaded"] = session.ready.wait(60)
            result["title"] = window.evaluate_js("document.title")
            result["origin"] = window.evaluate_js("location.origin")
            result["settings"] = json.loads(window.evaluate_js(snapshot_js(session.base_url)) or "{}")
            window.evaluate_js(_SMOKE_GAMEPLAY_JS)
            result["gameplay"] = _smoke_wait_js(window, "__redlineSmoke")
            if bridge_url:
                window.evaluate_js(_SMOKE_BRIDGE_JS % json.dumps(bridge_url))
                result["bridge_ws"] = _smoke_wait_js(window, "__redlineBridge")
            if write_settings:
                window.evaluate_js(
                    "(function(s){for(var k in s){localStorage.setItem(k,s[k])}})(%s)" % json.dumps(write_settings)
                )
                session.snapshot()
        except Exception as exc:
            log.exception("gui smoke failed")
            result["error"] = repr(exc)
        finally:
            window.destroy()

    return worker


def write_report(path: Path | None, report: dict) -> None:
    if path is None:
        return
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def run_smoke(
    args: argparse.Namespace, supervisor: Supervisor, base_url: str, request_close: list, on_close: Callable[[], None], shutdown: threading.Event,
) -> int:
    report_path = Path(args.smoke_report) if args.smoke_report else None
    children = [c for c in (supervisor.server, supervisor.bridge.process) if c is not None]
    report: dict = {
        "status": "ready",
        "launcher_pid": os.getpid(),
        "base_url": base_url,
        "server_port": supervisor.server_port,
        "bridge": {"mode": supervisor.bridge.mode, "port": supervisor.bridge.port},
        "child_pids": {c.name: c.pid for c in children},
        "checks": smoke_checks(base_url),
    }
    failures = smoke_failures(report["checks"])
    if supervisor.bridge.mode == "failed":
        failures.append("bridge failed")
    if args.smoke_gui:
        gui: dict = {}
        write_settings = sanitize(json.loads(args.smoke_write_settings)) if args.smoke_write_settings else {}
        worker = smoke_gui_worker(supervisor.bridge.url, write_settings, gui)
        run_window(base_url, supervisor, request_close, on_close, worker=worker)
        report["gui"] = gui
        if not gui.get("page_loaded") or not gui.get("title") or gui.get("error") or gui.get("gameplay") != "ok" or gui.get("bridge_ws") != "ok":
            failures.append(f"gui={gui}")
    report["failures"] = failures
    write_report(report_path, report)
    shutdown.wait(args.smoke_hold)
    return EXIT_FAILURE if failures else EXIT_OK


# ---------------------------------------------------------------- orchestration


def run_app(args: argparse.Namespace, paths: AppPaths) -> int:
    smoke = args.smoke or args.smoke_gui
    lock = InstanceLock(paths)
    if not lock.acquire():
        info = lock.read_info()
        log.info("another instance is running: %s", info)
        if smoke:
            print(f"{APP_NAME} is already running: {info}", file=sys.stderr)
        elif not activate_running_instance(info.get("pid")):
            show_error("REDLINE 已在執行中。", paths)
        return EXIT_ALREADY_RUNNING

    bind_host = os.environ.get("REDLINE_APP_BIND_HOST") or LOOPBACK
    supervisor = Supervisor(paths, bind_host)
    shutdown = threading.Event()
    request_close: list[Callable[[], None]] = []

    def cleanup() -> None:
        supervisor.stop()
        lock.clear_info()

    def on_signal() -> None:
        shutdown.set()
        cleanup()
        for close in request_close:
            close()
        if request_close:
            # 視窗正常關閉後主流程會自行結束；這只是最後防線。
            time.sleep(STOP_GRACE_S)
            os._exit(EXIT_OK)

    install_shutdown_signals(on_signal)
    try:
        supervisor.spawn_bridge()
        port = supervisor.start_server()
        supervisor.wait_for_bridge()
        base_url = f"http://{LOOPBACK}:{port}"
        info = {"pid": os.getpid(), "url": base_url, "server_port": port, "bridge": {"mode": supervisor.bridge.mode, "port": supervisor.bridge.port}}
        lock.publish(info)
        if smoke:
            return run_smoke(args, supervisor, base_url, request_close, cleanup, shutdown)
        if not shutdown.is_set():
            run_window(base_url, supervisor, request_close, cleanup, on_ready=lambda: lock.publish({**info, "window_ready": True}))
        return EXIT_OK
    except ShutdownRequested:
        return EXIT_OK
    finally:
        supervisor.stop()
        lock.release()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME)
    parser.add_argument("--redline-child", choices=("server", "bridge"), help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--bind-host", default=LOOPBACK, help=argparse.SUPPRESS)
    parser.add_argument("--parent-pid", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--smoke", action="store_true", help="打包驗證：不開視窗，檢查後自動關閉")
    parser.add_argument("--smoke-gui", action="store_true", help="打包驗證：開真實視窗，檢查頁面後自動關閉")
    parser.add_argument("--smoke-report", help="smoke 結果 JSON 的路徑")
    parser.add_argument("--smoke-write-settings", help="打包驗證：--smoke-gui 時寫入這些設定（JSON），用來驗證跨連接埠保留")
    parser.add_argument("--smoke-hold", type=float, default=0.0, help="檢查完成後保持執行的秒數（收到信號會提早結束）")
    return parser


def main(argv: list[str] | None = None) -> int:
    # parse_known_args：LaunchServices 可能附加系統參數，不能因此啟動失敗。
    args, _ = build_parser().parse_known_args(argv)
    if args.redline_child:
        return run_child(args)
    smoke = args.smoke or args.smoke_gui
    paths = AppPaths.resolve()
    setup_logging(paths)
    log.info("launcher start pid=%s frozen=%s smoke=%s", os.getpid(), getattr(sys, "frozen", False), smoke)
    try:
        return run_app(args, paths)
    except StartupError as exc:
        log.error("fatal: %s", exc)
        message = str(exc)
    except Exception as exc:
        log.exception("unexpected launcher failure")
        message = f"發生未預期的錯誤：{exc}"
    print(message, file=sys.stderr)
    if not smoke:
        show_error(message, paths)
    return EXIT_FAILURE
