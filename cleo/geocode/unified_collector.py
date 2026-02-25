"""Unified address collector — gathers geocodable addresses from all sources.

Collects addresses from:
  Priority 1: RT property addresses (from extracted/active/*.json)
  Priority 1: GW property addresses (from gw_parsed/active/*.json)
  Priority 2: Brand store addresses (from brands/data/*.json)
  Priority 3: RT buyer/seller addresses (from extracted/active/*.json)
  Priority 3: GW owner mailing addresses (from gw_parsed/active/*.json)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cleo.geocode.collector import collect_addresses as collect_rt_addresses_raw
from cleo.geowarehouse.address import parse_mpac_address

logger = logging.getLogger(__name__)


@dataclass
class AddressRef:
    """Metadata about a collected address."""
    address: str
    priority: int  # 1=property, 2=brand, 3=buyer/seller
    sources: list[str] = field(default_factory=list)  # e.g. ["rt", "gw", "brand"]
    roles: list[str] = field(default_factory=list)  # e.g. ["property", "seller"]


def collect_all(
    extracted_dir: Optional[Path] = None,
    reviews_path: Optional[Path] = None,
    gw_parsed_dir: Optional[Path] = None,
    brands_data_dir: Optional[Path] = None,
) -> dict[str, AddressRef]:
    """Collect geocodable addresses from all sources.

    Returns dict keyed by normalized (uppercased) address string.
    """
    all_addresses: dict[str, AddressRef] = {}

    def _add(addr: str, priority: int, source: str, role: str) -> None:
        key = addr.strip().upper()
        if not key:
            return
        if key not in all_addresses:
            all_addresses[key] = AddressRef(address=key, priority=priority)
        ref = all_addresses[key]
        # Keep the highest priority (lowest number)
        if priority < ref.priority:
            ref.priority = priority
        if source not in ref.sources:
            ref.sources.append(source)
        if role not in ref.roles:
            ref.roles.append(role)

    # --- RT addresses (from extracted data) ---
    rt_stats = {"property": 0, "buyer_seller": 0}
    if extracted_dir and extracted_dir.is_dir():
        rt_refs, _ = collect_rt_addresses_raw(
            extracted_dir, reviews_path or Path("/dev/null")
        )
        for addr, refs in rt_refs.items():
            for ref in refs:
                role = ref.get("role", "property")
                if role == "property":
                    _add(addr, priority=1, source="rt", role="property")
                    rt_stats["property"] += 1
                else:
                    _add(addr, priority=3, source="rt", role=role)
                    rt_stats["buyer_seller"] += 1

    logger.info(
        "RT: %d property addresses, %d buyer/seller addresses",
        rt_stats["property"], rt_stats["buyer_seller"],
    )

    # --- GW addresses (from parsed GW records) ---
    gw_stats = {"property": 0, "owner": 0}
    if gw_parsed_dir and gw_parsed_dir.is_dir():
        for f in sorted(gw_parsed_dir.glob("*.json")):
            if f.stem == "_meta":
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            # GW property address (Priority 1)
            site = data.get("site_structure", {})
            property_address = site.get("property_address", "")
            municipality = site.get("municipality", "")

            if property_address and municipality:
                parsed = parse_mpac_address(
                    property_address,
                    municipality,
                    summary_address=data.get("summary", {}).get("address", ""),
                )
                street = parsed.get("street", "")
                city = parsed.get("city", "")
                postal = parsed.get("postal_code", "")

                if street and city:
                    parts = [street, city, "ONTARIO"]
                    if postal:
                        parts.append(postal)
                    geocodable = ", ".join(parts)
                    _add(geocodable, priority=1, source="gw", role="property")
                    gw_stats["property"] += 1

            # GW owner mailing address (Priority 3)
            owner_addr = site.get("owner_mailing_address", "").strip()
            if owner_addr:
                # Owner mailing addresses are already formatted as a single
                # line like "12994 KEELE ST SUITE 6 KING CITY ON L7B 1H8".
                # We add ", CANADA" will be handled by the geocodio client.
                # For the store key, use as-is (uppercased).
                _add(owner_addr, priority=3, source="gw", role="owner")
                gw_stats["owner"] += 1

    logger.info(
        "GW: %d property addresses, %d owner addresses",
        gw_stats["property"], gw_stats["owner"],
    )

    # --- Brand store addresses (Priority 2) ---
    brand_count = 0
    if brands_data_dir and brands_data_dir.is_dir():
        for f in sorted(brands_data_dir.glob("*.json")):
            try:
                stores = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for store_rec in stores:
                addr = store_rec.get("address", "")
                city = store_rec.get("city", "")
                province = store_rec.get("province", "ON")
                if not addr or not city:
                    continue
                geocodable = f"{addr}, {city}, {province}"
                _add(geocodable, priority=2, source="brand", role="store")
                brand_count += 1

    logger.info("Brand: %d store addresses", brand_count)

    logger.info(
        "Total unique addresses collected: %d",
        len(all_addresses),
    )

    return all_addresses


def register_in_store(store, addresses: dict[str, AddressRef]) -> int:
    """Ensure all collected addresses exist in the CoordinateStore.

    Creates empty entries for new addresses. Returns count of newly added.
    """
    added = 0
    for key in addresses:
        if key not in store.addresses:
            store.addresses[key] = {}
            added += 1
    return added


def stats_summary(addresses: dict[str, AddressRef]) -> dict:
    """Return summary statistics about collected addresses."""
    by_source: dict[str, int] = {}
    by_priority: dict[int, int] = {}
    by_role: dict[str, int] = {}

    for ref in addresses.values():
        for s in ref.sources:
            by_source[s] = by_source.get(s, 0) + 1
        by_priority[ref.priority] = by_priority.get(ref.priority, 0) + 1
        for r in ref.roles:
            by_role[r] = by_role.get(r, 0) + 1

    return {
        "total": len(addresses),
        "by_source": by_source,
        "by_priority": by_priority,
        "by_role": by_role,
    }
