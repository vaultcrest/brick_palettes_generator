#!/usr/bin/env python3

import json
from pathlib import Path

# ------------------------------------------------------------
# PATHS
# ------------------------------------------------------------

CACHE_DIR = Path("cache")

LEGO_TO_BL_CACHE_FILE = CACHE_DIR / "lego_to_bricklink.json"

MANUAL_OVERRIDE_FILE = CACHE_DIR / "manual_overrides.json"

BL_TO_LEGO_CACHE_FILE = CACHE_DIR / "bricklink_to_lego.json"

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------


def load_json_file(path, default):

    if path.exists():

        try:

            with open(
                path,
                encoding="utf-8",
            ) as f:

                return json.load(f)

        except Exception as e:

            print(f"Failed loading {path}: {e}")

    return default


def save_json_file(path, data):

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            sort_keys=True,
        )


# ------------------------------------------------------------
# LOAD SOURCES
# ------------------------------------------------------------

lego_to_bl_cache = load_json_file(
    LEGO_TO_BL_CACHE_FILE,
    {},
)

manual_overrides = load_json_file(
    MANUAL_OVERRIDE_FILE,
    {},
)

# ------------------------------------------------------------
# MERGE SOURCES
# ------------------------------------------------------------

combined = {}

#
# Cache mappings
#

for (
    element_id,
    mapping,
) in lego_to_bl_cache.items():

    combined[str(element_id)] = mapping

#
# Manual overrides win
#

for (
    element_id,
    mapping,
) in manual_overrides.items():

    combined[str(element_id)] = mapping

# ------------------------------------------------------------
# BUILD REVERSE CACHE
# ------------------------------------------------------------

reverse_cache = {}

duplicates = 0

for (
    element_id,
    mapping,
) in combined.items():

    try:

        bl_part = mapping["bl_part_no"]

        bl_color = mapping["bl_color_id"]

        bl_type = mapping.get(
            "bl_item_type",
            "PART",
        )

        reverse_key = f"{bl_part}" f"|{bl_color}" f"|{bl_type}"

        if reverse_key not in reverse_cache:

            reverse_cache[reverse_key] = []

        if element_id not in reverse_cache[reverse_key]:

            reverse_cache[reverse_key].append(element_id)

        else:

            duplicates += 1

    except Exception as e:

        print(f"Skipping " f"{element_id}: {e}")

# ------------------------------------------------------------
# SORT OUTPUT
# ------------------------------------------------------------

for key in reverse_cache:

    reverse_cache[key] = sorted(reverse_cache[key])

# ------------------------------------------------------------
# SAVE
# ------------------------------------------------------------

save_json_file(
    BL_TO_LEGO_CACHE_FILE,
    reverse_cache,
)

# ------------------------------------------------------------
# SUMMARY
# ------------------------------------------------------------

print("\nDONE")

print(f"Reverse mappings: " f"{len(reverse_cache)}")

print(f"Duplicate entries skipped: " f"{duplicates}")

print(f"\nSaved:")

print(BL_TO_LEGO_CACHE_FILE)
