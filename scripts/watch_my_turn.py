"""Poll a REDLINE MCP seat and print one line each time it becomes this
seat's turn to act -- either its own turn, or a pending_choice that belongs
to it. Silent while waiting on another player, so this only emits real
turn-transition events, not a busy log.

Meant to be run as a background/monitored process by an Agent runtime (e.g.
Claude Code's `Monitor` tool, or any mechanism that turns a subprocess's
stdout lines into notifications) so the Agent gets woken up only when there
is something to actually do, instead of polling get_state itself in a loop.
See "讓 Agent 跟真人對局" in the project README for the full walkthrough.

Usage:
    uv run python scripts/watch_my_turn.py --creds /path/to/seat.json

The credentials file is the same {game_id, player_id, resume_token, ...}
JSON shape red_army_controller.state_store.StateStore writes (permissions
must be 0600) -- reuse a controller-created one, or hand-write one after
create_room/join_room:

    {"game_id": "...", "player_id": "...", "resume_token": "..."}
    chmod 600 /path/to/seat.json
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from red_army_controller.mcp_gateway import MCPGateway
from red_army_controller.state_store import StateFileError, StateStore

DEFAULT_MCP_URL = "http://127.0.0.1:8765/mcp"
DEFAULT_POLL_SECONDS = 3.0


def actionable(state: dict) -> str | None:
    s = state.get("state") or {}
    if s.get("game_over"):
        return "game_over"
    pending = s.get("pending_choice") or {}
    if pending:
        return "pending_choice" if pending.get("is_mine_to_resolve") else None
    if s.get("is_my_turn"):
        return "my_turn"
    return None


async def watch(creds_path: Path, mcp_url: str, poll_seconds: float) -> None:
    try:
        creds = StateStore(creds_path).load()
    except StateFileError as exc:
        print(f"[watch] cannot load credentials from {creds_path}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    was_actionable = False
    async with MCPGateway(mcp_url) as gw:
        while True:
            try:
                state = await gw.call(
                    "get_state",
                    {
                        "game_id": creds.game_id,
                        "player_id": creds.player_id,
                        "resume_token": creds.resume_token,
                    },
                )
            except Exception as exc:  # transient MCP/transport hiccup -- keep polling
                print(f"[watch] transient error, retrying: {type(exc).__name__}", flush=True)
                await asyncio.sleep(poll_seconds)
                continue

            reason = actionable(state)
            if reason == "game_over":
                print("[watch] game_over", flush=True)
                return
            if reason and not was_actionable:
                turn = (state.get("state") or {}).get("turn")
                print(f"[watch] your_turn reason={reason} turn={turn}", flush=True)
            was_actionable = bool(reason)
            await asyncio.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--creds", required=True, type=Path,
        help="Path to the seat credentials JSON (0600 permissions; {game_id, player_id, resume_token}).",
    )
    parser.add_argument(
        "--mcp-url", default=DEFAULT_MCP_URL,
        help=f"REDLINE MCP Streamable HTTP endpoint (default: {DEFAULT_MCP_URL}).",
    )
    parser.add_argument(
        "--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS,
        help=f"Seconds between polls (default: {DEFAULT_POLL_SECONDS}).",
    )
    args = parser.parse_args()
    asyncio.run(watch(args.creds, args.mcp_url, args.poll_seconds))


if __name__ == "__main__":
    main()
