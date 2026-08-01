#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import importlib
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
CSV_PATH = REPO / "data/raw/event_and_era_cards.csv"
OUT = REPO / "docs/records/design/card-art/event-card-trials/全國人大召開-v1"
ART = OUT / "全國人大召開_插圖.png"
SVG = OUT / "全國人大召開_完整卡面.svg"
PNG = OUT / "全國人大召開_完整卡面.png"
PREVIEW = OUT / "全國人大召開_270x220.png"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def load_row() -> dict[str, str]:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for values in reader:
            if values and values[0] == "全國人大召開":
                return {
                    "name": values[0], "summary": values[1], "mission": values[2],
                    "success": values[3], "failure": values[4], "copies": values[5],
                }
    raise RuntimeError("找不到事件卡：全國人大召開")


def valid_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        return path.stat().st_size > 10000
    except Exception:
        return False


def wrap_cjk(text: str, width: int) -> list[str]:
    lines, current = [], ""
    for char in text.strip():
        current += char
        if len(current) >= width and char in "，。；：、！？]］":
            lines.append(current); current = ""
        elif len(current) >= width + 2:
            lines.append(current); current = ""
    if current:
        lines.append(current)
    return lines


def panel(y: int, label: str, text: str, color: str) -> str:
    lines = wrap_cjk(text, 25)
    size = 44 if len(lines) <= 2 else 38
    line_height = int(size * 1.18)
    start_y = y + 65 if len(lines) <= 2 else y + 50
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


def make_svg(row: dict[str, str]) -> str:
    summary_lines = wrap_cjk(row["summary"], 34)
    summary = "".join(
        f'<text x="82" y="{438 + i * 40}" fill="#f7e5b8" font-family="PingFang TC, sans-serif" font-size="31" font-weight="750">{esc(line)}</text>'
        for i, line in enumerate(summary_lines)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1350" height="1100" viewBox="0 0 1350 1100" role="img" aria-labelledby="title desc">
<title id="title">{esc(row['name'])}事件卡試作</title>
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
<text x="147" y="122" fill="#f7eedc" font-family="PingFang TC, sans-serif" font-size="70" font-weight="900" letter-spacing="3">{esc(row['name'])}</text>
<text x="1260" y="111" text-anchor="end" fill="#dec493" font-family="PingFang TC, sans-serif" font-size="25" font-weight="800">回合事件｜完成任務以獲得獎勵，否則承受懲罰</text>
<g clip-path="url(#artClip)"><image xlink:href="全國人大召開_插圖.png" href="全國人大召開_插圖.png" x="45" y="178" width="1260" height="320" preserveAspectRatio="xMidYMid slice"/><rect x="45" y="389" width="1260" height="109" fill="#080b0f" opacity=".76"/></g>
<rect x="45" y="178" width="1260" height="320" rx="18" fill="none" stroke="#d8b777" stroke-width="5"/>
{summary}
{panel(520, '任務條件', row['mission'], '#244a68')}
{panel(700, '成功獎勵', row['success'], '#2c6656')}
{panel(880, '失敗懲罰', row['failure'], '#7f302d')}
<rect x="13" y="13" width="1324" height="1074" rx="40" fill="url(#grain)" pointer-events="none"/>
</svg>'''


def generate_art() -> None:
    provider_cls = importlib.import_module("plugins.image_gen.openai-codex").OpenAICodexImageGenProvider
    provider = provider_cls()
    if not provider.is_available():
        raise RuntimeError("OpenAI Codex OAuth image provider unavailable")
    prompt = '''Create premium TEXT-FREE landscape key art for a historical political-strategy board-game event called “National Assembly Convened”. Fictional East Asian authoritarian state inspired by the 1920s–1940s and modern monumental politics, without depicting any real country, leader or party. Show a vast monumental assembly hall prepared for a grand political congress: rows of anonymous officials in dark suits entering beneath towering columns, harsh searchlights and ceremonial red drapery with absolutely no symbols. In the foreground and side streets, local officials erect temporary barricades and suppress a peaceful group of petitioners carrying completely blank papers; distant civic organizers quietly help one another and awaken to resistance. Translate the mechanic into composition: official pressure above, special faction action and civilian awakening below, one vulnerable community node threatened inside the city. Deep crimson, charcoal, cold marble, muted brass and paper white; cinematic historical gouache, strong wide composition, restrained screen-print texture, realistic anatomy and hands, professional tabletop key art, opaque full-bleed background. No real leader, national flag, party emblem, star, hammer-and-sickle, readable placard, letters, numbers, logos, watermark, frame, border, UI, title, weapon or gore. ABSOLUTELY NO typography anywhere.'''
    response = provider.generate(prompt, aspect_ratio="landscape")
    if not response.get("success"):
        raise RuntimeError(response.get("error", str(response)))
    shutil.copy2(Path(response["image"]), ART)
    if not valid_image(ART):
        raise RuntimeError("invalid generated art")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    row = load_row()
    if not valid_image(ART):
        generate_art()
    SVG.write_text(make_svg(row), encoding="utf-8")
    ET.parse(SVG)
    subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1350,1100", "--force-device-scale-factor=1", f"--screenshot={PNG}", SVG.as_uri()], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["sips", "-z", "220", "270", str(PNG), "--out", str(PREVIEW)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"DONE {OUT}")


if __name__ == "__main__":
    main()
