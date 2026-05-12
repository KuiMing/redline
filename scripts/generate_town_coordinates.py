import json
from pathlib import Path
import math

BASE_DIR = Path(__file__).resolve().parent.parent
MAP_PATH = BASE_DIR / "data" / "map.json"
OUTPUT_PATH = BASE_DIR / "data" / "town_coordinates.v1.json"

CANVAS_WIDTH = 2400
CANVAS_HEIGHT = 1400

# ✅ 半地理區域中心（手動定義）
REGION_CENTERS = {
    "china": (1500, 700),
    "taiwan": (1750, 900),
    "hong_kong": (1500, 850),
    "manchuria": (1500, 400),
    "mongolian_plateau": (1300, 300),
    "inner_mongolia": (1400, 450),
    "turkestan": (900, 600),
    "tibet_region": (1200, 800),
    "india": (1000, 900),
    "middle_east": (600, 750),
    "japan": (1900, 550),
    "korean_peninsula": (1700, 500),
    "trans_siberian": (1000, 250),
    "anglo_america": (300, 800),
    "europe": (500, 500),
    "outer_manchuria": (1600, 250),
    "southeast_asia": (1400, 1000)
}

with open(MAP_PATH, encoding="utf-8") as f:
    map_data = json.load(f)


towns_by_region = {
    region_key: []
    for region_key in REGION_CENTERS
}

for town, info in map_data.get("towns", {}).items():
    rulers = set(info.get("ruler") or [])
    if "紅軍" in rulers:
        towns_by_region["china"].append(town)
    if "臺灣" in rulers:
        towns_by_region["taiwan"].append(town)
    if town in {"香港城", "九龍城", "新界", "上粉沙打", "元朗", "上水"}:
        towns_by_region["hong_kong"].append(town)
    if "滿洲" in rulers:
        towns_by_region["manchuria"].append(town)
    if "蒙古" in rulers:
        towns_by_region["mongolian_plateau"].append(town)
    if town in {"呼和浩特", "包頭", "烏海", "赤峰", "通遼", "巴彥淖爾", "鄂爾多斯"}:
        towns_by_region["inner_mongolia"].append(town)
    if town in {"阿拉木圖", "阿斯塔納", "塔什干", "撒馬爾罕", "比什凱克", "杜尚別", "克孜勒蘇", "伊寧", "克拉瑪依", "喀什"}:
        towns_by_region["turkestan"].append(town)
    if "藏國" in rulers:
        towns_by_region["tibet_region"].append(town)
    if "印度" in rulers:
        towns_by_region["india"].append(town)
    if "天方" in rulers:
        towns_by_region["middle_east"].append(town)
    if "東洋" in rulers:
        towns_by_region["japan"].append(town)
    if town in {"首爾", "釜山"}:
        towns_by_region["korean_peninsula"].append(town)
    if "北國" in rulers:
        towns_by_region["trans_siberian"].append(town)
        if town in {"海參崴", "伯力", "赤塔", "海蘭泡", "薩哈林"}:
            towns_by_region["outer_manchuria"].append(town)
    if "英美" in rulers:
        towns_by_region["anglo_america"].append(town)
    if "歐洲" in rulers:
        towns_by_region["europe"].append(town)
    if "南洋" in rulers:
        towns_by_region["southeast_asia"].append(town)

for towns in towns_by_region.values():
    towns.sort()


town_coords = {}

for region_key, towns in towns_by_region.items():
    center = REGION_CENTERS.get(region_key)
    if not center:
        continue

    count = len(towns)

    if count == 0:
        continue

    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)

    spacing_x = 80
    spacing_y = 60

    start_x = center[0] - (cols - 1) * spacing_x / 2
    start_y = center[1] - (rows - 1) * spacing_y / 2

    for i, town in enumerate(towns):
        row = i // cols
        col = i % cols
        x = start_x + col * spacing_x
        y = start_y + row * spacing_y

        town_coords[town] = {
            "x": round(x),
            "y": round(y)
        }

output = {
    "canvas": {
        "width": CANVAS_WIDTH,
        "height": CANVAS_HEIGHT
    },
    "towns": town_coords
}

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"✅ Generated {len(town_coords)} town coordinates")
