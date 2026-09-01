#!/usr/bin/env python3
"""Browser proof：Lobby 使用大型陣營／根據地選擇視窗，且可重新開啟。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8768").rstrip("/")
OUT = ROOT / "docs/records/faction-ui/faction-picker-modal"
REPORT_JSON = OUT / "FACTION_PICKER_MODAL_VALIDATION.json"
REPORT_MD = OUT / "FACTION_PICKER_MODAL_VALIDATION.md"
SCREENSHOT_1280 = OUT / "uyghur_faction_picker_1280x720_20260824.png"
SCREENSHOT_1024 = OUT / "uyghur_faction_picker_1024x768_20260824.png"
ERA_SCREENSHOT_1280 = OUT / "manchuria_era_stage_1280x720_20260824.png"
ERA_SCREENSHOT_1024 = OUT / "manchuria_era_stage_1024x768_20260824.png"
DIRECT_BASE_SCREENSHOT = OUT / "direct_base_selection_1280x720_20260824.png"
DIRECT_BASE_SCREENSHOT_1024 = OUT / "direct_base_selection_1024x768_20260824.png"
BEIJING_BUTTON_SCREENSHOT = OUT / "beijing_base_button_1280x720_20260824.png"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        host = browser.new_page(viewport={"width": 1280, "height": 720})
        host.on("console", lambda message: console_errors.append(f"host:{message.text}") if message.type == "error" else None)
        host.on("pageerror", lambda error: console_errors.append(f"host:{error}"))
        host.goto(BASE_URL, wait_until="networkidle")
        host.fill("#playerName", "host")
        host.click("#createRoomBtn")
        host.wait_for_function("document.getElementById('factionPicker')?.style.display === 'flex'")

        initial = host.evaluate(
            """() => {
              const overlay = document.getElementById('factionPicker');
              const dialog = document.querySelector('.faction-picker-dialog');
              const rect = dialog?.getBoundingClientRect();
              return {
                visible: overlay?.style.display === 'flex' && overlay?.getAttribute('aria-hidden') === 'false',
                title: document.getElementById('factionPickerTitle')?.textContent.trim() || '',
                categories: Array.from(document.querySelectorAll('#factionList button')).map(button => button.textContent.trim()),
                detailPlaceholder: document.getElementById('factionDetailPanel')?.textContent.trim() || '',
                focusedId: document.activeElement?.id || '',
                rect: rect ? {left:rect.left,top:rect.top,right:rect.right,bottom:rect.bottom,width:rect.width,height:rect.height}:null,
              };
            }"""
        )
        record(
            "create_room_auto_opens_large_picker",
            initial["visible"] and initial["title"] == "選擇陣營與根據地" and len(initial["categories"]) >= 9 and "能力與觸發條件" in initial["detailPlaceholder"] and initial["focusedId"] == "closeFactionPickerBtn",
            initial,
        )
        rect = initial["rect"] or {}
        record(
            "picker_fits_1280x720",
            bool(rect) and rect["left"] >= 0 and rect["top"] >= 0 and rect["right"] <= 1280 and rect["bottom"] <= 720 and rect["width"] >= 1000,
            rect,
        )
        host.press("#closeFactionPickerBtn", "Shift+Tab")
        focus_trap = host.evaluate("document.activeElement?.closest('#factionPicker')?.id === 'factionPicker'")
        record("keyboard_focus_stays_inside_picker", focus_trap, {"focusedId": host.evaluate("document.activeElement?.id || ''"), "insidePicker": focus_trap})
        host.locator("#closeFactionPickerBtn").focus()

        host.locator("#factionList button", has_text="紅軍").click()
        host.wait_for_function("document.querySelector('#factionBaseList button')?.textContent.trim() === '北京'")
        beijing_rect = host.locator("#factionBaseList button", has_text="北京").bounding_box() or {}
        red_base_panel_rect = host.locator("#factionBaseList").bounding_box() or {}
        record(
            "single_base_button_keeps_normal_height",
            bool(beijing_rect) and bool(red_base_panel_rect) and 36 <= beijing_rect["height"] <= 80 and beijing_rect["width"] <= 180 and 112 <= red_base_panel_rect["height"] <= 120,
            {"button": beijing_rect, "panel": red_base_panel_rect},
        )
        host.screenshot(path=str(BEIJING_BUTTON_SCREENSHOT), full_page=True)

        host.locator("#factionList button", has_text="反賊").click()
        host.locator("#factionVariantList button", has_text="吳越").click()
        host.wait_for_function("document.querySelectorAll('#factionBaseList button').length >= 20")
        base_labels = host.locator("#factionBaseList button").all_text_contents()
        host.locator("#factionBaseList button", has_text="東京").click()
        host.wait_for_function("document.getElementById('factionDetailBases')?.textContent.includes('東京')")
        host.locator("#factionBaseList button", has_text="倫敦").click()
        host.wait_for_function("document.getElementById('factionDetailBases')?.textContent.includes('倫敦')")
        direct_base_state = host.evaluate(
            """() => ({
              labels: Array.from(document.querySelectorAll('#factionBaseList button')).map(button => button.textContent.trim()),
              activeBase: document.querySelector('#factionBaseList .active')?.textContent.trim() || '',
              detailBase: document.getElementById('factionDetailBases')?.textContent.trim() || '',
            })"""
        )
        record(
            "bases_are_directly_switchable_without_category_back_button",
            "東京" in base_labels and "倫敦" in base_labels and "任意東洋" not in base_labels and "任意英美城鎮" not in base_labels and not any("返回根據地類別" in label for label in direct_base_state["labels"]) and direct_base_state["activeBase"] == "倫敦" and "倫敦" in direct_base_state["detailBase"] and "東京" not in direct_base_state["detailBase"],
            direct_base_state,
        )
        rebel_base_panel_rect = host.locator("#factionBaseList").bounding_box() or {}
        record(
            "all_factions_use_rebel_base_panel_height",
            bool(red_base_panel_rect) and bool(rebel_base_panel_rect) and abs(red_base_panel_rect["height"] - rebel_base_panel_rect["height"]) <= 1 and 112 <= rebel_base_panel_rect["height"] <= 120,
            {"redArmy": red_base_panel_rect, "rebel": rebel_base_panel_rect},
        )
        host.screenshot(path=str(DIRECT_BASE_SCREENSHOT), full_page=True)
        host.set_viewport_size({"width": 1024, "height": 768})
        host.wait_for_timeout(120)
        direct_base_rect = host.evaluate(
            """() => {
              const list = document.getElementById('factionBaseList')?.getBoundingClientRect();
              const pane = document.querySelector('.faction-picker-selection-pane')?.getBoundingClientRect();
              return list && pane ? {listTop:list.top,listBottom:list.bottom,listHeight:list.height,listOffsetHeight:document.getElementById('factionBaseList').offsetHeight,paneTop:pane.top,paneBottom:pane.bottom}:null;
            }"""
        )
        record(
            "direct_base_list_remains_operable_at_1024x768",
            bool(direct_base_rect) and direct_base_rect["listTop"] >= direct_base_rect["paneTop"] and direct_base_rect["listBottom"] <= direct_base_rect["paneBottom"] and direct_base_rect["listOffsetHeight"] == 116,
            direct_base_rect,
        )
        host.screenshot(path=str(DIRECT_BASE_SCREENSHOT_1024), full_page=True)
        host.set_viewport_size({"width": 1280, "height": 720})

        host.locator("#factionVariantList button", has_text="民國派").click()
        host.wait_for_function("document.querySelectorAll('#factionBaseList button').length >= 50")
        inside_wall_labels = host.locator("#factionBaseList button").all_text_contents()
        record(
            "any_inside_wall_expands_to_real_towns",
            "北京" in inside_wall_labels and "上海" in inside_wall_labels and "任意牆內" not in inside_wall_labels and "任意牆內城鎮" not in inside_wall_labels,
            {"count": len(inside_wall_labels), "sample": inside_wall_labels[:12]},
        )

        host.locator("#factionList button", has_text="維吾爾").click()
        host.wait_for_function("document.querySelectorAll('#factionBaseList button').length >= 4")
        host.locator("#factionBaseList button", has_text="伊斯坦堡").click()
        host.wait_for_function("document.getElementById('confirmFactionBtn')?.offsetParent !== null")
        selected = host.evaluate(
            """() => ({
              detail: document.getElementById('factionDetailPanel')?.textContent.trim() || '',
              info: document.getElementById('factionPickerInfo')?.textContent.trim() || '',
              confirmText: document.getElementById('confirmFactionBtn')?.textContent.trim() || '',
              activeCategory: document.querySelector('#factionList .active')?.textContent.trim() || '',
              activeBase: document.querySelector('#factionBaseList .active')?.textContent.trim() || '',
            })"""
        )
        record(
            "selected_faction_shows_ability_restriction_and_win_condition",
            selected["activeCategory"] == "維吾爾" and selected["activeBase"] == "伊斯坦堡" and "游擊隊" in selected["detail"] and "新疆社會管控" in selected["detail"] and "獲勝條件" in selected["detail"] and selected["confirmText"] == "確認陣營與根據地",
            selected,
        )
        host.screenshot(path=str(SCREENSHOT_1280), full_page=True)

        host.click("#confirmFactionBtn")
        host.wait_for_function("document.getElementById('factionPicker')?.style.display === 'none'")
        post_confirm = host.evaluate(
            """() => ({
              modalHidden: document.getElementById('factionPicker')?.style.display === 'none',
              reopenText: document.getElementById('openFactionPickerBtn')?.textContent.trim() || '',
              reopenDisabled: document.getElementById('openFactionPickerBtn')?.disabled,
              roster: document.getElementById('lobbyRoster')?.textContent.trim() || '',
            })"""
        )
        record(
            "confirm_returns_to_lobby_with_reopen_button",
            post_confirm["modalHidden"] and post_confirm["reopenText"] == "變更陣營與根據地" and not post_confirm["reopenDisabled"] and "維吾爾" in post_confirm["roster"] and "伊斯坦堡" in post_confirm["roster"],
            post_confirm,
        )

        host.click("#openFactionPickerBtn")
        host.wait_for_function("document.getElementById('factionPicker')?.style.display === 'flex'")
        reopened = host.evaluate(
            """() => ({
              info: document.getElementById('factionPickerInfo')?.textContent.trim() || '',
              activeCategory: document.querySelector('#factionList .active')?.textContent.trim() || '',
              activeBase: document.querySelector('#factionBaseList .active')?.textContent.trim() || '',
            })"""
        )
        record(
            "reopen_restores_confirmed_selection",
            reopened["activeCategory"] == "維吾爾" and reopened["activeBase"] == "伊斯坦堡" and "維吾爾" in reopened["info"] and "伊斯坦堡" in reopened["info"],
            reopened,
        )

        host.set_viewport_size({"width": 1024, "height": 768})
        host.wait_for_timeout(120)
        host.screenshot(path=str(SCREENSHOT_1024), full_page=True)
        rect_1024 = host.evaluate(
            """() => { const rect=document.querySelector('.faction-picker-dialog')?.getBoundingClientRect(); return rect ? {left:rect.left,top:rect.top,right:rect.right,bottom:rect.bottom,width:rect.width,height:rect.height}:null; }"""
        )
        record(
            "picker_fits_1024x768",
            bool(rect_1024) and rect_1024["left"] >= 0 and rect_1024["top"] >= 0 and rect_1024["right"] <= 1024 and rect_1024["bottom"] <= 768,
            rect_1024,
        )

        host.set_viewport_size({"width": 1280, "height": 720})
        host.locator("#factionList button", has_text="滿洲").click()
        host.wait_for_function("document.querySelectorAll('#factionBaseList button').length >= 3")
        host.locator("#factionBaseList button", has_text="東京").click()
        host.wait_for_function("document.getElementById('factionDetailEra')?.textContent.includes('[滿洲]滿洲地方派系凝聚')")
        manchuria = host.evaluate(
            """() => ({
              ability: document.getElementById('factionDetailAbilities')?.textContent.trim() || '',
              era: document.getElementById('factionDetailEra')?.textContent.trim() || '',
              eraCardExists: Boolean(document.querySelector('#factionDetailEra .faction-picker-era-card')),
            })"""
        )
        expected_ability = "展現實力：在己方行動階段打出至少3張不同名稱的非起始牌，獲得3點宣傳或3點資金"
        record(
            "show_strength_uses_requested_wording_and_player_choice_copy",
            expected_ability in manchuria["ability"] and "：獲得3點宣傳或3點資金" not in manchuria["ability"] and "則可" not in manchuria["ability"],
            manchuria["ability"],
        )
        record(
            "selected_faction_shows_era_stage_before_confirmation",
            manchuria["eraCardExists"] and all(part in manchuria["era"] for part in ["[滿洲]滿洲地方派系凝聚", "觸發條件", "紅軍壓制", "革命反撲"]) and "效果期限" not in manchuria["era"],
            manchuria["era"],
        )
        host.evaluate("document.getElementById('factionDetailPanel').scrollTop = document.getElementById('factionDetailPanel').scrollHeight")
        host.wait_for_timeout(120)
        host.screenshot(path=str(ERA_SCREENSHOT_1280), full_page=True)
        host.set_viewport_size({"width": 1024, "height": 768})
        host.evaluate("document.getElementById('factionDetailPanel').scrollTop = document.getElementById('factionDetailPanel').scrollHeight")
        host.wait_for_timeout(120)
        host.screenshot(path=str(ERA_SCREENSHOT_1024), full_page=True)

        host.click("#confirmFactionBtn")
        host.wait_for_function("document.getElementById('factionPicker')?.style.display === 'none'")
        record("updated_manchuria_base_returns_to_lobby", True, {"display": "none", "base": "東京"})

        room_id = host.input_value("#roomId")
        visitor = browser.new_page(viewport={"width": 1280, "height": 720})
        visitor.on("console", lambda message: console_errors.append(f"visitor:{message.text}") if message.type == "error" else None)
        visitor.on("pageerror", lambda error: console_errors.append(f"visitor:{error}"))
        visitor.goto(BASE_URL, wait_until="networkidle")
        visitor.fill("#roomId", room_id)
        visitor.fill("#playerName", "visitor")
        visitor.click("#joinRoomBtn")
        visitor.wait_for_function("document.getElementById('factionPicker')?.style.display === 'flex'")
        join_state = visitor.evaluate(
            """() => ({
              visible: document.getElementById('factionPicker')?.style.display === 'flex',
              info: document.getElementById('factionPickerInfo')?.textContent.trim() || '',
              reopenEnabled: !document.getElementById('openFactionPickerBtn')?.disabled,
            })"""
        )
        record(
            "join_room_auto_opens_picker",
            join_state["visible"] and "請先選擇" in join_state["info"] and join_state["reopenEnabled"],
            join_state,
        )
        visitor.locator("#factionList button", has_text="蒙古").click()
        visitor.wait_for_function("document.querySelectorAll('#factionBaseList button').length >= 3")
        occupied_state = visitor.evaluate(
            """() => ({
              tokyoDisabled: Array.from(document.querySelectorAll('#factionBaseList button')).find(button => button.textContent.trim() === '東京')?.disabled,
              tokyoTitle: Array.from(document.querySelectorAll('#factionBaseList button')).find(button => button.textContent.trim() === '東京')?.title || '',
              newYorkDisabled: Array.from(document.querySelectorAll('#factionBaseList button')).find(button => button.textContent.trim() === '紐約')?.disabled,
            })"""
        )
        occupied_server_result = visitor.evaluate(
            """async () => (await fetch('/choose-faction', {
              method: 'POST', headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({game_id: gameId, player_id: playerId, faction_id: 'mongol', base_name: '東京'}),
            })).json()"""
        )
        record(
            "occupied_base_is_disabled_and_server_rejects_race",
            occupied_state["tokyoDisabled"] is True and occupied_state["newYorkDisabled"] is False and "已被其他玩家選擇" in occupied_state["tokyoTitle"] and occupied_server_result.get("error") == "Base already taken",
            {"ui": occupied_state, "server": occupied_server_result},
        )
        visitor.close()
        host.close()
        browser.close()

    record("browser_console_has_no_errors", not console_errors, console_errors)
    summary = {"total": len(checks), "passed": sum(1 for check in checks if check["passed"]), "failed": sum(1 for check in checks if not check["passed"])}
    report = {"summary": summary, "service": BASE_URL, "checks": checks, "screenshots": [str(path.relative_to(ROOT)) for path in [SCREENSHOT_1280, SCREENSHOT_1024, ERA_SCREENSHOT_1280, ERA_SCREENSHOT_1024, DIRECT_BASE_SCREENSHOT, DIRECT_BASE_SCREENSHOT_1024]]}
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text("\n".join(["# 大型陣營與根據地選擇視窗 Browser 驗證", "", f"Summary: **{summary['passed']}/{summary['total']} passed**", "", *[f"- {'PASS' if check['passed'] else 'FAIL'}: `{check['name']}`" for check in checks], ""]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
