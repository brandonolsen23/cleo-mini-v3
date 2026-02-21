"""Collect all geocodable addresses from extracted data, applying overrides."""

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


def collect_addresses(
    extracted_dir: Path,
    reviews_path: Path,
) -> Tuple[Dict[str, List[Dict]], Set[str]]:
    """Scan all extracted JSON files and collect geocodable addresses.

    Applies overrides from extract_reviews.json.

    Returns:
        address_refs: {normalized_address: [{rt_id, role, addr_index}]}
        unique_addresses: set of unique address strings to geocode
    """
    # Load overrides
    overrides = {}
    if reviews_path.exists():
        try:
            reviews = json.loads(reviews_path.read_text(encoding="utf-8"))
            for rt_id, review in reviews.items():
                if review.get("overrides"):
                    overrides[rt_id] = review["overrides"]
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load extract reviews: %s", e)

    address_refs: Dict[str, List[Dict]] = defaultdict(list)
    skipped = 0
    total_addresses = 0

    source_files = sorted(extracted_dir.glob("*.json"))
    for src_path in source_files:
        if src_path.stem == "_meta":
            continue

        try:
            data = json.loads(src_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read %s: %s", src_path.name, e)
            continue

        rt_id = data.get("rt_id", src_path.stem)
        rt_overrides = overrides.get(rt_id, {})

        # Property addresses
        prop_addrs = data.get("property", {}).get("addresses", [])
        for i, addr_entry in enumerate(prop_addrs):
            if addr_entry.get("skip_geocode"):
                skipped += 1
                continue

            override_key = f"property_{i}"
            if override_key in rt_overrides and rt_overrides[override_key].strip():
                # Override replaces all expanded addresses for this entry
                addr = rt_overrides[override_key].strip()
                address_refs[addr].append({
                    "rt_id": rt_id,
                    "role": "property",
                    "addr_index": i,
                    "overridden": True,
                })
                total_addresses += 1
            else:
                # Use all expanded addresses
                for expanded_addr in addr_entry.get("expanded", []):
                    address_refs[expanded_addr].append({
                        "rt_id": rt_id,
                        "role": "property",
                        "addr_index": i,
                    })
                    total_addresses += 1

        # Seller address
        seller = data.get("seller", {})
        if not seller.get("skip_geocode"):
            if "seller" in rt_overrides and rt_overrides["seller"].strip():
                addr = rt_overrides["seller"].strip()
                if addr:
                    address_refs[addr].append({
                        "rt_id": rt_id,
                        "role": "seller",
                    })
                    total_addresses += 1
            else:
                addr = seller.get("normalized", "").strip()
                if addr:
                    address_refs[addr].append({
                        "rt_id": rt_id,
                        "role": "seller",
                    })
                    total_addresses += 1
        else:
            skipped += 1

        # Buyer address
        buyer = data.get("buyer", {})
        if not buyer.get("skip_geocode"):
            if "buyer" in rt_overrides and rt_overrides["buyer"].strip():
                addr = rt_overrides["buyer"].strip()
                if addr:
                    address_refs[addr].append({
                        "rt_id": rt_id,
                        "role": "buyer",
                    })
                    total_addresses += 1
            else:
                addr = buyer.get("normalized", "").strip()
                if addr:
                    address_refs[addr].append({
                        "rt_id": rt_id,
                        "role": "buyer",
                    })
                    total_addresses += 1
        else:
            skipped += 1

    unique = set(address_refs.keys())

    logger.info(
        "Collected %d total address references, %d unique, %d skipped (skip_geocode)",
        total_addresses, len(unique), skipped,
    )

    return dict(address_refs), unique
