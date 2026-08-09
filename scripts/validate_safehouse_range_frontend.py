#!/usr/bin/env python3
"""Browser proof: 2026-08-09 playtest 回報 — 安全屋（`type: "passive"`）不該有任何專屬的
按鈕、面板或地圖捷徑。

使用者原話：「安全屋的功能，只有建立組織的時候才會發動啦～遊戲剛開始，根本不能建立組織，
根本不應該有安全屋的按鈕可以用。」

先前的修法只把「支援建立」側欄與地圖高亮的距離算式改成分牆內牆外，等於把不該存在的 UI
改得更精準，沒有解決真正的問題。這份驗證改為證明：

1. 開局（ACTION 階段、尚未出任何牌）指揮中心沒有任何安全屋／支援建立面板可以點。
2. 戰略地圖沒有安全屋專屬的建立高亮與「點一下就免出牌建組織」捷徑；點 2 格外的牆內城鎮
   不會建出任何組織。
3. 安全屋唯一正確的表現方式仍然有效：打出帶 `build` 效果的行動卡（組織經驗丙，range 1）
   之後，後端給的候選城鎮清單確實包含 2 格外的牆內城鎮（廣州／沙田），而且真的建得起來。
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
RECORD_DIR = ROOT / "docs" / "records" / "safehouse"
JSON_PATH = RECORD_DIR / "SAFEHOUSE_RANGE_FRONTEND_VALIDATION.json"
MD_PATH = RECORD_DIR / "SAFEHOUSE_RANGE_FRONTEND_VALIDATION.md"

BUILD_CARD = "組織經驗丙"  # 唯一效果就是 {"type": "build", "range": 1}，沒有其他前置選擇
# 香港城（牆內）出發：1 格鄰居全部牆內；2 格外的牆內城鎮只有安全屋 +1 才進得了候選清單。
ONE_STEP_INNER = {"九龍城", "柴灣", "澳門", "赤柱"}
TWO_STEP_INNER = {"廣州", "沙田", "油尖旺", "葵青", "西貢", "觀塘", "赤臘角"}


def setup_game(base: str, card: str | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"base": base}
    if card:
        payload["card"] = card
    return requests.post(
        f"{BASE_URL}/test/setup-safehouse-range-proof", json=payload, timeout=10
    ).json()


def open_command_center(page, setup: Dict[str, Any]) -> None:
    page.goto(
        f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
        wait_until="networkidle",
    )
    page.wait_for_function("() => Boolean(window.lastGameState)")
    page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
    page.wait_for_timeout(500)


def open_map_frame(page):
    page.evaluate(
        """() => {
          const btn = Array.from(document.querySelectorAll('button'))
            .find(b => b.textContent.trim() === '戰略地圖');
          if (btn) btn.click();
        }"""
    )
    page.wait_for_timeout(2000)
    return next((f for f in page.frames if "leaflet_game_map" in (f.url or "")), None)


def run_no_safehouse_ui_at_game_start(base: str) -> Dict[str, Any]:
    """開局（未出任何牌）指揮中心不該有任何安全屋／支援建立入口。"""
    setup = setup_game(base)
    failures: List[str] = []
    screenshot = RECORD_DIR / f"safehouse-no-button-at-game-start-{base}.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        open_command_center(page, setup)
        page.screenshot(path=str(screenshot))

        probe = page.evaluate(
            """() => {
              const ids = ['buildSupportPanel', 'buildSupportInfo', 'buildSupportOrigins', 'buildSupportTargets'];
              const clickable = Array.from(document.querySelectorAll('button, [onclick], .base-choice-btn'))
                .filter(el => el.offsetParent !== null)
                .map(el => (el.textContent || '').trim())
                .filter(text => text.includes('安全屋') || text.includes('支援建立'));
              const visibleText = (document.body.innerText || '');
              return {
                leftover_dom_ids: ids.filter(id => document.getElementById(id) !== null),
                render_fn_still_defined: (() => { try { return eval('typeof renderBuildSupport') !== 'undefined'; } catch (e) { return false; } })(),
                clickable_safehouse_labels: clickable,
                page_mentions_support_panel: visibleText.includes('支援建立'),
                page_mentions_safehouse: visibleText.includes('安全屋'),
                turn_phase: String(window.lastGameState?.turn_phase || ''),
                pending_choice: window.lastGameState?.pending_choice || null,
              };
            }"""
        )
        browser.close()

    if probe["leftover_dom_ids"]:
        failures.append(f"支援建立面板 DOM 仍存在：{probe['leftover_dom_ids']}")
    if probe["render_fn_still_defined"]:
        failures.append("renderBuildSupport() 仍然被定義，安全屋面板可能被重新掛回去")
    if probe["clickable_safehouse_labels"]:
        failures.append(f"仍有安全屋／支援建立的可點擊元素：{probe['clickable_safehouse_labels']}")
    if probe["page_mentions_support_panel"]:
        failures.append("畫面上仍出現「支援建立」字樣")
    if probe["pending_choice"]:
        failures.append(f"開局不該有待決選擇：{probe['pending_choice']}")
    if "action" not in probe["turn_phase"].lower():
        failures.append(f"測試前提不成立，目前不是行動階段：{probe['turn_phase']}")

    return {
        "name": f"no_safehouse_button_at_game_start_base_{base}",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "screenshot": str(screenshot.relative_to(ROOT)),
        "probe": probe,
    }


def run_map_has_no_safehouse_shortcut() -> Dict[str, Any]:
    """戰略地圖不該有安全屋專屬高亮，也不該能點 2 格外的牆內城鎮直接建組織。"""
    setup = setup_game("香港城")
    failures: List[str] = []
    screenshot = RECORD_DIR / "safehouse-map-no-shortcut.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        open_command_center(page, setup)
        frame = open_map_frame(page)
        if frame is None:
            browser.close()
            return {
                "name": "map_has_no_safehouse_build_shortcut",
                "status": "failed",
                "failures": ["找不到戰略地圖 iframe"],
                "screenshot": None,
            }

        frame.wait_for_function("() => Boolean(MAP_DATA) && Boolean(lastGameState)", timeout=15000)
        symbols = frame.evaluate(
            """() => {
              const probe = name => {
                try { return eval(`typeof ${name}`); } catch (e) { return 'undefined'; }
              };
              return {
                playerHasSafehouse: probe('playerHasSafehouse'),
                buildOptionsForTown: probe('buildOptionsForTown'),
                isInsideWallTown: probe('isInsideWallTown'),
                selectedBuildTargets: probe('selectedBuildTargets'),
                buildHighlightLayer: probe('buildHighlightLayer'),
              };
            }"""
        )
        for name, kind in symbols.items():
            if kind != "undefined":
                failures.append(f"地圖仍保留安全屋捷徑符號 {name}（typeof = {kind}）")

        # 選取自己的城鎮後，只該亮出移動候選，不該多出任何建立候選。
        frame.evaluate("() => selectTownForCurrentMapAction('香港城', { autoFocus: false })")
        frame.wait_for_timeout(500)
        page.screenshot(path=str(screenshot))

        # 直接點 2 格外的牆內城鎮（廣州）：沒有卡牌待決選擇時不該建出任何組織。
        clicked = frame.evaluate(
            """() => {
              const marker = currentMarkers.get('廣州');
              if (!marker) return false;
              marker.fire('click');
              return true;
            }"""
        )
        if not clicked:
            failures.append("地圖上找不到廣州的 marker，無法驗證點擊行為")
        frame.wait_for_timeout(1200)

        orgs = page.evaluate(
            """() => {
              const me = (window.lastGameState?.players || []).find(p => p.id === playerId);
              return me ? me.orgs : null;
            }"""
        )
        if orgs is None:
            failures.append("讀不到玩家組織狀態")
        elif set(orgs.keys()) != {"香港城"}:
            failures.append(f"點地圖竟然建出組織（應維持只有香港城）：{orgs}")

        browser.close()

    return {
        "name": "map_has_no_safehouse_build_shortcut",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "screenshot": str(screenshot.relative_to(ROOT)),
    }


def run_card_build_still_gets_safehouse_bonus() -> Dict[str, Any]:
    """正面案例：打出 build 效果的行動卡後，2 格外的牆內城鎮仍在候選清單，而且建得起來。"""
    setup = setup_game("香港城", card=BUILD_CARD)
    failures: List[str] = []
    screenshot = RECORD_DIR / "safehouse-card-build-choice-includes-two-step-inner.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        open_command_center(page, setup)

        played = page.evaluate(
            """(cardName) => {
              const btn = Array.from(document.querySelectorAll('.hand-card-action-btn'))
                .find(b => b.dataset.cardMode === 'action' && b.dataset.cardName === cardName);
              if (!btn) return 'button-not-found';
              if (btn.disabled) return 'button-disabled';
              btn.click();
              return 'clicked';
            }""",
            BUILD_CARD,
        )
        if played != "clicked":
            failures.append(f"沒能用手牌的「行動」按鈕打出{BUILD_CARD}：{played}")

        page.wait_for_timeout(1500)
        choice = page.evaluate("() => window.lastGameState?.pending_choice || null")
        towns = {entry.get("town") for entry in ((choice or {}).get("towns") or [])}
        if not choice:
            failures.append("打出卡牌後沒有出現建立組織的待決選擇")
        else:
            if choice.get("choice_key") != "card_build_organization":
                failures.append(f"待決選擇不是卡牌建立組織：{choice.get('choice_key')}")
            missing_one_step = ONE_STEP_INNER - towns
            if missing_one_step:
                failures.append(f"候選清單缺少 1 格內的牆內城鎮：{sorted(missing_one_step)}")
            missing_two_step = TWO_STEP_INNER - towns
            if missing_two_step:
                failures.append(
                    f"安全屋 +1 失效：候選清單缺少 2 格外的牆內城鎮 {sorted(missing_two_step)}"
                )

        frame = open_map_frame(page)
        if frame is None:
            failures.append("找不到戰略地圖 iframe")
        else:
            frame.wait_for_function("() => Boolean(MAP_DATA)", timeout=15000)
            frame.wait_for_timeout(800)
            page.screenshot(path=str(screenshot))
            frame.evaluate(
                """() => {
                  const marker = currentMarkers.get('廣州');
                  if (marker) marker.fire('click');
                }"""
            )
            frame.wait_for_timeout(600)
            frame.evaluate(
                """() => {
                  const btn = document.getElementById('directBuildBtn');
                  if (btn && !btn.disabled) btn.click();
                }"""
            )
            page.wait_for_timeout(1500)
            orgs = page.evaluate(
                """() => {
                  const me = (window.lastGameState?.players || []).find(p => p.id === playerId);
                  return me ? me.orgs : null;
                }"""
            )
            if not orgs or "廣州" not in orgs:
                failures.append(f"透過卡牌流程仍建不出 2 格外的牆內組織（廣州）：{orgs}")

        browser.close()

    return {
        "name": "card_triggered_build_still_offers_two_step_inner_town",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "screenshot": str(screenshot.relative_to(ROOT)),
        "choice_towns": sorted(t for t in towns if t),
    }


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        run_no_safehouse_ui_at_game_start("臺北"),
        run_no_safehouse_ui_at_game_start("香港城"),
        run_map_has_no_safehouse_shortcut(),
        run_card_build_still_gets_safehouse_bonus(),
    ]
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] != "passed"),
        "results": results,
    }
    JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Safehouse — 被動能力不該有專屬按鈕（Validation）",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        f"Summary: {summary['passed']} passed / {summary['failed']} failed / {summary['total']} total.",
        "",
        "## Scope",
        "- 安全屋在 `data/factions/all_faction.integrated.v2.json` 是 `type: \"passive\"`，",
        "  只該在玩家用正常方式（打出帶 `build` 效果的行動卡）建立組織時，把牆內目標的",
        "  可建立距離 +1；不該有自己的按鈕、面板或地圖捷徑。",
        "- 負面驗證：開局（行動階段、未出任何牌）指揮中心沒有「支援建立」面板、沒有任何",
        "  安全屋字樣的可點擊元素；戰略地圖沒有安全屋專屬高亮，點 2 格外的牆內城鎮不會建組織。",
        "- 正面驗證：以香港城根據地打出「組織經驗丙」（`build` range 1）後，候選清單仍包含",
        "  1 格內的牆內城鎮與 2 格外的牆內城鎮（廣州／沙田等），並且實際建得起來。",
        "",
    ]
    for r in results:
        lines.append(f"## {r['name']} — {r['status']}")
        lines.append("")
        if r.get("screenshot"):
            lines.append(f"- screenshot: `{r['screenshot']}`")
        if r.get("choice_towns"):
            lines.append(f"- 卡牌建立候選城鎮: {r['choice_towns']}")
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
