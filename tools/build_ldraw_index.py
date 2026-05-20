#!/usr/bin/env python3

import json
import re
from pathlib import Path

# ------------------------------------------------------------
# PATHS
# ------------------------------------------------------------

LDRAW_PARTS_DIR = Path("/mnt/c/Users/Public/Documents/LDraw/parts")

OUTPUT_DIR = Path("data/ldraw")

OUTPUT_FILE = OUTPUT_DIR / "part_index.json"

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------


def parse_dat_metadata(dat_path):

    description = None

    official = False

    printed = False

    alias = False

    flexible = False

    primitive = False

    subpart = False

    try:

        with open(
            dat_path,
            encoding="utf-8",
            errors="ignore",
        ) as f:

            lines = []

            #
            # Only need first few lines
            #

            for _ in range(25):

                line = f.readline()

                if not line:

                    break

                lines.append(line.strip())

        #
        # First line description
        #

        if lines:

            first = lines[0]

            if first.startswith("0 "):

                description = first[2:].strip()

        #
        # Metadata parsing
        #

        for line in lines:

            upper = line.upper()

            if "!LDRAW_ORG UNOFFICIAL" in upper:

                official = False

            elif "!LDRAW_ORG" in upper:

                official = True

            if "ALIAS" in upper:

                alias = True

            if "FLEXIBLE" in upper:

                flexible = True

            if "PRIMITIVE" in upper:

                primitive = True

            if "SUBPART" in upper:

                subpart = True

        #
        # Printed part detection
        #

        filename = dat_path.name.lower()

        if "p" in filename:

            #
            # Example:
            # 3001p01.dat
            #

            stem = filename.removesuffix(".dat")

            if any(char.isdigit() for char in stem):

                printed = bool(
                    re.search(
                        r"p\d+$",
                        stem,
                    )
                )

    except Exception as e:

        print(f"Failed parsing {dat_path}: {e}")

    return {
        "description": description,
        "official": official,
        "printed": printed,
        "alias": alias,
        "flexible": flexible,
        "primitive": primitive,
        "subpart": subpart,
    }


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not LDRAW_PARTS_DIR.exists():

        print("LDraw parts directory does not exist:")

        print(LDRAW_PARTS_DIR)

        return

    print("Scanning LDraw parts...")

    index = {}

    dat_files = sorted(LDRAW_PARTS_DIR.glob("*.dat"))

    total = len(dat_files)

    print(f"Found {total} DAT files")

    for idx, dat_path in enumerate(
        dat_files,
        start=1,
    ):

        filename = dat_path.name.lower()
        metadata = parse_dat_metadata(dat_path)

        #
        # Skip subparts
        #

        if metadata["subpart"]:
            continue
        if metadata["primitive"]:
            continue
        if not metadata["official"]:
            continue
        index[filename] = metadata
        #
        # Progress
        #

        if idx % 1000 == 0 or idx == total:

            percent = round((idx / total) * 100)

            print(f"Progress: " f"{percent}% " f"({idx}/{total})")
    #
    # Save
    #

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            index,
            f,
            indent=2,
            sort_keys=True,
        )

    #
    # Summary
    #

    official_count = sum(1 for v in index.values() if v["official"])

    printed_count = sum(1 for v in index.values() if v["printed"])

    alias_count = sum(1 for v in index.values() if v["alias"])

    primitive_count = sum(1 for v in index.values() if v["primitive"])

    flexible_count = sum(1 for v in index.values() if v["flexible"])

    print()

    print("DONE")

    print()

    print(f"Indexed parts: {len(index)}")

    print(f"Official parts: {official_count}")

    print(f"Printed parts: {printed_count}")

    print()

    print(f"Saved: {OUTPUT_FILE}")

    print(f"Alias parts: {alias_count}")

    print(f"Flexible parts: {flexible_count}")

    print(f"Primitive parts: {primitive_count}")


# ------------------------------------------------------------
# ENTRY
# ------------------------------------------------------------


if __name__ == "__main__":

    main()
