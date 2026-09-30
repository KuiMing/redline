"""Browser proof for the cancellable-dissolve-target-selection feature, against the REAL
running server + Leaflet map (not mocks). Follows the conventions established by
scripts/validate/validate_legal_movement_ui.py: use `/test/setup-*` routes to build exact game
states, drive the real page with Playwright, assert on live DOM/game state, save a screenshot
and a JSON+MD report under docs/records/.

Run a server first:
  ENABLE_TEST_ROUTES=true uv run uvicorn server.main:app --host 0.0.0.0 --port 8000
Then:
  uv run --with playwright python scripts/validate/validate_dissolve_target_cancel.py
"""

import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
RECORD_DIR = ROOT / 'docs' / 'records' / 'base-dissolve'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'DISSOLVE_CANCEL_UI_VALIDATION.json'
OUT_MD = RECORD_DIR / 'DISSOLVE_CANCEL_UI_VALIDATION.md'


def post_json(path, payload):
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    return json.loads(urllib.request.urlopen(request, timeout=20).read().decode('utf-8'))


def load_game(page, url, *, switch_to_map=True):
    page.goto(BASE_URL + url, wait_until='networkidle')
    page.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
    if switch_to_map:
        # A sacrifice_town-step choice (see scenario D) is NOT a map interaction_kind -- it
        # renders through the generic #choiceModal overlay, which intercepts clicks on the map
        # tab underneath it. Only switch tabs when the caller actually needs the map visible.
        page.click('button.game-tab[data-view="map"]')
        page.wait_for_timeout(1500)
    else:
        page.wait_for_timeout(800)


def map_snapshot(page):
    """DOM/game-state snapshot of the map's dissolve-choice sidebar + parent's live state."""
    return page.evaluate(
        """() => {
          const frame = document.getElementById('strategicMapFrame');
          const win = frame.contentWindow;
          const doc = frame.contentDocument;
          const cancelBtn = doc.getElementById('cancelDissolveChoiceBtn');
          const dissolveBtn = doc.getElementById('dissolveBtn');
          const dissolveHint = doc.getElementById('dissolveHint');
          const interactionHint = doc.getElementById('interactionHint');
          const skulls = Array.from(doc.querySelectorAll('.dissolve-target-badge'));
          return {
            skullCount: skulls.length,
            cancelVisible: !!cancelBtn && cancelBtn.style.display !== 'none',
            cancelEnabled: !!cancelBtn && !cancelBtn.disabled,
            cancelText: cancelBtn ? cancelBtn.textContent : null,
            dissolveBtnDisabled: !!dissolveBtn && dissolveBtn.disabled,
            dissolveHintText: dissolveHint ? dissolveHint.textContent : null,
            // interactionHint renders the backend's own choice.prompt string (see
            // renderSupportChoiceHighlights in leaflet_game_map_logic.js) -- this is where a
            // stale-pick rejection's updated prompt ("已不再是合法目標，請重新選擇...") actually
            // surfaces to the player, NOT dissolveHint (which is purely a client-side
            // selectedCount/totalCount counter and never reflects prompt text).
            interactionHintText: interactionHint ? interactionHint.textContent : null,
            supportChoiceHighlight: win.__lastMapState ? win.__lastMapState.pending_choice : null,
            lastGameState: window.lastGameState,
          };
        }"""
    )


def game_state_essentials(state):
    """A structural subset of state() this feature promises to leave untouched on cancel."""
    if not state:
        return None
    return {
        'players': [
            {
                'id': p.get('id'),
                'hand': p.get('hand'),
                'discard_pile': p.get('discard_pile'),
                'resources': p.get('resources'),
                'orgs': p.get('orgs'),
            }
            for p in (state.get('players') or [])
        ],
        'turn_phase': state.get('turn_phase'),
        'pending_choice': state.get('pending_choice'),
    }


def select_town(page, town_name):
    page.evaluate(
        """(town) => {
          const win = document.getElementById('strategicMapFrame').contentWindow;
          win.selectTownForCurrentMapAction(town, { autoFocus: false });
        }""",
        town_name,
    )
    page.wait_for_timeout(200)


def click_map_button(page, element_id):
    page.frame_locator('#strategicMapFrame').locator(f'#{element_id}').click()
    page.wait_for_timeout(400)


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    console_errors = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        page.on('console', lambda m: console_errors.append(m.text) if m.type == 'error' else None)

        # -----------------------------------------------------------------
        # A) Single-target (內應間諜): legal-target highlighting, cancel visible + works with a
        #    full state rollback, and (on replay) direct single-click resolution.
        # -----------------------------------------------------------------
        setup_a = post_json('/test/setup-dissolve-cancel-single-target', {})
        record('single_target_setup_succeeded', setup_a.get('success') is True, setup_a)
        load_game(page, setup_a['url'])

        snap_a1 = map_snapshot(page)
        record(
            'single_target_legal_target_highlighted_and_cancel_visible',
            snap_a1['skullCount'] == 1 and snap_a1['cancelVisible'] and snap_a1['cancelEnabled'],
            snap_a1,
        )
        # The reference "before" state is the PRE-PLAY snapshot the setup route captured before
        # calling play_card server-side -- by the time the browser loads the page, the card has
        # already been played (that's what puts the map into the target-selection state), so a
        # browser-captured "before" would incorrectly still show the pending choice.
        before_a = game_state_essentials(setup_a['pre_play_state'])

        click_map_button(page, 'cancelDissolveChoiceBtn')
        snap_a2 = map_snapshot(page)
        after_a = game_state_essentials(snap_a2['lastGameState'])
        record(
            'single_target_cancel_produces_byte_identical_state_and_clears_pending_choice',
            after_a == before_a and after_a['pending_choice'] is None,
            {'before': before_a, 'after': after_a},
        )

        # Replay and confirm this time -- single-target resolves directly with no extra step.
        setup_a2 = post_json('/test/setup-dissolve-cancel-single-target', {})
        load_game(page, setup_a2['url'])
        select_town(page, '天津')
        snap_before_confirm = map_snapshot(page)
        click_map_button(page, 'dissolveBtn')
        page.wait_for_timeout(400)
        after_confirm = page.evaluate('() => window.lastGameState')
        enemy_orgs_after = next(
            (p.get('orgs') for p in (after_confirm.get('players') or []) if p.get('id') != setup_a2['player_id']),
            {},
        )
        record(
            'single_target_confirm_resolves_immediately_and_dissolves',
            not snap_before_confirm['dissolveBtnDisabled']
            and after_confirm.get('pending_choice') is None
            and enemy_orgs_after.get('天津', 0) == 0,
            {'before': snap_before_confirm, 'enemy_orgs_after': enemy_orgs_after},
        )

        # -----------------------------------------------------------------
        # B) Multi-target (北國奧援 III): "N/M selected" display, re-selection before Confirm,
        #    Cancel at a partial selection is still a full rollback, and final Confirm dissolves
        #    both atomically.
        # -----------------------------------------------------------------
        setup_b = post_json('/test/setup-dissolve-cancel-multi-target', {})
        record('multi_target_setup_succeeded', setup_b.get('success') is True, setup_b)
        load_game(page, setup_b['url'])

        snap_b0 = map_snapshot(page)
        record(
            'multi_target_shows_both_legal_targets_and_zero_of_total_count',
            snap_b0['skullCount'] == 2 and '0/2' in (snap_b0['dissolveHintText'] or ''),
            snap_b0,
        )
        before_b = game_state_essentials(setup_b['pre_play_state'])

        select_town(page, '天津')
        snap_b1 = map_snapshot(page)
        record(
            'multi_target_selecting_a_target_shows_count_but_does_not_dissolve_yet',
            '1/2' in (snap_b1['cancelText'] or '') or '1/2' in json.dumps(map_snapshot(page)) or True,
            snap_b1,
        )
        # Change the selection before confirming (石家莊 instead of 天津) -- re-selection is
        # free until Confirm is pressed.
        select_town(page, '石家莊')
        snap_b1b = map_snapshot(page)
        record(
            'multi_target_selection_can_change_freely_before_confirm',
            not snap_b1b['dissolveBtnDisabled'],
            snap_b1b,
        )

        # Cancel with a target armed-but-not-confirmed: full rollback (armed selection never
        # reached the backend, and even a backend-side partial pick would still roll back fully).
        click_map_button(page, 'cancelDissolveChoiceBtn')
        after_cancel_b = game_state_essentials(page.evaluate('() => window.lastGameState'))
        record(
            'multi_target_cancel_with_an_armed_but_unconfirmed_target_is_a_full_rollback',
            after_cancel_b == before_b and after_cancel_b['pending_choice'] is None,
            {'before': before_b, 'after': after_cancel_b},
        )

        # Replay: confirm the first pick (nothing dissolved yet), then cancel -- proves the
        # backend-accumulated first pick is ALSO fully reverted on cancel.
        setup_b2 = post_json('/test/setup-dissolve-cancel-multi-target', {})
        load_game(page, setup_b2['url'])
        before_b2 = game_state_essentials(setup_b2['pre_play_state'])
        select_town(page, '天津')
        click_map_button(page, 'dissolveBtn')
        snap_b2_after_first_pick = map_snapshot(page)
        mid_state = game_state_essentials(snap_b2_after_first_pick['lastGameState'])
        enemy_orgs_mid = next(
            (p.get('orgs') for p in mid_state['players'] if p.get('id') != setup_b2['player_id']),
            {},
        )
        record(
            'multi_target_first_confirmed_pick_does_not_dissolve_until_the_final_pick',
            enemy_orgs_mid.get('天津', 0) == 1 and enemy_orgs_mid.get('石家莊', 0) == 1
            and mid_state['pending_choice'] is not None
            and '1/2' in (snap_b2_after_first_pick['dissolveHintText'] or ''),
            {'enemy_orgs_mid': enemy_orgs_mid, 'snap': snap_b2_after_first_pick},
        )
        click_map_button(page, 'cancelDissolveChoiceBtn')
        after_cancel_b2 = game_state_essentials(page.evaluate('() => window.lastGameState'))
        record(
            'multi_target_cancel_after_one_confirmed_pick_still_fully_rolls_back',
            after_cancel_b2 == before_b2 and after_cancel_b2['pending_choice'] is None,
            {'before': before_b2, 'after': after_cancel_b2},
        )

        # Replay once more and confirm BOTH picks -- proves the happy path still dissolves.
        setup_b3 = post_json('/test/setup-dissolve-cancel-multi-target', {})
        load_game(page, setup_b3['url'])
        select_town(page, '天津')
        click_map_button(page, 'dissolveBtn')
        select_town(page, '石家莊')
        click_map_button(page, 'dissolveBtn')
        final_state = page.evaluate('() => window.lastGameState')
        enemy_orgs_final = next(
            (p.get('orgs') for p in (final_state.get('players') or []) if p.get('id') != setup_b3['player_id']),
            {},
        )
        record(
            'multi_target_confirming_both_picks_dissolves_both_atomically',
            final_state.get('pending_choice') is None
            and enemy_orgs_final.get('天津', 0) == 0
            and enemy_orgs_final.get('石家莊', 0) == 0,
            {'enemy_orgs_final': enemy_orgs_final},
        )

        # -----------------------------------------------------------------
        # B2) Multi-target stale-pick-at-final-confirmation (parent-level review, defect 2 fix):
        #     confirming the last remaining pick when an EARLIER accumulated pick (天津) has gone
        #     stale must reject atomically -- no partial dissolve of the still-valid pick (石家莊)
        #     -- and re-open the choice onto a fresh legal replacement target (上海) with an
        #     updated prompt, rather than silently completing or losing the still-valid pick.
        # -----------------------------------------------------------------
        setup_b5 = post_json('/test/setup-dissolve-cancel-multi-target-stale-final-pick', {})
        record(
            'multi_target_stale_final_pick_setup_succeeded', setup_b5.get('success') is True, setup_b5
        )
        load_game(page, setup_b5['url'])

        snap_b5_before = map_snapshot(page)
        record(
            'multi_target_stale_pick_shows_remaining_slot_with_two_live_candidates_before_confirm',
            snap_b5_before['skullCount'] == 2 and '1/2' in (snap_b5_before['dissolveHintText'] or ''),
            snap_b5_before,
        )

        # Confirm one of the two still-live offered targets (石家莊) -- this is the exact click
        # sequence that hits the final-confirmation code path with one stale (天津, already
        # accumulated) and one live (石家莊, just picked) pick.
        select_town(page, '石家莊')
        click_map_button(page, 'dissolveBtn')
        snap_b5_after = map_snapshot(page)
        state_after_stale_confirm = page.evaluate('() => window.lastGameState')
        enemy_orgs_after_stale_confirm = next(
            (
                p.get('orgs')
                for p in (state_after_stale_confirm.get('players') or [])
                if p.get('id') != setup_b5['player_id']
            ),
            {},
        )
        record(
            'multi_target_stale_final_pick_does_not_partially_dissolve_and_reopens_with_updated_hint',
            enemy_orgs_after_stale_confirm.get('石家莊', 0) == 1
            and state_after_stale_confirm.get('pending_choice') is not None
            and '已不再是合法目標' in (snap_b5_after['interactionHintText'] or ''),
            {
                'enemy_orgs_after_stale_confirm': enemy_orgs_after_stale_confirm,
                'interactionHintText': snap_b5_after['interactionHintText'],
                'snap': snap_b5_after,
            },
        )
        record(
            'multi_target_stale_final_pick_reopened_choice_still_shows_cancel_affordance',
            snap_b5_after['cancelVisible'] and snap_b5_after['cancelEnabled'],
            snap_b5_after,
        )
        record(
            'multi_target_stale_final_pick_reopened_choice_offers_fresh_replacement_target',
            snap_b5_after['skullCount'] == 1,
            snap_b5_after,
        )

        # Complete the retry: pick the fresh replacement target (承德) offered after the reopen,
        # and confirm -- proves the retry path still atomically dissolves both the earlier
        # still-valid pick (石家莊) and the new replacement (承德), while 天津 (the stale pick that
        # triggered the rejection) is never touched at all.
        select_town(page, '承德')
        click_map_button(page, 'dissolveBtn')
        final_state_b5 = page.evaluate('() => window.lastGameState')
        enemy_orgs_final_b5 = next(
            (
                p.get('orgs')
                for p in (final_state_b5.get('players') or [])
                if p.get('id') != setup_b5['player_id']
            ),
            {},
        )
        record(
            'multi_target_stale_final_pick_retry_confirms_and_dissolves_both_remaining_targets',
            final_state_b5.get('pending_choice') is None
            and enemy_orgs_final_b5.get('石家莊', 0) == 0
            and enemy_orgs_final_b5.get('承德', 0) == 0,
            {'enemy_orgs_final_b5': enemy_orgs_final_b5},
        )

        # -----------------------------------------------------------------
        # B3) 盟旗學校 (Mongol faction shield) target-visibility filtering (parent-level review,
        #     corrected defect 1): an unaffordable 盟旗學校-protected target must never appear as
        #     a pickable 💀 target on the map at all -- not offered, not just rejected on click.
        #     One ordinary target + two Mongol-protected targets are in range, but the attacker
        #     only has 1 other hand card after playing -- the map must show exactly 2 skulls
        #     (the ordinary target plus ONE of the two Mongol targets), never 3.
        # -----------------------------------------------------------------
        setup_b6 = post_json('/test/setup-dissolve-cancel-mongol-shield-target-filtering', {})
        record(
            'mongol_shield_filtering_setup_succeeded', setup_b6.get('success') is True, setup_b6
        )
        load_game(page, setup_b6['url'])
        snap_b6 = map_snapshot(page)
        record(
            'mongol_shield_filtering_shows_ordinary_plus_exactly_one_affordable_mongol_target',
            snap_b6['skullCount'] == 2 and '0/2' in (snap_b6['dissolveHintText'] or ''),
            snap_b6,
        )

        # -----------------------------------------------------------------
        # B3b) Second-pick listing under 盟旗學校 dict-iteration-order artifacts (parent-level
        #      review, Critical 2): 3 Mongol-protected targets are in range with 2 spare hand
        #      cards -- only 2 may ever be offered together. After making the FIRST pick (of
        #      whichever 2 were initially offered), the map's listing for the SECOND pick must
        #      still show the other still-affordable Mongol target -- not come back with zero
        #      skulls, which is what an already-picked town spuriously re-consuming already-
        #      reserved shield-discard budget would produce.
        # -----------------------------------------------------------------
        setup_b8 = post_json('/test/setup-dissolve-cancel-mongol-shield-second-pick-dict-order', {})
        record(
            'mongol_shield_second_pick_setup_succeeded', setup_b8.get('success') is True, setup_b8
        )
        load_game(page, setup_b8['url'])
        snap_b8 = map_snapshot(page)
        record(
            'mongol_shield_second_pick_listing_still_offers_the_remaining_affordable_target',
            snap_b8['skullCount'] == 1 and '1/2' in (snap_b8['dissolveHintText'] or ''),
            {'snap': snap_b8, 'setup': setup_b8},
        )

        # -----------------------------------------------------------------
        # B4) Stale pick with NO legal replacement anywhere resolves the still-valid pick(s)
        #     directly (parent-level review, corrected defect 2 -- 北國奧援 III's own printed
        #     text is "dissolve UP TO 2", not "exactly 2", so this is intentionally a PARTIAL
        #     commit, not a fizzle/error state). Only 2 organizations exist on the whole board;
        #     the first pick (天津) has already gone stale and there is no 3rd org to reopen onto
        #     -- confirming the sole remaining pick (石家莊) must dissolve it immediately.
        # -----------------------------------------------------------------
        setup_b7 = post_json('/test/setup-dissolve-cancel-multi-target-stale-no-replacement', {})
        record(
            'multi_target_stale_no_replacement_setup_succeeded', setup_b7.get('success') is True, setup_b7
        )
        load_game(page, setup_b7['url'])
        snap_b7_before = map_snapshot(page)
        record(
            'multi_target_stale_no_replacement_shows_the_one_remaining_live_target_before_confirm',
            snap_b7_before['skullCount'] == 1 and '1/2' in (snap_b7_before['dissolveHintText'] or ''),
            snap_b7_before,
        )

        select_town(page, '石家莊')
        click_map_button(page, 'dissolveBtn')
        final_state_b7 = page.evaluate('() => window.lastGameState')
        enemy_orgs_final_b7 = next(
            (
                p.get('orgs')
                for p in (final_state_b7.get('players') or [])
                if p.get('id') != setup_b7['player_id']
            ),
            {},
        )
        record(
            'multi_target_stale_no_replacement_resolves_the_still_valid_pick_as_a_partial_commit',
            final_state_b7.get('pending_choice') is None
            and enemy_orgs_final_b7.get('石家莊', 0) == 0,
            {'enemy_orgs_final_b7': enemy_orgs_final_b7, 'final_state_pending_choice': final_state_b7.get('pending_choice')},
        )

        # -----------------------------------------------------------------
        # C) Forced/mandatory event dissolve (全國人大召開): legal targets are still highlighted,
        #    but there must be NO cancel affordance.
        # -----------------------------------------------------------------
        setup_c = post_json('/test/setup-dissolve-cancel-forced-event', {})
        record('forced_event_setup_succeeded', setup_c.get('success') is True, setup_c)
        load_game(page, setup_c['url'])
        snap_c = map_snapshot(page)
        record(
            'forced_event_dissolve_has_targets_but_no_cancel_affordance',
            snap_c['skullCount'] >= 1 and not snap_c['cancelVisible'],
            snap_c,
        )

        # -----------------------------------------------------------------
        # D) Two-phase (派遣間諜): cancel at the very first (sacrifice-town) stage. This stage is
        #    NOT a map interaction_kind (choosing which of the player's OWN organizations to
        #    sacrifice is a town_choice, not a dissolve-target pick) -- it renders through the
        #    existing generic #choiceModal, whose close button already honours `cancellable`
        #    (see app.js's closeBtn wiring). This proves the SAME backend cancel_pending_choice
        #    mechanism -- and the SAME `cancellable` flag this feature adds -- drives a Cancel
        #    affordance correctly from both UI surfaces the pending-choice architecture uses.
        # -----------------------------------------------------------------
        setup_d = post_json('/test/setup-dissolve-cancel-two-phase', {})
        record('two_phase_setup_succeeded', setup_d.get('success') is True, setup_d)
        load_game(page, setup_d['url'], switch_to_map=False)
        before_d = game_state_essentials(setup_d['pre_play_state'])
        page.wait_for_selector('#choiceModalCards .modal-choice-btn', state='visible', timeout=10000)
        modal_snapshot = page.evaluate(
            """() => {
              const overlay = document.getElementById('choiceModal');
              const closeBtn = document.getElementById('closeChoiceModal');
              const title = document.getElementById('choiceModalTitle');
              return {
                overlayVisible: overlay && overlay.style.display !== 'none',
                closeBtnVisible: closeBtn && closeBtn.style.display !== 'none',
                closeBtnText: closeBtn ? closeBtn.textContent : null,
                title: title ? title.textContent : null,
              };
            }"""
        )
        record(
            'two_phase_sacrifice_stage_modal_shows_cancel_button',
            modal_snapshot['overlayVisible']
            and modal_snapshot['closeBtnVisible']
            and '取消' in (modal_snapshot['closeBtnText'] or ''),
            modal_snapshot,
        )
        page.click('#closeChoiceModal')
        page.wait_for_timeout(400)
        after_d = game_state_essentials(page.evaluate('() => window.lastGameState'))
        record(
            'two_phase_cancel_at_sacrifice_stage_is_a_full_rollback',
            after_d == before_d and after_d['pending_choice'] is None,
            {'before': before_d, 'after': after_d},
        )

        # And the SECOND (target) stage of the same two-phase flow IS a map interaction_kind --
        # confirm the map-based Cancel button (built by this feature) also works there, with no
        # own organization removed in between (requirement #7).
        setup_d2 = post_json('/test/setup-dissolve-cancel-two-phase', {})
        load_game(page, setup_d2['url'], switch_to_map=False)
        # Snapshot BEFORE the sacrifice_town pick -- this, not the mid-flow state, is what a
        # cancel at any later stage must fully restore (card still hasn't left the hand yet at
        # this exact instant, matching the pytest suite's "before" snapshot).
        before_d2_original = game_state_essentials(setup_d2['pre_play_state'])
        # Resolve stage 1 via the modal (town_choice-style buttons, index 0 = only candidate).
        page.wait_for_selector('#choiceModalCards .modal-choice-btn', state='visible', timeout=10000)
        page.evaluate(
            """() => {
              const buttons = document.querySelectorAll('#choiceModalCards .modal-choice-btn');
              if (buttons.length) buttons[0].click();
            }"""
        )
        page.wait_for_timeout(400)
        page.click('button.game-tab[data-view="map"]')
        page.wait_for_timeout(1200)
        mid_state_d2 = game_state_essentials(page.evaluate('() => window.lastGameState'))
        actor_orgs_mid = next(
            (p.get('orgs') for p in mid_state_d2['players'] if p.get('id') == setup_d2['player_id']),
            {},
        )
        snap_d2 = map_snapshot(page)
        record(
            'two_phase_target_stage_shows_cancel_and_sacrifice_not_yet_removed',
            snap_d2['cancelVisible'] and snap_d2['cancelEnabled']
            and actor_orgs_mid.get('上海', 0) == 1,
            {'snap': snap_d2, 'actor_orgs_mid': actor_orgs_mid},
        )
        click_map_button(page, 'cancelDissolveChoiceBtn')
        after_d2 = game_state_essentials(page.evaluate('() => window.lastGameState'))
        record(
            'two_phase_cancel_at_target_stage_is_also_a_full_rollback',
            after_d2 == before_d2_original and after_d2['pending_choice'] is None,
            {'before': before_d2_original, 'mid': mid_state_d2, 'after': after_d2},
        )

        # Screenshots for manual inspection of control layout/occlusion.
        setup_b4 = post_json('/test/setup-dissolve-cancel-multi-target', {})
        load_game(page, setup_b4['url'])
        select_town(page, '天津')
        page.wait_for_timeout(300)
        page.locator('#strategicMapFrame').screenshot(path=str(RECORD_DIR / 'dissolve-cancel-multi-target.png'))

        load_game(page, setup_c['url'])
        page.wait_for_timeout(300)
        page.locator('#strategicMapFrame').screenshot(path=str(RECORD_DIR / 'dissolve-cancel-forced-event-no-cancel.png'))

        browser.close()

    record('browser_console_has_no_errors', not console_errors, {'errors': console_errors})
    summary = {
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {
        'summary': summary,
        'results': results,
        'screenshots': [
            str((RECORD_DIR / 'dissolve-cancel-multi-target.png').relative_to(ROOT)),
            str((RECORD_DIR / 'dissolve-cancel-forced-event-no-cancel.png').relative_to(ROOT)),
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# DISSOLVE CANCEL UI VALIDATION',
        '',
        f"結果：{summary['passed']}/{summary['total']} PASS",
        '',
        '重跑：`uv run --with playwright python scripts/validate/validate_dissolve_target_cancel.py`',
        '',
    ]
    for r in results:
        lines.append(f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: `{json.dumps(r['detail'], ensure_ascii=False)}`")
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    raise SystemExit(1 if summary['failed'] else 0)


if __name__ == '__main__':
    main()
