"""Prove that the host controller resumes its seat after the MCP container restarts.

Builds an isolated two-service Compose stack on free host ports, creates a Red
Army lobby seat, restarts only redline-mcp while the game container remains
alive, and resumes from the 0600 state file. No /test/* route or model is used.
Proof contains no runtime room/player identifiers.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
RECORD_DIR = ROOT / "docs" / "records" / "mcp-server"
OUT_JSON = RECORD_DIR / "RED_ARMY_MCP_RESTART_SMOKE.json"
OUT_MD = RECORD_DIR / "RED_ARMY_MCP_RESTART_SMOKE.md"
PROJECT = f"redline-red-army-restart-{uuid.uuid4().hex[:8]}"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def compose(env: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-p", PROJECT, "-f", str(ROOT / "docker-compose.yml"), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def wait_health(url: str, timeout: float = 60) -> bool:
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


async def create_and_resume(mcp_url: str, state_file: Path, restart) -> bool:
    from red_army_controller.config import ControllerConfig
    from red_army_controller.controller import RedArmyController

    config = ControllerConfig(mcp_url=mcp_url, state_file=state_file)
    controller = RedArmyController(config)
    await controller.create()
    if not restart():
        return False
    resumed = RedArmyController(config)
    status = await resumed.status()
    return status is not None and status.phase == "lobby"


def main() -> None:
    game_port = free_port()
    mcp_port = free_port()
    env = dict(os.environ)
    env.update({"REDLINE_HOST_PORT": str(game_port), "REDLINE_MCP_HOST_PORT": str(mcp_port)})
    mcp_health = f"http://127.0.0.1:{mcp_port}/health"
    mcp_url = f"http://127.0.0.1:{mcp_port}/mcp"
    results: list[dict] = []

    def record(name: str, ok: bool) -> None:
        results.append({"name": name, "ok": bool(ok)})

    build = compose(env, "build")
    record("compose_build_succeeds", build.returncode == 0)
    up = None
    try:
        if build.returncode == 0:
            up = compose(env, "up", "-d")
            record("compose_up_succeeds", up.returncode == 0)
            ready = up.returncode == 0 and wait_health(mcp_health)
            record("mcp_becomes_healthy", ready)
            if ready:
                with tempfile.TemporaryDirectory(prefix="redline-mcp-restart-") as temporary:
                    def restart() -> bool:
                        result = compose(env, "restart", "redline-mcp")
                        record("mcp_container_restart_succeeds", result.returncode == 0)
                        healthy = result.returncode == 0 and wait_health(mcp_health)
                        record("restarted_mcp_becomes_healthy", healthy)
                        return healthy

                    try:
                        resumed = asyncio.run(create_and_resume(mcp_url, Path(temporary) / "seat.json", restart))
                    except Exception:
                        resumed = False
                    record("controller_resumes_seat_after_mcp_process_restart", resumed)
    finally:
        down = compose(env, "down", "-v", "--remove-orphans")
        record("compose_down_succeeds", down.returncode == 0)
        subprocess.run(
            ["docker", "image", "rm", f"{PROJECT}-redline-mcp:latest", f"{PROJECT}-redline:latest"],
            capture_output=True,
            text=True,
        )

    payload = {
        "summary": {
            "total": len(results),
            "passed": sum(1 for item in results if item["ok"]),
            "failed": sum(1 for item in results if not item["ok"]),
        },
        "results": results,
    }
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# REDLINE Red Army controller — MCP restart smoke",
        "",
        "An isolated Docker Compose stack creates a Red Army seat, restarts only `redline-mcp`, and resumes through the new MCP process while the game process remains alive. No model or `/test/*` route is used. Proof contains no runtime identifiers.",
        "",
        f"- total: {payload['summary']['total']} / passed: {payload['summary']['passed']} / failed: {payload['summary']['failed']}",
        "",
    ]
    lines.extend(f"- {'✅' if item['ok'] else '❌'} `{item['name']}`" for item in results)
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    if payload["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
