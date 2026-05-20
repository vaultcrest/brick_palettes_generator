#!/usr/bin/env python3

import json
from pathlib import Path

# ------------------------------------------------------------
# PATHS
# ------------------------------------------------------------

DATA_DIR = Path("data")

STUDIO_COLOR_DEFINITION_FILE = DATA_DIR / "ldraw" / "CustomColorDefinition.txt"

OUTPUT_FILE = DATA_DIR / "color_database.json"

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------


def safe_int(value):

    value = str(value).strip()

    if not value:
        return None

    try:
        return int(value)

    except ValueError:
        return None


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------


def build_color_database():

    if not STUDIO_COLOR_DEFINITION_FILE.exists():

        raise FileNotFoundError("Missing Studio color definition:\n" f"{STUDIO_COLOR_DEFINITION_FILE}")

    print("Loading Studio color definitions")

    color_database = {
        #
        # Primary canonical mappings
        #
        "studio": {},
        "bricklink": {},
        "ldraw": {},
        "lego": {},
        #
        # Material/special variants
        #
        "studio_variants": {},
    }

    with open(
        STUDIO_COLOR_DEFINITION_FILE,
        encoding="utf-8",
        errors="ignore",
    ) as f:

        #
        # Skip header
        #

        next(f)

        for line in f:

            line = line.strip()

            if not line:
                continue

            #
            # Tab-delimited
            #

            parts = line.split("\t")

            #
            # Expected columns:
            #
            # 0 Studio Color Code
            # 1 BL Color Code
            # 2 LDraw Color Code
            # 3 LDD Color Code
            # 4 Studio Color Name
            # 5 BL Color Name
            # 6 LDraw Color Name
            # 7 LDD Color Name
            #

            if len(parts) < 8:
                continue

            studio_color_id = safe_int(parts[0])

            bricklink_color_id = safe_int(parts[1])

            ldraw_color_id = safe_int(parts[2])

            lego_color_id = safe_int(parts[3])

            studio_name = parts[4].strip()

            bricklink_name = parts[5].strip()

            ldraw_name = parts[6].strip()

            lego_name = parts[7].strip()

            entry = {
                "studio": {
                    "id": (studio_color_id),
                    "name": (studio_name),
                },
                "bricklink": {
                    "id": (bricklink_color_id),
                    "name": (bricklink_name),
                },
                "ldraw": {
                    "id": (ldraw_color_id),
                    "name": (ldraw_name),
                },
                "lego": {
                    "id": (lego_color_id),
                    "name": (lego_name),
                },
            }

            #
            # Studio color index
            #
            # Studio IDs are unique,
            # including material variants.
            #

            if studio_color_id is not None:

                color_database["studio"][str(studio_color_id)] = entry

            #
            # BrickLink canonical index
            #
            # IMPORTANT:
            # Keep FIRST occurrence only.
            #
            # Later entries are usually:
            # - Rubber
            # - Chrome
            # - Pearl
            # - Glitter
            # - Metallic
            #
            # We do NOT want those
            # overwriting canonical colors.
            #

            if bricklink_color_id is not None:

                bl_key = str(bricklink_color_id)

                if bl_key not in color_database["bricklink"]:

                    color_database["bricklink"][bl_key] = entry

            #
            # LDraw canonical index
            #

            if ldraw_color_id is not None:

                ldraw_key = str(ldraw_color_id)

                if ldraw_key not in color_database["ldraw"]:

                    color_database["ldraw"][ldraw_key] = entry

            #
            # LEGO/LDD canonical index
            #

            if lego_color_id is not None:

                lego_key = str(lego_color_id)

                if lego_key not in color_database["lego"]:

                    color_database["lego"][lego_key] = entry

            #
            # Store ALL Studio variants
            #
            # Examples:
            # - Rubber
            # - Chrome
            # - Pearl
            # - Metallic
            # - Glitter
            # - Glow
            # - Satin
            #

            if bricklink_color_id is not None and studio_color_id is not None:

                variant_key = f"{bricklink_color_id}_" f"{studio_color_id}"

                color_database["studio_variants"][variant_key] = entry

    #
    # Save
    #

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            color_database,
            f,
            indent=2,
            sort_keys=True,
        )

    #
    # Summary
    #

    print()

    print("Saved color database:")

    print(OUTPUT_FILE)

    print()

    print(f"Studio colors: " f"{len(color_database['studio'])}")

    print(f"BrickLink colors: " f"{len(color_database['bricklink'])}")

    print(f"LDraw colors: " f"{len(color_database['ldraw'])}")

    print(f"LEGO colors: " f"{len(color_database['lego'])}")

    print(f"Studio variants: " f"{len(color_database['studio_variants'])}")


# ------------------------------------------------------------
# ENTRY
# ------------------------------------------------------------


if __name__ == "__main__":

    build_color_database()
