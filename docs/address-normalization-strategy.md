# Address Normalization Strategy — Phase 0

**Created:** 2026-02-25
**Status:** Approved
**Priority:** #1 — blocks all downstream work (parcels, party grouping, app reorg)

---

## Why This Matters

Every feature in the system — map pins, brand matching, parcel boundaries, portfolio views, party grouping — depends on addresses being clean and consistent. The rest doesn't matter if the data isn't good.

---

## The Pipeline (Definitive Order)

This is the single path every address follows, regardless of source:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  1. RAW ADDRESS        Any source: Realtrack, brands, GeoWarehouse, GIS    │
│         │                                                                   │
│         ▼                                                                   │
│  2. NORMALIZE          Clean → Standardize → Resolve city                  │
│         │              Output: NormalizedAddress (structured, canonical)     │
│         ▼                                                                   │
│  3. EXPAND (PACKAGE)   Split compounds, bundle all forms as aliases        │
│         │              "123-125 Main St" → package with 3 searchable forms │
│         │              Non-compounds pass through as single-item packages  │
│         ▼                                                                   │
│  4. GEOCODE            Get lat/lng for each form in the package            │
│         │              Best coordinates assigned to the package             │
│         ▼                                                                   │
│  5. PARCEL LOOKUP      Spatial query with lat/lng (PRIMARY)                │
│         │              Address string query (FALLBACK only)                 │
│         │              Returns: PIN, boundary, zoning, assessment           │
│         ▼                                                                   │
│  6. COMBINE            Merge into one property record with full context    │
│                        Dedup by key, merge by PIN, tag with category       │
│                        Output: Property with aliases, coords, parcel, tags │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why this order matters

**Normalize BEFORE expand:** The expander gets clean, consistent input every time. No periods, no mixed case, no abbreviation variants. Expanded sub-addresses inherit the normalization for free.

**Geocode BEFORE parcel lookup:** A lat/lng spatial query ("which parcel contains this point?") is far more reliable than matching address strings against municipal databases. The current harvester already supports spatial queries (`query_at_point` + `_find_containing_parcel`) but uses them as a fallback. This pipeline makes spatial queries the primary strategy.

**Package concept:** A compound address like "123-125 Main St" doesn't become 3 separate properties. It becomes one address package with 3 searchable aliases, one set of coordinates, one parcel, one P-ID. Search for any alias, find the same property.

---

## Current State: What's Broken

### 6 separate normalization implementations

| Module | File | Direction | City Aliases | Suite Handling |
|--------|------|-----------|-------------|----------------|
| Property dedup | `cleo/properties/normalize.py` | Expand (ST→STREET) | 228 entries | None |
| Party clustering | `cleo/parties/normalize.py` | Expand (7 patterns) | None | None |
| Brand matching | `brands/match.py` | Contract (STREET→ST) | 12 entries | Strips prefix |
| GeoWarehouse | `cleo/geowarehouse/address.py` | None (raw MPAC) | None | None |
| Parcel harvester | `cleo/parcels/harvester.py` | Contract (STREET→ST) | None | Strips unit/apt |
| Address expander | `cleo/extract/address_expander.py` | None | None | None |

Property dedup **expands** abbreviations while brand matching and parcel harvester **contract** them. They normalize in opposite directions. The same address can produce different canonical forms depending on which code path touches it.

### Normalize happens too late

Currently: parse → expand (raw) → geocode → normalize (at dedup time). The expander works on raw messy input. Normalization should happen immediately after parsing, before anything else touches the address.

### No searchable aliases for compound addresses

When Realtrack gives us "123 - 125 Main St", the expander produces `["123 Main St", "125 Main St"]` for geocoding. But the property is keyed only on the compound form. Searching for "123 Main St" returns nothing.

### Parcel lookup does string matching first, spatial queries second

The harvester tries address LIKE queries against ArcGIS (fragile, abbreviation-sensitive), and only falls back to lat/lng spatial queries if the string match fails. This is backwards — spatial queries should be primary.

### No address categories

The geocode collector tags addresses with `role` (property, seller, buyer), but this isn't carried through the pipeline. All geocoded addresses end up in the same cache with no way to filter what shows on the map vs. what's a corporate address.

### City alias table is hand-maintained

228 entries built by hand. No systematic way to catch gaps. New community names silently fail normalization rather than being flagged for review.

---

## Architecture: One Module, One Direction, One Dataclass

### Single canonical module: `cleo/normalize.py`

Every module that touches addresses imports from this one file. No more local abbreviation dicts, no more per-module city alias tables.

### One direction: expand to long form

All abbreviations expand: ST→STREET, AVE→AVENUE, N→NORTH, DR→DRIVE, etc. This is:
- More readable for humans
- Less ambiguous for geocoders (ST could be STREET or SAINT — expanded form resolves this)
- Consistent with the existing property dedup module (our largest normalization investment)

### Structured output: `NormalizedAddress` dataclass

```python
@dataclass(frozen=True)
class NormalizedAddress:
    street_number: str            # "123"
    street_name: str              # "MAIN STREET EAST"
    unit: str | None              # "SUITE 200" or None
    city: str                     # "TORONTO" (after alias resolution)
    province: str                 # "ONTARIO"
    postal_code: str | None       # "M5V 1K5" (formatted with space) or None
    raw: str                      # Original input preserved exactly as received
    category: AddressCategory     # property | corporate_seller | corporate_buyer | brand | geowarehouse | mailing

    @property
    def full_street(self) -> str:
        """Street number + name, no unit."""
        return f"{self.street_number} {self.street_name}"

    @property
    def dedup_key(self) -> str:
        """Primary dedup key: 'STREET_NUMBER STREET_NAME|CITY'"""
        return f"{self.full_street}|{self.city}"

    @property
    def geocode_query(self) -> str:
        """Best-effort geocoding string."""
        parts = [self.full_street]
        if self.unit:
            parts[0] = f"{parts[0]}, {self.unit}"
        parts.extend([self.city, self.province])
        if self.postal_code:
            parts.append(self.postal_code)
        return ", ".join(parts)

    @property
    def display(self) -> str:
        """Human-readable display form."""
        parts = [self.full_street]
        if self.unit:
            parts.append(self.unit)
        parts.append(self.city)
        return ", ".join(parts)
```

### Three normalization layers

```
Layer 1: CLEAN
  - Uppercase
  - Strip periods (but protect "St." before saint names)
  - Collapse whitespace
  - Normalize unicode (é→e, ½→1/2)

Layer 2: STANDARDIZE
  - Protect saint names: "ST PAUL" → "SAINT PAUL" before ST→STREET
  - Expand street types: ST→STREET, AVE→AVENUE, RD→ROAD, DR→DRIVE, etc.
  - Expand directions: N→NORTH, E→EAST, W→WEST, S→SOUTH
  - Extract and normalize unit: UNIT|SUITE|STE|APT|#|FLOOR → "SUITE N" or "UNIT N"
  - Extract street number (handle letter suffixes: 620A, 373B)
  - Strip suite prefixes from brand data (B03-70 → 70)

Layer 3: CONTEXTUALIZE
  - Resolve city aliases (Thornhill→VAUGHAN, Scarborough→TORONTO)
  - Flag unknown cities (not in municipal reference list)
  - Normalize province (Ontario/ON/Ont. → ONTARIO)
  - Format postal code (M5V1K5 → M5V 1K5)
  - Detect non-Ontario addresses (flag, don't normalize)
```

---

## Design Decision 1: Compound Addresses & Aliases

### The problem

Realtrack gives us "123 - 125 Main St". Today, the expander creates two geocoding queries but the property is keyed only on the compound form. Searching for "123 Main St" finds nothing.

### The solution

Every property gets an `aliases` list. For compound addresses, ALL forms are stored:

```json
{
  "P00042": {
    "address": "123 - 125 MAIN STREET EAST",
    "city": "TORONTO",
    "aliases": [
      "123 MAIN STREET EAST",
      "125 MAIN STREET EAST",
      "123 - 125 MAIN STREET EAST"
    ],
    "rt_ids": ["RT50001"],
    ...
  }
}
```

**Rules:**
- One P-ID per property, regardless of how many aliases it has
- The `address` field is the primary form (the raw compound, normalized)
- The `aliases` list contains ALL searchable forms (including the primary)
- Search checks aliases, not just the primary address
- Brand matching checks aliases
- Parcel lookups try each alias until one returns a hit
- Geocoding submits all aliases (compound + each expansion)
- If a standalone transaction exists for "123 Main St" AND a compound transaction exists for "123 - 125 Main St", they merge into one property with both RT IDs

### How this works in the registry

```
Phase 1: Scan parsed data → build initial property entries with raw address
Phase 2: Scan extracted data → for compound addresses, add expanded forms to aliases
Phase 3: Cross-reference → if "123 Main St" exists as both a standalone AND as an alias
          of "123 - 125 Main St", merge the standalone into the compound property
Phase 4: PIN-based merge (existing)
Phase 5: Loose directional merge (existing)
```

The alias list also captures other match-worthy forms:
- Brand data that abbreviates differently ("123 Main St E" vs "123 MAIN STREET EAST")
- GeoWarehouse address format differences
- User-corrected addresses from the review UI

---

## Design Decision 2: Address Categories

### Every address gets a category

```python
class AddressCategory(str, Enum):
    PROPERTY = "property"                # Transaction property — shows on main map
    CORPORATE_SELLER = "corporate_seller" # Seller corp address — geocoded, not on main map
    CORPORATE_BUYER = "corporate_buyer"   # Buyer corp address — geocoded, not on main map
    BRAND = "brand"                       # Brand store location — shows on map as brand overlay
    GEOWAREHOUSE = "geowarehouse"         # MPAC property address — merges with property
    MAILING = "mailing"                   # GW owner mailing address — geocoded, not on main map
```

### Where each category goes

| Category | Geocode? | Main Map? | Ownership Map (future)? | Property Registry? |
|----------|----------|-----------|------------------------|-------------------|
| `property` | Yes | Yes | No | Yes — primary |
| `corporate_seller` | Yes | No | Yes (as corp HQ) | No — stored on party |
| `corporate_buyer` | Yes | No | Yes (as corp HQ) | No — stored on party |
| `brand` | Yes | Yes (brand overlay) | No | Yes — merged via matching |
| `geowarehouse` | Yes | Yes (merged) | No | Yes — merged via PIN |
| `mailing` | Yes | No | Yes (as mailing addr) | No — stored on GW record |

### How this flows

The category is assigned at the earliest point — when the address is first extracted or ingested — and carried through every step:

```
Realtrack parser → property address tagged as PROPERTY
                 → seller address tagged as CORPORATE_SELLER
                 → buyer address tagged as CORPORATE_BUYER
Brand scraper    → store address tagged as BRAND
GW parser        → property_address tagged as GEOWAREHOUSE
                 → owner_mailing_address tagged as MAILING
```

The geocode collector already tracks `role` — this formalizes it as a proper enum and carries it through to the property/party registries and the frontend.

### Future: Ownership map

When you eventually build the ownership map, you'll have corporate addresses already geocoded and categorized. You'll be able to show: "This company at 18 York St, Suite 1500, Toronto owns properties at [pin] [pin] [pin]." The data will be ready because we categorized it now.

---

## Design Decision 3: City Consolidation — Authoritative Source

### The problem

The 228-entry `CITY_ALIASES` dict in `normalize.py` was hand-built. When a new community name appears in the data (from a brand scraper, a new Realtrack record, or a GeoWarehouse file), it silently fails to resolve rather than being flagged.

### The solution: Three-tier city resolution

**Tier 1: Ontario Municipal Directory (canonical)**

Ontario has 444 municipalities. We already pull this from Wikipedia's "List of municipalities in Ontario" via `build_markets.py` → `markets.json` (544 entries including aliases). This becomes the canonical reference.

Build a `data/municipalities.json` that contains:
```json
{
  "TORONTO": {
    "official_name": "Toronto",
    "tier": "single",
    "population": 2794356,
    "communities": [
      "NORTH YORK", "SCARBOROUGH", "ETOBICOKE", "YORK",
      "EAST YORK", "DOWNSVIEW", "WILLOWDALE", "DON MILLS",
      "AGINCOURT", "WESTON", "REXDALE", "LEASIDE"
    ]
  },
  "VAUGHAN": {
    "official_name": "Vaughan",
    "tier": "lower",
    "upper_tier": "York Region",
    "population": 323103,
    "communities": ["WOODBRIDGE", "MAPLE", "CONCORD", "KLEINBURG", "THORNHILL"]
  }
}
```

**Tier 2: Variant/abbreviation corrections (manual)**

Handles spelling variants, abbreviations, and typos that aren't community names:
```json
{
  "N. YORK": "TORONTO",
  "N YORK": "TORONTO",
  "E. YORK": "TORONTO",
  "S.S. MARIE": "SAULT STE. MARIE",
  "S.S.MARIE": "SAULT STE. MARIE",
  "ST CATHARINES": "ST. CATHARINES",
  "SAULT STE MARIE": "SAULT STE. MARIE"
}
```

**Tier 3: Unknown city flagging**

When a city isn't found in Tier 1 (communities) or Tier 2 (variants), it gets flagged for human review rather than silently passing through:

```json
{
  "unknown_cities": {
    "METRO TORONTO": {
      "first_seen": "2026-02-25",
      "count": 142,
      "sample_addresses": ["123 MAIN ST", "456 QUEEN ST W"],
      "suggested_resolution": "TORONTO"
    }
  }
}
```

A CLI command (`cleo normalize --review-cities`) shows unknown cities and lets you resolve them, which adds them to Tier 2.

### Keeping it current

Enhance `build_markets.py` (or create `build_municipalities.py`) to:
1. Pull the official municipality list from Wikipedia/Stats Canada (already does this)
2. Build the community → municipality reverse mapping (new)
3. Cross-reference against the existing `CITY_ALIASES` dict to catch gaps
4. Output `data/municipalities.json` as the source of truth
5. Move `CITY_ALIASES` from a hardcoded Python dict to loaded from this JSON file

When the JSON is the source, anyone can add an entry without touching Python code.

---

## Implementation Plan

The steps follow the pipeline order. Each step builds the next piece of the chain.

---

### Step 1: Audit current state (read-only, no risk)

Build `scripts/audit_addresses.py` that scans every address in the system and reports baseline metrics. This tells us where the biggest wins are before we write any normalization code.

**Per-source breakdown:**
- Realtrack: X addresses parsed, Y geocoded successfully, Z failed (by failure category)
- Brands: X locations, Y matched to properties, Z unmatched (by reason)
- GeoWarehouse: X records, Y matched to properties, Z unmatched
- Parcels: X lookups attempted, Y returned geometry, Z failed

**Normalization metrics:**
- How many raw addresses collapse to the same normalized form (dedup working)
- How many addresses from different sources normalize to different forms for the same physical place (dedup failing)
- How many city names aren't in the alias table

**Known-bad categories:**
- No street number
- Legal descriptions (not geocodable)
- PO Box / rural route
- Intersections (NEC/SWC/etc.)
- Non-Ontario addresses (USA, international)
- Unknown city names

---

### Step 2: Build `cleo/normalize.py` — Pipeline Stage 2 (NORMALIZE)

The canonical normalization module. Every module that touches addresses imports from here. No more local abbreviation dicts or city alias tables elsewhere.

**Consolidate from existing code:**
- `cleo/properties/normalize.py` — saint name protection, abbreviation expansion, city aliases (228 entries)
- `brands/match.py` — suite prefix stripping, city aliases (12 entries, merge any missing)
- `cleo/parcels/harvester.py` — unit stripping regex
- `cleo/geowarehouse/address.py` — MPAC format parsing

**Core API:**
```python
# Primary entry point — takes raw address + context, returns structured canonical form
normalize(raw_address: str, city: str, province: str = "Ontario",
          category: AddressCategory = AddressCategory.PROPERTY) → NormalizedAddress

# For already-split components (GeoWarehouse, brand scrapers with structured fields)
normalize_from_components(street: str, city: str, province: str,
                          postal_code: str = "", unit: str = "",
                          category: AddressCategory = ...) → NormalizedAddress

# For MPAC format ("90 PINEBUSH RD CAMBRIDGE ON N1R8J8" + municipality hint)
normalize_mpac(mpac_address: str, municipality: str,
               category: AddressCategory = AddressCategory.GEOWAREHOUSE) → NormalizedAddress
```

**Backward compatibility:** `normalize_address_for_dedup()`, `normalize_city_for_dedup()`, `make_dedup_key()`, `make_loose_dedup_key()` all still work as thin wrappers.

---

### Step 3: Build `data/municipalities.json` — City source of truth

The authoritative reference for city resolution. Three tiers:

**Tier 1 — Ontario Municipal Directory (canonical):**
Enhance `build_markets.py` to output structured municipality data with communities nested under their parent municipality. Already pulls from Wikipedia/Stats Canada. New: build the reverse lookup (community → municipality).

**Tier 2 — Variant corrections (manual JSON, not hardcoded Python):**
Spelling variants, abbreviations, typos: `"N. YORK" → "TORONTO"`, `"S.S. MARIE" → "SAULT STE. MARIE"`.
Stored in `data/municipalities.json` as a separate `variants` section. Editable without touching code.

**Tier 3 — Unknown city flagging:**
Cities not in Tier 1 or Tier 2 get flagged with count and sample addresses. CLI command `cleo normalize --review-cities` to resolve them. Prevents silent failures.

---

### Step 4: Build golden test set — `tests/test_normalize.py`

100+ test cases covering every edge case observed in the data. This becomes the regression safety net — every normalization change must pass this suite.

Categories:
- Saint ambiguity (`ST PAUL ST` vs `ST E`)
- City aliases (Thornhill→Vaughan, Scarborough→Toronto, Nepean→Ottawa)
- Suite/unit formats (Unit 2, Ste 200, #3, B03-70, APT 4B)
- MPAC format (no commas, postal glued on)
- Non-Ontario addresses (USA, international — flagged, not normalized)
- Garbage inputs (legal descriptions, PO boxes, intersections)
- Directional ambiguity (N/S/E/W as suffix vs part of street name)
- Period handling (Ave. → AVENUE, St. Thomas stays ST. THOMAS)

---

### Step 5: Build the Address Package — Pipeline Stage 3 (EXPAND)

Update `cleo/extract/address_expander.py` to output **packages** instead of flat lists.

**Before (current):**
```python
expand_compound_address("123 - 125 Main St", "Toronto", "Ontario")
→ ["123 Main St, Toronto, Ontario", "125 Main St, Toronto, Ontario"]
```

**After (packages):**
```python
expand_to_package(normalized_address: NormalizedAddress)
→ AddressPackage(
    primary="123 - 125 MAIN STREET, TORONTO, ONTARIO",
    aliases=[
        "123 MAIN STREET, TORONTO, ONTARIO",
        "125 MAIN STREET, TORONTO, ONTARIO",
        "123 - 125 MAIN STREET, TORONTO, ONTARIO",
    ],
    is_compound=True,
    category=AddressCategory.PROPERTY,
)
```

Non-compound addresses pass through as single-item packages (one alias = the primary).

The key rule: **one package = one property**. All aliases in a package resolve to the same P-ID.

---

### Step 6: Rewire geocoding — Pipeline Stage 4 (GEOCODE)

Update `cleo/geocode/collector.py` to:
- Accept `AddressPackage` objects (not raw strings)
- Submit all aliases for geocoding (compound + each expansion)
- Assign best coordinates to the package (not just individual strings)
- Carry `AddressCategory` through to the cache so we know what each geocoded address is

The geocode cache key is still the address string, but each package's aliases all point to the same property.

---

### Step 7: Rewire parcel harvester — Pipeline Stage 5 (PARCEL LOOKUP)

Flip the priority in `cleo/parcels/harvester.py`:

**Before (current):**
1. Try address LIKE query (primary) → fragile string matching
2. Fall back to lat/lng spatial query

**After:**
1. Try lat/lng spatial query (primary) → `query_at_point` + `_find_containing_parcel` → reliable, format-agnostic
2. Fall back to address LIKE query (for properties without coords)
3. If address fallback needed, try each alias in the package until one hits

The spatial query infrastructure already exists in the harvester. This is mostly reordering the logic in `harvest_parcels()` (lines 337-370).

---

### Step 8: Rewire property registry — Pipeline Stage 6 (COMBINE)

Update `cleo/properties/registry.py` to:
- Store `aliases` on every property record
- Use `NormalizedAddress.dedup_key` for primary dedup
- Merge packages: if "123 Main St" exists standalone AND as an alias of "123-125 Main St", merge into one property
- Store `category` on each address (enables map filtering)
- PIN-based merge (existing, unchanged)
- Loose directional merge (existing, unchanged)

---

### Step 9: Rewire remaining consumers

Replace local normalization with imports from `cleo/normalize.py`:

1. `brands/match.py` — use canonical city aliases + normalization for matching, check property aliases
2. `cleo/parties/normalize.py` — use canonical address normalization for clustering signals
3. `cleo/geowarehouse/address.py` — parse MPAC into raw components, then pass through `normalize_mpac()`
4. `cleo/web/app.py` — search checks aliases, map filters by category

---

### Step 10: Re-run pipelines and measure

Run the full pipeline end-to-end with the new normalization:
1. Re-extract (`cleo extract --sandbox`, `--diff`, `--promote`)
2. Re-geocode (all aliases in packages)
3. Re-run parcel lookups (spatial-first)
4. Re-build property registry (`cleo properties`) with aliases and categories
5. Re-run brand matching (against aliases)
6. Compare all metrics against Step 1 baseline

---

## Success Criteria

| Metric | Current (estimated) | Target |
|--------|-------------------|--------|
| Properties with geocodes | ~85% | >97% |
| Brands matched to properties | 65% (7,881 / 12,138) | >90% |
| Parcel lookup hit rate | Unknown (WIP) | >80% for municipalities with ArcGIS |
| Unknown cities in alias table | Unknown | <20 (flagged for review) |
| Duplicate property pairs | Unknown | <50 (down from likely hundreds) |
| Search finds compound sub-addresses | No | Yes |
| Corporate addresses separated from map | Partially | Fully |

---

## What This Unlocks

Once Phase 0 is solid:

- **Phase 1 (Parcels):** Municipal GIS queries work because addresses are clean → parcel boundaries populate → PIN-based dedup replaces address-only dedup
- **Phase 2 (Party Grouping):** Address signals in clustering are reliable → conservative grouping produces trustworthy portfolios
- **Phase 3 (App Reorg):** Parcel page has clean data → Owner page has trustworthy portfolio → the prospecting workflow works end-to-end in Cleo
- **Phase 4 (Integrations):** Clean contact addresses → HubSpot sync doesn't create duplicates → drip campaigns target the right people

---

## Files That Will Be Created/Modified

### New files
- `scripts/audit_addresses.py` — Step 1: baseline measurement
- `cleo/normalize.py` — Step 2: canonical normalization module (`NormalizedAddress`, `AddressCategory`, `AddressPackage`)
- `data/municipalities.json` — Step 3: authoritative city reference with community→municipality mapping
- `tests/test_normalize.py` — Step 4: golden test set (100+ edge cases)

### Modified files (by pipeline stage)
- `cleo/extract/address_expander.py` — Step 5: output `AddressPackage` with aliases
- `cleo/geocode/collector.py` — Step 6: accept packages, geocode all aliases, carry categories
- `cleo/parcels/harvester.py` — Step 7: spatial-first parcel lookup, address-string fallback
- `cleo/properties/registry.py` — Step 8: store aliases + categories, merge packages
- `brands/match.py` — Step 9: use canonical normalization, match against aliases
- `cleo/parties/normalize.py` — Step 9: import from canonical module
- `cleo/geowarehouse/address.py` — Step 9: parse MPAC → `normalize_mpac()`
- `cleo/web/app.py` — Step 9: search checks aliases, map filters by category
- `cleo/properties/normalize.py` — becomes thin backward-compatible wrapper
- `scripts/build_markets.py` — enhanced to output `municipalities.json`

### Preserved (backward compatible during migration)
- `normalize_address_for_dedup()` — still works, wraps new module
- `normalize_city_for_dedup()` — still works, wraps new module
- `make_dedup_key()` — still works, wraps new module
- `make_loose_dedup_key()` — still works, wraps new module
