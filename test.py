#!/usr/bin/env python3

import json
import re
from pathlib import Path

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

FAILED_MAPPINGS_PATH = Path("cache/failed_studio_mappings.json")

# Output file
EXCLUSIONS_PATH = Path("studio_exclusions.yaml")


# -------------------------------------------------------------------
# PRINT DETECTION
# -------------------------------------------------------------------

PRINT_PATTERNS = [
    r"pb\d+",  # 3068bpb023
    r"p\d+$",  # 3001p01
    r"pat\d+",  # patterned parts
    r"pr\d*$",
    r"op\d+",
]


def is_excluded_part(
    part_id: str,
    bricklink_name: str = "",
) -> bool:
    """
    Detect unsupported printed/decorated/cloth parts.
    """

    p = (part_id or "").lower()
    name = (bricklink_name or "").lower()

    # ------------------------------------------------------------
    # Cloth / fabric / sails / capes / flags
    # ------------------------------------------------------------

    CLOTH_TERMS = [
        "cloth",
        "plastic",
    ]

    for term in CLOTH_TERMS:
        if term in name:
            return True

    # ------------------------------------------------------------
    # Printed / patterned parts
    # ------------------------------------------------------------

    # Common BL printed notation
    if re.search(r"pb\d+", p):
        return True

    # Standard print suffixes
    for pattern in PRINT_PATTERNS:
        if re.search(pattern, p):
            return True

    # Examples:
    # 973pb1234c01
    # 3626cpb001
    # 3068bpb023

    if re.match(r"^\d+[a-z]+", p):

        if "pb" in p or re.search(r"p\d+", p):
            return True

    return False


# -------------------------------------------------------------------
# LOAD FAILED MAPPINGS
# -------------------------------------------------------------------


def load_failed_mappings(path: Path):

    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    parts = []

    #
    # failed_studio_mappings.json format:
    #
    # {
    #   "6223932": {
    #       "bricklink_part": "3626pb2108",
    #       "bricklink_name": "...",
    #   }
    # }
    #

    for _element_id, entry in data.items():

        if not isinstance(entry, dict):
            continue

        bricklink_part = entry.get("bricklink_part")

        if not bricklink_part:
            continue

        parts.append(
            {
                "part_id": bricklink_part.lower(),
                "bricklink_name": entry.get(
                    "bricklink_name",
                    "",
                ),
            }
        )

    return parts


# -------------------------------------------------------------------
# YAML WRITER
# -------------------------------------------------------------------


def build_yaml(parts):

    lines = []

    #
    # Deduplicate by part_id
    #

    deduped = {}

    for entry in parts:

        part_id = entry["part_id"]

        if part_id not in deduped:
            deduped[part_id] = entry

    #
    # Sorted stable output
    #

    for part_id in sorted(deduped.keys()):

        entry = deduped[part_id]

        bricklink_name = entry.get("bricklink_name", "").strip()

        lines.append(f"{part_id}:")
        lines.append("  reason: no digital geometry exists")
        lines.append("  category: N/A")
        lines.append("  skip_studio: true")

        #
        # Optional notes block
        #

        if bricklink_name:

            safe_name = bricklink_name.replace('"', "'")

            lines.append("  notes:")
            lines.append(f'    - "{safe_name}"')

        lines.append("")

    return "\n".join(lines)


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------


def main():

    failed_parts = load_failed_mappings(FAILED_MAPPINGS_PATH)

    printed_parts = []
    remaining_parts = []

    for entry in failed_parts:

        part_id = entry["part_id"]
        bricklink_name = entry["bricklink_name"]

        printed_parts.append(
            {
                "part_id": str(part_id),
                "bricklink_name": bricklink_name,
            }
        )

    # Write YAML exclusions
    yaml_output = build_yaml(printed_parts)

    EXCLUSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(EXCLUSIONS_PATH, "w", encoding="utf-8") as f:
        f.write(yaml_output)

    # ----------------------------------------------------------------
    # CLI OUTPUT
    # ----------------------------------------------------------------

    print("=" * 60)
    print(f"Printed exclusions written: {len(printed_parts)}")
    print(f"Remaining unresolved parts: {len(remaining_parts)}")
    print(f"Output file: {EXCLUSIONS_PATH}")
    print("=" * 60)

    if printed_parts:
        print("\nSample printed exclusions:")
        for p in printed_parts[:25]:
            print(f"  {p}")

    if remaining_parts:
        print("\nSample remaining unresolved:")
        for p in remaining_parts[:25]:
            print(f"  {p}")


if __name__ == "__main__":
    main()
