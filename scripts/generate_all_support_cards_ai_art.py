#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import importlib
import json
import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
CSV_PATH = REPO / "data/raw/support_cards.csv"
OUT = REPO / "docs/records/design/card-art/all-support-cards-ai-review"
ART_DIR = OUT / "art"
SVG_DIR = OUT / "svg"
PNG_DIR = OUT / "png"
PREVIEW_DIR = OUT / "preview-220x270"
PROGRESS = OUT / "ai-generation-progress.json"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
TIANFANG_V3 = REPO / "docs/records/design/card-art/support-card-trials/天方奧援-印度南洋-v3/天方奧援_插圖.png"

REGION_STYLE = {
    "英美奧援": {
        "colors": ("#18253a", "#aa7b31", "#b9d5ed"),
        "caption": "跨洋金融與通信網絡，將資源送往遠方盟友",
        "prompt": """A fictional 1920s–1940s transatlantic Anglo-American support network: monumental harbor skyline, ocean liner and cargo cranes, Art Deco financial hall, brass telegraph equipment, undersea cable routes glowing across a globe with no labels, diverse period bankers, dock organizers and radio operators transferring stacks of blank bonds and coin crates. Visualize escalating money support: one, two, then three streams of resources converging. Navy, steel blue, copper and warm bank-lamp gold; cinematic gouache and 1930s poster geometry.""",
    },
    "東洋奧援": {
        "colors": ("#17222c", "#a74b37", "#d9c493"),
        "caption": "跨越城牆的東亞網絡，在牆內建立新的組織節點",
        "prompt": """An unmistakably JAPANESE 1920s–1940s urban support network, not generic East Asia: a modernizing Japanese castle town and port inspired by Tokyo, Yokohama and Kobe, with dark kawara tiled roofs, machiya wooden lattice facades, shoji screens, narrow lantern-lit alleys with completely blank lanterns, massive Japanese castle stone ramparts and moat, early electric railway, tram wires, telegraph poles, and Mount Fuji visible in the distance. Japanese civic organizers in a historically grounded mix of kimono, haori, hakama and 1930s Western suits carry blank plans across the stone wall into an inner neighborhood, where new glowing community nodes appear. Clear mechanic: establish an organization beyond the wall at long range, then within one step. Indigo, sumi charcoal, aged cedar, muted vermilion and parchment; refined Japanese woodblock composition blended with cinematic historical gouache, realistic people and hands. No Chinese architectural roofs, no generic pan-Asian city, no flags, rising-sun motif, military insignia, readable kanji, shrine icon, party emblem or real leader.""",
    },
    "南洋奧援": {
        "colors": ("#0d3334", "#b66e2b", "#9bd9d1"),
        "caption": "群島港口與海運信使，帶來情報與新的手牌選擇",
        "prompt": """A fictional 1920s–1940s Southeast Asian maritime support network: tropical archipelago port, wooden trading vessels and steam ferry, shophouse arcades, rain clouds, palms and telegraph station, diverse local couriers exchanging blank sealed cards and packets across islands. Show two fresh blank cards arriving, with one older blank card optionally returned to a discard tray. Teal, monsoon blue, warm teak and amber; cinematic hand-painted gouache, respectful historical realism.""",
    },
    "印度奧援": {
        "colors": ("#352312", "#b56535", "#e3bd65"),
        "caption": "南亞鐵路與印刷網絡，將分神層層送入對手棄牌堆",
        "prompt": """A fictional 1920s–1940s South Asian support network: grand railway terminus, arched civic buildings, printing workshop, telegraph clerk, textile patterns and busy organizers routing three sealed blank disruption packets along rail lines into a distant dark discard tray. Make the one-two-three escalating packets visually clear without numbers. Saffron, indigo, marigold, dark teak and brass; dignified South Asian period setting, cinematic gouache with refined poster design.""",
    },
    "天方奧援": {
        "colors": ("#102a2d", "#b7872f", "#a9e2dc"),
        "caption": "西亞商旅與電報網絡，迫使鄰近對手棄置手牌",
        "prompt": "",
    },
    "歐洲奧援": {
        "colors": ("#20283a", "#9c4637", "#d5c7a9"),
        "caption": "跨國印刷與廣播網絡，持續擴大宣傳聲量",
        "prompt": """A fictional interwar 1920s–1940s European support network: cobbled continental city, railway station clock with no numerals, modernist radio studio, rotary printing press producing blank sheets, news kiosks with blank posters, couriers connecting several cities by luminous routes. Visualize escalating public influence as two, three, then four expanding broadcast waves. Slate blue, burgundy, cream and brass; sophisticated European modernist gouache and screen-print texture, no flags or political symbols.""",
    },
    "北國奧援": {
        "colors": ("#18232d", "#7b3b32", "#b7d2d8"),
        "caption": "雪國鐵路與地下網絡，逐步瓦解鄰近的對手節點",
        "prompt": """A fictional 1920s–1940s northern Eurasian support network in winter: snowbound industrial rail junction, birch forest, telegraph lines, austere apartment blocks and clandestine organizers around an unmarked tactical map. One allied network node is deliberately sacrificed while one or two nearby rival nodes made of wooden markers are removed. Cold steel blue, snow gray, dark pine and restrained brick red; cinematic historical gouache, no flags, stars, party emblems, real leaders, weapons or gore.""",
    },
    "臺灣奧援": {
        "colors": ("#16302a", "#9e5633", "#b8d7bd"),
        "caption": "島嶼城鎮與民間網絡，在瓦解後建立新的組織",
        "prompt": """A fictional 1920s–1940s Taiwan island support network: subtropical harbor town, brick arcades, tiled homes, narrow-gauge railway, tea and camphor warehouses, mountains beyond, telegraph poles and local civic organizers. On a town map made of unlabeled wooden pieces, one rival node is removed and a new community node is established in the same place. Forest green, terracotta, sea blue and warm paper; respectful historical gouache, no flags, emblems or readable signs.""",
    },
    "紅軍奧援": {
        "colors": ("#281514", "#9b3e32", "#d3b47b"),
        "caption": "一張往返陣營之間的起始牌，帶來資源與情報",
        "prompt": """A fictional 1920s–1940s Chinese rural revolutionary support network without real leaders or party symbols: mountain village courier station, rough wooden table, radio and supply satchels, a single blank crimson-backed card passing between two opposing groups across a river bridge, with one new blank message card being drawn and small coin and pamphlet bundles supplied. Earth brown, weathered red, charcoal and warm lantern gold; cinematic historical gouache, human solidarity and strategic tension, no flags, stars, emblems, weapons or gore.""",
    },
}

BASE_PROMPT = """Create premium TEXT-FREE historical board-game key art for {name}. {scene}
Fictional East/West Asian political-strategy setting inspired by the 1920s–1940s. Make the named region immediately recognizable through dignified architecture, geography, clothing, transport and material culture rather than labels. Translate the exact mechanic into concrete visual motifs. Strong shallow-wide composition, clear central silhouette, polished hand-painted gouache, restrained screen-print grain, realistic anatomy and hands, opaque full-bleed background.
No real political leader, national flag, party emblem, explicit religious icon, stereotype, modern brand, copyrighted character, weapon or gore. ABSOLUTELY NO readable text, letters, numbers, map labels, signs, logos, watermark, frame, border, UI, title, cost token, resource icon or typography anywhere."""


def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def slug_condition(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]+", "-", value).strip("-")


def load_rows() -> list[dict[str, str]]:
    result = []
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for index, values in enumerate(reader, 1):
            if not values or not values[0]:
                continue
            if values[0] == "紅軍奧援":
                result.append({
                    "index": str(index), "name": values[0], "cost": values[1],
                    "special": values[2], "tier3_condition": "", "tier3_effect": "",
                    "tier2_condition": "", "tier2_effect": "", "tier1_condition": "",
                    "tier1_effect": "", "copies": values[8] or "1", "variant": "起始牌",
                })
            else:
                result.append({
                    "index": str(index), "name": values[0], "cost": values[1],
                    "tier3_condition": values[2], "tier3_effect": values[3],
                    "tier2_condition": values[4], "tier2_effect": values[5],
                    "tier1_condition": values[6], "tier1_effect": values[7],
                    "copies": values[8], "special": "", "variant": values[4],
                })
    return result


def valid_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        return path.stat().st_size > 10000
    except Exception:
        return False


def save_progress(done: list[str], failed: dict[str, str], current: str | None = None) -> None:
    temp = PROGRESS.with_suffix(".tmp")
    temp.write_text(json.dumps({"done": done, "failed": failed, "current": current, "updated_at": time.time()}, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(PROGRESS)


def generate_art(rows: list[dict[str, str]]) -> None:
    unique_names = list(dict.fromkeys(row["name"] for row in rows))
    force_names = {name.strip() for name in os.environ.get("FORCE_SUPPORT_ART", "").split(",") if name.strip()}
    tianfang_target = ART_DIR / "天方奧援_插圖.png"
    if valid_image(TIANFANG_V3) and not valid_image(tianfang_target):
        shutil.copy2(TIANFANG_V3, tianfang_target)

    provider_cls = importlib.import_module("plugins.image_gen.openai-codex").OpenAICodexImageGenProvider
    provider = provider_cls()
    if not provider.is_available():
        raise RuntimeError("OpenAI Codex OAuth image provider unavailable")

    done = [name for name in unique_names if name not in force_names and valid_image(ART_DIR / f"{name}_插圖.png")]
    failed: dict[str, str] = {}
    save_progress(done, failed)
    for index, name in enumerate(unique_names, 1):
        destination = ART_DIR / f"{name}_插圖.png"
        if name not in force_names and valid_image(destination):
            print(f"[{index:02d}/{len(unique_names)}] SKIP {name}", flush=True)
            continue
        style = REGION_STYLE[name]
        prompt = BASE_PROMPT.format(name=name, scene=style["prompt"])
        last_error = ""
        for attempt in range(1, 4):
            try:
                save_progress(done, failed, name)
                print(f"[{index:02d}/{len(unique_names)}] GENERATE {name} attempt={attempt}", flush=True)
                response = provider.generate(prompt, aspect_ratio="landscape")
                if not response.get("success"):
                    raise RuntimeError(response.get("error") or str(response))
                shutil.copy2(Path(response["image"]), destination)
                if not valid_image(destination):
                    raise RuntimeError("invalid generated image")
                done.append(name); failed.pop(name, None); save_progress(done, failed)
                print(f"[{index:02d}/{len(unique_names)}] SAVED {destination}", flush=True)
                break
            except Exception as exc:
                last_error = str(exc); failed[name] = last_error; save_progress(done, failed, name)
                print(f"[{index:02d}/{len(unique_names)}] ERROR {name}: {last_error}", flush=True)
                if attempt < 3:
                    time.sleep(10 * attempt)
        else:
            print(f"GAVE UP {name}: {last_error}", flush=True)
    if failed:
        raise RuntimeError(f"Image generation failures remain: {failed}")
    save_progress(done, failed)


def cost_items(value: str) -> list[tuple[str, str]]:
    return [(label, number) for number, label in re.findall(r"(\d+)\s*(資金|宣傳)", value)]


def cost_group(value: str) -> str:
    if value == "起始牌":
        return '<text x="155" y="11" fill="#f0d8a8" font-family="PingFang TC, sans-serif" font-size="34" font-weight="900">起始牌</text>'
    x, chunks = 145, []
    for label, number in cost_items(value):
        fill = "#ead296" if label == "資金" else "#e8c69d"
        grad = "money" if label == "資金" else "prop"
        chunks.append(f'<text x="{x}" y="10" fill="{fill}" font-family="PingFang TC, sans-serif" font-size="27" font-weight="800">{label}</text>')
        cx = x + 98
        chunks.append(f'<circle cx="{cx}" r="39" fill="url(#{grad})" stroke="#efd099" stroke-width="5"/>')
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
    effects = "".join(f'<text x="246" y="{y + 79 + i * line_height}" fill="#30271f" font-family="PingFang TC, sans-serif" font-size="{size}" font-weight="700">{esc(line)}</text>' for i, line in enumerate(lines))
    return f'''<g><rect x="70" y="{y}" width="960" height="166" rx="18" fill="#eadcc0" stroke="#8f7654" stroke-width="3"/><rect x="88" y="{y+18}" width="116" height="130" rx="16" fill="{accent}"/><text x="146" y="{y+83}" text-anchor="middle" fill="#fff2cf" font-family="Avenir Next, sans-serif" font-size="45" font-weight="900">{tier}</text><text x="246" y="{y+39}" fill="#765729" font-family="PingFang TC, sans-serif" font-size="25" font-weight="800">條件｜{esc(condition)}</text>{effects}</g>'''


def common_svg_start(row: dict[str, str], dark: str, accent: str, light: str) -> str:
    title, caption = row["name"], REGION_STYLE[row["name"]]["caption"]
    art_name = f"{title}_插圖.png"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1100" height="1350" viewBox="0 0 1100 1350" role="img" aria-labelledby="title desc"><title id="title">{esc(title)}完整卡面</title><desc id="desc">{esc(row['cost'])}；依正式 support_cards.csv 排版。</desc><defs><linearGradient id="frame" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{accent}"/><stop offset=".35" stop-color="{dark}"/><stop offset=".72" stop-color="#071011"/><stop offset="1" stop-color="{light}"/></linearGradient><linearGradient id="header"><stop stop-color="#111015"/><stop offset=".68" stop-color="{dark}"/><stop offset="1" stop-color="#111015"/></linearGradient><radialGradient id="prop"><stop stop-color="#d37656"/><stop offset="1" stop-color="#91362b"/></radialGradient><radialGradient id="money"><stop stop-color="#d7ad54"/><stop offset="1" stop-color="#7b591b"/></radialGradient><pattern id="grain" width="43" height="47" patternUnits="userSpaceOnUse"><circle cx="7" cy="10" r="1" fill="#fff" opacity=".05"/><circle cx="31" cy="34" r=".9" fill="#000" opacity=".13"/></pattern><clipPath id="artClip"><rect x="52" y="216" width="996" height="405" rx="16"/></clipPath></defs><rect width="1100" height="1350" rx="50" fill="#080503"/><rect x="13" y="13" width="1074" height="1324" rx="42" fill="url(#frame)" stroke="#c7ae78" stroke-width="5"/><rect x="31" y="31" width="1038" height="1288" rx="32" fill="#18100b" stroke="#d0b982" stroke-width="2"/><path d="M45 45h1010v150H45z" fill="url(#header)"/><path d="M46 194h1008" stroke="{light}" stroke-width="6"/><g transform="translate(102 119)"><circle r="38" fill="{dark}" stroke="{light}" stroke-width="5"/><path d="M-22 8Q0-24 22 8Q0 33-22 8Z" fill="none" stroke="{light}" stroke-width="6"/><circle cy="8" r="7" fill="{accent}"/></g><text x="158" y="142" fill="#f6ecd8" font-family="PingFang TC, sans-serif" font-size="65" font-weight="800" letter-spacing="3">{esc(title)}</text><g transform="translate(560 120)"><text x="0" y="10" fill="#e6d4ad" font-family="PingFang TC, sans-serif" font-size="27" font-weight="800">{('卡牌類型' if row['cost']=='起始牌' else '購買費用')}</text>{cost_group(row['cost'])}</g><g clip-path="url(#artClip)"><image xlink:href="../art/{esc(art_name)}" href="../art/{esc(art_name)}" x="52" y="216" width="996" height="405" preserveAspectRatio="xMidYMid slice"/><rect x="52" y="553" width="996" height="68" fill="#071516" opacity=".75"/></g><rect x="52" y="216" width="996" height="405" rx="16" fill="none" stroke="{light}" stroke-width="6"/><text x="84" y="597" fill="#f2dca8" font-family="PingFang TC, sans-serif" font-size="25" font-weight="700">{esc(caption)}</text>'''


def full_svg(row: dict[str, str]) -> str:
    dark, accent, light = REGION_STYLE[row["name"]]["colors"]
    start = common_svg_start(row, dark, accent, light)
    if row["name"] != "紅軍奧援":
        body = tier_panel(644, "III", row["tier3_condition"], row["tier3_effect"], accent) + tier_panel(820, "II", row["tier2_condition"], row["tier2_effect"], dark) + tier_panel(996, "I", row["tier1_condition"], row["tier1_effect"], "#584c3f")
        footer = f'<rect x="70" y="1182" width="960" height="104" rx="18" fill="#0d2022" stroke="#aa956c" stroke-width="3"/><text x="102" y="1248" fill="#dfc99a" font-family="PingFang TC, sans-serif" font-size="29" font-weight="800">奧援卡</text><text x="938" y="1248" text-anchor="end" fill="#b9deda" font-family="PingFang TC, sans-serif" font-size="27" font-weight="700">卡牌張數 {esc(row["copies"])}</text>'
    else:
        source = row["special"]
        effect = source.replace("提供資源：1資金+1宣傳。卡牌效果：", "")
        lines = wrap_cjk(effect, 16)
        effect_text = "".join(f'<text x="100" y="{760+i*58}" fill="#30271f" font-family="PingFang TC, sans-serif" font-size="46" font-weight="700">{esc(line)}</text>' for i, line in enumerate(lines))
        body = f'<rect x="70" y="644" width="960" height="480" rx="18" fill="#eadcc0" stroke="#8f7654" stroke-width="3"/><text x="100" y="688" fill="#765729" font-family="PingFang TC, sans-serif" font-size="27" font-weight="900">卡牌效果</text>{effect_text}'
        footer = f'<rect x="70" y="1142" width="960" height="144" rx="18" fill="#0d2022" stroke="#aa956c" stroke-width="3"/><text x="102" y="1200" fill="#dfc99a" font-family="PingFang TC, sans-serif" font-size="29" font-weight="800">提供資源</text><text x="330" y="1237" fill="#ead296" font-family="PingFang TC, sans-serif" font-size="31" font-weight="800">資金 1</text><text x="600" y="1237" fill="#e8c69d" font-family="PingFang TC, sans-serif" font-size="31" font-weight="800">宣傳 1</text><text x="938" y="1237" text-anchor="end" fill="#b9deda" font-family="PingFang TC, sans-serif" font-size="25" font-weight="700">卡牌張數 {esc(row["copies"])}</text><desc>{esc(source)}</desc>'
    return start + body + footer + '<rect x="13" y="13" width="1074" height="1324" rx="42" fill="url(#grain)" pointer-events="none"/></svg>'


def render(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    manifest = []
    for sequence, row in enumerate(rows, 1):
        suffix = slug_condition(row["variant"])
        stem = f"{sequence:02d}_{row['name']}_{suffix}"
        svg_path, png_path, preview_path = SVG_DIR/f"{stem}.svg", PNG_DIR/f"{stem}.png", PREVIEW_DIR/f"{stem}.png"
        svg_path.write_text(full_svg(row), encoding="utf-8")
        ET.parse(svg_path)
        subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1100,1350", "--force-device-scale-factor=1", f"--screenshot={png_path}", svg_path.as_uri()], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sips", "-z", "270", "220", str(png_path), "--out", str(preview_path)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        manifest.append({**row, "stem": stem})
        print(f"RENDER [{sequence:02d}/{len(rows)}] {stem}", flush=True)
    with (OUT/"manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["stem", "name", "variant", "cost", "tier3_condition", "tier3_effect", "tier2_condition", "tier2_effect", "tier1_condition", "tier1_effect", "special", "copies"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(manifest)
    return manifest


def contact_sheet(manifest: list[dict[str, str]]) -> None:
    cols, cell_w, cell_h = 4, 280, 350
    sheet = Image.new("RGB", (cols*cell_w, ((len(manifest)+cols-1)//cols)*cell_h), "#080b10")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", 18)
    for i, item in enumerate(manifest):
        x, y = (i%cols)*cell_w+30, (i//cols)*cell_h+10
        card = Image.open(PREVIEW_DIR/f"{item['stem']}.png").convert("RGB")
        sheet.paste(card, (x, y)); draw.text((x, y+278), f"{i+1:02d}. {item['name']}", fill="#f1f5f9", font=font); draw.text((x, y+304), item["variant"], fill="#b9c4d2", font=font)
    sheet.save(OUT/"全部奧援卡_總覽.png")


def make_index(manifest: list[dict[str, str]]) -> None:
    cards = "".join(f'<article><a href="png/{esc(x["stem"])}.png"><img src="preview-220x270/{esc(x["stem"])}.png"></a><h2>{esc(x["name"])}</h2><p>{esc(x["variant"])}</p></article>' for x in manifest)
    (OUT/"index.html").write_text(f'<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>全部奧援卡</title><style>body{{background:#080b10;color:#eee;font-family:-apple-system,sans-serif}}main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:22px}}article{{padding:12px;background:#111827;border-radius:14px}}img{{width:220px;height:270px;display:block;margin:auto}}h2,p{{margin:8px}}</style><main>{cards}</main></html>', encoding="utf-8")


def package() -> Path:
    zip_path = OUT.parent / "全部奧援卡_AI插圖_未提交檢查包.zip"
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(OUT), str(zip_path)], check=True)
    return zip_path


def main() -> None:
    for directory in (OUT, ART_DIR, SVG_DIR, PNG_DIR, PREVIEW_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    generate_art(rows)
    manifest = render(rows)
    contact_sheet(manifest)
    make_index(manifest)
    zip_path = package()
    save_progress(list(dict.fromkeys(r["name"] for r in rows)), {}, None)
    print(f"DONE arts={len(set(r['name'] for r in rows))} faces={len(rows)} zip={zip_path}", flush=True)


if __name__ == "__main__":
    main()
