#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import importlib
import json
import math
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
CSV_PATH = REPO / "data/raw/event_and_era_cards.csv"
ROOT = REPO / "docs/records/design/card-art/all-era-card-trials-ai-review"
ART_DIR = ROOT / "art"
SVG_DIR = ROOT / "svg"
PNG_DIR = ROOT / "png"
PREVIEW_DIR = ROOT / "preview-270x220"
PROGRESS = ROOT / "ai-generation-progress.json"
MANIFEST = ROOT / "manifest.csv"
CONTACT = ROOT / "各陣營時代關卡_總覽.png"
ZIP_PATH = REPO / "docs/records/design/card-art/各陣營時代關卡_AI試畫_未提交檢查包.zip"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

BASE_STYLE = (
    "Create premium TEXT-FREE landscape key art for a historical political-strategy board-game ERA MILESTONE card. "
    "Fictionalized political history, cinematic historical gouache, restrained screen-print texture, clear wide composition "
    "that survives a shallow crop, realistic anatomy and hands, dramatic but dignified, opaque full-bleed background. "
    "Translate three beats into one image: a movement reaches a threshold, authoritarian repression follows, and a resilient "
    "counter-movement emerges. No readable writing, letters, numbers, map labels, real national flag, party emblem, star, "
    "hammer-and-sickle, logo, watermark, frame, border, UI, title, graphic gore, sexual content, or typography anywhere. "
)

SCENES = {
    "香港": "Rainy subtropical harbor metropolis at night, dense towers and steep streets, civic organizers with blank umbrellas and blank paper form a broad network; plainclothes security raid apartment corridors in shadow while determined resistance groups regroup below neon-like light with no signs or text. Palette: wet teal, amber, charcoal, crimson accents.",
    "蒙古": "Vast Southern Mongolian grassland under a storm sky, herders and students gather around a fallen rider's riderless horse to defend pasture; distant officials sow suspicion between groups, yet a new generation joins hands across the steppe. Gers, horses and windswept grass, no flags. Palette: sky blue, ochre, black, weathered red.",
    "藏國": "High Tibetan plateau spanning three cultural regions, monastery silhouettes and a railway cutting across snowy valleys; prepared civilian networks rally in towns, armored trains and security columns arrive, while spiritual resolve and community solidarity rise from mountain paths. Plain cloth streamers only, no symbols or writing. Palette: saffron, deep maroon, ice blue, stone gray.",
    "哈薩克": "Central Asian borderlands around the Dzungarian basin, mounted guides and families cross guarded mountain passes through multiple routes, aided from both sides by three tribal circles represented only by people and landscape; authorities close routes, but escaped compatriots reinforce the movement. Palette: turquoise, gold, alpine blue, dusk violet.",
    "維吾爾": "Tarim oasis city on a solemn festival night, seven distant city lights across desert routes; armed security sweeps toward neighborhoods while protectors shelter families and disciplined resistance gathers beyond mud-brick walls. Islamic Central Asian arches without writing, no gore. Palette: lapis, sand, moonlit indigo, restrained crimson.",
    "滿洲": "Northeastern industrial heartland with rail yards, brick factories, snow and old civic buildings; local officials and regional networks quietly consolidate power as central inspectors arrive, while administrators secure archives and supply routes. No historical state symbols. Palette: steel blue, rust, pine green, muted gold.",
    "反賊": "A modernizing East Asian city shifting from a relatively open decade into digital winter: public discussion spaces go dark under expanding surveillance towers and blank screens, while small underground reading circles and neighborhood organizers plant resilient new networks. Palette: cold cyan, black, paper white, warning red.",
    "臺灣": "Island democracy with coastal mountains, dense city, temple roofs and civic halls; appeasement politicians obstruct cross-strait resistance while covert influence spreads in shadow, but civil groups rebuild networks and counter infiltration from local communities. No real flag or party logo. Palette: ocean blue, jade, warm civic gold, restrained red.",
}

FACTION_COLORS = {
    "香港": "#3f6f78", "蒙古": "#806234", "藏國": "#814b43", "哈薩克": "#3c7180",
    "維吾爾": "#38746a", "滿洲": "#596a48", "反賊": "#555b75", "臺灣": "#376d86",
}


def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def safe_name(value: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]", "_", value).strip()


def valid_image(path: Path, size: tuple[int, int] | None = None) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            if size and image.size != size:
                return False
        return path.stat().st_size > 10000
    except Exception:
        return False


def load_rows() -> list[dict[str, str]]:
    rows, era = [], False
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        for values in csv.reader(handle):
            if not values:
                continue
            if values[0] == "時代關卡名稱":
                era = True
                continue
            if not era:
                continue
            if not values[0].strip():
                break
            match = re.match(r"^\[([^]]+)\](.+)$", values[0].strip())
            if not match:
                raise RuntimeError(f"無法解析時代關卡名稱：{values[0]}")
            rows.append({
                "canonical_name": values[0].strip(), "faction": match.group(1), "title": match.group(2),
                "summary": values[1].strip(), "trigger": values[2].strip(),
                "suppression": values[3].strip(), "counterattack": values[4].strip(), "copies": values[5].strip(),
            })
    if len(rows) != 8:
        raise RuntimeError(f"預期 8 張時代關卡，實得 {len(rows)}")
    if set(SCENES) != {row["faction"] for row in rows}:
        raise RuntimeError("SCENES 與 CSV 陣營不一致")
    return rows


def wrap_cjk(text: str, width: int) -> list[str]:
    lines, current = [], ""
    for char in text.strip():
        current += char
        if len(current) >= width and char in "，。；：、！？]］ ":
            lines.append(current.strip()); current = ""
        elif len(current) >= width + 2:
            lines.append(current.strip()); current = ""
    if current.strip():
        lines.append(current.strip())
    return lines or ["無"]


def panel(y: int, label: str, text: str, color: str) -> str:
    compact_len = len(re.sub(r"\s+", "", text))
    if compact_len <= 44:
        width, size = 22, 42
    elif compact_len <= 84:
        width, size = 28, 32
    else:
        width, size = 31, 27
    lines = wrap_cjk(text, width)
    line_height = int(size * 1.18)
    total_height = (len(lines) - 1) * line_height
    start_y = y + 92 - total_height // 2 + size // 3
    body = "".join(
        f'<text x="265" y="{start_y + i * line_height}" fill="#28231e" font-family="PingFang TC, sans-serif" font-size="{size}" font-weight="750">{esc(line)}</text>'
        for i, line in enumerate(lines)
    )
    return f'''<g>
      <rect x="45" y="{y}" width="1260" height="166" rx="18" fill="#eee3cf" stroke="#89765d" stroke-width="3"/>
      <rect x="61" y="{y + 18}" width="170" height="130" rx="14" fill="{color}"/>
      <text x="146" y="{y + 99}" text-anchor="middle" fill="#fff7e7" font-family="PingFang TC, sans-serif" font-size="34" font-weight="900">{label}</text>
      {body}
    </g>'''


def make_svg(row: dict[str, str], art_filename: str) -> str:
    summary_lines = wrap_cjk(row["summary"], 34)
    summary_size = 31 if len(summary_lines) <= 2 else 27
    summary_step = 40 if len(summary_lines) <= 2 else 34
    summary_y = 438 if len(summary_lines) <= 2 else 423
    summary = "".join(
        f'<text x="82" y="{summary_y + i * summary_step}" fill="#f8e8bf" font-family="PingFang TC, sans-serif" font-size="{summary_size}" font-weight="750">{esc(line)}</text>'
        for i, line in enumerate(summary_lines)
    )
    title_size = 62 if len(row["title"]) <= 8 else 52
    faction_color = FACTION_COLORS[row["faction"]]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1350" height="1100" viewBox="0 0 1350 1100" role="img" aria-labelledby="title desc">
<title id="title">{esc(row['canonical_name'])}時代關卡</title>
<desc id="desc">{esc(row['summary'])}；觸發條件 {esc(row['trigger'])}；紅軍壓制 {esc(row['suppression'])}；革命反撲 {esc(row['counterattack'])}。</desc>
<defs>
  <linearGradient id="frame" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{faction_color}"/><stop offset=".3" stop-color="#25171a"/><stop offset=".72" stop-color="#090d11"/><stop offset="1" stop-color="#aa8748"/></linearGradient>
  <linearGradient id="header"><stop stop-color="#0d1117"/><stop offset=".55" stop-color="#312023"/><stop offset="1" stop-color="#0d1117"/></linearGradient>
  <pattern id="grain" width="43" height="47" patternUnits="userSpaceOnUse"><circle cx="7" cy="10" r="1" fill="#fff" opacity=".05"/><circle cx="31" cy="34" r=".9" fill="#000" opacity=".13"/></pattern>
  <clipPath id="artClip"><rect x="45" y="178" width="1260" height="320" rx="18"/></clipPath>
</defs>
<rect width="1350" height="1100" rx="48" fill="#070709"/>
<rect x="13" y="13" width="1324" height="1074" rx="40" fill="url(#frame)" stroke="#cdb887" stroke-width="5"/>
<rect x="29" y="29" width="1292" height="1042" rx="31" fill="#171111" stroke="#d0b982" stroke-width="2"/>
<path d="M43 43h1264v112H43z" fill="url(#header)"/><path d="M44 155h1262" stroke="#d8b777" stroke-width="6"/>
<rect x="61" y="66" width="132" height="66" rx="18" fill="{faction_color}" stroke="#e0c684" stroke-width="3"/>
<text x="127" y="112" text-anchor="middle" fill="#fff7df" font-family="PingFang TC, sans-serif" font-size="32" font-weight="900">{esc(row['faction'])}</text>
<text x="218" y="119" fill="#f7eedc" font-family="PingFang TC, sans-serif" font-size="{title_size}" font-weight="900" letter-spacing="2">{esc(row['title'])}</text>
<text x="1260" y="111" text-anchor="end" fill="#dec493" font-family="PingFang TC, sans-serif" font-size="24" font-weight="800">時代關卡｜達成觸發後，同時面對壓制與反撲</text>
<g clip-path="url(#artClip)"><image xlink:href="../art/{esc(art_filename)}" href="../art/{esc(art_filename)}" x="45" y="178" width="1260" height="320" preserveAspectRatio="xMidYMid slice"/><rect x="45" y="389" width="1260" height="109" fill="#080b0f" opacity=".76"/></g>
<rect x="45" y="178" width="1260" height="320" rx="18" fill="none" stroke="#d8b777" stroke-width="5"/>
{summary}
{panel(520, '觸發條件', row['trigger'], '#315b77')}
{panel(700, '紅軍壓制', row['suppression'], '#833832')}
{panel(880, '革命反撲', row['counterattack'], '#39705c')}
<rect x="13" y="13" width="1324" height="1074" rx="40" fill="url(#grain)" pointer-events="none"/>
</svg>'''


def write_progress(done: list[str], failed: dict[str, str], current: str | None) -> None:
    tmp = PROGRESS.with_suffix(".tmp")
    tmp.write_text(json.dumps({"done": done, "failed": failed, "current": current}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS)


def generate_art(provider, row: dict[str, str], path: Path) -> None:
    mechanic = (
        f" The milestone is {row['canonical_name']}. Visual concept only, never render these words: "
        f"context {row['summary']}; threshold {row['trigger']}; repression {row['suppression']}; counter-movement {row['counterattack']}. "
    )
    response = provider.generate(BASE_STYLE + SCENES[row["faction"]] + mechanic, aspect_ratio="landscape")
    if not response.get("success"):
        raise RuntimeError(response.get("error", str(response)))
    shutil.copy2(Path(response["image"]), path)
    if not valid_image(path):
        raise RuntimeError("invalid generated art")


def render(row: dict[str, str]) -> tuple[Path, Path, Path]:
    name = safe_name(row["canonical_name"])
    art = ART_DIR / f"{name}_插圖.png"
    svg = SVG_DIR / f"{name}.svg"
    png = PNG_DIR / f"{name}.png"
    preview = PREVIEW_DIR / f"{name}.png"
    svg.write_text(make_svg(row, art.name), encoding="utf-8")
    ET.parse(svg)
    subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1350,1100", "--force-device-scale-factor=1", f"--screenshot={png}", svg.as_uri()], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["sips", "-z", "220", "270", str(png), "--out", str(preview)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return svg, png, preview


def font(size: int, bold: bool = False):
    for candidate in ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc"]:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def make_contact(rows: list[dict[str, str]]) -> None:
    cols, gap, label_h = 2, 28, 44
    rows_n = math.ceil(len(rows) / cols)
    canvas = Image.new("RGB", (cols * 270 + (cols + 1) * gap, rows_n * (220 + label_h) + (rows_n + 1) * gap), "#171312")
    draw = ImageDraw.Draw(canvas)
    for i, row in enumerate(rows):
        x = gap + (i % cols) * (270 + gap)
        y = gap + (i // cols) * (220 + label_h + gap)
        path = PREVIEW_DIR / f"{safe_name(row['canonical_name'])}.png"
        with Image.open(path) as image:
            canvas.paste(image.convert("RGB"), (x, y))
        draw.text((x + 135, y + 227), f"{row['canonical_name']}", fill="#f4e4bf", font=font(21, True), anchor="ma")
    canvas.save(CONTACT)


def main() -> None:
    for directory in (ROOT, ART_DIR, SVG_DIR, PNG_DIR, PREVIEW_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    provider_cls = importlib.import_module("plugins.image_gen.openai-codex").OpenAICodexImageGenProvider
    probe = provider_cls()
    if not probe.is_available():
        raise RuntimeError("OpenAI Codex OAuth image provider unavailable")

    done = [row["canonical_name"] for row in rows if valid_image(ART_DIR / f"{safe_name(row['canonical_name'])}_插圖.png")]
    failed: dict[str, str] = {}
    pending = [row for row in rows if row["canonical_name"] not in done]
    write_progress(done, failed, "、".join(row["canonical_name"] for row in pending[:3]) or None)

    def worker(row: dict[str, str]) -> str:
        provider = provider_cls()
        path = ART_DIR / f"{safe_name(row['canonical_name'])}_插圖.png"
        generate_art(provider, row, path)
        return row["canonical_name"]

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(worker, row): row for row in pending}
        for future in as_completed(futures):
            row = futures[future]
            name = row["canonical_name"]
            try:
                future.result()
                done.append(name)
                print(f"GENERATED {len(done)}/{len(rows)} {name}", flush=True)
            except Exception as exc:
                failed[name] = str(exc)
                print(f"FAILED {name}: {exc}", flush=True)
            remaining = [item["canonical_name"] for item in pending if item["canonical_name"] not in done and item["canonical_name"] not in failed]
            write_progress(done, failed, "、".join(remaining[:3]) or None)
    if failed:
        raise RuntimeError(f"產圖失敗：{failed}")

    for index, row in enumerate(rows, 1):
        print(f"RENDER {index}/{len(rows)} {row['canonical_name']}", flush=True)
        render(row)
    write_progress([row["canonical_name"] for row in rows], {}, None)

    with MANIFEST.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["序號", "時代關卡名稱", "陣營", "簡述", "觸發條件", "紅軍壓制", "革命反撲", "卡牌張數", "插圖", "完整卡面", "270x220預覽"])
        for i, row in enumerate(rows, 1):
            name = safe_name(row["canonical_name"])
            writer.writerow([i, row["canonical_name"], row["faction"], row["summary"], row["trigger"], row["suppression"], row["counterattack"], row["copies"], f"art/{name}_插圖.png", f"png/{name}.png", f"preview-270x220/{name}.png"])
    make_contact(rows)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(ROOT), str(ZIP_PATH)], check=True)
    print(f"DONE cards={len(rows)} contact={CONTACT} zip={ZIP_PATH}", flush=True)


if __name__ == "__main__":
    main()
