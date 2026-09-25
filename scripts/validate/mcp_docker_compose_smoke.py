"""Real `docker build` + `docker compose up` proof for docker-compose.yml:
builds both images, brings up an isolated test stack (own Compose project
name, own host ports — never touches the production 8000 port or any
existing container), confirms:

  - `redline`'s HTTP healthcheck passes (game server up)
  - `redline-mcp`'s `/health` passes (MCP process up)
  - a real MCP tool call over Streamable HTTP reaches the `redline` service
    *through the Compose-internal network* (REDLINE_BASE_URL=http://redline:8000
    as baked into docker-compose.yml — not host.docker.internal, not a
    published port)

...then tears the stack down. This does NOT prove a production deployment;
see docs/mcp_server.md's "Build vs. test stack vs. deploy" note.

Run: `uv run python scripts/validate/mcp_docker_compose_smoke.py`
(needs Docker running; takes a few minutes for the image builds)
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "mcp-server"
OUT_JSON = RECORD_DIR / "MCP_DOCKER_COMPOSE_SMOKE.json"
OUT_MD = RECORD_DIR / "MCP_DOCKER_COMPOSE_SMOKE.md"

# Unique per run so this can never collide with a real deployment's project
# name (which would be the repo directory name, e.g. "redline") or with a
# concurrent run of this same script.
PROJECT_NAME = f"redline-mcp-smoke-{uuid.uuid4().hex[:8]}"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-p", PROJECT_NAME, "-f", str(ROOT / "docker-compose.yml"), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=check,
    )


def _wait_http_ok(url: str, deadline_seconds: float = 90) -> bool:
    import urllib.request

    deadline = time.time() + deadline_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False


async def _check_mcp_reaches_redline_over_internal_network(mcp_base_url: str) -> dict:
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with streamable_http_client(f"{mcp_base_url}/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("list_factions", {})
            text = result.content[0].text if result.content else "{}"
            data = json.loads(text)
            return {
                "is_error": result.is_error,
                "ok": data.get("ok"),
                "faction_count": len(data.get("factions", [])),
            }


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    def record(name, ok, detail=None):
        results.append({"name": name, "ok": bool(ok), "detail": detail or {}})

    redline_host_port = _free_port()
    mcp_host_port = _free_port()
    env = dict(os.environ)
    env["REDLINE_HOST_PORT"] = str(redline_host_port)
    env["REDLINE_MCP_HOST_PORT"] = str(mcp_host_port)

    build = subprocess.run(
        ["docker", "compose", "-p", PROJECT_NAME, "-f", str(ROOT / "docker-compose.yml"), "build"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    record("docker_compose_build_succeeds", build.returncode == 0, {"returncode": build.returncode})

    up = None
    try:
        if build.returncode == 0:
            up = subprocess.run(
                ["docker", "compose", "-p", PROJECT_NAME, "-f", str(ROOT / "docker-compose.yml"), "up", "-d"],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
            )
            record("docker_compose_up_succeeds", up.returncode == 0, {"returncode": up.returncode})

            redline_ready = _wait_http_ok(f"http://127.0.0.1:{redline_host_port}/server-info")
            record("redline_service_becomes_healthy", redline_ready, {})

            mcp_ready = _wait_http_ok(f"http://127.0.0.1:{mcp_host_port}/health")
            record("mcp_service_becomes_healthy", mcp_ready, {})

            if redline_ready and mcp_ready:
                try:
                    call_result = asyncio.run(
                        _check_mcp_reaches_redline_over_internal_network(f"http://127.0.0.1:{mcp_host_port}")
                    )
                    record(
                        "mcp_tool_call_reaches_redline_over_compose_internal_network",
                        call_result["is_error"] is not True and call_result["ok"] is True and call_result["faction_count"] > 0,
                        call_result,
                    )
                except Exception as exc:  # pragma: no cover - proof output, not a hard failure path
                    record("mcp_tool_call_reaches_redline_over_compose_internal_network", False, {"error": str(exc)})
    finally:
        down = subprocess.run(
            ["docker", "compose", "-p", PROJECT_NAME, "-f", str(ROOT / "docker-compose.yml"), "down", "-v", "--remove-orphans"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        record("docker_compose_down_succeeds", down.returncode == 0, {"returncode": down.returncode})

    payload = {
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r["ok"]),
            "failed": sum(1 for r in results if not r["ok"]),
        },
        "results": results,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# REDLINE MCP server — Docker Compose stack smoke",
        "",
        "Real `docker compose build` + `up -d` + teardown of docker-compose.yml, using an isolated "
        "project name and isolated free host ports (never the production 8000 port or an existing "
        "container). This proves the test stack starts and the MCP service can reach `redline` over the "
        "Compose-internal network — it does NOT mean anything was deployed. Rerun: "
        "`uv run python scripts/validate/mcp_docker_compose_smoke.py` (needs Docker; a few minutes).",
        "",
        f"- total: {payload['summary']['total']} / passed: {payload['summary']['passed']} / failed: {payload['summary']['failed']}",
        "",
        "## Results",
    ]
    for result in payload["results"]:
        icon = "✅" if result["ok"] else "❌"
        lines.append(f"- {icon} `{result['name']}`")
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    if payload["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
