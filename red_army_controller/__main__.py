from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import signal
from pathlib import Path

from red_army_controller.config import ControllerConfig
from red_army_controller.controller import ControllerStopped, RedArmyController


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automatic REDLINE Red Army controller")
    parser.add_argument("command", choices=["create", "run", "status"])
    parser.add_argument("--mcp-url")
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--hermes-profile")
    parser.add_argument("--hermes-binary")
    parser.add_argument("--mcp-server-name")
    parser.add_argument("--poll-seconds", type=float)
    return parser


def _config(args: argparse.Namespace) -> ControllerConfig:
    config = ControllerConfig.from_env()
    overrides = {}
    for argument, field in (
        ("mcp_url", "mcp_url"),
        ("state_file", "state_file"),
        ("name", "player_name"),
        ("hermes_profile", "hermes_profile"),
        ("hermes_binary", "hermes_binary"),
        ("mcp_server_name", "mcp_server_name"),
        ("poll_seconds", "poll_seconds"),
    ):
        value = getattr(args, argument)
        if value is not None:
            overrides[field] = value
    return dataclasses.replace(config, **overrides)


def _status_json(status) -> str:
    return json.dumps(dataclasses.asdict(status), ensure_ascii=False)


async def _main_async(args: argparse.Namespace) -> int:
    controller = RedArmyController(_config(args))
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, controller.stop)
        except NotImplementedError:
            pass

    if args.command == "status":
        status = await controller.status()
        print(_status_json(status))
        return 0

    credentials = await controller.create() if args.command == "create" else None
    if credentials is not None:
        # game_id is a room code meant to be shared. Never print player_id or resume_token.
        print(json.dumps({"game_id": credentials.game_id, "status": "waiting_for_players"}, ensure_ascii=False), flush=True)
    try:
        await controller.run(credentials)
    except ControllerStopped as exc:
        logging.getLogger("redline-red-army").error("%s", exc)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        return asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
