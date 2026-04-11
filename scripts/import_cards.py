import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
CARDS_DIR = BASE_DIR / "data" / "cards"

CARDS_DIR.mkdir(parents=True, exist_ok=True)


def clean_row(row):
    return {k.strip(): v.strip() for k, v in row.items() if k and v and v.strip()}


def import_support_cards():
    path = RAW_DIR / "support_cards.csv"
    cards = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = clean_row(row)
            if not row:
                continue
            cards.append(row)
    out = CARDS_DIR / "support_cards.v1.1.json"
    json.dump(cards, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def import_action_cards():
    path = RAW_DIR / "action_cards.csv"
    cards = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = clean_row(row)
            if not row:
                continue
            cards.append(row)
    out = CARDS_DIR / "action_cards.v1.1.json"
    json.dump(cards, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def import_event_cards():
    path = RAW_DIR / "event_and_era_cards.csv"
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if any(cell.strip() for cell in row):
                rows.append(row)
    out = CARDS_DIR / "event_and_era_cards.v1.1.json"
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def main():
    import_support_cards()
    import_action_cards()
    import_event_cards()
    print("Cards imported successfully.")


if __name__ == "__main__":
    main()
