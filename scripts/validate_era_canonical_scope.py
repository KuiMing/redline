#!/usr/bin/env python3
"""Validate canonical scope and structured effect declarations for raw era-stage cards."""

import json
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW_PATH = BASE / "data" / "cards" / "event_and_era_cards.v1.1.json"
ERA_PATH = BASE / "data" / "era_structured.v1.1.json"
EVENT_PATH = BASE / "data" / "events_structured.v1.1.json"
RECORD_DIR = BASE / "docs" / "records" / "event-cards"
STAMP = date.today().strftime("%Y_%m_%d")
OUT_JSON = RECORD_DIR / f"ERA_CANONICAL_SCOPE_AUDIT_{STAMP}.json"
OUT_MD = RECORD_DIR / f"ERA_CANONICAL_SCOPE_AUDIT_{STAMP}.md"

EXPECTED_RAW_ERA_COUNT = 8
STATIC_SUPPLY_CARDS = {"內鬥", "分神"}


def load_json(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def raw_era_rows():
    rows = load_json(RAW_PATH)
    in_era = False
    out = []
    for row in rows:
        if not isinstance(row, list) or not row:
            continue
        if row[0] == "時代關卡名稱":
            in_era = True
            continue
        if not in_era:
            continue
        if not row[0]:
            continue
        out.append({
            "name": row[0],
            "description": row[1] if len(row) > 1 else "",
            "trigger_text": row[2] if len(row) > 2 else "",
            "red_suppression_text": row[3] if len(row) > 3 else "",
            "revolution_counterattack_text": row[4] if len(row) > 4 else "",
            "copies": int(row[5]) if len(row) > 5 and str(row[5]).isdigit() else None,
        })
    return out


def effect_types(effect_map):
    result = []
    for key in ("red_suppression", "revolution_counterattack"):
        effect = (effect_map or {}).get(key) or {}
        result.append(effect.get("type"))
    return result


def classify_runtime_status(era):
    effects = era.get("effects") or {}
    if not effects:
        return "trigger_only"
    types = set(t for t in effect_types(effects) if t)
    if not types:
        return "trigger_only"
    return "structured_effects_declared"


def validate_static_supply_effect(era):
    problems = []
    for key, effect in (era.get("effects") or {}).items():
        if effect.get("type") != "add_static_cards_to_discard":
            continue
        card = effect.get("card")
        if card not in STATIC_SUPPLY_CARDS:
            problems.append(f"{era['id']} {key} adds non-static card {card}")
        if effect.get("consume_static_supply") is not True:
            problems.append(f"{era['id']} {key} does not explicitly consume static supply")
    return problems


def build_audit():
    raw_rows = raw_era_rows()
    structured_eras = load_json(ERA_PATH)["eras"]
    structured_events = load_json(EVENT_PATH)["events"]
    era_by_name = {era["name"]: era for era in structured_eras}
    event_names = {event["name"] for event in structured_events}
    unbracketed_event_adaptations = {
        "[反賊]公知世代的終結": "公知世代的終結" in event_names,
        "[臺灣]綏靖派反對介入對岸": "臺灣綏靖派反對介入" in event_names,
    }

    entries = []
    failures = []
    static_supply_problems = []
    for raw in raw_rows:
        era = era_by_name.get(raw["name"])
        if not era:
            failures.append(f"missing structured era for {raw['name']}")
            entries.append({**raw, "structured": None, "runtime_status": "missing"})
            continue
        effects = era.get("effects") or {}
        if "red_suppression" not in effects or "revolution_counterattack" not in effects:
            failures.append(f"missing two-sided effects for {raw['name']}")
        static_supply_problems.extend(validate_static_supply_effect(era))
        entries.append({
            **raw,
            "structured": {
                "id": era.get("id"),
                "name": era.get("name"),
                "trigger": era.get("trigger"),
                "duration": era.get("duration"),
                "effects": effects,
            },
            "runtime_status": classify_runtime_status(era),
            "canonical_decision": "era_stage_mechanic_not_event_deck_card",
            "needs_runtime_followup": True,
        })

    if len(raw_rows) != EXPECTED_RAW_ERA_COUNT:
        failures.append(f"expected {EXPECTED_RAW_ERA_COUNT} raw era rows, got {len(raw_rows)}")
    for raw in raw_rows:
        if raw["name"] in event_names:
            failures.append(f"raw bracketed era row unexpectedly appears in event deck: {raw['name']}")
    failures.extend(static_supply_problems)

    payload = {
        "generated_at": date.today().isoformat(),
        "status": "passed" if not failures else "failed",
        "summary": {
            "raw_era_rows": len(raw_rows),
            "structured_era_rows": len(structured_eras),
            "raw_era_rows_represented_as_era_stage": sum(1 for raw in raw_rows if raw["name"] in era_by_name),
            "raw_bracketed_era_rows_in_event_deck": sum(1 for raw in raw_rows if raw["name"] in event_names),
            "legacy_event_like_adaptations_still_present": unbracketed_event_adaptations,
            "structured_effect_rows": sum(1 for e in entries if e.get("runtime_status") == "structured_effects_declared"),
            "failures": failures,
        },
        "canonical_decision": {
            "scope": "The 8 raw era-stage rows are canonical era-stage mechanics, not event-deck cards.",
            "reason": "Raw source labels these rows under 時代關卡名稱 and current UI/runtime already has EraEngine plus era achievement modal/pinned HUD.",
            "next_runtime_step": "Apply the declared red_suppression and revolution_counterattack effects through EraEngine with deterministic validators and focused UI proof.",
        },
        "entries": entries,
    }
    return payload


def write_reports(payload):
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Era Canonical Scope Audit",
        "",
        f"Generated: {payload['generated_at']}",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- {key}: {json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value}")
    lines.extend([
        "",
        "## Canonical decision",
        "",
        f"- Scope: {payload['canonical_decision']['scope']}",
        f"- Reason: {payload['canonical_decision']['reason']}",
        f"- Next runtime step: {payload['canonical_decision']['next_runtime_step']}",
        "",
        "## Card-by-card",
        "",
    ])
    for entry in payload["entries"]:
        lines.append(f"### {entry['name']}")
        lines.append("")
        lines.append(f"- canonical_decision: {entry.get('canonical_decision')}")
        lines.append(f"- runtime_status: {entry.get('runtime_status')}")
        lines.append(f"- trigger: {entry.get('trigger_text')}")
        lines.append(f"- 紅軍壓制: {entry.get('red_suppression_text')}")
        lines.append(f"- 革命反撲: {entry.get('revolution_counterattack_text')}")
        structured = entry.get("structured") or {}
        if structured:
            effects = structured.get("effects") or {}
            lines.append(f"- structured_id: {structured.get('id')}")
            lines.append(f"- red_suppression_effect: `{(effects.get('red_suppression') or {}).get('type')}`")
            lines.append(f"- revolution_counterattack_effect: `{(effects.get('revolution_counterattack') or {}).get('type')}`")
        lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main():
    payload = build_audit()
    write_reports(payload)
    print(json.dumps({"status": payload["status"], "summary": payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
