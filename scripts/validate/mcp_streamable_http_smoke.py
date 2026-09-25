"""Protocol-level proof for the REDLINE MCP server's Streamable HTTP
transport: spawns `python -m mcp_server --transport streamable-http` as a
real subprocess bound to a real socket, and talks real MCP-over-HTTP to it
(initialize, tools/list, resources/list, tools/call) via the official `mcp`
client SDK, plus raw HTTP requests to verify the DNS-rebinding Host/Origin
protection actually rejects a spoofed request (this needs genuine HTTP
headers over a real socket — the in-process ASGI-transport unit tests in
scripts/tests/test_mcp_http_transport.py deliberately disable this check).

It also spawns a real REDLINE HTTP+WebSocket server (server.main:app) as a
second subprocess, on an isolated port, WITHOUT ENABLE_TEST_ROUTES.

Deliberately does not create a room/game: every check here uses tools that
need no game_id/player_id (list_factions, get_rules_text, ...), so the
recorded proof has no per-run credentials/ids to redact or normalize in the
first place — see scripts/validate/mcp_stdio_smoke.py for that concern.

Run: `uv run python scripts/validate/mcp_streamable_http_smoke.py`
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "mcp-server"
OUT_JSON = RECORD_DIR / "MCP_STREAMABLE_HTTP_SMOKE.json"
OUT_MD = RECORD_DIR / "MCP_STREAMABLE_HTTP_SMOKE.md"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(url: str, deadline_seconds: float = 20) -> None:
    import urllib.request

    deadline = time.time() + deadline_seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError(f"{url} did not become ready in time")


def _start_redline_server(port: int) -> subprocess.Popen:
    env = {k: v for k, v in os.environ.items() if k != "ENABLE_TEST_ROUTES"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_ready(f"http://127.0.0.1:{port}/factions")
    except RuntimeError:
        proc.terminate()
        raise
    return proc


def _start_mcp_http_server(redline_base_url: str, port: int) -> subprocess.Popen:
    env = dict(os.environ)
    env["REDLINE_BASE_URL"] = redline_base_url
    env["REDLINE_MCP_HTTP_HOST"] = "127.0.0.1"  # real socket; not the container 0.0.0.0 bind
    env["REDLINE_MCP_HTTP_PORT"] = str(port)
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_server", "--transport", "streamable-http"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_ready(f"http://127.0.0.1:{port}/health")
    except RuntimeError:
        proc.terminate()
        raise
    return proc


async def _run(mcp_base_url: str) -> dict:
    import httpx2
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    results = []

    def record(name, ok, detail=None):
        results.append({"name": name, "ok": bool(ok), "detail": detail or {}})

    health_url = f"{mcp_base_url}/health"
    mcp_url = f"{mcp_base_url}/mcp"

    async with httpx2.AsyncClient() as raw_client:
        health_response = await raw_client.get(health_url)
        record(
            "health_endpoint_ok_without_any_game_backend_dependency",
            health_response.status_code == 200 and health_response.json().get("status") == "ok",
            {"status_code": health_response.status_code, "body": health_response.json()},
        )

        # DNS-rebinding protection: a request whose Host header doesn't match
        # any allowed_hosts pattern must be rejected before it ever reaches
        # MCP session handling (see mcp_server/__main__.py's
        # _run_streamable_http and mcp_server/config.py's DEFAULT_ALLOWED_HOSTS).
        spoofed_host_response = await raw_client.post(
            mcp_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Host": "evil.example.com",
            },
            content=json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "0"}}}
            ),
        )
        record(
            "dns_rebinding_protection_rejects_spoofed_host_header",
            spoofed_host_response.status_code == 421,
            {"status_code": spoofed_host_response.status_code},
        )

        spoofed_origin_response = await raw_client.post(
            mcp_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Origin": "http://evil.example.com",
            },
            content=json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "0"}}}
            ),
        )
        record(
            "dns_rebinding_protection_rejects_spoofed_origin_header",
            spoofed_origin_response.status_code == 403,
            {"status_code": spoofed_origin_response.status_code},
        )

    async with streamable_http_client(mcp_url) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            record("initialize_succeeds", init.server_info.name == "redline", {"server_info": str(init.server_info)})

            tools = await session.list_tools()
            record("tool_count_is_32", len(tools.tools) == 32, {"count": len(tools.tools)})

            resources = await session.list_resources()
            record(
                "rules_resource_listed",
                any(str(r.uri) == "redline://rules" for r in resources.resources),
                {"resources": [str(r.uri) for r in resources.resources]},
            )

            async def call(name, args):
                result = await session.call_tool(name, args)
                text = result.content[0].text if result.content else "{}"
                return json.loads(text), result.is_error

            # Deliberately game-state-free calls (see module docstring) —
            # still real REDLINE-backed data (list_factions round-trips to
            # the live REDLINE server's own /factions endpoint), just
            # nothing tied to a specific room/player.
            rules_text, err = await call("get_rules_text", {})
            record(
                "get_rules_text_ok",
                rules_text.get("ok") is True and not err,
                {"ok": rules_text.get("ok"), "length": len(rules_text.get("rules_markdown", ""))},
            )

            factions, err = await call("list_factions", {})
            record(
                "list_factions_reaches_real_redline_server",
                factions.get("ok") is True and not err and any(f.get("faction_id") == "red_army" for f in factions.get("factions", [])),
                {"ok": factions.get("ok"), "faction_count": len(factions.get("factions", []))},
            )

    return {
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r["ok"]),
            "failed": sum(1 for r in results if not r["ok"]),
        },
        "results": results,
    }


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    redline_port = _free_port()
    mcp_port = _free_port()
    redline_proc = _start_redline_server(redline_port)
    try:
        mcp_proc = _start_mcp_http_server(f"http://127.0.0.1:{redline_port}", mcp_port)
    except Exception:
        redline_proc.terminate()
        raise
    try:
        payload = asyncio.run(_run(f"http://127.0.0.1:{mcp_port}"))
    finally:
        for proc in (mcp_proc, redline_proc):
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# REDLINE MCP server — Streamable HTTP protocol smoke",
        "",
        "Real `python -m mcp_server --transport streamable-http` subprocess on a real socket, talking real "
        "MCP-over-HTTP to a real REDLINE HTTP+WS server (isolated ports, /test/* routes disabled). No room/game "
        "is created (see module docstring), so there is no per-run credential/id content to redact. Rerun: "
        "`uv run python scripts/validate/mcp_streamable_http_smoke.py`",
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
