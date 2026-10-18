#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=11,<13"]
# ///
"""Validate runtime half-height card assets and purchase UI contracts."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = ROOT / "static" / "card-art-half-height"
MANIFEST = RUNTIME_ROOT / "manifest.json"
APP_JS = ROOT / "static" / "app.js"
STYLE_CSS = ROOT / "static" / "style.css"
INDEX_HTML = ROOT / "static" / "index.html"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def validate_png(path: Path) -> None:
    require(path.is_file(), f"missing runtime card: {path.relative_to(ROOT)}")
    with Image.open(path) as image:
        require(image.size == (1100, 675), f"wrong dimensions for {path.name}: {image.size}")
        image.load()
    with Image.open(path) as image:
        image.verify()


def main() -> None:
    require(MANIFEST.is_file(), "missing runtime half-height manifest")
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(isinstance(entries, list), "runtime manifest must be a list")
    require(len(entries) == 63, f"runtime manifest must contain 63 cards, got {len(entries)}")
    actions = [entry for entry in entries if entry.get("kind") == "action"]
    support = [entry for entry in entries if entry.get("kind") == "support"]
    require(len(actions) == 46, f"expected 46 action cards, got {len(actions)}")
    require(len(support) == 17, f"expected 17 support cards, got {len(support)}")
    manifest_paths = set()
    for entry in entries:
        rel = entry.get("path")
        require(isinstance(rel, str) and bool(rel), f"invalid manifest path: {entry!r}")
        require(rel not in manifest_paths, f"duplicate manifest path: {rel}")
        manifest_paths.add(rel)
        require(entry.get("width") == 1100 and entry.get("height") == 675, f"wrong manifest size: {rel}")
        validate_png(RUNTIME_ROOT / rel)

    actual_paths = {
        path.relative_to(RUNTIME_ROOT).as_posix()
        for folder in (RUNTIME_ROOT / "actions", RUNTIME_ROOT / "support")
        for path in folder.glob("*.png")
    }
    require(actual_paths == manifest_paths, "runtime card files differ from manifest")

    app = APP_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    require("/static/card-art-half-height" in app, "compact cards do not use runtime half-height assets")
    require('class="purchase-card-select-button' in app, "purchase cards do not render select buttons")
    require("purchase-card-selected-overlay" in app, "selected purchase card overlay is missing")
    require("purchase-card-checkbox" not in app, "legacy purchase checkbox remains in app.js")
    require("purchase-card-checkbox" not in css, "legacy purchase checkbox styles remain")
    require("background: rgba(255, 255, 255, 0.28)" in css, "selected overlay is not 28% white")
    require(".card.rl-pad-focus::after" in css, "controller focus does not target the controller's rl-pad-focus class")
    require("border: 2px solid #ffd83d" in css, "controller focus is not an opaque yellow border")
    require("background: transparent" in css, "controller focus border interior is not transparent")
    require("border-width: 2.57px" in css, "living-room zoom does not preserve a 2px focus border")
    require("grid-template-rows: repeat(3, minmax(0, 1fr))" in css, "command centre is not a three-row layout")
    random_pos = html.index('id="randomMarketPanel"')
    static_pos = html.index('id="controlPanel"')
    hand_pos = html.index('id="handPanel"')
    require(random_pos < static_pos < hand_pos, "command centre DOM order must be random, static, hand")
    require("half-height-purchase-ui" in html, "static asset cache version was not updated")
    print("PASS: runtime half-height cards 63/63 and purchase UI source contracts")


if __name__ == "__main__":
    main()
