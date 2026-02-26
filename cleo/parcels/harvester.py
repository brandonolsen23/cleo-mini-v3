"""Property-by-property parcel + zoning harvest from ArcGIS services.

For each property with coordinates in a covered municipality, queries the
ArcGIS parcel service to find the containing parcel polygon and attributes,
then optionally queries the zoning overlay.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from shapely.geometry import Point, shape

from cleo.config import PROPERTIES_PATH
from cleo.parcels.client import ArcGISClient
from cleo.parcels.registry import ServiceConfig, ServiceRegistry
from cleo.parcels.store import ParcelStore

logger = logging.getLogger(__name__)


def _extract_attributes(raw_attrs: dict, field_map: dict) -> dict:
    """Map raw ArcGIS field names to our normalized attribute names."""
    result: dict = {}

    # Direct field mappings
    for our_key in ("pin", "arn", "address", "city", "zone_code", "zone_desc",
                    "assessment", "property_use", "legal_desc", "property_class"):
        field_name = field_map.get(our_key)
        if field_name and field_name in raw_attrs:
            val = raw_attrs[field_name]
            if val is not None:
                result[our_key] = val

    # Composite address from split fields
    if "address" not in result:
        parts = []
        for addr_field in ("address_number", "address_street", "address_road"):
            field_name = field_map.get(addr_field)
            if field_name and field_name in raw_attrs:
                val = raw_attrs[field_name]
                if val and str(val).strip():
                    parts.append(str(val).strip())
        if parts:
            result["address"] = " ".join(parts)

        # Handle unit prefix
        unit_field = field_map.get("address_unit")
        if unit_field and unit_field in raw_attrs:
            unit = raw_attrs[unit_field]
            if unit and str(unit).strip():
                result["address_unit"] = str(unit).strip()

    # Area: normalize to square meters
    area_field = field_map.get("area")
    if area_field and area_field in raw_attrs:
        raw_area = raw_attrs[area_field]
        if raw_area is not None:
            area_unit = field_map.get("area_unit", "sqm")
            if area_unit == "hectares":
                result["area_sqm"] = round(float(raw_area) * 10000, 1)
            else:
                # UTM services return area in sq meters
                result["area_sqm"] = round(float(raw_area), 1)

    return result


def _arcgis_to_geojson(geometry: dict) -> Optional[dict]:
    """Convert ArcGIS JSON geometry to GeoJSON.

    ArcGIS uses {"rings": [[[x,y],...]], "spatialReference": {...}}
    GeoJSON uses {"type": "Polygon", "coordinates": [[[lng,lat],...]]}

    When outSR=4326, ArcGIS returns coords in WGS84 already.
    """
    if not geometry:
        return None

    rings = geometry.get("rings")
    if rings:
        # Single polygon or multi-ring
        if len(rings) == 1:
            return {"type": "Polygon", "coordinates": rings}
        else:
            return {"type": "Polygon", "coordinates": rings}

    # Already GeoJSON?
    if "type" in geometry and "coordinates" in geometry:
        return geometry

    return None


def _find_containing_parcel(
    features: list[dict], lat: float, lng: float
) -> Optional[dict]:
    """From a list of ArcGIS features, find the one whose polygon contains the point.

    Post-filters the bbox-based query results for actual containment.
    """
    point = Point(lng, lat)
    for feat in features:
        geom_json = _arcgis_to_geojson(feat.get("geometry", {}))
        if not geom_json:
            continue
        try:
            poly = shape(geom_json)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.contains(point):
                return feat
        except Exception:
            continue

    # No containment match -- return the first feature as a proximity fallback
    if features:
        return features[0]
    return None


def _normalize_address_for_query(address: str) -> str:
    """Normalize a property address for an ArcGIS LIKE query.

    Uppercases, strips unit numbers (e.g. "Unit 2", "#3"), and abbreviates
    common road suffixes to improve match rate against the city's address layer.
    """
    import re
    addr = address.upper().strip()

    # Strip unit prefixes: "UNIT 2", "#3", "APT 4B", etc.
    addr = re.sub(r'\b(UNIT|APT|SUITE|STE|#)\s*[\w-]+\b', '', addr)

    # Abbreviate common road suffixes
    suffix_map = {
        r'\bSTREET\b': 'ST',
        r'\bAVENUE\b': 'AVE',
        r'\bROAD\b': 'RD',
        r'\bDRIVE\b': 'DR',
        r'\bCOURT\b': 'CRT',
        r'\bCRESCENT\b': 'CRES',
        r'\bBOULEVARD\b': 'BLVD',
        r'\bPLACE\b': 'PL',
        r'\bLANE\b': 'LN',
        r'\bTERRACE\b': 'TERR',
        r'\bCIRCLE\b': 'CIR',
        r'\bPARKWAY\b': 'PKY',
    }
    for pattern, abbr in suffix_map.items():
        addr = re.sub(pattern, abbr, addr)

    return addr.strip()


def _harvest_by_address(
    client: ArcGISClient,
    svc,
    pid: str,
    prop: dict,
    store,
) -> Optional[dict]:
    """Harvest a parcel by address lookup via the city's Address layer.

    1. Normalize the property address for a LIKE query.
    2. Query the Address layer to get Parcel_ID.
    3. Query the Parcel layer by GIS_ID to get the polygon.
    4. Return a feature dict ready for store.add_parcels(), or None on failure.
    """
    address = prop.get("address", "").strip()
    if not address:
        return None

    normalized = _normalize_address_for_query(address)
    where = f"{svc.address_field} LIKE '{normalized}%'"

    addr_features = client.query_by_where(
        svc.address_url,
        where=where,
        out_fields=f"{svc.address_field},{svc.parcel_link_field}",
        return_geometry=False,
    )

    if not addr_features:
        logger.debug("Address lookup found no results for %s (%s)", pid, normalized)
        return None

    parcel_id = addr_features[0].get("attributes", {}).get(svc.parcel_link_field)
    if parcel_id is None:
        return None

    # Fetch the parcel polygon by GIS_ID
    parcel_features = client.query_by_where(
        svc.parcels_url,
        where=f"{svc.parcel_gis_id_field} = {parcel_id}",
        out_fields="*",
        return_geometry=True,
    )

    if not parcel_features:
        logger.debug("Parcel lookup found no polygon for %s (parcel_id=%s)", pid, parcel_id)
        return None

    best = parcel_features[0]
    raw_attrs = best.get("attributes", {})
    attrs = _extract_attributes(raw_attrs, svc.field_map)

    geojson_geom = _arcgis_to_geojson(best.get("geometry", {}))
    if geojson_geom is None:
        return None

    # Optionally query zoning using the address point from the Address layer
    if svc.zoning_url:
        addr_geom = addr_features[0].get("geometry")
        if addr_geom and "x" in addr_geom and "y" in addr_geom:
            # Address layer returns point in outSR=4326
            pt_lng, pt_lat = addr_geom["x"], addr_geom["y"]
            zone_attrs = client.query_zoning_at_point(
                svc.zoning_url, pt_lat, pt_lng, 4326,
            )
            if zone_attrs:
                zone_code_field = svc.field_map.get("zone_code")
                zone_desc_field = svc.field_map.get("zone_desc")
                if zone_code_field and zone_code_field in zone_attrs:
                    attrs["zone_code"] = zone_attrs[zone_code_field]
                if zone_desc_field and zone_desc_field in zone_attrs:
                    attrs["zone_desc"] = zone_attrs[zone_desc_field]

    return {"geometry": geojson_geom, "properties": attrs}


def harvest_parcels(
    municipality: Optional[str] = None,
    dry_run: bool = False,
    limit: Optional[int] = None,
) -> dict:
    """Harvest parcel polygons for properties in covered municipalities.

    Args:
        municipality: If provided, only harvest for this municipality key.
        dry_run: If True, count eligible properties without querying.
        limit: Max number of properties to query (for testing).

    Returns:
        Summary dict with counts.
    """
    if not PROPERTIES_PATH.exists():
        return {"error": "No properties.json"}

    registry = ServiceRegistry()
    registry.load()

    store = ParcelStore()

    # Load properties
    reg = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
    props = reg.get("properties", {})

    # Group properties by municipality service
    by_service: dict[str, list[tuple[str, dict]]] = {}
    no_coords = 0
    no_coverage = 0

    for pid, prop in props.items():
        city = prop.get("city", "")
        svc = registry.resolve(city)
        if svc is None:
            no_coverage += 1
            continue

        if municipality and svc.key != municipality:
            continue

        lat, lng = prop.get("lat"), prop.get("lng")
        # Include properties without coords if the service has address lookup
        if lat is None or lng is None:
            if not svc.has_address_lookup:
                no_coords += 1
                continue

        by_service.setdefault(svc.key, []).append((pid, prop))

    if not by_service:
        return {
            "error": f"No properties found for {'municipality=' + municipality if municipality else 'any covered municipality'}",
            "no_coords": no_coords,
            "no_coverage": no_coverage,
        }

    if dry_run:
        total = sum(len(v) for v in by_service.values())
        return {
            "dry_run": True,
            "eligible_properties": total,
            "by_municipality": {k: len(v) for k, v in by_service.items()},
            "no_coords": no_coords,
            "no_coverage": no_coverage,
        }

    # Harvest
    client = ArcGISClient()
    total_queried = 0
    total_found = 0
    total_no_result = 0
    errors = 0
    start_time = time.time()

    try:
        for svc_key, prop_list in by_service.items():
            svc = registry.get(svc_key)
            if svc is None:
                continue

            logger.info(
                "Harvesting %d properties for %s (%s)",
                len(prop_list), svc.name, svc.key,
            )

            # Skip properties already mapped
            already_mapped = set(store.property_to_parcel.keys())
            already_no_cov = set(store.no_coverage)

            batch_features: list[dict] = []

            for pid, prop in prop_list:
                if pid in already_mapped or pid in already_no_cov:
                    continue

                if limit is not None and total_queried >= limit:
                    break

                lat, lng = prop.get("lat"), prop.get("lng")
                feat: Optional[dict] = None

                # Try address-based lookup first
                if svc.has_address_lookup:
                    feat = _harvest_by_address(client, svc, pid, prop, store)
                    total_queried += 1

                # Fall back to coordinate bbox if address lookup failed and coords exist
                if feat is None and lat is not None and lng is not None:
                    if svc.has_address_lookup:
                        logger.debug("Address lookup failed for %s, falling back to coords", pid)
                    features = client.query_at_point(
                        svc.parcels_url, lat, lng, svc.srid,
                    )
                    if not svc.has_address_lookup:
                        total_queried += 1

                    if features:
                        best = _find_containing_parcel(features, lat, lng)
                        if best is not None:
                            raw_attrs = best.get("attributes", {})
                            attrs = _extract_attributes(raw_attrs, svc.field_map)
                            geojson_geom = _arcgis_to_geojson(best.get("geometry", {}))
                            if geojson_geom:
                                if svc.zoning_url:
                                    zone_attrs = client.query_zoning_at_point(
                                        svc.zoning_url, lat, lng, svc.srid,
                                    )
                                    if zone_attrs:
                                        zone_code_field = svc.field_map.get("zone_code")
                                        zone_desc_field = svc.field_map.get("zone_desc")
                                        if zone_code_field and zone_code_field in zone_attrs:
                                            attrs["zone_code"] = zone_attrs[zone_code_field]
                                        if zone_desc_field and zone_desc_field in zone_attrs:
                                            attrs["zone_desc"] = zone_attrs[zone_desc_field]
                                feat = {"geometry": geojson_geom, "properties": attrs}

                if feat is None:
                    store.mark_no_coverage(pid)
                    total_no_result += 1
                    continue

                batch_features.append({
                    "geometry": feat["geometry"],
                    "properties": feat["properties"],
                    "_prop_id": pid,
                })
                total_found += 1

            # Add batch to store
            if batch_features:
                # Separate _prop_id before storing
                prop_ids = []
                clean_features = []
                for feat in batch_features:
                    prop_ids.append(feat.pop("_prop_id"))
                    clean_features.append(feat)

                result = store.add_parcels(svc_key, clean_features)
                logger.info(
                    "%s: added=%d, skipped_dups=%d",
                    svc_key, result["added"], result["skipped_dups"],
                )

                # Link properties to parcels
                for feat, pid in zip(clean_features, prop_ids):
                    pcl_id = feat.get("properties", {}).get("pcl_id")
                    if pcl_id:
                        store.set_property_mapping(pid, pcl_id)

            if limit is not None and total_queried >= limit:
                break

    finally:
        client.close()

    store.save()
    elapsed = time.time() - start_time

    return {
        "queried": total_queried,
        "found": total_found,
        "no_result": total_no_result,
        "errors": errors,
        "elapsed_s": round(elapsed, 1),
        "no_coords": no_coords,
        "no_coverage_total": no_coverage,
    }


def harvest_status() -> dict:
    """Return current harvest status from disk."""
    store = ParcelStore()
    st = store.status()

    registry = ServiceRegistry()
    registry.load()

    return {
        **st,
        "services": {
            k: {
                "name": svc.name,
                "parcels_url": svc.parcels_url,
                "zoning_url": svc.zoning_url,
                "cities": svc.cities,
            }
            for k, svc in registry.all_services().items()
        },
    }
