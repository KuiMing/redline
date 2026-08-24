import json
import os
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'faction-ui'
OUT_JSON = RECORD_DIR / 'FACTION_PICKER_COMBINATION_VALIDATION.json'
OUT_MD = RECORD_DIR / 'FACTION_PICKER_COMBINATION_VALIDATION.md'
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')


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
        if a.startswith('【展現實力】'):
            return a.replace('【展現實力】', '展現實力：', 1).replace('，則可獲得', '，獲得').removesuffix('。')
        return a
    name = a.get('name_override') or a.get('name')
    if name == '展現實力':
        return f"{name}：{a.get('trigger', '')}，{a.get('effect', '')}".rstrip('，')
    return '：'.join([x for x in [name, a.get('trigger'), a.get('effect')] if x])


def is_rule_like_ability(a):
    return isinstance(a, dict) and a.get('type') in {'setup', 'restriction'}


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


def prepare_option(page, combo):
    page.goto(BASE_URL + '/new-game', wait_until='domcontentloaded')
    page.fill('#playerName', 'host')
    page.locator('#createRoomBtn').click()
    page.wait_for_function("document.getElementById('factionPicker')?.style.display === 'flex'")

    page.locator('#factionList .faction-choice-btn', has_text=re.compile(f'^{escape_regex_text(combo["category"])}$')).first.click()
    page.wait_for_timeout(150)

    if combo['mode'] != 'direct':
        page.locator('#factionVariantList .faction-choice-btn', has_text=re.compile(f'^{escape_regex_text(combo["option_label"])}$')).first.click()
        page.wait_for_timeout(150)


def validate_combo(page, combo):
    if combo['base_town']:
        page.locator('#factionBaseList .base-choice-btn', has_text=re.compile(f'^{escape_regex_text(combo["base_town"])}$')).first.click()
        page.wait_for_function(
            """town => document.querySelector('#factionBaseList .active')?.textContent.trim() === town
              && document.getElementById('factionDetailBases')?.textContent.includes(town)""",
            arg=combo['base_town'],
        )

    info = text_of(page.locator('#factionPickerInfo'))
    title = text_of(page.locator('#factionDetailTitle'))
    bases = text_of(page.locator('#factionDetailBases'))
    abilities = text_of(page.locator('#factionDetailAbilities'))
    rules = text_of(page.locator('#factionDetailRules'))
    win = text_of(page.locator('#factionDetailWin'))
    confirm_visible = page.locator('#confirmFactionBtn').is_visible()

    detail_option = combo['option']
    if combo['base_town'] and combo['option'].get('variant_details'):
        detail_option = combo['option']['variant_details'].get(combo['base_town'], detail_option)

    all_expected_abilities = list(detail_option.get('abilities', []) or detail_option.get('abilities_text', []))
    selected_base = next((base for base in (detail_option.get('bases', []) or []) if isinstance(base, dict) and base.get('name') == combo['base_town']), None)
    if selected_base:
        all_expected_abilities.extend(selected_base.get('abilities', []) or [])
    expected_abilities = [render_ability(a) for a in all_expected_abilities if not is_rule_like_ability(a)]
    expected_rules = [
        *(detail_option.get('setup_effects', []) or []),
        *(detail_option.get('special_rules', []) or []),
        *(detail_option.get('restrictions', []) or []),
        *(render_ability(a) for a in all_expected_abilities if is_rule_like_ability(a)),
    ]
    if detail_option.get('win_condition_text'):
        expected_wins = [detail_option['win_condition_text']]
    else:
        expected_wins = [humanize_win_condition(w) for w in detail_option.get('win_conditions', [])]

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
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    categories = json.loads(urllib.request.urlopen(f'{BASE_URL}/factions').read().decode('utf-8'))['categories']
    combos = build_combos(categories)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1800})
        prepared_option = None
        for idx, combo in enumerate(combos, 1):
            option_key = (combo['category_id'], combo['option_id'])
            if option_key != prepared_option:
                prepare_option(page, combo)
                prepared_option = option_key
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
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    import urllib.request
    main()
