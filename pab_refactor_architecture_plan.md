# Pick-a-Brick Studio Resolver Refactor Plan

## Core Refactor Goal

Keep the existing `canonical_mapping.json` schema exactly as-is.

Refactor the entire pipeline underneath it into a much smaller, cleaner, modular system.

The new architecture should:
- use authoritative data sources first
- avoid repeated resolution work
- separate concerns cleanly
- allow functionality to be added back incrementally
- resolve Studio parts once per unique BrickLink part
- keep exports and repair logic as optional later stages

---

# What We Know Now

## The real authoritative mapping chain is:

```text
LEGO Element ID
    ->
BrickLink canonical part
    ->
Studio DAT translation
    ->
Canonical DB
```

This is now the actual core system.

---

# Current Major Discoveries

## 1. StudioPartDefinition2.txt is the real resolver

The generated:

```text
studio_part_definitions.json
```

is now the primary and authoritative:

```text
BrickLink part -> DAT file
```

translation layer.

This replaced most heuristic lookup logic.

Current telemetry:

```text
studio_definition_resolved: 15626
studio_unresolved: 664
```

This proved:
- Studio definitions are the real source of truth
- Most previous heuristics were reconstructing data Studio already knew
- LDraw is no longer the primary resolver

---

## 2. LDraw is now secondary

LDraw should now mostly serve as:
- geometry existence validation
- compatibility fallback
- missing geometry source

NOT:
- canonical identity resolution
- primary mapping source

---

## 3. Studio palettes are no longer primary

Studio palette DAT detection is now mostly a compatibility validator.

Not the primary translation layer.

---

## 4. Current system performs too much repeated work

Current architecture resolves Studio per LEGO element:

```text
16734 LEGO items
-> 16734 Studio resolutions
```

But many LEGO elements resolve to the same BrickLink part.

The future architecture should instead:

```text
16734 LEGO items
-> unique BrickLink parts
-> resolve Studio ONCE
-> fan results back out
```

This is likely the single biggest performance improvement.

---

## 5. Repeated unresolved lookups are a major problem

Current logs show repeated unresolved Studio attempts for the same parts.

Meaning:
- no negative cache
- no deduplication
- repeated candidate generation
- repeated filesystem lookups
- repeated unresolved logging

Need:

```python
studio_resolution_cache = {}
studio_negative_cache = {}
```

including caching unresolved results.

---

## 6. Rebrickable fallback entries often have missing metadata

Pattern:

```json
"source": "rebrickable_fallback",
"bricklink": {
  "name": null
}
```

This should NOT be repaired during Studio resolution.

Metadata repair should become a separate isolated post-processing stage.

---

## 7. DUPLO and Braille should be centralized exclusions

Current exclusions:

```text
reject_duplo
reject_braille
```

These should remain.

Future exclusions should also support:
- unsupported assemblies
- physical-only parts
- train axle assemblies
- powered-up internals
- other non-geometry parts

---

## 8. Some parts are fundamentally not resolvable in Studio

Example:

```text
x1687
```

Train wheel metal axle assembly.

Need explicit exclusion database.

Example:

```python
PALETTE_EXCLUSIONS = {
    "x1687": {
        "reason": "physical assembly not modeled in Studio",
        "skip_studio": True,
        "skip_ldraw": True,
    }
}
```

---

# Keep Exactly As-Is

## canonical_mapping.json schema

This is now the stable API and datastore.

Keep structure unchanged.

---

# Keep From Current System

## 1. Studio definition lookup

Keep:

```text
studio_part_definitions.json
```

as the primary Studio resolver.

---

## 2. Color database

Keep current color mapping system.

---

## 3. Rejection helper system

Keep:
- reject_duplo
- reject_braille

---

## 4. Failed review concept

Keep unresolved export concept.

Implementation can change.

---

# Remove Initially

The following should NOT exist in the first clean rebuild:

- incremental update logic
- XML exports
- Studio palette exports
- reverse index generation
- stale entry removal
- retry persistence
- print heuristics
- geometry heuristics
- invalid replacement logic
- alternate traversal
- metadata repair during resolution
- candidate explosion logic
- export telemetry complexity
- LDraw fallback heuristics

All of these can become optional modules later.

---

# Desired Bare-Roots Architecture

# Phase 1 — Load lookup data

Load:

```text
studio_part_definitions.json
color database
```

Optional:

```text
LDraw index
```

only if needed.

---

# Phase 2 — Fetch LEGO inventory

Only:

```text
fetch current PAB inventory
```

---

# Phase 3 — Resolve BrickLink mappings

ONLY:

```text
element_id -> BrickLink part
```

No Studio yet.

---

# Phase 4 — Build unique BrickLink part set

Deduplicate all BrickLink parts.

Example:

```python
unique_parts = {
    ("PART", "3001"),
    ("PART", "3069b"),
}
```

---

# Phase 5 — Resolve Studio once per unique part

PRIMARY:

```text
studio_part_definitions.json
```

No heuristics initially.

No alternates initially.

No print canonicalization initially.

No invalid replacement logic initially.

No LDraw fallback initially.

---

# Phase 6 — Fan Studio results back out

Apply cached Studio results to all canonical entries.

---

# Phase 7 — Build canonical entries

Keep EXACT SAME canonical schema.

---

# Phase 8 — Save canonical DB

Done.

---

# Future Optional Modules

These should become optional add-ons later.

## Optional Modules

### LDraw fallback module

Compatibility / existence fallback only.

---

### InvalidPartMap support

Optional compatibility layer.

---

### Print canonicalization

Optional optimization layer.

---

### Alternate traversal

Optional fallback layer.

---

### Incremental rebuild support

Optional optimization.

---

### Metadata repair pass

Optional post-processing stage.

---

### Reverse index generation

Optional export artifact.

---

### Palette generation

Optional export layer.

---

### BrickLink XML export

Optional export layer.

---

# Desired Future Module Layout

```text
modules/
    lego_api.py
    bricklink_api.py
    studio_resolver.py
    canonical_builder.py
    repair.py
    exports.py
```

---

# Desired Data Flow

```text
LEGO API
    ->
BrickLink mapping
    ->
unique BrickLink parts
    ->
Studio resolution cache
    ->
canonical entries
    ->
exports
```

---

# New Source-of-Truth Hierarchy

## 1. BrickLink Mapping API

Authoritative for:

```text
LEGO element -> BrickLink part
```

---

## 2. StudioPartDefinition2.txt

Authoritative for:

```text
BrickLink part -> DAT file
```

---

## 3. Studio palettes

Compatibility validator only.

Not primary resolver.

---

## 4. LDraw

Fallback geometry source only.

Not primary resolver.

---

# Biggest Architectural Shift

The project is no long
