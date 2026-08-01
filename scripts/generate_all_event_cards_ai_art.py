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
ROOT = REPO / "docs/records/design/card-art/all-event-cards-ai-review"
ART_DIR = ROOT / "art"
SVG_DIR = ROOT / "svg"
PNG_DIR = ROOT / "png"
PREVIEW_DIR = ROOT / "preview-270x220"
PROGRESS = ROOT / "ai-generation-progress.json"
MANIFEST = ROOT / "manifest.csv"
CONTACT = ROOT / "全部事件卡_總覽.png"
ZIP_PATH = REPO / "docs/records/design/card-art/全部事件卡_AI插圖_未提交檢查包.zip"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
EXISTING_ART = REPO / "docs/records/design/card-art/event-card-trials/全國人大召開-v1/全國人大召開_插圖.png"

BASE_STYLE = (
    "Premium TEXT-FREE landscape key art for a historical political-strategy board-game event. "
    "Fictional East Asian authoritarian setting, cinematic historical gouache, restrained screen-print texture, "
    "strong wide composition designed for a shallow crop, deep crimson, charcoal, muted brass, cold stone and paper white, "
    "realistic anatomy and hands, professional tabletop illustration, opaque full-bleed background. "
    "No real leader, real national flag, party emblem, star, hammer-and-sickle, readable placard, letters, numbers, "
    "logos, watermark, frame, border, UI, title, graphic gore, or typography anywhere. "
)

SCENES = {
    "歲月靜好": "A deceptively calm prosperous city evening: families strolling, warm apartment windows, quiet tram and tree-lined promenade, while barely visible surveillance shadows and distant checkpoints suggest fragile calm. No overt conflict; serene but uneasy stillness.",
    "全國人大召開": "A vast monumental assembly hall prepared for a grand political congress: rows of anonymous officials beneath towering columns and ceremonial red drapery without symbols; below, local officials erect barricades and pressure peaceful petitioners carrying completely blank papers while civic organizers quietly help one another.",
    "香港抗暴之戰": "A dense subtropical harbor city of steep streets and towers at night, immense peaceful crowds flowing with blank umbrellas and blank papers, improvised barricades, volunteers passing supplies, harsh police searchlights and rain; solidarity and determined civic resistance, no identifiable skyline logo.",
    "重大災難": "After a massive earthquake and flood in a fictional inland city, ordinary people form rescue chains through rubble and water while officials conceal a damaged facility behind screens; a lone whistleblower holds a completely blank notebook, grief turning into courage, no corpses.",
    "藏印邊境軍事對峙": "High frozen Himalayan frontier with two distant military patrols facing across a rocky pass, tense but no combat; far below, civilian organizers quietly establish community nodes and move couriers while authorities are distracted, prayer flags must be plain strips without symbols or text.",
    "貿易戰加劇": "A vast container port and industrial financial district under economic pressure: idle cranes, sealed blank cargo, tariff barriers represented by towering customs gates, merchants and workers regrouping while overseas allies extend a lifeline through ships and exchanged blank dossiers; no currency marks.",
    "東突厥集中營": "A bleak Central Asian desert-edge detention compound with watchtowers and fences in the distance; in foreground, escaped witnesses protected by villagers and organizers, one survivor carrying blank testimony pages, turquoise architecture and dry mountains, dignity and urgency, no graphic violence.",
    "北京政爭": "A monumental northern imperial capital at sleepless midnight: anonymous rival elites confer behind lit palace windows while university-age civic organizers meet discreetly in a courtyard and exchange blank folders; layered intrigue, friendship overtures and hidden alliances, no identifiable real landmark.",
    "紅軍權貴出逃": "A disgraced authoritarian elite family escaping at night through a guarded airport and border rail terminal with suitcases and blank dossiers, aided by covert escorts and decoy vehicles; intelligence networks unravel behind them, tense movement across several routes, no luxury-brand logos.",
    "烏魯木齊七五事件": "A Central Asian boulevard after unrest, shuttered bazaars, severed telephone and network cables, smoke haze without gore; local witnesses and foreign journalists establish a covert communications link using cameras with blank screens and paper maps without writing, seven-city cultural atmosphere.",
    "上海合作組織": "A cold northern diplomatic-security summit represented without symbols: anonymous officials around a circular table with blank folders, behind them a large relief map with no labels and long operational arrows, security units extending their reach toward distant northern towns and civic networks.",
    "一帶一路 南洋": "A humid Southeast Asian port with container cranes, palms, shophouses and a new monumental rail viaduct; authoritarian investors and local officials exchange blank contracts while covert security organizers establish a distant node, investment grandeur masking political expansion.",
    "一帶一路 天方": "A West Asian desert trade hub with sandstone arches, tiled courtyards, oil port and newly built rail corridor; authoritarian investors and local officials exchange blank contracts while covert personnel establish a distant organization node, investment masking political expansion.",
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
    rows = []
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for values in reader:
            if not values or not values[0]:
                break
            if values[0] == "時代關卡名稱":
                break
            rows.append({
                "name": values[0].strip(), "summary": values[1].strip(),
                "mission": values[2].strip(), "success": values[3].strip(),
                "failure": values[4].strip(), "copies": values[5].strip(),
            })
    if len(rows) != 13:
        raise RuntimeError(f"預期 13 種事件卡，實得 {len(rows)}")
    return rows


def wrap_cjk(text: str, width: int) -> list[str]:
    if not text:
        return ["無"]
    lines, current = [], ""
    for char in text.strip():
        current += char
        if len(current) >= width:
            lines.append(current.strip()); current = ""
    if current.strip():
        lines.append(current.strip())
    return lines


def panel(y: int, label: str, text: str, color: str) -> str:
    # 文字區從 x=265 到 x=1280，44pt 中文字每行以 22 字為安全上限，
    # 避免 270×220 預覽中右側貼邊或被裁切。
    lines = wrap_cjk(text, 22)
    if len(lines) <= 2:
        size, line_height, start_y = 44, 52, y + (65 if len(lines) == 2 else 101)
    else:
        size, line_height, start_y = 34, 40, y + 45
    body = "".join(
        f'<text x="265" y="{start_y + i * line_height}" fill="#2b241d" font-family="PingFang TC, sans-serif" font-size="{size}" font-weight="750">{esc(line)}</text>'
        for i, line in enumerate(lines)
    )
    return f'''<g>
      <rect x="45" y="{y}" width="1260" height="166" rx="18" fill="#eadfc8" stroke="#8d795c" stroke-width="3"/>
      <rect x="61" y="{y + 18}" width="170" height="130" rx="14" fill="{color}"/>
      <text x="146" y="{y + 99}" text-anchor="middle" fill="#fff5df" font-family="PingFang TC, sans-serif" font-size="34" font-weight="900">{label}</text>
      {body}
    </g>'''


def make_svg(row: dict[str, str], art_filename: str) -> str:
    summary_lines = wrap_cjk(row["summary"], 34)
    summary_size = 31 if len(summary_lines) <= 2 else 27
    summary_height = 40 if len(summary_lines) <= 2 else 34
    summary_y = 438 if len(summary_lines) <= 2 else 423
    summary = "".join(
        f'<text x="82" y="{summary_y + i * summary_height}" fill="#f7e5b8" font-family="PingFang TC, sans-serif" font-size="{summary_size}" font-weight="750">{esc(line)}</text>'
        for i, line in enumerate(summary_lines)
    )
    title_size = 70 if len(row["name"]) <= 8 else 62
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1350" height="1100" viewBox="0 0 1350 1100" role="img" aria-labelledby="title desc">
<title id="title">{esc(row['name'])}事件卡</title>
<desc id="desc">{esc(row['summary'])}；任務條件 {esc(row['mission'])}；成功獎勵 {esc(row['success'])}；失敗懲罰 {esc(row['failure'])}。</desc>
<defs>
  <linearGradient id="frame" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#9d342e"/><stop offset=".3" stop-color="#281416"/><stop offset=".72" stop-color="#090b0f"/><stop offset="1" stop-color="#a98442"/></linearGradient>
  <linearGradient id="header"><stop stop-color="#0d1016"/><stop offset=".55" stop-color="#321719"/><stop offset="1" stop-color="#0d1016"/></linearGradient>
  <pattern id="grain" width="43" height="47" patternUnits="userSpaceOnUse"><circle cx="7" cy="10" r="1" fill="#fff" opacity=".05"/><circle cx="31" cy="34" r=".9" fill="#000" opacity=".13"/></pattern>
  <clipPath id="artClip"><rect x="45" y="178" width="1260" height="320" rx="18"/></clipPath>
</defs>
<rect width="1350" height="1100" rx="48" fill="#070506"/>
<rect x="13" y="13" width="1324" height="1074" rx="40" fill="url(#frame)" stroke="#c9b081" stroke-width="5"/>
<rect x="29" y="29" width="1292" height="1042" rx="31" fill="#170f0e" stroke="#d0b982" stroke-width="2"/>
<path d="M43 43h1264v112H43z" fill="url(#header)"/><path d="M44 155h1262" stroke="#d8b777" stroke-width="6"/>
<g transform="translate(94 99)"><circle r="34" fill="#4a1d1d" stroke="#e0bd78" stroke-width="5"/><path d="M-17-13h34v26h-34zM-28 0h56M0-25v50" fill="none" stroke="#e0bd78" stroke-width="5"/></g>
<text x="147" y="122" fill="#f7eedc" font-family="PingFang TC, sans-serif" font-size="{title_size}" font-weight="900" letter-spacing="2">{esc(row['name'])}</text>
<text x="1260" y="111" text-anchor="end" fill="#dec493" font-family="PingFang TC, sans-serif" font-size="25" font-weight="800">回合事件｜完成任務以獲得獎勵，否則承受懲罰</text>
<g clip-path="url(#artClip)"><image xlink:href="../art/{esc(art_filename)}" href="../art/{esc(art_filename)}" x="45" y="178" width="1260" height="320" preserveAspectRatio="xMidYMid slice"/><rect x="45" y="389" width="1260" height="109" fill="#080b0f" opacity=".76"/></g>
<rect x="45" y="178" width="1260" height="320" rx="18" fill="none" stroke="#d8b777" stroke-width="5"/>
{summary}
{panel(520, '任務條件', row['mission'], '#244a68')}
{panel(700, '成功獎勵', row['success'], '#2c6656')}
{panel(880, '失敗懲罰', row['failure'], '#7f302d')}
<rect x="13" y="13" width="1324" height="1074" rx="40" fill="url(#grain)" pointer-events="none"/>
</svg>'''


def write_progress(done: list[str], failed: dict[str, str], current: str | None) -> None:
    tmp = PROGRESS.with_suffix(".tmp")
    tmp.write_text(json.dumps({"done": done, "failed": failed, "current": current}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS)


def generate_art(provider, row: dict[str, str], path: Path) -> None:
    scene = SCENES[row["name"]]
    mechanic = f" Visually support this event summary and mechanic without text: {row['summary']}; mission: {row['mission']}; success: {row['success']}; failure: {row['failure']}."
    response = provider.generate(BASE_STYLE + scene + mechanic, aspect_ratio="landscape")
    if not response.get("success"):
        raise RuntimeError(response.get("error", str(response)))
    shutil.copy2(Path(response["image"]), path)
    if not valid_image(path):
        raise RuntimeError("invalid generated art")


def render(row: dict[str, str]) -> tuple[Path, Path, Path]:
    name = safe_name(row["name"])
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
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc" if bold else "/System/Library/Fonts/STHeiti Light.ttc",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def make_contact(rows: list[dict[str, str]]) -> None:
    cols, gap, label_h = 3, 24, 42
    rows_n = math.ceil(len(rows) / cols)
    canvas = Image.new("RGB", (cols * 270 + (cols + 1) * gap, rows_n * (220 + label_h) + (rows_n + 1) * gap), "#171312")
    draw = ImageDraw.Draw(canvas)
    for i, row in enumerate(rows):
        x = gap + (i % cols) * (270 + gap)
        y = gap + (i // cols) * (220 + label_h + gap)
        with Image.open(PREVIEW_DIR / f"{safe_name(row['name'])}.png") as image:
            canvas.paste(image.convert("RGB"), (x, y))
        draw.text((x + 135, y + 226), f"{i + 1:02d}  {row['name']}", fill="#f4e4bf", font=font(22, True), anchor="ma")
    canvas.save(CONTACT)


def main() -> None:
    for directory in (ROOT, ART_DIR, SVG_DIR, PNG_DIR, PREVIEW_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    if set(SCENES) != {row["name"] for row in rows}:
        raise RuntimeError("SCENES 與 CSV 事件卡名稱不一致")

    existing_target = ART_DIR / "全國人大召開_插圖.png"
    if not valid_image(existing_target) and valid_image(EXISTING_ART):
        shutil.copy2(EXISTING_ART, existing_target)

    provider_cls = importlib.import_module("plugins.image_gen.openai-codex").OpenAICodexImageGenProvider
    probe = provider_cls()
    if not probe.is_available():
        raise RuntimeError("OpenAI Codex OAuth image provider unavailable")

    done = [row["name"] for row in rows if valid_image(ART_DIR / f"{safe_name(row['name'])}_插圖.png")]
    failed: dict[str, str] = {}
    pending = [row for row in rows if row["name"] not in done]
    write_progress(done, failed, "、".join(row["name"] for row in pending[:3]) or None)

    def worker(row: dict[str, str]) -> str:
        provider = provider_cls()
        art = ART_DIR / f"{safe_name(row['name'])}_插圖.png"
        generate_art(provider, row, art)
        return row["name"]

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(worker, row): row for row in pending}
        for future in as_completed(futures):
            row = futures[future]
            name = row["name"]
            try:
                future.result()
                done.append(name)
                print(f"GENERATED {len(done)}/{len(rows)} {name}", flush=True)
            except Exception as exc:
                failed[name] = str(exc)
                print(f"FAILED {name}: {exc}", flush=True)
            remaining = [item["name"] for item in pending if item["name"] not in done and item["name"] not in failed]
            write_progress(done, failed, "、".join(remaining[:3]) or None)

    if failed:
        raise RuntimeError(f"產圖失敗：{failed}")

    for index, row in enumerate(rows, 1):
        print(f"RENDER {index}/{len(rows)} {row['name']}", flush=True)
        render(row)
    write_progress([row["name"] for row in rows], {}, None)

    with MANIFEST.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["序號", "事件卡名稱", "事件簡述", "任務條件", "成功獎勵", "失敗懲罰", "卡牌張數", "插圖", "完整卡面", "270x220預覽"])
        for i, row in enumerate(rows, 1):
            name = safe_name(row["name"])
            writer.writerow([i, row["name"], row["summary"], row["mission"], row["success"], row["failure"], row["copies"], f"art/{name}_插圖.png", f"png/{name}.png", f"preview-270x220/{name}.png"])
    make_contact(rows)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(ROOT), str(ZIP_PATH)], check=True)
    print(f"DONE cards={len(rows)} contact={CONTACT} zip={ZIP_PATH}", flush=True)


if __name__ == "__main__":
    main()
