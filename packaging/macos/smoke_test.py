#!/usr/bin/env python3
"""驗證建好的 REDLINE.app 或 DMG（只用標準函式庫，不需要專案相依）。

    python packaging/macos/smoke_test.py --dmg dist/REDLINE-2.0.0-macOS-arm64.dmg [--gui]
    python packaging/macos/smoke_test.py --app dist/REDLINE.app [--gui]

全程從「外部」檢查：/server-info 回 200、/test/* 不存在、惡意 Host／Origin 被拒絕、關閉後子行程與
連接埠都已清除。測試用獨立的狀態目錄、WebKit 儲存（CFFIXED_USER_HOME）與 bridge 埠，結束時確認沒有
在真實家目錄留下任何東西。--gui 另外驗證真實視窗、跨連接埠保留設定，以及從 LaunchServices 啟動
（open -n）後以 application quit（與 Cmd-Q 相同的路徑）結束。

遊戲優先埠 18100 與測試 bridge 埠被佔用時會失敗，不會跳過。
"""

from __future__ import annotations

import argparse
import fcntl
import http.client
import json
import os
import plistlib
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
BUNDLE_ID = "io.github.kuiming.redline"
GAME_PORT = 18100
TEST_BRIDGE_PORT = 18870
READY_TIMEOUT_S = 120
QUIT_TIMEOUT_S = 30
VOLUME_KEY = "redline.music.volume.v1"
FIXED_VOLUME = "70"  # 合法（0–100、每次 10）且不是預設的 30
LAN_TEST_HOST = "192.168.1.20"
REPO_ROOT = Path(__file__).resolve().parents[2]
CARD_ART_DIRS = ("actions", "era", "events", "support")
LSREGISTER = "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
# App 預設會使用、測試不該碰到的真實家目錄路徑。
USER_STATE_PATHS = tuple(
    Path.home() / "Library" / relative
    for relative in (
        "Logs/REDLINE",
        "Application Support/REDLINE",
        f"WebKit/{BUNDLE_ID}",
        f"Caches/{BUNDLE_ID}",
        f"HTTPStorages/{BUNDLE_ID}",
        f"Saved Application State/{BUNDLE_ID}.savedState",
    )
)


class Failure(Exception):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)
    print(f"  ok: {message}", flush=True)


def http_status(url: str) -> int:
    try:
        with opener.open(url, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def http_status_with_headers(port: int, headers: dict[str, str]) -> int:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", "/server-info", headers=headers)
        return connection.getresponse().status
    finally:
        connection.close()


def websocket_status(port: int, path: str, headers: dict[str, str]) -> int:
    lines = [
        f"GET {path} HTTP/1.1", "Upgrade: websocket", "Connection: Upgrade",
        "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==", "Sec-WebSocket-Version: 13",
        *(f"{name}: {value}" for name, value in headers.items()),
    ]
    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        return int(sock.makefile("rb").readline().split()[1])


def assert_host_origin_guard(port: int) -> None:
    good = f"127.0.0.1:{port}"
    evil = "https://evil.example"
    check(http_status_with_headers(port, {"Host": good}) == 200, "no-Origin local client allowed")
    check(http_status_with_headers(port, {"Host": f"localhost:{port}", "Origin": f"http://localhost:{port}"}) == 200, "localhost same-origin allowed")
    check(http_status_with_headers(port, {"Host": "evil.example"}) == 403, "hostile Host rejected (HTTP)")
    check(http_status_with_headers(port, {"Host": good, "Origin": evil}) == 403, "hostile Origin rejected (HTTP)")
    check(websocket_status(port, "/ws/smoke/smoke", {"Host": good, "Origin": f"http://{good}"}) == 101, "same-origin WebSocket allowed")
    check(websocket_status(port, "/ws/smoke/smoke", {"Host": "evil.example"}) == 403, "hostile Host rejected (WebSocket)")
    check(websocket_status(port, "/ws/smoke/smoke", {"Host": good, "Origin": evil}) == 403, "hostile Origin rejected (WebSocket)")


def assert_lan_guard(port: int) -> None:
    """明確開放區網時：IP 字面值可用；網域名稱即使 Host 與 Origin 同源也要拒絕（DNS rebinding）。"""
    lan = f"{LAN_TEST_HOST}:{port}"
    evil = f"evil.example:{port}"
    ws = "/ws/smoke/smoke"
    check(http_status_with_headers(port, {"Host": lan}) == 200, "LAN IP literal allowed (HTTP)")
    check(http_status_with_headers(port, {"Host": lan, "Origin": f"http://{lan}"}) == 200, "LAN IP same-origin allowed (HTTP)")
    check(websocket_status(port, ws, {"Host": lan, "Origin": f"http://{lan}"}) == 101, "LAN IP same-origin allowed (WebSocket)")
    check(http_status_with_headers(port, {"Host": evil}) == 403, "DNS name rejected in LAN mode (HTTP)")
    check(http_status_with_headers(port, {"Host": evil, "Origin": f"http://{evil}"}) == 403, "matching evil Host+Origin rejected (HTTP)")
    check(websocket_status(port, ws, {"Host": evil, "Origin": f"http://{evil}"}) == 403, "matching evil Host+Origin rejected (WebSocket)")
    check(http_status_with_headers(port, {"Host": f"{LAN_TEST_HOST}:{port + 1}"}) == 403, "wrong port rejected in LAN mode")
    check(http_status_with_headers(port, {"Host": lan, "Origin": f"http://{evil}"}) == 403, "cross-origin rejected in LAN mode")


def card_art_files(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file() and path.name != ".DS_Store"}


def assert_card_art_bundled(resources: Path, source: Path | None = REPO_ROOT / "static/card-art") -> None:
    """卡牌圖隨 static/ 打包：每個分類都要有檔案，且（在 repo 中執行時）與來源完全相同。"""
    bundled = resources / "static/card-art"
    for name in CARD_ART_DIRS:
        check(any((bundled / name).glob("*")), f"card art bundled: {name}")
    if source is not None and source.is_dir():
        expected, actual = card_art_files(source), card_art_files(bundled)
        check(expected == actual, f"bundled card art matches the source ({len(actual)} files); differences: {sorted(expected ^ actual)[:5]}")


def assert_no_secrets_in_logs(state: Path) -> None:
    for log_file in (state / "logs").glob("*.log"):
        text = log_file.read_text(encoding="utf-8", errors="replace")
        check("resume_token" not in text and "evil.example" not in text and "/ws/" not in text, f"{log_file.name} has no tokens, paths, or hostile headers")


def pid_alive(pid: int) -> bool:
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith("Z")


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_until(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return predicate()


def isolated_env(state: Path, bridge_port: int = TEST_BRIDGE_PORT) -> dict[str, str]:
    home = state / "home"
    home.mkdir(parents=True, exist_ok=True)
    return {
        "REDLINE_APP_STATE_DIR": str(state),
        "REDLINE_APP_BRIDGE_PORT": str(bridge_port),
        # 讓 WebKit 的資料與快取落在測試目錄，不寫入真實的 ~/Library。
        "CFFIXED_USER_HOME": str(home),
    }


def exclusive_listener(port: int) -> socket.socket:
    """獨佔地綁住連接埠；已被佔用就失敗，不跳過。

    SO_REUSEADDR 只是為了略過上一個情境留下的 TIME_WAIT：同一位址已有 listener 時 bind 仍會失敗，
    而 macOS 上它允許疊在 *:port 上的情況，由前面的 connect 檢查擋掉。
    """
    if port_open(port):
        raise Failure(f"port {port} is already in use; stop whatever is using it and retry")
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", port))
        sock.listen()
    except OSError as exc:
        sock.close()
        raise Failure(f"cannot own port {port}: {exc}") from exc
    return sock


class Run:
    """啟動一次 packaged app 的 smoke 模式。"""

    def __init__(self, binary: Path, state: Path, *flags: str, hold: float = 300.0, bridge_port: int = TEST_BRIDGE_PORT, extra_env: dict[str, str] | None = None) -> None:
        self.report_path = state / f"report-{time.monotonic_ns()}.json"
        self.state = state
        env = {
            **os.environ,
            **isolated_env(state, bridge_port),
            # 故意打開：packaged app 必須無視它。
            "ENABLE_TEST_ROUTES": "true",
            **(extra_env or {}),
        }
        command = [str(binary), *(flags or ("--smoke",)), "--smoke-report", str(self.report_path), "--smoke-hold", str(hold)]
        self.process = subprocess.Popen(command, env=env)

    def wait_ready(self) -> dict:
        ok = wait_until(lambda: self.report_path.exists() or self.process.poll() is not None, READY_TIMEOUT_S)
        check(ok and self.report_path.exists(), f"smoke report written (rc={self.process.poll()})")
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        check(report["failures"] == [], f"in-app checks passed: {report['failures']}")
        return report

    def assert_serving(self, report: dict) -> None:
        check(http_status(report["base_url"] + "/server-info") == 200, "external GET /server-info == 200")
        check(http_status(report["base_url"] + "/test/setup-safehouse-range-proof") == 404, "test route is 404 despite ENABLE_TEST_ROUTES=true")

    def assert_cleaned(self, report: dict, timeout: float = 10.0) -> None:
        pids = list(report["child_pids"].values())
        check(wait_until(lambda: not any(pid_alive(p) for p in pids), timeout), f"child processes gone: {pids}")
        ports = [report["server_port"]]
        if report["bridge"]["mode"] == "spawned":
            ports.append(report["bridge"]["port"])
        check(wait_until(lambda: not any(port_open(p) for p in ports), timeout), f"ports closed: {ports}")


def scenario_clean_exit(binary: Path, state: Path) -> None:
    print("[clean exit]", flush=True)
    run = Run(binary, state, hold=4.0)
    report = run.wait_ready()
    check(set(report["child_pids"]) == {"server", "bridge"}, "server and bridge both spawned")
    run.assert_serving(report)
    assert_host_origin_guard(report["server_port"])
    check(run.process.wait(timeout=30) == 0, "launcher exit code 0")
    run.assert_cleaned(report)
    assert_no_secrets_in_logs(state)


def scenario_second_instance(binary: Path, state: Path) -> None:
    print("[single instance & SIGTERM]", flush=True)
    run = Run(binary, state)
    report = run.wait_ready()
    second = Run(binary, state)
    check(second.process.wait(timeout=30) == 3, "second instance exits with code 3")
    check(run.process.poll() is None and http_status(report["base_url"] + "/server-info") == 200, "first instance unaffected")
    run.process.send_signal(signal.SIGTERM)
    check(run.process.wait(timeout=30) == 0, "SIGTERM: launcher exit code 0")
    run.assert_cleaned(report)


def scenario_port_conflict(binary: Path, state: Path) -> None:
    print("[port conflict]", flush=True)
    # 佔住 game 優先埠與 bridge 埠（模擬其他程式）。
    blockers = [exclusive_listener(GAME_PORT), exclusive_listener(TEST_BRIDGE_PORT)]
    try:
        run = Run(binary, state, hold=4.0)
        report = run.wait_ready()
        check(report["server_port"] != GAME_PORT, f"game moved off the occupied port: {report['server_port']}")
        check(report["bridge"]["port"] != TEST_BRIDGE_PORT and report["bridge"]["mode"] == "spawned", f"bridge moved off the occupied port: {report['bridge']}")
        run.assert_serving(report)
        assert_host_origin_guard(report["server_port"])
        check(run.process.wait(timeout=30) == 0, "launcher exit code 0")
        run.assert_cleaned(report)
    finally:
        for blocker in blockers:
            blocker.close()


def scenario_lan_mode(binary: Path, state: Path) -> None:
    print("[LAN opt-in Host/Origin rules]", flush=True)
    run = Run(binary, state, extra_env={"REDLINE_APP_BIND_HOST": "0.0.0.0"})
    report = run.wait_ready()
    assert_lan_guard(report["server_port"])
    run.process.send_signal(signal.SIGTERM)
    check(run.process.wait(timeout=30) == 0, "SIGTERM: launcher exit code 0")
    run.assert_cleaned(report)


def scenario_launcher_killed(binary: Path, state: Path) -> None:
    print("[launcher SIGKILL]", flush=True)
    run = Run(binary, state)
    report = run.wait_ready()
    run.process.kill()
    run.process.wait()
    run.assert_cleaned(report, timeout=15.0)
    # flock 隨行程釋放，下一次啟動不該被視為重複實例。
    rerun = Run(binary, state, hold=0.0)
    rerun_report = rerun.wait_ready()
    check(rerun.process.wait(timeout=30) == 0, "relaunch succeeds after a crash")
    rerun.assert_cleaned(rerun_report)


def scenario_gui_and_settings(binary: Path, state: Path) -> None:
    print("[real window; settings across a port fallback]", flush=True)
    volume = FIXED_VOLUME
    written = {VOLUME_KEY: volume, "redline.sessions.v1": '{"g":{"resume_token":"SMOKE-SECRET"}}'}
    run = Run(binary, state, "--smoke-gui", "--smoke-write-settings", json.dumps(written), hold=0.0)
    report = run.wait_ready()
    print(f"  gui: {report['gui']}", flush=True)
    check(report["gui"]["gameplay"] == "ok", "same-origin fetch and WebSocket work inside the real WebView")
    check(run.process.wait(timeout=30) == 0, "launcher exit code 0 after window closes")
    run.assert_cleaned(report)
    settings_text = (state / "settings.json").read_text(encoding="utf-8")
    check(VOLUME_KEY in settings_text and "SMOKE-SECRET" not in settings_text, "settings file holds the volume but no credentials")

    blocker = exclusive_listener(report["server_port"])
    try:
        relaunch = Run(binary, state, "--smoke-gui", hold=0.0)
        moved = relaunch.wait_ready()
        print(f"  gui: {moved['gui']}", flush=True)
        check(moved["gui"]["origin"] != report["gui"]["origin"], f"relaunch used a different origin: {moved['gui']['origin']}")
        check(moved["gui"]["settings"].get(VOLUME_KEY) == volume, f"volume {volume} preserved across the port change")
        check(relaunch.process.wait(timeout=30) == 0, "launcher exit code 0 after window closes")
        relaunch.assert_cleaned(moved)
    finally:
        blocker.close()


def running_app_count() -> int:
    found = subprocess.run(["lsappinfo", "find", f"bundleid={BUNDLE_ID}"], capture_output=True, text=True, check=True).stdout
    return len(found.split())


def lock_is_free(state: Path) -> bool:
    fd = os.open(state / "instance.lock", os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def scenario_launchservices(app: Path, root: Path) -> None:
    print("[LaunchServices open -n, application quit]", flush=True)
    if running_app_count():
        raise Failure("another REDLINE is running; quit it first, the quit event targets the bundle id")
    state = root / "launchservices"
    copy = root / "copied" / "REDLINE.app"
    copy.parent.mkdir(parents=True)
    state.mkdir(parents=True)
    subprocess.run(["ditto", str(app), str(copy)], check=True)
    env_args = [arg for key, value in isolated_env(state).items() for arg in ("--env", f"{key}={value}")]
    instance_file = state / "instance.json"
    pids: list[int] = []
    try:
        subprocess.run(["open", "-n", *env_args, str(copy)], check=True, timeout=60)

        def window_ready() -> bool:
            try:
                return json.loads(instance_file.read_text(encoding="utf-8")).get("window_ready") is True
            except (OSError, ValueError):
                return False

        check(wait_until(window_ready, READY_TIMEOUT_S), "launched through LaunchServices; window finished loading")
        info = json.loads(instance_file.read_text(encoding="utf-8"))
        launcher = info["pid"]
        pids.append(launcher)
        command = subprocess.run(["ps", "-o", "command=", "-p", str(launcher)], capture_output=True, text=True).stdout
        check(str(copy.resolve()) in command or str(copy) in command, "running from the copied app")
        children = [int(pid) for pid in subprocess.run(["pgrep", "-P", str(launcher)], capture_output=True, text=True).stdout.split()]
        pids.extend(children)
        check(len(children) == 2, f"launcher owns server and bridge: {children}")
        check(http_status(info["url"] + "/server-info") == 200, "external GET /server-info == 200")

        # 與 Cmd-Q 相同：送 application quit，由 NSApplication 走 terminate 流程，不用信號。
        subprocess.run(["osascript", "-e", f'tell application id "{BUNDLE_ID}" to quit'], check=True, timeout=QUIT_TIMEOUT_S, capture_output=True)
        check(wait_until(lambda: not pid_alive(launcher), QUIT_TIMEOUT_S), "launcher exited after application quit")
        check(wait_until(lambda: not any(pid_alive(pid) for pid in children), 10.0), f"child processes gone: {children}")
        ports = [info["server_port"], info["bridge"]["port"]]
        check(wait_until(lambda: not any(port_open(port) for port in ports), 10.0), f"ports closed: {ports}")
        check(not instance_file.exists(), "instance.json removed")
        check(lock_is_free(state), "instance lock released")
        check(wait_until(lambda: running_app_count() == 0, 10.0), "LaunchServices no longer lists the app")
    except Failure:
        dump_logs(state)
        raise
    finally:
        for pid in pids:
            if pid_alive(pid):
                os.kill(pid, signal.SIGKILL)
        subprocess.run([LSREGISTER, "-u", str(copy)], capture_output=True)


def dump_logs(state: Path) -> None:
    for log_file in sorted((state / "logs").glob("*.log")):
        print(f"--- {log_file.name} ---\n{log_file.read_text(encoding='utf-8', errors='replace')[-2000:]}", flush=True)


def check_notices(path: Path) -> None:
    check(path.is_file(), str(path.name) + " present")
    text = path.read_text(encoding="utf-8")
    required_entries = (
        "pywebview", "uvicorn", "CPython", "OpenSSL", "MapLibre", "Permission is hereby granted",
        # PyInstaller 會打包 setuptools 的這些 vendored 模組（build.sh 另以實際 PYZ 內容檢查）。
        "vendored: jaraco.text ", "vendored: more_itertools ", "vendored: packaging ", "vendored: tomli ",
        "vendored: wheel ", "vendored: backports.tarfile ", "setuptools/_vendor/",
    )
    for required in required_entries:
        check(required in text, f"notices mention {required}")


def check_structure(app: Path) -> Path:
    print(f"[structure] {app}", flush=True)
    binary = app / "Contents/MacOS/REDLINE"
    check(binary.is_file() and os.access(binary, os.X_OK), "Contents/MacOS/REDLINE is executable")
    archs = subprocess.run(["lipo", "-archs", str(binary)], capture_output=True, text=True).stdout.strip()
    check(archs == "arm64", f"binary architecture: {archs}")
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    check(info["CFBundleIdentifier"] == "io.github.kuiming.redline" and bool(info["CFBundleShortVersionString"]), f"Info.plist version {info['CFBundleShortVersionString']}")
    resources = app / "Contents/Resources"
    for relative in ("static/index.html", "static/app.js", "data/map.json", "rules.md", "LICENSE.md", "LICENSE-CODE"):
        check((resources / relative).is_file(), f"Resources/{relative}")
    check((app / "Contents/Frameworks/static").exists(), "static reachable from the runtime root")
    check_notices(resources / "THIRD-PARTY-NOTICES.txt")
    assert_card_art_bundled(resources)
    check((resources / info["CFBundleIconFile"]).is_file(), f"icon {info['CFBundleIconFile']}")
    check(subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], capture_output=True).returncode == 0, "signature valid (ad-hoc)")
    return binary


def run_scenarios(app: Path, gui: bool) -> None:
    binary = check_structure(app)
    before = {path for path in USER_STATE_PATHS if path.exists()}
    with tempfile.TemporaryDirectory(prefix="redline-smoke-", ignore_cleanup_errors=True) as temp:
        root = Path(temp)
        scenarios = {
            "clean": lambda state: scenario_clean_exit(binary, state),
            "second": lambda state: scenario_second_instance(binary, state),
            "conflict": lambda state: scenario_port_conflict(binary, state),
            "lan": lambda state: scenario_lan_mode(binary, state),
            "killed": lambda state: scenario_launcher_killed(binary, state),
        }
        if gui:
            scenarios["gui"] = lambda state: scenario_gui_and_settings(binary, state)
        for name, scenario in scenarios.items():
            state = root / name
            state.mkdir()
            try:
                scenario(state)
            except Failure:
                dump_logs(state)
                raise
        if gui:
            scenario_launchservices(app, root)
    created = sorted(str(path) for path in USER_STATE_PATHS if path.exists() and path not in before)
    check(not created, f"no user state created in the real home directory: {created}")


def detach(mount: str) -> None:
    for attempt in range(6):
        force = ["-force"] if attempt == 5 else []
        if subprocess.run(["hdiutil", "detach", mount, *force], capture_output=True).returncode == 0:
            return
        time.sleep(2)
    raise Failure(f"could not detach {mount}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--app", type=Path)
    target.add_argument("--dmg", type=Path)
    parser.add_argument("--gui", action="store_true", help="另外開真實視窗驗證（需要已登入的桌面工作階段）")
    args = parser.parse_args()
    try:
        if args.app:
            run_scenarios(args.app.resolve(), args.gui)
        else:
            with tempfile.TemporaryDirectory(prefix="redline-dmg-") as mount:
                subprocess.run(["hdiutil", "attach", str(args.dmg), "-nobrowse", "-readonly", "-mountpoint", mount], check=True, stdout=subprocess.DEVNULL)
                try:
                    print(f"[dmg] {args.dmg}: {sorted(p.name for p in Path(mount).iterdir())}", flush=True)
                    check((Path(mount) / "Applications").is_symlink(), "Applications shortcut")
                    check_notices(Path(mount) / "THIRD-PARTY-NOTICES.txt")
                    for name in ("LICENSE.md", "LICENSE-CODE"):
                        check((Path(mount) / name).is_file(), f"DMG root has {name}")
                    run_scenarios(Path(mount) / "REDLINE.app", args.gui)
                finally:
                    # 啟動過的 App 會被 LaunchServices 記錄；路徑還在時才能註銷。
                    subprocess.run([LSREGISTER, "-u", str(Path(mount) / "REDLINE.app")], capture_output=True)
                    detach(mount)
    except Failure as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    print("SMOKE PASSED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
