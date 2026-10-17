#!/usr/bin/env python3
# /// script
# dependencies = ["pillow>=11,<13"]
# ///
"""Validate the complete review-only half-height card batch."""
from __future__ import annotations

import importlib.util
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts/generate_half_height_cards.py"
OUTPUT = ROOT / "docs/records/design/card-art/half-height-cards"
EXPECTED_ACTIONS = 46
EXPECTED_SUPPORT = 17
EXPECTED_SIZE = (1100, 675)


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_half_height_cards", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"無法載入 {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: object) -> None:
    if not condition:
        raise AssertionError(message)


def png_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        size = image.size
        image.verify()
    return size


def visible_text(svg: str) -> str:
    root = ET.fromstring(svg)
    return "".join(root.itertext()).replace(" ", "").replace("\n", "")


def main() -> None:
    generator = load_generator()
    actions = generator.load_action_rows()
    supports = generator.load_support_rows()
    require(len(actions) == EXPECTED_ACTIONS, len(actions))
    require(len(supports) == EXPECTED_SUPPORT, len(supports))

    expected_paths: set[str] = set()
    expected_manifest: list[dict[str, object]] = []
    for row in actions:
        name = row["行動卡名稱"].strip()
        svg = generator.action_svg(row)
        text = visible_text(svg)
        for expected in (name, row["行動卡意涵"].strip(), "購買費用", "提供資源"):
            require(expected.replace(" ", "") in text, (name, expected))
        generator.resource_items(row["購買費用"].strip())
        generator.resource_items(row["提供資源"].strip())
        path = f"actions/{name}.png"
        expected_paths.add(path)
        expected_manifest.append({
            "kind": "action", "name": name, "variant": "", "path": path,
            "width": EXPECTED_SIZE[0], "height": EXPECTED_SIZE[1],
        })

    for index, row in enumerate(supports, 1):
        stem = f"{index:02d}_{row['name']}_{generator.slug_condition(row['variant'])}"
        svg = generator.support_svg(row)
        text = visible_text(svg)
        for expected in (row["name"], row["cost"], generator.SUPPORT_CAPTIONS[row["name"]]):
            require(expected.replace(" ", "") in text, (stem, expected))
        if row["name"] == "紅軍奧援":
            for expected in ("提供資源", *[part for item in generator.resource_items(row["resources"]) for part in item]):
                require(expected in text, (stem, expected))
        else:
            require("II級條件" in text and row["variant"] in text, stem)
        path = f"support/{stem}.png"
        expected_paths.add(path)
        expected_manifest.append({
            "kind": "support", "name": row["name"], "variant": row["variant"], "path": path,
            "width": EXPECTED_SIZE[0], "height": EXPECTED_SIZE[1],
        })

    manifest_path = OUTPUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest == expected_manifest, "manifest 與 canonical card data 不一致")
    require(len(manifest) == EXPECTED_ACTIONS + EXPECTED_SUPPORT, len(manifest))
    manifest_paths = {item["path"] for item in manifest}
    require(manifest_paths == expected_paths, manifest_paths ^ expected_paths)
    require(all((item["width"], item["height"]) == EXPECTED_SIZE for item in manifest), "manifest 尺寸錯誤")

    actual_paths = {
        path.relative_to(OUTPUT).as_posix()
        for path in OUTPUT.glob("**/*.png")
        if path.parent.name in {"actions", "support"}
    }
    require(actual_paths == expected_paths, actual_paths ^ expected_paths)
    for relative in sorted(expected_paths):
        path = OUTPUT / relative
        size = png_size(path)
        require(size == EXPECTED_SIZE, (relative, size))
        require(path.stat().st_size > 100_000, (relative, path.stat().st_size))

    contact_sheets = {
        "半高行動卡總覽.png": (1040, 2336),
        "半高奧援卡總覽.png": (1040, 1006),
    }
    for name, expected_size in contact_sheets.items():
        path = OUTPUT / name
        require(png_size(path) == expected_size, (name, png_size(path)))

    generator.validate_output_path(OUTPUT)
    print(
        "PASS "
        f"actions={len(actions)} support={len(supports)} total={len(manifest)} "
        f"size={EXPECTED_SIZE[0]}x{EXPECTED_SIZE[1]} output={OUTPUT.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
