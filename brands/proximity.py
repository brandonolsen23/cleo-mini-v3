"""Proximity-based brand-to-property matching.

Uses spatial grid for fast nearest-neighbor lookup. Matches brand stores
to properties within a configurable distance threshold (default 150m).
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BRANDS_DATA_DIR = Path(__file__).resolve().parent / "data"
PROPERTIES_PATH = DATA_DIR / "properties.json"
BRAND_MATCHES_PATH = DATA_DIR / "brand_matches.json"
BRAND_PROXIMITY_PATH = DATA_DIR / "brand_proximity.json"

# Grid cell size in degrees (~1.1km at 43N latitude)
GRID_CELL_SIZE = 0.01


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters between two lat/lng points."""
    R = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _grid_key(lat: float, lng: float) -> tuple[int, int]:
    """Convert lat/lng to grid cell key."""
    return (int(lat / GRID_CELL_SIZE), int(lng / GRID_CELL_SIZE))


def build_property_grid(
    properties: dict,
    coord_store=None,
) -> dict[tuple[int, int], list[tuple[str, float, float]]]:
    """Build spatial grid from property registry.

    Each cell maps to a list of (prop_id, lat, lng).
    Uses coordinate store for best coords, falls back to property lat/lng.
    """
    grid: dict[tuple[int, int], list[tuple[str, float, float]]] = defaultdict(list)

    for pid, prop in properties.items():
        lat, lng = None, None

        # Try coordinate store first (best multi-provider coords)
        if coord_store:
            addr = prop.get("address", "")
            city = prop.get("city", "")
            if addr and city:
                # Try the address format used in geocode cache (with province)
                province = prop.get("province", "ONTARIO")
                postal = prop.get("postal_code", "")
                # Build key matching geocode_cache format
                parts = [addr, city, province]
                if postal:
                    parts.append(postal)
                addr_key = ", ".join(parts)
                coords = coord_store.best_coords(addr_key)
                if coords:
                    lat, lng = coords

        # Fall back to property's own coordinates
        if lat is None:
            lat = prop.get("lat")
            lng = prop.get("lng")

        if lat is not None and lng is not None:
            key = _grid_key(lat, lng)
            grid[key].append((pid, lat, lng))

    return dict(grid)


def find_nearby(
    lat: float,
    lng: float,
    grid: dict[tuple[int, int], list[tuple[str, float, float]]],
    threshold_m: float = 150,
) -> list[tuple[str, float]]:
    """Find properties within threshold_m meters of (lat, lng).

    Returns list of (prop_id, distance_m) sorted by distance.
    """
    center = _grid_key(lat, lng)
    results: list[tuple[str, float]] = []

    # Check 3x3 neighborhood of grid cells
    for di in range(-1, 2):
        for dj in range(-1, 2):
            cell = (center[0] + di, center[1] + dj)
            for pid, plat, plng in grid.get(cell, []):
                dist = haversine_m(lat, lng, plat, plng)
                if dist <= threshold_m:
                    results.append((pid, dist))

    results.sort(key=lambda x: x[1])
    return results


def _load_already_matched() -> set[tuple[str, str]]:
    """Load (brand, address) pairs already in brand_matches.json."""
    matched = set()
    if BRAND_MATCHES_PATH.exists():
        data = json.loads(BRAND_MATCHES_PATH.read_text(encoding="utf-8"))
        for entries in data.values():
            for e in entries:
                matched.add((e.get("brand", "").upper(), e.get("address", "").upper()))
    return matched


def _load_brand_stores() -> list[dict]:
    """Load all brand store JSON files."""
    stores = []
    for path in sorted(BRANDS_DATA_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        stores.extend(data)
    return stores


def run_proximity_match(
    threshold_m: float = 150,
    coord_store=None,
) -> dict:
    """Run proximity-based brand-to-property matching.

    Returns result dict with matches and stats, also writes brand_proximity.json.
    """
    from coordinates import CoordinateStore

    if coord_store is None:
        coord_store = CoordinateStore()

    # Load properties
    reg = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
    properties = reg.get("properties", {})

    # Build spatial grid
    grid = build_property_grid(properties, coord_store)
    grid_props = sum(len(v) for v in grid.values())
    print(f"Property grid: {grid_props} geocoded properties in {len(grid)} cells")

    # Load brand stores
    stores = _load_brand_stores()

    # Skip stores already matched by address matching
    already_matched = _load_already_matched()

    matches: list[dict] = []
    no_coords = 0
    already_done = 0
    no_nearby = 0

    for store in stores:
        brand = store.get("brand", "")
        addr = store.get("address", "")
        city = store.get("city", "")

        # Skip if already matched by address
        if (brand.upper(), addr.upper()) in already_matched:
            already_done += 1
            continue

        # Get best coordinates for this store
        lat, lng = None, None
        province = store.get("province", "ON")

        # Try coordinate store
        if addr and city:
            addr_key = f"{addr}, {city}, {province}"
            coords = coord_store.best_coords(addr_key)
            if coords:
                lat, lng = coords

        # Fall back to store's own coordinates
        if lat is None:
            lat = store.get("lat")
            lng = store.get("lng")

        if lat is None or lng is None:
            no_coords += 1
            continue

        # Find nearby properties
        nearby = find_nearby(lat, lng, grid, threshold_m)
        if not nearby:
            no_nearby += 1
            continue

        best_pid, best_dist = nearby[0]
        prop = properties[best_pid]
        matches.append({
            "brand": brand,
            "store_name": store.get("store_name", ""),
            "store_address": addr,
            "store_city": city,
            "store_lat": lat,
            "store_lng": lng,
            "prop_id": best_pid,
            "prop_address": prop.get("address", ""),
            "prop_city": prop.get("city", ""),
            "distance_m": round(best_dist, 1),
            "alternatives": len(nearby) - 1,
        })

    # Write results
    output = {
        "threshold_m": threshold_m,
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "stats": {
            "total_stores": len(stores),
            "already_matched": already_done,
            "no_coordinates": no_coords,
            "no_nearby_property": no_nearby,
            "proximity_matches": len(matches),
        },
        "matches": matches,
    }

    with open(BRAND_PROXIMITY_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return output
