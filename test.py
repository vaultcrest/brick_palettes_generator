#!/usr/bin/env python3
import json
from pathlib import Path

# ----------------------------
# Load files
# ----------------------------

CACHE_DIR = Path("cache")

canonical_path = CACHE_DIR / "canonical_mapping.json"
studio_lookup_path = CACHE_DIR / "studio_lookup_index.json"

with open(canonical_path, encoding="utf-8") as f:
    canonical = json.load(f)

with open(studio_lookup_path, encoding="utf-8") as f:
    studio_lookup = json.load(f)

# ----------------------------
# Tracking
# ----------------------------

matched = {}
failed = {}

checked = 0
skipped_duplo = 0

for element_id, entry in canonical.items():

    bricklink = entry.get("bricklink", {})
    studio = entry.get("studio", {})

    bricklink_part = bricklink.get("part_no")
    bricklink_name = bricklink.get("name") or ""

    # Skip entries without part numbers
    if not bricklink_part:
        continue

    # Skip DUPLO entries
    if "duplo" in bricklink_name.lower() or studio.get("resolution_method") == "reject_duplo":
        skipped_duplo += 1
        continue

    checked += 1

    studio_file = studio_lookup.get(bricklink_part.lower())

    if studio_file:
        matched[element_id] = studio_file
    else:
        failed[element_id] = bricklink_part

print("Total checked :", checked)
print("Matched       :", len(matched))
print("Failed        :", len(failed))
print("Skipped duplo :", skipped_duplo)

# ----------------------------
# Save failures
# ----------------------------

failed_path = CACHE_DIR / "failed.json"

with open(failed_path, "w", encoding="utf-8") as f:
    json.dump(failed, f, indent=2)

print(f"Failed list saved to: {failed_path}")
