# REDLINE MCP Server

An in-repo [MCP](https://modelcontextprotocol.io) server (stdio by default,
Streamable HTTP optional — see [§2](#2-run-the-mcp-server)) that lets an
MCP-compatible LLM client play REDLINE end-to-end: create or join a room,
pick a faction, start the game, read its own privacy-scoped view of the
board, discover what it can legally do right now, and act.

It is a **client** of the real REDLINE HTTP + WebSocket server
(`server/main.py`) — the same endpoints a browser uses. It never imports
`server.game` (or any other `server/*.py` module) and never calls a
`/test/*` route. Every tool call ultimately becomes one HTTP request or one
WebSocket message against a running REDLINE server process.

```
LLM client <--MCP (stdio or Streamable HTTP)--> mcp_server (this package) <--HTTP+WS--> server.main:app
```

Can also be run as a two-container [Docker Compose](#4-docker--docker-compose)
stack alongside the game server.

For copy-paste Claude Code and OpenAI Codex setup, the standard gameplay
loop, and the controller adapter contract, see
[`agent_mcp_controller_integration.md`](agent_mcp_controller_integration.md).

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

Two transports are supported. **stdio is the default** and what most desktop
MCP clients expect; **Streamable HTTP** is opt-in, for running the server as
a long-lived process other machines/processes can reach over HTTP (this is
what the Docker Compose stack in [§4](#4-docker--docker-compose) uses).

### stdio (default)

```bash
uv run python -m mcp_server
```

Reads/writes JSON-RPC on stdin/stdout and exits when stdin closes. Meant to
be launched by an MCP client, not run interactively.

### Streamable HTTP

```bash
uv run python -m mcp_server --transport streamable-http
# or: --host/--port/--path flags, or the REDLINE_MCP_HTTP_* env vars below
```

Starts a long-lived HTTP server (`http://127.0.0.1:8080/mcp` by default) an
MCP client connects to by URL instead of spawning a subprocess. See
[§5 Security](#5-security-streamable-http-transport) before binding
anywhere other than `127.0.0.1`/`localhost`.

### Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `REDLINE_BASE_URL` | `http://127.0.0.1:8000` | Base URL of the REDLINE HTTP server. |
| `REDLINE_WS_BASE_URL` | derived from `REDLINE_BASE_URL` (`http→ws`, `https→wss`) | Override if the WS endpoint lives behind a different host/path than the HTTP one. |
| `REDLINE_MCP_HTTP_TIMEOUT` | `10` | Seconds before an HTTP lobby call (create/join/ready/start/...) times out. |
| `REDLINE_MCP_WS_CONNECT_TIMEOUT` | `10` | Seconds to wait for a WebSocket connection (and its first pushed state) before giving up. |
| `REDLINE_MCP_ACTION_TIMEOUT` | `8` | Seconds to wait for the state update that follows a sent action before treating it as lost. |
| `REDLINE_MCP_TRANSPORT` | `stdio` | Default for `--transport` when the flag is omitted (`stdio` or `streamable-http`). |
| `REDLINE_MCP_HTTP_HOST` | `127.0.0.1` | Bind host for `--transport streamable-http`. A container sets this to `0.0.0.0`; see [§5](#5-security-streamable-http-transport) for why that does **not** by itself expose anything beyond what `REDLINE_MCP_ALLOWED_HOSTS`/`_ORIGINS` permit. |
| `REDLINE_MCP_HTTP_PORT` | `8080` | Bind port for `--transport streamable-http`. |
| `REDLINE_MCP_HTTP_PATH` | `/mcp` | HTTP path for the MCP endpoint. |
| `REDLINE_MCP_ALLOWED_HOSTS` | `127.0.0.1:*,localhost:*,[::1]:*` | Comma-separated `Host` header patterns accepted (DNS-rebinding protection). Add your own only if a reverse proxy in front of this presents a different Host. |
| `REDLINE_MCP_ALLOWED_ORIGINS` | `http://127.0.0.1:*,http://localhost:*,http://[::1]:*` | Comma-separated `Origin` header patterns accepted. |
| `REDLINE_MCP_ENABLE_DNS_REBINDING_PROTECTION` | `true` | Set `false` only if you fully understand the risk (see [§5](#5-security-streamable-http-transport)) — never disable this on anything reachable beyond your own machine. |

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

### Example Streamable HTTP client configuration

Once a Streamable HTTP server is running (directly, or via
[Docker Compose](#4-docker--docker-compose)), an MCP client connects to it by
URL instead of spawning a subprocess. The exact key names vary by client —
check yours — but most look like this:

```json
{
  "mcpServers": {
    "redline": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

Replace `localhost:8080` with wherever the server is actually reachable —
`localhost:8765` for the default Docker Compose port mapping (see
[§4](#4-docker--docker-compose)), or your real host/port. This endpoint is
**unauthenticated**; see [§5 Security](#5-security-streamable-http-transport)
before pointing a client at anything beyond your own machine.

## 3. Connecting to an already-running REDLINE server

Nothing special is needed: point `REDLINE_BASE_URL` at it. This works
whether that server is on the same machine, on your LAN (the address the
lobby UI itself shows other players — see `/server-info`), or reachable over
the network some other way. The MCP server itself holds no game state of its
own; it only proxies to whatever `REDLINE_BASE_URL` points at.

## 4. Docker / Docker Compose

`docker-compose.yml` builds and runs the REDLINE game server and its MCP
server together, as two separate images:

```bash
docker compose up --build
```

- **`redline`** — the existing game server, built from the repo's root
  `Dockerfile` (unmodified — this Compose file adds a service around it, it
  does not change how that image is built). Host port defaults to `8000`,
  same as the single-container instructions above; override with
  `REDLINE_HOST_PORT`.
- **`redline-mcp`** — the MCP server, built from `mcp_server/Dockerfile` (a
  separate, minimal image — it copies only `mcp_server/`, `rules.md`, and
  the shared `pyproject.toml`/`uv.lock`; it never copies `server/`, `data/`,
  or `static/`). Talks to `redline` over the Compose-internal network by
  service name — `REDLINE_BASE_URL=http://redline:8000`, **not**
  `host.docker.internal` and not the published host port. Runs
  `--transport streamable-http` bound to `0.0.0.0` *inside* the container
  (required for Docker's port mapping to reach it at all), but its **host**
  port mapping is `127.0.0.1:8765:8080` by default — bound to localhost
  only, so `docker compose up` with no overrides never exposes the
  unauthenticated MCP endpoint to your LAN. Override the host port with
  `REDLINE_MCP_HOST_PORT`; see [§5](#5-security-streamable-http-transport)
  before changing the bind address itself.

Once up, point an MCP client at `http://127.0.0.1:8765/mcp` (see the
Streamable HTTP client config example above).

**Startup ordering:** `redline-mcp` depends on `redline` only for container
*start order* (`condition: service_started`), not on `redline`'s
healthcheck passing — the MCP process must be able to come up before the
game server is ready; its own `/health` reflects only "is the MCP process
itself serving," never "does REDLINE have any rooms yet" or any other game
state. A gameplay tool call made before `redline` is reachable comes back as
a clear MCP transport error (see "Error handling" below), not a healthcheck
failure.

**Build vs. test stack vs. deploy.** `docker compose build` (or `up
--build`) succeeding, and even a full `docker compose up` coming up healthy,
proves the images are correct and the two services can talk to each other —
it does **not** mean anything has been deployed anywhere. Bringing up this
stack for real use (beyond your own machine, or long-running) is a decision
you make deliberately, e.g. by running `docker compose up -d` on a server
you control, with your own reverse proxy/TLS/auth in front per §5.

## 5. Security (Streamable HTTP transport)

The Streamable HTTP endpoint has **no built-in authentication or
authorization**. Anyone who can send it an HTTP request with an accepted
`Host`/`Origin` can call every tool — which, per the [Privacy](#privacy)
section above, is scoped to whatever `player_id` the caller supplies, but
nothing stops a caller from supplying any `player_id` it can guess or
observe (this mirrors REDLINE's own existing trust model — a `resume_token`
protects *reconnecting* to a seat, not the initial WS connection; see
`server/main.py`). Treat this endpoint the same way you'd treat an
unauthenticated internal API.

**Defaults, and what they actually protect:**

- **DNS-rebinding protection is always on** (`enable_dns_rebinding_protection`,
  default `true`) and is built **explicitly** in
  `mcp_server/__main__.py`/`config.py` — the `mcp` SDK itself only
  auto-enables this when the bind host is literally
  `127.0.0.1`/`localhost`/`::1`; a container binds `0.0.0.0` (required for
  Docker's port mapping to work), which would silently leave protection
  *off* if left to the SDK's default. `REDLINE_MCP_ALLOWED_HOSTS`/
  `_ALLOWED_ORIGINS` default to localhost-only patterns regardless of bind
  host, so the real boundary is "what Host/Origin header did the request
  carry," not "what interface did the socket bind." A request with an
  unrecognized `Host` gets `421`; an unrecognized `Origin` gets `403`
  (verified for real, over a real socket, by
  `scripts/validate/mcp_streamable_http_smoke.py`).
- **Docker Compose binds the host port to `127.0.0.1` only** by default
  (§4) — defense in depth on top of the header checks: even a request that
  somehow carried an accepted `Host`/`Origin` still can't reach the port
  from another machine unless you deliberately change the port mapping.
- **No CORS headers are added.** This is not designed to be called directly
  from browser-based JavaScript on another origin; the Origin check above
  exists for DNS-rebinding protection, not to grant cross-origin access.
- **Sessions**: stateful by default (`mcp` SDK defaults — a 30-minute idle
  timeout, up to 10000 concurrent sessions), matching a normal MCP client
  that holds one long-lived connection. Not tuned further here since nothing
  in this task required it; the SDK's `run_streamable_http_async` accepts
  `session_idle_timeout`/`max_sessions` if you need to change them (not
  currently exposed as env vars — edit `mcp_server/__main__.py` if needed).

**If you need to expose this beyond `127.0.0.1` on one machine** (a real LAN
or Internet deployment): put a reverse proxy in front that terminates TLS
and adds real authentication (a bearer token, mTLS, your proxy's own auth —
anything), and only then widen `REDLINE_MCP_ALLOWED_HOSTS`/`_ORIGINS` (and
the Compose port binding) to match. **Do not** just change
`REDLINE_MCP_HTTP_HOST`/the port mapping to `0.0.0.0`/a public port and call
it done — an unauthenticated MCP server reachable from the Internet lets
anyone who finds it play (or grief) any game whose `game_id` they can guess
or observe, with no rate limiting.

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

**`/health`** (Streamable HTTP transport only) is a plain HTTP `GET`
endpoint, not an MCP tool or resource — it exists purely for a Docker
healthcheck (or any other liveness probe) and is unauthenticated by design;
see §5.

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
- No authentication on the Streamable HTTP transport — see §5. Not suitable
  to expose beyond `127.0.0.1` without a reverse proxy adding real auth.
- `session_idle_timeout`/`max_sessions` for Streamable HTTP use the `mcp`
  SDK's own defaults and aren't currently exposed as env vars (unlike the
  bind host/port/path and the DNS-rebinding settings, which are).
- Docker: the root `Dockerfile`'s `uv sync --frozen --no-dev` now also
  installs the `mcp` package into the **game** image (since `mcp` is a
  top-level `[project.dependencies]` entry, added for the MCP server) —
  harmless (`server/*.py` never imports it, confirmed by
  `scripts/tests/test_mcp_docker_compose_config.py`), just a few extra MB
  the game image doesn't use.
