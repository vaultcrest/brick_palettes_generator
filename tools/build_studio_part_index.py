#!/usr/bin/env python3

import json
import re
from pathlib import Path

# ------------------------------------------------------------
# SEARCH ROOTS
# ------------------------------------------------------------

SEARCH_ROOTS = {
    #
    # Official standalone LDraw
    #
    "ldraw_official": Path("/mnt/c/Users/Public/Documents/LDraw/parts"),
    "ldraw_unofficial": Path("/mnt/c/Users/Public/Documents/LDraw/Unofficial/parts"),
    #
    # Studio bundled libraries
    #
    "studio_official": Path("/mnt/c/Program Files/Studio 2.0/ldraw/parts"),
    "studio_unofficial": Path("/mnt/c/Program Files/Studio 2.0/ldraw/UnOfficial/parts"),
    #
    # Studio LEGO aliases / generated assets
    #
    "studio_lego": Path("/mnt/c/Program Files/Studio 2.0/ldraw/LEGO"),
}

# ------------------------------------------------------------
# OUTPUT
# ------------------------------------------------------------

CACHE_DIR = Path("cache")

OUTPUT_FILE = CACHE_DIR / "studio_index.json"
LOOKUP_OUTPUT_FILE = CACHE_DIR / "studio_lookup_index.json"
# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------


def extract_geometry_revision(stem):

    match = re.match(
        r"^([0-9]+)([a-z])$",
        stem.lower(),
    )

    if not match:
        return None

    return {
        "base": match.group(1),
        "revision": match.group(2),
    }


def normalize_lookup_keys(stem):

    keys = set()

    stem = stem.lower()

    #
    # Original stem
    #

    keys.add(stem)

    #
    # Geometry revision fallback
    #
    # 3044c -> 3044
    #

    match = re.match(
        r"^([0-9]+)([a-z])$",
        stem,
    )

    if match:

        keys.add(match.group(1))

    #
    # Strip bl_ prefix for lookup
    # while preserving canonical filename
    #

    if stem.startswith("bl_"):

        keys.add(stem[3:])

    return sorted(keys)


def detect_printed(stem):

    stem = stem.lower()

    #
    # Examples:
    #
    # 3001p01
    # 973pb4487c01
    # 3626pr0012
    #

    return bool(
        re.search(
            r"(?:p\d+|pb[a-z0-9]+|pr[a-z0-9]+)",
            stem,
        )
    )


def is_placeable_candidate(descriptions):

    #
    # No descriptions = probably safe
    #

    if not descriptions:
        return True

    for desc in descriptions:

        if not desc:
            continue

        desc = desc.strip()

        #
        # Redirect stubs
        #
        # ~Moved to 3665
        #

        if desc.startswith("~Moved to"):
            return False

        #
        # Internal helper geometry
        #
        # ~Motor Pull Back ...
        #

        if desc.startswith("~"):
            return False

        #
        # Stickers are not meaningful
        # Pick-a-Brick Studio targets
        #

        if desc.startswith("Sticker"):
            return False

        #
        # FILE-only metadata stubs
        #

        non_file_descriptions = [d for d in descriptions if d and not d.startswith("FILE ")]

        if desc.startswith("FILE ") and not non_file_descriptions:
            return False
    return True


def parse_dat_metadata(dat_path):

    description = None

    official = False

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
            # Only inspect header
            #

            for _ in range(25):

                line = f.readline()

                if not line:
                    break

                lines.append(line.strip())

        #
        # Description
        #

        if lines:

            first = lines[0]

            if first.startswith("0 "):

                description = first[2:].strip()

        #
        # Metadata tags
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

    except Exception as e:

        print(f"Failed parsing " f"{dat_path}: {e}")

    stem = dat_path.stem.lower()

    printed = detect_printed(stem)

    return {
        "description": description,
        "official": official,
        "printed": printed,
        "alias": alias,
        "flexible": flexible,
        "primitive": primitive,
        "subpart": subpart,
    }


def classify_lookup_relationship(entry, key, filename):

    stem = entry["stem"]

    if stem == key:
        return "exact"

    if entry["bricklink_alias"]:
        return "aliases"

    if entry["placeable_candidate"] and entry["geometry_revision"] and entry["geometry_revision"]["base"] == key:
        return "geometry_fallbacks"

    return "aliases"


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------


def main():

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    index = {}

    total_files = 0

    source_counts = {}

    #
    # Scan all sources
    #

    for source_name, root in SEARCH_ROOTS.items():

        print()
        print(f"Scanning {source_name}")

        print(root)

        if not root.exists():

            print("Missing directory")

            continue

        dat_files = sorted(root.rglob("*.dat"))

        print(f"Found {len(dat_files)} DAT files")

        source_counts[source_name] = len(dat_files)

        total_files += len(dat_files)

        for idx, dat_path in enumerate(
            dat_files,
            start=1,
        ):

            metadata = parse_dat_metadata(dat_path)

            #
            # Skip geometry internals
            #

            if metadata["primitive"]:
                continue

            if metadata["subpart"]:
                continue

            filename = dat_path.name.lower()

            stem = dat_path.stem.lower()

            geometry_revision = extract_geometry_revision(stem)

            #
            # Create entry if needed
            #

            if filename not in index:

                index[filename] = {
                    "descriptions": [],
                    "placeable_candidate": True,
                    "official": (metadata["official"]),
                    "printed": (metadata["printed"]),
                    "bricklink_alias": (filename.startswith("bl_")),
                    "alias": (metadata["alias"]),
                    "flexible": (metadata["flexible"]),
                    "primitive": (metadata["primitive"]),
                    "subpart": (metadata["subpart"]),
                    "geometry_revision": (geometry_revision),
                    "stem": stem,
                    "lookup_keys": [],
                    "locations": [],
                }

            entry = index[filename]
            if not entry["geometry_revision"] and geometry_revision:

                entry["geometry_revision"] = geometry_revision
            #
            # Merge metadata conservatively
            #

            entry["official"] = entry["official"] or metadata["official"]

            entry["printed"] = entry["printed"] or metadata["printed"]

            entry["alias"] = entry["alias"] or metadata["alias"]

            entry["flexible"] = entry["flexible"] or metadata["flexible"]

            #
            # Merge descriptions
            #

            description = metadata.get("description")

            if description and description not in entry["descriptions"]:

                entry["descriptions"].append(description)

            entry["placeable_candidate"] = is_placeable_candidate(entry["descriptions"])
            #
            # Merge lookup aliases
            #

            lookup_keys = normalize_lookup_keys(stem)

            entry["lookup_keys"] = sorted(set(entry["lookup_keys"] + lookup_keys))

            #
            # Store relative filesystem location
            #

            relative_path = str(dat_path.relative_to(root))

            location = {
                "source": source_name,
                "path": relative_path,
            }

            if location not in entry["locations"]:

                entry["locations"].append(location)

            #
            # Progress
            #

            if idx % 5000 == 0 or idx == len(dat_files):

                percent = round((idx / len(dat_files)) * 100)

                print(f"Progress: " f"{percent}% " f"({idx}/{len(dat_files)})")

    #
    # Stable output ordering
    #

    index = dict(sorted(index.items()))

    #
    # Reverse lookup index
    #

    lookup_index = {}

    for filename, entry in index.items():

        #
        # Do not expose non-placeable
        # files to resolver lookup
        #

        if not entry["placeable_candidate"]:
            continue

        for key in entry["lookup_keys"]:

            bucket = lookup_index.setdefault(
                key,
                {
                    "exact": [],
                    "aliases": [],
                    "geometry_fallbacks": [],
                },
            )

            relationship = classify_lookup_relationship(
                entry,
                key,
                filename,
            )

            bucket[relationship].append(filename)

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
    with open(
        LOOKUP_OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            lookup_index,
            f,
            indent=2,
            sort_keys=True,
        )
    #
    # Summary stats
    #

    printed_count = sum(1 for v in index.values() if v["printed"])

    official_count = sum(1 for v in index.values() if v["official"])

    alias_count = sum(1 for v in index.values() if v["alias"])

    flexible_count = sum(1 for v in index.values() if v["flexible"])
    placeable_count = sum(1 for v in index.values() if v["placeable_candidate"])
    bl_alias_count = sum(1 for v in index.values() if v["bricklink_alias"])
    print(f"Lookup keys: {len(lookup_index)}")
    print()
    print("DONE")
    print()

    print("Source counts")

    for source_name, count in source_counts.items():

        print(f"{source_name}: {count}")

    print()

    print(f"Indexed files: " f"{len(index)}")

    print(f"Total scanned files: " f"{total_files}")

    print(f"Official parts: " f"{official_count}")

    print(f"Printed parts: " f"{printed_count}")

    print(f"Alias parts: " f"{alias_count}")

    print(f"Flexible parts: " f"{flexible_count}")
    print(f"Placeable candidates: " f"{placeable_count}")
    print(f"BrickLink aliases: " f"{bl_alias_count}")

    print()

    print(f"Saved: {OUTPUT_FILE}")
    print(f"Saved: {LOOKUP_OUTPUT_FILE}")


# ------------------------------------------------------------
# ENTRY
# ------------------------------------------------------------

if __name__ == "__main__":

    main()
