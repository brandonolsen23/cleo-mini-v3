"""Pipeline metric collectors — one function per stage.

Each collector scans the relevant data files and returns a dict of metrics.
Designed to be fast enough to run on every `cleo monitor` invocation.

Every field that exists in each stage's data files is tracked here.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from cleo.config import (
    DATA_DIR,
    HTML_DIR,
    COORDINATES_PATH,
    PARCELS_DIR,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_files(directory: Path, pattern: str = "*.json") -> int:
    if not directory.exists():
        return 0
    return sum(1 for _ in directory.glob(pattern))


def _load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _field_coverage(records: list[dict], field_path: str) -> int:
    """Count records where a dotted field path is non-empty."""
    count = 0
    for rec in records:
        val = rec
        for key in field_path.split("."):
            if isinstance(val, dict):
                val = val.get(key)
            else:
                val = None
                break
        if val is not None and val != "" and val != []:
            count += 1
    return count


def _coverage_entry(count: int, total: int) -> dict:
    return {"count": count, "pct": round(count / total * 100, 1) if total else 0}


def _address_block_coverage(records: list[dict], block_key: str) -> dict[str, dict]:
    """Compute field coverage for a normalized address block (seller/buyer/owner_address)."""
    fields = [
        "raw_address", "street_number", "street_name", "street_suffix",
        "street_direction", "unit", "unit_type", "po_box", "rural_route",
        "building_name", "normalized_city", "city_status", "address_scope",
        "category", "normalized_province", "raw_city", "municipality",
        "normalized_postal_code",
    ]
    total = 0
    counts: dict[str, int] = {f: 0 for f in fields}

    for rec in records:
        block = rec.get(block_key)
        if not block or not isinstance(block, dict):
            continue
        total += 1
        for f in fields:
            if block.get(f):
                counts[f] += 1

    return {f: _coverage_entry(c, total) for f, c in counts.items()} if total else {}


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def collect_ingest_metrics() -> dict[str, Any]:
    start = time.time()
    tracker_path = DATA_DIR / "seen_rt_ids.json"
    index_path = DATA_DIR / "html_index.json"

    # Count HTML files by type
    by_type: dict[str, int] = {}
    total_html = 0
    if HTML_DIR.exists():
        for type_dir in sorted(HTML_DIR.iterdir()):
            if type_dir.is_dir():
                count = sum(1 for f in type_dir.glob("*.html"))
                if count:
                    by_type[type_dir.name] = count
                    total_html += count
        # Also count flat HTML files (legacy)
        flat = sum(1 for f in HTML_DIR.glob("*.html"))
        if flat:
            by_type["_flat"] = flat
            total_html += flat

    # Tracker info
    tracker_data = _load_json(tracker_path) or {}
    tracker_total = len(tracker_data)

    # Find latest batch
    latest_ts = None
    latest_type = None
    batch_count = 0
    if tracker_data:
        by_ts: dict[str, list] = {}
        for rt_id, info in tracker_data.items():
            if isinstance(info, dict):
                ts = info.get("ts", "")[:10]  # date portion
                if ts:
                    by_ts.setdefault(ts, []).append(rt_id)
        if by_ts:
            latest_date = max(by_ts.keys())
            latest_ts = latest_date
            batch_count = len(by_ts[latest_date])
            # Get types in latest batch
            types_in_batch = set()
            for rt_id in by_ts[latest_date]:
                info = tracker_data[rt_id]
                if isinstance(info, dict) and info.get("type"):
                    types_in_batch.add(info["type"])
            latest_type = ", ".join(sorted(types_in_batch)) if types_in_batch else None

    # Index info
    index_data = _load_json(index_path) or {}
    index_total = len(index_data)

    return {
        "stage": "ingest",
        "total_html_files": total_html,
        "by_type": by_type,
        "tracker_total": tracker_total,
        "index_total": index_total,
        "latest_batch_date": latest_ts,
        "latest_batch_count": batch_count,
        "latest_batch_types": latest_type,
        "elapsed": round(time.time() - start, 2),
    }


# ---------------------------------------------------------------------------
# Parse — tracks ALL fields from parsed records
# ---------------------------------------------------------------------------

def collect_parse_metrics() -> dict[str, Any]:
    start = time.time()
    from cleo.parse.versioning import active_version, active_dir

    version = active_version()
    parsed_dir = active_dir()

    if not parsed_dir or not parsed_dir.exists():
        return {"stage": "parsed", "version": version, "total_records": 0}

    # Load all parsed records
    records = []
    for f in parsed_dir.glob("*.json"):
        if f.stem == "_meta":
            continue
        try:
            records.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass

    total = len(records)
    if total == 0:
        return {"stage": "parsed", "version": version, "total_records": 0}

    # Field coverage — every non-volatile field
    fields = {
        # Transaction / address
        "address": "transaction.address.address",
        "city": "transaction.address.city",
        "municipality": "transaction.address.municipality",
        "province": "transaction.address.province",
        "postal_code": "transaction.address.postal_code",
        "address_suite": "transaction.address.address_suite",
        "alternate_addresses": "transaction.address.alternate_addresses",
        # Transaction core
        "sale_price": "transaction.sale_price",
        "sale_price_raw": "transaction.sale_price_raw",
        "sale_date": "transaction.sale_date",
        "sale_date_iso": "transaction.sale_date_iso",
        "arn": "transaction.arn",
        "pins": "transaction.pins",
        "rt_number": "transaction.rt_number",
        # Transferor (seller)
        "seller_name": "transferor.name",
        "seller_contact": "transferor.contact",
        "seller_phone": "transferor.phone",
        "seller_address": "transferor.address",
        "seller_phones": "transferor.phones",
        "seller_company_lines": "transferor.company_lines",
        "seller_contact_lines": "transferor.contact_lines",
        "seller_address_lines": "transferor.address_lines",
        "seller_officer_titles": "transferor.officer_titles",
        "seller_aliases": "transferor.aliases",
        "seller_alternate_names": "transferor.alternate_names",
        "seller_attention": "transferor.attention",
        # Transferee (buyer)
        "buyer_name": "transferee.name",
        "buyer_contact": "transferee.contact",
        "buyer_phone": "transferee.phone",
        "buyer_address": "transferee.address",
        "buyer_phones": "transferee.phones",
        "buyer_company_lines": "transferee.company_lines",
        "buyer_contact_lines": "transferee.contact_lines",
        "buyer_address_lines": "transferee.address_lines",
        "buyer_officer_titles": "transferee.officer_titles",
        "buyer_aliases": "transferee.aliases",
        "buyer_alternate_names": "transferee.alternate_names",
        "buyer_attention": "transferee.attention",
        # Site
        "legal_description": "site.legal_description",
        "site_area": "site.site_area",
        "site_area_units": "site.site_area_units",
        "site_frontage": "site.site_frontage",
        "site_frontage_units": "site.site_frontage_units",
        "site_depth": "site.site_depth",
        "site_depth_units": "site.site_depth_units",
        "zoning": "site.zoning",
        # Consideration
        "cash": "consideration.cash",
        "assumed_debt": "consideration.assumed_debt",
        "chattels": "consideration.chattels",
        "verbatim": "consideration.verbatim",
        "chargees": "consideration.chargees",
        # Broker
        "brokerage": "broker.brokerage",
        "broker_phone": "broker.phone",
        # Extras
        "building_sf": "export_extras.building_sf",
        "description": "description",
        "photos": "photos",
    }

    coverage: dict[str, dict] = {}
    for label, path in fields.items():
        count = _field_coverage(records, path)
        coverage[label] = _coverage_entry(count, total)

    # Flag counts
    html_flags = _load_json(DATA_DIR / "html_flags.json") or {}
    parse_flags = _load_json(DATA_DIR / "parse_flags.json") or {}

    # Count flags by ID
    h_flag_counts: dict[str, int] = {}
    for rt_id, flags in html_flags.items():
        for flag in flags:
            h_flag_counts[flag] = h_flag_counts.get(flag, 0) + 1

    p_flag_counts: dict[str, int] = {}
    for rt_id, flags in parse_flags.items():
        for flag in flags:
            p_flag_counts[flag] = p_flag_counts.get(flag, 0) + 1

    # Reviews
    reviews = _load_json(DATA_DIR / "reviews.json") or {}
    review_counts = {"clean": 0, "bad_source": 0, "parser_issue": 0, "other": 0}
    for rt_id, rev in reviews.items():
        det = rev.get("determination", "other")
        review_counts[det] = review_counts.get(det, 0) + 1

    return {
        "stage": "parsed",
        "version": version,
        "total_records": total,
        "field_coverage": coverage,
        "html_flags_total": len(html_flags),
        "html_flag_counts": h_flag_counts,
        "parse_flags_total": len(parse_flags),
        "parse_flag_counts": p_flag_counts,
        "reviews": review_counts,
        "elapsed": round(time.time() - start, 2),
    }


# ---------------------------------------------------------------------------
# Normalize — tracks ALL fields including seller/buyer/owner/alt blocks
# ---------------------------------------------------------------------------

def collect_normalize_metrics() -> dict[str, Any]:
    start = time.time()
    from cleo.normalize.versioning import store as norm_store

    version = norm_store.active_version()
    norm_dir = norm_store.active_dir()

    if not norm_dir or not norm_dir.exists():
        return {"stage": "normalized", "version": version, "total_records": 0}

    records = []
    for f in norm_dir.glob("*.json"):
        if f.stem == "_meta":
            continue
        try:
            records.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass

    total = len(records)
    if total == 0:
        return {"stage": "normalized", "version": version, "total_records": 0}

    # Source breakdown
    by_source: dict[str, int] = {}
    for rec in records:
        src = rec.get("source", "unknown")
        by_source[src] = by_source.get(src, 0) + 1

    # Category / city_status / scope breakdowns (property block)
    categories: dict[str, int] = {}
    city_statuses: dict[str, int] = {}
    scopes: dict[str, int] = {}

    # Field coverage on property block — all fields
    prop_fields = {
        "raw_address": 0,
        "street_number": 0,
        "street_name": 0,
        "street_suffix": 0,
        "street_direction": 0,
        "unit": 0,
        "unit_type": 0,
        "po_box": 0,
        "rural_route": 0,
        "building_name": 0,
        "normalized_city": 0,
        "normalized_postal_code": 0,
        "normalized_province": 0,
        "raw_city": 0,
        "municipality": 0,
        "raw_coords": 0,
    }

    # Block presence counts
    has_seller = 0
    has_buyer = 0
    has_owner_addr = 0
    has_property_alt = 0

    # Source-specific metadata
    has_gw_id = 0
    has_pin = 0
    has_owner_name = 0
    has_owner_care_of = 0
    has_owner_contacts = 0
    has_brand = 0
    has_brand_id = 0
    has_store_name = 0

    for rec in records:
        prop = rec.get("property", {})
        cat = prop.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

        cs = prop.get("city_status", "unknown")
        city_statuses[cs] = city_statuses.get(cs, 0) + 1

        scope = prop.get("address_scope", "unknown")
        scopes[scope] = scopes.get(scope, 0) + 1

        for field in prop_fields:
            if prop.get(field):
                prop_fields[field] += 1

        if rec.get("seller"):
            has_seller += 1
        if rec.get("buyer"):
            has_buyer += 1
        if rec.get("owner_address"):
            has_owner_addr += 1
        if rec.get("property_alt"):
            has_property_alt += 1

        # Source-specific
        if rec.get("gw_id"):
            has_gw_id += 1
        if rec.get("pin"):
            has_pin += 1
        if rec.get("owner_name"):
            has_owner_name += 1
        if rec.get("owner_care_of"):
            has_owner_care_of += 1
        if rec.get("owner_contacts"):
            has_owner_contacts += 1
        if rec.get("brand"):
            has_brand += 1
        if rec.get("brand_id"):
            has_brand_id += 1
        if rec.get("store_name"):
            has_store_name += 1

    prop_coverage = {
        k: _coverage_entry(v, total)
        for k, v in prop_fields.items()
    }

    # Per-role address block field coverage
    seller_coverage = _address_block_coverage(records, "seller")
    buyer_coverage = _address_block_coverage(records, "buyer")
    owner_address_coverage = _address_block_coverage(records, "owner_address")

    return {
        "stage": "normalized",
        "version": version,
        "total_records": total,
        "by_source": by_source,
        "categories": categories,
        "city_statuses": city_statuses,
        "address_scopes": scopes,
        "property_field_coverage": prop_coverage,
        "has_seller": has_seller,
        "has_buyer": has_buyer,
        "has_owner_address": has_owner_addr,
        "has_property_alt": has_property_alt,
        "seller_field_coverage": seller_coverage,
        "buyer_field_coverage": buyer_coverage,
        "owner_address_field_coverage": owner_address_coverage,
        # Source-specific metadata
        "gw_metadata": {
            "gw_id": _coverage_entry(has_gw_id, total),
            "pin": _coverage_entry(has_pin, total),
            "owner_name": _coverage_entry(has_owner_name, total),
            "owner_care_of": _coverage_entry(has_owner_care_of, total),
            "owner_contacts": _coverage_entry(has_owner_contacts, total),
        },
        "brand_metadata": {
            "brand": _coverage_entry(has_brand, total),
            "brand_id": _coverage_entry(has_brand_id, total),
            "store_name": _coverage_entry(has_store_name, total),
        },
        "elapsed": round(time.time() - start, 2),
    }


# ---------------------------------------------------------------------------
# Expand — tracks address-level field coverage
# ---------------------------------------------------------------------------

def collect_expand_metrics() -> dict[str, Any]:
    start = time.time()
    from cleo.expand.versioning import store as exp_store

    version = exp_store.active_version()
    exp_dir = exp_store.active_dir()

    if not exp_dir or not exp_dir.exists():
        return {"stage": "expanded", "version": version, "total_records": 0}

    total_records = 0
    total_addresses = 0
    skip_geocode_count = 0
    compound_splits = 0  # records with >1 property address
    by_source: dict[str, int] = {}
    addresses_per_record: dict[int, int] = {}  # count -> frequency

    roles_present = {"property": 0, "property_alt": 0, "seller": 0, "buyer": 0, "owner_address": 0}

    # Address-level field coverage (across ALL addresses in ALL roles)
    addr_fields = {
        "street_number": 0, "street_name": 0, "street_suffix": 0,
        "street_direction": 0, "unit": 0, "unit_type": 0,
        "city": 0, "province": 0, "postal_code": 0,
        "canonical": 0,
    }
    has_raw_coords = 0

    all_addresses: list[dict] = []

    for f in exp_dir.glob("*.json"):
        if f.stem == "_meta":
            continue
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue

        total_records += 1
        src = rec.get("source", "unknown")
        by_source[src] = by_source.get(src, 0) + 1

        if rec.get("raw_coords"):
            has_raw_coords += 1

        # Count addresses in property block
        prop = rec.get("property", {})
        addrs = prop.get("addresses", [])
        n_prop_addrs = len(addrs)

        if n_prop_addrs > 1:
            compound_splits += 1

        for role in roles_present:
            block = rec.get(role)
            if role == "property_alt":
                if block and isinstance(block, list) and len(block) > 0:
                    roles_present[role] += 1
                    for alt in block:
                        alt_addrs = alt.get("addresses", [])
                        total_addresses += len(alt_addrs)
                        all_addresses.extend(alt_addrs)
                        for a in alt_addrs:
                            if a.get("skip_geocode"):
                                skip_geocode_count += 1
            elif block and isinstance(block, dict) and "addresses" in block:
                roles_present[role] += 1
                role_addrs = block.get("addresses", [])
                total_addresses += len(role_addrs)
                all_addresses.extend(role_addrs)
                for a in role_addrs:
                    if a.get("skip_geocode"):
                        skip_geocode_count += 1

        # Track address distribution
        bucket = min(n_prop_addrs, 10)  # cap at 10+
        addresses_per_record[bucket] = addresses_per_record.get(bucket, 0) + 1

    # Compute address-level field coverage
    for a in all_addresses:
        for f in addr_fields:
            if a.get(f):
                addr_fields[f] += 1

    addr_total = len(all_addresses)
    address_field_coverage = {
        k: _coverage_entry(v, addr_total)
        for k, v in addr_fields.items()
    }

    return {
        "stage": "expanded",
        "version": version,
        "total_records": total_records,
        "total_addresses": total_addresses,
        "skip_geocode": skip_geocode_count,
        "geocodable": total_addresses - skip_geocode_count,
        "compound_splits": compound_splits,
        "by_source": by_source,
        "roles_present": roles_present,
        "addresses_per_record_distribution": dict(sorted(addresses_per_record.items())),
        "address_field_coverage": address_field_coverage,
        "has_raw_coords": has_raw_coords,
        "elapsed": round(time.time() - start, 2),
    }


# ---------------------------------------------------------------------------
# Geocode — tracks match_code sub-fields
# ---------------------------------------------------------------------------

def collect_geocode_metrics() -> dict[str, Any]:
    start = time.time()

    if not COORDINATES_PATH.exists():
        return {"stage": "geocoded", "total_addresses": 0}

    from cleo.geocode.store import CoordinateStore
    cs = CoordinateStore(COORDINATES_PATH)

    total = len(cs.addresses)
    with_coords = 0
    by_provider: dict[str, int] = {}
    accuracy_counts: dict[str, int] = {}
    confidence_counts: dict[str, int] = {}
    multi_provider = 0

    # Match code sub-field distributions
    match_code_fields = {
        "address_number": {},
        "street": {},
        "postcode": {},
        "place": {},
        "region": {},
        "locality": {},
        "country": {},
    }

    for addr_key in cs.addresses:
        entry = cs.get(addr_key)
        if not entry:
            continue

        best = cs.best_coords(addr_key)
        if best is not None:
            with_coords += 1

        providers_with_data = []
        for provider in ["mapbox", "geocodio", "here", "scraper"]:
            if provider in entry and entry[provider].get("lat") is not None:
                providers_with_data.append(provider)
                by_provider[provider] = by_provider.get(provider, 0) + 1

                # Accuracy (mapbox-specific)
                if provider == "mapbox":
                    acc = entry[provider].get("accuracy", "unknown")
                    accuracy_counts[acc] = accuracy_counts.get(acc, 0) + 1
                    mc = entry[provider].get("match_code", {})
                    if isinstance(mc, dict):
                        conf = mc.get("confidence", "unknown")
                        confidence_counts[conf] = confidence_counts.get(conf, 0) + 1
                        # Sub-field distributions
                        for mf in match_code_fields:
                            val = mc.get(mf, "unknown")
                            match_code_fields[mf][val] = match_code_fields[mf].get(val, 0) + 1
                    else:
                        confidence_counts["unknown"] = confidence_counts.get("unknown", 0) + 1

        if len(providers_with_data) > 1:
            multi_provider += 1

    # Store meta
    meta = {}
    raw = _load_json(COORDINATES_PATH)
    if isinstance(raw, dict) and "meta" in raw:
        meta = raw["meta"]

    return {
        "stage": "geocoded",
        "total_addresses": total,
        "with_coords": with_coords,
        "missing_coords": total - with_coords,
        "coverage_pct": round(with_coords / total * 100, 1) if total else 0,
        "by_provider": by_provider,
        "multi_provider": multi_provider,
        "accuracy": accuracy_counts,
        "confidence": confidence_counts,
        "match_code_detail": match_code_fields,
        "meta": meta,
        "elapsed": round(time.time() - start, 2),
    }


# ---------------------------------------------------------------------------
# Parcels — tracks provincial_raw + municipal parcels + services + index
# ---------------------------------------------------------------------------

def collect_parcel_metrics() -> dict[str, Any]:
    start = time.time()
    raw_path = PARCELS_DIR / "provincial_raw.json"
    parcels_path = PARCELS_DIR / "parcels.json"
    queried_path = PARCELS_DIR / "queried_points.json"
    services_path = PARCELS_DIR / "services.json"
    index_path = PARCELS_DIR / "property_parcel_index.json"
    cache_path = PARCELS_DIR / "parcel_cache.json"

    result: dict[str, Any] = {"stage": "parcels"}

    # Provincial raw
    if raw_path.exists():
        try:
            data = json.loads(raw_path.read_text(encoding="utf-8"))
            meta = data.get("meta", {})
            features = data.get("features", [])
            result["provincial_total"] = meta.get("total", len(features))
            result["provincial_by_municipality"] = meta.get("by_municipality", {})

            # Count unique ARNs
            arns = set()
            for feat in features:
                arn = feat.get("properties", {}).get("ASSESSMENT_ROLL_NUMBER")
                if arn:
                    arns.add(str(arn))
            result["unique_arns"] = len(arns)

            # Property-to-parcel mapping
            p2p = data.get("property_to_parcel", {})
            result["provincial_property_links"] = len(p2p)
            no_cov = data.get("no_coverage", [])
            result["provincial_no_coverage"] = len(no_cov)
        except Exception:
            result["provincial_total"] = 0
    else:
        result["provincial_total"] = 0

    # Municipal parcels (parcels.json)
    if parcels_path.exists():
        try:
            data = json.loads(parcels_path.read_text(encoding="utf-8"))
            meta = data.get("meta", {})
            features = data.get("features", [])
            result["municipal_total"] = meta.get("total", len(features))
            result["municipal_by_municipality"] = meta.get("by_municipality", {})

            # Field coverage on municipal features
            muni_with_arn = 0
            muni_with_address = 0
            muni_with_zoning = 0
            muni_with_assessment = 0
            for feat in features:
                props = feat.get("properties", {})
                if props.get("arn"):
                    muni_with_arn += 1
                if props.get("address"):
                    muni_with_address += 1
                if props.get("zoning") or props.get("property_use"):
                    muni_with_zoning += 1
                if props.get("assessment"):
                    muni_with_assessment += 1
            muni_total = len(features)
            result["municipal_field_coverage"] = {
                "arn": _coverage_entry(muni_with_arn, muni_total),
                "address": _coverage_entry(muni_with_address, muni_total),
                "zoning": _coverage_entry(muni_with_zoning, muni_total),
                "assessment": _coverage_entry(muni_with_assessment, muni_total),
            }

            p2p = data.get("property_to_parcel", {})
            result["municipal_property_links"] = len(p2p)
        except Exception:
            result["municipal_total"] = 0
    else:
        result["municipal_total"] = 0

    # Queried points
    queried_data = _load_json(queried_path)
    if queried_data:
        result["queried_points"] = queried_data.get("total", 0)
    else:
        result["queried_points"] = 0

    # Services registry
    services = _load_json(services_path)
    if services and isinstance(services, dict):
        result["services_total"] = len(services)
    else:
        result["services_total"] = 0

    # Property-parcel index
    idx = _load_json(index_path)
    if idx and isinstance(idx, dict):
        result["property_parcel_index_total"] = len(idx)
    else:
        result["property_parcel_index_total"] = 0

    # Parcel cache
    cache = _load_json(cache_path)
    if cache and isinstance(cache, dict):
        result["parcel_cache_total"] = len(cache.get("parcels", cache))
    else:
        result["parcel_cache_total"] = 0

    # File sizes
    for label, path in [("provincial_raw", raw_path), ("municipal_parcels", parcels_path)]:
        if path.exists():
            result[f"{label}_size_mb"] = round(path.stat().st_size / 1024 / 1024, 1)

    result["elapsed"] = round(time.time() - start, 2)
    return result


# ---------------------------------------------------------------------------
# Properties — tracks ALL fields
# ---------------------------------------------------------------------------

def collect_property_metrics() -> dict[str, Any]:
    start = time.time()
    props_path = DATA_DIR / "properties.json"

    if not props_path.exists():
        return {"stage": "properties", "total": 0}

    data = _load_json(props_path) or {}
    props = data.get("properties", {})
    meta = data.get("meta", {})

    total = len(props)
    if total == 0:
        return {"stage": "properties", "total": 0, "meta": meta}

    # Track every field
    field_counts: dict[str, int] = {}
    prop_field_names = [
        "address", "city", "municipality", "province", "postal_code",
        "lat", "lng", "building_sf", "site_area",
        "rt_ids", "sources", "transaction_count", "created", "updated",
        # GW enrichment
        "gw_ids", "gw_data",
        # Footprint enrichment
        "footprint_id", "footprint_area_sqm", "footprint_match_method", "footprint_snap_source",
        "pre_snap_lat", "pre_snap_lng",
        # Operators
        "operator_ids",
        # Pipeline
        "pipeline_status",
    ]
    for fn in prop_field_names:
        field_counts[fn] = 0

    with_coords = 0
    multi_tx = 0
    total_rt_ids = 0
    by_source: dict[str, int] = {}
    tx_count_dist: dict[int, int] = {}

    # GW data sub-field tracking
    gw_data_fields: dict[str, int] = {}

    for pid, p in props.items():
        # Field presence
        for fn in prop_field_names:
            val = p.get(fn)
            if val is not None and val != "" and val != [] and val != {}:
                field_counts[fn] += 1

        if p.get("lat") is not None and p.get("lng") is not None:
            with_coords += 1

        rt_ids = p.get("rt_ids", [])
        n = len(rt_ids)
        total_rt_ids += n
        if n > 1:
            multi_tx += 1

        bucket = min(n, 5)
        tx_count_dist[bucket] = tx_count_dist.get(bucket, 0) + 1

        for src in p.get("sources", []):
            by_source[src] = by_source.get(src, 0) + 1

        # GW data sub-fields
        gw = p.get("gw_data", {})
        if isinstance(gw, dict) and gw:
            for gk in gw:
                if gw[gk] is not None and gw[gk] != "" and gw[gk] != []:
                    gw_data_fields[gk] = gw_data_fields.get(gk, 0) + 1

    field_coverage = {k: _coverage_entry(v, total) for k, v in field_counts.items()}

    # Brand matches
    brand_matches = _load_json(DATA_DIR / "brand_matches.json") or {}
    brand_matched = len(brand_matches) if isinstance(brand_matches, dict) else 0

    # GW sub-field coverage
    gw_total = field_counts.get("gw_data", 0)
    gw_data_coverage = {
        k: _coverage_entry(v, gw_total)
        for k, v in gw_data_fields.items()
    } if gw_total else {}

    return {
        "stage": "properties",
        "total": total,
        "meta": meta,
        "with_coords": with_coords,
        "with_coords_pct": round(with_coords / total * 100, 1) if total else 0,
        "field_coverage": field_coverage,
        "gw_data_coverage": gw_data_coverage,
        "multi_transaction": multi_tx,
        "total_rt_ids_linked": total_rt_ids,
        "by_source": by_source,
        "transaction_count_distribution": dict(sorted(tx_count_dist.items())),
        "brand_matched": brand_matched,
        "elapsed": round(time.time() - start, 2),
    }


# ---------------------------------------------------------------------------
# Parties — tracks ALL actual fields (is_company, not "type")
# ---------------------------------------------------------------------------

def collect_party_metrics() -> dict[str, Any]:
    start = time.time()
    parties_path = DATA_DIR / "parties.json"

    if not parties_path.exists():
        return {"stage": "parties", "total": 0}

    data = _load_json(parties_path) or {}
    meta = data.get("meta", {})
    parties = data.get("parties", {})

    total = len(parties)
    if total == 0:
        return {"stage": "parties", "total": 0, "meta": meta}

    # Track every field
    companies = 0
    persons = 0
    with_phone = 0
    with_address = 0
    with_contacts = 0
    with_aliases = 0
    with_alternate_names = 0
    with_operator_ids = 0
    with_display_override = 0

    total_appearances = 0
    total_buy = 0
    total_sell = 0
    total_rt_ids = 0

    # Appearance detail tracking
    appearance_with_sale_price = 0
    appearance_with_prop_address = 0
    appearance_with_sale_date = 0

    for gid, p in parties.items():
        if p.get("is_company"):
            companies += 1
        else:
            persons += 1

        if p.get("phones"):
            with_phone += 1
        if p.get("addresses"):
            with_address += 1
        if p.get("contacts"):
            with_contacts += 1
        if p.get("aliases"):
            with_aliases += 1
        if p.get("alternate_names"):
            with_alternate_names += 1
        if p.get("operator_ids"):
            with_operator_ids += 1
        if p.get("display_name_override"):
            with_display_override += 1

        total_buy += p.get("buy_count", 0)
        total_sell += p.get("sell_count", 0)
        total_rt_ids += len(p.get("rt_ids", []))

        apps = p.get("appearances", [])
        total_appearances += len(apps)
        for app in apps:
            if app.get("sale_price"):
                appearance_with_sale_price += 1
            if app.get("prop_address"):
                appearance_with_prop_address += 1
            if app.get("sale_date_iso"):
                appearance_with_sale_date += 1

    return {
        "stage": "parties",
        "total": total,
        "meta": meta,
        "companies": companies,
        "persons": persons,
        "with_phone": with_phone,
        "with_address": with_address,
        "with_contacts": with_contacts,
        "with_aliases": with_aliases,
        "with_alternate_names": with_alternate_names,
        "with_operator_ids": with_operator_ids,
        "with_display_override": with_display_override,
        "total_appearances": total_appearances,
        "total_buy_count": total_buy,
        "total_sell_count": total_sell,
        "total_rt_ids_linked": total_rt_ids,
        "appearance_coverage": {
            "sale_price": _coverage_entry(appearance_with_sale_price, total_appearances),
            "prop_address": _coverage_entry(appearance_with_prop_address, total_appearances),
            "sale_date_iso": _coverage_entry(appearance_with_sale_date, total_appearances),
        },
        "elapsed": round(time.time() - start, 2),
    }


# ---------------------------------------------------------------------------
# GeoWarehouse — tracks ALL blocks: summary, registry, site_structure, sales
# ---------------------------------------------------------------------------

def collect_gw_metrics() -> dict[str, Any]:
    start = time.time()
    gw_html_dir = DATA_DIR / "gw_html"
    gw_parsed_dir = DATA_DIR / "gw_parsed"

    html_count = 0
    if gw_html_dir.exists():
        html_count = sum(1 for f in gw_html_dir.glob("*.html"))

    # Find active or v001
    parsed_dir = gw_parsed_dir / "active"
    if not parsed_dir.exists():
        parsed_dir = gw_parsed_dir / "v001"

    parsed_count = 0
    unique_pins = set()

    # Summary block fields
    summary_fields: dict[str, int] = {
        "address": 0, "owner_names": 0, "last_sale_price": 0,
        "last_sale_date": 0, "lot_size_area": 0, "lot_size_perimeter": 0,
        "party_to": 0, "legal_description": 0,
    }

    # Registry block fields
    registry_fields: dict[str, int] = {
        "gw_address": 0, "land_registry_office": 0, "owner_names": 0,
        "ownership_type": 0, "land_registry_status": 0, "property_type": 0,
        "registration_type": 0, "pin": 0,
    }

    # Site structure fields
    site_fields: dict[str, int] = {
        "arn": 0, "frontage": 0, "zoning": 0, "depth": 0,
        "property_description": 0, "property_code": 0,
        "current_assessed_value": 0, "valuation_date": 0,
        "assessment_legal_description": 0, "site_area": 0,
        "property_address": 0, "municipality": 0,
        "owner_names_mpac": 0, "owner_mailing_address": 0,
    }

    # Sales history
    with_sales_history = 0
    total_sales_entries = 0
    has_gw_id = 0

    if parsed_dir.exists():
        for f in parsed_dir.glob("*.json"):
            if f.stem == "_meta":
                continue
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            parsed_count += 1
            pin = rec.get("pin")
            if pin:
                unique_pins.add(pin)
            if rec.get("gw_id"):
                has_gw_id += 1

            # Summary
            summary = rec.get("summary", {})
            for sf in summary_fields:
                if summary.get(sf):
                    summary_fields[sf] += 1

            # Registry
            registry = rec.get("registry", {})
            for rf in registry_fields:
                if registry.get(rf):
                    registry_fields[rf] += 1

            # Site structure
            ss = rec.get("site_structure", {})
            for ssf in site_fields:
                if ss.get(ssf):
                    site_fields[ssf] += 1

            # Sales history
            sales = rec.get("sales_history", [])
            if sales:
                with_sales_history += 1
                total_sales_entries += len(sales)

    return {
        "stage": "geowarehouse",
        "html_files": html_count,
        "parsed_records": parsed_count,
        "unique_pins": len(unique_pins),
        "has_gw_id": has_gw_id,
        "summary_coverage": {
            k: _coverage_entry(v, parsed_count)
            for k, v in summary_fields.items()
        },
        "registry_coverage": {
            k: _coverage_entry(v, parsed_count)
            for k, v in registry_fields.items()
        },
        "site_structure_coverage": {
            k: _coverage_entry(v, parsed_count)
            for k, v in site_fields.items()
        },
        "with_sales_history": with_sales_history,
        "total_sales_entries": total_sales_entries,
        "avg_sales_per_record": round(total_sales_entries / parsed_count, 1) if parsed_count else 0,
        "elapsed": round(time.time() - start, 2),
    }


# ---------------------------------------------------------------------------
# Brands — tracks ALL fields
# ---------------------------------------------------------------------------

def collect_brand_metrics() -> dict[str, Any]:
    start = time.time()
    brands_dir = Path(DATA_DIR).parent / "brands" / "data"

    if not brands_dir.exists():
        return {"stage": "brands", "total_brands": 0, "total_stores": 0}

    total_brands = 0
    total_stores = 0
    with_coords = 0
    with_phone = 0
    with_postal = 0
    with_store_name = 0
    with_address = 0
    with_city = 0
    with_province = 0
    with_source_url = 0
    by_brand: dict[str, int] = {}

    for f in sorted(brands_dir.glob("*.json")):
        try:
            stores = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(stores, list):
            continue

        brand_name = f.stem
        total_brands += 1
        count = len(stores)
        by_brand[brand_name] = count
        total_stores += count

        for s in stores:
            if s.get("lat") is not None and s.get("lng") is not None:
                with_coords += 1
            if s.get("phone"):
                with_phone += 1
            if s.get("postal_code"):
                with_postal += 1
            if s.get("store_name"):
                with_store_name += 1
            if s.get("address"):
                with_address += 1
            if s.get("city"):
                with_city += 1
            if s.get("province"):
                with_province += 1
            if s.get("source_url"):
                with_source_url += 1

    field_coverage = {
        "coords": _coverage_entry(with_coords, total_stores),
        "phone": _coverage_entry(with_phone, total_stores),
        "postal_code": _coverage_entry(with_postal, total_stores),
        "store_name": _coverage_entry(with_store_name, total_stores),
        "address": _coverage_entry(with_address, total_stores),
        "city": _coverage_entry(with_city, total_stores),
        "province": _coverage_entry(with_province, total_stores),
        "source_url": _coverage_entry(with_source_url, total_stores),
    }

    return {
        "stage": "brands",
        "total_brands": total_brands,
        "total_stores": total_stores,
        "field_coverage": field_coverage,
        "top_brands": dict(sorted(by_brand.items(), key=lambda x: -x[1])[:20]),
        "elapsed": round(time.time() - start, 2),
    }


# ---------------------------------------------------------------------------
# Collect All
# ---------------------------------------------------------------------------

def collect_all() -> dict[str, Any]:
    """Run all collectors and return combined metrics."""
    collected_at = datetime.now().isoformat(timespec="seconds")

    metrics = {
        "collected_at": collected_at,
        "ingest": collect_ingest_metrics(),
        "parsed": collect_parse_metrics(),
        "normalized": collect_normalize_metrics(),
        "expanded": collect_expand_metrics(),
        "geocoded": collect_geocode_metrics(),
        "parcels": collect_parcel_metrics(),
        "properties": collect_property_metrics(),
        "geowarehouse": collect_gw_metrics(),
        "brands": collect_brand_metrics(),
        # Legacy / frozen — collected but separated from active pipeline
        "legacy": {
            "parties": collect_party_metrics(),
        },
    }

    return metrics
