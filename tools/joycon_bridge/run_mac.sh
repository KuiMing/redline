#!/usr/bin/env bash
# 在 Mac 上啟動 REDLINE Joy-Con bridge。請先保持「Finally the Controller Works」開啟。
# 用法：tools/joycon_bridge/run_mac.sh [--port 8000] [--allow-origin http://<LAN-IP>:8100] [--dump-packets]
set -euo pipefail
cd "$(dirname "$0")/../.."
exec uv run python -m tools.joycon_bridge "$@"
