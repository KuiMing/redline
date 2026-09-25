"""Protocol-level proof for the REDLINE MCP server: actually spawns
`python -m mcp_server` as a subprocess and talks real MCP-over-stdio to it
(initialize, tools/list, resources/list, tools/call) via the official
`mcp` client SDK — not a unit test calling Python functions directly.

It also spawns a real REDLINE HTTP+WebSocket server (server.main:app) as a
second subprocess, on an isolated port, WITHOUT ENABLE_TEST_ROUTES, so the
whole run proves the MCP layer works against the public boundary only.

Run: `uv run python scripts/validate/mcp_stdio_smoke.py`
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "mcp-server"
OUT_JSON = RECORD_DIR / "MCP_STDIO_SMOKE.json"
OUT_MD = RECORD_DIR / "MCP_STDIO_SMOKE.md"

# Each run creates a fresh room with random game_id/player_id/resume_token —
# committing those to docs/records/ would (a) leave the worktree dirty after
# every rerun (pure diff noise) and (b) commit live-looking credentials/ids
# that are meaningless outside this one process anyway. Redact by shape
# (UUIDs and long url-safe-base64-ish tokens), not by key name, so this
# stays correct even if a new field is added later. Ordinary game content
# (Chinese card/event names, short English words) never matches.
_DYNAMIC_VALUE_RE = re.compile(r"^[A-Za-z0-9_-]{20,}$")


def _redact_dynamic_values(value):
    if isinstance(value, dict):
        return {k: _redact_dynamic_values(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_dynamic_values(v) for v in value]
    if isinstance(value, str) and _DYNAMIC_VALUE_RE.match(value):
        return "<redacted>"
    return value


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_redline_server(port: int) -> subprocess.Popen:
    env = {k: v for k, v in os.environ.items() if k != "ENABLE_TEST_ROUTES"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    import urllib.request

    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/factions", timeout=1)
            return proc
        except Exception:
            time.sleep(0.3)
    proc.terminate()
    raise RuntimeError("REDLINE test server did not become ready in time")


async def _run(base_url: str) -> dict:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    results = []

    def record(name, ok, detail=None):
        results.append({"name": name, "ok": bool(ok), "detail": detail or {}})

    env = dict(os.environ)
    env["REDLINE_BASE_URL"] = base_url
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server"], cwd=str(ROOT), env=env)

    async with stdio_client(params) as (read, write):
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

            rules_content = await session.read_resource("redline://rules")
            rules_text = rules_content.contents[0].text if rules_content.contents else ""
            record("rules_resource_readable", "勝利條件" in rules_text, {"length": len(rules_text)})

            async def call(name, args):
                result = await session.call_tool(name, args)
                text = result.content[0].text if result.content else "{}"
                return json.loads(text), result.is_error

            host, err = await call("create_room", {"player_name": "SmokeHost"})
            record("create_room_ok", host.get("ok") is True and not err, host)
            game_id, host_id = host.get("game_id"), host.get("player_id")

            guest, err = await call("join_room", {"game_id": game_id, "player_name": "SmokeGuest"})
            record("join_room_ok", guest.get("ok") is True and not err, guest)
            guest_id = guest.get("player_id")

            await call("choose_faction", {"game_id": game_id, "player_id": host_id, "faction_id": "red_army"})
            await call(
                "choose_faction",
                {"game_id": game_id, "player_id": guest_id, "faction_id": "taiwan_green", "base_name": "臺北"},
            )
            await call("set_ready", {"game_id": game_id, "player_id": host_id})
            await call("set_ready", {"game_id": game_id, "player_id": guest_id})

            started, err = await call("start_game", {"game_id": game_id, "player_id": host_id})
            record("start_game_ok", started.get("ok") is True and not err, started)

            # Drain any immediate opening pending choice (random first event) before
            # asserting on legal actions — see scripts/tests/test_mcp_e2e_smoke.py.
            for player_id in (host_id, guest_id):
                for _ in range(5):
                    legal, _ = await call("get_legal_actions", {"game_id": game_id, "player_id": player_id})
                    entry = next((a for a in legal.get("actions", []) if a["kind"] == "resolve_pending_choice"), None)
                    if entry is None:
                        break
                    if entry.get("use_indices_param"):
                        pick = list(range(entry.get("min_count") or entry.get("count") or 0))
                        await call("resolve_pending_choice", {"game_id": game_id, "player_id": player_id, "indices": pick})
                    else:
                        await call("resolve_pending_choice", {"game_id": game_id, "player_id": player_id, "index": 0})

            # Detail payloads below deliberately capture shape (key sets,
            # booleans, counts) rather than the actual random game content
            # (which event/cards were drawn, hand order, ...) — the game
            # engine shuffles with no fixed seed, so raw content would make
            # every rerun's proof differ for no meaningful reason. See the
            # module docstring's redaction note for the id/token half of
            # this same concern.
            host_state, err = await call("get_state", {"game_id": game_id, "player_id": host_id})
            record(
                "get_state_ok_and_privacy_scoped",
                host_state.get("ok") is True and not err,
                {"ok": host_state.get("ok"), "state_keys": sorted((host_state.get("state") or {}).keys())},
            )

            host_players, err = await call(
                "get_state_detail", {"game_id": game_id, "player_id": host_id, "section": "players"}
            )
            guest_row = next(p for p in host_players.get("value", []) if p["id"] == guest_id)
            hand_is_redacted = all(card == "未知手牌" for card in guest_row.get("hand", []))
            record(
                "other_players_hand_redacted",
                hand_is_redacted,
                {"hand_entries_are_placeholder": hand_is_redacted},
            )

            current_name = host_state["state"]["current_player_name"]
            actor_id = host_id if current_name == "SmokeHost" else guest_id
            legal, _ = await call("get_legal_actions", {"game_id": game_id, "player_id": actor_id})
            play_entry = next((a for a in legal.get("actions", []) if a["kind"] == "play_card"), None)
            record(
                "legal_actions_lists_play_card",
                play_entry is not None,
                {"ok": legal.get("ok"), "action_kinds": sorted({a["kind"] for a in legal.get("actions", [])})},
            )

            if play_entry is not None:
                played, err = await call(
                    "play_card", {"game_id": game_id, "player_id": actor_id, "index": play_entry["index"], "mode": "resource"}
                )
                record("play_card_ok", played.get("ok") is True and not err, {"ok": played.get("ok"), "error": err})

            advanced, err = await call("advance_turn", {"game_id": game_id, "player_id": actor_id})
            record("advance_turn_ok", advanced.get("ok") is True and not err, {"ok": advanced.get("ok"), "error": err})

            card_detail, _ = await call("get_card_detail", {"name": "追隨者"})
            record("get_card_detail_ok", card_detail.get("ok") is True, card_detail)

            faction_detail, _ = await call("get_faction_detail", {"faction_id": "red_army"})
            record("get_faction_detail_ok", faction_detail.get("ok") is True, faction_detail)

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
    port = _free_port()
    server_proc = _start_redline_server(port)
    try:
        payload = asyncio.run(_run(f"http://127.0.0.1:{port}"))
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()

    redacted_payload = _redact_dynamic_values(payload)
    OUT_JSON.write_text(json.dumps(redacted_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# REDLINE MCP server — stdio protocol smoke",
        "",
        "Real `python -m mcp_server` subprocess talking MCP-over-stdio to a real REDLINE HTTP+WS server "
        "(isolated port, /test/* routes disabled). Rerun: `uv run python scripts/validate/mcp_stdio_smoke.py`",
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
