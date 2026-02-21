"""Extraction engine: reads parsed JSON and produces geocodable address expansions."""

import json
import logging
import time
from pathlib import Path
from typing import Dict, List

from .address_expander import expand_compound_address, is_legal_description, is_po_box, normalize_party_address

logger = logging.getLogger(__name__)


def _extract_record(data: Dict, source_version: str) -> Dict:
    """Extract geocodable addresses from a single parsed record."""
    addr = data.get("transaction", {}).get("address", {})
    city = addr.get("city", "")
    province = addr.get("province", "Ontario")

    # Property addresses: primary + alternates
    property_addresses: List[Dict] = []

    primary = addr.get("address", "")
    if primary:
        expanded = expand_compound_address(primary, city, province)
        entry = {"original": primary, "expanded": expanded}
        if is_po_box(primary) or is_legal_description(primary):
            entry["skip_geocode"] = True
        property_addresses.append(entry)

    for alt in addr.get("alternate_addresses", []):
        if alt:
            expanded = expand_compound_address(alt, city, province)
            entry = {"original": alt, "expanded": expanded}
            if is_po_box(alt) or is_legal_description(alt):
                entry["skip_geocode"] = True
            property_addresses.append(entry)

    # Promote addresses with street numbers to the front
    property_addresses.sort(
        key=lambda a: 0 if a["expanded"] and a["expanded"][0][:1].isdigit() else 1
    )

    # Seller address (simple normalization)
    seller_addr = data.get("transferor", {}).get("address", "")
    seller = {
        "original": seller_addr,
        "normalized": normalize_party_address(seller_addr, "", ""),
    }
    if is_po_box(seller_addr):
        seller["skip_geocode"] = True

    # Buyer address (simple normalization)
    buyer_addr = data.get("transferee", {}).get("address", "")
    buyer = {
        "original": buyer_addr,
        "normalized": normalize_party_address(buyer_addr, "", ""),
    }
    if is_po_box(buyer_addr):
        buyer["skip_geocode"] = True

    return {
        "rt_id": data.get("rt_id", ""),
        "source_version": source_version,
        "property": {
            "addresses": property_addresses,
        },
        "seller": seller,
        "buyer": buyer,
    }


def extract_all(
    source_dir: Path,
    output_dir: Path,
    source_version: str = "",
) -> Dict:
    """Extract geocodable addresses from all parsed JSON files.

    Reads each {RT_ID}.json in source_dir, expands addresses, and writes
    the extraction result to output_dir/{RT_ID}.json.

    Returns summary: {total, extracted, errors, elapsed}
    """
    start = time.time()
    total = 0
    extracted = 0
    errors = 0
    error_ids: List[str] = []

    source_files = sorted(source_dir.glob("*.json"))

    for src_path in source_files:
        if src_path.stem == "_meta":
            continue
        total += 1

        try:
            data = json.loads(src_path.read_text(encoding="utf-8"))
            result = _extract_record(data, source_version)

            out_path = output_dir / src_path.name
            out_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            extracted += 1
        except Exception as e:
            errors += 1
            error_ids.append(src_path.stem)
            logger.error("Error extracting %s: %s", src_path.stem, e)

        if total % 2000 == 0:
            logger.info("Progress: %d / %d", total, len(source_files))

    elapsed = time.time() - start
    logger.info(
        "Done: %d extracted, %d errors in %.1fs",
        extracted, errors, elapsed,
    )

    return {
        "total": total,
        "extracted": extracted,
        "errors": errors,
        "error_ids": error_ids,
        "elapsed": elapsed,
    }
