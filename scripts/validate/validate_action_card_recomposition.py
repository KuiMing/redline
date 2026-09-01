#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "docs/records/design/card-art/all-action-cards-ai-review"
RECORD = ROOT / "docs/records/card-art"
OUT_JSON = RECORD / "ACTION_CARD_HEAD_SAFE_RECOMPOSITION_VALIDATION.json"
OUT_MD = RECORD / "ACTION_CARD_HEAD_SAFE_RECOMPOSITION_VALIDATION.md"


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not PNG: {path}")
    return struct.unpack(">II", header[16:24])


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    with (ROOT / "data/raw/action_cards.csv").open(encoding="utf-8-sig", newline="") as handle:
        names = [row["行動卡名稱"].strip() for row in csv.DictReader(handle)]
    with (RECORD / "ACTION_CARD_ART_CROP_AUDIT.csv").open(encoding="utf-8-sig", newline="") as handle:
        audit = {row["name"]: row for row in csv.DictReader(handle)}

    results: list[dict] = []
    for name in names:
        composed = REVIEW / "art-composed" / f"{name}_插圖.png"
        full = REVIEW / "png" / f"{name}.png"
        preview = REVIEW / "preview-220x270" / f"{name}.png"
        runtime = ROOT / "static/card-art/actions" / f"{name}.png"
        svg = REVIEW / "svg" / f"{name}.svg"
        root = ET.parse(svg).getroot()
        image_nodes = [node for node in root.iter() if node.tag.endswith("image")]
        hrefs = {value for node in image_nodes for key, value in node.attrib.items() if key.endswith("href")}
        row = audit.get(name, {})
        checks = {
            "composed_996x468": composed.exists() and png_size(composed) == (996, 468),
            "full_1100x1350": full.exists() and png_size(full) == (1100, 1350),
            "preview_220x270": preview.exists() and png_size(preview) == (220, 270),
            "runtime_matches_review": runtime.exists() and digest(runtime) == digest(full),
            "svg_uses_explicit_composed_crop": f"../art-composed/{name}_插圖.png" in hrefs,
            "visual_review_passed": row.get("review_status") == "pass_head_safe_2026-07-26",
        }
        results.append({"name": name, "passed": all(checks.values()), "checks": checks})

    summary = {
        "cards": len(results),
        "passed": sum(1 for row in results if row["passed"]),
        "failed": sum(1 for row in results if not row["passed"]),
    }
    payload = {"summary": summary, "results": results}
    RECORD.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 行動卡頭部安全取景重組驗證",
        "",
        "可重跑：`uv run python scripts/validate/validate_action_card_recomposition.py`",
        "",
        f"- cards: {summary['cards']} / passed: {summary['passed']} / failed: {summary['failed']}",
        "",
    ]
    for row in results:
        lines.append(f"- {'✅' if row['passed'] else '❌'} `{row['name']}` — {json.dumps(row['checks'], ensure_ascii=False)}")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
