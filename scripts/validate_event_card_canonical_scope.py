#!/usr/bin/env python3
"""Audit canonical scope for Redline event/era cards.

This validator compares raw event/era card declarations, structured event data,
and runtime deck construction assumptions. It writes a handoff record under
``docs/records/event-cards/`` and exits non-zero only for mechanical audit
failures such as malformed data or missing raw event rows in structured data.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "data" / "cards" / "event_and_era_cards.v1.1.json"
STRUCTURED_PATH = ROOT / "data" / "events_structured.v1.1.json"
RECORD_DIR = ROOT / "docs" / "records" / "event-cards"
STAMP = date.today().strftime("%Y_%m_%d")
JSON_OUT = RECORD_DIR / f"EVENT_CARD_CANONICAL_SCOPE_AUDIT_{STAMP}.json"
MD_OUT = RECORD_DIR / f"EVENT_CARD_CANONICAL_SCOPE_AUDIT_{STAMP}.md"

# Existing MVP used to adapt two raw era rows into event-like structured rows
# with shortened names. These rows are now canonical era-stage mechanics in
# ``data/era_structured.v1.1.json`` and must not stay in the runtime event deck.
ERA_STRUCTURED_ALIASES = {}

# Raw-vs-structured semantic deltas previously identified in TODO.md and now
# resolved by runtime validators. Keep this empty so stale deltas fail review
# by inspection instead of being treated as current gaps.
KNOWN_TODO_DELTAS = {}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def parse_raw_cards(rows: list[Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    section: str | None = None
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            continue
        if row[0] == "事件卡名稱":
            section = "event"
            continue
        if row[0] == "時代關卡名稱":
            section = "era"
            continue
        if section not in {"event", "era"}:
            raise AssertionError(f"raw row before section header: {row!r}")
        try:
            copies = int(row[5])
        except (TypeError, ValueError) as exc:
            raise AssertionError(f"invalid copy count for {row[0]}: {row[5]!r}") from exc
        cards.append(
            {
                "section": section,
                "name": row[0],
                "brief": row[1],
                "trigger_text": row[2],
                "success_or_red_text": row[3],
                "failure_or_rebel_text": row[4],
                "copies": copies,
            }
        )
    return cards


def summarize_effect(event: dict[str, Any] | None) -> dict[str, Any] | None:
    if not event:
        return None
    payload: dict[str, Any] = {
        "id": event.get("id"),
        "name": event.get("name"),
        "type": event.get("type"),
    }
    if event.get("type") == "mission":
        payload.update(
            {
                "trigger_type": (event.get("trigger") or {}).get("type"),
                "success_type": (event.get("success") or {}).get("type"),
                "failure_type": (event.get("failure") or {}).get("type"),
            }
        )
    elif event.get("type") == "auto":
        payload["effect_type"] = (event.get("effect") or {}).get("type")
    return payload


def main() -> int:
    raw_cards = parse_raw_cards(load_json(RAW_PATH))
    structured = load_json(STRUCTURED_PATH).get("events", [])
    if not isinstance(structured, list):
        raise AssertionError("structured events is not a list")

    structured_by_name = {event.get("name"): event for event in structured if isinstance(event, dict)}
    base_structured = [event for event in structured if "（副本）" not in str(event.get("name", ""))]
    base_names = {event.get("name") for event in base_structured}
    raw_counts = {card["name"]: card["copies"] for card in raw_cards}

    entries: list[dict[str, Any]] = []
    failures: list[str] = []
    for card in raw_cards:
        structured_name = card["name"] if card["name"] in structured_by_name else ERA_STRUCTURED_ALIASES.get(card["name"])
        event = structured_by_name.get(structured_name) if structured_name else None
        in_runtime_deck = bool(structured_name in base_names)
        if card["section"] == "event" and not event:
            failures.append(f"raw event missing from structured data: {card['name']}")
        status = "structured"
        if card["section"] == "era" and event:
            status = "partial_era_adapted"
        elif card["section"] == "era":
            status = "era_not_structured"
        elif not event:
            status = "event_missing_structured"
        notes: list[str] = []
        if card["name"] in KNOWN_TODO_DELTAS:
            notes.append(KNOWN_TODO_DELTAS[card["name"]])
        if card["section"] == "era" and not event:
            notes.append("Raw era-stage row is represented in data/era_structured.v1.1.json, not in structured event runtime data.")
        if card["section"] == "era" and event:
            notes.append("Unexpected: raw era-stage row is still represented as an event-like adaptation.")
        entries.append(
            {
                **card,
                "structured_name": structured_name,
                "structured": summarize_effect(event),
                "in_runtime_event_deck": in_runtime_deck,
                "runtime_copy_count": (raw_counts.get(structured_name, 1) if in_runtime_deck else 0),
                "scope_status": status,
                "notes": notes,
            }
        )

    structured_base_names = {event.get("name") for event in base_structured}
    represented_names = {entry["structured_name"] for entry in entries if entry.get("structured_name")}
    orphan_structured = sorted(name for name in structured_base_names if name not in represented_names)

    trigger_types: Counter[str] = Counter()
    effect_types: Counter[str] = Counter()
    for event in structured:
        if event.get("type") == "mission":
            trigger_types[(event.get("trigger") or {}).get("type", "none")] += 1
            effect_types[(event.get("success") or {}).get("type", "none")] += 1
            effect_types[(event.get("failure") or {}).get("type", "none")] += 1
        elif event.get("type") == "auto":
            effect_types[(event.get("effect") or {}).get("type", "none")] += 1
        else:
            effect_types["none"] += 1

    raw_event_copies = sum(card["copies"] for card in raw_cards if card["section"] == "event")
    runtime_deck_copies = sum(int(raw_counts.get(event.get("name"), 1) or 1) for event in base_structured)
    payload = {
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "paths": {
            "raw_cards": str(RAW_PATH.relative_to(ROOT)),
            "structured_events": str(STRUCTURED_PATH.relative_to(ROOT)),
        },
        "summary": {
            "raw_total_cards": len(raw_cards),
            "raw_event_rows": sum(1 for card in raw_cards if card["section"] == "event"),
            "raw_era_rows": sum(1 for card in raw_cards if card["section"] == "era"),
            "raw_event_declared_copies": raw_event_copies,
            "structured_rows_including_duplicates": len(structured),
            "structured_base_rows": len(base_structured),
            "structured_duplicate_rows": len(structured) - len(base_structured),
            "runtime_event_deck_copies": runtime_deck_copies,
            "raw_event_runtime_deck_copies": raw_event_copies,
            "era_rows_not_structured": sum(1 for entry in entries if entry["scope_status"] == "era_not_structured"),
            "era_rows_partially_adapted": sum(1 for entry in entries if entry["scope_status"] == "partial_era_adapted"),
            "known_raw_structured_deltas": len(KNOWN_TODO_DELTAS),
            "orphan_structured_base_rows": orphan_structured,
        },
        "runtime_vocabulary": {
            "trigger_types": dict(sorted(trigger_types.items())),
            "effect_types": dict(sorted(effect_types.items())),
        },
        "entries": entries,
        "canonical_scope_recommendation": [
            "Treat event-card runtime deck scope as the 13 raw event rows only.",
            "Treat the 8 raw era-stage rows as data/era_structured.v1.1.json era-stage mechanics, not event-deck cards.",
            "Do not reintroduce event-like adaptations for raw era rows unless the canonical scope is explicitly changed.",
        ],
    }

    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Event Card Canonical Scope Audit",
        "",
        f"Status: {payload['status']}",
        f"Raw source: `{payload['paths']['raw_cards']}`",
        f"Structured source: `{payload['paths']['structured_events']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Runtime vocabulary in structured data", ""])
    lines.append(f"- trigger_types: {payload['runtime_vocabulary']['trigger_types']}")
    lines.append(f"- effect_types: {payload['runtime_vocabulary']['effect_types']}")
    lines.extend(["", "## Card-by-card scope", ""])
    for entry in entries:
        structured_summary = entry["structured"] or {}
        if structured_summary.get("type") == "mission":
            runtime = f"mission trigger={structured_summary.get('trigger_type')} success={structured_summary.get('success_type')} failure={structured_summary.get('failure_type')}"
        elif structured_summary.get("type") == "auto":
            runtime = f"auto effect={structured_summary.get('effect_type')}"
        elif structured_summary.get("type"):
            runtime = structured_summary.get("type")
        else:
            runtime = "not structured"
        lines.append(f"- {entry['name']}")
        lines.append(f"  - section: {entry['section']}; copies: {entry['copies']}; status: {entry['scope_status']}")
        lines.append(f"  - structured_name: {entry['structured_name'] or 'none'}; in_runtime_event_deck: {entry['in_runtime_event_deck']}; runtime_copy_count: {entry['runtime_copy_count']}")
        lines.append(f"  - runtime: {runtime}")
        lines.append(f"  - raw trigger/condition: {entry['trigger_text']}")
        lines.append(f"  - raw success/red: {entry['success_or_red_text']}")
        lines.append(f"  - raw failure/rebel: {entry['failure_or_rebel_text']}")
        for note in entry["notes"]:
            lines.append(f"  - note: {note}")
    lines.extend(["", "## Canonical scope recommendation", ""])
    for item in payload["canonical_scope_recommendation"]:
        lines.append(f"- {item}")
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": payload["status"], "json": str(JSON_OUT), "md": str(MD_OUT), "summary": payload["summary"]}, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
