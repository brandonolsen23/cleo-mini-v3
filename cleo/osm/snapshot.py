"""OSM POI snapshot: fetch branded POIs from Overpass and create OSM source records.

OSM records enter the pipeline directly at the Parcelled stage with native coords
(no parse/normalize/expand/geocode needed). Each POI gets a stable OSM_{5-digit} ID.

Output: data/osm_pois/active/{OSM_00001}.json (versioned via VersionedStore)
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from cleo.osm.brand_search import fetch_all_branded_pois, load_master_brands, _normalize

logger = logging.getLogger(__name__)


def _assign_osm_ids(pois: List[Dict]) -> List[Dict]:
    """Assign stable OSM_{5-digit} IDs, sorted by osm_id for determinism."""
    # Sort by osm_id so IDs are stable across runs
    pois.sort(key=lambda p: p.get("osm_id", ""))
    for i, poi in enumerate(pois, start=1):
        poi["id"] = f"OSM_{i:05d}"
    return pois


def build_snapshot(
    output_dir: Path,
    skip_fetch: bool = False,
    cached_pois_path: Path | None = None,
) -> Dict[str, Any]:
    """Build OSM POI snapshot records.

    If skip_fetch is True and cached_pois_path exists, reuses previously
    fetched POIs instead of querying Overpass again.

    Returns summary: {total_fetched, filtered, written, elapsed}
    """
    start = time.time()

    # --- Fetch or load POIs ---
    if skip_fetch and cached_pois_path and cached_pois_path.exists():
        logger.info("Loading cached POIs from %s", cached_pois_path)
        raw = json.loads(cached_pois_path.read_text(encoding="utf-8"))
        # Could be the raw list or the osm_brands.json structure
        if isinstance(raw, dict) and "properties" in raw:
            # Extract all POIs from the osm_brands.json property-matched structure
            all_pois = []
            seen_osm_ids = set()
            for pid, pdata in raw.get("properties", {}).items():
                for match_type in ("confirmed", "nearby"):
                    for poi in pdata.get(match_type, []):
                        oid = poi.get("osm_id", "")
                        if oid and oid not in seen_osm_ids:
                            seen_osm_ids.add(oid)
                            all_pois.append(poi)
            pois = all_pois
            logger.info("Extracted %d unique POIs from cached osm_brands.json", len(pois))
        elif isinstance(raw, list):
            pois = raw
        else:
            pois = []
    else:
        logger.info("Fetching all branded POIs from Overpass...")
        pois = fetch_all_branded_pois()

    total_fetched = len(pois)
    logger.info("Total POIs: %d", total_fetched)

    # --- Filter to master brands ---
    master = load_master_brands()
    if master:
        filtered = []
        for poi in pois:
            brand = poi.get("brand", "")
            norm_brand = _normalize(brand)
            if norm_brand in master:
                poi["category"] = master[norm_brand].get("category", "")
                poi["tracked_brand"] = master[norm_brand].get("csv_name", brand)
                filtered.append(poi)
        logger.info("Filtered to %d POIs matching %d master brands", len(filtered), len(master))
        pois = filtered
    else:
        logger.warning("No master brands CSV found — using all %d POIs", len(pois))

    # --- Deduplicate by osm_id ---
    seen = {}
    unique = []
    for poi in pois:
        oid = poi.get("osm_id", "")
        if oid and oid not in seen:
            seen[oid] = True
            unique.append(poi)
    logger.info("After dedup: %d unique POIs", len(unique))
    pois = unique

    # --- Assign IDs and write ---
    pois = _assign_osm_ids(pois)
    output_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for poi in pois:
        record = _build_record(poi)
        out_path = output_dir / f"{record['id']}.json"
        out_path.write_text(
            json.dumps(record, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        written += 1

    if written % 5000 == 0 and written > 0:
        logger.info("Progress: %d written", written)

    elapsed = time.time() - start
    logger.info("Snapshot complete: %d records in %.1fs", written, elapsed)

    return {
        "total_fetched": total_fetched,
        "filtered": len(pois),
        "written": written,
        "elapsed": elapsed,
    }


def _build_record(poi: Dict) -> Dict:
    """Build an OSM snapshot record from a parsed Overpass POI.

    The record is structured so the parcelled engine can consume it directly:
    - source: "osm"
    - coords: native lat/lng from Overpass
    - No ARN, no PIN (spatial resolution only)
    """
    osm_id_parts = poi.get("osm_id", "").split("/")
    osm_type = osm_id_parts[0] if len(osm_id_parts) == 2 else "unknown"
    osm_numeric_id = osm_id_parts[1] if len(osm_id_parts) == 2 else poi.get("osm_id", "")

    return {
        "id": poi["id"],
        "source": "osm",
        "osm_type": osm_type,
        "osm_numeric_id": osm_numeric_id,
        "osm_id_full": poi.get("osm_id", ""),

        # POI metadata
        "name": poi.get("name", ""),
        "brand": poi.get("brand", ""),
        "tracked_brand": poi.get("tracked_brand", ""),
        "category": poi.get("category", ""),
        "phone": poi.get("phone", ""),
        "website": poi.get("website", ""),

        # Native coordinates (the key input for parcelled stage)
        "coords": {
            "lat": poi.get("lat"),
            "lng": poi.get("lng"),
            "provider": "osm",
        },

        # Address from OSM tags (may be partial or empty)
        "address": {
            "housenumber": poi.get("housenumber", ""),
            "street": poi.get("address", ""),
            "city": poi.get("city", ""),
            "postal_code": poi.get("postal_code", ""),
        },
    }
