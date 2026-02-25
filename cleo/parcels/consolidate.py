"""Parcel-based property consolidation.

Groups properties that share the same legal parcel, assigns brand POIs
via spatial containment, and enriches properties.json with parcel metadata.

No property merging -- each P-ID stays independent. The parcel groups them
via parcel_group, parcel_brands, and parcel_building_count fields.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from cleo.config import (
    BRANDS_DATA_DIR,
    PARCELS_CONSOLIDATION_PATH,
    PROPERTIES_PATH,
)
from cleo.parcels.spatial import ParcelIndex
from cleo.parcels.store import ParcelStore

logger = logging.getLogger(__name__)

# All parcel-related fields we manage on properties
_PARCEL_FIELDS = [
    "parcel_id",
    "parcel_pin",
    "parcel_arn",
    "parcel_area_sqm",
    "zoning_code",
    "zoning_desc",
    "parcel_assessment",
    "parcel_property_use",
    "parcel_group",
    "parcel_brands",
    "parcel_building_count",
]


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
                    })
        except (json.JSONDecodeError, TypeError):
            continue

    return pois


def _load_footprint_index():
    """Try to load the FootprintIndex. Returns None if unavailable."""
    try:
        from cleo.footprints.spatial import FootprintIndex

        idx = FootprintIndex()
        idx.load()
        if idx.count > 0:
            return idx
    except Exception:
        pass
    return None


def consolidate(dry_run: bool = False) -> dict:
    """Run full parcel-based consolidation.

    1. Load ParcelIndex (STRtree)
    2. Map each property with coords to a parcel via containment
    3. Build reverse map: pcl_id -> [P-IDs]
    4. Map brand POIs to parcels via containment
    5. Optionally count footprints per parcel
    6. Write parcel fields to properties.json
    7. Save consolidation summary

    Returns summary dict with stats.
    """
    if not PROPERTIES_PATH.exists():
        return {"error": "No properties.json."}

    # Load parcel spatial index
    parcel_index = ParcelIndex()
    parcel_index.load()
    if parcel_index.count == 0:
        return {"error": "No parcels loaded. Run 'cleo parcels --harvest' first."}

    store = ParcelStore()

    # Load properties
    reg = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
    props = reg.get("properties", {})

    # --- Step 1: Map properties to parcels via spatial containment ---
    # Use existing property_to_parcel from harvester as primary source,
    # then fill gaps via spatial query for any property with coords.
    prop_to_pcl: dict[str, str] = dict(store.property_to_parcel)

    spatially_matched = 0
    for pid, prop in props.items():
        if pid in prop_to_pcl:
            continue
        lat = prop.get("lat") or prop.get("latitude")
        lng = prop.get("lng") or prop.get("longitude")
        if not lat or not lng:
            continue
        pcl_ids = parcel_index.find_containing(float(lat), float(lng))
        if pcl_ids:
            prop_to_pcl[pid] = pcl_ids[0]
            spatially_matched += 1

    # --- Step 2: Build reverse map: pcl_id -> [P-IDs] ---
    pcl_to_pids: dict[str, list[str]] = defaultdict(list)
    for pid, pcl_id in prop_to_pcl.items():
        if pid in props:  # only include known properties
            pcl_to_pids[pcl_id].append(pid)

    # Sort for deterministic output
    for pcl_id in pcl_to_pids:
        pcl_to_pids[pcl_id].sort()

    # --- Step 3: Map brand POIs to parcels ---
    brand_pois = _load_brand_pois()
    pcl_to_brands: dict[str, set[str]] = defaultdict(set)
    brands_matched = 0

    for poi in brand_pois:
        pcl_ids = parcel_index.find_containing(poi["lat"], poi["lng"])
        if not pcl_ids:
            continue
        pcl_to_brands[pcl_ids[0]].add(poi["brand"])
        brands_matched += 1

    # --- Step 4: Count footprints per parcel (optional) ---
    fp_index = _load_footprint_index()
    pcl_to_fp_count: dict[str, int] = {}

    if fp_index:
        for pcl_id in pcl_to_pids:
            feat = parcel_index.get_feature(pcl_id)
            if not feat:
                continue
            clat = feat.get("centroid_lat")
            clng = feat.get("centroid_lng")
            if clat is None or clng is None:
                continue
            # Find footprints whose center falls inside this parcel polygon
            # Use the parcel polygon to query footprint index
            fp_ids = fp_index.find_containing(clat, clng)
            if fp_ids:
                pcl_to_fp_count[pcl_id] = len(fp_ids)

    # --- Step 5: Clear stale parcel fields, then write enrichment ---
    cleared = 0
    for prop in props.values():
        had = "parcel_id" in prop
        for field in _PARCEL_FIELDS:
            prop.pop(field, None)
        if had:
            cleared += 1

    enriched = 0
    for pid, pcl_id in prop_to_pcl.items():
        if pid not in props:
            continue

        parcel = store.get_parcel(pcl_id)
        prop = props[pid]
        prop["parcel_id"] = pcl_id

        # Copy parcel attributes
        if parcel:
            pcl_props = parcel.get("properties", {})
            if pcl_props.get("pin"):
                prop["parcel_pin"] = pcl_props["pin"]
            if pcl_props.get("arn"):
                prop["parcel_arn"] = pcl_props["arn"]
            if pcl_props.get("area_sqm"):
                prop["parcel_area_sqm"] = pcl_props["area_sqm"]
            if pcl_props.get("zone_code"):
                prop["zoning_code"] = pcl_props["zone_code"]
            if pcl_props.get("zone_desc"):
                prop["zoning_desc"] = pcl_props["zone_desc"]
            if pcl_props.get("assessment"):
                prop["parcel_assessment"] = pcl_props["assessment"]
            if pcl_props.get("property_use"):
                prop["parcel_property_use"] = pcl_props["property_use"]

        # Parcel group: other P-IDs on the same parcel (exclude self)
        group = [p for p in pcl_to_pids[pcl_id] if p != pid]
        if group:
            prop["parcel_group"] = group

        # Brands spatially inside this parcel
        brands = pcl_to_brands.get(pcl_id)
        if brands:
            prop["parcel_brands"] = sorted(brands)

        # Footprint count
        fp_count = pcl_to_fp_count.get(pcl_id)
        if fp_count:
            prop["parcel_building_count"] = fp_count

        enriched += 1

    # --- Step 6: Build consolidation summary ---
    multi_property_parcels = {
        pcl_id: pids for pcl_id, pids in pcl_to_pids.items() if len(pids) > 1
    }

    # Build detailed multi-property records for the summary
    multi_details = []
    for pcl_id, pids in sorted(multi_property_parcels.items(), key=lambda x: -len(x[1])):
        feat = parcel_index.get_feature(pcl_id) or {}
        detail = {
            "pcl_id": pcl_id,
            "property_count": len(pids),
            "property_ids": pids,
            "addresses": [],
            "brands": sorted(pcl_to_brands.get(pcl_id, set())),
            "municipality": feat.get("municipality", ""),
        }
        for pid in pids:
            p = props.get(pid, {})
            addr = p.get("address", "")
            city = p.get("city", "")
            if addr:
                detail["addresses"].append(f"{addr}, {city}" if city else addr)
        multi_details.append(detail)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_properties": len(props),
            "properties_with_parcel": enriched,
            "spatially_matched": spatially_matched,
            "parcels_with_multiple_properties": len(multi_property_parcels),
            "total_brand_pois": len(brand_pois),
            "brands_matched_to_parcel": brands_matched,
            "parcels_with_brands": len(pcl_to_brands),
            "parcels_with_footprints": len(pcl_to_fp_count),
        },
        "multi_property_parcels": multi_details,
    }

    if not dry_run:
        # Write properties.json
        tmp = PROPERTIES_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(reg, f, indent=2, ensure_ascii=False)
        tmp.rename(PROPERTIES_PATH)
        logger.info("Enriched %d properties with parcel consolidation data", enriched)

        # Write consolidation summary
        PARCELS_CONSOLIDATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp2 = PARCELS_CONSOLIDATION_PATH.with_suffix(".tmp")
        with open(tmp2, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        tmp2.rename(PARCELS_CONSOLIDATION_PATH)
        logger.info(
            "Saved consolidation summary: %d multi-property parcels",
            len(multi_property_parcels),
        )

    return {
        "enriched": enriched,
        "cleared_stale": cleared,
        "total_properties": len(props),
        "spatially_matched": spatially_matched,
        "multi_property_parcels": len(multi_property_parcels),
        "brands_matched": brands_matched,
        "parcels_with_brands": len(pcl_to_brands),
        "dry_run": dry_run,
        "multi_details": multi_details,
    }
