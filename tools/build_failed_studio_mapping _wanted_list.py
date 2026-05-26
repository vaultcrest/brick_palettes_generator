#!/usr/bin/env python3

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

CACHE_DIR = Path("cache")
OUTPUT_DIR = Path("output")

FAILED_MAPPINGS_FILE = CACHE_DIR / "failed_studio_mappings.json"

OUTPUT_XML_FILE = OUTPUT_DIR / "failed_studio_review.xml"

# -------------------------------------------------------------------
# LOAD FAILED MAPPINGS
# -------------------------------------------------------------------

with open(
    FAILED_MAPPINGS_FILE,
    encoding="utf-8",
) as f:

    failed_mappings = json.load(f)

# -------------------------------------------------------------------
# BUILD XML
# -------------------------------------------------------------------

inventory = ET.Element("INVENTORY")

count = 0

for element_id, entry in sorted(failed_mappings.items()):

    bricklink_part = entry.get("bricklink_part")

    bricklink_color_id = entry.get("bricklink_color_id")

    lego_name = entry.get(
        "lego_name",
        "Unknown LEGO Part",
    )

    #
    # Skip malformed entries
    #

    if not bricklink_part:
        continue

    if bricklink_color_id is None:
        continue

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
    ).text = str(bricklink_part)

    ET.SubElement(
        item,
        "COLOR",
    ).text = str(bricklink_color_id)

    ET.SubElement(
        item,
        "MAXPRICE",
    ).text = "0.0000"

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
        f"{lego_name} " f"(LEGO Element {element_id})"
    )

    ET.SubElement(
        item,
        "NOTIFY",
    ).text = "N"

    count += 1

# -------------------------------------------------------------------
# PRETTY FORMAT XML
# -------------------------------------------------------------------

xml_bytes = ET.tostring(
    inventory,
    encoding="utf-8",
)

pretty_xml = minidom.parseString(xml_bytes).toprettyxml(indent="  ")

# Remove empty lines
pretty_xml = "\n".join(line for line in pretty_xml.splitlines() if line.strip())

# -------------------------------------------------------------------
# WRITE FILE
# -------------------------------------------------------------------

with open(
    OUTPUT_XML_FILE,
    "w",
    encoding="utf-8",
) as f:

    f.write(pretty_xml)

# -------------------------------------------------------------------
# OUTPUT
# -------------------------------------------------------------------

print(f"Saved failed Studio review XML: " f"{OUTPUT_XML_FILE}")

print(f"XML items written: {count}")
