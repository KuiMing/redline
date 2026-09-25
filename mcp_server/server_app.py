"""Builds the REDLINE MCPServer instance: registers every tool and resource
against a shared AppContext (one RedlineClient + RulesCatalog per process).
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_server.config import RedlineMCPConfig
from mcp_server.context import AppContext
from mcp_server.redline_client import RedlineClient
from mcp_server.rules_data import read_rules_markdown, RulesCatalog
from mcp_server.tools import gameplay, lobby, rules

SERVER_INSTRUCTIONS = (
    "REDLINE is a hidden-role, asymmetric board game (one Red Army player vs. several "
    "resistance factions). This MCP server drives a running REDLINE HTTP+WebSocket "
    "server on behalf of ONE seat at a time — pass the game_id and player_id you got "
    "back from create_room/join_room on every gameplay call. Typical flow: "
    "create_room or join_room -> choose_faction -> set_ready -> (host) start_game -> "
    "loop: get_state or get_legal_actions -> one action tool -> repeat until game_over. "
    "Every action tool's result already includes a fresh `legal_actions` block (same "
    "shape get_legal_actions returns) reflecting the state right after that action — "
    "act on it directly for your next move; only call get_legal_actions again if you "
    "want to re-derive it for some other reason. "
    "When a pending_choice is present, resolve it with resolve_pending_choice(index=...), or "
    "indices=[...] for a multi-pick choice, "
    "before anything else will be accepted. get_state never reveals other players' "
    "hidden hands or private choices — that redaction happens server-side."
)


def build_server(config: RedlineMCPConfig | None = None) -> tuple[MCPServer, AppContext]:
    config = config or RedlineMCPConfig.from_env()
    client = RedlineClient(
        base_url=config.base_url,
        ws_base_url=config.ws_base_url,
        http_timeout=config.http_timeout_seconds,
        ws_connect_timeout=config.ws_connect_timeout_seconds,
        action_wait_timeout=config.action_wait_timeout_seconds,
    )
    ctx = AppContext(client=client, rules=RulesCatalog(client))
    app = MCPServer(name="redline", instructions=SERVER_INSTRUCTIONS)
    register_tools(app, ctx)
    register_resources(app, ctx)
    register_health_route(app)
    return app, ctx


def register_health_route(app: MCPServer) -> None:
    """`/health` reports only whether this MCP process itself is up and
    serving — NOT whether the REDLINE game server it proxies to is reachable
    or has any rooms. A Docker healthcheck must never treat "REDLINE has no
    rooms yet" or "REDLINE isn't ready yet" as this process being unhealthy;
    each gameplay tool call already reports a connection failure to the
    REDLINE server as its own actionable MCP tool error (see
    mcp_server/tools/errors.py) — that is the correct place for that signal,
    not this endpoint. Only meaningful under `--transport streamable-http`;
    harmless to register unconditionally (unused under stdio)."""

    @app.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "server": "redline-mcp"})


def register_tools(app: MCPServer, ctx: AppContext) -> None:
    # ---- lobby ----
    @app.tool()
    async def create_room(player_name: str) -> dict[str, Any]:
        """Create a new REDLINE room. Caller becomes the host seat."""
        return await lobby.create_room(ctx, player_name)

    @app.tool()
    async def join_room(
        game_id: str,
        player_name: str,
        player_id: str | None = None,
        resume_token: str | None = None,
        device_id: str | None = None,
    ) -> dict[str, Any]:
        """Join an existing room by game_id. Pass player_id+resume_token to resume a seat you already held."""
        return await lobby.join_room(
            ctx, game_id, player_name, player_id=player_id, resume_token=resume_token, device_id=device_id
        )

    @app.tool()
    async def resume_room(game_id: str, player_id: str, resume_token: str) -> dict[str, Any]:
        """Reconnect a specific seat after a dropped session, using the resume_token from create_room/join_room."""
        return await lobby.resume_room(ctx, game_id, player_id, resume_token)

    @app.tool()
    async def get_room_status(game_id: str) -> dict[str, Any]:
        """Lobby snapshot for a known game_id: seats, factions/bases chosen, ready flags, started."""
        return await lobby.get_room_status(ctx, game_id)

    @app.tool()
    async def list_known_rooms() -> dict[str, Any]:
        """Rooms this MCP process has touched this run (session-local; REDLINE has no global room directory)."""
        return await lobby.list_known_rooms(ctx)

    @app.tool()
    async def choose_faction(game_id: str, player_id: str, faction_id: str, base_name: str | None = None) -> dict[str, Any]:
        """Pick a faction (and base, if it has options) for a seat in the lobby."""
        return await lobby.choose_faction(ctx, game_id, player_id, faction_id, base_name=base_name)

    @app.tool()
    async def set_ready(game_id: str, player_id: str, ready: bool = True) -> dict[str, Any]:
        """Mark a seat ready (or not) to start."""
        return await lobby.set_ready(ctx, game_id, player_id, ready=ready)

    @app.tool()
    async def set_market_mode(game_id: str, player_id: str, market_mode: str) -> dict[str, Any]:
        """Host-only: set 'sample_53' or 'all_cards' before starting."""
        return await lobby.set_market_mode(ctx, game_id, player_id, market_mode)

    @app.tool()
    async def start_game(game_id: str, player_id: str, market_mode: str | None = None) -> dict[str, Any]:
        """Host-only: start the game once every seat has chosen a faction and is ready."""
        return await lobby.start_game(ctx, game_id, player_id, market_mode=market_mode)

    @app.tool()
    async def list_factions() -> dict[str, Any]:
        """Compact list of every selectable faction_id/name/category. Use get_faction_detail for abilities."""
        return await lobby.list_factions(ctx)

    # ---- gameplay ----
    @app.tool()
    async def get_state(game_id: str, player_id: str, resume_token: str | None = None) -> dict[str, Any]:
        """This seat's current view: phase, turn, pending choice, resources, purchase area — never other players' hands."""
        return await gameplay.get_state(ctx, game_id, player_id, resume_token=resume_token)

    @app.tool()
    async def get_state_detail(game_id: str, player_id: str, section: str) -> dict[str, Any]:
        """Deep-dive into one raw state section (map, purchase_area, players, action_log, pending_choice, active_eras, active_era_details, era_notification, current_event, static_purchase_supply)."""
        return await gameplay.get_state_detail(ctx, game_id, player_id, section)

    @app.tool()
    async def get_legal_actions(game_id: str, player_id: str) -> dict[str, Any]:
        """Server-grounded list of everything this seat can legally attempt right now, with ready-to-use parameters."""
        return await gameplay.get_legal_actions(ctx, game_id, player_id)

    @app.tool()
    async def play_card(game_id: str, player_id: str, index: int, mode: str, target_player_id: str | None = None) -> dict[str, Any]:
        """Play hand card at `index`. mode='resource' always works; mode='action' triggers its printed effect (some cards need target_player_id)."""
        return await gameplay.play_card(ctx, game_id, player_id, index, mode, target_player_id=target_player_id)

    @app.tool()
    async def build_organization(game_id: str, player_id: str, town: str) -> dict[str, Any]:
        """Resolve a pending build-organization choice onto `town` (see get_legal_actions for legal towns)."""
        return await gameplay.build_organization(ctx, game_id, player_id, town)

    @app.tool()
    async def move_organization(game_id: str, player_id: str, from_town: str, to_town: str, mode: str = "road") -> dict[str, Any]:
        """Move one organization. mode='road' (1 step) or 'rail' (3 steps); see get_legal_actions for legal from/to pairs."""
        return await gameplay.move_organization(ctx, game_id, player_id, from_town, to_town, mode=mode)

    @app.tool()
    async def buy_card(game_id: str, player_id: str, index: int) -> dict[str, Any]:
        """Buy one card from the purchase area at `index`."""
        return await gameplay.buy_card(ctx, game_id, player_id, index)

    @app.tool()
    async def buy_cards(game_id: str, player_id: str, indices: list[int]) -> dict[str, Any]:
        """Buy several purchase-area cards in one call."""
        return await gameplay.buy_cards(ctx, game_id, player_id, indices)

    @app.tool()
    async def dissolve_organization(game_id: str, player_id: str, defender_player_id: str, town: str) -> dict[str, Any]:
        """Direct dissolve of an organization at `town` owned (or shared) by defender_player_id. Rarely needed — most dissolves are a pending_choice; check get_legal_actions first."""
        return await gameplay.dissolve_organization(ctx, game_id, player_id, defender_player_id, town)

    @app.tool()
    async def use_faction_action(
        game_id: str, player_id: str, name: str, guess: str | None = None, target_player_id: str | None = None
    ) -> dict[str, Any]:
        """Trigger a faction's activated ability by its exact name (see get_legal_actions/get_faction_detail). guess is 'odd' or 'even' for 賭徒耳語/民族祭儀."""
        return await gameplay.use_faction_action(ctx, game_id, player_id, name, guess=guess, target_player_id=target_player_id)

    @app.tool()
    async def advance_turn(game_id: str, player_id: str) -> dict[str, Any]:
        """Advance the turn/event phase, or end the action phase and pass the turn — REDLINE's single 'next' button."""
        return await gameplay.advance_turn(ctx, game_id, player_id)

    @app.tool()
    async def use_topdeck_right(game_id: str, player_id: str) -> dict[str, Any]:
        """Use an available top-deck (peek/take) right, if get_state/get_legal_actions shows one is pending."""
        return await gameplay.use_topdeck_right(ctx, game_id, player_id)

    @app.tool()
    async def resolve_pending_choice(
        game_id: str, player_id: str, index: int | None = None, indices: list[int] | None = None
    ) -> dict[str, Any]:
        """Answer the current pending_choice by picking from its options/towns/targets/cards list. Pass `index` for a single pick; pass `indices` (a list) when get_legal_actions shows choice_type 'multi_card_choice' (count/min_count > 1)."""
        return await gameplay.resolve_pending_choice(ctx, game_id, player_id, index=index, indices=indices)

    @app.tool()
    async def cancel_pending_choice(game_id: str, player_id: str) -> dict[str, Any]:
        """Cancel the current pending_choice, if get_state/get_legal_actions marks it cancellable."""
        return await gameplay.cancel_pending_choice(ctx, game_id, player_id)

    @app.tool()
    async def set_base(game_id: str, player_id: str, town: str, label: str | None = None) -> dict[str, Any]:
        """During base_selection phase, pick this seat's starting base town."""
        return await gameplay.set_base(ctx, game_id, player_id, town, label=label)

    @app.tool()
    async def relocate_hong_kong_base(game_id: str, player_id: str, town: str) -> dict[str, Any]:
        """Hong Kong only: use the free base-relocation window opened by 香港抗暴之戰."""
        return await gameplay.relocate_hong_kong_base(ctx, game_id, player_id, town)

    @app.tool()
    async def keep_hong_kong_base(game_id: str, player_id: str) -> dict[str, Any]:
        """Hong Kong only: decline the free relocation window and stay at the current base."""
        return await gameplay.keep_hong_kong_base(ctx, game_id, player_id)

    @app.tool()
    async def disconnect_session(game_id: str, player_id: str) -> dict[str, Any]:
        """Close this seat's live connection. The next call for the same game_id/player_id reconnects automatically."""
        return await gameplay.disconnect_session(ctx, game_id, player_id)

    # ---- rules/reference ----
    @app.tool()
    async def get_rules_text() -> dict[str, Any]:
        """Full REDLINE rulebook (rules.md) as Traditional Chinese markdown."""
        return await rules.get_rules_text(ctx)

    @app.tool()
    async def list_cards() -> dict[str, Any]:
        """Compact index of every card name + kind. Use get_card_detail for full effect text."""
        return await rules.list_cards(ctx)

    @app.tool()
    async def get_card_detail(name: str) -> dict[str, Any]:
        """Full printed text for one card by its exact name."""
        return await rules.get_card_detail(ctx, name)

    @app.tool()
    async def get_faction_detail(faction_id: str, base_name: str | None = None) -> dict[str, Any]:
        """Full ability/rule/win-condition text for one faction (and base variant, if relevant)."""
        return await rules.get_faction_detail(ctx, faction_id, base_name=base_name)


def register_resources(app: MCPServer, ctx: AppContext) -> None:
    @app.resource("redline://rules", name="REDLINE rulebook", mime_type="text/markdown")
    def rules_resource() -> str:
        return read_rules_markdown()
