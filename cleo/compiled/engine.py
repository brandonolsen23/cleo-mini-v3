"""Compilation engine: assembles complete records from all pipeline stages.

Reads from:
  - parsed/active/{RT_ID}.json     (bypass fields: transaction, site, consideration, parties, broker, etc.)
  - expanded/active/{ID}.json      (address pipeline output with canonicals)
  - coordinates.json               (geocode results per canonical address)
  - parcels/property_parcel_index.json  (parcel matches per property)
  - parcels/parcels.json           (parcel boundary features)

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


def _compile_rt_record(
    record_id: str,
    parsed: Dict,
    expanded: Optional[Dict],
    coord_store: Dict[str, Dict],
    parcel_index: Dict[str, Dict],
    parcel_features: Dict[str, Dict],
) -> Dict:
    """Compile a single Realtrack record from all pipeline stages."""
    txn = parsed.get("transaction", {})
    addr = txn.get("address", {})
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

        # === PARCEL (from parcel lookup) ===
        "parcel": None,
    }

    # Null out zero building_sf (5 records have "000")
    if result["site"]["building_sf"] == 0:
        result["site"]["building_sf"] = None

    # --- Assemble addresses from expanded + geocoded ---
    if expanded:
        result["source_versions"]["expanded"] = expanded.get("source_version", "")
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
                    result["addresses"][role] = all_addrs
            else:
                enriched = []
                for a in role_data.get("addresses", []):
                    enriched.append(_enrich_address(a, coord_store))
                if enriched:
                    result["addresses"][role] = enriched

    # --- Parcel lookup (property address coords or ARN) ---
    # ARN is already normalized to 20-digit in the transaction block above.
    # Provincial parcel ARNs are natively 20-digit, so direct string match works.
    arn = result["transaction"]["arn"]
    if arn and arn in parcel_features:
        feat = parcel_features[arn]
        result["parcel"] = {
            "arn": arn,
            "pcl_id": feat.get("pcl_id", ""),
            "assessment": feat.get("assessment"),
            "property_use": feat.get("property_use", ""),
            "legal_desc": feat.get("legal_desc", ""),
            "area_sqm": feat.get("area_sqm"),
            "municipality": feat.get("municipality", ""),
            "centroid_lat": feat.get("centroid_lat"),
            "centroid_lng": feat.get("centroid_lng"),
        }
    # Also check the property_parcel_index (keyed by P-ID, uses legacy matching)
    if result["parcel"] is None and arn:
        for pid, match in parcel_index.items():
            match_arn = normalize_arn(match.get("parcel_arn", ""))
            if match_arn == arn:
                parcel_entry = dict(match)
                parcel_entry["property_id"] = pid
                result["parcel"] = parcel_entry
                break

    # Fallback: try to match via property coords
    if result["parcel"] is None:
        prop_addrs = result["addresses"].get("property", [])
        if prop_addrs:
            first = prop_addrs[0]
            if first.get("lat") and first.get("lng"):
                # Check parcel index for any property at these coords
                for pid, match in parcel_index.items():
                    if match.get("address", "").upper() == first.get("canonical", "").split(",")[0].upper():
                        parcel_entry = dict(match)
                        parcel_entry["property_id"] = pid
                        feature_arn = match.get("parcel_arn", "")
                        if feature_arn in parcel_features:
                            parcel_entry["feature"] = parcel_features[feature_arn]
                        result["parcel"] = parcel_entry
                        break

    return result


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


def _compile_gw_record(
    record_id: str,
    expanded: Dict,
    coord_store: Dict[str, Dict],
) -> Dict:
    """Compile a single GeoWarehouse record."""
    result: Dict[str, Any] = {
        "id": record_id,
        "source": "geowarehouse",
        "source_versions": {
            "expanded": expanded.get("source_version", ""),
        },
        "addresses": {},
        "parcel": None,
    }

    for role in ("property", "property_alt", "owner_address"):
        role_data = expanded.get(role)
        if role_data is None:
            continue
        if isinstance(role_data, list):
            all_addrs = []
            for item in role_data:
                for a in item.get("addresses", []):
                    all_addrs.append(_enrich_address(a, coord_store))
            if all_addrs:
                result["addresses"][role] = all_addrs
        else:
            enriched = [_enrich_address(a, coord_store) for a in role_data.get("addresses", [])]
            if enriched:
                result["addresses"][role] = enriched

    return result


def _compile_brand_record(
    record_id: str,
    expanded: Dict,
    coord_store: Dict[str, Dict],
) -> Dict:
    """Compile a single brand record."""
    result: Dict[str, Any] = {
        "id": record_id,
        "source": "brand",
        "source_versions": {
            "expanded": expanded.get("source_version", ""),
        },
        "addresses": {},
        "parcel": None,
    }

    prop = expanded.get("property")
    if prop:
        enriched = [_enrich_address(a, coord_store) for a in prop.get("addresses", [])]
        if enriched:
            result["addresses"]["property"] = enriched

    return result


def compile_all(
    parsed_dir: Path,
    expanded_dir: Path,
    coordinates_path: Path,
    parcel_index_path: Path,
    parcels_path: Path,
    output_dir: Path,
) -> Dict:
    """Compile all records from all sources into output_dir.

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

    logger.info("Loading parcel index...")
    parcel_index: Dict[str, Dict] = {}
    if parcel_index_path.exists():
        data = json.loads(parcel_index_path.read_text(encoding="utf-8"))
        parcel_index = data.get("matches", {})
    logger.info("  %d parcel matches loaded", len(parcel_index))

    logger.info("Loading parcel features...")
    parcel_features: Dict[str, Dict] = {}
    # Load municipal parcels (parcels.json — short ARNs)
    if parcels_path.exists():
        data = json.loads(parcels_path.read_text(encoding="utf-8"))
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            arn = normalize_arn(props.get("arn", ""))
            if arn:
                parcel_features[arn] = props
    # Load provincial parcels (provincial_raw.json — 20-digit ARNs)
    provincial_path = parcels_path.parent / "provincial_raw.json"
    if provincial_path.exists():
        data = json.loads(provincial_path.read_text(encoding="utf-8"))
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            arn = normalize_arn(props.get("ASSESSMENT_ROLL_NUMBER", ""))
            if arn and arn not in parcel_features:
                parcel_features[arn] = {
                    "arn": arn,
                    "pcl_id": props.get("pcl_id", ""),
                    "municipality": props.get("municipality", ""),
                    "centroid_lat": props.get("centroid_lat"),
                    "centroid_lng": props.get("centroid_lng"),
                }
    logger.info("  %d parcel features loaded", len(parcel_features))

    # --- Track source versions ---
    parsed_ver = ""
    if (parsed_dir.parent / "active").is_symlink():
        parsed_ver = (parsed_dir.parent / "active").resolve().name
    expanded_ver = ""
    if (expanded_dir.parent / "active").is_symlink():
        expanded_ver = (expanded_dir.parent / "active").resolve().name

    # --- Process expanded records (all sources: RT, GW, brand) ---
    expanded_files = sorted(expanded_dir.glob("*.json"))
    for exp_path in expanded_files:
        if exp_path.stem == "_meta":
            continue
        total += 1
        record_id = exp_path.stem

        try:
            expanded = json.loads(exp_path.read_text(encoding="utf-8"))
            source = expanded.get("source", "unknown")

            if source == "realtrack":
                # Load parsed record for bypass fields
                parsed_path = parsed_dir / f"{record_id}.json"
                if parsed_path.exists():
                    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
                else:
                    parsed = {}
                    logger.warning("No parsed file for %s", record_id)

                result = _compile_rt_record(
                    record_id, parsed, expanded,
                    coord_store, parcel_index, parcel_features,
                )
                result["source_versions"]["parsed"] = parsed_ver
                result["source_versions"]["expanded"] = expanded_ver

            elif source == "geowarehouse":
                result = _compile_gw_record(record_id, expanded, coord_store)
                result["source_versions"]["expanded"] = expanded_ver

            elif source == "brand":
                result = _compile_brand_record(record_id, expanded, coord_store)
                result["source_versions"]["expanded"] = expanded_ver

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
        },
    }
