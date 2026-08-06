#!/usr/bin/env python3
"""Generate the eleven Redline full-screen victory backgrounds through Codex OAuth.

Run from the repository root with Hermes' bundled Python:

    OPENAI_IMAGE_MODEL=gpt-image-2-medium \
      "$HOME/.hermes/hermes-agent/venv/bin/python" \
      scripts/generate_victory_ending_ai_art.py

Existing non-empty PNGs are skipped, so interrupted batches can be resumed safely.
"""

from __future__ import annotations

import argparse
import importlib
import json
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "static" / "victory-art"
STYLE = (
    "Create a cinematic 16:9 full-screen victory background for an alternate-history "
    "political strategy board game set in East and Central Asia. Painterly realistic "
    "digital matte painting, premium game key art, dramatic volumetric light, deep "
    "atmosphere, layered foreground/midground/background, historically and geographically "
    "recognizable architecture and landscape, dignified human figures, rich detail, no "
    "graphic violence. Compose for a game end screen: strongest visual subjects around "
    "the left and right thirds, with calmer darker negative space through the center and "
    "lower-middle for a translucent results panel. Edge-to-edge artwork with no frame. "
    "ABSOLUTELY NO text, letters, captions, logos, watermarks, UI, borders, maps with labels, "
    "or fake writing. Do not depict modern politicians or identifiable real individuals. "
)

SCENES = {
    "red_army": (
        "Red Army victory, shown entirely from the human cost of totalitarian conquest: a once-"
        "prosperous East Asian metropolis has become a rain-soaked wasteland of burned apartment "
        "blocks, collapsed shops, shattered civic buildings, blacked-out homes and abandoned "
        "public transit. Long columns of exhausted displaced civilians—elderly people, parents "
        "carrying children, families dragging their remaining belongings—move through mud and "
        "ash beneath armed checkpoints and watchtowers. Searchlights rake the ruins, factory smoke "
        "and distant fires choke an iron-red sky, severe blank crimson banners hang from a vast "
        "authoritarian monument. Show hunger, grief, fear, homelessness and a whole society crushed; "
        "the victory must feel unmistakably catastrophic, bleak and morally horrifying, never "
        "heroic or celebratory. No gore, no corpses, no active violence."
    ),
    "red_army_triumph": (
        "Red Army victory as seen through its own grandiose propaganda: the Red Army has conquered "
        "the entire world. A colossal global capital at sunrise, combining monumental East Asian "
        "palaces with futuristic towers, an enormous unlabeled globe monument beneath vast blank "
        "crimson banners, triumphal avenues stretching to the horizon, endless disciplined columns, "
        "armored formations, aircraft and ocean fleets arriving from every continent. Victorious "
        "commanders stand on a high terrace overlooking a planet unified under red light; distant "
        "landmarks from many world regions are absorbed into one immense imperial skyline. Make it "
        "overwhelmingly vast, glorious, invincible and self-mythologizing—the regime sincerely sees "
        "this as the final conquest of history. No suffering, ruins or frightened civilians in this "
        "propaganda viewpoint. Deep crimson, gold and sunrise-white palette."
    ),
    "taiwan_green": (
        "Taiwan green-line victory: a free, democratic and prosperous Taiwan at sunrise, "
        "Taipei skyline and green mountains, lively civic plaza, families and citizens openly "
        "celebrating, clean transit and warm city lights, ocean glinting beyond the island. "
        "Hopeful emerald, turquoise and gold palette; mood of liberty, peace and flourishing."
    ),
    "taiwan_blue": (
        "Taiwan blue-line victory: a dramatic Republic-era strategic triumph looking west "
        "across the Taiwan Strait, dignified officers and civilian planners on a coastal "
        "command terrace, distant fleet silhouettes and mainland mountains under a blue-hour "
        "sunrise, navy blue and restrained crimson palette. Mood of resolve and planning a "
        "historic return, grand but not violent; no readable maps or insignia."
    ),
    "hong_kong": (
        "Hong Kong victory: Victoria Harbour at dawn reborn as a free city, iconic dense "
        "harbour skyline and Lion Rock silhouette, ferries on luminous water, citizens filling "
        "a waterfront promenade beneath warm lantern-like lights, broken storm clouds opening "
        "to rose-gold sunlight. Mood of resilience, freedom and a city breathing again."
    ),
    "uyghur": (
        "Uyghur victory: an independent East Turkestan at a radiant new dawn, Kashgar old-city "
        "architecture, turquoise domes without writing, bustling bazaar, musicians and families "
        "in culturally respectful Uyghur dress, poplar-lined oasis, desert and snow peaks in the "
        "distance. Turquoise, sand and gold palette; mood of cultural survival and freedom."
    ),
    "tibet": (
        "Tibetan victory: the high plateau liberated at sunrise, Lhasa-inspired white-and-ochre "
        "hilltop architecture, immense snow mountains, windblown prayer flags shown only as "
        "colorful fabric with no writing, monks and families overlooking a peaceful valley. "
        "Saffron, maroon, cobalt and snow-gold palette; mood of spiritual dignity and renewal."
    ),
    "manchuria": (
        "Manchurian victory: rebirth across the forests and great northern plains, elegant "
        "Harbin-inspired brick and stone city, modern rail lines and restored industry in the "
        "distance, birch and pine forests, broad river under pale northern dawn, workers and "
        "families gathering in the foreground. Jade, amber and steel-blue palette; mood of "
        "independent renewal rather than militarism."
    ),
    "mongol": (
        "Mongol victory: a reunited Mongolia embracing the Inner Mongolian grasslands, endless "
        "steppe beneath an enormous blue sky, horse riders and herding families around a modern "
        "ger encampment, distant contemporary capital and sacred mountains, golden eagle soaring, "
        "sunlight breaking across the plains. Cobalt, grass green and gold palette; sweeping, "
        "majestic mood of unity and open horizons."
    ),
    "kazakh": (
        "Kazakh victory: the Ili valley free beneath the Tian Shan, turquoise river winding "
        "through golden grasslands, snow mountains, horse riders and families beside ornamented "
        "yurts, distant modern town glowing at sunset, eagle high in the sky. Sky blue, white and "
        "gold palette; mood of homecoming, dignity and a borderland opening into freedom."
    ),
    "rebel": (
        "Grand rebel coalition victory: many regional resistance movements united after the old "
        "regime falls, a vast diverse crowd crossing a monumental city square at sunrise, farmers, "
        "workers, students and local leaders carrying many differently colored blank fabric banners "
        "with no symbols or writing, distant provincial landscapes layered into the horizon. Warm "
        "ember, terracotta and gold palette; exuberant solidarity without a single dominant faction."
    ),
}


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as fh:
        signature = fh.read(24)
    if len(signature) < 24 or signature[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a valid PNG: {path}")
    return struct.unpack(">II", signature[16:24])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", choices=SCENES, help="Generate only one scene")
    parser.add_argument("--force", action="store_true", help="Replace an existing scene")
    args = parser.parse_args()

    provider_module = importlib.import_module("plugins.image_gen.openai-codex")
    provider = provider_module.OpenAICodexImageGenProvider()
    if not provider.is_available():
        raise SystemExit("No usable Codex OAuth token")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    selected = {args.scene: SCENES[args.scene]} if args.scene else SCENES

    for index, (key, scene) in enumerate(selected.items(), start=1):
        destination = OUTPUT_DIR / f"{key}.png"
        if not args.force and destination.exists() and destination.stat().st_size > 0:
            width, height = png_dimensions(destination)
            print(f"[{index}/{len(selected)}] SKIP {key}: {width}x{height}", flush=True)
            continue

        print(f"[{index}/{len(selected)}] GENERATE {key}", flush=True)
        result = provider.generate(STYLE + scene, aspect_ratio="landscape")
        if not result.get("success"):
            raise RuntimeError(f"Generation failed for {key}: {result}")
        source = Path(str(result["image"]))
        shutil.copy2(source, destination)
        width, height = png_dimensions(destination)
        print(f"[{index}/{len(selected)}] SAVED {destination} ({width}x{height})", flush=True)

    manifest: dict[str, dict[str, object]] = {}
    for key, scene in SCENES.items():
        destination = OUTPUT_DIR / f"{key}.png"
        width, height = png_dimensions(destination)
        manifest[key] = {
            "file": destination.relative_to(ROOT).as_posix(),
            "width": width,
            "height": height,
            "prompt": STYLE + scene,
        }

    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps({"generator": "OpenAI Codex Responses image_generation", "scenes": manifest}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"WROTE {manifest_path}")


if __name__ == "__main__":
    main()
