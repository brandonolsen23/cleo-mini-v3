"""Normalization engine: reads all address sources and produces normalized output.

All address sources (Realtrack, brands, GeoWarehouse) flow through this engine.
Each source has its own adapter that extracts raw fields and feeds them through
the core normalizer (cleo.normalize.address). Output is a unified set of
normalized JSON files written to the same versioned directory.

Record ID conventions:
    RT*       — Realtrack transaction records (15,805)
    BR_*      — Brand store locations (14,000+)
    GW*       — GeoWarehouse property records (449)
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, List

from cleo.normalize.address import (
    normalize_from_fields,
    normalize_from_mpac,
    normalize_from_string,
)

logger = logging.getLogger(__name__)


# ── Source adapters ──


def _normalize_rt_record(data: Dict, source_version: str) -> Dict:
    """Normalize all addresses in a single parsed Realtrack record."""
    addr = data.get("transaction", {}).get("address", {})

    # Property address — fields are already split by the parser
    property_result = normalize_from_fields(
        address=addr.get("address", ""),
        city=addr.get("city", "") or addr.get("municipality", ""),
        province=addr.get("province", "Ontario"),
        postal_code=addr.get("postal_code", ""),
        unit=addr.get("address_suite", ""),
    )

    # Carry through raw city and municipality for reference
    raw_city = addr.get("city", "")
    municipality = addr.get("municipality", "")
    if raw_city:
        property_result["raw_city"] = raw_city
    if municipality and municipality != raw_city:
        property_result["municipality"] = municipality

    # Alternate property addresses — normalized with same city/province as main property
    alt_addresses = addr.get("alternate_addresses", [])
    property_alt = []
    for alt_raw in alt_addresses:
        if not alt_raw or not alt_raw.strip():
            continue
        alt_result = normalize_from_fields(
            address=alt_raw,
            city=addr.get("city", "") or addr.get("municipality", ""),
            province=addr.get("province", "Ontario"),
        )
        if raw_city:
            alt_result["raw_city"] = raw_city
        if municipality and municipality != raw_city:
            alt_result["municipality"] = municipality
        property_alt.append(alt_result)

    # Seller address — comma-separated string from the parser
    seller_raw = data.get("transferor", {}).get("address", "")
    seller_result = None
    if seller_raw:
        seller_result = normalize_from_string(
            raw=seller_raw,
            category_hint="corporate_seller",
        )

    # Buyer address — comma-separated string from the parser
    buyer_raw = data.get("transferee", {}).get("address", "")
    buyer_result = None
    if buyer_raw:
        buyer_result = normalize_from_string(
            raw=buyer_raw,
            category_hint="corporate_buyer",
        )

    result = {
        "rt_id": data.get("rt_id", ""),
        "source": "realtrack",
        "source_version": source_version,
        "property": property_result,
    }
    if property_alt:
        result["property_alt"] = property_alt
    if seller_result:
        result["seller"] = seller_result
    if buyer_result:
        result["buyer"] = buyer_result

    return result


_UNIT_IN_CITY_RE = re.compile(
    r"^(?:UNIT|SUITE|STE|APT)\s*#?\s*(.+)$",
    re.IGNORECASE,
)


def _normalize_brand_record(store: Dict, brand_file: str) -> Dict:
    """Normalize a single brand store location."""
    raw_coords = None
    if store.get("lat") and store.get("lng"):
        raw_coords = {
            "lat": store["lat"],
            "lng": store["lng"],
            "source": "brand_scraper",
        }

    address = store.get("address", "")
    city = store.get("city", "")
    unit_override = ""

    # Detect unit data jammed into the city field (e.g. "UNIT 1", "UNIT D108 BURLINGTON")
    m = _UNIT_IN_CITY_RE.match(city.strip())
    if m:
        remainder = m.group(1).strip()
        # Check if a real city name follows the unit (e.g. "UNIT D108 BURLINGTON")
        parts = remainder.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].isalpha() and len(parts[1]) > 2:
            unit_override = parts[0].strip().lstrip("#")
            city = parts[1].strip()
        else:
            unit_override = remainder.lstrip("#")
            city = ""

    property_result = normalize_from_fields(
        address=address,
        city=city,
        province=store.get("province", "ON"),
        postal_code=store.get("postal_code", ""),
        unit=unit_override,
        category_hint="brand",
        raw_coords=raw_coords,
    )

    return {
        "source": "brand",
        "source_file": brand_file,
        "brand": store.get("brand", ""),
        "store_name": store.get("store_name", ""),
        "property": property_result,
    }


def _normalize_gw_record(data: Dict) -> Dict:
    """Normalize a single GeoWarehouse property record.

    Produces both a property address and an owner mailing address
    (if available in site_structure.owner_mailing_address).
    Also extracts C/O and ATTN names, classifying them as person or company.
    """
    from cleo.utils.text import is_company_name as _is_company_name

    ss = data.get("site_structure", {})
    summary = data.get("summary", {})
    registry = data.get("registry", {})

    property_result = normalize_from_mpac(
        property_address=ss.get("property_address", ""),
        municipality=ss.get("municipality", ""),
        summary_address=summary.get("address", ""),
    )

    result = {
        "gw_id": data.get("gw_id", ""),
        "source": "geowarehouse",
        "pin": data.get("pin", ""),
        "property": property_result,
    }

    # Owner name from registry/MPAC
    owner_name = (
        registry.get("owner_names", "")
        or ss.get("owner_names_mpac", "")
        or ""
    ).strip()
    if owner_name and owner_name != "N/A":
        result["owner_name"] = owner_name

    # Owner mailing address — same MPAC flat format but no municipality hint
    owner_addr = ss.get("owner_mailing_address", "").strip()
    if owner_addr and owner_addr.upper() != "N/A":
        owner_result = normalize_from_mpac(
            property_address=owner_addr,
            municipality="",  # no hint — city detected from string
        )
        owner_result["raw_address"] = owner_addr

        # Classify extracted names from C/O, ATTN, or prefix patterns
        _NON_PERSON_WORDS = {
            # Departments / routing
            "DEPARTMENT", "DEPT", "HEADQUARTERS", "OFFICE", "DIVISION",
            # Buildings / locations
            "TOWER", "TOWERS", "HALL", "PLAZA", "MALL", "COURT",
            "COLONNADE", "CENTRE", "CENTER",
            # Store brands that aren't companies by keyword
            "IGA",
        }
        extracted = owner_result.pop("_extracted_names", [])
        contacts = []
        care_of_companies = []
        for entry in extracted:
            name = entry["name"]
            source = entry["source"]
            # Filter out department/building/routing text
            name_words = set(name.upper().split())
            if name_words & _NON_PERSON_WORDS:
                care_of_companies.append(name)
                continue
            is_company = _is_company_name(name)
            if is_company:
                care_of_companies.append(name)
            else:
                contacts.append(name)

        if contacts:
            result["owner_contacts"] = contacts
        if care_of_companies:
            result["owner_care_of"] = care_of_companies

        result["owner_address"] = owner_result

    return result


# ── Main normalize loop ──


def normalize_all(
    source_dir: Path,
    output_dir: Path,
    source_version: str = "",
    brands_dir: Path | None = None,
    gw_dir: Path | None = None,
    skip_brand_files: set[str] | None = None,
) -> Dict:
    """Normalize addresses from all sources into a single output directory.

    Sources:
        source_dir  — Realtrack parsed JSON (RT*.json)
        brands_dir  — Brand scraper JSON (*.json, each file = array of stores)
        gw_dir      — GeoWarehouse parsed JSON (GW*.json)

    Returns summary: {total, normalized, errors, by_source, categories, elapsed}
    """
    start = time.time()
    total = 0
    normalized = 0
    errors = 0
    error_ids: List[str] = []
    categories: Dict[str, int] = {}
    by_source: Dict[str, int] = {}

    def _write(record_id: str, result: Dict, source_label: str) -> None:
        nonlocal total, normalized, errors
        total += 1
        try:
            cat = result.get("property", {}).get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
            by_source[source_label] = by_source.get(source_label, 0) + 1

            out_path = output_dir / f"{record_id}.json"
            out_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            normalized += 1
        except Exception as e:
            errors += 1
            error_ids.append(record_id)
            logger.error("Error normalizing %s: %s", record_id, e)

    # ── Realtrack records ──
    rt_files = sorted(source_dir.glob("*.json"))
    for src_path in rt_files:
        if src_path.stem == "_meta":
            continue
        try:
            data = json.loads(src_path.read_text(encoding="utf-8"))
            result = _normalize_rt_record(data, source_version)
            _write(src_path.stem, result, "realtrack")
        except Exception as e:
            errors += 1
            total += 1
            error_ids.append(src_path.stem)
            logger.error("Error normalizing RT %s: %s", src_path.stem, e)

        if total % 2000 == 0:
            logger.info("Progress: %d RT records", total)

    logger.info("Realtrack: %d records", by_source.get("realtrack", 0))

    # ── Brand records ──
    if brands_dir and brands_dir.is_dir():
        _skip = skip_brand_files or set()
        brand_idx = 0
        for brand_path in sorted(brands_dir.glob("*.json")):
            if brand_path.name in _skip:
                logger.info("Skipping brand file %s (excluded)", brand_path.name)
                continue
            try:
                stores = json.loads(brand_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error("Error reading brand file %s: %s", brand_path.name, e)
                continue

            if not isinstance(stores, list):
                continue

            for store in stores:
                brand_idx += 1
                brand_id = f"BR_{brand_idx:05d}"
                try:
                    result = _normalize_brand_record(store, brand_path.name)
                    result["brand_id"] = brand_id
                    _write(brand_id, result, "brand")
                except Exception as e:
                    errors += 1
                    total += 1
                    error_ids.append(brand_id)
                    logger.error("Error normalizing brand %s: %s", brand_id, e)

        logger.info("Brands: %d records", by_source.get("brand", 0))

    # ── GeoWarehouse records ──
    if gw_dir and gw_dir.is_dir():
        gw_active = gw_dir / "active"
        gw_source = gw_active if gw_active.is_dir() else None

        # Fall back to highest version dir
        if not gw_source:
            versions = sorted(
                [d for d in gw_dir.iterdir() if d.is_dir() and d.name.startswith("v")],
                key=lambda d: d.name,
            )
            if versions:
                gw_source = versions[-1]

        if gw_source:
            for gw_path in sorted(gw_source.glob("*.json")):
                if gw_path.stem == "_meta":
                    continue
                try:
                    data = json.loads(gw_path.read_text(encoding="utf-8"))
                    result = _normalize_gw_record(data)
                    _write(gw_path.stem, result, "geowarehouse")
                except Exception as e:
                    errors += 1
                    total += 1
                    error_ids.append(gw_path.stem)
                    logger.error("Error normalizing GW %s: %s", gw_path.stem, e)

            logger.info("GeoWarehouse: %d records", by_source.get("geowarehouse", 0))

    elapsed = time.time() - start
    logger.info(
        "Done: %d normalized (%s), %d errors in %.1fs",
        normalized,
        ", ".join(f"{k}={v}" for k, v in sorted(by_source.items())),
        errors,
        elapsed,
    )

    return {
        "total": total,
        "normalized": normalized,
        "errors": errors,
        "error_ids": error_ids,
        "by_source": by_source,
        "categories": dict(sorted(categories.items(), key=lambda x: -x[1])),
        "elapsed": elapsed,
    }
