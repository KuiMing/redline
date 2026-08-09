#!/usr/bin/env python3
"""Browser proof：2026-08-09 playtest 回報的兩件事。

一、時代關卡的「無法無視距離建立牆內組織」（`restrict_ignore_distance_build`，
    [反賊]公知世代的終結／[哈薩克]伊塔事件）生效後，思想家／組織經驗甲／東洋奧援
    只能在己方組織 1 格內（另有增加建立距離的能力時為 2 格）建立牆內組織；牆外仍
    維持無視距離；不屬於該時代 target_camp 的玩家完全不受影響。

二、「時代關卡達成」浮窗的縮小鍵原本在浮窗左下角，且縮小後任何玩家都再也點不開說明。
    修法後按鈕移到浮窗右上角，縮小後的釘選卡片變成可點，且**每位玩家**（不只觸發者）
    都能重新叫出完整的達成條件／紅軍壓制／革命反撲說明。

前置：伺服器需已在 http://127.0.0.1:8000 執行。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "http://127.0.0.1:8000"
RECORD_DIR = ROOT / "docs" / "records" / "era-restrict-ignore-distance"
JSON_PATH = RECORD_DIR / "ERA_RESTRICT_IGNORE_DISTANCE_VALIDATION.json"
MD_PATH = RECORD_DIR / "ERA_RESTRICT_IGNORE_DISTANCE_VALIDATION.md"


def setup_game(**payload: Any) -> Dict[str, Any]:
    return requests.post(
        f"{BASE_URL}/test/setup-era-restrict-ignore-distance-proof", json=payload, timeout=15
    ).json()


def open_command_center(page, game_id: str, player_id: str) -> None:
    page.goto(f"{BASE_URL}/?game_id={game_id}&player_id={player_id}", wait_until="networkidle")
    page.wait_for_function("() => Boolean(window.lastGameState)")
    page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
    page.wait_for_timeout(400)


def play_ideologue_and_read_candidates(page) -> Dict[str, Any]:
    """用手牌的「行動」按鈕正常打出思想家，走完可選的移除本牌步驟，
    回傳前端權威狀態裡的 card_build_organization 候選城鎮。"""
    page.evaluate(
        """() => {
      const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === '行動');
      if (btn) btn.click();
    }"""
    )
    page.wait_for_timeout(1200)
    for _ in range(4):
        choice = page.evaluate(
            """() => {
          const s = window.lastGameState || {};
          const c = s.pending_choice;
          return c ? {key: c.choice_key, towns: (c.towns || []).map(t => t.town || t)} : null;
        }"""
        )
        if choice and choice["key"] == "card_build_organization":
            return choice
        page.evaluate(
            "() => { document.querySelector('#choiceModalCards .modal-choice-btn')?.click(); }"
        )
        page.wait_for_timeout(1200)
    return {"key": None, "towns": []}


def case_card_build(page, name: str, setup_payload: Dict[str, Any], shot: Path) -> Dict[str, Any]:
    setup = setup_game(**setup_payload)
    if setup.get("error"):
        return {"name": name, "status": "failed", "failures": [setup["error"]]}
    open_command_center(page, setup["game_id"], setup["player_id"])
    page.evaluate("() => { if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement(); }")
    page.wait_for_timeout(300)
    choice = play_ideologue_and_read_candidates(page)
    page.screenshot(path=str(shot))

    towns = set(choice["towns"])
    expected_inner = set(setup["ideologue_inner"])
    expected_outer_count = setup["ideologue_outer_count"]
    ui_inner = towns & set(json.loads(json.dumps(setup["ideologue_inner"]))) if expected_inner else set()
    failures: List[str] = []
    if choice["key"] != "card_build_organization":
        failures.append("沒有進入卡牌建立組織的城鎮選擇")
    if ui_inner != expected_inner:
        failures.append(f"牆內候選不符：UI={sorted(ui_inner)} 期望={sorted(expected_inner)}")
    if len(towns) != len(expected_inner) + expected_outer_count:
        failures.append(
            f"候選總數不符：UI={len(towns)} 期望={len(expected_inner) + expected_outer_count}"
        )
    return {
        "name": name,
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "era": setup.get("era_name"),
        "origin": setup["origin"],
        "near_inner": setup["near_inner"],
        "ui_candidate_count": len(towns),
        "ui_inner": sorted(ui_inner),
        "ui_outer_count": len(towns) - len(ui_inner),
        "screenshot": str(shot.relative_to(ROOT)),
    }


def case_support_downgrade() -> Dict[str, Any]:
    """東洋奧援 tier-3（牆內任意）在時代生效後降級為 tier-2（1 格內）的候選清單。"""
    failures: List[str] = []
    detail = {}
    for label, payload in (
        ("rebels", {"era": "rebels", "faction": "liberals", "origin": "上海"}),
        ("kazakh", {"era": "kazakh", "faction": "kazakh", "origin": "烏魯木齊"}),
    ):
        s = setup_game(**payload)
        base = setup_game(**{**payload, "era": None})
        detail[label] = {
            "anywhere": s["east_asia_support_anywhere"],
            "near": s["east_asia_support_near"],
            "baseline_anywhere_count": len(base["east_asia_support_anywhere"]),
        }
        if s["east_asia_support_anywhere"] != s["east_asia_support_near"]:
            failures.append(f"{label}：tier-3 沒有降級為 1 格內")
        if len(base["east_asia_support_anywhere"]) <= len(s["east_asia_support_near"]):
            failures.append(f"{label}：對照組（時代未觸發）沒有比降級後更寬")
    return {
        "name": "east_asia_support_tier3_downgraded_by_era",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "detail": detail,
    }


def case_era_modal_reopen(ctx) -> Dict[str, Any]:
    setup = setup_game(era="rebels", faction="liberals", origin="上海")
    failures: List[str] = []
    shots = {}

    page = ctx.new_page()
    open_command_center(page, setup["game_id"], setup["player_id"])
    geo = page.evaluate(
        """() => {
      const btn = document.getElementById('eraAchievementMinimizeBtn');
      const glass = document.querySelector('#eraAchievementModal .era-achievement-glass');
      const b = btn.getBoundingClientRect(), g = glass.getBoundingClientRect();
      return {leftFrac: (b.x - g.x) / g.width, topFrac: (b.y - g.y) / g.height, text: btn.textContent.trim()};
    }"""
    )
    shot = RECORD_DIR / "era-modal-minimize-button-top-right.png"
    page.screenshot(path=str(shot))
    shots["minimize_button"] = str(shot.relative_to(ROOT))
    # 使用者要求「不要放在左下角」：右上角＝水平靠右、垂直靠上
    if not (geo["leftFrac"] > 0.6 and geo["topFrac"] < 0.2):
        failures.append(f"縮小鍵不在浮窗右上角：{geo}")

    page.click("#eraAchievementMinimizeBtn")
    page.wait_for_timeout(500)
    minimized = page.evaluate(
        "() => ({modal: document.getElementById('eraAchievementModal').style.display,"
        " pins: document.querySelectorAll('.era-pin-card').length})"
    )
    shot = RECORD_DIR / "era-modal-minimized-pin.png"
    page.screenshot(path=str(shot))
    shots["minimized"] = str(shot.relative_to(ROOT))
    if minimized["modal"] != "none" or minimized["pins"] < 1:
        failures.append(f"縮小後狀態不正確：{minimized}")

    page.click(".era-pin-card")
    page.wait_for_timeout(500)
    reopened = page.evaluate(
        """() => ({
      modal: document.getElementById('eraAchievementModal').style.display,
      title: document.getElementById('eraAchievementTitle').textContent,
      condition: document.getElementById('eraAchievementCondition').textContent,
      suppression: document.getElementById('eraAchievementSuccess').textContent,
      counterattack: document.getElementById('eraAchievementFail').textContent,
    })"""
    )
    shot = RECORD_DIR / "era-modal-reopened-by-trigger-player.png"
    page.screenshot(path=str(shot))
    shots["reopened_trigger_player"] = str(shot.relative_to(ROOT))
    if reopened["modal"] != "flex" or setup["era_name"] not in reopened["title"]:
        failures.append(f"觸發方點釘選卡片沒有重新開啟浮窗：{reopened}")

    # 第二位玩家（紅軍，不是觸發者）：先關掉浮窗，再點釘選卡片
    page2 = ctx.new_page()
    open_command_center(page2, setup["game_id"], setup["opponent_player_id"])
    page2.evaluate("() => { document.getElementById('eraAchievementModal').style.display = 'none'; }")
    page2.wait_for_timeout(300)
    page2.click(".era-pin-card")
    page2.wait_for_timeout(500)
    reopened2 = page2.evaluate(
        """() => ({
      modal: document.getElementById('eraAchievementModal').style.display,
      title: document.getElementById('eraAchievementTitle').textContent,
      condition: document.getElementById('eraAchievementCondition').textContent,
      suppression: document.getElementById('eraAchievementSuccess').textContent,
    })"""
    )
    shot = RECORD_DIR / "era-modal-reopened-by-second-player.png"
    page2.screenshot(path=str(shot))
    shots["reopened_second_player"] = str(shot.relative_to(ROOT))
    if reopened2["modal"] != "flex" or setup["era_name"] not in reopened2["title"]:
        failures.append(f"第二位玩家點釘選卡片沒有重新開啟浮窗：{reopened2}")
    for field in ("condition", "suppression"):
        if "暫缺" in (reopened2.get(field) or ""):
            failures.append(f"第二位玩家看到的說明缺內容：{field}={reopened2.get(field)}")

    page.close()
    page2.close()
    return {
        "name": "era_achievement_modal_button_top_right_and_reopenable_by_every_player",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "minimize_button_position": geo,
        "trigger_player_reopened": reopened,
        "second_player_reopened": reopened2,
        "screenshots": shots,
    }


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1500, "height": 950})
        page = ctx.new_page()
        results.append(case_card_build(
            page, "rebels_era_ideologue_limited_to_one_step_inside_wall",
            {"card": "思想家", "era": "rebels"},
            RECORD_DIR / "ideologue-rebels-era-active.png"))
        results.append(case_card_build(
            page, "rebels_era_with_build_range_bonus_extends_to_two_steps",
            {"card": "思想家", "era": "rebels", "build_range_bonus": 1},
            RECORD_DIR / "ideologue-rebels-era-bonus.png"))
        results.append(case_card_build(
            page, "no_era_control_still_ignores_distance",
            {"card": "思想家", "era": None},
            RECORD_DIR / "ideologue-no-era-control.png"))
        results.append(case_card_build(
            page, "kazakh_era_applies_the_same_restriction",
            {"card": "思想家", "era": "kazakh", "faction": "kazakh", "origin": "烏魯木齊"},
            RECORD_DIR / "ideologue-kazakh-era-active.png"))
        results.append(case_card_build(
            page, "other_camp_unaffected_while_rebels_era_active",
            {"card": "思想家", "era": "rebels", "faction": "kazakh", "origin": "烏魯木齊"},
            RECORD_DIR / "ideologue-other-camp-unaffected.png"))
        page.close()
        results.append(case_support_downgrade())
        results.append(case_era_modal_reopen(ctx))
        browser.close()

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] != "passed"),
        "results": results,
    }
    JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 時代關卡「無法無視距離建立牆內組織」＋ 時代關卡達成浮窗重新開啟（Validation）",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        f"Summary: {summary['passed']} passed / {summary['failed']} failed / {summary['total']} total.",
        "",
        "可重跑指令（需先啟動伺服器於 127.0.0.1:8000）：",
        "`python3 scripts/validate_era_restrict_ignore_distance.py`",
        "",
    ]
    for r in results:
        lines.append(f"## {r['name']} — {r['status']}")
        lines.append("")
        for key in ("era", "origin", "near_inner", "ui_candidate_count", "ui_inner", "ui_outer_count"):
            if key in r:
                lines.append(f"- {key}: {r[key]}")
        if r.get("minimize_button_position"):
            lines.append(f"- 縮小鍵在浮窗內的相對位置: {r['minimize_button_position']}")
        if r.get("screenshot"):
            lines.append(f"- screenshot: `{r['screenshot']}`")
        for label, path in (r.get("screenshots") or {}).items():
            lines.append(f"- screenshot({label}): `{path}`")
        if r["failures"]:
            lines.append(f"- failures: {r['failures']}")
        lines.append("")
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"{summary['passed']} passed / {summary['failed']} failed")
    if summary["failed"]:
        for r in results:
            if r["status"] != "passed":
                print(f"  [{r['name']}] {r['failures']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
