import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ALL_FACTIONS_FILE = DATA_DIR / "factions" / "all_faction.json"
OUTPUT_DIR = DATA_DIR / "factions"


def main():
    if not ALL_FACTIONS_FILE.exists():
        raise FileNotFoundError(f"Cannot find {ALL_FACTIONS_FILE}")

    with open(ALL_FACTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    factions = data.get("factions", [])
    schema_version = data.get("schema_version", "unknown")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for faction in factions:
        faction_id = faction["id"]
        output_path = OUTPUT_DIR / f"{faction_id}.v{schema_version}.json"

        with open(output_path, "w", encoding="utf-8") as out:
            json.dump({
                "schema_version": schema_version,
                **faction
            }, out, ensure_ascii=False, indent=2)

        print(f"Generated: {output_path.name}")

    print("\nAll factions split successfully.")


if __name__ == "__main__":
    main()
