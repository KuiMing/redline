# REDLINE MCP Server

An in-repo [MCP](https://modelcontextprotocol.io) server (stdio transport)
that lets an MCP-compatible LLM client play REDLINE end-to-end: create or
join a room, pick a faction, start the game, read its own privacy-scoped
view of the board, discover what it can legally do right now, and act.

It is a **client** of the real REDLINE HTTP + WebSocket server
(`server/main.py`) — the same endpoints a browser uses. It never imports
`server.game` (or any other `server/*.py` module) and never calls a
`/test/*` route. Every tool call ultimately becomes one HTTP request or one
WebSocket message against a running REDLINE server process.

```
LLM client (stdio) <--MCP--> mcp_server (this package) <--HTTP+WS--> server.main:app
```

## Install

Dependencies are managed the same way as the rest of the repo:

```bash
uv sync
```

This pulls in the `mcp` package (the official Python MCP SDK) alongside the
existing FastAPI/uvicorn/websockets dependencies.

## 1. Start a REDLINE server

The MCP server needs a REDLINE HTTP+WebSocket server to talk to. Start one
the normal way (see the root [README.md](../README.md)):

```bash
uv run uvicorn server.main:app --host 0.0.0.0 --port 8000
```

`/test/*` routes do **not** need to be enabled — the MCP server never uses
them, so leave `ENABLE_TEST_ROUTES` unset (the default) even in development.

## 2. Run the MCP server

```bash
uv run python -m mcp_server
```

This starts a stdio MCP server (reads/writes JSON-RPC on stdin/stdout) and
exits when stdin closes. It's meant to be launched by an MCP client, not run
interactively.

### Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `REDLINE_BASE_URL` | `http://127.0.0.1:8000` | Base URL of the REDLINE HTTP server. |
| `REDLINE_WS_BASE_URL` | derived from `REDLINE_BASE_URL` (`http→ws`, `https→wss`) | Override if the WS endpoint lives behind a different host/path than the HTTP one. |
| `REDLINE_MCP_HTTP_TIMEOUT` | `10` | Seconds before an HTTP lobby call (create/join/ready/start/...) times out. |
| `REDLINE_MCP_WS_CONNECT_TIMEOUT` | `10` | Seconds to wait for a WebSocket connection (and its first pushed state) before giving up. |
| `REDLINE_MCP_ACTION_TIMEOUT` | `8` | Seconds to wait for the state update that follows a sent action before treating it as lost. |

### Example stdio client configuration

Most MCP clients (Claude Code, Claude Desktop, etc.) take a JSON block like
this. Replace `$HOME` with wherever you actually cloned the repo, and point
`REDLINE_BASE_URL` at whichever REDLINE server you started in step 1
(`localhost` here is a placeholder — use your real host/port):

```json
{
  "mcpServers": {
    "redline": {
      "command": "uv",
      "args": ["run", "--directory", "$HOME/redline", "python", "-m", "mcp_server"],
      "env": {
        "REDLINE_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Connecting to an already-running REDLINE server

Nothing special is needed: point `REDLINE_BASE_URL` at it. This works
whether that server is on the same machine, on your LAN (the address the
lobby UI itself shows other players — see `/server-info`), or reachable over
the network some other way. The MCP server itself holds no game state of its
own; it only proxies to whatever `REDLINE_BASE_URL` points at.

## Example: room creation through the first turn

A typical tool-call sequence (arguments/results abbreviated):

```
create_room(player_name="Alice")
  -> {game_id, player_id: host_id, resume_token, role: "host"}

join_room(game_id, player_name="Bob")
  -> {player_id: guest_id, resume_token, role: "guest"}

list_factions()
  -> [{faction_id: "red_army", ...}, {faction_id: "taiwan_green", ...}, ...]

choose_faction(game_id, host_id, faction_id="red_army")
choose_faction(game_id, guest_id, faction_id="taiwan_green", base_name="臺北")

set_ready(game_id, host_id, ready=true)
set_ready(game_id, guest_id, ready=true)

start_game(game_id, host_id)
  -> {ok: true, next_step: "Call get_state for each seated player_id..."}

get_state(game_id, guest_id)
  -> {ok: true, state: {turn: 1, game_phase: "main", turn_phase: "action",
       current_player_name: "Bob", is_my_turn: true, my_hand_size: 5,
       pending_choice: null, ...},
      legal_action_kinds: {kind_counts: {play_card: 5, buy_card: 6, advance_turn: 1}}}

get_legal_actions(game_id, guest_id)
  -> {actions: [{kind: "play_card", index: 0, card_name: "追隨者",
       modes: ["resource", "action"]}, ...,
       {kind: "advance_turn", why: "..."}]}

play_card(game_id, guest_id, index=0, mode="resource")
  -> {ok: true, state: {...}, legal_action_kinds: {...}}

advance_turn(game_id, guest_id)
  -> {ok: true, state: {current_player_name: "Alice", turn_phase: "action", ...}}
```

If an action is rejected (wrong turn, illegal target, insufficient
resources, ...) the tool still returns `{"ok": false, "error": "<reason>",
"state": {...}, "legal_action_kinds": {...}}` — never a bare protocol
error — so the caller always has enough context to pick a different action.
Only transport-level failures (server unreachable, connection dropped,
action timed out) surface as an MCP tool error; see "Error handling" below.

If a `pending_choice` shows up (an event, reaction window, or card effect
that needs a decision before anything else is accepted), resolve it with
`resolve_pending_choice(game_id, player_id, index=...)` — or `indices=[...]`
for the rarer multi-pick case (`get_legal_actions` marks these with
`"use_indices_param": true` plus `count`/`min_count`).

## Tools

**Lobby**: `create_room`, `join_room`, `resume_room`, `get_room_status`,
`list_known_rooms`, `choose_faction`, `set_ready`, `set_market_mode`,
`start_game`, `list_factions`.

**Gameplay**: `get_state`, `get_state_detail`, `get_legal_actions`,
`play_card`, `build_organization`, `move_organization`, `buy_card`,
`buy_cards`, `dissolve_organization`, `use_faction_action`, `advance_turn`,
`use_topdeck_right`, `resolve_pending_choice`, `cancel_pending_choice`,
`set_base`, `relocate_hong_kong_base`, `keep_hong_kong_base`,
`disconnect_session`.

**Rules/reference**: `get_rules_text`, `list_cards`, `get_card_detail`,
`get_faction_detail`.

**Resources**: `redline://rules` (the full rulebook as markdown — the same
content `get_rules_text` returns).

Every tool has its own docstring/description visible to the client; this is
the map, not the full spec.

## Design notes

### Why no new server/*.py endpoints

Everything required is already reachable through the existing public HTTP
routes (`server/lobby_routes.py`) and the single WebSocket endpoint
(`server/main.py`'s `/ws/{game_id}/{player_id}`). In particular:

- **Reading state** doesn't need a new HTTP "get current state" endpoint:
  the WebSocket already pushes a fresh, viewer-scoped `Game.state(player_id)`
  on connect and after every action. The MCP server keeps one live
  connection per `(game_id, player_id)` it has touched and caches the latest
  pushed state; `get_state` returns that cache (connecting lazily first, if
  needed).
- **"Legal actions right now"** doesn't need a new endpoint either: it's
  synthesized entirely from fields `state()` already returns —
  `hand_action_legality`, `map.legal_organization_moves`,
  `purchase_area_affordable`, `pending_choice`, `pending_base_choices`,
  `faction_action_used`, `red_army_action_count`/`_limit` — plus the public
  `/factions` catalog to know which activated-ability names a player's
  faction actually has. See `mcp_server/summarize.py`.
- **"List joinable rooms"** has no server-side equivalent — REDLINE has no
  global room directory; a `game_id` is shared out of band, like a room
  code, on purpose. `list_known_rooms` is deliberately session-local
  bookkeeping (rooms this MCP process has touched), not a claim of global
  discovery. Adding a real "list every room on the server" endpoint would be
  a meaningful new information-disclosure surface for something the product
  never exposes, so it was left out.

### Privacy

`get_state`/`get_legal_actions`/`get_state_detail` only ever forward what
`Game.state(player_id)` already scoped for that `player_id` — hidden hands
come back as `"未知手牌"` placeholders for every seat but your own, exactly
as the browser client sees it. On top of that, this layer adds its own
extra floor: `summarize_state()` never includes any player's raw hand array
at all (only a count), and a `pending_choice` belonging to a different
player is collapsed to `{waiting_on, reason}` with its `options`/`cards`
list stripped — even in the hypothetical case where the underlying
`pending_choice` projection contained another player's private option
contents (e.g., a "pick a hand card to bottom-deck" choice), this layer
would still not surface it to a non-owning viewer. See
`scripts/tests/test_mcp_privacy_and_legal_actions.py`.

### Error handling

- A rejected game/lobby action (illegal move, wrong turn, room full, ...)
  comes back as a normal tool result `{"ok": false, "error": "...", ...}` —
  not an MCP-protocol error — so the model keeps full state/legal-action
  context and can just try something else.
- A transport failure (server unreachable, WebSocket auth rejected, action
  timed out waiting for a response) raises an MCP tool error. There's no
  useful game state to attach, and the right response (reconnect/retry) is
  genuinely different from "pick another legal action".
- Every WebSocket session reconnects lazily and automatically on the next
  tool call after a drop; `resume_token`s returned by `create_room`/
  `join_room`/`resume_room` are remembered internally so callers don't have
  to pass them on every subsequent call.

## Known limitations

- `dissolve_organization` maps to a lower-level WS action used by a minority
  of dissolve interactions; most dissolve flows arrive as a `pending_choice`
  instead — check `get_legal_actions` first.
- `get_legal_actions`' faction-action entries are best-effort candidates
  (gated by turn/usage-count only); the server remains authoritative and can
  still reject a specific attempt (e.g. no valid target in range this turn).
- A single MCP server process talks for one seat at a time per tool call,
  but can hold sessions open for multiple `(game_id, player_id)` pairs
  simultaneously (e.g. to inspect two seats you control). It cannot act as
  two different LLM "players" concurrently reasoning about the same seat.
