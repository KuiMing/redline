"""Build the card presentation catalog consumed by the HTTP API."""

import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
ACTION_CSV_PATH = BASE_DIR / "data" / "raw" / "action_cards.csv"
SUPPORT_CSV_PATH = BASE_DIR / "data" / "raw" / "support_cards.csv"


def load_card_presentation_catalog():
    catalog = {}
    if ACTION_CSV_PATH.exists():
        with ACTION_CSV_PATH.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) < 10 or not row[1]:
                    continue
                catalog[row[1]] = {
                    "name": row[1],
                    "color": row[2],
                    "kind": row[3],
                    "strength": row[4],
                    "cost_text": row[5],
                    "effect_text": row[6],
                    "resource_text": row[7],
                    "position_text": row[8],
                    "meaning_text": row[9],
                    "count_text": row[10] if len(row) > 10 else "",
                }
    if SUPPORT_CSV_PATH.exists():
        with SUPPORT_CSV_PATH.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            rows_by_name = {}
            order = []
            for row in reader:
                if len(row) < 9 or not row[0]:
                    continue
                name = row[0]
                if name not in rows_by_name:
                    rows_by_name[name] = []
                    order.append(name)
                rows_by_name[name].append(row)
            for name in order:
                rows = rows_by_name[name]
                first = rows[0]
                # 每種奧援卡實體上印有 len(rows) 種不同印刷變體：III級門檻地區與效果、I級效果
                # 皆相同，只有 II級門檻地區（區域主導者優待）不同，各變體各自的張數見 row[8]。
                # 兩種變體都要呈現，不能只取第一列或把地區合併成一條（2026-07-16 使用者裁決）。
                variants = [
                    {
                        "tier3_region": row[2],
                        "tier3_text": row[3],
                        "tier2_regions": [
                            region.strip()
                            for region in row[4].split("、")
                            if region.strip()
                        ],
                        "tier2_text": row[5],
                        "tier1_text": row[7],
                        "copies": row[8] if len(row) > 8 else "",
                    }
                    for row in rows
                ]
                total_copies = sum(int(variant["copies"] or 0) for variant in variants)
                tier2_lines = "\n".join(
                    f"II級（{'/'.join(variant['tier2_regions'])}其一主導，此變體{variant['copies']}張）：{variant['tier2_text']}"
                    for variant in variants
                )
                catalog[name] = {
                    "name": name,
                    "color": "奧援",
                    "kind": "奧援",
                    "strength": "特殊",
                    "cost_text": first[1],
                    "effect_text": (
                        f"III級（{first[2]}主導）：{first[3]}\n"
                        f"{tier2_lines}\nI級（皆未主導）：{first[7]}"
                    ),
                    "resource_text": "依效果而定",
                    "position_text": "隨機購買區",
                    "meaning_text": "奧援卡",
                    "count_text": str(total_copies),
                    "support_variants": variants,
                }
    catalog["紅軍奧援"] = {
        "name": "紅軍奧援",
        "color": "奧援",
        "kind": "奧援",
        "strength": "特殊",
        "cost_text": "起始牌",
        "effect_text": "行動：抽1張牌。若您為紅軍，打出後將本牌放進任一反共陣營玩家棄牌堆；若您為反共陣營玩家，打出後將本牌放進紅軍棄牌堆。",
        "resource_text": "提供1資金+1宣傳；打出後依陣營放入對應棄牌堆",
        "position_text": "起始牌",
        "meaning_text": "會轉移至對立陣營棄牌堆的特殊奧援卡",
        "count_text": "1",
    }
    return catalog


CARD_PRESENTATION_CATALOG = load_card_presentation_catalog()
