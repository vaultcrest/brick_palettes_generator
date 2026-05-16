#!/usr/bin/env python3

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

#
# CONFIG
#

REBRICKABLE_API_KEY = os.getenv("REBRICKABLE_API_KEY")

#
# TEST ELEMENT
#

ELEMENT_ID = "6577455"

#
# REQUEST
#

url = "https://rebrickable.com/api/v3/lego/" f"elements/{ELEMENT_ID}/"

headers = {
    "Authorization": (f"key {REBRICKABLE_API_KEY}"),
    "User-Agent": ("rebrickable-debug/1.0"),
}

print(f"Fetching LEGO element " f"{ELEMENT_ID}...")

response = requests.get(
    url,
    headers=headers,
    timeout=30,
)

print(f"HTTP {response.status_code}")

response.raise_for_status()

data = response.json()

#
# FULL RAW OUTPUT
#

print("\nFULL RAW RESPONSE:\n")

print(
    json.dumps(
        data,
        indent=2,
    )
)

#
# PART INFO
#

part = data.get("part", {})

print("\nPART INFO:\n")

print(
    json.dumps(
        part,
        indent=2,
    )
)

#
# COLOR INFO
#

color = data.get("color", {})

print("\nCOLOR INFO:\n")

print(
    json.dumps(
        color,
        indent=2,
    )
)

#
# EXTERNAL IDS
#

print("\nPART EXTERNAL IDS:\n")

print(
    json.dumps(
        part.get(
            "external_ids",
            {},
        ),
        indent=2,
    )
)

print("\nCOLOR EXTERNAL IDS:\n")

print(
    json.dumps(
        color.get(
            "external_ids",
            {},
        ),
        indent=2,
    )
)

#
# BrickLink extraction
#

bricklink_ids = part.get(
    "external_ids",
    {},
).get(
    "BrickLink",
    [],
)

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

print("\nRESOLVED BRICKLINK:\n")

print(
    "BrickLink part:",
    bricklink_ids,
)

print(
    "BrickLink color:",
    bl_color_ids,
)

#
# Studio DAT guesses
#

if bricklink_ids:

    bl_part = bricklink_ids[0]

    print("\nPossible Studio DAT names:\n")

    print(f"{bl_part}.dat")

    print(f"bl_{bl_part}.dat")
