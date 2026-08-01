#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get(
    'ACTION_CARD_ART_OUT',
    REPO / 'docs/records/design/card-art/all-action-cards-ai-review',
))
ART = OUT / 'art'
PROGRESS = OUT / 'ai-generation-progress.json'
CSV_PATH = REPO / 'data/raw/action_cards.csv'

CATEGORY_STYLE = {
    '宣傳': 'charcoal gray and warm parchment with restrained brick-red accents, public persuasion and human connection',
    '資金': 'burnished copper, amber, dark walnut and warm lamplight, discreet patronage and material networks',
    '混亂': 'deep violet, charcoal and cold gray, fractured attention and internal tension',
    '交通': 'teal, steel blue and misty gray, roads rail lines movement and logistical flow',
    '指揮': 'navy blue, parchment and cool strategic light, maps planning coordination and decisive action',
    '間諜': 'forest green, black and muted amber, clandestine observation coded networks and secrecy',
    '組織': 'walnut brown, charcoal and warm brass, community nodes distant supporters and disciplined expansion',
    '整肅': 'burnt orange, black and aged paper, severe internal review removal and ideological discipline',
    '武裝': 'deep red, gunmetal and smoke gray, organized pressure and tactical readiness without gore',
}

def valid_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        return path.stat().st_size > 10000
    except Exception:
        return False


def prompt_for(row: dict) -> str:
    name = row['行動卡名稱']
    effect = row['行動卡效果']
    meaning = row['行動卡意涵']
    style = CATEGORY_STYLE.get(row['種類'], CATEGORY_STYLE['宣傳'])
    return f'''Create a premium TEXT-FREE portrait illustration for a historical political-strategy board-game action card concept called “{name}”.

Narrative meaning: {meaning}.
Game mechanic to visualize through concrete imagery and composition: {effect}.

Fictional East Asian setting inspired by the 1920s–1940s. Do not depict any real political leader, real party emblem, national flag, copyrighted character, or identifiable modern brand. Translate the mechanic into a distinct visual motif, not merely a literal portrait of the title. Use one strong focal silhouette, layered environmental storytelling, clear action direction, and high readability after cropping into a wide card-art window. The visual palette and emotional vocabulary should be: {style}.

Art direction: cinematic hand-painted gouache and historical board-game key art, restrained screen-print texture, subtle aged-paper grain, dramatic side lighting, realistic human anatomy, expressive but natural faces and hands, polished professional tabletop illustration, opaque full-bleed background. Keep the center and upper-middle visually rich; keep the extreme perimeter calmer for cropping.

ABSOLUTELY NO readable text, letters, numbers, labels, signs, logos, watermark, card frame, border, UI, cost tokens, resource symbols, title, or typography anywhere in the image. Portrait artwork only.'''


def save_progress(done, failed, current=None):
    PROGRESS.write_text(json.dumps({'done': done, 'failed': failed, 'current': current, 'updated_at': time.time()}, ensure_ascii=False, indent=2), encoding='utf-8')


def make_contact_sheet(rows):
    cols, cell_w, cell_h = 8, 240, 310
    count = len(rows)
    sheet = Image.new('RGB', (cols * cell_w, ((count + cols - 1)//cols) * cell_h), '#080b10')
    draw = ImageDraw.Draw(sheet)
    font_path = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'
    font = ImageFont.truetype(font_path, 18)
    for i, row in enumerate(rows):
        name = row['行動卡名稱']
        x, y = (i % cols) * cell_w + 10, (i // cols) * cell_h + 8
        card = Image.open(OUT/'preview-220x270'/f'{name}.png').convert('RGB')
        sheet.paste(card, (x, y))
        draw.text((x, y + 275), f'{i+1:02d}. {name}', fill='#f1f5f9', font=font)
    sheet.save(OUT/'全部行動卡_總覽.png')


def main():
    ART.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))

    provider_cls = importlib.import_module('plugins.image_gen.openai-codex').OpenAICodexImageGenProvider
    provider = provider_cls()
    print(f'provider={provider.display_name} available={provider.is_available()} model={provider.default_model()}', flush=True)
    if not provider.is_available():
        raise SystemExit('OpenAI Codex image provider unavailable')

    done = [row['行動卡名稱'] for row in rows if valid_image(ART/f"{row['行動卡名稱']}_插圖.png")]
    failed = {}
    save_progress(done, failed)
    for index, row in enumerate(rows, 1):
        name = row['行動卡名稱']
        destination = ART / f'{name}_插圖.png'
        if valid_image(destination):
            print(f'[{index:02d}/{len(rows)}] SKIP {name}', flush=True)
            continue
        save_progress(done, failed, name)
        last_error = None
        for attempt in range(1, 4):
            try:
                print(f'[{index:02d}/{len(rows)}] GENERATE {name} attempt={attempt}', flush=True)
                result = provider.generate(prompt_for(row), aspect_ratio='portrait')
                if not result.get('success'):
                    raise RuntimeError(result.get('error') or str(result))
                source = Path(result['image'])
                shutil.copy2(source, destination)
                if not valid_image(destination):
                    raise RuntimeError('generated file is not a valid non-empty image')
                done.append(name)
                failed.pop(name, None)
                save_progress(done, failed)
                print(f'[{index:02d}/{len(rows)}] SAVED {destination}', flush=True)
                break
            except Exception as exc:
                last_error = str(exc)
                failed[name] = last_error
                save_progress(done, failed, name)
                print(f'[{index:02d}/{len(rows)}] ERROR {name}: {last_error}', flush=True)
                if attempt < 3:
                    time.sleep(8 * attempt)
        else:
            print(f'GAVE UP {name}: {last_error}', flush=True)

    if failed:
        raise SystemExit(f'Image generation failures remain: {failed}')

    print('Rendering all full card faces with AI illustrations...', flush=True)
    render_env = os.environ.copy()
    render_env['ACTION_CARD_ART_OUT'] = str(OUT)
    subprocess.run(
        ['python3', str(REPO/'scripts/generate_all_action_cards.py')],
        cwd=REPO,
        env=render_env,
        check=True,
    )
    make_contact_sheet(rows)
    zip_path = OUT.parent/'全部行動卡_AI插圖_未提交檢查包.zip'
    subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(OUT), str(zip_path)], check=True)
    save_progress(done, failed, None)
    print(f'DONE cards={len(rows)} zip={zip_path}', flush=True)

if __name__ == '__main__':
    main()
