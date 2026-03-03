"""Unified address collector — gathers geocodable addresses from all sources.

Collects from expanded pipeline (preferred, all sources merged):
  data/expanded/active/*.json — RT, brand, and GW addresses with skip_geocode flags

Legacy fallback (if no expanded data):
  extracted/active/*.json, gw_parsed/active/*.json, brands/data/*.json
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Role → priority mapping
_ROLE_PRIORITY = {
    "property": 1,
    "store": 2,
    "seller": 3,
    "buyer": 3,
    "owner_address": 3,
}

# Source prefix → source label
_SOURCE_LABELS = {
    "RT": "rt",
    "GW": "gw",
    "BR": "brand",
}


@dataclass
class AddressRef:
    """Metadata about a collected address."""
    address: str
    priority: int  # 1=property, 2=brand, 3=buyer/seller
    sources: list[str] = field(default_factory=list)  # e.g. ["rt", "gw", "brand"]
    roles: list[str] = field(default_factory=list)  # e.g. ["property", "seller"]


def _detect_source(record_id: str) -> str:
    """Detect source label from record ID prefix."""
    for prefix, label in _SOURCE_LABELS.items():
        if record_id.startswith(prefix):
            return label
    return "unknown"


def collect_from_expanded(expanded_dir: Path) -> dict[str, AddressRef]:
    """Collect geocodable addresses from expanded pipeline output.

    Reads all expanded JSON files and collects non-skipped canonical
    addresses with their roles and source types.
    """
    all_addresses: dict[str, AddressRef] = {}

    def _add(addr: str, priority: int, source: str, role: str) -> None:
        key = addr.strip().upper()
        if not key:
            return
        if key not in all_addresses:
            all_addresses[key] = AddressRef(address=key, priority=priority)
        ref = all_addresses[key]
        if priority < ref.priority:
            ref.priority = priority
        if source not in ref.sources:
            ref.sources.append(source)
        if role not in ref.roles:
            ref.roles.append(role)

    stats = {"property": 0, "seller": 0, "buyer": 0, "owner": 0, "alt": 0, "skipped": 0}

    for f in sorted(expanded_dir.glob("*.json")):
        if f.stem == "_meta":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        source = _detect_source(f.stem)

        for role in ("property", "seller", "buyer", "owner_address"):
            block = data.get(role)
            if not block:
                continue
            priority = _ROLE_PRIORITY.get(role, 3)
            # Brands: property addresses get priority 2
            if source == "brand" and role == "property":
                priority = 2
            for addr in block.get("addresses", []):
                if addr.get("skip_geocode"):
                    stats["skipped"] += 1
                    continue
                canonical = addr.get("canonical", "")
                if canonical:
                    _add(canonical, priority=priority, source=source, role=role)
                    if role == "property":
                        stats["property"] += 1
                    elif role == "owner_address":
                        stats["owner"] += 1
                    else:
                        stats[role] = stats.get(role, 0) + 1

        for alt in data.get("property_alt", []):
            for addr in alt.get("addresses", []):
                if addr.get("skip_geocode"):
                    stats["skipped"] += 1
                    continue
                canonical = addr.get("canonical", "")
                if canonical:
                    priority = 2 if source == "brand" else 1
                    _add(canonical, priority=priority, source=source, role="property_alt")
                    stats["alt"] += 1

    logger.info(
        "Expanded: %d property, %d seller, %d buyer, %d owner, %d alt, %d skipped",
        stats["property"], stats["seller"], stats["buyer"],
        stats["owner"], stats["alt"], stats["skipped"],
    )
    logger.info("Total unique addresses collected: %d", len(all_addresses))

    return all_addresses


def collect_all(
    extracted_dir: Optional[Path] = None,
    reviews_path: Optional[Path] = None,
    gw_parsed_dir: Optional[Path] = None,
    brands_data_dir: Optional[Path] = None,
    expanded_dir: Optional[Path] = None,
) -> dict[str, AddressRef]:
    """Collect geocodable addresses from all sources.

    If expanded_dir is provided and exists, collects from the expanded
    pipeline (which already includes RT, brand, and GW). Otherwise falls
    back to legacy extracted + GW + brand collection.

    Returns dict keyed by normalized (uppercased) address string.
    """
    # Prefer expanded pipeline — it has all sources merged with skip_geocode flags
    if expanded_dir and expanded_dir.is_dir():
        return collect_from_expanded(expanded_dir)

    # Legacy fallback: collect from extracted + GW + brands separately
    from cleo.geocode.collector import collect_addresses as collect_rt_addresses_raw
    from cleo.geowarehouse.address import parse_mpac_address

    all_addresses: dict[str, AddressRef] = {}

    def _add(addr: str, priority: int, source: str, role: str) -> None:
        key = addr.strip().upper()
        if not key:
            return
        if key not in all_addresses:
            all_addresses[key] = AddressRef(address=key, priority=priority)
        ref = all_addresses[key]
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

            owner_addr = site.get("owner_mailing_address", "").strip()
            if owner_addr:
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
    logger.info("Total unique addresses collected: %d", len(all_addresses))

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
