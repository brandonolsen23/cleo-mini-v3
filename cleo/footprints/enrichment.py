"""Enrich properties.json with building footprint data.

Adds footprint_id, footprint_area_sqm, footprint_building_type,
footprint_match_method fields, and **snaps property coordinates** to the
best available location so that map pins land on the actual building
rather than in an adjacent parking lot.

Coordinate priority (highest to lowest):
1. Brand POI coords from scraper data — store locators place pins on buildings
2. Building footprint centroid for containment matches
3. Original geocoded address coords (no snap)
"""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path

from cleo.config import (
    BRAND_MATCHES_PATH,
    BRANDS_DATA_DIR,
    FOOTPRINTS_MATCHES_PATH,
    PROPERTIES_PATH,
)
from cleo.footprints.spatial import FootprintIndex

logger = logging.getLogger(__name__)


def _norm_addr(s: str) -> str:
    """Normalize address for matching: lowercase, strip punctuation, collapse whitespace."""
    s = s.lower().strip()
    s = s.replace(".", "").replace(",", "")
    s = re.sub(r"\s+", " ", s)
    # Normalize common abbreviations
    s = re.sub(r"\bstreet\b", "st", s)
    s = re.sub(r"\bavenue\b", "ave", s)
    s = re.sub(r"\broad\b", "rd", s)
    s = re.sub(r"\bdrive\b", "dr", s)
    s = re.sub(r"\bboulevard\b", "blvd", s)
    return s


def _norm_city(s: str) -> str:
    """Normalize city for matching: lowercase, strip punctuation."""
    s = s.lower().strip()
    s = s.replace(".", "").replace(",", "")
    s = re.sub(r"\s+", " ", s)
    return s


def _build_brand_poi_coords() -> dict[str, tuple[float, float]]:
    """Build prop_id -> (lat, lng) from brand scraper data.

    For properties with brand matches, finds the brand's POI coordinates
    from scraper data files. Store locator coordinates are typically more
    accurate than geocoded addresses because they place pins directly on
    the building.
    """
    if not BRAND_MATCHES_PATH.exists():
        return {}

    brand_matches = json.loads(BRAND_MATCHES_PATH.read_text(encoding="utf-8"))

    # Load all brand scraper data into a lookup:
    # (brand_lower, addr_norm, city_norm) -> (lat, lng)
    scraper_lookup: dict[tuple[str, str, str], tuple[float, float]] = {}
    if BRANDS_DATA_DIR.exists():
        for f in sorted(BRANDS_DATA_DIR.glob("*.json")):
            try:
                stores = json.loads(f.read_text(encoding="utf-8"))
                for store in stores:
                    if isinstance(store, dict) and store.get("lat") and store.get("lng"):
                        key = (
                            store.get("brand", "").lower().strip(),
                            _norm_addr(store.get("address", "")),
                            _norm_city(store.get("city", "")),
                        )
                        scraper_lookup[key] = (store["lat"], store["lng"])
            except (json.JSONDecodeError, TypeError):
                continue

    # Match brand_matches entries to scraper coords
    result: dict[str, tuple[float, float]] = {}
    for pid, entries in brand_matches.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            key = (
                entry.get("brand", "").lower().strip(),
                _norm_addr(entry.get("address", "")),
                _norm_city(entry.get("city", "")),
            )
            coords = scraper_lookup.get(key)
            if coords:
                result[pid] = coords
                break  # Use first matching brand's coords

    return result


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def enrich_properties(dry_run: bool = False, snap_coords: bool = True) -> dict:
    """Add footprint fields to properties.json and snap coords to buildings.

    Reads matches from FOOTPRINTS_MATCHES_PATH and adds footprint metadata
    to each matched property. When snap_coords=True (default), also moves
    the property's lat/lng to the matched building footprint centroid so
    that map pins land on the actual building.

    Returns:
        Summary dict with counts.
    """
    if not FOOTPRINTS_MATCHES_PATH.exists():
        return {"error": "No matches file. Run 'cleo footprint-match' first."}
    if not PROPERTIES_PATH.exists():
        return {"error": "No properties.json."}

    matches = json.loads(FOOTPRINTS_MATCHES_PATH.read_text(encoding="utf-8"))
    property_footprints = matches.get("property_footprints", {})

    reg = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
    props = reg.get("properties", {})

    # Load spatial index for area calculation and building type lookup
    index = FootprintIndex()
    index.load()

    # Build brand POI coords lookup: prop_id -> (lat, lng) from scraper data
    brand_poi_coords = _build_brand_poi_coords() if snap_coords else {}
    logger.info("Found brand POI coords for %d properties", len(brand_poi_coords))

    enriched = 0
    cleared = 0
    snapped_brand = 0
    snapped_centroid = 0
    snap_distances: list[float] = []

    # First, clear stale footprint fields from all properties
    for prop in props.values():
        had = "footprint_id" in prop
        prop.pop("footprint_id", None)
        prop.pop("footprint_area_sqm", None)
        prop.pop("footprint_building_type", None)
        prop.pop("footprint_match_method", None)
        prop.pop("footprint_snap_source", None)
        # Restore original coords if previously snapped
        if "pre_snap_lat" in prop:
            prop["lat"] = prop.pop("pre_snap_lat")
            prop["lng"] = prop.pop("pre_snap_lng")
        else:
            prop.pop("pre_snap_lat", None)
            prop.pop("pre_snap_lng", None)
        if had:
            cleared += 1

    # Apply matches
    for pid, match_info in property_footprints.items():
        if pid not in props:
            continue

        fp_id = match_info.get("footprint_id")
        method = match_info.get("method", "")
        if not fp_id:
            continue

        prop = props[pid]
        prop["footprint_id"] = fp_id
        prop["footprint_match_method"] = method

        # Get area
        area = index.get_area_sqm(fp_id)
        if area is not None:
            prop["footprint_area_sqm"] = area

        # Get building type from OSM enrichment
        feat_props = index.get_feature(fp_id)
        if feat_props:
            btype = feat_props.get("building_type", "")
            if btype:
                prop["footprint_building_type"] = btype

        # --- Coordinate snapping (priority order) ---
        if snap_coords and prop.get("lat") is not None:
            old_lat, old_lng = prop["lat"], prop["lng"]
            snap_lat, snap_lng = None, None
            snap_source = None

            # Priority 1: Brand POI coords from scraper data
            # Store locator coordinates land directly on the building.
            # Also re-match footprint using brand coords for better accuracy.
            # Cap at 500m to filter wrong-store matches (same brand, wrong city).
            if pid in brand_poi_coords:
                blat, blng = brand_poi_coords[pid]
                brand_dist = _haversine_m(old_lat, old_lng, blat, blng)
                if brand_dist <= 500:
                    snap_lat, snap_lng = blat, blng
                    snap_source = "brand_poi"

                # Re-match footprint using brand coords (more accurate)
                fps = index.find_containing(blat, blng)
                if fps:
                    prop["footprint_id"] = fps[0]
                    prop["footprint_match_method"] = "brand_containment"
                    # Update area/type for new footprint
                    new_area = index.get_area_sqm(fps[0])
                    if new_area is not None:
                        prop["footprint_area_sqm"] = new_area
                    new_feat = index.get_feature(fps[0])
                    if new_feat:
                        btype = new_feat.get("building_type", "")
                        if btype:
                            prop["footprint_building_type"] = btype

            # Priority 2: Building centroid for containment matches only
            elif method == "containment" and feat_props:
                centroid_lat = feat_props.get("centroid_lat")
                centroid_lng = feat_props.get("centroid_lng")
                if centroid_lat is not None and centroid_lng is not None:
                    snap_lat, snap_lng = centroid_lat, centroid_lng
                    snap_source = "footprint_centroid"

            # Apply snap
            if snap_lat is not None and snap_lng is not None:
                dist = _haversine_m(old_lat, old_lng, snap_lat, snap_lng)
                prop["pre_snap_lat"] = old_lat
                prop["pre_snap_lng"] = old_lng
                prop["lat"] = round(snap_lat, 7)
                prop["lng"] = round(snap_lng, 7)
                prop["footprint_snap_source"] = snap_source
                snap_distances.append(dist)
                if snap_source == "brand_poi":
                    snapped_brand += 1
                else:
                    snapped_centroid += 1

        enriched += 1

    # Also snap properties that have brand POI coords but NO footprint match
    # (brand coords are still better than geocoded addresses)
    for pid, (blat, blng) in brand_poi_coords.items():
        if pid not in props or pid in property_footprints:
            continue
        prop = props[pid]
        if prop.get("lat") is None:
            continue
        old_lat, old_lng = prop["lat"], prop["lng"]
        dist = _haversine_m(old_lat, old_lng, blat, blng)
        if dist > 500:
            continue  # Wrong-store match (same brand, wrong city)
        prop["pre_snap_lat"] = old_lat
        prop["pre_snap_lng"] = old_lng
        prop["lat"] = round(blat, 7)
        prop["lng"] = round(blng, 7)
        prop["footprint_snap_source"] = "brand_poi"
        snapped_brand += 1
        snap_distances.append(dist)

        # Try to find a footprint at the brand coords
        fps = index.find_containing(blat, blng)
        if fps:
            prop["footprint_id"] = fps[0]
            prop["footprint_match_method"] = "brand_containment"
            area = index.get_area_sqm(fps[0])
            if area is not None:
                prop["footprint_area_sqm"] = area
            feat = index.get_feature(fps[0])
            if feat:
                btype = feat.get("building_type", "")
                if btype:
                    prop["footprint_building_type"] = btype

    coords_snapped = snapped_brand + snapped_centroid

    if not dry_run:
        tmp = PROPERTIES_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(reg, f, indent=2, ensure_ascii=False)
        tmp.rename(PROPERTIES_PATH)
        logger.info("Enriched %d properties with footprint data", enriched)
        if coords_snapped:
            logger.info(
                "Snapped %d coordinates (%d brand POI, %d footprint centroid)",
                coords_snapped, snapped_brand, snapped_centroid,
            )

    avg_snap = (sum(snap_distances) / len(snap_distances)) if snap_distances else 0
    max_snap = max(snap_distances) if snap_distances else 0

    return {
        "enriched": enriched,
        "cleared_stale": cleared,
        "coords_snapped": coords_snapped,
        "snapped_brand_poi": snapped_brand,
        "snapped_footprint_centroid": snapped_centroid,
        "avg_snap_distance_m": round(avg_snap, 1),
        "max_snap_distance_m": round(max_snap, 1),
        "total_properties": len(props),
        "brand_poi_available": len(brand_poi_coords),
        "dry_run": dry_run,
    }
