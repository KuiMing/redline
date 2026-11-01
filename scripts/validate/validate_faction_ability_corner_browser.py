#!/usr/bin/env python3
"""正式 Browser proof：指揮中心「陣營能力」位於右上角、隨機購買區最右邊。

幾何全部取自真實頁面（getBoundingClientRect），固定 1280×720 舞台等比例縮放：
  1. 陣營能力面板在隨機購買區內，貼齊右上角（右緣、上緣與隨機購買區同一側）。
  2. 面板在五張隨機購買卡的右邊，與五張卡、卡下方的選擇按鈕、購買操作列、結束行動、分頁、HUD 完全不重疊。
  3. 能力說明與發動按鈕完整可見（沒有被裁切）；字級可讀。
  4. 面板不在常設購買區；常設六張卡、隨機五張卡的位置與面板顯示與否無關（沒有版面位移）。
  5. 發動按鈕仍會開啟既有流程（澳門：賭徒耳語視窗）。
  6. 桌面與客廳（?display=living-room）兩種顯示；覆蓋澳門、改革開放派、自由派、民族祭儀各族（能力說明長度不同）。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_joycon_controller import post_json, start_server  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/records/ui-layout/faction-ability-corner-20261020"
REPORT_JSON = ROOT / "docs/records/ui-layout/FACTION_ABILITY_CORNER_VALIDATION.json"
REPORT_MD = ROOT / "docs/records/ui-layout/FACTION_ABILITY_CORNER_VALIDATION.md"

FACTIONS = (("aomen", "澳門"), ("reform_opening", "改革開放派"), ("liberals", "自由派"), ("zhuang", "壯族"))
EXPECTED_DESCRIPTIONS = {
    "aomen": "將 1 張手牌放入牌庫底，再猜牌庫頂牌購買費用的奇偶；猜中獲得 3 點宣傳與 3 點資金。",
    "reform_opening": "檢視牌庫頂 3 張牌，以任意順序放回牌庫頂，然後抽 1 張牌。",
    "liberals": "展示牌庫頂牌；購買費用為奇數時加入手牌，為偶數時放入棄牌堆。",
    "zhuang": "猜牌庫頂牌購買費用的奇偶。猜中獲得 2 點宣傳與 2 點資金；猜錯則選擇獲得 2 點宣傳或 2 點資金。",
}

GEOMETRY_JS = """() => {
  const rect = el => { if (!el) return null; const r = el.getBoundingClientRect(); return {left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height}; };
  const visible = el => !!el && getComputedStyle(el).display !== 'none' && el.getClientRects().length > 0;
  const panel = document.getElementById('factionActionPanel');
  const market = document.getElementById('randomMarketPanel');
  const stage = document.getElementById('designStage');
  const sr = stage.getBoundingClientRect();
  const scale = sr.width / stage.offsetWidth;
  const inStage = r => r && ({left: (r.left - sr.left) / scale, top: (r.top - sr.top) / scale, right: (r.right - sr.left) / scale, bottom: (r.bottom - sr.top) / scale, width: r.width / scale, height: r.height / scale});
  const randomCards = [...document.querySelectorAll('#purchaseRandom .purchase-card-item')];
  const staticCards = [...document.querySelectorAll('#purchaseStatic .purchase-card-item')];
  const info = document.getElementById('factionActionInfo');
  const button = document.querySelector('#factionActionButtons .base-choice-btn');
  const buyButton = document.getElementById('openPurchaseConfirmBtn');
  const description = document.querySelector('#factionActionInfo .faction-action-placeholder, #factionActionInfo .faction-action-result');
  const others = {
    controls: document.getElementById('purchaseSelectionControls'),
    endStep: document.getElementById('advanceStepBtn'),
    tabs: document.getElementById('gameTabs'),
    hud: document.getElementById('hud'),
    hand: document.getElementById('handPanel'),
    staticPanel: document.getElementById('controlPanel'),
  };
  return {
    stage: {w: stage.offsetWidth, h: stage.offsetHeight, scale, display: document.documentElement.dataset.display || 'desktop'},
    panelVisible: visible(panel),
    panelParent: panel.parentElement && panel.parentElement.id,
    insideStaticPanel: !!document.querySelector('#controlPanel #factionActionPanel'),
    panel: inStage(rect(panel)), market: inStage(rect(market)),
    randomCards: randomCards.map(c => inStage(rect(c))), staticCards: staticCards.map(c => inStage(rect(c))),
    others: Object.fromEntries(Object.entries(others).map(([k, el]) => [k, {visible: visible(el), rect: inStage(rect(el))}])),
    titleText: panel.querySelector('.panel-title')?.textContent.trim(),
    descriptionText: description ? description.textContent.trim() : '',
    buttonText: button ? button.textContent.trim() : '',
    buyButtonText: buyButton ? buyButton.textContent.trim() : '',
    button: inStage(rect(button)), description: inStage(rect(description)),
    panelClipped: panel.scrollHeight > panel.clientHeight + 1 || panel.scrollWidth > panel.clientWidth + 1,
    descriptionFontPx: description ? parseFloat(getComputedStyle(description).fontSize) : null,
    buttonFontPx: button ? parseFloat(getComputedStyle(button).fontSize) : null,
    randomCount: randomCards.length, staticCount: staticCards.length,
  };
}"""


def overlap(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return False
    return a["left"] < b["right"] - 0.5 and b["left"] < a["right"] - 0.5 and a["top"] < b["bottom"] - 0.5 and b["top"] < a["bottom"] - 0.5


def inside(inner: dict, outer: dict, slack: float = 0.5) -> bool:
    return (inner["left"] >= outer["left"] - slack and inner["right"] <= outer["right"] + slack
            and inner["top"] >= outer["top"] - slack and inner["bottom"] <= outer["bottom"] + slack)


def check_geometry(g: dict, mode: str, controls_open: bool) -> dict:
    panel, market = g["panel"], g["market"]
    cards = g["randomCards"]
    last_card = max(cards, key=lambda c: c["right"]) if cards else None
    controls = g["others"]["controls"]
    problems = []
    if not g["panelVisible"]:
        problems.append("面板不可見")
        return {"ok": False, "problems": problems}
    if g["stage"]["w"] != 1280 or g["stage"]["h"] != 720:
        problems.append("舞台不是固定 1280×720")
    if g["panelParent"] != "randomMarketPanel" or g["insideStaticPanel"]:
        problems.append("面板不在隨機購買區內／仍在常設購買區")
    if g["titleText"] != "陣營能力":
        problems.append("標題不是「陣營能力」")
    panel_top_gap = panel["top"] - market["top"]
    min_panel_top_gap = 40 if mode == "living-room" else 45
    if market["right"] - panel["right"] > 12 or not min_panel_top_gap <= panel_top_gap <= 60:
        problems.append(f"不在隨機購買區右側操作列下方：右距 {market['right'] - panel['right']:.1f}、上距 {panel_top_gap:.1f}")
    if panel["height"] >= market["height"] * 0.8:
        problems.append(f"陣營能力框未依內容縮短：面板高 {panel['height']:.1f}、隨機購買區高 {market['height']:.1f}")
    if g["randomCount"] != 5 or g["staticCount"] != 6:
        problems.append(f"購買卡數量改變：隨機 {g['randomCount']}、常設 {g['staticCount']}")
    if last_card and last_card["right"] > panel["left"] - 6:
        problems.append("面板沒有在五張隨機購買卡的右邊（留白不足）")
    for index, card in enumerate(cards):
        if overlap(panel, card):
            problems.append(f"遮住隨機購買卡 {index + 1}（含選擇按鈕）")
    if controls_open:
        if not g["others"]["controls"]["visible"] or overlap(panel, controls["rect"]):
            problems.append("購買操作列不可見或與面板重疊")
        elif market["right"] - controls["rect"]["right"] > 12:
            problems.append(f"購買操作列未回到原本右上位置：右距 {market['right'] - controls['rect']['right']:.1f}")
        elif panel["top"] - controls["rect"]["bottom"] < 7.5:
            problems.append(f"陣營能力框與購買操作列間距不足：{panel['top'] - controls['rect']['bottom']:.1f}")
    for name in ("endStep", "tabs", "hud", "hand", "staticPanel"):
        other = g["others"][name]
        if other["visible"] and overlap(panel, other["rect"]):
            problems.append(f"遮住 {name}")
    if not inside(panel, {"left": 0, "top": 0, "right": 1280, "bottom": 720}):
        problems.append("面板超出舞台")
    if not g["button"] or not inside(g["button"], panel) or not inside(g["description"], panel):
        problems.append("說明或按鈕不在面板內")
    if g["panelClipped"]:
        problems.append("說明或按鈕被裁切")
    min_font = 16 if mode == "living-room" else 11
    if (g["descriptionFontPx"] or 0) < min_font or (g["buttonFontPx"] or 0) < min_font:
        problems.append(f"字級過小：說明 {g['descriptionFontPx']}px、按鈕 {g['buttonFontPx']}px（至少 {min_font}px）")
    return {"ok": not problems, "problems": problems}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    errors: list[str] = []
    shots: list[str] = []
    details: dict = {}

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({"name": name, "passed": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {json.dumps(detail, ensure_ascii=False, default=str)[:600]}"), flush=True)

    server = None
    base = os.environ.get("REDLINE_BASE_URL", "").rstrip("/")
    if not base:
        server, base = start_server()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for mode in ("desktop", "living-room"):
                for faction_id, label in FACTIONS:
                    setup = post_json(base, "/test/setup-faction-action-used-proof", {"faction_id": faction_id, "faction_action_used": False})
                    context = browser.new_context(viewport={"width": 1280, "height": 720})
                    page = context.new_page()
                    page.on("console", lambda m, mode=mode: errors.append(f"[{mode}] {m.text}") if m.type == "error" else None)
                    page.on("pageerror", lambda e, mode=mode: errors.append(f"[{mode}] {e}"))
                    suffix = "&display=living-room" if mode == "living-room" else ""
                    page.goto(f"{base}/?game_id={setup['game_id']}&player_id={setup['player_id']}{suffix}", wait_until="networkidle")
                    page.wait_for_function("() => Boolean(window.lastGameState)")
                    page.wait_for_timeout(700)
                    page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
                    page.wait_for_timeout(300)

                    key = f"{mode}_{faction_id}"
                    g = page.evaluate(GEOMETRY_JS)
                    verdict = check_geometry(g, mode, controls_open=False)
                    record(f"{key}_ability_top_right_of_random_market_without_covering_anything", verdict["ok"], verdict["problems"])
                    record(
                        f"{key}_ability_copy_is_direct_without_redundant_faction_or_phase_prefix",
                        g["descriptionText"] == EXPECTED_DESCRIPTIONS[faction_id],
                        g["descriptionText"],
                    )
                    shot = OUT / f"{key}_1280x720.png"
                    page.screenshot(path=str(shot))
                    shots.append(str(shot.relative_to(ROOT)))

                    # 選一張隨機卡讓購買操作列出現，再檢查不重疊（走既有「選擇卡牌」按鈕）
                    page.locator("#purchaseRandom .purchase-card-select-button:not([disabled])").first.click()
                    page.wait_for_timeout(250)
                    g2 = page.evaluate(GEOMETRY_JS)
                    verdict2 = check_geometry(g2, mode, controls_open=True)
                    record(f"{key}_purchase_controls_visible_and_not_overlapped_by_ability", verdict2["ok"] and g2["others"]["controls"]["visible"], verdict2["problems"])
                    record(f"{key}_purchase_button_uses_compact_label", g2["buyButtonText"] == "購買", g2["buyButtonText"])
                    if faction_id == "aomen":
                        shot2 = OUT / f"{key}_with_purchase_controls_1280x720.png"
                        page.screenshot(path=str(shot2))
                        shots.append(str(shot2.relative_to(ROOT)))
                        # 發動按鈕仍開啟既有流程
                        page.locator("#factionActionButtons .base-choice-btn").click()
                        page.wait_for_timeout(300)
                        modal = page.evaluate("() => getComputedStyle(document.getElementById('factionActionModal')).display")
                        record(f"{key}_activate_button_still_opens_existing_gambler_modal", modal != "none", modal)
                        page.evaluate("() => document.getElementById('closeFactionActionModal').click()")
                        page.wait_for_timeout(200)
                    details[key] = {
                        "panel": g["panel"], "lastRandomCardRight": max(c["right"] for c in g["randomCards"]),
                        "descriptionLength": len(g["descriptionText"]), "descriptionFontPx": g["descriptionFontPx"],
                        "buttonText": g["buttonText"], "panelClipped": g["panelClipped"],
                    }
                    context.close()

                # 面板隱藏（本回合已用）時，卡牌位置不因面板而位移
                shown = browser.new_context(viewport={"width": 1280, "height": 720})
                hidden = browser.new_context(viewport={"width": 1280, "height": 720})
                snapshots = {}
                for name, used, ctx in (("shown", False, shown), ("hidden", True, hidden)):
                    setup = post_json(base, "/test/setup-faction-action-used-proof", {"faction_id": "aomen", "faction_action_used": used})
                    page = ctx.new_page()
                    suffix = "&display=living-room" if mode == "living-room" else ""
                    page.goto(f"{base}/?game_id={setup['game_id']}&player_id={setup['player_id']}{suffix}", wait_until="networkidle")
                    page.wait_for_function("() => Boolean(window.lastGameState)")
                    page.wait_for_timeout(700)
                    page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
                    page.wait_for_timeout(300)
                    snapshots[name] = page.evaluate(GEOMETRY_JS)
                    if name == "hidden":
                        shot = OUT / f"{mode}_ability_hidden_after_use_1280x720.png"
                        page.screenshot(path=str(shot))
                        shots.append(str(shot.relative_to(ROOT)))
                same_cards = (snapshots["shown"]["randomCards"] == snapshots["hidden"]["randomCards"]
                              and snapshots["shown"]["staticCards"] == snapshots["hidden"]["staticCards"])
                record(f"{mode}_card_positions_do_not_depend_on_ability_panel", same_cards and not snapshots["hidden"]["panelVisible"],
                       {"shown_visible": snapshots["shown"]["panelVisible"], "hidden_visible": snapshots["hidden"]["panelVisible"]})
                shown.close()
                hidden.close()
            browser.close()
    finally:
        if server:
            server.terminate()
    fatal = [e for e in errors if "favicon" not in e and "Failed to load resource" not in e and "net::ERR" not in e]
    record("browser_console_has_no_errors", not fatal, fatal[:5])

    summary = {"total": len(checks), "passed": sum(1 for c in checks if c["passed"])}
    summary["failed"] = summary["total"] - summary["passed"]
    report = {"generated_at": datetime.now().isoformat(timespec="seconds"), "summary": summary, "checks": checks,
              "details": details, "screenshots": shots}
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    REPORT_MD.write_text("\n".join([
        "# 陣營能力右上角位置 Browser 驗證", "", f"Summary: **{summary['passed']}/{summary['total']} passed**", "",
        *[f"- {'PASS' if c['passed'] else 'FAIL'}: `{c['name']}`" for c in checks], "",
        "截圖（固定 1280×720）：", *[f"- `{p}`" for p in shots], "",
    ]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    sys.exit(1 if summary["failed"] else 0)


if __name__ == "__main__":
    main()
