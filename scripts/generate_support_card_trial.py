#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import importlib
import os
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
CSV_PATH = REPO / "data/raw/support_cards.csv"
VARIANT = os.environ.get("SUPPORT_CARD_TRIAL_VARIANT", "v1")
OUT_NAME = "天方奧援-印度南洋" if VARIANT == "v1" else f"天方奧援-印度南洋-{VARIANT}"
OUT = REPO / "docs/records/design/card-art/support-card-trials" / OUT_NAME
ART = OUT / "天方奧援_插圖.png"
SVG = OUT / "天方奧援_完整卡面.svg"
PNG = OUT / "天方奧援_完整卡面.png"
PREVIEW = OUT / "天方奧援_220x270.png"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def load_row() -> dict[str, str]:
    # CSV 有兩個同名的「區域主導者優待」欄位，必須按欄位位置讀取，
    # 不能使用 DictReader，否則第一個條件會被第二個覆蓋。
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for values in reader:
            if values[0] == "天方奧援" and values[4] == "印度、南洋":
                return {
                    "奧援卡名稱": values[0],
                    "購買費用": values[1],
                    "III級條件": values[2],
                    "III級效果": values[3],
                    "II級條件": values[4],
                    "II級效果": values[5],
                    "I級條件": values[6],
                    "I級效果": values[7],
                    "卡牌張數": values[8],
                }
    raise RuntimeError("找不到天方奧援印度、南洋版本")


def cost_items(value: str) -> list[tuple[str, str]]:
    return [(label, number) for number, label in re.findall(r"(\d+)\s*(資金|宣傳)", value)]


def cost_group(items: list[tuple[str, str]]) -> str:
    x = 145
    chunks = []
    for label, number in items:
        fill = "#ead296" if label == "資金" else "#e8c69d"
        grad = "money" if label == "資金" else "prop"
        chunks.append(f'<text x="{x}" y="10" fill="{fill}" font-family="PingFang TC, sans-serif" font-size="27" font-weight="800">{label}</text>')
        cx = x + 98
        chunks.append(f'<circle cx="{cx}" r="39" fill="url(#{grad})" stroke="#efd099" stroke-width="5" filter="url(#shadow)"/>')
        chunks.append(f'<text x="{cx}" y="14" text-anchor="middle" fill="#fff5d8" font-family="Avenir Next, sans-serif" font-size="43" font-weight="900">{number}</text>')
        x += 160
    return "".join(chunks)


def wrap_cjk(text: str, width: int = 18) -> list[str]:
    lines, current = [], ""
    for char in text.strip():
        current += char
        if len(current) >= width and char in "，。；：、！？":
            lines.append(current); current = ""
        elif len(current) >= width + 2:
            lines.append(current); current = ""
    if current:
        lines.append(current)
    return lines


def tier_panel(y: int, tier: str, condition: str, effect: str, accent: str) -> str:
    lines = wrap_cjk(effect)
    size = 38 if len(lines) <= 2 else 34
    line_height = int(size * 1.22)
    effect_svg = "".join(
        f'<text x="246" y="{y + 79 + i * line_height}" fill="#30271f" font-family="PingFang TC, sans-serif" font-size="{size}" font-weight="700">{esc(line)}</text>'
        for i, line in enumerate(lines)
    )
    return f'''<g>
      <rect x="70" y="{y}" width="960" height="166" rx="18" fill="#eadcc0" stroke="#8f7654" stroke-width="3"/>
      <rect x="88" y="{y + 18}" width="116" height="130" rx="16" fill="{accent}"/>
      <text x="146" y="{y + 83}" text-anchor="middle" fill="#fff2cf" font-family="Avenir Next, sans-serif" font-size="45" font-weight="900">{tier}</text>
      <text x="246" y="{y + 39}" fill="#765729" font-family="PingFang TC, sans-serif" font-size="25" font-weight="800">條件｜{esc(condition)}</text>
      {effect_svg}
    </g>'''


def make_svg(row: dict[str, str], tier2_condition: str, tier1_condition: str) -> str:
    title = row["奧援卡名稱"]
    effect3 = row["III級效果"]
    effect2 = row["II級效果"]
    effect1 = row["I級效果"]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1100" height="1350" viewBox="0 0 1100 1350" role="img" aria-labelledby="title desc">
<title id="title">{esc(title)}完整卡面試作</title>
<desc id="desc">購買費用 {esc(row['購買費用'])}；III、II、I 級效果依正式 CSV 排版。</desc>
<defs>
  <linearGradient id="frame" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#b7872f"/><stop offset=".35" stop-color="#102a2d"/><stop offset=".72" stop-color="#071516"/><stop offset="1" stop-color="#3c8790"/></linearGradient>
  <linearGradient id="header"><stop stop-color="#111015"/><stop offset=".68" stop-color="#123235"/><stop offset="1" stop-color="#111015"/></linearGradient>
  <radialGradient id="prop" cx="35%" cy="30%" r="75%"><stop stop-color="#d37656"/><stop offset="1" stop-color="#91362b"/></radialGradient>
  <radialGradient id="money" cx="35%" cy="30%" r="75%"><stop stop-color="#d7ad54"/><stop offset="1" stop-color="#7b591b"/></radialGradient>
  <pattern id="grain" width="43" height="47" patternUnits="userSpaceOnUse"><circle cx="7" cy="10" r="1" fill="#fff" opacity=".05"/><circle cx="31" cy="34" r=".9" fill="#000" opacity=".13"/></pattern>
  <filter id="shadow" x="-30%" y="-30%" width="160%" height="170%"><feGaussianBlur in="SourceAlpha" stdDeviation="7"/><feOffset dy="7"/><feColorMatrix values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .58 0"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <clipPath id="artClip"><rect x="52" y="216" width="996" height="405" rx="16"/></clipPath>
</defs>
<rect width="1100" height="1350" rx="50" fill="#080503"/>
<rect x="13" y="13" width="1074" height="1324" rx="42" fill="url(#frame)" stroke="#c7ae78" stroke-width="5"/>
<rect x="31" y="31" width="1038" height="1288" rx="32" fill="#18100b" stroke="#d0b982" stroke-width="2"/>
<path d="M45 45h1010v150H45z" fill="url(#header)"/><path d="M46 194h1008" stroke="#a9e2dc" stroke-width="6"/>
<g transform="translate(102 119)"><circle r="38" fill="#123235" stroke="#a9e2dc" stroke-width="5"/><path d="M-22 8Q0-24 22 8Q0 33-22 8Z" fill="none" stroke="#a9e2dc" stroke-width="6"/><circle cy="8" r="7" fill="#d3aa55"/></g>
<text x="158" y="142" fill="#f6ecd8" font-family="PingFang TC, sans-serif" font-size="65" font-weight="800" letter-spacing="3">{esc(title)}</text>
<g transform="translate(560 120)"><text x="0" y="10" fill="#e6d4ad" font-family="PingFang TC, sans-serif" font-size="27" font-weight="800">購買費用</text>{cost_group(cost_items(row['購買費用']))}</g>
<g clip-path="url(#artClip)"><image xlink:href="天方奧援_插圖.png" href="天方奧援_插圖.png" x="52" y="216" width="996" height="405" preserveAspectRatio="xMidYMid slice"/><rect x="52" y="553" width="996" height="68" fill="#071516" opacity=".75"/></g>
<rect x="52" y="216" width="996" height="405" rx="16" fill="none" stroke="#a9e2dc" stroke-width="6"/>
<text x="84" y="597" fill="#f2dca8" font-family="PingFang TC, sans-serif" font-size="25" font-weight="700" letter-spacing="2">遠方援助化作隱密施壓，迫使鄰近對手棄置手牌</text>
{tier_panel(644, 'III', row['III級條件'], effect3, '#8f6425')}
{tier_panel(820, 'II', tier2_condition, effect2, '#236d72')}
{tier_panel(996, 'I', tier1_condition, effect1, '#584c3f')}
<rect x="70" y="1182" width="960" height="104" rx="18" fill="#0d2022" stroke="#aa956c" stroke-width="3"/>
<text x="102" y="1248" fill="#dfc99a" font-family="PingFang TC, sans-serif" font-size="29" font-weight="800">奧援卡</text>
<text x="938" y="1248" text-anchor="end" fill="#b9deda" font-family="PingFang TC, sans-serif" font-size="27" font-weight="700">卡牌張數 {esc(row['卡牌張數'])}</text>
<rect x="13" y="13" width="1074" height="1324" rx="42" fill="url(#grain)" pointer-events="none"/>
</svg>'''


def generate_art() -> None:
    provider_cls = importlib.import_module("plugins.image_gen.openai-codex").OpenAICodexImageGenProvider
    provider = provider_cls()
    if not provider.is_available():
        raise RuntimeError("OpenAI Codex OAuth image provider unavailable")
    if VARIANT == "v3":
        prompt = '''Create a premium TEXT-FREE landscape illustration for a historical political-strategy board-game support card concept called “Aid from the Western Lands”. The setting must read immediately and unmistakably as a fictional 1920s–1940s WEST ASIAN / MIDDLE EASTERN caravan and telegraph hub, treated with historical dignity rather than fantasy or stereotype. Show a sunlit sandstone caravanserai courtyard with horseshoe and pointed arches, carved wooden mashrabiya screens, restrained turquoise-and-cobalt geometric tilework, woven kilim textiles, brass astrolabe and compass, telegraph wires, date palms, distant desert caravan silhouettes, and a warm ochre city skyline. Period West Asian merchants, couriers and organizers in varied dignified urban clothing gather around a low intelligence table. At the center, an envoy's hand deliberately pulls TWO sealed BLANK dossiers from a nearby rival's spread, while luminous route threads connect the courtyard to distant desert and port networks—clearly visualizing remote regional support, one-step proximity, selective pressure, and two discarded hand cards. Strong shallow-wide composition: regional architecture and textiles visible across the entire frame, two blank dossiers and hands in the center, caravans and telegraph network behind. Rich lapis blue, turquoise, saffron, copper, sand and deep indigo; cinematic hand-painted gouache with refined Persian miniature-inspired spatial layering and 1930s travel-poster geometry, realistic anatomy, professional tabletop key art, opaque full-bleed background. No Arabian Nights fantasy, no belly dancers, no genies, no exotic caricature, no real leader, no national flag, no party emblem, no explicit religious icon, no modern brand, no weapon, no gore. ABSOLUTELY NO readable text, Arabic script, letters, numbers, map labels, logos, watermark, frame, border, UI, title, cost token, resource icon, or typography anywhere.'''
    elif VARIANT == "v2":
        prompt = '''Create a premium TEXT-FREE landscape-friendly illustration for a historical political-strategy board-game support card concept called “Aid from the Western Lands”. Visualize the mechanic directly: distant support exerts pressure on a nearby rival, and stronger regional influence selectively removes two items from that rival's hand. Use a dramatic near-overhead composition of a nocturnal intelligence table in a fictional 1920s–1940s crossroads city. At center, two sealed BLANK dossiers are being pulled away from an adjacent rival's spread toward a remote network, guided by a brass divider and luminous route threads crossing an unmarked map. Surrounding objects: blank envelopes, telegraph cable, compass, wax seals without symbols, distant arcade and caravan silhouettes visible through an open courtyard. No dominant portrait; make the hands, two dossiers, proximity, and converging routes the unmistakable focal motif. Visually distinct from a realistic envoy scene: elegant graphic poster composition, bold geometric shadows, crisp silhouettes, layered gouache and linocut texture, midnight indigo, emerald, saffron gold, silver-blue moonlight, cinematic contrast, professional tabletop key art, realistic hands, opaque full-bleed background, designed to survive a shallow wide crop. No real leader, party emblem, national flag, identifiable religion, stereotype, modern brand, weapon, or gore. ABSOLUTELY NO readable text, letters, numbers, map labels, symbols, logos, watermark, frame, border, UI, title, cost token, resource icon, or typography anywhere.'''
    else:
        prompt = '''Create a premium TEXT-FREE portrait illustration for a historical political-strategy board-game support card called “Aid from the Western Lands”. The mechanic: a distant network quietly pressures a nearby rival, forcing cards from that rival's hand to be discarded; stronger regional influence lets the acting player choose more of what is lost. Show a fictional 1920s–1940s cosmopolitan caravan-and-port intelligence network connecting West and East: a composed envoy in the foreground, sealed blank envelopes and unmarked cards being selectively removed from a rival's hand, brass compass, telegraph wires, distant domes and harbor silhouettes. Convey discreet foreign support, proximity, surveillance, selective disruption, and escalating leverage. Deep indigo, oxidized turquoise, warm ochre, brass and parchment; cinematic hand-painted gouache, historical board-game key art, restrained screen-print texture, realistic anatomy and hands, one strong focal silhouette, opaque full-bleed background, central composition suitable for a shallow wide crop. No real political leader, party emblem, national flag, identifiable religion, stereotype, modern brand, weapon, or gore. ABSOLUTELY NO readable text, letters, numbers, symbols, logos, watermark, frame, border, UI, title, cost token, resource icon, or typography anywhere.'''
    result = provider.generate(prompt, aspect_ratio="landscape" if VARIANT in {"v2", "v3"} else "portrait")
    if not result.get("success"):
        raise RuntimeError(result.get("error", str(result)))
    shutil.copy2(Path(result["image"]), ART)
    with Image.open(ART) as image:
        image.verify()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    row = load_row()
    tier2_condition, tier1_condition = row['II級條件'], row['I級條件']
    if not ART.exists() or ART.stat().st_size < 10000:
        generate_art()
    SVG.write_text(make_svg(row, tier2_condition, tier1_condition), encoding="utf-8")
    subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1100,1350", "--force-device-scale-factor=1", f"--screenshot={PNG}", SVG.as_uri()], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["sips", "-z", "270", "220", str(PNG), "--out", str(PREVIEW)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"DONE {OUT}")


if __name__ == "__main__":
    main()
