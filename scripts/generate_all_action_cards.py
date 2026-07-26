#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import html
import math
import os
import random
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data/raw/action_cards.csv"
OUT = Path(os.environ.get(
    "ACTION_CARD_ART_OUT",
    ROOT / "docs/records/design/card-art/all-action-cards",
))
ART_DIR = OUT / "art"
ART_COMPOSED_DIR = OUT / "art-composed"
SVG_DIR = OUT / "svg"
PNG_DIR = OUT / "png"
PREVIEW_DIR = OUT / "preview-220x270"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

PALETTES = {
    "灰": ("#18202a", "#758295", "#d8dee8"),
    "銅": ("#21160d", "#a76831", "#efc277"),
    "紫": ("#1d1027", "#7e4ba1", "#d5b2ea"),
    "青": ("#0b2024", "#318b98", "#9ddde2"),
    "藍": ("#0d1729", "#346db0", "#acd0ff"),
    "綠": ("#0c2018", "#3d8a61", "#a8dfbf"),
    "棕": ("#21160e", "#745032", "#e0bd83"),
    "橘": ("#29150b", "#b65c25", "#ffc084"),
    "紅": ("#280d0d", "#a53631", "#f2a09a"),
}

TYPE_ICON = {
    "宣傳": "megaphone", "資金": "coins", "混亂": "crack", "交通": "arrows",
    "指揮": "map", "間諜": "eye", "組織": "network", "整肅": "papers", "武裝": "shield",
}

SPECIAL = {
    "追隨者": "followers", "思想家": "book", "合作談判": "handshake", "高效行動": "filter",
    "模仿戰術": "mirror", "乘勝追擊": "return", "擴大戰果": "expand", "誘導虛耗": "decoy",
    "點燃熱情": "flame", "樹立信心": "rise", "網羅人才": "talent", "凝聚共識": "converge",
    "思想建設": "booknet", "派遣間諜": "dispatch", "內應間諜": "inside", "情報網": "networkeye",
    "離間": "split", "走漏風聲": "leak", "地下黨": "tunnel", "爆料黑幕": "spotlight",
    "輿論丕變": "swirl", "行動預告": "calendar", "企業人脈": "factorylink", "產業滲透": "factoryblock",
    "企畫遊說": "pitch", "行動募資": "fundraise",
}


def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def parse_resource(value: str):
    value = (value or "").strip()
    if not value or value in {"無", "0"}:
        return []
    result = []
    for part in value.replace("＋", "+").split("+"):
        part = part.strip()
        for label in ("資金", "宣傳"):
            if part.startswith(label):
                number = part[len(label):].strip() or "0"
                result.append((label, number))
    return result


def wrap_cjk(text: str, width: int):
    text = (text or "").strip()
    lines, current = [], ""
    punctuation = "，。；：、！？）】」』"
    for char in text:
        current += char
        if len(current) >= width and char in punctuation:
            lines.append(current)
            current = ""
        elif len(current) >= width + 2:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines or ["無效果。"]


def person(x, y, s, color="#111820", opacity=1.0):
    return f'''<g transform="translate({x} {y}) scale({s})" opacity="{opacity}">
      <circle cx="0" cy="-47" r="23" fill="{color}"/>
      <path d="M-34-12 Q0-34 34-12 L48 82 L-48 82 Z" fill="{color}"/>
      <path d="M-18 80 L-31 145 M18 80 L31 145" stroke="{color}" stroke-width="22" stroke-linecap="round"/>
    </g>'''


def icon(kind, accent, light):
    if kind in {"network", "talent", "converge", "booknet", "networkeye"}:
        nodes = [(80,260),(260,120),(470,245),(690,110),(890,260),(330,385),(690,390)]
        lines = ''.join(f'<path d="M{nodes[i][0]} {nodes[i][1]} L{nodes[j][0]} {nodes[j][1]}"/>' for i,j in [(0,1),(1,2),(2,3),(3,4),(2,5),(2,6),(5,6)])
        circles = ''.join(f'<circle cx="{x}" cy="{y}" r="{28 if k==2 else 18}"/>' for k,(x,y) in enumerate(nodes))
        return f'<g fill="none" stroke="{light}" stroke-width="10" opacity=".78">{lines}{circles}</g>'
    if kind in {"megaphone", "spotlight"}:
        return f'<g transform="translate(360 125)" fill="none" stroke="{light}" stroke-width="18"><path d="M30 120 L310 25 L310 255 L30 165 Z" fill="{accent}" opacity=".48"/><path d="M45 160 L5 305 L100 325 L145 180"/><path d="M340 45 L470-20 M350 140 L520 140 M340 235 L470 300"/></g>'
    if kind in {"coins", "pitch", "fundraise"}:
        return f'<g transform="translate(235 105)" stroke="{light}" stroke-width="12" fill="{accent}" opacity=".85"><ellipse cx="110" cy="255" rx="105" ry="35"/><path d="M5 105v150c0 48 210 48 210 0V105"/><ellipse cx="110" cy="105" rx="105" ry="35"/><ellipse cx="430" cy="255" rx="105" ry="35"/><path d="M325 165v90c0 48 210 48 210 0v-90"/><ellipse cx="430" cy="165" rx="105" ry="35"/></g>'
    if kind in {"arrows", "return", "expand", "rise"}:
        return f'<g fill="none" stroke="{light}" stroke-width="24" stroke-linecap="round" stroke-linejoin="round"><path d="M100 360 C280 90 540 430 860 120"/><path d="M760 100 L880 100 L870 220"/><path d="M160 430 C400 250 650 520 930 290" opacity=".55"/></g>'
    if kind in {"map", "calendar"}:
        return f'<g transform="translate(205 80)" fill="none" stroke="{light}" stroke-width="13"><path d="M0 70 L205 0 L420 75 L625 5 V345 L420 415 L205 340 L0 410 Z" fill="{accent}" opacity=".32"/><path d="M205 0V340 M420 75V415"/><path d="M65 300 C230 120 380 350 565 120" stroke-dasharray="22 18"/><circle cx="65" cy="300" r="24" fill="{light}"/><circle cx="565" cy="120" r="24" fill="{light}"/></g>'
    if kind in {"eye", "inside", "dispatch"}:
        return f'<g transform="translate(175 105)" fill="none" stroke="{light}" stroke-width="18"><path d="M0 190 Q350-100 700 190 Q350 480 0 190Z" fill="{accent}" opacity=".32"/><circle cx="350" cy="190" r="105"/><circle cx="350" cy="190" r="42" fill="{light}"/></g>'
    if kind in {"papers", "leak", "filter"}:
        return f'<g transform="translate(260 50)" stroke="{light}" stroke-width="11"><path d="M0 70 L420 0 L500 370 L80 440 Z" fill="#e7ddca" opacity=".86"/><path d="M80 145 L390 90 M95 215 L405 160 M110 285 L370 240"/><path d="M460 70 L650 35 L705 310 L520 355" fill="{accent}" opacity=".62"/></g>'
    if kind in {"shield"}:
        return f'<g transform="translate(310 35)"><path d="M240 0 L455 80 L420 300 Q360 430 240 485 Q120 430 60 300 L25 80 Z" fill="{accent}" stroke="{light}" stroke-width="16"/><path d="M240 78V390 M95 190H385" stroke="{light}" stroke-width="22"/></g>'
    if kind in {"handshake"}:
        return f'<g transform="translate(100 145)" fill="{accent}" stroke="{light}" stroke-width="13"><path d="M0 90 L245 15 L390 125 L285 245 L120 190 Z"/><path d="M800 90 L555 15 L410 125 L515 245 L680 190 Z"/><path d="M285 245 L360 315 L520 175 M515 245 L440 315 L280 175" fill="none"/></g>'
    if kind in {"book", "booknet"}:
        return f'<g transform="translate(205 100)" fill="{accent}" stroke="{light}" stroke-width="15"><path d="M0 30 Q185-20 335 90 V395 Q175 290 0 345 Z"/><path d="M670 30 Q485-20 335 90 V395 Q495 290 670 345 Z"/><path d="M335 90V395"/></g>'
    if kind in {"flame"}:
        return f'<path d="M520 475 C330 380 380 210 505 85 C490 230 610 210 620 40 C770 230 775 405 590 485 C610 355 520 340 520 475Z" fill="{accent}" stroke="{light}" stroke-width="15"/>'
    if kind in {"mirror"}:
        return f'<g stroke="{light}" stroke-width="13" fill="{accent}" opacity=".8"><path d="M500 35 L610 35 L610 485 L500 485 Z" fill="#b9d7de" opacity=".42"/>{person(335,210,1.15,accent)}{person(770,210,1.15,accent)}<path d="M555 45V475"/></g>'
    if kind in {"followers"}:
        return person(360,250,1.1,accent,.85)+person(570,205,1.35,light,.95)+person(760,275,.95,accent,.7)
    if kind in {"crack", "split", "decoy"}:
        return f'<g fill="none" stroke="{light}" stroke-width="14"><path d="M525 20 L450 145 L555 220 L430 330 L520 500"/><path d="M100 395 Q300 110 455 180" stroke-dasharray="18 18"/><path d="M950 395 Q760 110 585 180" stroke-dasharray="18 18"/></g>'+person(250,255,1.1,accent,.8)+person(800,255,1.1,accent,.8)
    if kind in {"tunnel"}:
        return f'<path d="M120 500 Q150 60 550 60 Q950 60 980 500" fill="#080b0d" stroke="{light}" stroke-width="18"/>'+person(550,275,1.0,accent,.9)
    if kind in {"factorylink", "factoryblock"}:
        return f'<g transform="translate(110 120)" fill="{accent}" stroke="{light}" stroke-width="13"><path d="M0 330V145 L180 240 V120 L360 220 V70 L520 180 V330Z"/><rect x="570" y="80" width="90" height="250"/><path d="M615 80V0 M700 330H850" fill="none"/></g>'
    if kind in {"swirl"}:
        return f'<g transform="translate(525 255)" fill="none" stroke="{light}" stroke-width="16"><path d="M0 0 C-260-210-410 110-190 210 C40 320 350 150 330-80 C315-255 70-310-95-180"/><path d="M-130-225 L-55-185 L-115-115" fill="{accent}"/></g>'
    return f'<circle cx="550" cy="255" r="170" fill="{accent}" opacity=".42" stroke="{light}" stroke-width="16"/>'


def art_svg(row, index):
    name, color, kind = row["行動卡名稱"], row["顏色"], row["種類"]
    dark, accent, light = PALETTES.get(color, PALETTES["灰"])
    seed = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    motif = SPECIAL.get(name, TYPE_ICON.get(kind, "network"))
    stars = ''.join(f'<circle cx="{rng.randint(40,1060)}" cy="{rng.randint(30,480)}" r="{rng.randint(2,7)}" fill="{light}" opacity="{rng.uniform(.08,.28):.2f}"/>' for _ in range(28))
    skyline = ''.join(f'<rect x="{x}" y="{rng.randint(320,420)}" width="{rng.randint(55,115)}" height="{rng.randint(80,185)}" fill="#070b0f" opacity=".72"/>' for x in range(0,1100,90))
    main = icon(motif, accent, light)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="520" viewBox="0 0 1100 520" role="img" aria-labelledby="title desc">
<title id="title">{esc(name)}插圖</title><desc id="desc">依據卡牌效果與意涵繪製的無文字策略卡插圖。</desc>
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{dark}"/><stop offset=".55" stop-color="#111820"/><stop offset="1" stop-color="{accent}"/></linearGradient><radialGradient id="glow"><stop stop-color="{light}" stop-opacity=".34"/><stop offset="1" stop-color="{light}" stop-opacity="0"/></radialGradient></defs>
<rect width="1100" height="520" fill="url(#bg)"/><circle cx="550" cy="220" r="390" fill="url(#glow)"/>{stars}{skyline}
<path d="M0 455 Q250 390 520 455 T1100 430 V520 H0Z" fill="#070a0e" opacity=".85"/>{main}
<rect width="1100" height="520" fill="none" stroke="{light}" stroke-opacity=".25" stroke-width="8"/>
</svg>'''


def cost_group(items):
    if not items:
        return '<text x="145" y="10" fill="#e8ddca" font-family="PingFang TC, Noto Sans TC, sans-serif" font-size="31" font-weight="800">免費</text>'
    x = 145
    chunks = []
    for label, number in items:
        fill = "#ead296" if label == "資金" else "#e8c69d"
        grad = "money" if label == "資金" else "prop"
        chunks.append(f'<text x="{x}" y="10" fill="{fill}" font-family="PingFang TC, Noto Sans TC, sans-serif" font-size="27" font-weight="800">{label}</text>')
        cx = x + 98
        chunks.append(f'<circle cx="{cx}" r="39" fill="url(#{grad})" stroke="#efd099" stroke-width="5" filter="url(#shadow)"/>')
        chunks.append(f'<text x="{cx}" y="14" text-anchor="middle" fill="#fff5d8" font-family="Avenir Next, sans-serif" font-size="43" font-weight="900">{esc(number)}</text>')
        x += 160
    return ''.join(chunks)


def resource_footer(items):
    if not items:
        return '<text x="545" y="1255" fill="#b7afa4" font-family="PingFang TC, Noto Sans TC, sans-serif" font-size="31" font-weight="800">無</text>'
    x = 545
    chunks = []
    for label, number in items:
        fill = "#ead296" if label == "資金" else "#e8c69d"
        grad = "money" if label == "資金" else "prop"
        chunks.append(f'<text x="{x}" y="1255" fill="{fill}" font-family="PingFang TC, Noto Sans TC, sans-serif" font-size="30" font-weight="800">{label}</text>')
        cx = x + 118
        chunks.append(f'<circle cx="{cx}" cy="1244" r="39" fill="url(#{grad})" stroke="#efd099" stroke-width="5"/>')
        chunks.append(f'<text x="{cx}" y="1258" text-anchor="middle" fill="#fff5d8" font-family="Avenir Next, sans-serif" font-size="43" font-weight="900">{esc(number)}</text>')
        x += 210
    return ''.join(chunks)


def full_svg(row):
    name, color = row["行動卡名稱"], row["顏色"]
    dark, accent, light = PALETTES.get(color, PALETTES["灰"])
    effect_lines = wrap_cjk(row["行動卡效果"], 16)
    if len(effect_lines) <= 2: base_size, line_height = 53, 68
    elif len(effect_lines) <= 4: base_size, line_height = 47, 57
    elif len(effect_lines) <= 6: base_size, line_height = 41, 49
    else: base_size, line_height = 36, 43
    max_units = max(sum(1 if ord(char) > 127 else 0.58 for char in line) for line in effect_lines)
    font_size = max(34, min(base_size, int(880 / max_units)))
    line_height = max(line_height, int(font_size * 1.18))
    effect_start = 835
    effect_text = ''.join(f'<text x="96" y="{effect_start+i*line_height}" fill="#29231e" font-family="PingFang TC, Noto Sans TC, sans-serif" font-size="{font_size}" font-weight="700">{esc(line)}</text>' for i,line in enumerate(effect_lines))
    title_size = 65 if len(name) <= 5 else 57
    art_png_name = f"{name}_插圖.png"
    if (ART_COMPOSED_DIR / art_png_name).exists():
        art_href = f"../art-composed/{art_png_name}"
    elif (ART_DIR / art_png_name).exists():
        art_href = f"../art/{art_png_name}"
    else:
        art_href = f"../art/{name}_插圖.svg"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1100" height="1350" viewBox="0 0 1100 1350" role="img" aria-labelledby="title desc">
<title id="title">{esc(name)}完整卡面</title><desc id="desc">購買費用 {esc(row['購買費用'])}，提供資源 {esc(row['提供資源'])}。</desc>
<defs>
<linearGradient id="frame" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{accent}"/><stop offset=".34" stop-color="{dark}"/><stop offset=".76" stop-color="#0a0908"/><stop offset="1" stop-color="{accent}"/></linearGradient>
<linearGradient id="header" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#111015"/><stop offset=".68" stop-color="{dark}"/><stop offset="1" stop-color="#111015"/></linearGradient>
<linearGradient id="paper" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#f1e6cd"/><stop offset="1" stop-color="#cfbb91"/></linearGradient>
<radialGradient id="prop" cx="35%" cy="30%" r="75%"><stop stop-color="#d37656"/><stop offset="1" stop-color="#91362b"/></radialGradient>
<radialGradient id="money" cx="35%" cy="30%" r="75%"><stop stop-color="#d7ad54"/><stop offset="1" stop-color="#7b591b"/></radialGradient>
<pattern id="grain" width="43" height="47" patternUnits="userSpaceOnUse"><circle cx="7" cy="10" r="1" fill="#fff" opacity=".05"/><circle cx="31" cy="34" r=".9" fill="#000" opacity=".13"/></pattern>
<filter id="shadow" x="-30%" y="-30%" width="160%" height="170%"><feGaussianBlur in="SourceAlpha" stdDeviation="7"/><feOffset dy="7"/><feColorMatrix values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .58 0"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="artClip"><rect x="52" y="216" width="996" height="468" rx="16"/></clipPath>
</defs>
<rect width="1100" height="1350" rx="50" fill="#080503"/><rect x="13" y="13" width="1074" height="1324" rx="42" fill="url(#frame)" stroke="#bca98e" stroke-width="5"/><rect x="31" y="31" width="1038" height="1288" rx="32" fill="#18100b" stroke="#d0b982" stroke-width="2"/>
<path d="M45 45h1010v150H45z" fill="url(#header)"/><path d="M46 194h1008" stroke="{light}" stroke-width="6"/>
<g transform="translate(102 119)"><circle r="38" fill="{dark}" stroke="{light}" stroke-width="5"/><circle r="10" fill="{light}"/><path d="M0-10L-24-24M0-10L25-25M0 10L-27 26M0 10L26 26" stroke="{light}" stroke-width="5" stroke-linecap="round"/><circle cx="-24" cy="-24" r="6" fill="{accent}"/><circle cx="25" cy="-25" r="6" fill="{accent}"/><circle cx="-27" cy="26" r="6" fill="{accent}"/><circle cx="26" cy="26" r="6" fill="{accent}"/></g>
<text x="158" y="142" fill="#f6ecd8" font-family="PingFang TC, Noto Sans TC, sans-serif" font-size="{title_size}" font-weight="800" letter-spacing="3">{esc(name)}</text>
<g transform="translate(560 120)"><text x="0" y="10" fill="#e6d4ad" font-family="PingFang TC, Noto Sans TC, sans-serif" font-size="27" font-weight="800" letter-spacing="2">購買費用</text>{cost_group(parse_resource(row['購買費用']))}</g>
<g clip-path="url(#artClip)"><image xlink:href="{esc(art_href)}" href="{esc(art_href)}" x="52" y="216" width="996" height="468" preserveAspectRatio="xMidYMid meet"/><rect x="52" y="590" width="996" height="94" fill="#080b0f" opacity=".68"/></g>
<rect x="52" y="216" width="996" height="468" rx="16" fill="none" stroke="{light}" stroke-width="6"/><text x="84" y="650" fill="#f2dca8" font-family="PingFang TC, Noto Sans TC, sans-serif" font-size="25" font-weight="700" letter-spacing="2">{esc(row['行動卡意涵'])}</text>
<rect x="52" y="710" width="996" height="454" rx="20" fill="url(#paper)" stroke="#e1c78e" stroke-width="4"/><rect x="72" y="730" width="956" height="414" rx="14" fill="none" stroke="#725f49" stroke-width="2" opacity=".45"/>
<g transform="translate(96 750)"><rect width="128" height="40" rx="20" fill="{dark}"/><text x="64" y="28" text-anchor="middle" fill="#f2ddb0" font-family="PingFang TC, Noto Sans TC, sans-serif" font-size="21" font-weight="800" letter-spacing="3">卡牌效果</text></g>{effect_text}
<rect x="52" y="1190" width="996" height="108" rx="20" fill="#130d09" stroke="#a89879" stroke-width="3"/><text x="84" y="1255" fill="#e8ddca" font-family="PingFang TC, Noto Sans TC, sans-serif" font-size="31" font-weight="800" letter-spacing="3">提供資源</text>{resource_footer(parse_resource(row['提供資源']))}
<rect x="13" y="13" width="1074" height="1324" rx="42" fill="url(#grain)" pointer-events="none"/>
</svg>'''


def render_svg(svg_path: Path, png_path: Path, width=1100, height=1350):
    subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={width},{height}", "--force-device-scale-factor=1", f"--screenshot={png_path}", svg_path.as_uri()], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    for directory in (ART_DIR, SVG_DIR, PNG_DIR, PREVIEW_DIR): directory.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    manifest = []
    for index, row in enumerate(rows, 1):
        name = row["行動卡名稱"].strip()
        art_path = ART_DIR / f"{name}_插圖.svg"
        svg_path = SVG_DIR / f"{name}.svg"
        png_path = PNG_DIR / f"{name}.png"
        preview_path = PREVIEW_DIR / f"{name}.png"
        art_path.write_text(art_svg(row, index), encoding="utf-8")
        svg_path.write_text(full_svg(row), encoding="utf-8")
        render_svg(svg_path, png_path)
        subprocess.run(["sips", "-z", "270", "220", str(png_path), "--out", str(preview_path)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        manifest.append({"index": index, "name": name, "cost": row["購買費用"], "resource": row["提供資源"], "effect": row["行動卡效果"], "meaning": row["行動卡意涵"]})
        print(f"[{index:02d}/{len(rows)}] {name}")
    with (OUT / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["index","name","cost","resource","effect","meaning"])
        writer.writeheader(); writer.writerows(manifest)
    cards = ''.join(f'''<article><a href="png/{esc(item['name'])}.png"><img src="preview-220x270/{esc(item['name'])}.png" alt="{esc(item['name'])}"></a><h2>{item['index']:02d}. {esc(item['name'])}</h2><p>購買：{esc(item['cost'])}｜提供：{esc(item['resource'])}</p></article>''' for item in manifest)
    (OUT / "index.html").write_text(f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>逆統戰全部行動卡檢查表</title><style>body{{margin:0;background:#080b10;color:#edf2f7;font-family:-apple-system,BlinkMacSystemFont,"Noto Sans TC",sans-serif}}header{{position:sticky;top:0;padding:18px 28px;background:#101722eF;border-bottom:1px solid #334155;z-index:2}}main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:24px;padding:28px}}article{{background:#111827;border:1px solid #334155;border-radius:16px;padding:12px}}img{{display:block;width:220px;height:270px;object-fit:contain;margin:auto;border-radius:10px}}h2{{font-size:18px;margin:12px 0 6px}}p{{font-size:13px;color:#cbd5e1}}</style><header><strong>逆統戰全部行動卡｜共 {len(manifest)} 張</strong>　點卡牌可開啟 1100×1350 原圖</header><main>{cards}</main></html>''', encoding="utf-8")
    print(f"DONE {len(rows)} cards -> {OUT}")

if __name__ == "__main__": main()
