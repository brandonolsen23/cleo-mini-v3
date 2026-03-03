# Pipeline Stages Strategy — Incremental Improvement Cycle

**Created:** 2026-02-26
**Status:** Stages 1-6 implemented. See docs/pipeline-with-parcelled.md for the authoritative pipeline diagram.

---

## The Pattern That Works

The parsing stage has a cycle that produces stable, incremental improvement:

```
1. Run data through processor (sandbox)
2. Review outputs — confirm good ones as sources of truth
3. Give feedback on bad outputs (writes to a file Claude can read)
4. Claude makes sandbox edits to processor logic based on feedback
5. Re-run data through processor (new sandbox)
6. Diff against confirmed good data — any regressions?
7. If regressions → investigate, fix, re-run
8. If clean → promote to new best version
9. Review more outputs, confirm more sources of truth
10. Repeat
```

**Why it works:**
- You can never go backwards — confirmed-good records are protected
- Every change must prove it didn't break anything already right
- The three-panel review UI gives confidence by showing original source alongside outputs
- Feedback writes directly to a file, closing the loop between review and code edits
- Upstream fixes cascade: if you find a parser bug while working on normalization,
  re-run v015 all the way down through every stage with the same gates

---

## The Three-Panel Review UI

This is the pattern that made the parsing cycle work. For each stage:

```
┌─────────────────┬─────────────────┬─────────────────┐
│                  │                 │                  │
│  PANE 1          │  PANE 2         │  PANE 3          │
│  Original Source │  Current Best   │  Sandbox         │
│  (upstream input)│  (active ver.)  │  (candidate)     │
│                  │                 │                  │
├─────────────────┴─────────────────┴─────────────────┤
│  FEEDBACK BAR                                        │
│  [✓ Clean] [✗ Bad Data] [⚠ Processor Issue] [Notes] │
│  Writes to → data/{stage}_reviews.json               │
└──────────────────────────────────────────────────────┘
```

**Pane 1** shows the upstream input so you can verify what the processor received.
**Pane 2** shows the current best version so you know what's already promoted.
**Pane 3** shows the sandbox output so you can see what changed.
**Feedback bar** writes your determination + notes to a reviews file that Claude reads.

This exact pattern applies at every stage. What changes is what's in each pane.

---

## Stage 1: PARSED `[ACTIVE — v014]`

### Three-panel review

| Pane | Content |
|------|---------|
| **1. Source** | Raw HTML as rendered (the Realtrack page) |
| **2. Active** | Current best parse (v014 JSON, formatted) |
| **3. Sandbox** | New sandbox parse (candidate JSON, formatted) |

### Feedback file: `data/reviews.json`
```json
{
  "RT100008": {
    "date": "2026-02-11",
    "determination": "clean",
    "notes": "Address, price, parties all correct",
    "overrides": {}
  }
}
```

Determinations: `clean` | `bad_source` | `parser_issue`

### What's built
- Versioned store: `data/parsed/v001..v014/`, active symlink
- Three-panel web UI at `cleo web` → review page
- Regression check blocks promotion if confirmed-clean records changed
- Volatile fields excluded from diff: `ingest_timestamp`, `html_path`, `skip_index`

### Current state
- v014 active, 15,806 records (retail only)
- Cycle proven and working

---

## Stage 2: NORMALIZED `[ACTIVE — v024]`

### What it does
Takes raw parsed addresses and produces canonical normalized output.
One direction (expand), structured fields, resolved city names.

### Three-panel review

| Pane | Content |
|------|---------|
| **1. Source** | Parsed JSON address fields (raw from parser) |
| **2. Active** | Current best normalization (v019+ JSON) |
| **3. Sandbox** | New sandbox normalization (candidate) |

What you're checking: Did the raw address normalize correctly?
- "1476 QUEEN ST W" → "1476 QUEEN STREET WEST" (correct expansion)
- City "Scarborough" → "TORONTO" (correct alias resolution)
- "2457 Strathmore Cres" → "2457 STRATHMORE CRESCENT" (abbreviation expansion)

### Feedback file: `data/norm_reviews.json`
```json
{
  "RT100008": {
    "date": "2026-02-27",
    "determination": "clean",
    "notes": "All addresses normalized correctly",
    "overrides": {
      "city_normalized": "HAMILTON"
    }
  },
  "RT196880": {
    "date": "2026-02-27",
    "determination": "normalizer_issue",
    "notes": "ST PAUL STREET became STREET PAUL STREET — saint detection missed"
  }
}
```

Determinations: `clean` | `normalizer_issue` | `bad_upstream` (parser gave bad input)

Claude reads this file, sees the "normalizer_issue" notes, fixes the normalizer,
re-runs sandbox, checks the regression gate, and the cycle continues.

### Versioned store
```
data/normalized/
  sandbox/        ← test new normalization rules
  v001..v019/     ← promoted versions
  active -> v019
```

### Output per RT ID
```json
{
  "rt_id": "RT100008",
  "source_version": "v014",
  "property": {
    "raw_address": "1476 QUEEN ST W",
    "raw_city": "Toronto",
    "normalized_address": "1476 QUEEN STREET WEST",
    "normalized_city": "TORONTO",
    "category": "property"
  },
  "seller": {
    "raw": "2457 Strathmore Cres, Mississauga, Ontario, L5M 5K9",
    "normalized": "2457 STRATHMORE CRESCENT, MISSISSAUGA, ONTARIO, L5M 5K9",
    "category": "corporate_seller"
  },
  "buyer": {
    "raw": "126 Simcoe St, Suite 2007, Toronto, Ontario, M5H 4E9",
    "normalized": "126 SIMCOE STREET, SUITE 2007, TORONTO, ONTARIO, M5H 4E9",
    "category": "corporate_buyer"
  }
}
```

### Volatile fields
- `source_version` (which parse version the input came from)

### Regression check
Record marked `clean` whose normalization output changed → regression → blocks promotion.

### The cycle
```
cleo normalize --sandbox      → Normalize all parsed addresses into sandbox/
cleo normalize --diff         → Compare vs active, check regressions
                                 If regressions → fix normalizer, re-sandbox
cleo normalize --promote      → Promote to new version
cleo web → normalize review   → Three-panel review, confirm/flag
                                 Feedback → data/norm_reviews.json
                                 Claude reads feedback, makes fixes, re-runs
```

---

## Stage 3: EXPANDED `[ACTIVE — v007]`

### What it does
Takes normalized addresses and splits compound street numbers into individual
alternate addresses. Each alternate has decomposed fields for structured matching
and a canonical string for geocoding. No aliases are generated — matching
normalizes both sides at comparison time.

See `docs/expand-stage-plan.md` for the full design (terminology, identity rules,
dedup rules per source, multi-parcel transactions, matching flow).

### Three-panel review

| Pane | Content |
|------|---------|
| **1. Source** | Normalized JSON (from normalize stage) |
| **2. Active** | Current best expansion (v004+ JSON) |
| **3. Sandbox** | New sandbox expansion (candidate) |

What you're checking: Did compound street numbers split correctly?
- "123 & 125 MAIN STREET" → individual entries for 123 and 125
- Single addresses passed through as-is
- PO Boxes, legal descriptions, international addresses flagged as skip_geocode

### Feedback file: `data/expand_reviews.json`
```json
{
  "RT100008": {
    "date": "2026-02-28",
    "determination": "clean",
    "notes": "Expansion correct"
  },
  "RT43746": {
    "date": "2026-02-28",
    "determination": "expander_issue",
    "notes": "123 & 125 MAIN ST split wrong"
  }
}
```

Determinations: `clean` | `expander_issue` | `bad_upstream`

### Output per address entry
```json
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
}
```

### What's built
- Versioned store: `data/expanded/v001..v004/`, active symlink
- Three-panel web UI at `/review/expand`
- CLI cycle: `cleo expand --sandbox/--diff/--promote/--discard/--status`
- Regression gate: confirmed-clean records block promotion if changed
- 29,247 records → 64,244 individual address entries (compound splitting)

### Key design decisions
- **No aliases** — matching normalizes both sides at comparison time
- **No compound form kept** — "123 & 125" splits to [123, 125], compound form stays in normalized data
- **Decomposed fields preserved** — downstream can do structured matching (number + street + city)
- **Identity scoped to source record** — no cross-record linking happens here

---

## Stage 4: GEOCODED `[PLANNED — no review cycle yet]`

### What it does
Takes expanded address strings and gets lat/lng from geocoding providers.

### Three-panel review

| Pane | Content |
|------|---------|
| **1. Source** | Expanded address string (what was sent to geocoder) |
| **2. Active** | Current coordinates + map pin |
| **3. Sandbox** | New/updated coordinates + map pin (if re-geocoded) |

This one is different — instead of text comparison, you're looking at **map pins**.
The review UI shows the address on a map with the geocoded pin. You confirm the
pin is in the right spot or flag it as wrong.

For cases where there's no sandbox (just the cache), the review simplifies to:

| Pane | Content |
|------|---------|
| **1. Source** | Expanded address string |
| **2. Map** | Pin on map at geocoded coordinates |
| **3. Confidence** | Provider details, accuracy scores, agreement |

> **Not yet implemented.** This section describes the planned design. The review cycle for this stage has not been built yet.

### Feedback file: `data/geo_reviews.json`
```json
{
  "1476 QUEEN STREET WEST, TORONTO, ONTARIO": {
    "date": "2026-02-27",
    "determination": "correct",
    "confirmed_lat": 43.6407,
    "confirmed_lng": -79.4372,
    "notes": "Pin is on the building"
  },
  "CONC 4, WHITBY, ONTARIO": {
    "date": "2026-02-27",
    "determination": "not_geocodable",
    "notes": "Legal description — should have been caught upstream"
  }
}
```

Determinations: `correct` | `wrong_location` | `not_geocodable` | `bad_upstream`

### Regression check
Re-geocode produces coordinates >100m from confirmed → regression → keep confirmed coords.

### The cycle
```
cleo geocode                  → Geocode pending addresses (append to cache)
cleo geocode --check          → Flag addresses where coords moved vs confirmed
cleo web → geocode review     → Map view: see pin, confirm/flag
                                 Feedback → data/geo_reviews.json
                                 Claude reads feedback, investigates failures
```

---

## Stage 5: PARCELLED `[IN PROGRESS — engine built, sandbox tested]`

### What it does
Resolves every source record (RT, GW, Brand, OSM) to a provincial assessment parcel using a priority chain: ARN direct (high confidence) → PIN bridge (medium) → spatial/coords query (low) → none.

Reads from:
- `expanded/active/{ID}.json` (source and property addresses with canonicals)
- `parsed/active/{RT_ID}.json` (RT transaction ARN, PINs)
- `gw_parsed/active/{GW_ID}.json` (GW site_structure ARN, registry PIN)
- `coordinates.json` (geocoded coords per canonical address)
- `parcels/parcel_cache.json` (permanent provincial parcel geometry cache)

Writes one parcelled JSON per source record to `parcelled/active/{ID}.json`.

### Three-panel review

| Pane | Content |
|------|---------|
| **1. Source** | Expanded record + input identifiers (ARN, PINs, coords) |
| **2. Active** | Current parcelled output (resolved_arn, method, confidence) |
| **3. Map** | Parcel boundary polygon overlaid on map at centroid |

> Review UI not yet implemented. The versioned store (sandbox/promote/diff) is fully functional.

### Feedback file: `data/parcelled_reviews.json`

Determinations: `correct` | `wrong_parcel` | `bad_upstream`

### Versioned store
```
data/parcelled/
  sandbox/        ← test new resolution results
  v001/           ← promoted version
  active -> v001
```

### Token management
The AgMaps token is auto-fetched via headless browser (`scripts/fetch_agmaps_token.py`).
Token expiry mid-run is handled with automatic refresh.

### The cycle
```
cleo parcelled --sandbox       → Resolve all records (auto-fetches token)
cleo parcelled --sandbox --skip-api  → Cache-only mode (no API calls)
cleo parcelled --diff          → Compare vs active
cleo parcelled --promote       → Promote to new version
cleo parcelled --discard       → Discard sandbox
```

---

## Stage 6: COMPILED `[ACTIVE — v002]`

### What it does
Merges data from all pipeline stages into one unified record per source ID:
- **RT records:** transaction, parties, site, broker, description, photos (bypass from parsed) + addresses (from expanded) + geocode (from coordinates) + parcel (from parcelled)
- **GW records:** addresses + geocode + parcel
- **Brand records:** addresses + geocode + parcel
- **OSM records (planned):** coords + parcel

### Versioned store
```
data/compiled/
  v001/ through v002/
  active -> v002
```

### The cycle
```
cleo compile --sandbox    → Merge all pipeline outputs
cleo compile --diff       → Compare vs active
cleo compile --promote    → Promote to new version
```

---

## Properties Layer (Read-Only Grouping)

### What it does
Groups compiled records by 20-digit ARN into canonical property entries. One property per unique parcel. This is a read-only view built from compiled data — not a separate pipeline stage with its own sandbox/promote cycle.

Properties are rebuilt wholesale with `cleo properties`.

---

## The Cascade: Upstream Fix Flows Downstream

When you find a bug at any stage, the fix cascades cleanly:

```
Example: reviewing normalizations, you notice "123 Main St" has wrong city
because the PARSER gave city "Metro Toronto" instead of "Toronto".

Fix at source:
  1. Flag in norm_reviews.json: determination "bad_upstream"
  2. Fix the parser
  3. cleo parse --sandbox → --diff → --promote (v015)

Cascade downstream:
  4. cleo normalize --sandbox    (reads from v015 now — city is correct)
     cleo normalize --diff       (norm_reviews clean records still clean? yes)
     cleo normalize --promote
  5. cleo expand --sandbox       (reads from new normalization)
     cleo expand --diff
     cleo expand --promote
  6. cleo geocode                (new expanded address → better geocode)
  7. cleo parcelled --sandbox   (re-resolve with new geocoded coords)
     cleo parcelled --diff
     cleo parcelled --promote
  8. cleo compile --sandbox     (merge with new parcel data)
     cleo compile --diff
     cleo compile --promote
  9. cleo properties            (rebuild grouping from compiled ARNs)

Each stage's regression gate ensures the fix didn't break anything.
The audit --log after each promotion shows the numbers improving.
```

---

## Feedback Loop Summary

For each stage, three things need to be true:

1. **You can SEE the original** — the upstream input that went into the processor,
   so you know if the problem is here or upstream

2. **You can COMPARE** — current best vs sandbox candidate, side by side,
   so you can confirm improvements and catch regressions

3. **You can WRITE feedback** — that goes directly to a JSON file that Claude
   can read, understand, and act on immediately

| Stage | Feedback File | Claude Reads It To... |
|---|---|---|
| Parsed | `reviews.json` | Fix parser logic in `cleo/parse/parsers/` |
| Normalized | `norm_reviews.json` | Fix normalizer logic in `cleo/normalize/address.py` |
| Expanded | `expand_reviews.json` | Fix expander logic in `cleo/expand/expander.py` |
| Geocoded | `geo_reviews.json` | Investigate geocode failures, add overrides |
| Parcelled | `parcelled_reviews.json` | Fix resolution chain, add identifiers |
| Compiled | N/A (versioned, not reviewed) | Fix merge logic in `cleo/compiled/engine.py` |

---

## Build Order

```
1. Build Normalized stage         ← DONE (v024)
2. Rewire Expanded stage          ← DONE (v007)
3. Build Parcelled stage          ← DONE (engine built, sandbox tested)
4. Build Compiled stage           ← DONE (v002 active)
5. Add review cycle to Geocoded   ← PLANNED
6. Wire compiler to parcelled     ← IN PROGRESS (need full parcelled run)
7. Properties as read-only layer  ← PLANNED (rebuild from compiled/parcelled ARNs)
```

---

## What NOT To Do

- **Don't re-run brand matching until normalization is stable.** Brand matching
  is downstream of clean data. It's not even a game worth playing until the
  data is clean.

- **Don't promote without reviewing diffs.** Promotions are earned, not automatic.

- **Don't confirm records in bulk.** A small number of carefully reviewed
  confirmations is worth more than mass-confirming everything.

- **Don't skip the regression check.** Investigate why confirmed data changed.
  The regression might reveal a real bug worth fixing.

- **Don't celebrate downstream match numbers.** "1030 new brand matches" means
  nothing if the normalization changes again tomorrow. Track normalization quality,
  not match counts.
