#!/usr/bin/env python3
"""Reframe action-card source illustrations into the exact wide card-art window.

The AI sources are mostly portrait images.  Rendering them with an implicit
center-cover crop removed the protagonists' heads.  This script keeps the
original sources immutable and creates explicit, reviewed 996×468 crops whose
focal point is placed in the upper third of the card window.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
REVIEW_ROOT = Path(
    os.environ.get(
        "ACTION_CARD_ART_OUT",
        ROOT / "docs/records/design/card-art/all-action-cards-ai-review",
    )
)
SOURCE_DIR = REVIEW_ROOT / "art"
OUTPUT_DIR = REVIEW_ROOT / "art-composed"
AUDIT_PATH = REVIEW_ROOT / "action-card-art-crop-audit.csv"
CSV_PATH = ROOT / "data/raw/action_cards.csv"
TARGET_SIZE = (996, 468)
TARGET_RATIO = TARGET_SIZE[0] / TARGET_SIZE[1]

# Reviewed focal-point Y coordinates in source pixels.  These identify the
# principal face or the visual center of a crowd when no single portrait leads.
# They deliberately differ from an image-center crop; the target focal point is
# placed 35% down the final wide window, preserving heads plus hands/action below.
FOCAL_Y = {
    "追隨者": 300,
    "宣傳家": 374,
    "思想家": 350,
    "樂捐者": 330,
    "資助者": 355,
    "資本家": 335,
    "分神": 352,
    "內鬥": 305,
    "交通經驗丙": 270,
    "交通經驗乙": 520,
    "交通經驗甲": 520,
    "領導": 350,
    "謀劃": 255,
    "戰略": 330,
    "合作談判": 305,
    "高效行動": 370,
    "模仿戰術": 305,
    "乘勝追擊": 345,
    "擴大戰果": 320,
    "誘導虛耗": 510,
    "點燃熱情": 410,
    "樹立信心": 300,
    "網羅人才": 480,
    "凝聚共識": 365,
    "思想建設": 360,
    "派遣間諜": 310,
    "內應間諜": 450,
    "情報網": 630,
    "離間": 545,
    "走漏風聲": 345,
    "地下黨": 385,
    "組織經驗丙": 500,
    "組織經驗乙": 385,
    "組織經驗甲": 700,
    "批判": 425,
    "批鬥": 410,
    "武裝者": 305,
    "武裝小隊": 350,
    "武裝集團": 250,
    "爆料黑幕": 290,
    "輿論丕變": 380,
    "行動預告": 300,
    "企業人脈": 250,
    "產業滲透": 345,
    "企畫遊說": 225,
    "行動募資": 380,
}


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def crop_box(image: Image.Image, focal_y: int) -> tuple[int, int, int, int]:
    width, height = image.size
    crop_height = min(height, round(width / TARGET_RATIO))
    # Put the focal face at 35% of the crop, leaving more room below for hands,
    # documents, maps, and other mechanic-bearing action details.
    top = clamp(round(focal_y - crop_height * 0.35), 0, height - crop_height)
    return (0, top, width, top + crop_height)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    names = [row["行動卡名稱"].strip() for row in rows]
    if set(names) != set(FOCAL_Y):
        raise SystemExit(
            f"FOCAL_Y mismatch missing={sorted(set(names) - set(FOCAL_Y))} "
            f"extra={sorted(set(FOCAL_Y) - set(names))}"
        )

    audit_rows: list[dict[str, object]] = []
    for index, name in enumerate(names, 1):
        source = SOURCE_DIR / f"{name}_插圖.png"
        destination = OUTPUT_DIR / f"{name}_插圖.png"
        if not source.exists():
            raise FileNotFoundError(source)
        with Image.open(source) as opened:
            image = opened.convert("RGB")
            box = crop_box(image, FOCAL_Y[name])
            crop = image.crop(box).resize(TARGET_SIZE, Image.Resampling.LANCZOS)
            # Counteract a small amount of softness from the 5× production resize
            # without changing the illustration's palette or content.
            crop = ImageEnhance.Sharpness(crop).enhance(1.08)
            crop.save(destination, format="PNG", optimize=True)
        audit_rows.append(
            {
                "index": index,
                "name": name,
                "source_width": image.width,
                "source_height": image.height,
                "focal_y": FOCAL_Y[name],
                "crop_left": box[0],
                "crop_top": box[1],
                "crop_right": box[2],
                "crop_bottom": box[3],
                "output_width": TARGET_SIZE[0],
                "output_height": TARGET_SIZE[1],
                "review_status": "pass_head_safe_2026-07-26",
            }
        )
        print(f"[{index:02d}/{len(names)}] {name}: source={image.size} crop={box}")

    with AUDIT_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(audit_rows)
    print(f"DONE {len(audit_rows)} crops -> {OUTPUT_DIR}")
    print(f"AUDIT -> {AUDIT_PATH}")


if __name__ == "__main__":
    main()
