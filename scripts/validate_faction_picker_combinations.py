import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / 'FACTION_PICKER_COMBINATION_VALIDATION.json'
OUT_MD = ROOT / 'FACTION_PICKER_COMBINATION_VALIDATION.md'
BASE_URL = 'http://127.0.0.1:8000'


def humanize_win_condition(w):
    if not w:
        return '（暫無資料）'
    if isinstance(w, str):
        return w
    if w.get('text'):
        return w['text']
    t = w.get('type')
    if t == 'count_only':
        return f"回合結束時在{w.get('scope', '指定區域')}擁有至少 {w.get('count')} 個有效組織。"
    if t == 'count_and_required':
        required = '、'.join(w.get('required_locations', []))
        return f"回合結束時在{w.get('scope', '指定區域')}擁有至少 {w.get('count')} 個有效組織，且必須包含 {required}。"
    if t == 'default_survival':
        return w.get('text', '遊戲結束前未有反共陣營玩家達成勝利條件。')
    if t == 'taiwan_override':
        return w.get('text', '若有玩家選用臺灣，紅軍在臺灣城鎮達成指定組織數時直接獲勝。')
    return json.dumps(w, ensure_ascii=False)


def render_ability(a):
    if isinstance(a, str):
        return a
    return '：'.join([x for x in [a.get('name_override') or a.get('name'), a.get('trigger'), a.get('effect')] if x])


def faction_display_name(category, option):
    if option['id'] == 'taiwan_green':
        return '臺灣（綠線）'
    if option['id'] == 'taiwan_blue':
        return '臺灣（藍線）'
    if category['id'] in {'uyghur', 'tibet'} and option.get('variant'):
        return f"{category['label']}（{option['variant']}）"
    return option.get('variant') or option.get('name') or option.get('label') or option['id']


def build_combos(categories):
    combos = []
    for category in categories:
        for option in category['options']:
            resolved = option.get('base_resolved') or {}
            if not resolved:
                combos.append({
                    'category': category['label'],
                    'category_id': category['id'],
                    'option_id': option['id'],
                    'option_label': option.get('variant') or option.get('name') or option['id'],
                    'display_name': faction_display_name(category, option),
                    'base_group': None,
                    'base_town': None,
                    'option': option,
                    'mode': category['mode'],
                })
                continue
            for group, towns in resolved.items():
                for town in towns:
                    combos.append({
                        'category': category['label'],
                        'category_id': category['id'],
                        'option_id': option['id'],
                        'option_label': option.get('variant') or option.get('name') or option['id'],
                        'display_name': faction_display_name(category, option),
                        'base_group': group,
                        'base_town': town,
                        'option': option,
                        'mode': category['mode'],
                    })
    return combos


def text_of(locator):
    try:
        return (locator.text_content() or '').strip()
    except Exception:
        return ''


def escape_regex_text(text):
    return re.escape(text)


def validate_combo(page, combo):
    page.goto(BASE_URL, wait_until='domcontentloaded')
    create = page.evaluate("""async () => (await (await fetch('/create', {method:'POST'})).json())""")
    room = create['game_id']
    host_id = create['host_id']
    page.fill('#roomId', room)
    page.fill('#playerName', 'host')
    page.evaluate(f"playerId={json.dumps(host_id)}")
    page.get_by_text('JOIN OPERATION').click()
    page.wait_for_timeout(120)

    page.locator('#factionList .faction-choice-btn', has_text=re.compile(f'^{escape_regex_text(combo["category"])}$')).first.click()
    page.wait_for_timeout(60)

    if combo['mode'] != 'direct':
        page.locator('#factionVariantList .faction-choice-btn', has_text=re.compile(f'^{escape_regex_text(combo["option_label"])}$')).first.click()
        page.wait_for_timeout(60)

    if combo['base_group']:
        page.locator('#factionBaseList .base-choice-btn', has_text=re.compile(f'^{escape_regex_text(combo["base_group"])}$')).first.click()
        page.wait_for_timeout(60)
        if combo['base_town'] != combo['base_group']:
            page.locator('#factionBaseList .base-choice-btn', has_text=re.compile(f'^{escape_regex_text(combo["base_town"])}$')).first.click()
            page.wait_for_timeout(60)

    info = text_of(page.locator('#factionPickerInfo'))
    title = text_of(page.locator('#factionDetailTitle'))
    bases = text_of(page.locator('#factionDetailBases'))
    abilities = text_of(page.locator('#factionDetailAbilities'))
    rules = text_of(page.locator('#factionDetailRules'))
    win = text_of(page.locator('#factionDetailWin'))
    confirm_visible = page.locator('#confirmFactionBtn').is_visible()

    expected_abilities = [render_ability(a) for a in combo['option'].get('abilities', []) or combo['option'].get('abilities_text', [])]
    expected_rules = [
        *(combo['option'].get('setup_effects', []) or []),
        *(combo['option'].get('special_rules', []) or []),
        *(combo['option'].get('restrictions', []) or []),
    ]
    if combo['option'].get('win_condition_text'):
        expected_wins = [combo['option']['win_condition_text']]
    else:
        expected_wins = [humanize_win_condition(w) for w in combo['option'].get('win_conditions', [])]

    errors = []
    if combo['display_name'] not in info:
        errors.append(f'info missing display name: {combo["display_name"]}')
    if combo['base_town'] and combo['base_town'] not in info:
        errors.append(f'info missing base town: {combo["base_town"]}')
    if not title:
        errors.append('missing detail title')
    if combo['display_name'] not in title:
        errors.append(f'title mismatch: {title}')
    if combo['base_town'] and combo['base_town'] not in bases:
        errors.append(f'bases mismatch: {bases}')
    if not confirm_visible:
        errors.append('confirm button hidden')
    if expected_abilities:
        for item in expected_abilities:
            if item and item not in abilities:
                errors.append(f'ability missing: {item}')
                break
    else:
        if '（暫無資料）' not in abilities:
            errors.append('ability placeholder missing')
    if expected_rules:
        for item in expected_rules:
            if item and item not in rules:
                errors.append(f'rule missing: {item}')
                break
    else:
        if '（暫無資料）' not in rules:
            errors.append('rules placeholder missing')
    if expected_wins:
        for item in expected_wins:
            if item and item not in win:
                errors.append(f'win missing: {item}')
                break
    else:
        if '（暫無資料）' not in win:
            errors.append('win placeholder missing')
    if '{' in win or '"type"' in win:
        errors.append('win appears raw/json-like')

    return {
        'combo': {
            'category': combo['category'],
            'option': combo['option_label'],
            'base_group': combo['base_group'],
            'base_town': combo['base_town'],
        },
        'info': info,
        'title': title,
        'bases': bases,
        'abilities': abilities,
        'rules': rules,
        'win': win,
        'confirm_visible': confirm_visible,
        'ok': not errors,
        'errors': errors,
    }


def main():
    categories = json.loads(urllib.request.urlopen(f'{BASE_URL}/factions').read().decode('utf-8'))['categories']
    combos = build_combos(categories)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1800})
        for idx, combo in enumerate(combos, 1):
            result = validate_combo(page, combo)
            result['index'] = idx
            results.append(result)
            if idx % 25 == 0:
                print(f'validated {idx}/{len(combos)}', flush=True)
        browser.close()

    failed = [r for r in results if not r['ok']]
    summary = {
        'total': len(results),
        'passed': len(results) - len(failed),
        'failed': len(failed),
    }
    payload = {
        'summary': summary,
        'failed_examples': failed[:50],
        'results': results,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    lines = [
        '# FACTION PICKER COMBINATION VALIDATION',
        '',
        f"- total: {summary['total']}",
        f"- passed: {summary['passed']}",
        f"- failed: {summary['failed']}",
        '',
    ]
    if failed:
        lines.append('## Failed examples')
        lines.append('')
        for item in failed[:50]:
            c = item['combo']
            lines.append(f"- {c['category']} / {c['option']} / {c['base_group']} / {c['base_town']}: {'; '.join(item['errors'])}")
    else:
        lines.append('## Result')
        lines.append('')
        lines.append('All combinations passed.')
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    import urllib.request
    main()
