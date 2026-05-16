#!/usr/bin/env python3

import json
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

import requests
from curl_cffi import requests as curl_requests
from dotenv import load_dotenv
from requests_oauthlib import OAuth1

load_dotenv()

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

DEBUG = False

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

DATA_DIR = Path("data")

STUDIO_PALETTE_DIR = DATA_DIR / "studio_pallettes"

CANONICAL_DB_FILE = CACHE_DIR / "canonical_mapping.json"

FAILED_CACHE_FILE = CACHE_DIR / "failed_mappings.json"

OVERRIDE_FILE = CACHE_DIR / "manual_overrides.json"

BL_TO_LEGO_CACHE_FILE = CACHE_DIR / "bricklink_to_lego.json"

STUDIO_REFERENCE_FILE = CACHE_DIR / "studio_palette_reference.json"

SNAPSHOT_FILE = CACHE_DIR / "bestseller_snapshot.json"

ITEM_TYPE_MAP = {
    "PART": "P",
    "MINIFIG": "M",
    "SET": "S",
}

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
# LOAD STATE
# ------------------------------------------------------------

manual_overrides = load_json_file(
    OVERRIDE_FILE,
    {},
)

failed_cache = load_json_file(
    FAILED_CACHE_FILE,
    {},
)

canonical_db = {}

studio_reference = {}

# ------------------------------------------------------------
# STUDIO PALETTE REFERENCE PARSER
# ------------------------------------------------------------


def parse_studio_palette_reference():

    global studio_reference

    reference = {}

    if not STUDIO_PALETTE_DIR.exists():

        print("No studio palette dir")

        return {}

    for palette_file in sorted(STUDIO_PALETTE_DIR.iterdir()):

        if not palette_file.is_file():
            continue

        palette_name = palette_file.name

        print(f"Parsing studio palette {palette_name}")

        current_part = None

        with open(
            palette_file,
            encoding="utf-8",
            errors="ignore",
        ) as f:

            for raw_line in f:

                line = raw_line.strip()

                if not line:
                    continue

                if line.startswith("0 "):

                    current_part = line[2:]

                    if current_part not in reference:

                        reference[current_part] = {
                            "seen_in": [],
                        }

                    if palette_name not in reference[current_part]["seen_in"]:

                        reference[current_part]["seen_in"].append(palette_name)

    studio_reference = reference

    save_json_file(
        STUDIO_REFERENCE_FILE,
        studio_reference,
    )

    print(f"Loaded {len(reference)} studio refs")


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

    url = "https://www.lego.com/api/graphql/" "PickABrickQuery"
    headers = {
        "Referer": ("https://www.lego.com/" "en-us/pick-and-build/" "pick-a-brick"),
        "User-Agent": ("Mozilla/5.0"),
    }

    all_results = []

    page = 1

    while True:

        print(f"Fetching page {page}")

        json_body = {
            "operationName": ("PickABrickQuery"),
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

        response.raise_for_status()

        data = response.json()

        search = data["data"]["searchElements"]

        results = search["results"]

        if not results:
            break

        all_results.extend(results)

        if len(results) < per_page:
            break

        page += 1

        time.sleep(0.05)

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

    try:

        response = requests.get(
            url,
            auth=auth,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        if data["meta"]["code"] != 200 or not data["data"]:

            return None

        mapping = data["data"][0]

        return {
            "bl_part_no": (mapping["item"]["no"]),
            "bl_color_id": (mapping["color_id"]),
            "bl_item_type": (mapping["item"]["type"]),
            "source": "bricklink",
        }

    except Exception as e:

        print(
            "BrickLink lookup failed:",
            e,
        )

        return None


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

        ldraw_color_ids = (
            color.get(
                "external_ids",
                {},
            )
            .get(
                "LDraw",
                {},
            )
            .get(
                "ext_ids",
                [],
            )
        )

        return {
            "bl_part_no": (bricklink_ids[0]),
            "bl_color_id": (bl_color_ids[0]),
            "ldraw_color_id": (ldraw_color_ids[0] if ldraw_color_ids else 7),
            "bl_item_type": "PART",
            "source": ("rebrickable_fallback"),
        }

    except Exception as e:

        print(
            "Rebrickable fallback failed:",
            e,
        )

        return None


# ------------------------------------------------------------
# STUDIO PART FILE
# ------------------------------------------------------------


def build_studio_part_file(
    bricklink_part,
):

    if "pb" in bricklink_part or "pr" in bricklink_part:

        return f"bl_{bricklink_part}.dat"

    return f"{bricklink_part}.dat"


# ------------------------------------------------------------
# RESOLVE MAPPING
# ------------------------------------------------------------


def resolve_mapping(
    element_id,
):

    element_id = str(element_id)

    if element_id in manual_overrides:

        return manual_overrides[element_id]

    if element_id in failed_cache:

        return None

    mapping = lookup_bricklink_mapping(element_id)

    if not mapping:

        mapping = lookup_rebrickable_fallback(element_id)

        if mapping:

            manual_overrides[element_id] = mapping

            save_json_file(
                OVERRIDE_FILE,
                manual_overrides,
            )

    if not mapping:

        failed_cache[element_id] = {
            "status": "unresolved",
            "timestamp": (time.time()),
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

    canonical = {}

    for item in results:

        element_id = str(item["id"])

        mapping = resolve_mapping(element_id)

        if not mapping:
            continue

        bricklink_part = mapping["bl_part_no"]

        studio_part = build_studio_part_file(bricklink_part)

        studio_color = mapping.get(
            "ldraw_color_id",
            7,
        )

        canonical[element_id] = {
            "lego": {
                "element_id": (element_id),
                "design_id": (item.get("designId")),
                "name": (item.get("name")),
            },
            "bricklink": {
                "part_no": (bricklink_part),
                "color_id": (mapping["bl_color_id"]),
                "item_type": (mapping["bl_item_type"]),
            },
            "studio": {
                "part_file": (studio_part),
                "color_id": (studio_color),
                "known_studio_part": (studio_part in studio_reference),
            },
            "channel": (get_channel(item)),
            "price": {
                "cent_amount": (
                    item.get("price", {}).get(
                        "centAmount",
                        0,
                    )
                ),
                "formatted": (
                    item.get("price", {}).get(
                        "formattedAmount",
                        "$0.00",
                    )
                ),
            },
            "source": (mapping["source"]),
        }

    canonical_db = canonical

    save_json_file(
        CANONICAL_DB_FILE,
        canonical_db,
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
            f"{entry['lego']['name']} "
            f"(LEGO Element "
            f"{entry['lego']['element_id']})"
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
        "0",
        "-1",
    ]

    seen = set()

    for entry in entries:

        part_file = entry["studio"]["part_file"]

        color_id = entry["studio"]["color_id"]

        key = (
            part_file,
            color_id,
        )

        if key in seen:
            continue

        seen.add(key)

        lines.append(f"0 {part_file}")

        lines.append(f"1 {entry['lego']['name']}")

        lines.append(f"2 {color_id}")

    return "\n".join(lines)


# ------------------------------------------------------------
# EXPORTS
# ------------------------------------------------------------


def export_outputs():

    channels = {
        "bestseller": [],
        "standard": [],
        "out_of_stock": [],
        "all": [],
    }

    for entry in canonical_db.values():

        channel = entry["channel"]

        channels["all"].append(entry)

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

        palette_output = build_palette(
            entries,
            name,
        )

        with open(
            OUTPUT_DIR / f"{name}",
            "w",
            encoding="utf-8",
        ) as f:

            f.write(palette_output)

        print(f"Saved palette {name}")


# ------------------------------------------------------------
# REVERSE INDEX
# ------------------------------------------------------------


def rebuild_reverse_index():

    reverse = {}

    for (
        element_id,
        entry,
    ) in canonical_db.items():

        key = (
            f"{entry['bricklink']['part_no']}"
            f"|{entry['bricklink']['color_id']}"
            f"|{entry['bricklink']['item_type']}"
        )

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

    parse_studio_palette_reference()

    print("Fetching LEGO inventory")

    results = fetch_lego_inventory()

    unique = {}

    for item in results:

        unique[item["id"]] = item

    results = list(unique.values())

    print(f"Unique LEGO items: " f"{len(results)}")

    build_canonical_db(results)

    rebuild_reverse_index()

    export_outputs()

    print("DONE")


if __name__ == "__main__":
    main()
