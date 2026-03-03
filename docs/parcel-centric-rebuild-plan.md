I now have a thorough understanding of the entire codebase. Let me compile the comprehensive implementation plan.

---

# Parcel-Centric Architecture Rebuild -- Complete Implementation Plan

## Table of Contents
- Phase 0: Configuration and Data Structures
- Phase 1: Parcel Cache and Resolver
- Phase 2: Parcel Registry Builder
- Phase 3: CLI Commands
- Phase 4: Backend API Endpoints
- Phase 5: Frontend Stripping
- Phase 6: Frontend New Pages and Rewiring
- Phase 7: Integration Testing

---

## Pre-Implementation Notes

**Working directory:** `/Users/brandonolsen23/Library/Mobile Documents/com~apple~CloudDocs/01_Personal/01_Brandon/07_Development/2026-02-08 - Cleo Mini V3`

**Abbreviation:** This path is `$PROJ` in all references below.

**Existing data counts (verified):**
- 32 branded parcel cities, 15,207 parcels, 33,844 brand POIs
- 15,814 RT parsed records (active v015): 72.8% have ARN, 66.3% have PINs, 93.9% have ARN or PIN
- 449 GW parsed records (v001): 439 have both ARN and PIN
- 18,663 properties in legacy properties.json
- 544 municipalities in markets.json
- Geocode cache: ~50K addresses with lat/lng

**Key ARN/PIN conversion rules (verified from existing code):**
- RT ARN is 15-digit. Pad with "00000" to get 20-digit provincial format.
- RT PIN format in HTML: "XXXXX-XXXX". Strip dashes to get 9-digit format = GW format.
- Branded parcel files are keyed by 20-digit ARN.
- Provincial MapServer field: `ASSESSMENT_ROLL_NUMBER` (20-digit).

---

## PHASE 0: Configuration and Data Structures

### Step 0.1 -- Add new config constants

**File:** `$PROJ/cleo/config.py`

**Action:** Add these constants after the existing `BRANDED_PARCELS_DIR` and `PROPERTY_PARCEL_INDEX_PATH` lines (around line 85):

```python
# Parcel-centric registry
PARCEL_CACHE_PATH = PARCELS_DIR / "parcel_cache.json"
PARCEL_REGISTRY_PATH = DATA_DIR / "parcel_registry.json"
```

Also add to the `mkdir` block near line 116:

```python
BRANDED_PARCELS_DIR.mkdir(parents=True, exist_ok=True)
```

(BRANDED_PARCELS_DIR is already defined but not mkdir'd. It may already exist on disk but adding the mkdir is defensive.)

**No other config changes needed.** Existing constants for `PARCELS_DIR`, `BRANDED_PARCELS_DIR`, `AGMAPS_TOKEN`, `AGMAPS_PARCEL_URL`, `PARSED_DIR`, `GW_PARSED_DIR`, `PROPERTIES_PATH`, `MARKETS_PATH`, `GEOCODE_CACHE_PATH` are all already defined and correct.

**Test:** `python3 -c "from cleo.config import PARCEL_CACHE_PATH, PARCEL_REGISTRY_PATH; print(PARCEL_CACHE_PATH, PARCEL_REGISTRY_PATH)"`

**Expected output:**
```
data/parcels/parcel_cache.json data/parcel_registry.json
```

---

### Step 0.2 -- Define the Parcel Cache schema

**File:** `$PROJ/data/parcels/parcel_cache.json` (created by code, not manually)

**Schema:**
```json
{
  "meta": {
    "total": 15207,
    "seeded_from_branded": 15207,
    "resolved_from_api": 0,
    "last_updated": "2026-02-27T12:00:00Z"
  },
  "parcels": {
    "39360100900720000000": {
      "arn": "39360100900720000000",
      "pin": null,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[...], ...]]
      },
      "centroid": [42.98, -81.26],
      "attributes": {
        "OGF_ID": 1924444170,
        "ASSESSMENT_ROLL_NUMBER": "39360100900720000000",
        "OBJECTID": 244794977
      },
      "source": "branded_harvest",
      "cached_at": "2026-02-27T12:00:00Z"
    }
  }
}
```

---

### Step 0.3 -- Define the Parcel Registry schema

**File:** `$PROJ/data/parcel_registry.json` (created by code, not manually)

**Schema:**
```json
{
  "meta": {
    "total": 28000,
    "generated_at": "2026-02-27T12:00:00Z",
    "sources": {
      "branded": 15207,
      "rt": 12000,
      "gw": 400
    },
    "stats": {
      "with_transactions": 12000,
      "with_brands": 15207,
      "with_assessment": 400,
      "with_geometry": 27500,
      "geocode_resolved": 500
    }
  },
  "parcels": {
    "39360100900720000000": {
      "arn": "39360100900720000000",
      "pid": "P00028",
      "pin": "082620036",
      "geometry": { "type": "Polygon", "coordinates": [...] },
      "centroid": [42.98, -81.26],
      "city": "London",
      "addresses": ["717 RICHMOND ST", "215 PICCADILLY ST"],
      "area_sqm": 1200.5,
      "zoning": null,
      "population": 422324,
      "brands": [
        {"name": "Starbucks", "type": "cafe", "lat": 42.98, "lng": -81.26}
      ],
      "transactions": [
        {
          "rt_id": "RT100507",
          "date": "2014-05-26",
          "price": 3160000,
          "buyer": "717 Richmond Holdings ULC",
          "seller": "717 Richmond 2011 LP"
        }
      ],
      "assessment": {
        "value": 2147000,
        "property_code": "435",
        "property_description": "Freestanding retail building centre",
        "legal_desc": "PLAN 33R-10178...",
        "zoning": "C-1",
        "frontage": "237.84 ft",
        "owner": "POLNI HOLDINGS INC.",
        "owner_address": "..."
      },
      "discovered_via": "branded_harvest",
      "sources": ["branded", "rt", "gw"]
    }
  },
  "indexes": {
    "pin_to_arn": {
      "082620036": "39360100900720000000"
    },
    "rt_to_arn": {
      "RT100507": "39360100900720000000"
    },
    "pid_to_arn": {
      "P00028": "39360100900720000000"
    }
  }
}
```

---

## PHASE 1: Parcel Cache and Resolver

### Step 1.1 -- Create the Parcel Cache module

**File to create:** `$PROJ/cleo/parcels/cache.py`

**Dependencies:** Only `cleo.config` (already exists)

**Complete module structure:**

```python
"""Parcel geometry cache — permanent on-disk store of discovered parcel boundaries.

Keyed by 20-digit ARN. Seeded from branded_parcels/*.json, grows as
RT/GW records are resolved via the provincial MapServer API.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cleo.config import PARCEL_CACHE_PATH

logger = logging.getLogger(__name__)


class ParcelCache:
    """On-disk cache of parcel geometries and attributes, keyed by 20-digit ARN."""

    def __init__(self, path: Path | None = None):
        self._path = path or PARCEL_CACHE_PATH
        self._data: Optional[dict] = None

    def _load(self) -> dict:
        if self._data is not None:
            return self._data
        if self._path.exists():
            self._data = json.loads(self._path.read_text(encoding="utf-8"))
        else:
            self._data = {
                "meta": {
                    "total": 0,
                    "seeded_from_branded": 0,
                    "resolved_from_api": 0,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                },
                "parcels": {},
            }
        return self._data

    @property
    def parcels(self) -> dict[str, dict]:
        return self._load()["parcels"]

    @property
    def total(self) -> int:
        return len(self.parcels)

    def get(self, arn_20: str) -> Optional[dict]:
        """Look up a cached parcel by 20-digit ARN. Returns parcel dict or None."""
        return self.parcels.get(arn_20)

    def has(self, arn_20: str) -> bool:
        """Check if a parcel is in the cache."""
        return arn_20 in self.parcels

    def put(
        self,
        arn_20: str,
        pin: str | None,
        geometry: dict | None,
        centroid: list[float] | None,
        attributes: dict | None,
        source: str = "api",
    ) -> None:
        """Add or update a parcel in the cache."""
        data = self._load()
        data["parcels"][arn_20] = {
            "arn": arn_20,
            "pin": pin,
            "geometry": geometry,
            "centroid": centroid,
            "attributes": attributes or {},
            "source": source,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        data["meta"]["total"] = len(data["parcels"])

    def put_batch(self, entries: list[dict], source: str = "branded_harvest") -> int:
        """Add multiple parcels. Each entry must have at least 'arn'.
        Returns count of newly added entries (not updates)."""
        data = self._load()
        added = 0
        for entry in entries:
            arn = entry.get("arn", "")
            if not arn:
                continue
            is_new = arn not in data["parcels"]
            data["parcels"][arn] = {
                "arn": arn,
                "pin": entry.get("pin"),
                "geometry": entry.get("geometry"),
                "centroid": entry.get("centroid"),
                "attributes": entry.get("attributes", {}),
                "source": source,
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
            if is_new:
                added += 1
        data["meta"]["total"] = len(data["parcels"])
        return added

    def seed_from_branded_parcels(self, branded_dir: Path) -> int:
        """Seed cache from all branded_parcels/*.json files. Returns count added."""
        if not branded_dir.exists():
            return 0
        entries = []
        for f in sorted(branded_dir.iterdir()):
            if not f.name.endswith(".json"):
                continue
            try:
                file_data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for arn, parcel in file_data.get("parcels", {}).items():
                geom = parcel.get("geometry")
                centroid = _polygon_centroid_from_geojson(geom) if geom else None
                entries.append({
                    "arn": arn,
                    "pin": parcel.get("pin"),
                    "geometry": geom,
                    "centroid": centroid,
                    "attributes": parcel.get("attributes", {}),
                })
        added = self.put_batch(entries, source="branded_harvest")
        self._load()["meta"]["seeded_from_branded"] = added
        logger.info("Seeded parcel cache with %d parcels from branded harvests", added)
        return added

    def save(self) -> None:
        """Write cache to disk atomically."""
        data = self._load()
        data["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            # No indent — this file can be huge (15K+ parcels with geometry)
        tmp.rename(self._path)
        logger.info("Saved parcel cache: %d entries to %s", data["meta"]["total"], self._path)

    def stats(self) -> dict:
        """Return summary statistics."""
        data = self._load()
        with_geometry = sum(1 for p in data["parcels"].values() if p.get("geometry"))
        with_pin = sum(1 for p in data["parcels"].values() if p.get("pin"))
        by_source: dict[str, int] = {}
        for p in data["parcels"].values():
            src = p.get("source", "unknown")
            by_source[src] = by_source.get(src, 0) + 1
        return {
            "total": data["meta"]["total"],
            "with_geometry": with_geometry,
            "with_pin": with_pin,
            "by_source": by_source,
            "last_updated": data["meta"].get("last_updated", ""),
        }


def _polygon_centroid_from_geojson(geom: dict) -> list[float] | None:
    """Compute [lat, lng] centroid from GeoJSON polygon."""
    if not geom:
        return None
    gtype = geom.get("type", "")
    coords = geom.get("coordinates", [])
    if gtype == "Polygon" and coords:
        ring = coords[0]
    elif gtype == "MultiPolygon" and coords:
        ring = coords[0][0]
    else:
        return None
    if not ring:
        return None
    n = len(ring)
    avg_lng = sum(c[0] for c in ring) / n
    avg_lat = sum(c[1] for c in ring) / n
    return [round(avg_lat, 7), round(avg_lng, 7)]
```

**Test command:**
```bash
.venv/bin/python -c "
from cleo.parcels.cache import ParcelCache
from cleo.config import BRANDED_PARCELS_DIR
cache = ParcelCache()
added = cache.seed_from_branded_parcels(BRANDED_PARCELS_DIR)
print(f'Seeded {added} parcels')
cache.save()
print(cache.stats())
"
```

**Expected output:**
```
Seeded 15207 parcels
{'total': 15207, 'with_geometry': ~15207, 'with_pin': ~0, 'by_source': {'branded_harvest': 15207}, ...}
```

---

### Step 1.2 -- Create the Universal Parcel Resolver

**File to create:** `$PROJ/cleo/parcels/resolver.py`

**Dependencies:** `cleo.parcels.cache` (step 1.1), `cleo.parcels.provincial` (existing)

```python
"""Universal parcel resolver — resolves any identifier to a cached parcel.

Resolution priority:
  1. ARN lookup in cache (instant, O(1))
  2. ARN query against provincial API (if miss)
  3. PIN lookup via pin_to_arn index in cache
  4. PIN query against provincial API (if miss)
  5. Spatial point query against provincial API (if coords provided)

All resolved parcels are permanently cached.
"""

from __future__ import annotations

import logging
from typing import Optional

from cleo.parcels.cache import ParcelCache, _polygon_centroid_from_geojson

logger = logging.getLogger(__name__)


def pad_arn_15_to_20(arn_15: str) -> str:
    """Pad a 15-digit RT/GW ARN to 20-digit provincial format."""
    arn_clean = arn_15.strip()
    if len(arn_clean) == 20:
        return arn_clean
    if len(arn_clean) == 15:
        return arn_clean + "00000"
    # Try to pad anyway if it's a reasonable length
    if 10 <= len(arn_clean) < 20:
        return arn_clean + "0" * (20 - len(arn_clean))
    return arn_clean


def normalize_pin(pin: str) -> str:
    """Strip dashes from PIN, return bare digits."""
    return pin.replace("-", "").strip()


class ParcelResolver:
    """Resolve any identifier (ARN, PIN, coords) to a cached parcel record.

    Uses the ParcelCache for instant lookups. On cache miss, optionally
    queries the provincial MapServer API and caches the result permanently.

    Set skip_api=True to disable API queries (offline/cache-only mode).
    """

    def __init__(
        self,
        cache: ParcelCache | None = None,
        skip_api: bool = False,
    ):
        self._cache = cache or ParcelCache()
        self._skip_api = skip_api
        self._client = None  # lazy init
        self._pin_to_arn: dict[str, str] | None = None  # lazy built

        # Stats
        self.stats_cache_hit = 0
        self.stats_api_hit = 0
        self.stats_api_miss = 0
        self.stats_api_error = 0

    def _get_client(self):
        """Lazy-init the provincial client."""
        if self._client is None:
            from cleo.parcels.provincial import ProvincialParcelClient, TokenExpiredError
            try:
                self._client = ProvincialParcelClient()
            except ValueError:
                # No token configured
                self._client = False  # Sentinel: no client available
        return self._client if self._client is not False else None

    def _build_pin_index(self) -> dict[str, str]:
        """Build a PIN -> ARN reverse index from the cache."""
        if self._pin_to_arn is not None:
            return self._pin_to_arn
        self._pin_to_arn = {}
        for arn, parcel in self._cache.parcels.items():
            pin = parcel.get("pin")
            if pin:
                self._pin_to_arn[normalize_pin(pin)] = arn
        return self._pin_to_arn

    def _cache_feature(self, feature: dict, source: str = "api") -> Optional[str]:
        """Extract parcel data from a provincial API feature and cache it.
        Returns the 20-digit ARN or None."""
        attrs = feature.get("attributes", {})
        arn = str(attrs.get("ASSESSMENT_ROLL_NUMBER", ""))
        if not arn:
            return None

        # Convert ArcGIS rings to GeoJSON
        geometry = _arcgis_to_geojson(feature.get("geometry", {}))
        centroid = _polygon_centroid_from_geojson(geometry) if geometry else None
        pin = str(attrs.get("PIN", "")) if attrs.get("PIN") else None

        self._cache.put(
            arn_20=arn,
            pin=pin,
            geometry=geometry,
            centroid=centroid,
            attributes={
                k: v for k, v in attrs.items()
                if k not in ("ASSESSMENT_ROLL_NUMBER", "PIN", "Shape", "Shape.STArea()", "Shape.STLength()")
            },
            source=source,
        )

        # Update PIN index if we have one
        if pin and self._pin_to_arn is not None:
            self._pin_to_arn[normalize_pin(pin)] = arn

        return arn

    def resolve_by_arn(self, arn: str) -> Optional[dict]:
        """Resolve a parcel by ARN (15 or 20 digit). Returns cached parcel dict or None."""
        arn_20 = pad_arn_15_to_20(arn)

        # Check cache first
        cached = self._cache.get(arn_20)
        if cached:
            self.stats_cache_hit += 1
            return cached

        if self._skip_api:
            return None

        # Query API
        client = self._get_client()
        if not client:
            return None

        try:
            features = client.query_by_arn(arn_20)
        except Exception as exc:
            logger.warning("API error resolving ARN %s: %s", arn_20, exc)
            self.stats_api_error += 1
            return None

        if features:
            cached_arn = self._cache_feature(features[0], source="api_arn")
            if cached_arn:
                self.stats_api_hit += 1
                return self._cache.get(cached_arn)

        self.stats_api_miss += 1
        return None

    def resolve_by_pin(self, pin: str) -> Optional[dict]:
        """Resolve a parcel by PIN. Checks cache index first, then API."""
        pin_clean = normalize_pin(pin)

        # Check cache PIN index
        pin_index = self._build_pin_index()
        if pin_clean in pin_index:
            arn = pin_index[pin_clean]
            cached = self._cache.get(arn)
            if cached:
                self.stats_cache_hit += 1
                return cached

        if self._skip_api:
            return None

        # Query API by PIN
        client = self._get_client()
        if not client:
            return None

        try:
            features = client.query_by_pin(pin_clean)
        except Exception as exc:
            logger.warning("API error resolving PIN %s: %s", pin_clean, exc)
            self.stats_api_error += 1
            return None

        if features:
            cached_arn = self._cache_feature(features[0], source="api_pin")
            if cached_arn:
                self.stats_api_hit += 1
                return self._cache.get(cached_arn)

        self.stats_api_miss += 1
        return None

    def resolve_by_coords(self, lat: float, lng: float) -> Optional[dict]:
        """Resolve a parcel by spatial point query. Always hits API."""
        if self._skip_api:
            return None

        client = self._get_client()
        if not client:
            return None

        try:
            features = client.query_at_point(lat, lng)
        except Exception as exc:
            logger.warning("API error resolving coords (%s, %s): %s", lat, lng, exc)
            self.stats_api_error += 1
            return None

        if features:
            # Pick the containing parcel
            best = client.pick_containing_parcel(features, lat, lng)
            if best:
                cached_arn = self._cache_feature(best, source="api_spatial")
                if cached_arn:
                    self.stats_api_hit += 1
                    return self._cache.get(cached_arn)

        self.stats_api_miss += 1
        return None

    def resolve(
        self,
        arn: str | None = None,
        pin: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
    ) -> Optional[dict]:
        """Resolve using the best available identifier. Priority: ARN > PIN > coords."""
        if arn:
            result = self.resolve_by_arn(arn)
            if result:
                return result

        if pin:
            result = self.resolve_by_pin(pin)
            if result:
                return result

        if lat is not None and lng is not None:
            result = self.resolve_by_coords(lat, lng)
            if result:
                return result

        return None

    def save_cache(self) -> None:
        """Persist the cache to disk."""
        self._cache.save()

    def get_stats(self) -> dict:
        """Return resolution statistics."""
        return {
            "cache_total": self._cache.total,
            "cache_hits": self.stats_cache_hit,
            "api_hits": self.stats_api_hit,
            "api_misses": self.stats_api_miss,
            "api_errors": self.stats_api_error,
        }


def _arcgis_to_geojson(arcgis_geom: dict) -> Optional[dict]:
    """Convert ArcGIS geometry (rings format) to GeoJSON Polygon."""
    rings = arcgis_geom.get("rings")
    if not rings:
        return None
    # ArcGIS rings: [[[x,y], [x,y], ...], ...]
    # GeoJSON coordinates: same format
    return {
        "type": "Polygon",
        "coordinates": rings,
    }
```

**Test command:**
```bash
.venv/bin/python -c "
from cleo.parcels.resolver import ParcelResolver, pad_arn_15_to_20
resolver = ParcelResolver(skip_api=True)
# Seed cache first
from cleo.parcels.cache import ParcelCache
from cleo.config import BRANDED_PARCELS_DIR
cache = ParcelCache()
cache.seed_from_branded_parcels(BRANDED_PARCELS_DIR)
cache.save()
# Now test resolving
resolver = ParcelResolver(cache=cache, skip_api=True)
arn_20 = pad_arn_15_to_20('393601009007200')
result = resolver.resolve_by_arn(arn_20)
print('Found:' if result else 'Not found (expected if this ARN is not in branded harvests)')
print(resolver.get_stats())
"
```

---

## PHASE 2: Parcel Registry Builder

### Step 2.1 -- Create the Registry Builder module

**File to create:** `$PROJ/cleo/parcels/registry_builder.py`

**Dependencies:** `cleo.parcels.cache` (step 1.1), `cleo.parcels.resolver` (step 1.2), `cleo.config` (existing)

This is the core module that builds `data/parcel_registry.json` from all sources.

```python
"""Parcel registry builder — creates the master parcel-centric registry.

Builds data/parcel_registry.json by:
  Pass 1: Seed from branded_parcels/*.json (instant, no API)
  Pass 2: Resolve RT records to parcels via ARN/PIN/coords
  Pass 3: Resolve GW records to parcels via ARN/PIN
  Pass 4: Enrich with population from markets.json
  Pass 5: Assign stable P-IDs

Output: A single JSON file keyed by 20-digit ARN with all enrichment merged.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cleo.config import (
    BRANDED_PARCELS_DIR,
    GEOCODE_CACHE_PATH,
    GW_PARSED_DIR,
    MARKETS_PATH,
    PARCEL_REGISTRY_PATH,
    PARSED_DIR,
    PROPERTIES_PATH,
)
from cleo.parcels.cache import ParcelCache
from cleo.parcels.resolver import ParcelResolver, normalize_pin, pad_arn_15_to_20

logger = logging.getLogger(__name__)


def _parse_price(price_str: str) -> Optional[int]:
    """Parse '$3,160,000' to 3160000."""
    if not price_str:
        return None
    try:
        return int(float(price_str.replace("$", "").replace(",", "").strip()))
    except (ValueError, TypeError):
        return None


def _load_markets() -> dict[str, int]:
    """Load markets.json and return uppercase city -> population."""
    if not MARKETS_PATH.exists():
        return {}
    data = json.loads(MARKETS_PATH.read_text(encoding="utf-8"))
    return {k.upper(): v["population"] for k, v in data.get("markets", {}).items()}


def _load_geocode_cache() -> dict[str, dict]:
    """Load geocode_cache.json for lat/lng lookups by address string."""
    if not GEOCODE_CACHE_PATH.exists():
        return {}
    data = json.loads(GEOCODE_CACHE_PATH.read_text(encoding="utf-8"))
    # geocode_cache.json structure: {"address": {"lat": ..., "lng": ..., "status": "ok"}}
    return {
        addr: coords for addr, coords in data.items()
        if isinstance(coords, dict) and coords.get("lat") and coords.get("lng")
    }


def _load_legacy_pid_map() -> dict[str, dict]:
    """Load existing properties.json to preserve P-ID assignments.
    Returns {dedup_key: {"pid": "P00001", "rt_ids": [...], "lat": ..., "lng": ...}}."""
    if not PROPERTIES_PATH.exists():
        return {}
    data = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
    props = data.get("properties", {})
    result = {}
    for pid, prop in props.items():
        addr = (prop.get("address", "") or "").upper().strip()
        city = (prop.get("city", "") or "").upper().strip()
        key = f"{addr}|{city}"
        result[key] = {
            "pid": pid,
            "rt_ids": prop.get("rt_ids", []),
            "lat": prop.get("lat"),
            "lng": prop.get("lng"),
        }
    return result


def _next_pid(used_pids: set[str]) -> str:
    """Generate next P-prefixed ID."""
    max_num = 0
    for pid in used_pids:
        if pid.startswith("P") and pid[1:].isdigit():
            max_num = max(max_num, int(pid[1:]))
    return f"P{max_num + 1:05d}"


def build_registry(
    skip_api: bool = False,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Build the master parcel registry from all sources.

    Args:
        skip_api: If True, skip provincial API queries (cache-only mode).
        limit: Max RT records to process (for testing).
        dry_run: If True, don't save output files.

    Returns:
        Summary dict with stats.
    """
    start = time.time()

    # Initialize cache and resolver
    cache = ParcelCache()
    resolver = ParcelResolver(cache=cache, skip_api=skip_api)

    # Registry: arn_20 -> parcel dict
    registry: dict[str, dict] = {}

    # Reverse indexes
    pin_to_arn: dict[str, str] = {}
    rt_to_arn: dict[str, str] = {}
    pid_to_arn: dict[str, str] = {}

    # ----- Pass 1: Seed from branded parcels -----
    logger.info("Pass 1: Seeding from branded parcels...")
    branded_count = 0

    if BRANDED_PARCELS_DIR.exists():
        for f in sorted(BRANDED_PARCELS_DIR.iterdir()):
            if not f.name.endswith(".json"):
                continue
            try:
                file_data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            city_name = file_data.get("city", f.stem)

            for arn, parcel in file_data.get("parcels", {}).items():
                if arn not in registry:
                    geom = parcel.get("geometry")
                    centroid = None
                    if geom:
                        from cleo.parcels.cache import _polygon_centroid_from_geojson
                        centroid = _polygon_centroid_from_geojson(geom)

                    registry[arn] = {
                        "arn": arn,
                        "pid": None,
                        "pin": parcel.get("pin"),
                        "geometry": geom,
                        "centroid": centroid,
                        "city": city_name.title(),
                        "addresses": [],
                        "area_sqm": None,
                        "zoning": parcel.get("zoning"),
                        "population": None,
                        "brands": [],
                        "transactions": [],
                        "assessment": None,
                        "discovered_via": "branded_harvest",
                        "sources": ["branded"],
                    }
                    branded_count += 1

                # Merge brands
                existing_brand_names = {
                    b["name"] for b in registry[arn]["brands"]
                }
                for brand in parcel.get("brands", []):
                    if isinstance(brand, dict) and brand.get("name") not in existing_brand_names:
                        registry[arn]["brands"].append(brand)
                        existing_brand_names.add(brand["name"])

                # Merge addresses
                for addr in parcel.get("addresses", []):
                    if addr and addr not in registry[arn]["addresses"]:
                        registry[arn]["addresses"].append(addr)

                # Track PIN
                pin = parcel.get("pin")
                if pin:
                    pin_to_arn[normalize_pin(str(pin))] = arn

    # Also seed cache from branded parcels
    cache.seed_from_branded_parcels(BRANDED_PARCELS_DIR)

    logger.info("Pass 1 complete: %d branded parcels", branded_count)

    # ----- Pass 2: Resolve RT records -----
    logger.info("Pass 2: Resolving RT records...")
    rt_resolved = 0
    rt_unresolved = 0
    rt_total = 0

    parsed_active = PARSED_DIR / "active"
    if parsed_active.exists():
        rt_files = sorted(parsed_active.glob("*.json"))
        if limit:
            rt_files = rt_files[:limit]

        for f in rt_files:
            if f.stem == "_meta":
                continue
            rt_total += 1

            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            rt_id = data.get("rt_id", f.stem)
            txn = data.get("transaction", {})
            addr_obj = txn.get("address", {})
            site = data.get("site", {})

            # Get identifiers
            arn_15 = txn.get("arn", "")
            pins_raw = txn.get("pins", [])
            pins = [normalize_pin(p) for p in pins_raw if p]

            # Also check site.pins (string, comma-separated)
            site_pins_str = site.get("pins", "")
            if site_pins_str:
                for sp in str(site_pins_str).split(","):
                    np = normalize_pin(sp)
                    if np and len(np) >= 9 and np not in pins:
                        pins.append(np)

            # Try to get coords from geocode cache or properties
            lat = None
            lng = None
            prop_address = addr_obj.get("address", "")
            prop_city = addr_obj.get("city", "")

            # Resolve parcel
            parcel = None

            # Method 1: ARN
            if arn_15 and len(arn_15) >= 15:
                parcel = resolver.resolve_by_arn(arn_15)

            # Method 2: PIN
            if not parcel:
                for pin in pins:
                    if len(pin) >= 9:
                        parcel = resolver.resolve_by_pin(pin)
                        if parcel:
                            break

            # Method 3: Spatial (only if we have coords and API is enabled)
            # We'll get coords from the legacy property registry
            if not parcel and not skip_api:
                # Try to find coords from geocode cache
                addr_str = f"{prop_address}, {prop_city}, Ontario" if prop_address and prop_city else ""
                if addr_str:
                    geocode = _load_geocode_cache()  # TODO: cache this outside loop
                    gc = geocode.get(addr_str)
                    if gc:
                        lat = gc.get("lat")
                        lng = gc.get("lng")
                        if lat and lng:
                            parcel = resolver.resolve_by_coords(float(lat), float(lng))

            if parcel:
                arn_20 = parcel["arn"]
                rt_resolved += 1
                rt_to_arn[rt_id] = arn_20

                # Ensure registry entry exists
                if arn_20 not in registry:
                    registry[arn_20] = {
                        "arn": arn_20,
                        "pid": None,
                        "pin": parcel.get("pin"),
                        "geometry": parcel.get("geometry"),
                        "centroid": parcel.get("centroid"),
                        "city": prop_city or None,
                        "addresses": [],
                        "area_sqm": None,
                        "zoning": None,
                        "population": None,
                        "brands": [],
                        "transactions": [],
                        "assessment": None,
                        "discovered_via": "rt_resolve",
                        "sources": [],
                    }

                rec = registry[arn_20]
                if "rt" not in rec["sources"]:
                    rec["sources"].append("rt")

                # Merge address
                if prop_address and prop_address not in rec["addresses"]:
                    rec["addresses"].append(prop_address)
                for alt in addr_obj.get("alternate_addresses", []):
                    if alt and alt not in rec["addresses"]:
                        rec["addresses"].append(alt)

                # Merge city (prefer non-empty)
                if prop_city and not rec.get("city"):
                    rec["city"] = prop_city

                # Merge PIN
                for pin in pins:
                    if pin and not rec.get("pin"):
                        rec["pin"] = pin
                        pin_to_arn[pin] = arn_20

                # Add transaction summary
                price = _parse_price(txn.get("sale_price", ""))
                rec["transactions"].append({
                    "rt_id": rt_id,
                    "date": txn.get("sale_date_iso", ""),
                    "price": price,
                    "buyer": data.get("transferee", {}).get("name", ""),
                    "seller": data.get("transferor", {}).get("name", ""),
                })

                # Site area and zoning
                if site.get("site_area") and not rec.get("area_sqm"):
                    try:
                        acres = float(site["site_area"])
                        rec["area_sqm"] = round(acres * 4046.86, 1)
                    except (ValueError, TypeError):
                        pass
                if site.get("zoning") and not rec.get("zoning"):
                    rec["zoning"] = site["zoning"]
            else:
                rt_unresolved += 1

    logger.info("Pass 2 complete: %d/%d RT records resolved", rt_resolved, rt_total)

    # ----- Pass 3: Resolve GW records -----
    logger.info("Pass 3: Resolving GW records...")
    gw_resolved = 0
    gw_total = 0

    gw_dir = GW_PARSED_DIR / "v001"
    if gw_dir.exists():
        for f in sorted(gw_dir.glob("*.json")):
            if f.stem == "_meta":
                continue
            gw_total += 1

            try:
                gw_data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            gw_id = gw_data.get("gw_id", f.stem)
            site_struct = gw_data.get("site_structure", {})
            registry_info = gw_data.get("registry", {})
            summary = gw_data.get("summary", {})

            arn = site_struct.get("arn", "")
            pin = registry_info.get("pin", "") or gw_data.get("pin", "")

            parcel = None
            if arn and len(arn) >= 15:
                parcel = resolver.resolve_by_arn(arn)
            if not parcel and pin:
                parcel = resolver.resolve_by_pin(pin)

            if parcel:
                arn_20 = parcel["arn"]
                gw_resolved += 1

                if arn_20 not in registry:
                    registry[arn_20] = {
                        "arn": arn_20,
                        "pid": None,
                        "pin": parcel.get("pin"),
                        "geometry": parcel.get("geometry"),
                        "centroid": parcel.get("centroid"),
                        "city": None,
                        "addresses": [],
                        "area_sqm": None,
                        "zoning": None,
                        "population": None,
                        "brands": [],
                        "transactions": [],
                        "assessment": None,
                        "discovered_via": "gw_resolve",
                        "sources": [],
                    }

                rec = registry[arn_20]
                if "gw" not in rec["sources"]:
                    rec["sources"].append("gw")

                # Merge PIN
                if pin and not rec.get("pin"):
                    norm_pin = normalize_pin(pin)
                    rec["pin"] = norm_pin
                    pin_to_arn[norm_pin] = arn_20

                # Merge assessment data
                assessed_value = site_struct.get("current_assessed_value", "")
                if assessed_value:
                    rec["assessment"] = {
                        "value": _parse_price(assessed_value),
                        "property_code": site_struct.get("property_code", ""),
                        "property_description": site_struct.get("property_description", ""),
                        "legal_desc": site_struct.get("assessment_legal_description", ""),
                        "zoning": site_struct.get("zoning", ""),
                        "frontage": site_struct.get("frontage", ""),
                        "owner": summary.get("owner_names", ""),
                        "owner_address": site_struct.get("owner_mailing_address", ""),
                    }

                # Merge zoning
                if site_struct.get("zoning") and not rec.get("zoning"):
                    rec["zoning"] = site_struct["zoning"]

                # Merge address
                gw_address = summary.get("address", "")
                if gw_address:
                    # GW address format: "121 CONCESSION ST E, TILLSONBURG, N4G4W4"
                    addr_parts = gw_address.split(",")
                    street = addr_parts[0].strip() if addr_parts else ""
                    city_part = addr_parts[1].strip() if len(addr_parts) > 1 else ""
                    if street and street not in rec["addresses"]:
                        rec["addresses"].append(street)
                    if city_part and not rec.get("city"):
                        rec["city"] = city_part.title()

                # Merge sales history into transactions (only if not already from RT)
                existing_rt_ids = {t["rt_id"] for t in rec["transactions"]}
                for sale in gw_data.get("sales_history", []):
                    # Don't create duplicate entries — GW sales overlap with RT
                    # Only add if we have no RT transactions at all for this parcel
                    if not existing_rt_ids:
                        price = _parse_price(sale.get("sale_amount", ""))
                        rec["transactions"].append({
                            "rt_id": f"GW:{gw_id}",
                            "date": sale.get("sale_date", ""),
                            "price": price,
                            "buyer": sale.get("party_to", "").rstrip(";").strip(),
                            "seller": "",
                        })

    logger.info("Pass 3 complete: %d/%d GW records resolved", gw_resolved, gw_total)

    # ----- Pass 4: Population enrichment -----
    logger.info("Pass 4: Enriching with population data...")
    markets = _load_markets()
    pop_enriched = 0

    for arn, rec in registry.items():
        city = rec.get("city")
        if city:
            pop = markets.get(city.upper().strip())
            if pop:
                rec["population"] = pop
                pop_enriched += 1

    logger.info("Pass 4 complete: %d parcels with population data", pop_enriched)

    # ----- Pass 5: Assign stable P-IDs -----
    logger.info("Pass 5: Assigning P-IDs...")
    legacy = _load_legacy_pid_map()
    used_pids: set[str] = set()

    # First pass: assign P-IDs from legacy property registry
    for arn, rec in registry.items():
        # Match by address+city
        for addr in rec.get("addresses", []):
            city = (rec.get("city") or "").upper().strip()
            key = f"{addr.upper().strip()}|{city}"
            if key in legacy:
                pid = legacy[key]["pid"]
                rec["pid"] = pid
                pid_to_arn[pid] = arn
                used_pids.add(pid)
                break

    # Second pass: assign new P-IDs to unassigned parcels
    for arn, rec in registry.items():
        if rec.get("pid") is None:
            pid = _next_pid(used_pids)
            rec["pid"] = pid
            pid_to_arn[pid] = arn
            used_pids.add(pid)

    # Sort transactions by date (descending) within each parcel
    for rec in registry.values():
        rec["transactions"].sort(
            key=lambda t: t.get("date", "") or "0000",
            reverse=True,
        )

    # ----- Build output -----
    elapsed = round(time.time() - start, 1)

    output = {
        "meta": {
            "total": len(registry),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_s": elapsed,
            "sources": {
                "branded": sum(1 for r in registry.values() if "branded" in r.get("sources", [])),
                "rt": sum(1 for r in registry.values() if "rt" in r.get("sources", [])),
                "gw": sum(1 for r in registry.values() if "gw" in r.get("sources", [])),
            },
            "stats": {
                "with_transactions": sum(1 for r in registry.values() if r.get("transactions")),
                "with_brands": sum(1 for r in registry.values() if r.get("brands")),
                "with_assessment": sum(1 for r in registry.values() if r.get("assessment")),
                "with_geometry": sum(1 for r in registry.values() if r.get("geometry")),
                "with_population": pop_enriched,
                "rt_resolved": rt_resolved,
                "rt_unresolved": rt_unresolved,
                "gw_resolved": gw_resolved,
            },
        },
        "parcels": registry,
        "indexes": {
            "pin_to_arn": pin_to_arn,
            "rt_to_arn": rt_to_arn,
            "pid_to_arn": pid_to_arn,
        },
    }

    if not dry_run:
        # Save cache
        cache.save()
        # Save registry
        PARCEL_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = PARCEL_REGISTRY_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fp:
            json.dump(output, fp, ensure_ascii=False)
        tmp.rename(PARCEL_REGISTRY_PATH)
        logger.info("Saved parcel registry: %d parcels to %s", len(registry), PARCEL_REGISTRY_PATH)

    return {
        "total_parcels": len(registry),
        "branded": branded_count,
        "rt_resolved": rt_resolved,
        "rt_unresolved": rt_unresolved,
        "gw_resolved": gw_resolved,
        "with_population": pop_enriched,
        "elapsed_s": elapsed,
        "resolver_stats": resolver.get_stats(),
        "dry_run": dry_run,
    }
```

**Important note about geocode_cache loading:** In the actual implementation, the `_load_geocode_cache()` call inside the RT loop must be cached outside the loop (loaded once). The code above has a TODO comment for this. In the real implementation, load it before the loop:

```python
geocode = _load_geocode_cache()  # Load once before loop
```

**Test command (cache-only, no API):**
```bash
.venv/bin/python -c "
from cleo.parcels.registry_builder import build_registry
result = build_registry(skip_api=True, limit=100, dry_run=True)
import json; print(json.dumps(result, indent=2))
"
```

**Expected output:**
```json
{
  "total_parcels": ~15207,
  "branded": 15207,
  "rt_resolved": ~70,
  "rt_unresolved": ~30,
  "gw_resolved": ~0,
  "with_population": ~5000,
  "elapsed_s": ~5,
  "resolver_stats": {"cache_total": 15207, "cache_hits": ~70, ...},
  "dry_run": true
}
```

---

## PHASE 3: CLI Commands

### Step 3.1 -- Replace old `parcels` command group with new `parcels` command

**File to modify:** `$PROJ/cleo/cli.py`

**Action:** Replace the existing `parcels_cmd`, `parcel_enrich_cmd`, and `parcel_match_cmd` commands (lines 2538-2737) with a single new `parcels` command group. Keep the old commands' function bodies as comments for reference during transition, but replace with:

```python
@main.command(name="parcels")
@click.option("--build", is_flag=True, help="Build the full parcel registry.")
@click.option("--skip-api", is_flag=True, help="Build from cache only (no provincial API queries).")
@click.option("--limit", type=int, default=None, help="Process first N RT records (for testing).")
@click.option("--dry-run", is_flag=True, help="Preview without saving.")
@click.option("--status", "show_status", is_flag=True, help="Show registry stats.")
@click.option("--resolve-arn", "resolve_arn", default=None, help="Resolve a single ARN.")
@click.option("--resolve-pin", "resolve_pin", default=None, help="Resolve a single PIN.")
@click.option("--resolve-coords", "resolve_coords", nargs=2, type=float, default=None, help="Resolve lat lng.")
@click.option("--seed-cache", is_flag=True, help="Seed parcel cache from branded_parcels/ without building registry.")
def parcels_cmd(build, skip_api, limit, dry_run, show_status, resolve_arn, resolve_pin, resolve_coords, seed_cache):
    """Parcel-centric registry: build, resolve, and inspect.

    The parcel registry is the master data store. Every commercial parcel
    is discovered via branded locations, RT transactions, or GW records,
    then enriched with geometry, transactions, assessment, and population.

    \b
    Examples:
        cleo parcels --status                          # Show registry stats
        cleo parcels --seed-cache                      # Seed cache from branded harvests
        cleo parcels --build --skip-api                # Build from cache only
        cleo parcels --build --limit 100 --dry-run     # Test build with 100 RT records
        cleo parcels --build                           # Full build (requires AgMaps token)
        cleo parcels --resolve-arn 393601009007200     # Resolve a single ARN
        cleo parcels --resolve-pin 082620036           # Resolve a single PIN
        cleo parcels --resolve-coords 42.98 -81.26    # Resolve a point
    """
    from cleo.config import PARCEL_CACHE_PATH, PARCEL_REGISTRY_PATH, BRANDED_PARCELS_DIR

    if show_status:
        _parcels_status()
        return

    if seed_cache:
        from cleo.parcels.cache import ParcelCache
        cache = ParcelCache()
        added = cache.seed_from_branded_parcels(BRANDED_PARCELS_DIR)
        cache.save()
        stats = cache.stats()
        click.echo(f"Seeded parcel cache: {added:,} new parcels")
        click.echo(f"Total in cache:      {stats['total']:,}")
        click.echo(f"With geometry:       {stats['with_geometry']:,}")
        click.echo(f"Saved to {PARCEL_CACHE_PATH}")
        return

    if resolve_arn or resolve_pin or resolve_coords:
        _parcels_resolve(resolve_arn, resolve_pin, resolve_coords)
        return

    if build:
        from cleo.parcels.registry_builder import build_registry
        prefix = "[DRY RUN] " if dry_run else ""
        click.echo(f"{prefix}Building parcel registry...\n")

        result = build_registry(skip_api=skip_api, limit=limit, dry_run=dry_run)

        click.echo(f"\n{prefix}=== Parcel Registry Build ===")
        click.echo(f"{prefix}Total parcels:    {result['total_parcels']:,}")
        click.echo(f"{prefix}  Branded:        {result['branded']:,}")
        click.echo(f"{prefix}  RT resolved:    {result['rt_resolved']:,}")
        click.echo(f"{prefix}  RT unresolved:  {result['rt_unresolved']:,}")
        click.echo(f"{prefix}  GW resolved:    {result['gw_resolved']:,}")
        click.echo(f"{prefix}  With population:{result['with_population']:,}")
        click.echo(f"{prefix}  Elapsed:        {result['elapsed_s']:.1f}s")
        rs = result.get("resolver_stats", {})
        click.echo(f"\n{prefix}Resolver: cache_hits={rs.get('cache_hits', 0):,} "
                    f"api_hits={rs.get('api_hits', 0):,} "
                    f"api_misses={rs.get('api_misses', 0):,}")
        if not dry_run:
            click.echo(f"\nSaved to {PARCEL_REGISTRY_PATH}")
        return

    click.echo("Use --build, --status, --seed-cache, or --resolve-*. Run 'cleo parcels --help' for options.")


def _parcels_status():
    """Show parcel registry statistics."""
    from cleo.config import PARCEL_CACHE_PATH, PARCEL_REGISTRY_PATH

    click.echo("\n=== Parcel Cache ===")
    if PARCEL_CACHE_PATH.exists():
        from cleo.parcels.cache import ParcelCache
        cache = ParcelCache()
        stats = cache.stats()
        click.echo(f"Total:           {stats['total']:,}")
        click.echo(f"With geometry:   {stats['with_geometry']:,}")
        click.echo(f"With PIN:        {stats['with_pin']:,}")
        for src, cnt in sorted(stats.get("by_source", {}).items()):
            click.echo(f"  {src:>20s}: {cnt:,}")
    else:
        click.echo("(not built — run 'cleo parcels --seed-cache')")

    click.echo("\n=== Parcel Registry ===")
    if PARCEL_REGISTRY_PATH.exists():
        import json
        data = json.loads(PARCEL_REGISTRY_PATH.read_text(encoding="utf-8"))
        meta = data.get("meta", {})
        click.echo(f"Total parcels:   {meta.get('total', 0):,}")
        click.echo(f"Generated at:    {meta.get('generated_at', 'unknown')}")
        sources = meta.get("sources", {})
        for src, cnt in sorted(sources.items()):
            click.echo(f"  {src:>10s}: {cnt:,}")
        stats = meta.get("stats", {})
        click.echo(f"With transactions: {stats.get('with_transactions', 0):,}")
        click.echo(f"With brands:       {stats.get('with_brands', 0):,}")
        click.echo(f"With assessment:   {stats.get('with_assessment', 0):,}")
        click.echo(f"With geometry:     {stats.get('with_geometry', 0):,}")
        click.echo(f"With population:   {stats.get('with_population', 0):,}")
    else:
        click.echo("(not built — run 'cleo parcels --build')")
    click.echo()


def _parcels_resolve(resolve_arn, resolve_pin, resolve_coords):
    """Resolve a single parcel identifier."""
    import json as _json
    from cleo.parcels.cache import ParcelCache
    from cleo.parcels.resolver import ParcelResolver

    cache = ParcelCache()
    resolver = ParcelResolver(cache=cache, skip_api=False)

    result = None
    if resolve_arn:
        click.echo(f"Resolving ARN: {resolve_arn}")
        result = resolver.resolve_by_arn(resolve_arn)
    elif resolve_pin:
        click.echo(f"Resolving PIN: {resolve_pin}")
        result = resolver.resolve_by_pin(resolve_pin)
    elif resolve_coords:
        lat, lng = resolve_coords
        click.echo(f"Resolving coords: ({lat}, {lng})")
        result = resolver.resolve_by_coords(lat, lng)

    if result:
        # Print without geometry for readability
        display = dict(result)
        if display.get("geometry"):
            geom = display["geometry"]
            ncoords = len(geom.get("coordinates", [[]])[0]) if geom.get("coordinates") else 0
            display["geometry"] = f"<{geom.get('type', '?')} with {ncoords} vertices>"
        click.echo(_json.dumps(display, indent=2, ensure_ascii=False, default=str))
        resolver.save_cache()
    else:
        click.echo("Not found.")
    click.echo(f"\nResolver stats: {resolver.get_stats()}")
```

**Test command:**
```bash
.venv/bin/python -m cleo.cli parcels --status
.venv/bin/python -m cleo.cli parcels --seed-cache
.venv/bin/python -m cleo.cli parcels --build --skip-api --limit 50 --dry-run
```

---

## PHASE 4: Backend API Endpoints

### Step 4.1 -- Add new parcel API endpoints to app.py

**File to modify:** `$PROJ/cleo/web/app.py`

**Action:** Add these new endpoints. Place them after the existing branded-parcels endpoints (around line 4774) but before the React SPA catch-all route (line 4776).

Add this import at the top of app.py (with the other config imports, line 15):
```python
from cleo.config import ..., PARCEL_REGISTRY_PATH  # add to existing import
```

Add a cache variable near the other caches (around line 4345):
```python
# Parcel registry cache
_parcel_registry_cache: dict | None = None
_parcel_registry_mtime: float = 0
```

Add the lazy-loader:
```python
def _get_parcel_registry() -> dict:
    """Load and cache parcel_registry.json, reloading when file changes."""
    global _parcel_registry_cache, _parcel_registry_mtime
    if not PARCEL_REGISTRY_PATH.exists():
        return {"parcels": {}, "indexes": {}, "meta": {}}
    mtime = PARCEL_REGISTRY_PATH.stat().st_mtime
    if _parcel_registry_cache is not None and _parcel_registry_mtime == mtime:
        return _parcel_registry_cache
    _parcel_registry_cache = json.loads(PARCEL_REGISTRY_PATH.read_text(encoding="utf-8"))
    _parcel_registry_mtime = mtime
    return _parcel_registry_cache
```

**New endpoints:**

```python
# ---------------------------------------------------------------------------
# Parcel Registry API (new parcel-centric endpoints)
# ---------------------------------------------------------------------------

@app.get("/api/parcels/registry")
def api_parcel_registry_list(
    city: str | None = None,
    brand: str | None = None,
    has_transactions: bool | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    min_date: str | None = None,
    max_date: str | None = None,
    offset: int = 0,
    limit: int = 500,
):
    """List/search parcels from the registry with filters.

    Returns summary records (no geometry) for table display.
    Pagination via offset/limit.
    """
    reg = _get_parcel_registry()
    parcels = reg.get("parcels", {})

    results = []
    for arn, rec in parcels.items():
        # Apply filters
        if city and (rec.get("city") or "").upper() != city.upper():
            continue

        if brand:
            brand_names = [b.get("name", "").lower() for b in rec.get("brands", [])]
            if not any(brand.lower() in bn for bn in brand_names):
                continue

        if has_transactions is not None:
            if has_transactions and not rec.get("transactions"):
                continue
            if not has_transactions and rec.get("transactions"):
                continue

        # Price filter: check latest transaction price
        if min_price or max_price:
            prices = [t.get("price") for t in rec.get("transactions", []) if t.get("price")]
            if not prices:
                if min_price:
                    continue  # Skip if no price and we need min
            else:
                latest_price = prices[0]  # transactions are sorted desc
                if min_price and latest_price < min_price:
                    continue
                if max_price and latest_price > max_price:
                    continue

        # Date filter
        if min_date or max_date:
            dates = [t.get("date", "") for t in rec.get("transactions", []) if t.get("date")]
            if not dates:
                continue
            latest_date = dates[0]
            if min_date and latest_date < min_date:
                continue
            if max_date and latest_date > max_date:
                continue

        # Build summary (no geometry)
        txns = rec.get("transactions", [])
        latest_txn = txns[0] if txns else {}
        brand_names = sorted(set(b.get("name", "") for b in rec.get("brands", []) if b.get("name")))

        results.append({
            "arn": arn,
            "pid": rec.get("pid"),
            "pin": rec.get("pin"),
            "city": rec.get("city"),
            "address": rec["addresses"][0] if rec.get("addresses") else "",
            "addresses": rec.get("addresses", []),
            "population": rec.get("population"),
            "zoning": rec.get("zoning"),
            "area_sqm": rec.get("area_sqm"),
            "brand_count": len(brand_names),
            "brands": brand_names[:5],
            "transaction_count": len(txns),
            "latest_price": latest_txn.get("price"),
            "latest_date": latest_txn.get("date"),
            "latest_buyer": latest_txn.get("buyer"),
            "has_assessment": bool(rec.get("assessment")),
            "sources": rec.get("sources", []),
            "centroid": rec.get("centroid"),
        })

    total = len(results)
    results = results[offset:offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "results": results,
    }


@app.get("/api/parcels/registry/{arn}")
def api_parcel_registry_detail(arn: str):
    """Return full detail for a single parcel, including geometry."""
    reg = _get_parcel_registry()
    parcels = reg.get("parcels", {})

    if arn not in parcels:
        # Try padding 15-digit to 20-digit
        if len(arn) == 15:
            arn_20 = arn + "00000"
            if arn_20 in parcels:
                arn = arn_20
            else:
                raise HTTPException(404, f"Parcel not found: {arn}")
        else:
            raise HTTPException(404, f"Parcel not found: {arn}")

    rec = parcels[arn]

    # Include geometry for the detail view
    return {
        **rec,
        "arn": arn,
    }


@app.get("/api/parcels/registry/geojson")
def api_parcel_registry_geojson(
    south: float | None = None,
    west: float | None = None,
    north: float | None = None,
    east: float | None = None,
    city: str | None = None,
    brand: str | None = None,
    has_transactions: bool | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
):
    """Return GeoJSON FeatureCollection for map display.

    Bbox required for viewport-based loading. Features include
    polygon geometry + summary properties for popup/styling.
    Cap at 3000 features per request.
    """
    reg = _get_parcel_registry()
    parcels = reg.get("parcels", {})

    features = []
    for arn, rec in parcels.items():
        centroid = rec.get("centroid")
        if not centroid:
            continue

        # Bbox filter
        if south is not None and west is not None and north is not None and east is not None:
            lat, lng = centroid
            if not (south <= lat <= north and west <= lng <= east):
                continue

        # Filters (same as list endpoint)
        if city and (rec.get("city") or "").upper() != city.upper():
            continue
        if brand:
            brand_names = [b.get("name", "").lower() for b in rec.get("brands", [])]
            if not any(brand.lower() in bn for bn in brand_names):
                continue
        if has_transactions is not None:
            if has_transactions and not rec.get("transactions"):
                continue
            if not has_transactions and rec.get("transactions"):
                continue
        if min_price or max_price:
            prices = [t.get("price") for t in rec.get("transactions", []) if t.get("price")]
            latest_price = prices[0] if prices else None
            if min_price and (latest_price is None or latest_price < min_price):
                continue
            if max_price and latest_price and latest_price > max_price:
                continue

        txns = rec.get("transactions", [])
        latest = txns[0] if txns else {}
        brand_list = sorted(set(b.get("name", "") for b in rec.get("brands", []) if b.get("name")))

        geometry = rec.get("geometry")
        if not geometry:
            # Fall back to point if no polygon
            geometry = {
                "type": "Point",
                "coordinates": [centroid[1], centroid[0]],  # GeoJSON is [lng, lat]
            }

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "arn": arn,
                "pid": rec.get("pid"),
                "city": rec.get("city"),
                "address": rec["addresses"][0] if rec.get("addresses") else "",
                "brand_count": len(brand_list),
                "brands": brand_list[:3],
                "transaction_count": len(txns),
                "latest_price": latest.get("price"),
                "latest_date": latest.get("date"),
                "has_transactions": bool(txns),
                "population": rec.get("population"),
                "zoning": rec.get("zoning"),
                "sources": rec.get("sources", []),
            },
        })

        if len(features) >= 3000:
            break

    return {"type": "FeatureCollection", "features": features}


@app.get("/api/parcels/registry/stats")
def api_parcel_registry_stats():
    """Return registry statistics for the dashboard."""
    reg = _get_parcel_registry()
    meta = reg.get("meta", {})
    parcels = reg.get("parcels", {})

    # City breakdown
    city_counts: dict[str, int] = {}
    for rec in parcels.values():
        c = rec.get("city") or "Unknown"
        city_counts[c] = city_counts.get(c, 0) + 1

    return {
        "meta": meta,
        "city_counts": dict(sorted(city_counts.items(), key=lambda x: -x[1])[:50]),
        "total_parcels": meta.get("total", 0),
    }


@app.get("/api/parcels/registry/filters")
def api_parcel_registry_filters():
    """Return available filter values for the UI."""
    reg = _get_parcel_registry()
    parcels = reg.get("parcels", {})

    cities: dict[str, int] = {}
    brands: dict[str, int] = {}
    for rec in parcels.values():
        c = rec.get("city")
        if c:
            cities[c] = cities.get(c, 0) + 1
        for b in rec.get("brands", []):
            name = b.get("name", "")
            if name:
                brands[name] = brands.get(name, 0) + 1

    return {
        "cities": sorted(
            [{"name": c, "count": n, "population": rec.get("population")}
             for c, n in cities.items()],
            key=lambda x: -x["count"],
        ),
        "brands": sorted(
            [{"name": b, "count": n} for b, n in brands.items()],
            key=lambda x: -x["count"],
        )[:200],
    }


@app.get("/api/parcels/registry/by-pid/{pid}")
def api_parcel_by_pid(pid: str):
    """Look up a parcel by its P-ID. Returns redirect ARN."""
    reg = _get_parcel_registry()
    pid_to_arn = reg.get("indexes", {}).get("pid_to_arn", {})
    arn = pid_to_arn.get(pid)
    if not arn:
        raise HTTPException(404, f"No parcel for P-ID: {pid}")
    return {"arn": arn, "pid": pid}
```

**Test command (after building registry):**
```bash
curl http://localhost:8099/api/parcels/registry/stats
curl "http://localhost:8099/api/parcels/registry?city=London&limit=5"
```

---

## PHASE 5: Frontend Stripping

### Step 5.1 -- Update Sidebar navigation

**File to modify:** `$PROJ/frontend/src/components/layout/Sidebar.tsx`

**Action:** Replace the `navGroups` array. Remove: CRM Contacts, Deals, Outreach, Operators, Brands, Parties (Companies). Add: Parcels. Keep: Dashboard, Transactions, Map, Admin. Keep Properties for now (it becomes a legacy/redirect).

New `navGroups`:

```typescript
const navGroups: NavGroup[] = [
  {
    label: "",
    items: [
      { to: "/dashboard", label: "Dashboard", icon: SquaresFour },
      { to: "/parcels", label: "Parcels", icon: Buildings },
      { to: "/transactions", label: "Transactions", icon: Receipt },
      { to: "/map", label: "Map", icon: MapPin },
    ],
  },
  {
    label: "",
    items: [
      { to: "/admin", label: "Admin", icon: GearSix },
    ],
  },
];
```

Remove unused icon imports (`AddressBook`, `Handshake`, `Strategy`, `EnvelopeSimple`, `Storefront`, `UserCircle`).

---

### Step 5.2 -- Update App.tsx routes

**File to modify:** `$PROJ/frontend/src/App.tsx`

**Action:** Remove routes for: CRM (contacts, deals), Operators, Outreach, Brands, Parties, Contacts. Add routes for Parcels. Keep: Dashboard, Transactions, Map, Admin, Properties (redirect to parcels).

```typescript
import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import TransactionsPage from "./components/transactions/TransactionsPage";
import TransactionDetailPage from "./components/transactions/TransactionDetailPage";
import DashboardPage from "./components/dashboard/DashboardPage";
import AdminPage from "./components/admin/AdminPage";
import ParcelsPage from "./components/parcels/ParcelsPage";
import ParcelDetailPage from "./components/parcels/ParcelDetailPage";

const MapPage = lazy(() => import("./components/map/MapPage"));

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="parcels" element={<ParcelsPage />} />
        <Route path="parcels/:arn" element={<ParcelDetailPage />} />
        <Route path="transactions" element={<TransactionsPage />} />
        <Route path="transactions/:rtId" element={<TransactionDetailPage />} />
        {/* Legacy property URLs redirect to parcel lookup */}
        <Route path="properties/:propId" element={<Navigate to="/parcels" replace />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="map" element={<Suspense fallback={<div className="flex-1 flex items-center justify-center"><p className="text-sm text-gray-500">Loading map...</p></div>}><MapPage /></Suspense>} />
      </Route>
    </Routes>
  );
}
```

---

## PHASE 6: Frontend New Pages and Rewiring

### Step 6.1 -- Create Parcel types

**File to create:** `$PROJ/frontend/src/types/parcel.ts`

```typescript
export interface ParcelBrand {
  name: string;
  type: string;
  lat: number;
  lng: number;
}

export interface ParcelTransaction {
  rt_id: string;
  date: string;
  price: number | null;
  buyer: string;
  seller: string;
}

export interface ParcelAssessment {
  value: number | null;
  property_code: string;
  property_description: string;
  legal_desc: string;
  zoning: string;
  frontage: string;
  owner: string;
  owner_address: string;
}

export interface ParcelSummary {
  arn: string;
  pid: string | null;
  pin: string | null;
  city: string | null;
  address: string;
  addresses: string[];
  population: number | null;
  zoning: string | null;
  area_sqm: number | null;
  brand_count: number;
  brands: string[];
  transaction_count: number;
  latest_price: number | null;
  latest_date: string | null;
  latest_buyer: string | null;
  has_assessment: boolean;
  sources: string[];
  centroid: [number, number] | null;
}

export interface ParcelDetail {
  arn: string;
  pid: string | null;
  pin: string | null;
  city: string | null;
  addresses: string[];
  area_sqm: number | null;
  zoning: string | null;
  population: number | null;
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon | null;
  centroid: [number, number] | null;
  brands: ParcelBrand[];
  transactions: ParcelTransaction[];
  assessment: ParcelAssessment | null;
  discovered_via: string;
  sources: string[];
}

export interface ParcelListResponse {
  total: number;
  offset: number;
  limit: number;
  results: ParcelSummary[];
}

export interface ParcelFilter {
  name: string;
  count: number;
  population?: number;
}

export interface ParcelFiltersResponse {
  cities: ParcelFilter[];
  brands: ParcelFilter[];
}

export interface ParcelStatsResponse {
  meta: {
    total: number;
    generated_at: string;
    sources: Record<string, number>;
    stats: Record<string, number>;
  };
  city_counts: Record<string, number>;
  total_parcels: number;
}
```

---

### Step 6.2 -- Create Parcel API hooks

**File to create:** `$PROJ/frontend/src/api/parcels.ts`

```typescript
import { useCallback, useEffect, useState } from "react";
import { fetchApi } from "./client";
import type {
  ParcelSummary,
  ParcelDetail,
  ParcelListResponse,
  ParcelFiltersResponse,
  ParcelStatsResponse,
} from "../types/parcel";

export function useParcels(params?: Record<string, string>) {
  const [data, setData] = useState<ParcelListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const qs = params
      ? "?" + new URLSearchParams(params).toString()
      : "";
    fetchApi<ParcelListResponse>(`/parcels/registry${qs}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [params ? JSON.stringify(params) : ""]);

  useEffect(() => { load(); }, [load]);

  return { data, loading, error, reload: load };
}

export function useParcel(arn: string) {
  const [data, setData] = useState<ParcelDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchApi<ParcelDetail>(`/parcels/registry/${arn}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [arn]);

  useEffect(() => { load(); }, [load]);

  return { data, loading, error, reload: load };
}

export function useParcelFilters() {
  const [data, setData] = useState<ParcelFiltersResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi<ParcelFiltersResponse>("/parcels/registry/filters")
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading };
}

export function useParcelStats() {
  const [data, setData] = useState<ParcelStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi<ParcelStatsResponse>("/parcels/registry/stats")
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading };
}
```

---

### Step 6.3 -- Create ParcelsPage component

**File to create:** `$PROJ/frontend/src/components/parcels/ParcelsPage.tsx`

This is a TanStack Table page showing the parcel list with filters. Follow the existing pattern from `PropertiesPage.tsx` and `TransactionsPage.tsx`.

Key features:
- City filter dropdown (from `/api/parcels/registry/filters`)
- Brand filter dropdown
- Has transactions toggle
- Price range inputs
- Date range inputs
- Columns: ARN/PID, Address, City, Brands, Transactions, Latest Price, Latest Date, Sources
- Click row to navigate to `/parcels/{arn}`
- Pagination (offset/limit)

The component should be approximately 200-300 lines, following the exact same patterns as the existing `TransactionsPage.tsx` (TanStack Table, filters bar, column definitions).

---

### Step 6.4 -- Create ParcelDetailPage component

**File to create:** `$PROJ/frontend/src/components/parcels/ParcelDetailPage.tsx`

Key sections:
- **Header:** ARN, P-ID, City, Population, Addresses
- **Mini Map:** Mapbox GL showing parcel polygon with brand POI dots
- **Brands card:** List of brands on this parcel
- **Transactions card:** Table of RT transactions (linked to /transactions/:rtId)
- **Assessment card:** MPAC assessment data (if from GW)
- **Sources badge:** Which sources contributed data

The component should use `useParams()` to get `arn` from the URL, call `useParcel(arn)`, and render the data.

---

### Step 6.5 -- Rewire the Dashboard

**File to modify:** `$PROJ/frontend/src/components/dashboard/DashboardPage.tsx`

**Action:** The dashboard currently shows properties-centric data. Replace with parcel stats. Add a new `useParcelStats()` call. Show:
- Total parcels (with breakdown by source)
- Parcels with transactions
- Parcels with brands
- Top cities by parcel count
- Keep the existing transaction volume chart and recent transactions (those come from RT data and are still valid)

Remove: Pipeline card (CRM), Prospects card (CRM-related). These were CRM features being stripped.

Update the dashboard API call: keep `/api/dashboard` for transaction stats. Add `/api/parcels/registry/stats` for parcel stats.

---

### Step 6.6 -- Rewire the Map page

**File to modify:** `$PROJ/frontend/src/components/map/MapPage.tsx`

**Action:** Replace the property-point-based map with parcel-polygon-based map.

Key changes:
1. **Data source:** Change from `useProperties()` point GeoJSON to `/api/parcels/registry/geojson` polygon GeoJSON
2. **Layer style:** Show parcel polygons (filled, semi-transparent) instead of circles. Color by source or has_transactions.
3. **Popup:** Show parcel summary (ARN, address, city, brands, latest transaction)
4. **Click:** Navigate to `/parcels/{arn}` on polygon click
5. **Filters:** City, Brand, Has Transactions, Price Range (passed as query params to the geojson endpoint)
6. **Clustering:** At low zoom levels, show point clusters based on centroids. At zoom >= 14, switch to polygon display.

The existing MapPage is approximately 600 lines. The parcel version will be similar in size but with polygon layers instead of circle layers.

Reuse existing patterns:
- `react-map-gl/mapbox` components
- Source + Layer components for polygon fill and outline
- Popup component
- Filter panel (MultiSelect for cities, brands)

---

## PHASE 7: Integration Testing

### Step 7.1 -- End-to-end CLI test

```bash
# Step 1: Seed cache from branded harvests
.venv/bin/python -m cleo.cli parcels --seed-cache

# Expected: "Seeded parcel cache: ~15,207 new parcels"

# Step 2: Build registry (cache-only, no API)
.venv/bin/python -m cleo.cli parcels --build --skip-api

# Expected output:
# Total parcels:    ~15,300+
# Branded:          15,207
# RT resolved:      ~9,000-11,000 (ARN cache hits from branded parcels)
# RT unresolved:    ~5,000-7,000 (parcels not in branded harvest)
# GW resolved:      ~200-400
# With population:  ~5,000+

# Step 3: Check status
.venv/bin/python -m cleo.cli parcels --status

# Step 4: Resolve a single parcel (requires AgMaps token)
.venv/bin/python -m cleo.cli parcels --resolve-arn 393601009007200
```

### Step 7.2 -- API test

```bash
# Start backend
.venv/bin/python -m cleo.cli web &

# Test endpoints
curl -s http://localhost:8099/api/parcels/registry/stats | python3 -m json.tool
curl -s "http://localhost:8099/api/parcels/registry?city=London&limit=3" | python3 -m json.tool
curl -s "http://localhost:8099/api/parcels/registry/geojson?south=42.9&west=-81.4&north=43.1&east=-81.1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d[\"features\"])} features')"
```

### Step 7.3 -- Frontend test

```bash
cd frontend && npm run dev
# Open http://localhost:5173/parcels -- should show parcel table
# Open http://localhost:5173/map -- should show parcel polygons
# Open http://localhost:5173/dashboard -- should show parcel stats
```

---

## Dependencies and Sequencing

```
Phase 0 (config)
    |
Phase 1.1 (cache.py)
    |
Phase 1.2 (resolver.py) -- depends on cache.py
    |
Phase 2.1 (registry_builder.py) -- depends on cache + resolver
    |
Phase 3.1 (CLI commands) -- depends on all Phase 1-2
    |
Phase 4.1 (API endpoints) -- depends on Phase 2 (needs registry file)
    |
Phase 5 (frontend strip) -- independent of backend, can parallel with Phase 3-4
    |
Phase 6.1-6.2 (types + API hooks) -- needs Phase 4 API
    |
Phase 6.3-6.6 (pages) -- needs types + hooks
    |
Phase 7 (testing) -- needs everything
```

**What can be parallelized:**
- Phase 5 (frontend stripping) can run in parallel with Phase 1-4
- Phase 6.1-6.2 (types/hooks) can be written speculatively before Phase 4 is fully tested
- Phase 0 is trivial and takes 30 seconds

---

## Files NOT to Touch

These upstream pipelines remain unchanged:
- `cleo/parse/` -- parse pipeline
- `cleo/normalize/` -- normalization pipeline
- `cleo/extract/` -- extraction pipeline
- `cleo/geocode/` -- geocoding pipeline
- `cleo/validate/` -- validation checks
- `cleo/ingest/` -- scraping/fetching
- `cleo/geowarehouse/` -- GW parse pipeline
- `cleo/versioning.py` -- generic versioned store
- `cleo/properties/` -- legacy properties (keep, don't modify)
- `cleo/parties/` -- legacy parties (keep, don't modify)
- `cleo/web/crm.py` -- CRM router (keep file, just don't include in app)
- `cleo/web/operators.py` -- operators router (keep file, just don't include)
- `cleo/web/outreach.py` -- outreach router (keep file, just don't include)

---

## Files to Create (6 total)

1. `$PROJ/cleo/parcels/cache.py` -- ParcelCache class (Phase 1.1)
2. `$PROJ/cleo/parcels/resolver.py` -- ParcelResolver class (Phase 1.2)
3. `$PROJ/cleo/parcels/registry_builder.py` -- build_registry() (Phase 2.1)
4. `$PROJ/frontend/src/types/parcel.ts` -- TypeScript types (Phase 6.1)
5. `$PROJ/frontend/src/api/parcels.ts` -- API hooks (Phase 6.2)
6. `$PROJ/frontend/src/components/parcels/ParcelsPage.tsx` -- Parcel list page (Phase 6.3)
7. `$PROJ/frontend/src/components/parcels/ParcelDetailPage.tsx` -- Parcel detail page (Phase 6.4)

## Files to Modify (6 total)

1. `$PROJ/cleo/config.py` -- Add 2 path constants (Phase 0.1)
2. `$PROJ/cleo/cli.py` -- Replace parcel CLI commands (Phase 3.1)
3. `$PROJ/cleo/web/app.py` -- Add parcel registry API endpoints (Phase 4.1)
4. `$PROJ/frontend/src/App.tsx` -- Update routes (Phase 5.2)
5. `$PROJ/frontend/src/components/layout/Sidebar.tsx` -- Update navigation (Phase 5.1)
6. `$PROJ/frontend/src/components/dashboard/DashboardPage.tsx` -- Rewire to parcels (Phase 6.5)
7. `$PROJ/frontend/src/components/map/MapPage.tsx` -- Rewire to parcel polygons (Phase 6.6)

---

### Critical Files for Implementation

- `/Users/brandonolsen23/Library/Mobile Documents/com~apple~CloudDocs/01_Personal/01_Brandon/07_Development/2026-02-08 - Cleo Mini V3/cleo/parcels/registry_builder.py` - Core logic: the registry builder that merges branded parcels + RT + GW into the master parcel registry (must be created)
- `/Users/brandonolsen23/Library/Mobile Documents/com~apple~CloudDocs/01_Personal/01_Brandon/07_Development/2026-02-08 - Cleo Mini V3/cleo/parcels/resolver.py` - Core logic: the universal resolver that maps ARN/PIN/coords to cached parcels (must be created)
- `/Users/brandonolsen23/Library/Mobile Documents/com~apple~CloudDocs/01_Personal/01_Brandon/07_Development/2026-02-08 - Cleo Mini V3/cleo/parcels/provincial.py` - Existing code to understand: the working provincial API client that resolver.py wraps (reference pattern)
- `/Users/brandonolsen23/Library/Mobile Documents/com~apple~CloudDocs/01_Personal/01_Brandon/07_Development/2026-02-08 - Cleo Mini V3/cleo/web/app.py` - Must modify: add 6 new API endpoints for the parcel registry (lines ~4774+)
- `/Users/brandonolsen23/Library/Mobile Documents/com~apple~CloudDocs/01_Personal/01_Brandon/07_Development/2026-02-08 - Cleo Mini V3/cleo/parcels/property_matcher.py` - Reference pattern: the existing BrandedParcelIndex class loads all branded_parcels/*.json and builds ARN+spatial indexes (reusable logic for cache.py seeding)
