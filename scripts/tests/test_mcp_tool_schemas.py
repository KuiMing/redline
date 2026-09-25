"""Tool/resource registration sanity: every tool has a real name, a
non-empty description the model can read, and the input schema actually
requires the parameters an LLM must supply (so a client can't silently
omit e.g. `mode` on play_card).
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from mcp_server.server_app import build_server

EXPECTED_TOOL_NAMES = {
    "create_room",
    "join_room",
    "resume_room",
    "get_room_status",
    "list_known_rooms",
    "choose_faction",
    "set_ready",
    "set_market_mode",
    "start_game",
    "list_factions",
    "get_state",
    "get_state_detail",
    "get_legal_actions",
    "play_card",
    "build_organization",
    "move_organization",
    "buy_card",
    "buy_cards",
    "dissolve_organization",
    "use_faction_action",
    "advance_turn",
    "use_topdeck_right",
    "resolve_pending_choice",
    "cancel_pending_choice",
    "set_base",
    "relocate_hong_kong_base",
    "keep_hong_kong_base",
    "disconnect_session",
    "get_rules_text",
    "list_cards",
    "get_card_detail",
    "get_faction_detail",
}

REQUIRED_PARAMS = {
    "create_room": {"player_name"},
    "join_room": {"game_id", "player_name"},
    "choose_faction": {"game_id", "player_id", "faction_id"},
    "play_card": {"game_id", "player_id", "index", "mode"},
    "move_organization": {"game_id", "player_id", "from_town", "to_town"},
    # resolve_pending_choice: index and indices are each optional at the
    # schema level (exactly one is required, enforced at call time — see
    # test_mcp_privacy_and_legal_actions.py's multi_card_choice coverage and
    # gameplay.resolve_pending_choice's own validation).
    "buy_cards": {"game_id", "player_id", "indices"},
}


@pytest.fixture(scope="module")
def server_and_ctx():
    import os

    os.environ.setdefault("REDLINE_BASE_URL", "http://127.0.0.1:1")  # never dialed in this file
    return build_server()


def _tools_by_name(app):
    manager = app._tool_manager
    return {name: tool for name, tool in manager._tools.items()}


def test_every_expected_tool_is_registered(server_and_ctx):
    app, _ctx = server_and_ctx
    tools = _tools_by_name(app)
    assert set(tools) == EXPECTED_TOOL_NAMES


def test_every_tool_has_a_useful_description(server_and_ctx):
    app, _ctx = server_and_ctx
    for name, tool in _tools_by_name(app).items():
        assert tool.description and len(tool.description) > 10, f"{name} needs a real description"


def test_required_params_are_enforced_in_schema(server_and_ctx):
    app, _ctx = server_and_ctx
    tools = _tools_by_name(app)
    for name, required in REQUIRED_PARAMS.items():
        schema = tools[name].parameters
        assert required.issubset(set(schema.get("required", []))), (
            f"{name} schema should require {required}, got {schema.get('required')}"
        )


def test_rules_resource_is_registered(server_and_ctx):
    app, _ctx = server_and_ctx
    resources = app._resource_manager._resources
    assert "redline://rules" in resources


def test_play_card_mode_param_is_string_enum_shaped(server_and_ctx):
    app, _ctx = server_and_ctx
    schema = _tools_by_name(app)["play_card"].parameters
    mode_schema = schema["properties"]["mode"]
    assert mode_schema.get("type") == "string"
