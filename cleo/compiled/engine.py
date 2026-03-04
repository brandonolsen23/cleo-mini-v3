"""Compilation engine: assembles complete records from all pipeline stages.

Reads from:
  - parsed/active/{RT_ID}.json     (bypass fields: transaction, site, consideration, parties, broker, etc.)
  - expanded/active/{ID}.json      (address pipeline output with canonicals)
  - coordinates.json               (geocode results per canonical address)
  - parcelled/active/{ID}.json     (parcel resolution: ARN, method, geometry, centroid)
  - osm_pois/active/{ID}.json      (OSM POI metadata: brand, name, coords)

Writes one compiled JSON per source record to output_dir/{ID}.json.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from cleo.parcels.arn import normalize_arn

logger = logging.getLogger(__name__)


def _to_int(val: str) -> Optional[int]:
    """Convert string to int, return None if empty or invalid."""
    if not val:
        return None
    try:
        return int(val.replace(",", "").replace("$", "").strip())
    except (ValueError, AttributeError):
        return None


def _to_float(val: str) -> Optional[float]:
    """Convert string to float, return None if empty or invalid."""
    if not val:
        return None
    try:
        return float(val.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _load_parcelled(parcelled_dir: Path, record_id: str) -> Optional[Dict]:
    """Load parcelled resolution for a record. Returns None if not found."""
    path = parcelled_dir / f"{record_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_parcel(parcelled: Optional[Dict]) -> Optional[Dict]:
    """Extract parcel data from a parcelled resolution record into compiled format."""
    if not parcelled:
        return None

    res = parcelled.get("resolution", {})
    parcel = parcelled.get("parcel")

    if res.get("method") == "none" or not parcel:
        return None

    centroid = parcel.get("centroid")
    if isinstance(centroid, list) and len(centroid) >= 2:
        centroid_lat, centroid_lng = centroid[0], centroid[1]
    elif isinstance(centroid, dict):
        centroid_lat = centroid.get("lat")
        centroid_lng = centroid.get("lng")
    else:
        centroid_lat, centroid_lng = None, None

    return {
        "arn": res.get("resolved_arn", ""),
        "pin": res.get("pin") or parcel.get("pin", ""),
        "method": res.get("method", ""),
        "confidence": res.get("confidence"),
        "centroid_lat": centroid_lat,
        "centroid_lng": centroid_lng,
        "attributes": parcel.get("attributes", {}),
        "source": parcel.get("source", ""),
    }


def _enrich_address(addr: Dict, coord_store: Dict[str, Dict]) -> Dict:
    """Take an expanded address and attach geocode results."""
    enriched = dict(addr)
    canon = addr.get("canonical", "")
    if canon and canon in coord_store:
        providers = coord_store[canon]
        # Use mapbox as primary (most of our data)
        for provider in ("mapbox", "geocodio", "here", "scraper"):
            if provider in providers:
                pdata = providers[provider]
                enriched["lat"] = pdata.get("lat")
                enriched["lng"] = pdata.get("lng")
                enriched["geocode_accuracy"] = pdata.get("accuracy", "")
                enriched["geocode_provider"] = provider
                enriched["formatted_address"] = pdata.get("formatted_address", "")
                mc = pdata.get("match_code", {})
                if mc:
                    enriched["geocode_confidence"] = mc.get("confidence", "")
                break
    return enriched


def _assemble_addresses(expanded: Dict, coord_store: Dict[str, Dict]) -> Dict:
    """Assemble enriched addresses from expanded + geocoded data."""
    addresses: Dict[str, List[Dict]] = {}
    for role in ("property", "property_alt", "seller", "buyer", "owner_address"):
        role_data = expanded.get(role)
        if role_data is None:
            continue

        # property_alt is a list of {addresses: [...]}
        if isinstance(role_data, list):
            all_addrs: List[Dict] = []
            for item in role_data:
                for a in item.get("addresses", []):
                    all_addrs.append(_enrich_address(a, coord_store))
            if all_addrs:
                addresses[role] = all_addrs
        else:
            enriched = [_enrich_address(a, coord_store) for a in role_data.get("addresses", [])]
            if enriched:
                addresses[role] = enriched

    return addresses


def _compile_rt_record(
    record_id: str,
    parsed: Dict,
    expanded: Optional[Dict],
    coord_store: Dict[str, Dict],
    parcelled: Optional[Dict],
) -> Dict:
    """Compile a single Realtrack record from all pipeline stages."""
    txn = parsed.get("transaction", {})
    site = parsed.get("site", {})
    consid = parsed.get("consideration", {})
    xfer = parsed.get("transferor", {})
    xfee = parsed.get("transferee", {})
    broker = parsed.get("broker", {})
    extras = parsed.get("export_extras", {})

    result: Dict[str, Any] = {
        "id": record_id,
        "source": "realtrack",
        "source_versions": {},

        # === TRANSACTION (bypass from parsed) ===
        "transaction": {
            "sale_date": txn.get("sale_date_iso", ""),
            "sale_price": _to_int(txn.get("sale_price", "")),
            "sale_price_display": txn.get("sale_price", ""),
            "arn": normalize_arn(txn.get("arn", "")),
            "pins": txn.get("pins", []),
            "rt_number": txn.get("rt_number", ""),
        },

        # === CONSIDERATION (bypass from parsed) ===
        "consideration": {
            "cash": _to_int(consid.get("cash", "")),
            "assumed_debt": _to_int(consid.get("assumed_debt", "")),
            "chattels": consid.get("chattels", ""),
            "verbatim": consid.get("verbatim", ""),
            "chargees": consid.get("chargees", []),
        },

        # === SITE (bypass from parsed) ===
        "site": {
            "legal_description": site.get("legal_description", ""),
            "site_area": _to_float(site.get("site_area", "")),
            "site_area_units": site.get("site_area_units", ""),
            "site_frontage": _to_float(site.get("site_frontage", "")),
            "site_frontage_units": site.get("site_frontage_units", ""),
            "site_depth": _to_float(site.get("site_depth", "")),
            "site_depth_units": site.get("site_depth_units", ""),
            "zoning": site.get("zoning", ""),
            "building_sf": _to_int(extras.get("building_sf", "")),
        },

        # === SELLER (bypass from parsed) ===
        "seller": {
            "name": xfer.get("name", ""),
            "contact": xfer.get("contact", ""),
            "phone": xfer.get("phone", ""),
            "attention": xfer.get("attention", ""),
            "aliases": xfer.get("aliases", []),
            "alternate_names": xfer.get("alternate_names", []),
            "company_lines": xfer.get("company_lines", []),
            "phones": xfer.get("phones", []),
        },

        # === BUYER (bypass from parsed) ===
        "buyer": {
            "name": xfee.get("name", ""),
            "contact": xfee.get("contact", ""),
            "phone": xfee.get("phone", ""),
            "attention": xfee.get("attention", ""),
            "aliases": xfee.get("aliases", []),
            "alternate_names": xfee.get("alternate_names", []),
            "company_lines": xfee.get("company_lines", []),
            "phones": xfee.get("phones", []),
        },

        # === BROKER (bypass from parsed) ===
        "broker": {
            "brokerage": broker.get("brokerage", ""),
            "phone": broker.get("phone", ""),
        },

        # === OTHER (bypass from parsed) ===
        "description": parsed.get("description", ""),
        "photos": parsed.get("photos", []),

        # === ADDRESSES (from expand + geocode) ===
        "addresses": {},

        # === PARCEL (from parcelled stage) ===
        "parcel": _extract_parcel(parcelled),
    }

    # Null out zero building_sf (5 records have "000")
    if result["site"]["building_sf"] == 0:
        result["site"]["building_sf"] = None

    # --- Assemble addresses from expanded + geocoded ---
    if expanded:
        result["source_versions"]["expanded"] = expanded.get("source_version", "")
        result["addresses"] = _assemble_addresses(expanded, coord_store)

    return result


def _compile_gw_record(
    record_id: str,
    expanded: Dict,
    coord_store: Dict[str, Dict],
    parcelled: Optional[Dict],
) -> Dict:
    """Compile a single GeoWarehouse record."""
    result: Dict[str, Any] = {
        "id": record_id,
        "source": "geowarehouse",
        "source_versions": {
            "expanded": expanded.get("source_version", ""),
        },
        "addresses": _assemble_addresses(expanded, coord_store),
        "parcel": _extract_parcel(parcelled),
    }
    return result


def _compile_brand_record(
    record_id: str,
    expanded: Dict,
    coord_store: Dict[str, Dict],
    parcelled: Optional[Dict],
) -> Dict:
    """Compile a single brand record."""
    result: Dict[str, Any] = {
        "id": record_id,
        "source": "brand",
        "source_versions": {
            "expanded": expanded.get("source_version", ""),
        },
        "addresses": _assemble_addresses(expanded, coord_store),
        "parcel": _extract_parcel(parcelled),
    }
    return result


def _compile_osm_record(
    record_id: str,
    osm_poi: Dict,
    parcelled: Optional[Dict],
) -> Dict:
    """Compile a single OSM POI record.

    OSM records skip the address pipeline — they carry native coords
    and POI metadata (brand, name, category) directly.
    """
    coords = osm_poi.get("coords", {})
    address = osm_poi.get("address", {})

    result: Dict[str, Any] = {
        "id": record_id,
        "source": "osm",
        "source_versions": {},

        # OSM metadata
        "name": osm_poi.get("name", ""),
        "brand": osm_poi.get("brand", ""),
        "tracked_brand": osm_poi.get("tracked_brand", ""),
        "category": osm_poi.get("category", ""),
        "osm_id_full": osm_poi.get("osm_id_full", ""),
        "phone": osm_poi.get("phone", ""),
        "website": osm_poi.get("website", ""),

        # Native coords (no geocoding)
        "coords": {
            "lat": coords.get("lat"),
            "lng": coords.get("lng"),
            "provider": "osm",
        },

        # Address from OSM tags (may be partial)
        "address": {
            "housenumber": address.get("housenumber", ""),
            "street": address.get("street", ""),
            "city": address.get("city", ""),
            "postal_code": address.get("postal_code", ""),
        },

        # Parcel from parcelled stage
        "parcel": _extract_parcel(parcelled),
    }
    return result


def compile_all(
    parsed_dir: Path,
    expanded_dir: Path,
    coordinates_path: Path,
    parcelled_dir: Path,
    output_dir: Path,
    osm_pois_dir: Optional[Path] = None,
) -> Dict:
    """Compile all records from all sources into output_dir.

    Reads parcelled resolution data from parcelled_dir for each record.
    Optionally includes OSM POI records from osm_pois_dir.

    Returns summary: {total, compiled, errors, by_source, elapsed, source_versions}
    """
    start = time.time()
    total = 0
    compiled = 0
    errors = 0
    error_ids: List[str] = []
    by_source: Dict[str, int] = {}

    # --- Load shared data ---
    logger.info("Loading coordinate store...")
    coord_store: Dict[str, Dict] = {}
    if coordinates_path.exists():
        data = json.loads(coordinates_path.read_text(encoding="utf-8"))
        coord_store = data.get("addresses", {})
    logger.info("  %d addresses loaded", len(coord_store))

    # --- Track source versions ---
    parsed_ver = ""
    if (parsed_dir.parent / "active").is_symlink():
        parsed_ver = (parsed_dir.parent / "active").resolve().name
    expanded_ver = ""
    if (expanded_dir.parent / "active").is_symlink():
        expanded_ver = (expanded_dir.parent / "active").resolve().name
    parcelled_ver = ""
    if (parcelled_dir.parent / "active").is_symlink():
        parcelled_ver = (parcelled_dir.parent / "active").resolve().name

    parcelled_count = sum(1 for f in parcelled_dir.glob("*.json") if f.stem != "_meta") if parcelled_dir.exists() else 0
    logger.info("Parcelled: %s (%d records)", parcelled_ver or "none", parcelled_count)

    # --- Process expanded records (RT, GW, Brand) ---
    expanded_files = sorted(expanded_dir.glob("*.json"))
    for exp_path in expanded_files:
        if exp_path.stem == "_meta":
            continue
        total += 1
        record_id = exp_path.stem

        try:
            expanded = json.loads(exp_path.read_text(encoding="utf-8"))
            source = expanded.get("source", "unknown")

            # Load parcelled data for this record
            parcelled = _load_parcelled(parcelled_dir, record_id)

            if source == "realtrack":
                # Load parsed record for bypass fields
                parsed_path = parsed_dir / f"{record_id}.json"
                if parsed_path.exists():
                    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
                else:
                    parsed = {}
                    logger.warning("No parsed file for %s", record_id)

                result = _compile_rt_record(
                    record_id, parsed, expanded, coord_store, parcelled,
                )
                result["source_versions"]["parsed"] = parsed_ver
                result["source_versions"]["expanded"] = expanded_ver
                result["source_versions"]["parcelled"] = parcelled_ver

            elif source == "geowarehouse":
                result = _compile_gw_record(record_id, expanded, coord_store, parcelled)
                result["source_versions"]["expanded"] = expanded_ver
                result["source_versions"]["parcelled"] = parcelled_ver

            elif source == "brand":
                result = _compile_brand_record(record_id, expanded, coord_store, parcelled)
                result["source_versions"]["expanded"] = expanded_ver
                result["source_versions"]["parcelled"] = parcelled_ver

            else:
                logger.warning("Unknown source %s for %s", source, record_id)
                continue

            # Write compiled record
            out_path = output_dir / f"{record_id}.json"
            out_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            compiled += 1
            by_source[source] = by_source.get(source, 0) + 1

        except Exception as e:
            errors += 1
            error_ids.append(record_id)
            logger.error("Error compiling %s: %s", record_id, e)

        if total % 5000 == 0:
            logger.info("Progress: %d records", total)

    # --- Process OSM POI records ---
    if osm_pois_dir and osm_pois_dir.exists():
        osm_files = sorted(osm_pois_dir.glob("*.json"))
        osm_count = sum(1 for f in osm_files if f.stem != "_meta")
        if osm_count:
            logger.info("Processing %d OSM POI records...", osm_count)
        for osm_path in osm_files:
            if osm_path.stem == "_meta":
                continue
            total += 1
            record_id = osm_path.stem

            try:
                osm_poi = json.loads(osm_path.read_text(encoding="utf-8"))
                parcelled = _load_parcelled(parcelled_dir, record_id)

                result = _compile_osm_record(record_id, osm_poi, parcelled)
                result["source_versions"]["parcelled"] = parcelled_ver

                out_path = output_dir / f"{record_id}.json"
                out_path.write_text(
                    json.dumps(result, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                compiled += 1
                by_source["osm"] = by_source.get("osm", 0) + 1

            except Exception as e:
                errors += 1
                error_ids.append(record_id)
                logger.error("Error compiling OSM %s: %s", record_id, e)

            if total % 5000 == 0:
                logger.info("Progress: %d records", total)

    elapsed = time.time() - start
    logger.info(
        "Done: %d compiled, %d errors in %.1fs",
        compiled, errors, elapsed,
    )

    return {
        "total": total,
        "compiled": compiled,
        "errors": errors,
        "error_ids": error_ids,
        "elapsed": elapsed,
        "by_source": by_source,
        "source_versions": {
            "parsed": parsed_ver,
            "expanded": expanded_ver,
            "parcelled": parcelled_ver,
        },
    }
