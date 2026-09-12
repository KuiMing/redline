"""Real Docker/MCP smoke for the host-side Red Army controller.

The smoke uses real lobby HTTP, real WebSockets, and real Streamable HTTP MCP.
A deterministic fake Agent advances legal turns, so no model token is used.
No /test/* endpoint is enabled or called. Proof output contains no game/player IDs.
"""

from __future__ import annotations

import asyncio
import json
import os
import stat
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from red_army_controller.config import ControllerConfig
from red_army_controller.controller import RedArmyController
from red_army_controller.hermes_runner import AgentRunResult
from red_army_controller.mcp_gateway import MCPGateway

RECORD_DIR = ROOT / "docs" / "records" / "mcp-server"
OUT_JSON = RECORD_DIR / "RED_ARMY_CONTROLLER_SMOKE.json"
OUT_MD = RECORD_DIR / "RED_ARMY_CONTROLLER_SMOKE.md"


async def perform_safe_pass(gateway: MCPGateway, game_id: str, player_id: str) -> bool:
    """Resolve the first legal choice or advance. Return False after turn handoff."""
    state = await gateway.call("get_state", {"game_id": game_id, "player_id": player_id})
    summary = state.get("state") or {}
    pending = summary.get("pending_choice") or {}
    if not summary.get("is_my_turn") and not pending.get("is_mine_to_resolve"):
        return False
    legal = await gateway.call("get_legal_actions", {"game_id": game_id, "player_id": player_id})
    actions = legal.get("actions") or []
    if not actions:
        return False
    action = actions[0]
    kind = action.get("kind")
    arguments: dict[str, object] = {"game_id": game_id, "player_id": player_id}
    if kind == "resolve_pending_choice":
        if action.get("use_indices_param"):
            count = int(action.get("count") or action.get("min_count") or 1)
            upper = int((action.get("index_range") or [0, 0])[1])
            arguments["indices"] = list(range(min(count, upper + 1)))
        else:
            arguments["index"] = 0
        result = await gateway.call(kind, arguments)
    elif kind == "set_base":
        option = (action.get("options") or [])[0]
        arguments.update({"town": option["town"], "label": option.get("label")})
        result = await gateway.call(kind, arguments)
    else:
        advance = next((candidate for candidate in actions if candidate.get("kind") == "advance_turn"), None)
        if advance is None:
            raise RuntimeError(f"Smoke actor cannot safely pass legal action kind: {kind}")
        result = await gateway.call("advance_turn", arguments)
    if not result.get("ok"):
        raise RuntimeError("Legal smoke action failed")
    return True


class FakeAgent:
    def __init__(self, mcp_url: str):
        self.mcp_url = mcp_url
        self.game_id: str | None = None
        self.player_id: str | None = None
        self.invocations = 0
        self.private_prompt_was_clean = True

    async def run(self, prompt: str) -> AgentRunResult:
        self.invocations += 1
        self.private_prompt_was_clean &= "resume_token" in prompt and "private-resume-token" not in prompt
        assert self.game_id and self.player_id
        async with MCPGateway(self.mcp_url) as gateway:
            for _ in range(12):
                if not await perform_safe_pass(gateway, self.game_id, self.player_id):
                    break
        return AgentRunResult(0)


async def wait_until(predicate, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if await predicate():
            return
        await asyncio.sleep(0.1)
    raise TimeoutError("Smoke condition was not reached")


async def run_smoke(mcp_url: str) -> dict:
    checks: list[dict] = []

    def record(name: str, ok: bool) -> None:
        checks.append({"name": name, "ok": bool(ok)})

    with tempfile.TemporaryDirectory(prefix="redline-red-army-smoke-") as temporary:
        state_path = Path(temporary) / "seat.json"
        fake = FakeAgent(mcp_url)
        config = ControllerConfig(
            mcp_url=mcp_url,
            state_file=state_path,
            poll_seconds=0.1,
            post_agent_settle_seconds=0,
            failure_backoff_seconds=0.2,
        )
        controller = RedArmyController(config, runner=fake)
        credentials = await controller.create()
        fake.game_id = credentials.game_id
        fake.player_id = credentials.player_id
        record("creates_and_selects_red_army", bool(credentials.game_id))
        record("credential_file_is_0600", stat.S_IMODE(state_path.stat().st_mode) == 0o600)

        async with MCPGateway(mcp_url) as human:
            joined = await human.call("join_room", {"game_id": credentials.game_id, "player_name": "Human Smoke"})
            human_id = str(joined["player_id"])
            selected = await human.call("choose_faction", {
                "game_id": credentials.game_id,
                "player_id": human_id,
                "faction_id": "taiwan_green",
            })
            assert selected.get("ok")
            ready = await human.call("set_ready", {
                "game_id": credentials.game_id,
                "player_id": human_id,
                "ready": True,
            })
            assert ready.get("ok")

            task = asyncio.create_task(controller.run(credentials))
            try:
                async def started() -> bool:
                    room = await human.call("get_room_status", {"game_id": credentials.game_id})
                    return bool(room.get("started"))

                await wait_until(started)
                record("auto_starts_when_all_seats_ready", True)

                for _ in range(24):
                    human_state = await human.call("get_state", {"game_id": credentials.game_id, "player_id": human_id})
                    human_summary = human_state.get("state") or {}
                    if fake.invocations:
                        break
                    if human_summary.get("is_my_turn") or (human_summary.get("pending_choice") or {}).get("is_mine_to_resolve"):
                        await perform_safe_pass(human, credentials.game_id, human_id)
                    else:
                        await asyncio.sleep(0.1)

                async def agent_ran() -> bool:
                    return fake.invocations > 0

                await wait_until(agent_ran)
                record("automatically_invokes_agent_for_red_army", True)

                async def red_handed_off() -> bool:
                    state = await human.call("get_state", {"game_id": credentials.game_id, "player_id": credentials.player_id})
                    summary = state.get("state") or {}
                    pending = summary.get("pending_choice") or {}
                    return not summary.get("is_my_turn") and not pending.get("is_mine_to_resolve")

                await wait_until(red_handed_off)
                record("fake_agent_completes_red_army_handoff", True)
                record("resume_token_never_enters_agent_prompt", fake.private_prompt_was_clean)
            finally:
                controller.stop()
                await asyncio.wait_for(task, timeout=5)

        # A new MCP client session must rehydrate the stored seat without model help.
        resumed_controller = RedArmyController(config, runner=fake)
        status = await resumed_controller.status()
        record("controller_restart_rehydrates_seat", status is not None and status.game_id == credentials.game_id)

    return {
        "summary": {
            "total": len(checks),
            "passed": sum(1 for item in checks if item["ok"]),
            "failed": sum(1 for item in checks if not item["ok"]),
        },
        "results": checks,
    }


def main() -> None:
    mcp_url = os.environ.get("REDLINE_MCP_URL", "http://127.0.0.1:8765/mcp")
    payload = asyncio.run(run_smoke(mcp_url))
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# REDLINE automatic Red Army controller smoke",
        "",
        "Real Docker game server + Streamable HTTP MCP + host controller. The Agent is deterministic and fake, so no model token is used. No `/test/*` route is enabled or called. Proof contains no runtime game/player identifiers.",
        "",
        f"- total: {payload['summary']['total']} / passed: {payload['summary']['passed']} / failed: {payload['summary']['failed']}",
        "",
    ]
    for result in payload["results"]:
        lines.append(f"- {'✅' if result['ok'] else '❌'} `{result['name']}`")
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    if payload["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
