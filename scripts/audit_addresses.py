#!/usr/bin/env python3
"""Address Normalization Audit — Phase 0, Step 1.

Three clean sections:
  1. INGEST PIPELINE — each source through its own stages
  2. DATA MATCHING  — cross-source linkage (downstream, separate)
  3. NORMALIZATION QUALITY — internal metrics for tracking Phase 0

Usage:
    python scripts/audit_addresses.py                 # full report
    python scripts/audit_addresses.py --verbose       # + samples
    python scripts/audit_addresses.py --unknown-cities # all unknown cities
    python scripts/audit_addresses.py --log           # save snapshot
    python scripts/audit_addresses.py --history       # show trend
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cleo.config import (
    BRAND_MATCHES_PATH,
    BRANDS_DATA_DIR,
    COORDINATES_PATH,
    DATA_DIR,
    EXTRACTED_DIR,
    GEOCODE_CACHE_PATH,
    GW_PARSED_DIR,
    HTML_INDEX_PATH,
    PARCELS_PATH,
    PARSED_DIR,
    PROPERTIES_PATH,
)
from cleo.properties.normalize import (
    CITY_ALIASES,
    normalize_city_for_dedup,
    make_dedup_key,
)

AUDIT_LOG_PATH = DATA_DIR / "audit_log.jsonl"

# ---------------------------------------------------------------------------
# Address classification
# ---------------------------------------------------------------------------
_STARTS_WITH_DIGIT = re.compile(r"^\d")
_PO_BOX = re.compile(
    r"\b(P\.?O\.?\s*BOX|BOX\s+\d|GENERAL\s+DELIVERY)\b", re.IGNORECASE
)
_LEGAL_DESC = re.compile(
    r"\b(CONC(?:ESSION)?|LOT\s+\d|LOTS\s+\d|BLOCK\s+\d|PLAN\s+\d|CONDO\s+PLAN|PART\s+\d|"
    r"REGISTERED\s+PLAN|TWP|TOWNSHIP)\b",
    re.IGNORECASE,
)
_INTERSECTION = re.compile(
    r"\b(NEC|SWC|NWC|SEC|N/[EW]\s*C|S/[EW]\s*C|CORNER\s+OF)\b", re.IGNORECASE
)
_NON_ONTARIO_PROVINCE = re.compile(
    r",\s*(QUEBEC|ALBERTA|BRITISH\s+COLUMBIA|MANITOBA|SASKATCHEWAN|NOVA\s+SCOTIA|"
    r"NEW\s+BRUNSWICK|NEWFOUNDLAND|PRINCE\s+EDWARD\s+ISLAND|NUNAVUT|"
    r"YUKON|NORTHWEST\s+TERRITORIES)\b",
    re.IGNORECASE,
)
_US_STATE = re.compile(
    r",\s*(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|"
    r"MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|"
    r"ALABAMA|ALASKA|ARIZONA|ARKANSAS|CALIFORNIA|COLORADO|CONNECTICUT|DELAWARE|FLORIDA|"
    r"GEORGIA|HAWAII|IDAHO|ILLINOIS|INDIANA|IOWA|KANSAS|KENTUCKY|LOUISIANA|MAINE|MARYLAND|"
    r"MASSACHUSETTS|MICHIGAN|MINNESOTA|MISSISSIPPI|MISSOURI|MONTANA|NEBRASKA|NEVADA|"
    r"NEW\s+HAMPSHIRE|NEW\s+JERSEY|NEW\s+MEXICO|NEW\s+YORK|NORTH\s+CAROLINA|NORTH\s+DAKOTA|"
    r"OHIO|OKLAHOMA|OREGON|PENNSYLVANIA|RHODE\s+ISLAND|SOUTH\s+CAROLINA|SOUTH\s+DAKOTA|"
    r"TENNESSEE|TEXAS|UTAH|VERMONT|VIRGINIA|WASHINGTON|WEST\s+VIRGINIA|WISCONSIN|WYOMING)"
    r"\b",
    re.IGNORECASE,
)

_KNOWN_MUNICIPALITIES: set[str] = set()


def _build_known_cities() -> set[str]:
    cities: set[str] = set()
    for k, v in CITY_ALIASES.items():
        cities.add(k.upper())
        cities.add(v.upper())
    markets_path = DATA_DIR / "markets.json"
    if markets_path.exists():
        with open(markets_path) as f:
            md = json.load(f)
        if isinstance(md, dict):
            entries = md.get("markets", md)
            if isinstance(entries, dict):
                for name in entries:
                    if name not in ("meta", "source", "updated"):
                        cities.add(name.upper())
    return cities


def classify_address(address: str) -> str:
    if not address or not address.strip():
        return "empty"
    addr = address.strip()
    if _PO_BOX.search(addr):
        return "po_box"
    if _US_STATE.search(addr):
        return "us_address"
    if _NON_ONTARIO_PROVINCE.search(addr):
        return "non_ontario"
    if _LEGAL_DESC.search(addr) and not _STARTS_WITH_DIGIT.match(addr):
        return "legal_description"
    if _INTERSECTION.search(addr) and not _STARTS_WITH_DIGIT.match(addr):
        return "intersection"
    if not _STARTS_WITH_DIGIT.match(addr):
        return "no_street_number"
    return "ok"


def is_city_known(city: str) -> bool:
    if not city or not city.strip():
        return False
    upper = city.strip().upper()
    if upper in _KNOWN_MUNICIPALITIES:
        return True
    return normalize_city_for_dedup(city) in _KNOWN_MUNICIPALITIES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _active_dir(base: Path) -> Path | None:
    active = base / "active"
    if active.is_symlink() or active.is_dir():
        return active
    versions = sorted(base.glob("v*"))
    return versions[-1] if versions else None


PROPERTY_TYPE_ORDER = [
    "retail", "industrial", "office", "multifamily", "comm-ind-land",
    "farm", "res-land", "hotel-motel", "restaurant-bar", "other-bldg",
    "other-land",
]


def _pct(n: int, total: int) -> str:
    if not total:
        return "  -"
    return f"{n / total * 100:.1f}%"


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def collect_all(verbose: bool = False) -> dict:
    """Collect all metrics. Returns a flat dict."""

    # ── RT ID -> type lookup ──
    rt_to_type: dict[str, str] = {}
    idx = load_json(HTML_INDEX_PATH)
    if idx and isinstance(idx, dict):
        for rt_id, subpath in idx.items():
            rt_to_type[rt_id] = subpath.split("/")[0] if "/" in subpath else "unknown"

    # ── Stage 1: HTML by type ──
    html_by_type: Counter = Counter()
    html_dir = DATA_DIR / "html"
    for subdir in html_dir.iterdir():
        if subdir.is_dir() and subdir.name != ".DS_Store":
            n = len(list(subdir.glob("*.html")))
            if n:
                html_by_type[subdir.name] = n

    # ── Stage 2: Parsed by type ──
    parsed_by_type: Counter = Counter()
    parsed_dir = _active_dir(PARSED_DIR)

    # Normalization quality trackers
    rt_cities: Counter = Counter()
    rt_unknown_cities: Counter = Counter()
    property_categories: Counter = Counter()
    dedup_key_to_raws: defaultdict[str, list[tuple[str, str, str]]] = defaultdict(list)
    raw_addr_count = 0
    samples: defaultdict[str, list[str]] = defaultdict(list)

    def add_sample(key: str, val: str, limit: int = 5):
        if len(samples[key]) < limit:
            samples[key].append(val)

    if parsed_dir:
        for fp in sorted(parsed_dir.glob("*.json")):
            try:
                data = json.loads(fp.read_text())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            rt_id = data.get("rt_id", fp.stem)
            ptype = rt_to_type.get(rt_id, "unknown")
            parsed_by_type[ptype] += 1

            txn = data.get("transaction", {})
            ab = txn.get("address", {})
            addr = ab.get("address", "")
            city = ab.get("city", "")

            if addr:
                cat = classify_address(addr)
                property_categories[cat] += 1
                if verbose and cat != "ok":
                    add_sample(f"prop_{cat}", f"{addr} | {city}")
                if cat == "ok" and city:
                    raw_addr_count += 1
                    dedup_key_to_raws[make_dedup_key(addr, city)].append((addr, city, "rt"))
            if city:
                rt_cities[city] += 1
                if not is_city_known(city):
                    rt_unknown_cities[city] += 1

    # ── Stage 3: Normalized by type — DOES NOT EXIST YET (Phase 0 Step 2) ──
    # Will be filled in once cleo/normalize.py is built and wired in.
    # For now all zeros.

    # ── Stage 4: Extracted (expanded) by type ──
    extracted_by_type: Counter = Counter()
    ext_dir = _active_dir(EXTRACTED_DIR)
    if ext_dir:
        for fp in sorted(ext_dir.glob("*.json")):
            ptype = rt_to_type.get(fp.stem, "unknown")
            extracted_by_type[ptype] += 1

    # ── Stage 5: Geocoded by type ──
    # Load coordinate store keys, then check which parsed RT addresses are in it.
    coord_keys: set[str] = set()
    coords_data = load_json(COORDINATES_PATH)
    coord_store_total = 0
    coord_providers: Counter = Counter()
    if coords_data and isinstance(coords_data, dict):
        addresses = coords_data.get("addresses", {})
        coord_store_total = len(addresses)
        coord_keys = {k.upper() for k in addresses}
        for providers in addresses.values():
            if isinstance(providers, dict):
                for pname in providers:
                    coord_providers[pname] += 1

    legacy_cache = load_json(GEOCODE_CACHE_PATH)
    legacy_count = len(legacy_cache) if legacy_cache and isinstance(legacy_cache, dict) else 0

    # Count geocoded RT addresses by type by checking if the expanded
    # address appears in the coordinate store.
    geocoded_by_type: Counter = Counter()
    if ext_dir:
        for fp in sorted(ext_dir.glob("*.json")):
            try:
                data = json.loads(fp.read_text())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            ptype = rt_to_type.get(fp.stem, "unknown")
            # Check if any expanded property address is geocoded
            prop = data.get("property", {})
            found = False
            for addr_entry in prop.get("addresses", []):
                for expanded in addr_entry.get("expanded", []):
                    if expanded.upper() in coord_keys:
                        found = True
                        break
                if found:
                    break
            if found:
                geocoded_by_type[ptype] += 1

    # ── Stage 6: ArcGIS (parcels) — barely started ──
    parcel_data = load_json(PARCELS_PATH)
    parcel_total = 0
    parcel_munis: Counter = Counter()
    if parcel_data:
        features = parcel_data.get("features", [])
        parcel_total = len(features)
        for feat in features:
            fp = feat.get("properties", {})
            muni = fp.get("city", "") or fp.get("municipality", "")
            if muni:
                parcel_munis[muni] += 1

    # ── Stage 7: Canonicalized (properties registry) ──
    props_data = load_json(PROPERTIES_PATH)
    properties = props_data.get("properties", {}) if isinstance(props_data, dict) else {}
    props_total = len(properties)
    props_geocoded = 0
    props_by_source: Counter = Counter()
    no_coord_samples: list[str] = []

    for pid, p in properties.items():
        if not isinstance(p, dict):
            continue
        sources = p.get("sources", [])
        props_by_source["+".join(sorted(sources)) if sources else "none"] += 1
        lat, lng = p.get("lat"), p.get("lng")
        if lat and lng and lat != 0 and lng != 0:
            props_geocoded += 1
        elif verbose and len(no_coord_samples) < 10:
            no_coord_samples.append(f"{pid}: {p.get('address', '?')}, {p.get('city', '?')}")

    # ── Brands ingest pipeline ──
    brand_locations: Counter = Counter()  # brand -> location count
    brand_with_coords: Counter = Counter()  # brand -> locations that have scraper coords
    if BRANDS_DATA_DIR.exists():
        for bf in sorted(BRANDS_DATA_DIR.glob("*.json")):
            try:
                stores = json.loads(bf.read_text())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(stores, list):
                for s in stores:
                    brand = s.get("brand", "unknown")
                    brand_locations[brand] += 1
                    addr, city = s.get("address", ""), s.get("city", "")
                    if addr and city:
                        raw_addr_count += 1
                        dedup_key_to_raws[make_dedup_key(addr, city)].append(
                            (addr, city, "brand")
                        )
                    # Check if scraper provided coords
                    if s.get("lat") and s.get("lng"):
                        brand_with_coords[brand] += 1

    brand_total = sum(brand_locations.values())
    brand_count = len(brand_locations)
    brand_scraped_coords = sum(brand_with_coords.values())

    # ── GeoWarehouse ingest pipeline ──
    gw_total = 0
    gw_with_addr = 0
    gw_with_owner = 0
    gw_dir = _active_dir(GW_PARSED_DIR)
    if not gw_dir:
        versions = sorted(GW_PARSED_DIR.glob("v*"))
        gw_dir = versions[-1] if versions else None
    if gw_dir:
        for fp in sorted(gw_dir.glob("*.json")):
            try:
                d = json.loads(fp.read_text())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            gw_total += 1
            site = d.get("site_structure", {})
            pa = site.get("property_address", "")
            if pa:
                gw_with_addr += 1
                muni = site.get("municipality", "")
                if classify_address(pa) == "ok" and muni:
                    raw_addr_count += 1
                    dedup_key_to_raws[make_dedup_key(pa, muni)].append(
                        (pa, muni, "gw")
                    )
            if site.get("owner_mailing_address"):
                gw_with_owner += 1

    # ── Data Matching ──
    # RT -> Properties: count of properties with source containing "rt"
    rt_to_props = sum(1 for p in properties.values()
                      if isinstance(p, dict) and "rt" in p.get("sources", []))
    # Brands -> Properties
    matches_data = load_json(BRAND_MATCHES_PATH)
    brand_matched = 0
    if matches_data and isinstance(matches_data, dict):
        for ml in matches_data.values():
            if isinstance(ml, list):
                brand_matched += len(ml)
    brand_matched_props = len(matches_data) if matches_data else 0

    unmatched_data = load_json(DATA_DIR / "brand_unmatched.json")
    brand_unmatched = len(unmatched_data) if isinstance(unmatched_data, list) else 0

    # GW -> Properties
    gw_to_props = sum(1 for p in properties.values()
                      if isinstance(p, dict) and "gw" in p.get("sources", []))

    # ── Normalization quality ──
    multi_raw = {k: v for k, v in dedup_key_to_raws.items() if len(v) > 1}
    cross_source = {k: v for k, v in multi_raw.items() if len({s for _, _, s in v}) > 1}

    return {
        # Ingest: Realtrack
        "html_by_type": dict(html_by_type),
        "html_total": sum(html_by_type.values()),
        "parsed_by_type": dict(parsed_by_type),
        "parsed_total": sum(parsed_by_type.values()),
        "extracted_by_type": dict(extracted_by_type),
        "extracted_total": sum(extracted_by_type.values()),
        "geocoded_by_type": dict(geocoded_by_type),
        "geocoded_rt_total": sum(geocoded_by_type.values()),
        # Ingest: Brands
        "brand_total": brand_total,
        "brand_count": brand_count,
        "brand_scraped_coords": brand_scraped_coords,
        "brand_locations": dict(brand_locations.most_common()),
        # Ingest: GeoWarehouse
        "gw_total": gw_total,
        "gw_with_addr": gw_with_addr,
        "gw_with_owner": gw_with_owner,
        # Ingest: Parcels
        "parcel_total": parcel_total,
        "parcel_munis": dict(parcel_munis),
        # Canonicalized (properties)
        "properties_total": props_total,
        "properties_geocoded": props_geocoded,
        "properties_by_source": dict(props_by_source),
        # Geocoding store
        "coord_store_total": coord_store_total,
        "coord_providers": dict(coord_providers),
        "legacy_cache_total": legacy_count,
        # Data Matching
        "match_rt_to_props": rt_to_props,
        "match_brand_locations": brand_matched,
        "match_brand_props": brand_matched_props,
        "match_brand_unmatched": brand_unmatched,
        "match_gw_to_props": gw_to_props,
        # Normalization quality
        "norm_property_categories": dict(property_categories),
        "norm_raw_addresses": raw_addr_count,
        "norm_unique_keys": len(dedup_key_to_raws),
        "norm_multi_raw": len(multi_raw),
        "norm_cross_source": len(cross_source),
        "norm_city_total": sum(rt_cities.values()),
        "norm_city_unknown_count": sum(rt_unknown_cities.values()),
        "norm_city_unknown_unique": len(rt_unknown_cities),
        "norm_unknown_cities": dict(rt_unknown_cities.most_common(100)),
        # Verbose-only
        "_samples": dict(samples) if verbose else {},
        "_no_coord_samples": no_coord_samples,
        "_cross_source_samples": {
            k: [(r, c, s) for r, c, s in v]
            for k, v in list(sorted(cross_source.items()))[:10]
        } if verbose else {},
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(d: dict, verbose: bool = False, show_unknown: bool = False):
    W = 80

    # ==================================================================
    #  SECTION 1: INGEST PIPELINE
    # ==================================================================
    print()
    print("=" * W)
    print("  1. INGEST PIPELINE")
    print("=" * W)

    # ── Realtrack ──
    print()
    print("  REALTRACK")
    print(f"  {'Type':<16s} {'HTML':>7s} {'Parsed':>8s} {'Normal.':>8s} "
          f"{'Expanded':>9s} {'Geocoded':>9s} {'ArcGIS':>7s} {'Canon.':>7s}")
    print(f"  {'─' * 16} {'─' * 7} {'─' * 8} {'─' * 8} "
          f"{'─' * 9} {'─' * 9} {'─' * 7} {'─' * 7}")

    html_t = d["html_by_type"]
    pars_t = d["parsed_by_type"]
    ext_t = d["extracted_by_type"]
    geo_t = d["geocoded_by_type"]

    all_types = sorted(
        set(list(html_t.keys()) + list(pars_t.keys())),
        key=lambda t: PROPERTY_TYPE_ORDER.index(t) if t in PROPERTY_TYPE_ORDER else 99,
    )

    # How many properties come from each RT type? We don't have that directly,
    # so Canonicalized = same as Geocoded for now (all geocoded RT records are
    # in the registry). This is approximate.
    for ptype in all_types:
        h = html_t.get(ptype, 0)
        p = pars_t.get(ptype, 0)
        n = 0           # Normalized — not built yet
        e = ext_t.get(ptype, 0)
        g = geo_t.get(ptype, 0)
        a = 0           # ArcGIS — not wired per-type yet
        c = g           # Canonicalized ≈ geocoded for now
        print(f"  {ptype:<16s} {h:>7,} {p:>8,} {n:>8,} {e:>9,} {g:>9,} {a:>7,} {c:>7,}")

    # Totals
    print(f"  {'─' * 16} {'─' * 7} {'─' * 8} {'─' * 8} "
          f"{'─' * 9} {'─' * 9} {'─' * 7} {'─' * 7}")
    ht = d["html_total"]
    pt = d["parsed_total"]
    et = d["extracted_total"]
    gt = d["geocoded_rt_total"]
    print(f"  {'TOTAL':<16s} {ht:>7,} {pt:>8,} {0:>8,} {et:>9,} {gt:>9,} {0:>7,} {gt:>7,}")

    # ── Brands ──
    print()
    print("  BRANDS")
    print(f"  {d['brand_count']} brands, {d['brand_total']:,} store locations")
    print(f"  With scraper coordinates: {d['brand_scraped_coords']:,} "
          f"({_pct(d['brand_scraped_coords'], d['brand_total'])})")
    print(f"  Normalized: 0 (not built yet)")

    if verbose:
        print()
        top = d.get("brand_locations", {})
        shown = list(top.items())[:15]
        print(f"  {'Brand':<30s} {'Locations':>10s}")
        print(f"  {'─' * 30} {'─' * 10}")
        for brand, n in shown:
            print(f"  {brand:<30s} {n:>10,}")
        remaining = len(top) - len(shown)
        if remaining > 0:
            print(f"  ... and {remaining} more")

    # ── GeoWarehouse ──
    print()
    print("  GEOWAREHOUSE")
    print(f"  Parsed records:       {d['gw_total']:>6,}")
    print(f"  With property addr:   {d['gw_with_addr']:>6,}")
    print(f"  With owner addr:      {d['gw_with_owner']:>6,}")
    print(f"  Normalized: 0 (not built yet)")

    # ── Parcels (ArcGIS) ──
    print()
    print("  PARCELS (ArcGIS)")
    print(f"  Records harvested:    {d['parcel_total']:>6,}")
    if d["parcel_munis"]:
        for muni, n in sorted(d["parcel_munis"].items(), key=lambda x: -x[1]):
            print(f"    {muni:<28s} {n:>5,}")

    # ── Canonicalized (Properties Registry) ──
    print()
    print("  PROPERTIES REGISTRY (canonicalized)")
    print(f"  Total properties:     {d['properties_total']:>6,}")
    print(f"  With coordinates:     {d['properties_geocoded']:>6,}  "
          f"({_pct(d['properties_geocoded'], d['properties_total'])})")
    print()
    print("  By source:")
    for src, n in sorted(d["properties_by_source"].items(), key=lambda x: -x[1]):
        print(f"    {src:<22s} {n:>6,}")

    if verbose and d.get("_no_coord_samples"):
        print()
        print("  Missing coordinates (sample):")
        for s in d["_no_coord_samples"]:
            print(f"    {s}")

    # ── Geocoding Store ──
    print()
    print("  GEOCODING STORE")
    print(f"  Coordinate store:     {d['coord_store_total']:>6,} addresses")
    print(f"  Legacy cache:         {d['legacy_cache_total']:>6,} addresses")
    if d["coord_providers"]:
        print("  Providers:")
        for prov, n in sorted(d["coord_providers"].items(), key=lambda x: -x[1]):
            print(f"    {prov:<14s} {n:>8,}")

    # ==================================================================
    #  SECTION 2: DATA MATCHING
    # ==================================================================
    print()
    print("=" * W)
    print("  2. DATA MATCHING (downstream — depends on clean data)")
    print("=" * W)
    print()
    print(f"  {'Source':<16s} {'→':>2s}  {'Properties':>12s}  {'of':>3s}  {'Total':>12s}")
    print(f"  {'─' * 16} {'─' * 2}  {'─' * 12}  {'─' * 3}  {'─' * 12}")
    print(f"  {'Realtrack':<16s} {'→':>2s}  {d['match_rt_to_props']:>12,}  of  {d['properties_total']:>12,}")
    print(f"  {'Brands':<16s} {'→':>2s}  {d['match_brand_props']:>12,}  of  {d['properties_total']:>12,}")
    print(f"  {'GeoWarehouse':<16s} {'→':>2s}  {d['match_gw_to_props']:>12,}  of  {d['properties_total']:>12,}")
    print()
    print(f"  Brand detail: {d['match_brand_locations']:,} location matches across "
          f"{d['match_brand_props']:,} properties")
    print(f"  Brand unmatched: {d['match_brand_unmatched']:,} locations")

    # ==================================================================
    #  SECTION 3: NORMALIZATION QUALITY
    # ==================================================================
    print()
    print("=" * W)
    print("  3. NORMALIZATION QUALITY (Phase 0 tracking)")
    print("=" * W)

    # ── Address categories ──
    cats = d["norm_property_categories"]
    total_prop = sum(cats.values())
    print()
    print("  Property address quality:")
    for cat in ["ok", "no_street_number", "po_box", "legal_description",
                "intersection", "non_ontario", "us_address", "empty"]:
        n = cats.get(cat, 0)
        if n:
            label = cat.replace("_", " ")
            print(f"    {label:<25s} {n:>7,}  ({_pct(n, total_prop)})")
            if verbose:
                for s in d.get("_samples", {}).get(f"prop_{cat}", []):
                    print(f"      e.g. {s}")

    # ── City resolution ──
    print()
    ct_total = d["norm_city_total"]
    ct_unk = d["norm_city_unknown_count"]
    ct_known = ct_total - ct_unk
    print(f"  City resolution:")
    print(f"    Total references:   {ct_total:>8,}")
    print(f"    Known:              {ct_known:>8,}  ({_pct(ct_known, ct_total)})")
    print(f"    Unknown:            {ct_unk:>8,}  ({_pct(ct_unk, ct_total)})")
    print(f"    Unique unknown:     {d['norm_city_unknown_unique']:>8,}")

    unknown_cities = d.get("norm_unknown_cities", {})
    if unknown_cities:
        limit = 100 if show_unknown else 20
        print()
        shown = list(unknown_cities.items())[:limit]
        for city, count in shown:
            norm = normalize_city_for_dedup(city)
            print(f"    {count:>5}x  {city!r:30s}  -> {norm!r}")
        remaining = len(unknown_cities) - len(shown)
        if remaining > 0:
            print(f"    ... and {remaining} more (use --unknown-cities)")

    # ── Dedup consistency ──
    print()
    raw = d["norm_raw_addresses"]
    keys = d["norm_unique_keys"]
    ratio = raw / keys if keys else 0
    print(f"  Dedup consistency:")
    print(f"    Geocodable addresses:     {raw:>8,}")
    print(f"    Unique dedup keys:        {keys:>8,}")
    print(f"    Collapse ratio:           {ratio:>7.2f}x")
    print(f"    Multi-raw keys:           {d['norm_multi_raw']:>8,}")
    print(f"    Cross-source matches:     {d['norm_cross_source']:>8,}")

    if verbose and d.get("_cross_source_samples"):
        print()
        print("  Cross-source match samples:")
        for k, entries in d["_cross_source_samples"].items():
            print(f"    {k}")
            for raw, city, src in entries[:3]:
                print(f"      [{src}] {raw} | {city}")

    print()


# ---------------------------------------------------------------------------
# Snapshot logging
# ---------------------------------------------------------------------------

def save_snapshot(data: dict):
    snapshot = {k: v for k, v in data.items() if not k.startswith("_")}
    snapshot["timestamp"] = datetime.now().isoformat(timespec="seconds")
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(snapshot, separators=(",", ":")) + "\n")
    print(f"Snapshot saved to {AUDIT_LOG_PATH}")


def show_history():
    if not AUDIT_LOG_PATH.exists():
        print("No audit history. Run with --log to save a snapshot.")
        return

    snapshots = []
    with open(AUDIT_LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                snapshots.append(json.loads(line))

    if not snapshots:
        print("No audit history.")
        return

    print()
    print(f"  {'Date':<20s}  {'HTML':>7s}  {'Parsed':>7s}  {'Geocod':>7s}  "
          f"{'Props':>7s}  {'Geo %':>6s}  {'Unk City':>8s}")
    print(f"  {'─' * 20}  {'─' * 7}  {'─' * 7}  {'─' * 7}  "
          f"{'─' * 7}  {'─' * 6}  {'─' * 8}")

    for s in snapshots:
        ts = s.get("timestamp", "?")[:19]
        pt = s.get("properties_total", 0)
        pg = s.get("properties_geocoded", 0)
        gpct = f"{pg / pt * 100:.1f}%" if pt else "-"
        print(f"  {ts:<20s}  {s.get('html_total', 0):>7,}  "
              f"{s.get('parsed_total', 0):>7,}  "
              f"{s.get('geocoded_rt_total', 0):>7,}  "
              f"{pt:>7,}  {gpct:>6s}  "
              f"{s.get('norm_city_unknown_unique', 0):>8,}")

    print()
    print(f"  {len(snapshots)} snapshots")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Address normalization audit")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--unknown-cities", action="store_true")
    parser.add_argument("--log", action="store_true", help="Save snapshot")
    parser.add_argument("--history", action="store_true", help="Show trend")
    args = parser.parse_args()

    if args.history:
        show_history()
        return

    global _KNOWN_MUNICIPALITIES
    _KNOWN_MUNICIPALITIES = _build_known_cities()
    print(f"Loaded {len(_KNOWN_MUNICIPALITIES):,} known city/community names")
    print("Scanning...\n")

    data = collect_all(verbose=args.verbose)
    print_report(data, verbose=args.verbose, show_unknown=args.unknown_cities)

    if args.log:
        save_snapshot(data)


if __name__ == "__main__":
    main()
