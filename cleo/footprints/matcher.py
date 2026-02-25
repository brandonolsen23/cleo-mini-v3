"""Spatial matching engine: links properties and brand POIs to building footprints.

Matching cascade:
1. Footprint containment (point-in-polygon) — highest confidence
2. Footprint proximity (30m) — handles coordinate drift
3. Address-based matching — existing brands/match.py logic (unchanged)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from cleo.config import (
    BRAND_MATCHES_PATH,
    BRANDS_DATA_DIR,
    FOOTPRINTS_MATCHES_PATH,
    PROPERTIES_PATH,
)
from cleo.footprints.spatial import FootprintIndex

logger = logging.getLogger(__name__)

PROXIMITY_FALLBACK_M = 100


def _load_brand_pois() -> list[dict]:
    """Collect brand POI locations from brand_matches.json and scraper data.

    Returns list of dicts with at minimum: brand, lat, lng, prop_id (if matched).
    """
    pois: list[dict] = []

    # From brand_matches.json (existing address-based matches)
    if BRAND_MATCHES_PATH.exists():
        data = json.loads(BRAND_MATCHES_PATH.read_text(encoding="utf-8"))
        for prop_id, match_info in data.items():
            if isinstance(match_info, dict):
                brands = match_info.get("brands", [])
                for b in brands:
                    if isinstance(b, dict) and b.get("lat") and b.get("lng"):
                        pois.append({
                            "brand": b.get("brand", b.get("name", "")),
                            "lat": b["lat"],
                            "lng": b["lng"],
                            "prop_id": prop_id,
                            "source": "brand_match",
                        })
            elif isinstance(match_info, list):
                for b in match_info:
                    if isinstance(b, dict) and b.get("lat") and b.get("lng"):
                        pois.append({
                            "brand": b.get("brand", b.get("name", "")),
                            "lat": b["lat"],
                            "lng": b["lng"],
                            "prop_id": prop_id,
                            "source": "brand_match",
                        })

    # From scraper data files
    if BRANDS_DATA_DIR.exists():
        for f in sorted(BRANDS_DATA_DIR.glob("*.json")):
            try:
                stores = json.loads(f.read_text(encoding="utf-8"))
                brand_name = f.stem.replace("_", " ").title()
                for store in stores:
                    if isinstance(store, dict) and store.get("lat") and store.get("lng"):
                        pois.append({
                            "brand": store.get("brand", brand_name),
                            "lat": store["lat"],
                            "lng": store["lng"],
                            "source": "scraper",
                        })
            except (json.JSONDecodeError, TypeError):
                continue

    return pois


def match_properties(index: FootprintIndex, dry_run: bool = False) -> dict:
    """Match properties to building footprints.

    Returns dict with property_footprints and stats.
    """
    if not PROPERTIES_PATH.exists():
        return {"error": "No properties.json"}

    reg = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
    props = reg.get("properties", {})

    property_footprints: dict[str, dict] = {}
    contained = 0
    proximate = 0
    unmatched = 0
    no_coords = 0

    for pid, prop in props.items():
        lat, lng = prop.get("lat"), prop.get("lng")
        if lat is None or lng is None:
            no_coords += 1
            continue

        # Try containment first
        fps = index.find_containing(lat, lng)
        if fps:
            fp_id = fps[0]
            property_footprints[pid] = {
                "footprint_id": fp_id,
                "method": "containment",
                "distance_m": 0,
            }
            contained += 1
            continue

        # Fallback: nearest within 30m
        fp_id = index.find_nearest(lat, lng, max_m=PROXIMITY_FALLBACK_M)
        if fp_id:
            property_footprints[pid] = {
                "footprint_id": fp_id,
                "method": "proximity",
                "distance_m": PROXIMITY_FALLBACK_M,
            }
            proximate += 1
        else:
            unmatched += 1

    return {
        "property_footprints": property_footprints,
        "stats": {
            "total_properties": len(props),
            "no_coords": no_coords,
            "contained": contained,
            "proximate": proximate,
            "unmatched": unmatched,
            "match_rate_pct": round(
                100 * (contained + proximate) / max(len(props) - no_coords, 1), 1
            ),
        },
    }


def match_brands(index: FootprintIndex, property_footprints: dict[str, dict]) -> dict:
    """Match brand POIs to footprints and cross-reference with properties.

    Brands that share a footprint_id with a property are spatially matched.
    """
    pois = _load_brand_pois()
    if not pois:
        return {"brand_spatial_matches": [], "stats": {"brands_total": 0}}

    # Build reverse lookup: footprint_id -> prop_id
    fp_to_prop: dict[str, str] = {}
    for pid, info in property_footprints.items():
        fp_id = info.get("footprint_id")
        if fp_id:
            fp_to_prop[fp_id] = pid

    spatial_matches: list[dict] = []
    brands_matched = 0
    brands_no_fp = 0
    brands_fp_no_prop = 0

    for poi in pois:
        lat, lng = poi.get("lat"), poi.get("lng")
        if lat is None or lng is None:
            continue

        # Try containment
        fps = index.find_containing(lat, lng)
        if not fps:
            fp_id = index.find_nearest(lat, lng, max_m=PROXIMITY_FALLBACK_M)
            fps = [fp_id] if fp_id else []

        if not fps:
            brands_no_fp += 1
            continue

        fp_id = fps[0]
        prop_id = fp_to_prop.get(fp_id)
        if prop_id:
            spatial_matches.append({
                "brand": poi.get("brand", ""),
                "footprint_id": fp_id,
                "prop_id": prop_id,
                "method": "spatial",
                "lat": lat,
                "lng": lng,
            })
            brands_matched += 1
        else:
            brands_fp_no_prop += 1

    return {
        "brand_spatial_matches": spatial_matches,
        "stats": {
            "brands_total": len(pois),
            "brands_spatially_matched": brands_matched,
            "brands_no_footprint": brands_no_fp,
            "brands_footprint_no_property": brands_fp_no_prop,
        },
    }


def run_matching(dry_run: bool = False) -> dict:
    """Full matching pipeline: properties + brands -> footprints.

    Saves results to FOOTPRINTS_MATCHES_PATH.
    """
    index = FootprintIndex()
    index.load()

    if index.count == 0:
        return {"error": "No footprints loaded. Run 'cleo footprints' first."}

    # Match properties
    prop_result = match_properties(index, dry_run=dry_run)
    property_footprints = prop_result.get("property_footprints", {})

    # Match brands
    brand_result = match_brands(index, property_footprints)

    result = {
        "property_footprints": property_footprints,
        "brand_spatial_matches": brand_result.get("brand_spatial_matches", []),
        "stats": {
            **prop_result.get("stats", {}),
            **brand_result.get("stats", {}),
        },
    }

    if not dry_run:
        tmp = FOOTPRINTS_MATCHES_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        tmp.rename(FOOTPRINTS_MATCHES_PATH)
        logger.info("Saved matches to %s", FOOTPRINTS_MATCHES_PATH)

    return result


def match_status() -> dict:
    """Return current matching stats from disk."""
    if not FOOTPRINTS_MATCHES_PATH.exists():
        return {"matched": False}

    data = json.loads(FOOTPRINTS_MATCHES_PATH.read_text(encoding="utf-8"))
    return {
        "matched": True,
        "property_footprints": len(data.get("property_footprints", {})),
        "brand_spatial_matches": len(data.get("brand_spatial_matches", [])),
        "stats": data.get("stats", {}),
    }
