#!/usr/bin/env python3
"""
Build a compact searchable cache from Studio elementInfoList.json

Input:
    data/studio_files/elementInfoList.json

Output:
    cache/element_lookup.json

Transforms:
{
    "4116931": [
        "30322",
        5
    ]
}

Where:
    key   = LEGO Element ID
    value = [BrickLink Part No, BrickLink Color ID]

Optimized for:
    - fast lookups
    - readable pretty JSON
    - compact structure
"""

from __future__ import annotations

import json
from pathlib import Path

INPUT_FILE = Path("data/studio_files/elementInfoList.json")
OUTPUT_DIR = Path("cache")
OUTPUT_FILE = OUTPUT_DIR / "element_lookup.json"


def load_source(path: Path) -> list[dict]:
    """Load original Studio element info list."""

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_lookup(data: list[dict]) -> tuple[dict[str, list], list[dict]]:
    """
    Build compact lookup table.

    Result format:
        {
            "elementId": ["part_no", color_id]
        }
    """

    lookup: dict[str, list] = {}
    skipped_entries: list[dict] = []

    for index, row in enumerate(data):
        element_id = row.get("elementId")
        part_no = row.get("blItemNo")
        color_id = row.get("blColorCode")

        missing_fields = []

        if not element_id:
            missing_fields.append("elementId")

        if not part_no:
            missing_fields.append("blItemNo")

        if color_id is None:
            missing_fields.append("blColorCode")

        if missing_fields:
            skipped_entries.append(
                {
                    "index": index,
                    "missing_fields": missing_fields,
                    "row": row,
                }
            )
            continue

        lookup[str(element_id)] = [
            str(part_no),
            int(color_id),
        ]

    return lookup, skipped_entries


def save_lookup(lookup: dict[str, list], path: Path) -> None:
    """Save pretty formatted lookup cache."""

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            lookup,
            f,
            indent=4,
            ensure_ascii=False,
            sort_keys=True,
        )

    size_mb = path.stat().st_size / (1024 * 1024)

    print("\nSaved lookup cache:")
    print(f"  {path}")
    print(f"  Size: {size_mb:.2f} MB")


def print_skipped(skipped_entries: list[dict]) -> None:
    """Print skipped invalid entries."""

    if not skipped_entries:
        print("\nNo invalid entries skipped.")
        return

    print(f"\nSkipped invalid entries: {len(skipped_entries):,}")

    for entry in skipped_entries:
        print("\n----------------------------------------")
        print(f"Row Index: {entry['index']}")
        print(f"Missing:   {', '.join(entry['missing_fields'])}")

        print("Raw Row:")
        print(
            json.dumps(
                entry["row"],
                indent=4,
                ensure_ascii=False,
            )
        )


def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    print(f"Loading: {INPUT_FILE}")

    raw_data = load_source(INPUT_FILE)

    print(f"Loaded rows: {len(raw_data):,}")

    lookup, skipped_entries = build_lookup(raw_data)

    print(f"Valid entries:   {len(lookup):,}")

    save_lookup(lookup, OUTPUT_FILE)

    print_skipped(skipped_entries)

    print("\nDone.")


if __name__ == "__main__":
    main()
