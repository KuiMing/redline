#!/usr/bin/env python3
"""Validate that every player-facing error/prompt crosses the zh-TW boundary."""
from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "static" / "app.js"
INDEX = REPO / "static" / "index.html"
MESSAGES = REPO / "static" / "player_messages_zh_tw.js"
MAP_HTML = REPO / "static" / "leaflet_game_map.html"
MAP_LOGIC = REPO / "static" / "leaflet_game_map_logic.js"
SERVER = REPO / "server"


def backend_error_literals() -> list[str]:
    values: set[str] = set()
    for path in SERVER.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "error"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    values.add(value.value)
    return sorted(values)


def translate_with_node(values: list[str]) -> list[str]:
    node_source = r"""
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(input.map(value => window.playerMessageZhTw(value))));
"""
    result = subprocess.run(
        ["node", "-e", node_source, str(MESSAGES)],
        input=json.dumps(values, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    app = APP.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    map_html = MAP_HTML.read_text(encoding="utf-8")
    map_logic = MAP_LOGIC.read_text(encoding="utf-8")

    checks.append(("translation_file_exists", MESSAGES.exists(), str(MESSAGES)))
    localization_pos = index.find("/static/player_messages_zh_tw.js")
    app_pos = index.find("/static/app.js")
    checks.append((
        "translation_loads_before_app",
        0 <= localization_pos < app_pos,
        f"translation_pos={localization_pos}, app_pos={app_pos}",
    ))
    map_localization_pos = map_html.find("/static/player_messages_zh_tw.js")
    map_logic_pos = map_html.find("/static/leaflet_game_map_logic.js")
    checks.append((
        "translation_loads_before_map_logic",
        0 <= map_localization_pos < map_logic_pos,
        f"translation_pos={map_localization_pos}, map_logic_pos={map_logic_pos}",
    ))

    forbidden = [
        "alert(data.error)",
        "alert(state.error)",
        ": data.error);",
        "updateLobbyStatus(lobbyRes.error)",
    ]
    for snippet in forbidden:
        checks.append((f"no_raw_{snippet}", snippet not in app, snippet))
    checks.append(("map_state_error_is_translated", "error: state.error" not in map_logic, "error: state.error"))
    checks.append((
        "map_uses_shared_translation",
        "showStickyMapPlayerError(state.error)" in map_logic,
        "showStickyMapPlayerError(state.error)",
    ))
    checks.append((
        "action_log_is_html_escaped",
        "<div>${escapeHtml(entry)}</div>" in app and "<div>${entry}</div>" not in app,
        "action_log entries must be escaped before innerHTML",
    ))
    checks.append((
        "map_dynamic_prompts_are_html_escaped",
        "${escapeHtml(promptText)}" in map_logic and "${escapeHtml(stickyPlayerErrorMessage)}" in map_logic,
        "map prompt/error values must be escaped before innerHTML",
    ))

    required = [
        "playerMessageZhTw(data.error)",
        "playerMessageZhTw(state.error)",
        "playerMessageZhTw(choice.prompt",
    ]
    for snippet in required:
        checks.append((f"uses_{snippet}", snippet in app, snippet))

    representative = {
        "Game not found": "找不到遊戲房間。",
        "All players must be ready before start": "所有玩家都需要先按下準備。",
        "Target player has no organization within range": "目標玩家在範圍內沒有組織。",
        "Not enough move points (airport base relocation costs 2)": "移動次數不足；機場遷移根據地需要 2 次移動。",
        "No road connection": "起點與目標之間沒有道路連線。",
        "Base already taken: 北京": "以下根據地已被選擇：北京",
        "請先處理目前待選擇效果。": "請先處理目前待選擇效果。",
    }
    translated = translate_with_node(list(representative))
    for source, actual in zip(representative, translated):
        expected = representative[source]
        checks.append((f"translation:{source}", actual == expected, f"expected={expected!r}, actual={actual!r}"))

    unknown = translate_with_node(["A future unmapped player-visible error"])[0]
    checks.append((
        "unknown_english_uses_chinese_fallback",
        not re.search(r"[A-Za-z]{3,}", unknown),
        unknown,
    ))

    errors = backend_error_literals()
    translated_errors = translate_with_node(errors)
    leaking = [
        {"source": source, "translated": target}
        for source, target in zip(errors, translated_errors)
        if re.search(r"[A-Za-z]{3,}", target)
    ]
    checks.append((
        "backend_constant_errors_do_not_leak_english",
        not leaking,
        f"errors={len(errors)}, leaking={leaking[:5]}",
    ))
    generic_fallback = "操作失敗，請重新確認目前狀態後再試。"
    fallback_sources = [source for source, target in zip(errors, translated_errors) if target == generic_fallback]
    checks.append((
        "backend_constant_errors_have_specific_translation",
        not fallback_sources,
        f"fallback_sources={fallback_sources}",
    ))

    failed = [entry for entry in checks if not entry[1]]
    report = {
        "status": "passed" if not failed else "failed",
        "checks_passed": len(checks) - len(failed),
        "checks_total": len(checks),
        "backend_error_literals": len(errors),
        "failed": [{"name": name, "detail": detail} for name, _, detail in failed],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
