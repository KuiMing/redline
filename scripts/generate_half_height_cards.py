#!/usr/bin/env python3
# /// script
# dependencies = ["pillow>=11,<13"]
# ///
"""Generate compact 1100×675 card faces without touching full cards."""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ACTION_CSV = ROOT / "data/raw/action_cards.csv"
SUPPORT_CSV = ROOT / "data/raw/support_cards.csv"
ACTION_ART = ROOT / "docs/records/design/card-art/all-action-cards-ai-review/art-composed"
SUPPORT_ART = ROOT / "docs/records/design/card-art/all-support-cards-ai-review/art"
DEFAULT_OUTPUT = ROOT / "docs/records/design/card-art/half-height-cards"
DEFAULT_REVIEW_OUTPUT = DEFAULT_OUTPUT
REVIEW_ROOT = ROOT / "docs/records/design/card-art"
PROTECTED_FULL_CARD_ROOT = ROOT / "static/card-art"
WIDTH, HEIGHT = 1100, 675
PREVIEW_WIDTH, PREVIEW_HEIGHT = 220, 135

SUPPORT_CAPTIONS = {
    "英美奧援": "跨洋金融與通信網絡，將資源送往遠方盟友",
    "東洋奧援": "跨越城牆的東亞網絡，在牆內建立新的組織節點",
    "南洋奧援": "群島港口與海運信使，帶來情報與新的手牌選擇",
    "印度奧援": "南亞鐵路與印刷網絡，將分神層層送入對手棄牌堆",
    "天方奧援": "西亞商旅與電報網絡，迫使鄰近對手棄置手牌",
    "歐洲奧援": "跨國印刷與廣播網絡，持續擴大宣傳聲量",
    "北國奧援": "雪國鐵路與地下網絡，逐步瓦解鄰近的對手節點",
    "臺灣奧援": "島嶼城鎮與民間網絡，在瓦解後建立新的組織",
    "紅軍奧援": "一張往返陣營之間的起始牌，帶來資源與情報",
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def slug_condition(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]+", "-", value).strip("-")


def resource_items(value: str) -> list[tuple[str, str]]:
    value = (value or "").strip()
    if not value or value in {"無", "0", "免費", "起始牌"}:
        return []
    items: list[tuple[str, str]] = []
    for part in value.replace("＋", "+").split("+"):
        part = part.strip()
        match = re.fullmatch(r"(?:(資金|宣傳)\s*(\d+)|(\d+)\s*(資金|宣傳))", part)
        if not match:
            raise ValueError(f"無法解析資源：{value!r}")
        label = match.group(1) or match.group(4)
        number = match.group(2) or match.group(3)
        items.append((label, number))
    return items


def support_printed_resources(value: str) -> str:
    match = re.search(r"提供資源[：:]\s*([^。]+)", value)
    if not match:
        raise ValueError(f"找不到奧援卡提供資源：{value!r}")
    resources = match.group(1).strip()
    resource_items(resources)
    return resources


def load_action_rows() -> list[dict[str, str]]:
    with ACTION_CSV.open(encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("行動卡名稱", "").strip()]


def load_support_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with SUPPORT_CSV.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        sequence = 0
        for values in reader:
            if not values or not values[0].strip():
                continue
            sequence += 1
            name = values[0].strip()
            variant = "起始牌" if name == "紅軍奧援" else values[4].strip()
            special = values[2].strip() if name == "紅軍奧援" else ""
            rows.append({
                "sequence": str(sequence),
                "name": name,
                "cost": values[1].strip(),
                "variant": variant,
                "special": special,
                "resources": support_printed_resources(special) if special else "",
            })
    return rows


def defs() -> str:
    return '''<defs>
<linearGradient id="bronze" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#72593a"/><stop offset=".5" stop-color="#4e3a28"/><stop offset="1" stop-color="#72593a"/></linearGradient>
<linearGradient id="header" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#211912"/><stop offset="1" stop-color="#100c09"/></linearGradient>
<radialGradient id="prop"><stop stop-color="#d37656"/><stop offset="1" stop-color="#91362b"/></radialGradient>
<radialGradient id="money"><stop stop-color="#d7ad54"/><stop offset="1" stop-color="#7b591b"/></radialGradient>
<pattern id="grain" width="41" height="43" patternUnits="userSpaceOnUse"><circle cx="7" cy="10" r="1" fill="#fff" opacity=".035"/><circle cx="29" cy="32" r=".9" fill="#000" opacity=".10"/></pattern>
<filter id="shadow" x="-30%" y="-30%" width="160%" height="170%"><feGaussianBlur in="SourceAlpha" stdDeviation="5"/><feOffset dy="5"/><feColorMatrix values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .55 0"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="artClip"><rect x="52" y="174" width="996" height="466" rx="16"/></clipPath>
</defs>'''


def frame_start(title: str, cost: str, art_path: Path, desc: str) -> str:
    title_size = 61 if len(title) <= 5 else 54
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
<title id="title">{esc(title)}半高卡面</title><desc id="desc">{esc(desc)}</desc>{defs()}
<rect width="1100" height="675" rx="46" fill="#090705"/>
<rect x="13" y="13" width="1074" height="649" rx="39" fill="url(#bronze)" stroke="#b99a61" stroke-width="5"/>
<rect x="31" y="31" width="1038" height="613" rx="29" fill="#17100b" stroke="#d0b982" stroke-width="2"/>
<path d="M45 45h1010v112H45z" fill="url(#header)"/>
<path d="M46 157h1008" stroke="#b99a61" stroke-width="5"/>
<g transform="translate(94 101)"><circle r="32" fill="#3f3021" stroke="#c3a56e" stroke-width="4"/><circle r="8" fill="#d0b982"/><path d="M0-8L-20-20M0-8L21-21M0 8L-22 22M0 8L22 22" stroke="#d0b982" stroke-width="4" stroke-linecap="round"/></g>
<text x="145" y="123" fill="#f6ecd8" font-family="PingFang TC, Noto Sans TC, sans-serif" font-size="{title_size}" font-weight="800" letter-spacing="3">{esc(title)}</text>
{cost_markup(cost)}
<g clip-path="url(#artClip)"><image xlink:href="{esc(art_path.as_uri())}" href="{esc(art_path.as_uri())}" x="52" y="174" width="996" height="466" preserveAspectRatio="xMidYMid slice"/><rect x="52" y="538" width="996" height="102" fill="#0b0907" opacity=".88"/></g>
<rect x="52" y="174" width="996" height="466" rx="16" fill="none" stroke="#b99a61" stroke-width="5"/>'''


def cost_markup(value: str) -> str:
    if value == "起始牌":
        body = '<text x="150" y="9" fill="#f0d8a8" font-family="PingFang TC, sans-serif" font-size="31" font-weight="900">起始牌</text>'
    else:
        items = resource_items(value)
        if not items:
            body = '<text x="150" y="9" fill="#e8ddca" font-family="PingFang TC, sans-serif" font-size="31" font-weight="800">免費</text>'
        else:
            chunks: list[str] = []
            x = 146
            for label, number in items:
                fill = "#ead296" if label == "資金" else "#e8c69d"
                gradient = "money" if label == "資金" else "prop"
                chunks.append(f'<text x="{x}" y="9" fill="{fill}" font-family="PingFang TC, sans-serif" font-size="27" font-weight="800">{label}</text>')
                cx = x + 93
                chunks.append(f'<circle cx="{cx}" r="34" fill="url(#{gradient})" stroke="#efd099" stroke-width="4" filter="url(#shadow)"/>')
                chunks.append(f'<text x="{cx}" y="13" text-anchor="middle" fill="#fff5d8" font-family="Avenir Next, sans-serif" font-size="43" font-weight="900">{esc(number)}</text>')
                x += 143
            body = "".join(chunks)
    return f'<g transform="translate(550 101)"><text x="0" y="9" fill="#e6d4ad" font-family="PingFang TC, sans-serif" font-size="27" font-weight="800">購買費用</text>{body}</g>'


def resource_markup(value: str) -> str:
    items = resource_items(value)
    chunks = ['<text x="630" y="573" fill="#e6d4ad" font-family="PingFang TC, sans-serif" font-size="27" font-weight="800">提供資源</text>']
    if not items:
        chunks.append('<text x="790" y="613" fill="#b7afa4" font-family="PingFang TC, sans-serif" font-size="27" font-weight="800">無</text>')
        return "".join(chunks)
    starts = [770] if len(items) == 1 else [748, 886]
    for x, (label, number) in zip(starts, items):
        fill = "#ead296" if label == "資金" else "#e8c69d"
        gradient = "money" if label == "資金" else "prop"
        chunks.append(f'<text x="{x}" y="613" fill="{fill}" font-family="PingFang TC, sans-serif" font-size="27" font-weight="800">{label}</text>')
        cx = x + 83
        chunks.append(f'<circle cx="{cx}" cy="602" r="29" fill="url(#{gradient})" stroke="#efd099" stroke-width="4"/>')
        chunks.append(f'<text x="{cx}" y="616" text-anchor="middle" fill="#fff5d8" font-family="Avenir Next, sans-serif" font-size="43" font-weight="900">{esc(number)}</text>')
    return "".join(chunks)


def frame_end() -> str:
    return '<rect x="13" y="13" width="1074" height="649" rx="39" fill="url(#grain)" pointer-events="none"/></svg>'


def action_svg(row: dict[str, str]) -> str:
    name = row["行動卡名稱"].strip()
    art_path = ACTION_ART / f"{name}_插圖.png"
    if not art_path.is_file():
        raise FileNotFoundError(art_path)
    meaning = row["行動卡意涵"].strip()
    start = frame_start(name, row["購買費用"].strip(), art_path, f"購買費用 {row['購買費用']}，提供資源 {row['提供資源']}。")
    caption = f'<text x="82" y="584" fill="#f2dca8" font-family="PingFang TC, sans-serif" font-size="25" font-weight="700">{esc(meaning)}</text><text x="82" y="616" fill="#b8aa91" font-family="PingFang TC, sans-serif" font-size="20" font-weight="700">行動卡</text>'
    return start + caption + resource_markup(row["提供資源"].strip()) + frame_end()


def support_svg(row: dict[str, str]) -> str:
    name, variant = row["name"], row["variant"]
    art_path = SUPPORT_ART / f"{name}_插圖.png"
    if not art_path.is_file():
        raise FileNotFoundError(art_path)
    start = frame_start(name, row["cost"], art_path, f"購買費用 {row['cost']}，版本 {variant}。")
    caption = SUPPORT_CAPTIONS[name]
    left = f'<text x="82" y="579" fill="#f2dca8" font-family="PingFang TC, sans-serif" font-size="23" font-weight="700">{esc(caption)}</text><text x="82" y="616" fill="#b8aa91" font-family="PingFang TC, sans-serif" font-size="22" font-weight="800">奧援卡</text>'
    if name == "紅軍奧援":
        right = resource_markup(row["resources"])
    else:
        right = f'<text x="692" y="574" fill="#e6d4ad" font-family="PingFang TC, sans-serif" font-size="27" font-weight="800">II級條件</text><text x="692" y="616" fill="#f4d49c" font-family="PingFang TC, sans-serif" font-size="27" font-weight="900">{esc(variant)}</text>'
    return start + left + right + frame_end()


def render_svg(svg: str, svg_path: Path, png_path: Path, chrome: Path) -> None:
    svg_path.write_text(svg, encoding="utf-8")
    ET.parse(svg_path)
    subprocess.run([
        str(chrome), "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--allow-file-access-from-files", f"--window-size={WIDTH},{HEIGHT}",
        "--force-device-scale-factor=1", f"--screenshot={png_path}", svg_path.as_uri(),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with Image.open(png_path) as image:
        if image.size != (WIDTH, HEIGHT):
            raise RuntimeError(f"輸出尺寸錯誤：{png_path} {image.size}")


def contact_sheet(items: list[dict[str, str]], review_output: Path, title: str) -> Path:
    columns, cell_w, cell_h = 4, 260, 190
    rows = (len(items) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_w, 56 + rows * cell_h), "#090b0e")
    draw = ImageDraw.Draw(sheet)
    font_path = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
    title_font = ImageFont.truetype(font_path, 24)
    label_font = ImageFont.truetype(font_path, 15)
    draw.text((24, 15), title, fill="#f4ead8", font=title_font)
    for index, item in enumerate(items):
        x = (index % columns) * cell_w + 20
        y = 56 + (index // columns) * cell_h
        with Image.open(item["path"]) as source:
            card = source.convert("RGB").resize((PREVIEW_WIDTH, PREVIEW_HEIGHT), Image.Resampling.LANCZOS)
        sheet.paste(card, (x, y))
        draw.text((x, y + 142), item["label"], fill="#d8dee8", font=label_font)
    review_output.mkdir(parents=True, exist_ok=True)
    destination = review_output / f"{title}.png"
    sheet.save(destination)
    return destination


def locate_chrome(value: str | None) -> Path:
    candidates = [
        Path(value) if value else None,
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path(shutil.which("google-chrome") or ""),
        Path(shutil.which("chromium") or ""),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise FileNotFoundError("找不到可用的 Chrome/Chromium")


def validate_output_path(output: Path) -> None:
    output = output.resolve()
    if output == PROTECTED_FULL_CARD_ROOT or output.is_relative_to(PROTECTED_FULL_CARD_ROOT):
        raise ValueError(f"禁止寫入完整卡牌目錄：{output}")
    if output.is_relative_to(ROOT):
        if not output.is_relative_to(REVIEW_ROOT):
            raise ValueError(f"儲存庫內輸出只能位於卡牌審閱目錄：{output}")
        relative = output.relative_to(REVIEW_ROOT)
        if not relative.parts or not relative.parts[0].startswith("half-height"):
            raise ValueError(f"半高卡輸出目錄名稱必須以 half-height 開頭：{output}")


def generate(output: Path, review_output: Path, chrome: Path) -> list[dict[str, object]]:
    validate_output_path(output)
    validate_output_path(review_output)
    action_rows, support_rows = load_action_rows(), load_support_rows()
    action_output, support_output = output / "actions", output / "support"
    validate_output_path(action_output)
    validate_output_path(support_output)
    action_output.mkdir(parents=True, exist_ok=True)
    support_output.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []
    action_review: list[dict[str, str]] = []
    support_review: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="redline-half-cards-") as temp_name:
        temp = Path(temp_name)
        for index, row in enumerate(action_rows, 1):
            name = row["行動卡名稱"].strip()
            destination = action_output / f"{name}.png"
            render_svg(action_svg(row), temp / f"action-{index:02d}.svg", destination, chrome)
            manifest.append({"kind": "action", "name": name, "variant": "", "path": destination.relative_to(output).as_posix(), "width": WIDTH, "height": HEIGHT})
            action_review.append({"path": str(destination), "label": f"{index:02d}. {name}"})
            print(f"ACTION [{index:02d}/{len(action_rows)}] {name}")
        for index, row in enumerate(support_rows, 1):
            stem = f"{index:02d}_{row['name']}_{slug_condition(row['variant'])}"
            destination = support_output / f"{stem}.png"
            render_svg(support_svg(row), temp / f"support-{index:02d}.svg", destination, chrome)
            manifest.append({"kind": "support", "name": row["name"], "variant": row["variant"], "path": destination.relative_to(output).as_posix(), "width": WIDTH, "height": HEIGHT})
            support_review.append({"path": str(destination), "label": f"{index:02d}. {row['name']}｜{row['variant']}"})
            print(f"SUPPORT [{index:02d}/{len(support_rows)}] {stem}")
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    contact_sheet(action_review, review_output, "半高行動卡總覽")
    contact_sheet(support_review, review_output, "半高奧援卡總覽")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--review-output", type=Path, default=DEFAULT_REVIEW_OUTPUT)
    parser.add_argument("--chrome", help="Chrome/Chromium 執行檔")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    review_output = args.review_output.resolve()
    manifest = generate(output, review_output, locate_chrome(args.chrome))
    print(f"DONE cards={len(manifest)} output={output}")
    print(f"REVIEW={review_output}")


if __name__ == "__main__":
    main()
