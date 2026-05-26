#!/usr/bin/env python3

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

import requests
import yaml
from curl_cffi import requests as curl_requests
from dotenv import load_dotenv
from requests_oauthlib import OAuth1

load_dotenv()

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

DEBUG = False
LIMIT_ITEMS = False  # add a number to limit to number of items
MAX_PAGES = False  # Limit number of pages from Lego for Debugging

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

DATA_DIR = Path("data")

LDRAW_INDEX_FILE = DATA_DIR / "studio_files" / "part_index.json"

STUDIO_DEFINITION_INDEX_FILE = CACHE_DIR / "studio_part_definitions.json"

CANONICAL_DB_FILE = CACHE_DIR / "canonical_mapping.json"

FAILED_CACHE_FILE = CACHE_DIR / "failed_mappings.json"

FAILED_STUDIO_CACHE_FILE = CACHE_DIR / "failed_studio_mappings.json"

MISSING_COLOR_MAPPING_FILE = CACHE_DIR / "missing_color_mappings.json"

OVERRIDE_FILE = CACHE_DIR / "manual_overrides.yaml"

BL_TO_LEGO_CACHE_FILE = CACHE_DIR / "bricklink_to_lego.json"

SNAPSHOT_FILE = CACHE_DIR / "pab_snapshot.json"

COLOR_DATABASE_FILE = DATA_DIR / "color_database.json"

STUDIO_PALETTE_DIR = DATA_DIR / "studio_palettes"

STUDIO_EXCLUSIONS_FILE = CACHE_DIR / "studio_exclusions.yaml"

studio_exclusions = {}

FORCE_REFRESH = False

FORCE_STUDIO_REFRESH = True

ITEM_TYPE_MAP = {
    "PART": "P",
    "MINIFIG": "M",
    "SET": "S",
}

# INVALID_PART_MAP_FILE = DATA_DIR / "studio_files" / "InvalidPartMap.xml"

# ------------------------------------------------------------
# AUTH
# ------------------------------------------------------------

auth = OAuth1(
    os.environ["BRICKLINK_CONSUMER_KEY"],
    os.environ["BRICKLINK_CONSUMER_SECRET"],
    os.environ["BRICKLINK_TOKEN"],
    os.environ["BRICKLINK_TOKEN_SECRET"],
)

# ------------------------------------------------------------
# GRAPHQL
# ------------------------------------------------------------

TEST_QUERY = """
query PickABrickQuery($input: ElementQueryInput!, $sku: String) {
  searchElements(input: $input) {
    results {
      ...ElementLeaf
      __typename
    }
    total
    count
    __typename
  }
}

fragment ElementLeaf on SearchResultElement {
  id
  designId
  collapseDesignId
  name
  imageUrl
  maxOrderQuantity
  deliveryChannel
  colorHex
  contrastColorHex

  price {
    centAmount
    formattedAmount
    currencyCode
    formattedValue
    __typename
  }

  quantityInSet(sku: $sku)

  siblings {
    id
    colorHex
    contrastColorHex
    availability

    price {
      formattedAmount
      formattedValue
      __typename
    }

    __typename
  }

  availability

  __typename
}
"""

stats = {
    "bricklink_success": 0,
    "manual_override": 0,
    "rebrickable_fallback": 0,
    "unresolved": 0,
    "temporary_failure": 0,
    "canonical_cache": 0,
    "incremental_skipped": 0,
    "incremental_updated": 0,
    "incremental_removed": 0,
    "studio_excluded": 0,
    "studio_invalid_replacement": 0,
    "studio_palette_resolved": 0,
    "ldraw_resolved": 0,
    "missing_color_mapping": 0,
    "canonical_mapping_reused": 0,
    "studio_definition_resolved": 0,
    "studio_definition_exact": 0,
    "studio_definition_bl_alias": 0,
    "studio_exact_resolved": 0,
    "studio_alias_resolved": 0,
    "studio_print_revision_resolved": 0,
    "studio_geometry_revision_resolved": 0,
    "studio_alternate_resolved": 0,
    "studio_invalid_replacement_resolved": 0,
    "ldraw_exact_resolved": 0,
    "ldraw_alias_resolved": 0,
    "ldraw_print_revision_resolved": 0,
    "ldraw_geometry_revision_resolved": 0,
    "ldraw_alternate_resolved": 0,
    "ldraw_invalid_replacement_resolved": 0,
    "studio_unresolved": 0,
}


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def load_yaml_file(path, default):

    if path.exists():

        try:

            with open(
                path,
                encoding="utf-8",
            ) as f:

                data = yaml.safe_load(f)

                if data is None:
                    return default

                return data

        except Exception as e:

            print(f"Failed loading {path}: {e}")

    return default


def save_yaml_file(path, data):

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as f:

        yaml.safe_dump(
            data,
            f,
            sort_keys=True,
            allow_unicode=True,
            default_flow_style=False,
        )


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

    temp_path = path.with_suffix(path.suffix + ".tmp")

    with open(
        temp_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            sort_keys=True,
        )

    temp_path.replace(path)


def fetch_bricklink_item_metadata(
    item_type,
    part_no,
):

    url = "https://api.bricklink.com/api/store/v1/items/" f"{item_type}/{part_no}"
    try:

        response = requests.get(
            url,
            auth=auth,
            timeout=5,
        )

        response.raise_for_status()

        data = response.json()

        if data["meta"]["code"] != 200:

            return {}

        item = data["data"]

        alternate_no = []

        raw_alternate = item.get("alternate_no")

        if raw_alternate:

            if isinstance(raw_alternate, str):

                alternate_no = [part.strip() for part in raw_alternate.split(",") if part.strip()]

            elif isinstance(raw_alternate, list):

                alternate_no = [str(part).strip() for part in raw_alternate if str(part).strip()]
        return {
            "name": item.get("name"),
            "alternate_no": alternate_no,
        }

    except requests.HTTPError as e:

        status = getattr(
            e.response,
            "status_code",
            None,
        )

        #
        # Many valid catalog items
        # do not resolve through
        # metadata endpoint.
        #

        if status == 400:

            return {}

        print(
            "BrickLink metadata lookup failed:",
            e,
        )

        return {}

    except Exception as e:

        print(
            "BrickLink metadata lookup failed:",
            e,
        )

        return {}


# ------------------------------------------------------------
# LOAD STATE
# ------------------------------------------------------------

manual_overrides = load_yaml_file(
    OVERRIDE_FILE,
    {},
)

failed_cache = load_json_file(
    FAILED_CACHE_FILE,
    {},
)

failed_studio_cache = load_json_file(
    FAILED_STUDIO_CACHE_FILE,
    {},
)

missing_color_mappings = {}

canonical_db = load_json_file(
    CANONICAL_DB_FILE,
    {},
)

print(f"Loaded canonical cache: " f"{len(canonical_db)} entries")

color_database = load_json_file(
    COLOR_DATABASE_FILE,
    {},
)

print(f"Loaded color database: " f"{len(color_database.get('bricklink', {}))} " f"BrickLink colors")

ldraw_index = {}
known_ldraw_parts = set()
known_studio_parts = set()
known_parts = {}
studio_definition_index = {}
invalid_part_map = {}


def load_ldraw_index():

    global ldraw_index
    global known_ldraw_parts

    ldraw_index = load_json_file(
        LDRAW_INDEX_FILE,
        {},
    )

    known_ldraw_parts = set(part.lower() for part in ldraw_index.keys())

    for part_file in known_ldraw_parts:

        known_parts.setdefault(
            part_file,
            {},
        )["ldraw"] = True

    print(f"Loaded " f"{len(known_ldraw_parts)} " f"LDraw parts")


def load_studio_definition_index():

    global studio_definition_index

    studio_definition_index = load_json_file(
        STUDIO_DEFINITION_INDEX_FILE,
        {},
    )

    print(f"Loaded " f"{len(studio_definition_index)} " f"Studio part definitions")


def load_studio_palettes():

    global known_studio_parts
    global known_parts

    if not STUDIO_PALETTE_DIR.exists():

        print("Missing studio palette dir:")

        print(STUDIO_PALETTE_DIR)

        return

    palette_files = sorted(path for path in STUDIO_PALETTE_DIR.iterdir() if (path.is_file() and not path.name.startswith(".")))

    studio_parts = set()

    for palette_file in palette_files:

        if not palette_file.is_file():
            continue

        try:

            with open(
                palette_file,
                encoding="utf-8",
                errors="ignore",
            ) as f:

                for line in f:

                    line = line.strip()

                    #
                    # Palette DAT line
                    #

                    if not line.startswith("0 "):
                        continue

                    dat_file = line[2:].strip().lower()

                    if not dat_file.endswith(".dat"):
                        continue

                    #
                    # Exact Studio entry
                    #

                    studio_parts.add(dat_file)

                    #
                    # Normalize bl_
                    #
                    # Example:
                    # bl_3069pb1265.dat
                    # -> 3069pb1265.dat
                    #

                    if dat_file.startswith("bl_"):

                        stripped = dat_file[3:]

                        studio_parts.add(stripped)

        except Exception as e:

            print(f"Failed reading " f"{palette_file}: {e}")

    known_studio_parts = studio_parts

    #
    # Merge into unified known_parts
    #

    for part_file in known_studio_parts:

        known_parts.setdefault(
            part_file,
            {},
        )["studio"] = True

    print(f"Loaded " f"{len(known_studio_parts)} " f"Studio palette parts")


def load_studio_exclusions():

    global studio_exclusions

    studio_exclusions = load_yaml_file(
        STUDIO_EXCLUSIONS_FILE,
        {},
    )

    #
    # Normalize all exclusion keys
    # to lowercase strings
    #

    studio_exclusions = {str(key).lower(): value for key, value in studio_exclusions.items()}

    print(f"Loaded " f"{len(studio_exclusions)} " f"Studio exclusions")


# def load_invalid_part_map():

#     global invalid_part_map

#     if not INVALID_PART_MAP_FILE.exists():

#         print("Missing InvalidPartMap:")

#         print(INVALID_PART_MAP_FILE)

#         return

#     tree = ET.parse(INVALID_PART_MAP_FILE)

#     root = tree.getroot()

#     mapping = {}

#     for item in root.findall(".//InvalidPart"):

#         source = (item.findtext("source") or "").strip().lower()

#         replacement = (item.findtext("replacement") or "").strip().lower()

#         bl_item_no = (item.findtext("BLItemNo") or "").strip()

#         if not source:
#             continue

#         mapping[source] = {
#             "replacement": replacement,
#             "bricklink_part": (bl_item_no),
#         }

#     invalid_part_map = mapping

#     print(f"Loaded " f"{len(invalid_part_map)} " f"invalid part mappings")


# ------------------------------------------------------------
# Channel Priority for parts
# ------------------------------------------------------------


def channel_priority(channel):

    priorities = {
        "pab": 3,
        "bap": 2,
        "out_of_stock": 1,
        "unknown": 0,
    }

    return priorities.get(
        str(channel).lower(),
        0,
    )


# ------------------------------------------------------------
# CHANNEL
# ------------------------------------------------------------


def get_channel(item):

    channel = item.get("deliveryChannel")

    if channel:
        return channel

    if item.get("availability") == "OUT_OF_STOCK":

        return "out_of_stock"

    return "unknown"


# ------------------------------------------------------------
# LEGO FETCH
# ------------------------------------------------------------


def fetch_lego_inventory(
    per_page=400,
):

    url = "https://www.lego.com/api/graphql/PickABrickQuery"

    headers = {
        "Referer": ("https://www.lego.com/" "en-us/pick-and-build/" "pick-a-brick"),
        "User-Agent": "Mozilla/5.0",
    }

    all_results = []

    page = 1

    while True:

        if MAX_PAGES and page > MAX_PAGES:

            print(f"Reached page limit: " f"{MAX_PAGES}")

            break

        print(f"Fetching page {page}")

        json_body = {
            "operationName": "PickABrickQuery",
            "variables": {
                "input": {
                    "page": page,
                    "perPage": per_page,
                    "sort": {
                        "key": "RELEVANCE",
                        "direction": "DESC",
                    },
                    "query": "",
                    "fetchSiblings": True,
                    "availability": [
                        "AVAILABLE",
                        "OUT_OF_STOCK",
                    ],
                },
            },
            "query": TEST_QUERY,
        }

        response = curl_requests.post(
            url,
            json=json_body,
            headers=headers,
            impersonate="chrome124",
            timeout=60,
        )

        if response.status_code != 200:

            print(response.text)

            response.raise_for_status()

        data = response.json()

        search = data["data"]["searchElements"]

        results = search["results"]

        if not results:
            break

        expanded_results = []

        for item in results:

            #
            # Primary item
            #

            expanded_results.append(item)

            #
            # Sibling color variants
            #

            for sibling in item.get("siblings", []):

                sibling_copy = dict(item)

                #
                # Override with sibling-specific fields
                #

                sibling_copy.update(sibling)

                #
                # Preserve parent metadata
                #

                sibling_copy["designId"] = item.get("designId")

                sibling_copy["name"] = item.get("name")

                sibling_copy["deliveryChannel"] = item.get("deliveryChannel")

                sibling_copy["imageUrl"] = item.get("imageUrl")

                sibling_copy["maxOrderQuantity"] = item.get("maxOrderQuantity")

                expanded_results.append(sibling_copy)

        all_results.extend(expanded_results)

        if len(results) < per_page:
            break

        page += 1

        time.sleep(0.05)

    #
    # Deduplicate by LEGO element ID
    #
    # Prefer:
    # PAB > BAP > OUT_OF_STOCK
    #

    deduped = {}

    for item in all_results:

        element_id = str(item.get("id"))

        existing = deduped.get(element_id)

        if not existing:

            deduped[element_id] = item

            continue

        existing_priority = channel_priority(get_channel(existing))

        new_priority = channel_priority(get_channel(item))

        if new_priority > existing_priority:

            deduped[element_id] = item

    all_results = list(deduped.values())

    snapshot_data = {
        "timestamp": time.time(),
        "results": all_results,
    }

    save_json_file(
        SNAPSHOT_FILE,
        snapshot_data,
    )

    return all_results


# ------------------------------------------------------------
# BRICKLINK LOOKUP
# ------------------------------------------------------------


def lookup_bricklink_mapping(
    element_id,
):

    url = "https://api.bricklink.com/api/store/v1/" f"item_mapping/{element_id}"

    max_attempts = 3

    for attempt in range(max_attempts):

        try:

            #
            # Small pacing delay
            #

            time.sleep(0.02)

            response = requests.get(
                url,
                auth=auth,
                timeout=5,
            )

            response.raise_for_status()

            data = response.json()

            if data["meta"]["code"] != 200 or not data["data"]:

                return None

            mapping = data["data"][0]

            item_type = mapping["item"]["type"]

            part_no = mapping["item"]["no"]

            stats["bricklink_success"] += 1

            return {
                "bl_part_no": part_no,
                "bl_color_id": mapping["color_id"],
                "bl_item_type": item_type,
                #
                # defer metadata lookup
                #
                "bl_name": None,
                "bl_alternate_no": [],
                "source": "bricklink",
            }

        except requests.exceptions.RequestException as e:

            error_message = str(e)

            print(
                f"BrickLink network failure " f"(attempt {attempt + 1}/" f"{max_attempts}):",
                error_message,
            )

            #
            # Final retry exhausted
            #

            if attempt == max_attempts - 1:

                return {
                    "_temporary_failure": True,
                    "_reason": error_message,
                }

            #
            # Exponential backoff
            #

            time.sleep(2 * (attempt + 1))

        except Exception as e:

            print(
                "BrickLink lookup failed:",
                e,
            )

            return None


# ------------------------------------------------------------
# Color Resolver
# ------------------------------------------------------------


def resolve_studio_color(
    bricklink_color_id,
):

    #
    # Invalid / placeholder color
    #

    if bricklink_color_id is None or bricklink_color_id == 0 or str(bricklink_color_id) == "0":

        return 0

    bricklink_colors = color_database.get(
        "bricklink",
        {},
    )
    color_entry = bricklink_colors.get(str(bricklink_color_id))

    #
    # Missing BL color mapping
    #

    if not color_entry:

        stats["missing_color_mapping"] += 1

        missing_color_mappings[str(bricklink_color_id)] = {
            "bricklink_color_id": (bricklink_color_id),
            "reason": ("missing_color_entry"),
        }

        return bricklink_color_id

    ldraw = color_entry.get("ldraw")

    #
    # Missing LDraw mapping
    #

    if not ldraw:

        stats["missing_color_mapping"] += 1

        missing_color_mappings[str(bricklink_color_id)] = {
            "bricklink_color_id": (bricklink_color_id),
            "reason": ("missing_ldraw_mapping"),
            "color_entry": (color_entry),
        }

        return bricklink_color_id

    return ldraw["id"]


# ------------------------------------------------------------
# REBRICKABLE FALLBACK
# ------------------------------------------------------------


def lookup_rebrickable_fallback(
    element_id,
):

    api_key = os.getenv("REBRICKABLE_API_KEY")

    if not api_key:
        return None

    url = "https://rebrickable.com/api/v3/lego/" f"elements/{element_id}/"

    headers = {
        "Authorization": (f"key {api_key}"),
        "User-Agent": ("brick-palette-generator/1.0"),
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            return None

        data = response.json()

        part = data.get(
            "part",
            {},
        )
        ## Debug name
        if not part.get("name"):
            print(f"REBRICKABLE no name data: " f"{data}")

        color = data.get(
            "color",
            {},
        )

        bricklink_ids = part.get(
            "external_ids",
            {},
        ).get(
            "BrickLink",
            [],
        )

        if not bricklink_ids:
            return None

        bl_color_ids = (
            color.get(
                "external_ids",
                {},
            )
            .get(
                "BrickLink",
                {},
            )
            .get(
                "ext_ids",
                [],
            )
        )

        if not bl_color_ids:
            return None

        return {
            "bl_part_no": (bricklink_ids[0]),
            "bl_color_id": (bl_color_ids[0]),
            "bl_item_type": "PART",
            "bl_name": part.get("name"),
            "bl_alternate_no": [],
            "source": ("rebrickable_fallback"),
        }

    except Exception as e:

        print(
            "Rebrickable fallback failed:",
            e,
        )

        return None


# ------------------------------------------------------------
# REJECTION HELPERS
# ------------------------------------------------------------


def should_reject_studio_part(
    bricklink_name,
    lego_name,
):

    bricklink_name = (bricklink_name or "").lower()

    lego_name = (lego_name or "").lower()

    combined = f"{bricklink_name} {lego_name}"

    reject_terms = {
        "duplo": "reject_duplo",
        "braille": "reject_braille",
    }

    for term, reason in reject_terms.items():

        if term in combined:

            return reason

    return None


# ------------------------------------------------------------
# STUDIO PART FILE
# ------------------------------------------------------------
def add_candidate(
    candidates,
    candidate,
    resolution_type,
    confidence,
    source,
    generated_from,
):

    candidate = candidate.lower()

    existing = candidates.get(candidate)

    #
    # Keep highest confidence version
    #

    if existing:

        if existing["confidence"] >= confidence:
            return

    candidates[candidate] = {
        "candidate": candidate,
        "resolution_type": resolution_type,
        "confidence": confidence,
        "source": source,
        "generated_from": generated_from,
    }


def resolve_studio_part(
    bricklink_part,
    alternate_parts,
):

    #
    # Resolution order:
    #
    # 1. Canonical BrickLink ID
    # 2. Reverse alternate IDs
    #
    # Example:
    #
    # 98313
    # -> 76116
    # -> 49753
    #

    candidates = {}

    #
    # Explicit Studio exclusions
    #
    # These are authoritative skips
    # for parts known to have
    # no usable Studio/LDraw model.
    #

    exclusion = studio_exclusions.get(bricklink_part.lower())

    if exclusion:

        stats["studio_excluded"] += 1

        return {
            "part_file": None,
            "source_type": "studio_exclusion",
            "resolved_from": "studio_exclusion",
            "resolution_method": "studio_exclusion",
            "candidate_metadata": {
                "reason": exclusion.get("reason"),
                "category": exclusion.get("category"),
            },
            "attempted": [],
        }

    #
    # PRIMARY:
    # Studio Part Definitions
    #

    definition_match = studio_definition_index.get(bricklink_part.lower())

    if definition_match:

        part_file = definition_match.lower()

        part_sources = known_parts.get(
            part_file,
            {},
        )

        source_type = None

        if part_sources.get("studio"):

            source_type = "studio_definition"

        elif part_sources.get("ldraw"):

            source_type = "studio_definition_ldraw"

        else:

            source_type = "studio_definition_missing"

        stats["studio_definition_resolved"] += 1

        if part_file.startswith("bl_"):

            stats["studio_definition_bl_alias"] += 1

        else:

            stats["studio_definition_exact"] += 1

        return {
            "part_file": part_file,
            "source_type": source_type,
            "resolved_from": bricklink_part,
            "candidate_metadata": {
                "candidate": bricklink_part,
                "resolution_type": "studio_definition",
                "confidence": 1.0,
                "source": "studio_part_definitions",
                "generated_from": bricklink_part,
            },
            "resolution_method": "studio_definition",
            "attempted": [],
        }
    # Debug area
    # else:
    #     print("Part not resolved:", bricklink_part.lower())

    # Debug area

    #
    # 1. Canonical BL part
    #

    add_candidate(
        candidates=candidates,
        candidate=bricklink_part,
        resolution_type="exact",
        confidence=1.0,
        source="bricklink_canonical",
        generated_from=bricklink_part,
    )

    #
    # 2. BrickLink Studio alias
    #
    # 973pb4487c01
    # -> bl_973pb4487c01
    #

    if not bricklink_part.startswith("bl_"):

        add_candidate(
            candidates=candidates,
            candidate=f"bl_{bricklink_part}",
            resolution_type="alias",
            confidence=0.99,
            source="generated_bl_alias",
            generated_from=bricklink_part,
        )

    #
    # 3. Print revision expansion
    #
    # 3069pb0304
    # -> 3069bpb0304
    #
    # 3626pb0267
    # -> 3626bpb0267
    # -> 3626cpb0267
    #

    print_match = re.match(
        r"^([0-9]+)(p(?:b|r)?[a-z0-9]+)$",
        bricklink_part,
        re.IGNORECASE,
    )

    if print_match:

        base = print_match.group(1)

        suffix = print_match.group(2)

        for revision in ["b", "c", "d"]:

            generated = f"{base}{revision}{suffix}"

            add_candidate(
                candidates=candidates,
                candidate=generated,
                resolution_type="print_revision",
                confidence=0.95,
                source="generated_print_revision",
                generated_from=bricklink_part,
            )

    #
    # 4. Geometry revision fallback
    #
    # 3044c -> 3044
    #

    geometry_match = re.match(
        r"^([0-9]+)([abd])$",
        bricklink_part,
        re.IGNORECASE,
    )

    if geometry_match:

        base = geometry_match.group(1)

        add_candidate(
            candidates=candidates,
            candidate=base,
            resolution_type="geometry_revision",
            confidence=0.80,
            source="generated_geometry_fallback",
            generated_from=bricklink_part,
        )

    #
    # 5. Assembly collapse - Disabled for now
    #
    # 4592c06 -> 4592
    #

    # assembly_match = re.match(
    #     r"^([0-9]+)c\d+$",
    #     bricklink_part,
    #     re.IGNORECASE,
    # )

    # if assembly_match:

    #     base = assembly_match.group(1)

    #     add_candidate(
    #         candidates=candidates,
    #         candidate=base,
    #         resolution_type="assembly_variant",
    #         confidence=0.75,
    #         source="generated_assembly_variant",
    #         generated_from=bricklink_part,
    #     )

    #
    # 6. Studio invalid replacement
    #

    canonical_dat = (f"{bricklink_part}.dat").lower()

    invalid_mapping = invalid_part_map.get(canonical_dat)

    if invalid_mapping:

        replacement = invalid_mapping.get("replacement")

        if replacement:

            replacement_part = replacement.removesuffix(".dat")

            add_candidate(
                candidates=candidates,
                candidate=replacement_part,
                resolution_type="invalid_replacement",
                confidence=0.97,
                source="invalid_part_map",
                generated_from=bricklink_part,
            )

    #
    # 7. Reverse alternates
    #

    reverse_alternates = list(reversed(alternate_parts))

    for alternate in reverse_alternates:

        add_candidate(
            candidates=candidates,
            candidate=alternate,
            resolution_type="alternate",
            confidence=0.90,
            source="bricklink_alternate",
            generated_from=bricklink_part,
        )

    #
    # Deduplicate while preserving order
    #

    attempted = []

    for candidate_data in sorted(
        candidates.values(),
        key=lambda x: x["confidence"],
        reverse=True,
    ):

        candidate = candidate_data["candidate"]

        part_file = (f"{candidate}.dat").lower()

        attempted.append(
            {
                "part_file": part_file,
                "resolution_type": (candidate_data["resolution_type"]),
                "confidence": (candidate_data["confidence"]),
                "source": (candidate_data["source"]),
                "generated_from": (candidate_data["generated_from"]),
            }
        )

        #
        # Studio palettes are PRIMARY
        # LDraw is SECONDARY
        #

        part_sources = known_parts.get(
            part_file,
            {},
        )

        source_type = None

        if part_sources.get("studio"):

            source_type = "studio_palette"

        elif part_sources.get("ldraw"):

            source_type = "ldraw"

        if source_type:

            if source_type == "studio_palette":

                stats["studio_palette_resolved"] += 1

            elif source_type == "ldraw":

                stats["ldraw_resolved"] += 1

            #
            # Resolution telemetry
            #

            resolution_method = candidate_data["resolution_type"]

            method_key = resolution_method

            if source_type == "studio_palette":

                stat_name = f"studio_{method_key}_resolved"

                if stat_name in stats:

                    stats[stat_name] += 1

            elif source_type == "ldraw":

                stat_name = f"ldraw_{method_key}_resolved"

                if stat_name in stats:

                    stats[stat_name] += 1

            resolution_method = candidate_data["resolution_type"]

            if candidate_data["source"] == "invalid_part_map":

                stats["studio_invalid_replacement"] += 1

            return {
                "part_file": part_file,
                "source_type": source_type,
                "resolved_from": candidate,
                "candidate_metadata": (candidate_data),
                "resolution_method": (resolution_method),
                "attempted": attempted,
            }
    #
    # Resolution failed
    #

    stats["studio_unresolved"] += 1

    if DEBUG:

        print(
            "Studio unresolved:",
            bricklink_part,
            attempted,
        )

    return {
        "part_file": None,
        "source_type": None,
        "resolved_from": None,
        "resolution_method": None,
        "attempted": attempted,
    }


# ------------------------------------------------------------
# RESOLVE MAPPING
# ------------------------------------------------------------

temporary_failures = []

lookup_progress = {
    "total": 0,
    "processed": 0,
    "next_report": 5,
}


def resolve_mapping(
    element_id,
):

    element_id = str(element_id)

    #
    # Manual override
    #

    if element_id in manual_overrides:
        stats["manual_override"] += 1
        return manual_overrides[element_id]

    #
    # Previously failed permanently
    #

    if element_id in failed_cache and not FORCE_REFRESH:

        cache_age = time.time() - failed_cache[element_id].get(
            "timestamp",
            0,
        )

        #
        # Retry unresolved entries
        # after 7 days
        #

        if cache_age < 604800:

            return None

    #
    # BrickLink lookup
    #

    mapping = lookup_bricklink_mapping(element_id)
    #
    # Temporary network/API failure
    #
    # Do NOT permanently cache
    #

    if mapping and mapping.get("_temporary_failure"):
        stats["temporary_failure"] += 1
        print(f"TEMPORARY FAILURE: " f"{element_id}")

        print(mapping.get("_reason"))

        temporary_failures.append(
            {
                "element_id": element_id,
                "reason": mapping.get("_reason"),
            }
        )

        return None

    #
    # Rebrickable fallback
    #

    if not mapping:

        mapping = lookup_rebrickable_fallback(element_id)

        if mapping:

            print(f"REBRICKABLE FALLBACK: " f"{element_id} " f"-> " f"{mapping['bl_part_no']}")
            stats["rebrickable_fallback"] += 1
            manual_overrides[element_id] = mapping

            save_yaml_file(
                OVERRIDE_FILE,
                manual_overrides,
            )

            #
            # DEBUG missing BL name
            #
            if not mapping.get("bl_name"):
                print(f"REBRICKABLE FALLBACK: " f"{element_id} " f"-> " f"{mapping['bl_part_no']}" f"-> " f"{mapping}")

            stats["rebrickable_fallback"] += 1
    #
    # Permanent failure
    #

    if not mapping:
        stats["unresolved"] += 1
        print(f"UNRESOLVED: " f"{element_id}")

        failed_cache[element_id] = {
            "status": "unresolved",
            "timestamp": time.time(),
        }

        save_json_file(
            FAILED_CACHE_FILE,
            failed_cache,
        )

        return None

    return mapping


# ------------------------------------------------------------
# BUILD CANONICAL DB
# ------------------------------------------------------------


def build_canonical_db(results):

    global canonical_db

    canonical = dict(canonical_db)

    lookup_progress["total"] = len(results)
    lookup_progress["processed"] = 0
    lookup_progress["next_report"] = 5

    for item in results:

        element_id = str(item["id"])

        lookup_progress["processed"] += 1

        processed = lookup_progress["processed"]

        total = lookup_progress["total"]

        percent = int((processed / total) * 100)

        if percent >= lookup_progress["next_report"]:

            print(f"BrickLink mapping progress: " f"{percent}% " f"({processed}/{total})")

            lookup_progress["next_report"] += 5

        existing = canonical.get(element_id)

        current_channel = get_channel(item)

        current_price = item.get(
            "price",
            {},
        ).get(
            "centAmount",
            0,
        )

        mapping = None

        #
        # Incremental behavior
        #

        if existing:

            existing_price = existing.get(
                "price",
                {},
            ).get(
                "cent_amount",
                0,
            )

            existing_channel = existing.get("channel")

            same_state = existing_price == current_price and existing_channel == current_channel

            #
            # Full incremental skip
            #

            if same_state and not FORCE_REFRESH and not FORCE_STUDIO_REFRESH:

                stats["incremental_skipped"] += 1

                stats["canonical_cache"] += 1

                continue

            # Studio-only refresh
            #

            elif same_state and FORCE_STUDIO_REFRESH and not FORCE_REFRESH:

                stats["canonical_mapping_reused"] += 1

                mapping = {
                    "bl_part_no": (existing["bricklink"]["part_no"]),
                    "bl_color_id": (existing["bricklink"]["color_id"]),
                    "bl_item_type": (existing["bricklink"]["item_type"]),
                    "bl_name": (existing["bricklink"]["name"]),
                    "bl_alternate_no": (existing["bricklink"]["alternate_no"]),
                    "source": (existing["source"]),
                }

        #
        # Fresh mapping lookup
        #

        if not mapping:

            mapping = resolve_mapping(element_id)

        if not mapping:
            continue
        #
        # Fetch missing BrickLink metadata
        # lazily only when needed
        #

        if not mapping.get("bl_name"):

            metadata = fetch_bricklink_item_metadata(
                mapping["bl_item_type"],
                mapping["bl_part_no"],
            )

            if metadata:

                mapping["bl_name"] = metadata.get("name")

                mapping["bl_alternate_no"] = metadata.get(
                    "alternate_no",
                    [],
                )

                print(f"Fetched missing metadata: " f"{mapping['bl_part_no']} " f"-> " f"{mapping['bl_name']}")
        #
        # Remove stale failed mapping
        #

        if element_id in failed_cache:

            del failed_cache[element_id]

        #
        # BrickLink canonical part
        #

        bricklink_part = mapping["bl_part_no"]

        #
        # Alternate IDs
        #

        alternate_parts = mapping.get(
            "bl_alternate_no",
            [],
        )

        studio_resolution = resolve_studio_part(
            bricklink_part,
            alternate_parts,
        )

        studio_part = studio_resolution["part_file"]

        #
        # Resolve Studio/LDraw color
        #

        studio_color = resolve_studio_color(mapping["bl_color_id"])

        #
        # Failed Studio/LDraw resolution
        #

        studio_supported = True

        reject_reason = studio_resolution.get("resolution_method") or "unresolved"

        #
        # Explicit Studio exclusions
        # should never appear in failed mappings
        #

        if reject_reason == "studio_exclusion":

            #
            # Remove any stale failed entries
            # tied to this excluded BrickLink part
            #

            stale_keys = []

            for failed_element_id, failed_entry in failed_studio_cache.items():

                failed_bl_part = str(failed_entry.get("bricklink_part", "")).lower()

                if failed_bl_part == bricklink_part.lower():

                    stale_keys.append(failed_element_id)

            for stale_key in stale_keys:

                del failed_studio_cache[stale_key]

            continue

        if not studio_part:

            studio_supported = False

            #
            # Intentionally excluded from Studio
            # and should NOT pollute failed mappings
            #

            if reject_reason == "studio_exclusion":
                pass

            else:

                failed_studio_cache[element_id] = {
                    "reject_reason": reject_reason,
                    "lego_name": (item.get("name")),
                    "bricklink_name": (mapping.get("bl_name")),
                    "bricklink_part": (bricklink_part),
                    "alternate_no": (alternate_parts),
                    "attempted_parts": (studio_resolution["attempted"]),
                    "resolution_candidates": ([bricklink_part] + alternate_parts),
                    "original_part": (bricklink_part),
                    "bricklink_color_id": (mapping["bl_color_id"]),
                    "studio_color_id": (studio_color),
                    "timestamp": time.time(),
                }

        #
        # Remove stale failed Studio entries
        #

        elif element_id in failed_studio_cache:

            del failed_studio_cache[element_id]

        #
        # Build canonical entry
        #

        canonical[element_id] = {
            #
            # LEGO metadata
            #
            "lego": {
                "element_id": (element_id),
                "design_id": (item.get("designId")),
                "name": (item.get("name")),
            },
            #
            # BrickLink canonical mapping
            #
            "bricklink": {
                "part_no": (bricklink_part),
                "alternate_no": (alternate_parts),
                "name": (mapping.get("bl_name")),
                "color_id": (mapping["bl_color_id"]),
                "item_type": (mapping["bl_item_type"]),
            },
            #
            # Studio/LDraw mapping
            #
            "studio": {
                "part_file": (studio_part),
                "resolved_from": (studio_resolution["resolved_from"]),
                "candidate_metadata": (studio_resolution.get("candidate_metadata")),
                "resolution_method": (studio_resolution.get("resolution_method")),
                "source_type": (studio_resolution.get("source_type")),
                "color_id": (studio_color),
                "resolved": (studio_supported),
            },
            #
            # LEGO metadata
            #
            "channel": (get_channel(item)),
            "price": {
                "cent_amount": (
                    item.get(
                        "price",
                        {},
                    ).get(
                        "centAmount",
                        0,
                    )
                ),
                "formatted": (
                    item.get(
                        "price",
                        {},
                    ).get(
                        "formattedAmount",
                        "$0.00",
                    )
                ),
            },
            #
            # Mapping source
            #
            "source": (mapping["source"]),
        }

        stats["incremental_updated"] += 1

    #
    # Remove stale entries
    #

    current_ids = {str(item["id"]) for item in results}

    stale_ids = [element_id for element_id in canonical if element_id not in current_ids]

    for stale_id in stale_ids:

        del canonical[stale_id]

        if stale_id in failed_cache:

            del failed_cache[stale_id]

        if stale_id in failed_studio_cache:

            del failed_studio_cache[stale_id]

    stats["incremental_removed"] += len(stale_ids)

    print(f"Removed stale entries: " f"{len(stale_ids)}")

    canonical_db = canonical

    save_json_file(
        CANONICAL_DB_FILE,
        canonical_db,
    )

    save_json_file(
        FAILED_CACHE_FILE,
        failed_cache,
    )

    save_json_file(
        FAILED_STUDIO_CACHE_FILE,
        failed_studio_cache,
    )

    save_json_file(
        MISSING_COLOR_MAPPING_FILE,
        missing_color_mappings,
    )

    print(f"Saved canonical DB: " f"{len(canonical_db)} entries")


# ------------------------------------------------------------
# XML EXPORT
# ------------------------------------------------------------


def build_xml(entries):

    inventory = ET.Element("INVENTORY")

    for entry in entries:

        item = ET.SubElement(
            inventory,
            "ITEM",
        )

        ET.SubElement(
            item,
            "ITEMTYPE",
        ).text = ITEM_TYPE_MAP.get(
            entry["bricklink"]["item_type"],
            "P",
        )

        ET.SubElement(
            item,
            "ITEMID",
        ).text = entry[
            "bricklink"
        ]["part_no"]

        ET.SubElement(
            item,
            "COLOR",
        ).text = str(entry["bricklink"]["color_id"])

        ET.SubElement(
            item,
            "MAXPRICE",
        ).text = f"{entry['price']['cent_amount'] / 100:.4f}"

        ET.SubElement(
            item,
            "MINQTY",
        ).text = "1"

        ET.SubElement(
            item,
            "CONDITION",
        ).text = "X"

        ET.SubElement(
            item,
            "REMARKS",
        ).text = (
            f"{entry['lego']['name']} " f"(LEGO Element " f"{entry['lego']['element_id']})"
        )

        ET.SubElement(
            item,
            "NOTIFY",
        ).text = "N"

    xml_bytes = ET.tostring(
        inventory,
        encoding="utf-8",
    )

    xml_str = minidom.parseString(xml_bytes).toprettyxml(indent="  ")

    return "\n".join(line for line in xml_str.splitlines() if line.strip())


# ------------------------------------------------------------
# PALETTE EXPORT
# ------------------------------------------------------------


def build_palette(entries, name):

    lines = [
        f"~+{name}",
        "14",
        "-1",
    ]

    #
    # Emit palette entries directly
    #
    # Do NOT aggregate counts.
    #
    # Studio palettes behave better when
    # each LEGO inventory entry is preserved.
    #

    for entry in entries:

        if not entry["studio"]["resolved"]:
            continue

        part_file = entry["studio"]["part_file"]

        bricklink_name = entry["bricklink"]["name"] or entry["lego"]["name"] or part_file

        #
        # Skip DUPLO in Studio palettes
        #

        if "duplo" in bricklink_name.lower():

            continue

        color_id = entry["studio"]["color_id"]

        lines.append(f"0 {part_file}")

        lines.append(f"1 {bricklink_name}")

        lines.append(f"2 {color_id}")

    return "\n".join(lines)


# ------------------------------------------------------------
# EXPORTS
# ------------------------------------------------------------
def export_failed_studio_review():

    seen = set()

    if not failed_studio_cache:

        return

    inventory = ET.Element("INVENTORY")

    for entry in failed_studio_cache.values():

        key = (
            entry["original_part"],
            entry.get(
                "bricklink_color_id",
                1,
            ),
        )

        if key in seen:
            continue

        seen.add(key)

        item = ET.SubElement(
            inventory,
            "ITEM",
        )

        ET.SubElement(
            item,
            "ITEMTYPE",
        ).text = "P"

        ET.SubElement(
            item,
            "ITEMID",
        ).text = entry["original_part"]

        ET.SubElement(
            item,
            "COLOR",
        ).text = str(
            entry.get(
                "bricklink_color_id",
                1,
            )
        )

        #
        # Rich remarks
        #

        remarks = []

        lego_name = entry.get("lego_name")

        bricklink_name = entry.get("bricklink_name")

        if lego_name:

            remarks.append(f"LEGO: {lego_name}")

        if bricklink_name:

            remarks.append(f"BL: {bricklink_name}")
        reject_reason = entry.get("reject_reason")

        if reject_reason:

            remarks.append(f"Reject: {reject_reason}")
        attempted = entry.get(
            "attempted_parts",
            [],
        )

        if attempted:

            attempt_strings = []

            for attempt in attempted:

                if isinstance(attempt, dict):

                    attempt_strings.append(
                        attempt.get(
                            "part_file",
                            "unknown",
                        )
                    )

                else:

                    attempt_strings.append(str(attempt))

            remarks.append("Attempts: " + ", ".join(attempt_strings))

        ET.SubElement(
            item,
            "REMARKS",
        ).text = " | ".join(remarks)

        ET.SubElement(
            item,
            "MINQTY",
        ).text = "1"

    xml_bytes = ET.tostring(
        inventory,
        encoding="utf-8",
    )

    xml_str = minidom.parseString(xml_bytes).toprettyxml(indent="  ")

    output_path = OUTPUT_DIR / "failed_studio_review.xml"

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as f:

        f.write("\n".join(line for line in xml_str.splitlines() if line.strip()))

    print("Saved failed Studio review XML")


def export_outputs():

    channels = {
        "bestseller": [],
        "standard": [],
        "out_of_stock": [],
        "all": [],
        "all_in_stock": [],
    }

    for entry in canonical_db.values():

        channel = entry["channel"]

        channels["all"].append(entry)

        if channel != "out_of_stock":

            channels["all_in_stock"].append(entry)

        if channel == "pab":

            channels["bestseller"].append(entry)

        elif channel == "bap":

            channels["standard"].append(entry)

        elif channel == "out_of_stock":

            channels["out_of_stock"].append(entry)

    # XML

    for (
        name,
        entries,
    ) in channels.items():

        xml_output = build_xml(entries)

        with open(
            OUTPUT_DIR / f"lego_inventory_{name}.xml",
            "w",
            encoding="utf-8",
        ) as f:

            f.write(xml_output)

        print(f"Saved XML {name}")

    # Studio palettes

    for (
        name,
        entries,
    ) in channels.items():

        palette_name = "Pick a Brick " + name.replace("_", " ").title()

        palette_output = build_palette(
            entries,
            palette_name,
        )

        with open(
            OUTPUT_DIR / palette_name,
            "w",
            encoding="utf-8",
        ) as f:

            f.write(palette_output)

        print(f"Saved palette " f"{palette_name}")


# ------------------------------------------------------------
# REVERSE INDEX
# ------------------------------------------------------------


def rebuild_reverse_index():

    reverse = {}

    for (
        element_id,
        entry,
    ) in canonical_db.items():
        if not entry["studio"]["resolved"]:
            continue
        key = f"{entry['bricklink']['part_no']}" f"|{entry['bricklink']['color_id']}" f"|{entry['bricklink']['item_type']}"

        if key not in reverse:
            reverse[key] = []

        reverse[key].append(element_id)

    save_json_file(
        BL_TO_LEGO_CACHE_FILE,
        reverse,
    )

    print(f"Saved reverse index " f"{len(reverse)}")


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------


def main():

    load_ldraw_index()

    load_studio_definition_index()

    load_studio_palettes()

    load_studio_exclusions()

    # load_invalid_part_map()

    print("Fetching LEGO inventory")

    results = fetch_lego_inventory()

    #
    # TEMP LIMIT FOR REFACTORING
    #

    if LIMIT_ITEMS:

        results = results[:LIMIT_ITEMS]

        print(f"Refactor limit enabled: " f"{len(results)} items")

    print(f"Unique LEGO items: " f"{len(results)}")

    build_canonical_db(results)

    rebuild_reverse_index()

    export_outputs()
    export_failed_studio_review()
    print(f"Temporary failures: {len(temporary_failures)}")

    for failure in temporary_failures:

        print(
            failure["element_id"],
            failure["reason"],
        )
    print()

    print(
        "Failed Studio mappings:",
        len(failed_studio_cache),
    )

    print("Lookup Statistics")

    for key, value in stats.items():

        print(f"{key}: {value}")

    print("DONE")


if __name__ == "__main__":
    main()
