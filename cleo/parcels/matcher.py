"""Brand POI -> parcel -> property matching.

Uses the ParcelIndex for point-in-polygon containment to assign
brand store locations to parcels, then cross-references with
the property-to-parcel mapping to link brands to properties.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from cleo.config import (
    BRAND_MATCHES_PATH,
    BRANDS_DATA_DIR,
    PARCELS_MATCHES_PATH,
)
from cleo.parcels.spatial import ParcelIndex
from cleo.parcels.store import ParcelStore

logger = logging.getLogger(__name__)


def _load_brand_pois() -> list[dict]:
    """Collect brand POI locations from scraper data files."""
    pois: list[dict] = []

    if not BRANDS_DATA_DIR.exists():
        return pois

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
                        "address": store.get("address", ""),
                        "city": store.get("city", ""),
                        "source": "scraper",
                    })
        except (json.JSONDecodeError, TypeError):
            continue

    return pois


def match_brands_to_parcels(dry_run: bool = False) -> dict:
    """Match brand POIs to parcels, then cross-reference with properties.

    For each brand POI with coordinates:
    1. Query ParcelIndex for containment
    2. If found, check if that parcel is linked to a property
    3. Record the brand -> parcel -> property chain

    Returns dict with matches and stats.
    """
    index = ParcelIndex()
    index.load()

    if index.count == 0:
        return {"error": "No parcels loaded. Run 'cleo parcels --harvest' first."}

    store = ParcelStore()
    prop_to_pcl = store.property_to_parcel

    # Build reverse: pcl_id -> prop_id
    pcl_to_prop: dict[str, str] = {}
    for pid, pcl_id in prop_to_pcl.items():
        pcl_to_prop[pcl_id] = pid

    pois = _load_brand_pois()
    if not pois:
        return {"error": "No brand POI data found in brands/data/"}

    matches: list[dict] = []
    matched_to_parcel = 0
    matched_to_property = 0
    no_parcel = 0

    for poi in pois:
        lat, lng = poi["lat"], poi["lng"]

        # Try containment
        pcl_ids = index.find_containing(lat, lng)
        if not pcl_ids:
            # Fallback: nearest within 30m
            nearest = index.find_nearest(lat, lng, max_m=30)
            pcl_ids = [nearest] if nearest else []

        if not pcl_ids:
            no_parcel += 1
            continue

        pcl_id = pcl_ids[0]
        matched_to_parcel += 1

        prop_id = pcl_to_prop.get(pcl_id)
        match_entry = {
            "brand": poi["brand"],
            "parcel_id": pcl_id,
            "lat": lat,
            "lng": lng,
            "address": poi.get("address", ""),
            "city": poi.get("city", ""),
        }

        if prop_id:
            match_entry["prop_id"] = prop_id
            matched_to_property += 1

        matches.append(match_entry)

    result = {
        "matches": matches,
        "stats": {
            "total_pois": len(pois),
            "matched_to_parcel": matched_to_parcel,
            "matched_to_property": matched_to_property,
            "no_parcel": no_parcel,
        },
    }

    if not dry_run:
        tmp = PARCELS_MATCHES_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        tmp.rename(PARCELS_MATCHES_PATH)
        logger.info("Saved %d brand-parcel matches to %s", len(matches), PARCELS_MATCHES_PATH)

    return result


def match_status() -> dict:
    """Return current matching stats from disk."""
    if not PARCELS_MATCHES_PATH.exists():
        return {"matched": False}

    data = json.loads(PARCELS_MATCHES_PATH.read_text(encoding="utf-8"))
    stats = data.get("stats", {})
    return {
        "matched": True,
        "brands_matched": stats.get("matched_to_property", 0),
        "total_pois": stats.get("total_pois", 0),
    }
