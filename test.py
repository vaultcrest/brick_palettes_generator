#!/usr/bin/env python3

import json
import os

import requests
from dotenv import load_dotenv
from requests_oauthlib import OAuth1

load_dotenv()

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

ELEMENT_ID = "6401028"

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
# REQUEST
# ------------------------------------------------------------

url = "https://api.bricklink.com/api/store/v1/" f"item_mapping/{ELEMENT_ID}"

print(f"Fetching: {url}")

response = requests.get(
    url,
    auth=auth,
    timeout=30,
)

print()
print(f"HTTP {response.status_code}")
print()

response.raise_for_status()

data = response.json()

# ------------------------------------------------------------
# FULL OUTPUT
# ------------------------------------------------------------

print("=== FULL RESPONSE ===")
print()

print(
    json.dumps(
        data,
        indent=2,
        sort_keys=True,
    )
)

print()

# ------------------------------------------------------------
# FIRST MAPPING
# ------------------------------------------------------------

if data.get("data"):

    mapping = data["data"][0]

    print("=== FIRST MAPPING ===")
    print()

    print(
        json.dumps(
            mapping,
            indent=2,
            sort_keys=True,
        )
    )

    print()

    print("=== ITEM OBJECT ===")
    print()

    print(
        json.dumps(
            mapping.get("item", {}),
            indent=2,
            sort_keys=True,
        )
    )
