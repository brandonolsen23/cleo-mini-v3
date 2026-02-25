"""Targeted brand search across Ontario via Overpass API.

Fetches ALL branded POIs in Ontario in a single query, then filters to
the master brands list and matches to properties by address and proximity.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import re
from pathlib import Path

import httpx

from cleo.config import MASTER_BRANDS_CSV, PROPERTIES_PATH, DATA_DIR
from cleo.properties.registry import load_registry

logger = logging.getLogger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

OSM_BRANDS_PATH = DATA_DIR / "osm_brands.json"

# Overpass query: all branded POIs in Ontario
QUERY = """
[out:json][timeout:120];
area["name"="Ontario"]["admin_level"="4"]->.ontario;
(
  node["brand"](area.ontario);
  way["brand"](area.ontario);
);
out center tags;
"""

# Manual aliases: CSV brand name -> list of OSM brand names that should match.
# Only needed when normalization alone doesn't work.
_BRAND_ALIASES: dict[str, list[str]] = {
    "Beer Store": ["The Beer Store"],
    "Independant": ["Your Independent Grocer"],
    "Home Depot": ["The Home Depot"],
    "Dominos Pizza": ["Domino's"],
    "Halubut House": ["Halibut House"],
    "Ultrimar": ["Ultramar"],
    "Petro Can": ["Petro-Canada"],
    "Scotia Bank": ["Scotiabank"],
    "Baskin Robbins": ["Baskin-Robbins"],
    "Indigo / Chapters": ["Indigo", "Chapters"],
    "Pet Smart": ["PetSmart"],
    "Kelseys Original Roadhouse": ["Kelsey's"],
    "Montana's BBQ & Bar": ["Montana's"],
    "Milestones Grill & Bar": ["Milestones"],
    "Chipotle Mexican Grill": ["Chipotle"],
    "Mary Brown's Chicken": ["Mary Brown's"],
    "Popeyes Louisiana Kitchen": ["Popeyes"],
    "Guac": ["Guac Mexi Grill"],
    "Wimpy's Diner": ["Wimpy's"],
    "The Works": ["The Works Gourmet Burger Bistro", "The Works Craft Burgers & Beer"],
    "Applebees": ["Applebee's"],
    "Barburrito": ["BarBurrito"],
    "Real Canadian Superstore": ["Real Canadian Superstore"],
    "Valu-Mart": ["Valu-mart"],
    "Longos": ["Longo's"],
}


def _normalize(name: str) -> str:
    """Normalize brand name: uppercase, strip non-alphanumeric."""
    return re.sub(r'[^A-Z0-9]', '', name.upper())


def load_master_brands() -> dict[str, dict]:
    """Load master brands from CSV.

    Returns dict mapping normalized OSM brand name -> {csv_name, category}.
    Multiple normalized keys may point to the same CSV brand (via aliases).
    """
    if not MASTER_BRANDS_CSV.exists():
        logger.warning("Master brands CSV not found: %s", MASTER_BRANDS_CSV)
        return {}

    lookup: dict[str, dict] = {}

    with open(MASTER_BRANDS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            csv_name = row.get("Brand Name", "").strip()
            category = row.get("Category", "").strip()
            if not csv_name:
                continue

            info = {"csv_name": csv_name, "category": category}

            # Primary normalized key
            lookup[_normalize(csv_name)] = info

            # Aliases for this brand
            for alias in _BRAND_ALIASES.get(csv_name, []):
                lookup[_normalize(alias)] = info

    return lookup


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters."""
    R = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _normalize_street(s: str) -> str:
    """Normalize a street name for comparison."""
    s = s.upper().strip()
    for full, abbr in [
        ("STREET", "ST"), ("AVENUE", "AVE"), ("DRIVE", "DR"),
        ("ROAD", "RD"), ("BOULEVARD", "BLVD"), ("CRESCENT", "CRES"),
        ("COURT", "CT"), ("PLACE", "PL"), ("LANE", "LN"),
        ("CIRCLE", "CIR"), ("HIGHWAY", "HWY"), ("PARKWAY", "PKWY"),
        ("TERRACE", "TERR"), ("TRAIL", "TRL"),
        ("NORTH", "N"), ("SOUTH", "S"), ("EAST", "E"), ("WEST", "W"),
    ]:
        s = re.sub(rf'\b{full}\b', abbr, s)
        s = re.sub(rf'\b{abbr}\.\b', abbr, s)
    return s


def _parse_element(el: dict) -> dict | None:
    """Parse an Overpass element into a brand location record."""
    tags = el.get("tags", {})
    brand = tags.get("brand")
    name = tags.get("name", brand)
    if not brand:
        return None

    if el["type"] == "node":
        lat, lng = el.get("lat"), el.get("lon")
    else:
        center = el.get("center", {})
        lat, lng = center.get("lat"), center.get("lon")

    if lat is None or lng is None:
        return None

    return {
        "osm_id": f"{el['type']}/{el['id']}",
        "brand": brand,
        "name": name or brand,
        "lat": lat,
        "lng": lng,
        "address": tags.get("addr:street", ""),
        "housenumber": tags.get("addr:housenumber", ""),
        "city": tags.get("addr:city", ""),
        "postal_code": tags.get("addr:postcode", ""),
        "phone": tags.get("phone", ""),
        "website": tags.get("website", ""),
        "category": None,
    }


def fetch_all_branded_pois() -> list[dict]:
    """Fetch all branded POIs in Ontario from Overpass. Single query, ~60s."""
    for url in OVERPASS_URLS:
        try:
            logger.info("Querying Overpass (%s) for all branded POIs in Ontario...", url)
            client = httpx.Client(timeout=180)
            resp = client.post(url, data={"data": QUERY})
            resp.raise_for_status()
            data = resp.json()
            client.close()

            elements = data.get("elements", [])
            logger.info("Got %d branded POIs from Overpass", len(elements))

            results = []
            for el in elements:
                parsed = _parse_element(el)
                if parsed:
                    results.append(parsed)
            return results
        except Exception as e:
            logger.warning("Overpass server %s failed: %s", url, e)
            continue

    raise RuntimeError("All Overpass servers failed")


def _grid_key(lat: float, lng: float, cell_deg: float = 0.01) -> tuple[int, int]:
    """Return grid cell index for a lat/lng. ~1km cells at Ontario latitudes."""
    return (int(lat / cell_deg), int(lng / cell_deg))


def _nearby_cells(lat: float, lng: float, cell_deg: float = 0.01) -> list[tuple[int, int]]:
    """Return the 9 grid cells around a point (self + 8 neighbors)."""
    cy, cx = _grid_key(lat, lng, cell_deg)
    return [(cy + dy, cx + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]


def _extract_street_number(address: str) -> tuple[str, str]:
    """Extract street number and street name from address like '1063 Talbot St'.

    Also handles '1014 1/2 Talbot St' → ('1014', 'TALBOT ST').
    """
    a = address.strip()
    # Handle "1014 1/2 Talbot St" pattern
    m = re.match(r'^(\d+)\s+\d+/\d+\s+(.+)', a)
    if m:
        return m.group(1).upper(), _normalize_street(m.group(2))
    # Standard "1063 Talbot St" or "1014.5 Talbot St"
    m = re.match(r'^(\d+[\w.-]*)\s+(.+)', a)
    if m:
        return m.group(1).upper(), _normalize_street(m.group(2))
    return "", _normalize_street(a)


def _parse_num(s: str) -> int | None:
    """Parse a street number like '1014', '1014.5', '1014A' into an integer."""
    m = re.match(r'(\d+)', s)
    return int(m.group(1)) if m else None


def match_to_properties(
    pois: list[dict],
    max_distance_m: float = 150,
) -> dict:
    """Match branded POIs to properties by address + proximity.

    Uses a grid-based spatial index for fast proximity lookup.
    Only returns confirmed (address match) entries.
    """
    reg = load_registry(PROPERTIES_PATH)
    props = reg.get("properties", {})

    # Build spatial grid index for fast proximity lookup
    grid: dict[tuple[int, int], list[tuple[str, dict]]] = {}
    # Build address lookup: (normalized_street, city) -> [(pid, prop, street_num)]
    addr_index: dict[tuple[str, str], list[tuple[str, dict, str]]] = {}
    # Street-only index for POIs missing city: normalized_street -> [(pid, prop, num)]
    street_index: dict[str, list[tuple[str, dict, str]]] = {}

    geocoded_count = 0
    for pid, prop in props.items():
        if prop.get("lat") is None or prop.get("lng") is None:
            continue
        geocoded_count += 1

        # Add to spatial grid
        cell = _grid_key(prop["lat"], prop["lng"])
        grid.setdefault(cell, []).append((pid, prop))

        # Add to address indexes
        addr = prop.get("address", "")
        city = prop.get("city", "")
        if addr:
            num, street = _extract_street_number(addr)
            street_index.setdefault(street, []).append((pid, prop, num))
            if city:
                key = (street, city.upper().strip())
                addr_index.setdefault(key, []).append((pid, prop, num))

    logger.info("Matching %d POIs against %d properties (grid: %d cells)...",
                len(pois), geocoded_count, len(grid))

    result: dict[str, dict] = {}

    for poi in pois:
        poi_addr = poi.get("address", "")
        poi_num = poi.get("housenumber", "")
        poi_city = poi.get("city", "")
        poi_lat, poi_lng = poi["lat"], poi["lng"]

        matched_pid = None

        # Try address match: street + city, or street-only if no city
        if poi_addr:
            poi_street = _normalize_street(poi_addr)

            if poi_city:
                candidates = addr_index.get((poi_street, poi_city.upper().strip()), [])
            else:
                candidates = street_index.get(poi_street, [])

            # Pick the best candidate by street number match + proximity
            best_score = 999999
            for pid, prop, prop_num in candidates:
                dist = _haversine_m(poi_lat, poi_lng, prop["lat"], prop["lng"])
                if dist > 500:
                    continue
                # Score: prefer exact number match, then close numbers, then just street
                num_score = dist  # base score is distance
                if poi_num and prop_num:
                    poi_n = _parse_num(poi_num)
                    prop_n = _parse_num(prop_num)
                    if poi_n is not None and prop_n is not None:
                        if poi_n == prop_n:
                            num_score = 0  # exact match, best possible
                        else:
                            num_score = abs(poi_n - prop_n) * 10  # penalize distance
                if num_score < best_score:
                    best_score = num_score
                    matched_pid = pid

        # No proximity fallback — only address-confirmed matches
        if matched_pid:
            entry = result.setdefault(matched_pid, [])
            entry.append({**poi, "match_type": "confirmed"})

    return result


def run_brand_search(dry_run: bool = False) -> dict:
    """Full pipeline: fetch branded POIs, filter to master brands, match to properties."""
    master = load_master_brands()
    logger.info("Master brands: %d entries (from CSV + aliases)", len(master))

    if dry_run:
        # Show which CSV brands have aliases
        csv_names = sorted({v["csv_name"] for v in master.values()})
        return {"dry_run": True, "master_brands": len(csv_names)}

    # Fetch all branded POIs in Ontario
    all_pois = fetch_all_branded_pois()

    # Filter to our master brands
    filtered = []
    brand_counts: dict[str, int] = {}
    for poi in all_pois:
        osm_norm = _normalize(poi["brand"])
        info = master.get(osm_norm)
        if info:
            poi["tracked_brand"] = info["csv_name"]
            poi["category"] = info["category"]
            filtered.append(poi)
            brand_counts[info["csv_name"]] = brand_counts.get(info["csv_name"], 0) + 1

    csv_brand_count = len({v["csv_name"] for v in master.values()})
    logger.info(
        "Filtered to %d POIs matching %d of %d master brands (of %d total POIs)",
        len(filtered), len(brand_counts), csv_brand_count, len(all_pois),
    )

    # Match to properties
    matches = match_to_properties(filtered)
    total_matches = sum(len(tenants) for tenants in matches.values())

    # Save results
    save_data = {
        "meta": {
            "total_pois_fetched": len(all_pois),
            "master_brands": csv_brand_count,
            "brands_matched_in_osm": len(brand_counts),
            "filtered_pois": len(filtered),
            "properties_with_matches": len(matches),
            "total_matches": total_matches,
            "brand_counts": dict(sorted(brand_counts.items(), key=lambda x: -x[1])),
        },
        "properties": {
            pid: {"confirmed": tenants}
            for pid, tenants in matches.items()
        },
    }

    OSM_BRANDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    OSM_BRANDS_PATH.write_text(
        json.dumps(save_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Saved to %s", OSM_BRANDS_PATH)

    return {
        "total_pois_fetched": len(all_pois),
        "master_brands": csv_brand_count,
        "brands_found_in_osm": len(brand_counts),
        "filtered_pois": len(filtered),
        "properties_with_matches": len(matches),
        "total_matches": total_matches,
        "top_brands": dict(list(sorted(brand_counts.items(), key=lambda x: -x[1]))[:25]),
    }


def refine_property_coords(dry_run: bool = False) -> dict:
    """Refine property coordinates using confirmed tenant OSM locations.

    For each property with confirmed brand tenants, computes the centroid
    of tenant coordinates and stores as osm_lat/osm_lng on the property.
    """
    if not OSM_BRANDS_PATH.exists():
        return {"error": "No brand search data. Run: cleo osm-brands"}

    brand_data = json.loads(OSM_BRANDS_PATH.read_text(encoding="utf-8"))
    reg = load_registry(PROPERTIES_PATH)
    props = reg.get("properties", {})

    updated = 0
    skipped = 0

    # Clear stale OSM coords from previous runs
    if not dry_run:
        for prop in props.values():
            prop.pop("osm_lat", None)
            prop.pop("osm_lng", None)
            prop.pop("osm_tenant_count", None)

    for pid, entry in brand_data.get("properties", {}).items():
        tenants = entry.get("confirmed", [])
        if not tenants:
            continue

        if pid not in props:
            skipped += 1
            continue

        prop = props[pid]
        prop_num = _parse_num(_extract_street_number(prop.get("address", ""))[0])

        # Only use tenants with close address numbers for centroid
        # (tenants on the same street but far away shouldn't skew the pin)
        close_tenants = []
        for t in tenants:
            t_num = _parse_num(t.get("housenumber", ""))
            if prop_num is not None and t_num is not None:
                if abs(prop_num - t_num) > 10:
                    continue  # too far along the street
            close_tenants.append(t)

        if not close_tenants:
            continue

        # Compute centroid of close tenant locations
        lats = [t["lat"] for t in close_tenants]
        lngs = [t["lng"] for t in close_tenants]
        centroid_lat = sum(lats) / len(lats)
        centroid_lng = sum(lngs) / len(lngs)

        if not dry_run:
            prop["osm_lat"] = round(centroid_lat, 7)
            prop["osm_lng"] = round(centroid_lng, 7)
            prop["osm_tenant_count"] = len(close_tenants)

        updated += 1

    if not dry_run:
        PROPERTIES_PATH.write_text(
            json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    logger.info("Coordinate refinement: %d properties updated, %d skipped", updated, skipped)
    return {
        "properties_refined": updated,
        "skipped": skipped,
        "dry_run": dry_run,
    }
