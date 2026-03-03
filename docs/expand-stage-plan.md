# Expand Stage — Design Plan

**Created:** 2026-02-28
**Status:** Implemented — v004 active
**Current:** 29,247 input records → 64,244 expanded address entries

---

## Purpose

The expand stage has one job: **split compound street numbers into individual addresses**.

A transaction listing "123, 125 & 129 MAIN STREET" contains three real addresses.
The expand stage splits them so each can be geocoded and matched to a parcel independently.

That's all it does. No alias generation. No cross-record linking. No dedup.

---

## Terminology

These two terms are different things with different purposes. Never conflate them.

| Term | Definition | Example | Geocode? | Store? |
|------|-----------|---------|----------|--------|
| **Alternate address** | A real, distinct address from the raw data. Represents a real piece of dirt. May come from the source directly (property_alt) or from compound splitting. | "123 MAIN ST" and "125 MAIN ST" from the same transaction | Yes | Yes |
| **Alias** | A spelling variant of the same address, used only for matching at comparison time. | "123 MAIN ST" vs "123 MAIN STREET" | No | No — never stored, never generated |

**Alternates** exist in the data. They're geocoded, matched to parcels, and linked to transactions.

**Aliases** don't exist anywhere. Matching normalizes both sides to the same long form
at comparison time (via `properties/normalize.py`). No pre-generation needed.

---

## Where Alternates Come From

There are two sources of alternate addresses for a given record:

1. **From the raw data (property_alt).** The parser extracted multiple distinct addresses
   from the source HTML. These arrive in the normalized data as separate address blocks
   under `property_alt`. Expand passes them through as-is (one address entry per block).

2. **From compound splitting.** A single address block with a compound street number
   like "123 & 125" gets split into individual addresses [123, 125]. Each becomes its
   own alternate. The compound form ("123 & 125 MAIN STREET") is NOT kept as an
   additional entry — it's the source representation, preserved in the normalized data
   if anyone needs it.

After expand, every address entry is a single, individual, geocodable address.

---

## Output Structure

### Per record
```json
{
  "id": "RT12345",
  "source": "realtrack",
  "source_version": "v019",
  "property": {
    "addresses": [
      {
        "street_number": "123",
        "street_name": "MAIN",
        "street_suffix": "STREET",
        "street_direction": "",
        "unit": "",
        "unit_type": "",
        "city": "LONDON",
        "province": "ONTARIO",
        "canonical": "123 MAIN STREET, LONDON, ONTARIO",
        "skip_geocode": false
      },
      {
        "street_number": "125",
        "street_name": "MAIN",
        "street_suffix": "STREET",
        "street_direction": "",
        "unit": "",
        "unit_type": "",
        "city": "LONDON",
        "province": "ONTARIO",
        "canonical": "125 MAIN STREET, LONDON, ONTARIO",
        "skip_geocode": false
      }
    ]
  },
  "property_alt": [
    {
      "addresses": [
        {
          "street_number": "200",
          "street_name": "KING",
          "street_suffix": "STREET",
          "street_direction": "",
          "unit": "",
          "unit_type": "",
          "city": "LONDON",
          "province": "ONTARIO",
          "canonical": "200 KING STREET, LONDON, ONTARIO",
          "skip_geocode": false
        }
      ]
    }
  ],
  "seller": {
    "addresses": [
      {
        "street_number": "500",
        "street_name": "BAY",
        "street_suffix": "STREET",
        "street_direction": "",
        "unit": "2007",
        "unit_type": "SUITE",
        "city": "TORONTO",
        "province": "ONTARIO",
        "canonical": "500 BAY STREET SUITE 2007, TORONTO, ONTARIO",
        "skip_geocode": false
      }
    ]
  },
  "buyer": { "addresses": [...] },
  "owner_address": { "addresses": [...] },
  "raw_coords": { "lat": 43.1, "lng": -81.2, "source": "brand_scraper" }
}
```

### Field definitions

| Field | Description |
|-------|-------------|
| `street_number` | Individual street number (never compound — "123", not "123 & 125") |
| `street_name` | Street name, already normalized to long form by normalizer |
| `street_suffix` | STREET, AVENUE, DRIVE, etc. — long form from normalizer |
| `street_direction` | NORTH, SOUTH, EAST, WEST — long form from normalizer |
| `unit` | Unit/suite number if present |
| `unit_type` | SUITE, UNIT, APARTMENT, FLOOR, BUILDING |
| `city` | Normalized city name from normalizer |
| `province` | Normalized province from normalizer |
| `canonical` | Reassembled full string for geocoding/display (deterministic from fields above) |
| `skip_geocode` | True for PO boxes, legal descriptions, empty, international addresses |

### What skip_geocode means

These addresses exist in the data and should be preserved, but aren't suitable for geocoding:

- **PO boxes** — not a physical location
- **Legal descriptions** — "CONC 4 PT LOT 7" isn't geocodable
- **International addresses** — outside Ontario, not relevant to parcel matching
- **Empty blocks** — address block existed but had no usable content (these return null, not skip_geocode)

Skipped addresses are still stored in the expanded output so the review UI can show them.
They just don't get sent to the geocoder.

---

## Identity Rules

These rules prevent the "party grouping chain" problem.

### Rule 1: Scoped to source record

Every expanded address belongs to exactly one record (RT12345, BR_00001, GW00001).
The expand stage never looks at other records. It processes one record at a time
with no shared state.

### Rule 2: No cross-linking in expand

The expand stage never says "this address from RT12345 is the same as that address
from BR_00001." It has no opinion on matching. It just splits compounds and passes
through fields.

### Rule 3: The property registry is the only merge point

The property registry (`properties.json`) is where records from different sources
get associated with the same physical property. This is the ONLY place in the system
where cross-source linking happens.

### Rule 4: One-way flow

```
Normalized → Expanded → Geocoded → Matched to Property
```

Data flows forward. A property record never pushes data back into expanded records.
The expanded output is immutable once promoted.

### Rule 5: Transactions attach, never merge

An RT transaction is always unique. Two sales of the same building are two separate
RT records that both MATCH to the same property. They don't merge. They don't dedupe.
They attach.

---

## Dedup Rules (per source)

Dedup does NOT happen in the expand stage. These rules are documented here because
they affect how expanded data gets consumed downstream.

### Realtrack — NEVER dedupe

Every RT transaction is unique. Period.

- Two RT records at the same address = two separate transactions (different sales)
- They both match to the same property in the registry
- They both keep their own expanded data

### Brands — Dedupe within brand + address

There's only one A&W at 123 Main Street. If two A&W records have the same address,
keep one.

- Different brands at the same address are NOT duplicates (A&W and Tim Hortons
  in the same building = two tenants, one parcel)
- Dedup happens at brand import time, NOT in the expand stage

### GeoWarehouse — Newest scrape per PIN takes precedence

GW records aren't deduped or deleted. Every scrape is saved.

- Same PIN scraped twice = the newer scrape's data takes precedence
- The older scrape isn't deleted — the newest just wins
- GW already handles this in `gw/engine.py` (dedup by PIN during parsing)
- If property info changes between scrapes (e.g. new assessment value),
  the newer version is the one that gets used

---

## Multi-Parcel Transactions

A transaction might list multiple addresses. After expand, each address is an
individual alternate. But **multiple addresses can map to the same parcel**.

```
RT transaction: "123 & 125 MAIN STREET"
  After expand:
    Alternate 1: 123 MAIN STREET
    Alternate 2: 125 MAIN STREET

  After geocode + parcel matching:
    Possibility A: Both land on PARCEL-001 (same lot, two frontages)
    Possibility B: 123 → PARCEL-001, 125 → PARCEL-002 (adjacent lots, multi-parcel deal)
    Possibility C: 123 → PARCEL-001, 125 → no match (one geocoded well, other didn't)
```

The expand stage makes no assumptions about this. It splits the compound into
individual geocodable addresses. Parcel matching downstream (point-in-polygon,
PIN lookup) determines which addresses land on which parcels.

The transaction (RT12345) gets linked to whatever parcel(s) its alternates resolve to.

---

## Matching Flow

Matching happens OUTSIDE the expand stage. This is how it works:

### Property registry matching (existing logic in properties/normalize.py)

Both sides normalize to the same long form before comparison:

```
Incoming:  "123 Main St"
Registry:  "123 MAIN STREET"

normalize("123 Main St")      → "123 MAIN STREET"
normalize("123 MAIN STREET")  → "123 MAIN STREET"
                                  ↑ same = match
```

`make_dedup_key(address, city)` handles:
- ST → STREET, AVE → AVENUE, HWY → HIGHWAY (suffix expansion)
- E → EAST, N → NORTH (direction expansion)
- City aliases (Scarborough → TORONTO, Stoney Creek → HAMILTON)
- Whitespace, punctuation normalization

This already works. No aliases needed.

### Brand matching (existing logic in brands/match.py)

1. Index properties by (street_number, normalized_city)
2. For each brand store, look up (number, city) in index
3. Score candidates by fuzzy street name similarity
4. Best match >= 0.6 threshold wins

Also already works without aliases.

### The expand stage's role in matching

Without expand: "123 & 125 MAIN ST" is a single compound address. It won't match
a brand at "123 MAIN ST" because the string "123 & 125" doesn't equal "123".

After expand: you have "123 MAIN STREET" and "125 MAIN STREET" as individual entries.
Now "123 MAIN STREET" matches the brand at "123 MAIN ST" via normalization.

That's the value. Expand makes compound addresses matchable by splitting them into
their individual components.

---

## What Gets Geocoded

All non-skipped alternate addresses from ALL roles get geocoded.

| Role | Geocode? | Why |
|------|----------|-----|
| property | Yes | Core transaction address — needs parcel matching |
| property_alt | Yes | Additional addresses from same transaction — also real parcels |
| seller | Yes | Seller's mailing address — useful for mapping seller geography |
| buyer | Yes | Buyer's mailing address — useful for mapping buyer geography |
| owner_address | Yes | GW owner address — useful for ownership mapping |

The geocoder dedupes by canonical string before sending to providers. If RT12345
and RT67890 both have "123 MAIN STREET, LONDON, ONTARIO", it geocodes once and
both records get the same coordinates from the cache.

Rough volume:
- ~29,247 records × ~1.5 addresses average = ~44K total addresses
- Dedup by canonical string → ~25-30K unique
- Minus skip_geocode → ~22-25K geocodable
- Many already in geocode cache (36K entries) → incremental only

---

## Code Changes Required

### 1. Simplify `cleo/expand/expander.py`

**Remove:**
- `_make_aliases()` function
- `_SUFFIX_ABBREVS` and `_DIR_ABBREVS` reverse maps
- `_build_location_suffix()` with `abbrev_province` parameter
- The "full compound form as extra entry" logic (lines 282-289)
- Import of `_STREET_TYPE_MAP`, `_DIRECTION_MAP` from properties.normalize

**Keep:**
- `_split_compound()` — the core value
- `_should_skip()` — skip_geocode logic
- `_reassemble_street()` — rebuild street from decomposed fields
- `_HIGHWAY_AMP_RE` — highway compound name detection
- All compound regex patterns

**Add:**
- Preserve decomposed fields in output (street_number, street_name, etc.)
- Build canonical from decomposed fields (deterministic reassembly)
- For compound splits, rewrite street_number for each individual address

**`expand_block()` new logic:**
```
1. Check if block is empty/skip → return null or skip entry
2. Reassemble street from decomposed fields
3. If no street (PO box, rural route, etc.) → pass through with skip_geocode
4. Split compound street numbers via _split_compound()
5. For each individual street:
   a. Extract the individual street number from the split string
   b. Copy all other fields from the original block (name, suffix, dir, city, etc.)
   c. Build canonical from the fields
   d. Set skip_geocode based on category/scope
6. Return list of address entries with decomposed fields
```

### 2. Update `cleo/expand/engine.py`

Minimal change — the engine just calls `expand_record()` and writes JSON.
The output structure change flows through automatically.

### 3. Update `cleo/web/static/review_expand.html`

- Remove alias display
- Show decomposed fields per address entry
- Show canonical string
- Show skip_geocode badge
- Diff highlighting on canonical between active and sandbox

### 4. Update `cleo/web/app.py`

No structural change to endpoints. The JSON shape changes but the endpoints
serve whatever's in the expanded files.

### 5. Update `docs/pipeline-stages-strategy.md`

- Stage 3 description to reflect "compound splitting only, no aliases"
- Update output format example
- Update feedback file reference to `expand_reviews.json`

---

## What Does NOT Change

- **Normalize stage** — expand consumes its output, doesn't modify it
- **Property registry** — still reads from legacy extracted/ for now (future wiring)
- **Geocode collector** — still reads from legacy extracted/ for now (future wiring)
- **Brand matching** — still reads from properties.json directly
- **GW matching** — still reads from gw_parsed directly
- **Review UI pattern** — still three-panel (Normalized Source | Active Expanded | Sandbox)
- **Sandbox/promote/regression cycle** — same pattern as all other stages

---

## Build Order

```
1. Simplify expander.py        ← Remove aliases, add decomposed fields to output
2. Rebuild sandbox              ← cleo expand --sandbox
3. Diff against v001            ← cleo expand --diff (structure changed, expect diffs)
4. Update review UI             ← Show decomposed fields, remove alias display
5. Review via UI                ← Spot-check compound splits
6. Promote to v002              ← cleo expand --promote
```

---

## Future Work

These happen after the expand output format is stable (v004 is stable):

1. **Wire geocode collector to read from expanded/** instead of extracted/ — NEXT
2. **Wire property registry to read from expanded/** instead of extracted/ — NEXT
3. **Retire the legacy extracted/ pipeline** once downstream is fully wired — DEFERRED (after geocode + property registry are wired to expanded/)
4. **Add parcel matching** — geocoded coordinates → point-in-polygon → parcel assignment — IN PROGRESS (cleo/parcels/ module exists)
5. **Multi-parcel transaction linking** — associate transaction with multiple parcels
   when alternates land on different parcels — DEFERRED (after parcel matching is complete)
