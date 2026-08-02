#!/usr/bin/env python3
"""Formal WebSocket/UI proof for canonical era and victory scopes across factions."""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "rules-audit" / "canonical-scopes"
REPORT_JSON = RECORD_DIR / "ALL_FACTION_SCOPE_UI_VALIDATION.json"
REPORT_MD = RECORD_DIR / "ALL_FACTION_SCOPE_UI_VALIDATION.md"
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

SCENARIOS = [
    {"name": "mongolia_outside", "total": 4, "inside": 0, "outside": 4, "era": False, "winner": None},
    {"name": "mongolia_inside", "total": 4, "inside": 4, "outside": 0, "era": True, "winner": None},
    {"name": "hong_kong_outside_victory", "total": 14, "inside": 0, "outside": 14, "era": False, "winner": None},
    {"name": "hong_kong_inside_victory", "total": 14, "inside": 14, "outside": 0, "era": True, "winner": "Actor"},
    {"name": "red_taiwan_without_taiwan", "total": 14, "inside": 0, "outside": 14, "era": None, "winner": None},
    {"name": "red_taiwan_with_taiwan", "total": 14, "inside": 0, "outside": 14, "era": None, "winner": "red_army"},
]


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())


def executable() -> str | None:
    configured = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if configured and Path(configured).exists():
        return configured
    cache = Path.home() / "Library/Caches/ms-playwright"
    candidates = []
    for pattern in [
        "chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell",
        "chromium-*/chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium",
    ]:
        candidates.extend(cache.glob(pattern))
    candidates = sorted((path for path in candidates if path.exists()), reverse=True)
    return str(candidates[0]) if candidates else None


def dismiss_non_victory_overlays(page) -> None:
    page.evaluate("""() => {
      if (typeof closeEventReveal === 'function') closeEventReveal();
      if (typeof closeEraAchievementModal === 'function') closeEraAchievementModal();
      if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
      let guard = document.getElementById('scope-proof-overlay-guard');
      if (!guard) {
        guard = document.createElement('style');
        guard.id = 'scope-proof-overlay-guard';
        guard.textContent = '#eventRevealModal,#eraAchievementModal,#factionActionModal{display:none!important;pointer-events:none!important}';
        document.head.appendChild(guard);
      }
      for (const id of ['eventRevealModal', 'eraAchievementModal', 'factionActionModal']) {
        const modal = document.getElementById(id);
        if (modal) { modal.classList.add('hidden'); modal.style.display = 'none'; }
      }
    }""")


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    checks = []
    console_errors = []
    screenshots = []

    def record(name, ok, detail=None):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    with sync_playwright() as pw:
        options: dict[str, object] = {"headless": True}
        browser_path = executable()
        if browser_path:
            options["executable_path"] = browser_path
        browser = pw.chromium.launch(**options)
        for scenario in SCENARIOS:
            setup = post_json("/test/setup-scope-audit-proof", {"scenario": scenario["name"]})
            if not setup.get("success"):
                raise RuntimeError(setup)
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: console_errors.append(str(error)))
            page.goto(
                f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
                wait_until="domcontentloaded",
            )
            page.locator("#gameShell").wait_for(state="visible", timeout=15000)
            page.wait_for_function(
                "expected => window.lastGameState?.players?.find(p => p.name === 'Actor')?.organization_counts?.total === expected",
                arg=scenario["total"], timeout=15000,
            )
            state = page.evaluate("window.lastGameState")
            actor = next(player for player in state["players"] if player["name"] == "Actor")
            counts = actor["organization_counts"]
            stage = state.get("my_era_stage")
            achieved = stage.get("achieved") if stage else None
            prefix = scenario["name"]
            record(f"{prefix}_server_counts", counts == {
                "total": scenario["total"],
                "inside_wall": scenario["inside"],
                "outside_wall": scenario["outside"],
            }, counts)
            record(f"{prefix}_count_conservation", counts["inside_wall"] + counts["outside_wall"] == counts["total"], counts)
            record(f"{prefix}_era_result", achieved is scenario["era"], {"actual": achieved, "expected": scenario["era"]})
            record(f"{prefix}_victory_result", state.get("winner") == scenario["winner"], {"actual": state.get("winner"), "expected": scenario["winner"]})

            dismiss_non_victory_overlays(page)
            if scenario["winner"]:
                page.locator("#victoryModal").wait_for(state="visible", timeout=5000)
                page.wait_for_timeout(500)
                dismiss_non_victory_overlays(page)
                page.locator("#victoryModal").wait_for(state="visible", timeout=5000)
                modal_text = page.locator("#victoryModal").inner_text()
                expected_name = "Actor" if scenario["winner"] == "Actor" else "紅軍"
                record(f"{prefix}_formal_victory_modal", expected_name in modal_text, modal_text)
            else:
                page.locator(".game-tab[data-view='log']").click()
                page.locator("#logView").wait_for(state="visible", timeout=5000)
                actor_card = page.locator(".player-status-card", has=page.locator(".player-status-name", has_text="Actor"))
                actor_card.wait_for(state="visible", timeout=5000)
                card_text = actor_card.inner_text()
                split = f"牆內 {scenario['inside']}／牆外 {scenario['outside']}"
                record(f"{prefix}_formal_status_split", split in card_text, card_text)

            if prefix in {"mongolia_outside", "mongolia_inside", "hong_kong_inside_victory", "red_taiwan_with_taiwan"}:
                shot = RECORD_DIR / f"{prefix}.png"
                page.screenshot(path=str(shot), full_page=True)
                screenshots.append(str(shot.relative_to(ROOT)))
            context.close()
        browser.close()

    record("browser_console_has_no_errors", not console_errors, console_errors)
    passed = sum(check["ok"] for check in checks)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed == len(checks) else "failed",
        "checks_passed": passed,
        "checks_total": len(checks),
        "checks": checks,
        "console_errors": console_errors,
        "screenshots": screenshots,
    }
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# 全陣營時代／勝利scope正式UI驗證", "",
        f"- 結果：**{passed}/{len(checks)} passed**", "",
        "## Scenarios", "",
        "- 蒙古：4個蒙古統治但牆外城鎮不觸發；4個牆內觸發。",
        "- 香港：14個牆外不勝；14個牆內勝利。",
        "- 紅軍：臺灣14個組織只有在臺灣玩家參戰時才勝利。", "",
        "## Checks", "",
    ]
    lines.extend(f"- {'PASS' if check['ok'] else 'FAIL'} `{check['name']}`" for check in checks)
    lines.extend(["", "## Screenshots", ""] + [f"- `{shot}`" for shot in screenshots] + [""])
    REPORT_MD.write_text("\n".join(lines))
    print(json.dumps({"status": payload["status"], "checks_passed": passed, "checks_total": len(checks)}, ensure_ascii=False))
    if payload["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
