#!/usr/bin/env python3

import json

INPUT_FILE = "data/ldraw/StudioPartDefinition2.txt"
OUTPUT_FILE = "cache/studio_part_definitions.json"

lookup = {}

with open(
    INPUT_FILE,
    encoding="utf-8",
    errors="ignore",
) as f:

    for line in f:

        line = line.strip()

        if not line:
            continue

        #
        # Split tab-separated fields
        #

        cols = line.split("\t")

        #
        # Need enough columns
        #

        if len(cols) < 5:
            continue

        #
        # Based on observed structure:
        #
        # cols[2] = BrickLink item no
        # cols[4] = LDraw filename
        #

        bl_id = cols[2].strip().lower()
        ldraw_file = cols[4].strip().lower()

        if not bl_id or not ldraw_file:
            continue

        #
        # Ensure .dat
        #

        if not ldraw_file.endswith(".dat"):
            ldraw_file += ".dat"

        lookup[bl_id] = ldraw_file

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        lookup,
        f,
        indent=2,
        sort_keys=True,
    )

print(f"Created lookup with {len(lookup)} entries")
print(f"Saved to: {OUTPUT_FILE}")
