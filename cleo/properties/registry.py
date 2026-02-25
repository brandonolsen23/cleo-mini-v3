"""Property registry — canonical deduplicated property list.

Scans parsed transaction data, deduplicates by normalized (address, city),
assigns stable property IDs, and maintains a persistent JSON registry
that can be enriched by future data sources.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from cleo.properties.normalize import (
    make_dedup_key,
    normalize_address_for_dedup,
    normalize_city_for_dedup,
)


def _next_prop_id(existing_ids: set[str]) -> str:
    """Generate the next P-prefixed ID (P00001, P00002, ...)."""
    max_num = 0
    for pid in existing_ids:
        if pid.startswith("P") and pid[1:].isdigit():
            max_num = max(max_num, int(pid[1:]))
    return f"P{max_num + 1:05d}"


def _parse_expanded_address(expanded: str) -> tuple[str, str]:
    """Parse an expanded address string like '1855 DUNDAS ST E, Toronto, Ontario'.

    Returns (address_part, city_part).
    """
    parts = [p.strip() for p in expanded.split(",")]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return expanded, ""


def build_registry(
    parsed_dir: Path,
    existing_registry_path: Path | None = None,
    extracted_dir: Path | None = None,
) -> dict:
    """Build or update the property registry from parsed data.

    Args:
        parsed_dir: Active parsed JSON directory.
        existing_registry_path: Path to existing properties.json to merge with.
            Preserves stable IDs and any manual edits.
        extracted_dir: Active extracted JSON directory (optional). When provided,
            compound addresses with multiple expanded entries create additional
            dedup keys, merging sub-addresses with standalone transactions.

    Returns:
        Registry dict: {"properties": {...}, "meta": {...}}
    """
    # Load existing registry if present
    existing: dict[str, dict] = {}
    key_to_pid: dict[str, str] = {}
    if existing_registry_path and existing_registry_path.exists():
        data = json.loads(existing_registry_path.read_text(encoding="utf-8"))
        existing = data.get("properties", {})
        # Build reverse lookup: dedup_key -> property ID
        for pid, prop in existing.items():
            key = make_dedup_key(prop.get("address", ""), prop.get("city", ""))
            key_to_pid[key] = pid

    # Scan all parsed JSON files
    scanned: dict[str, dict] = {}  # dedup_key -> {address, city, municipality, province, rt_ids}
    # Track physical property facts per RT ID for later backfill
    rt_facts: dict[str, dict] = {}  # rt_id -> {building_sf, site_area, sale_date_iso}

    for f in sorted(parsed_dir.glob("*.json")):
        if f.stem == "_meta":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        rt_id = data.get("rt_id", f.stem)
        tx = data.get("transaction", {})
        addr = tx.get("address", {})

        # Collect physical property facts from this transaction
        building_sf = data.get("export_extras", {}).get("building_sf", "")
        site_area = data.get("site", {}).get("site_area", "")
        if building_sf or site_area:
            rt_facts[rt_id] = {
                "building_sf": building_sf,
                "site_area": site_area,
                "sale_date_iso": tx.get("sale_date_iso", ""),
            }

        address = addr.get("address", "").strip()
        city = addr.get("city", "").strip()
        if not address:
            continue

        key = make_dedup_key(address, city)
        if key not in scanned:
            scanned[key] = {
                "address": address,
                "city": city,
                "municipality": addr.get("municipality", ""),
                "province": addr.get("province", "Ontario"),
                "rt_ids": [],
            }
        scanned[key]["rt_ids"].append(rt_id)

    # Phase 2: Expanded address matching from extracted data.
    # For compound addresses (e.g. "1855 - 1911 DUNDAS ST E"), the extraction
    # step produces individual expanded addresses.  If any expanded sub-address
    # matches an existing scanned key, merge the RT ID into that group instead
    # of leaving it as a separate property.
    expanded_merges = 0
    if extracted_dir and extracted_dir.is_dir():
        for f in sorted(extracted_dir.glob("*.json")):
            if f.stem == "_meta":
                continue
            ext = json.loads(f.read_text(encoding="utf-8"))
            rt_id = ext.get("rt_id", f.stem)

            for addr_entry in ext.get("property", {}).get("addresses", []):
                expanded_list = addr_entry.get("expanded", [])
                if len(expanded_list) <= 1:
                    continue  # Not a compound address

                for expanded in expanded_list:
                    addr_part, city_part = _parse_expanded_address(expanded)
                    if not addr_part:
                        continue
                    exp_key = make_dedup_key(addr_part, city_part)

                    # Only merge if this key already exists from a standalone
                    # transaction AND the RT ID isn't already there
                    if exp_key in scanned:
                        if rt_id not in scanned[exp_key]["rt_ids"]:
                            scanned[exp_key]["rt_ids"].append(rt_id)
                            expanded_merges += 1

    # Merge: update existing entries, add new ones
    used_ids = set(existing.keys())
    today = datetime.now().strftime("%Y-%m-%d")
    properties: dict[str, dict] = {}

    # Track which existing PIDs have been claimed so we can detect merges.
    # Multiple old keys may now resolve to the same scanned key due to
    # enhanced normalization — the earliest PID wins.
    claimed_pids: set[str] = set()

    for key, info in scanned.items():
        if key in key_to_pid:
            pid = key_to_pid[key]
            if pid in claimed_pids:
                # This PID was already used by a different key that normalized
                # to the same value.  Merge RT IDs into the existing entry.
                properties[pid]["rt_ids"] = sorted(
                    set(properties[pid]["rt_ids"]) | set(info["rt_ids"])
                )
                properties[pid]["transaction_count"] = len(properties[pid]["rt_ids"])
                continue
            claimed_pids.add(pid)
            # Existing property — update RT IDs, preserve everything else
            prop = dict(existing[pid])  # shallow copy
            prop["rt_ids"] = sorted(set(info["rt_ids"]))
            prop["transaction_count"] = len(prop["rt_ids"])
            # Don't overwrite manually-edited fields, but fill empty ones
            if not prop.get("municipality"):
                prop["municipality"] = info["municipality"]
            prop["updated"] = today
            properties[pid] = prop
        else:
            # Check if any existing PID resolves to this key under the NEW
            # normalization (the old key_to_pid was built with old norms from
            # the existing registry's stored address/city — re-check here).
            # This catches duplicates where existing entries have different
            # surface forms but normalize identically now.
            found_pid = None
            for pid, prop in properties.items():
                existing_key = make_dedup_key(prop.get("address", ""), prop.get("city", ""))
                if existing_key == key:
                    found_pid = pid
                    break

            if found_pid:
                # Merge into existing
                properties[found_pid]["rt_ids"] = sorted(
                    set(properties[found_pid]["rt_ids"]) | set(info["rt_ids"])
                )
                properties[found_pid]["transaction_count"] = len(properties[found_pid]["rt_ids"])
            else:
                # New property — assign next ID
                pid = _next_prop_id(used_ids)
                used_ids.add(pid)
                properties[pid] = {
                    "address": info["address"],
                    "city": info["city"],
                    "municipality": info["municipality"],
                    "province": info["province"],
                    "postal_code": "",
                    "lat": None,
                    "lng": None,
                    "rt_ids": sorted(set(info["rt_ids"])),
                    "transaction_count": len(set(info["rt_ids"])),
                    "sources": ["rt"],
                    "created": today,
                    "updated": today,
                }

    # Preserve existing entries not found in scan (e.g. manually added, brand sources).
    # But first check if they would now merge with an already-claimed property
    # under the enhanced normalization.
    for pid, prop in existing.items():
        if pid in properties:
            continue
        key = make_dedup_key(prop.get("address", ""), prop.get("city", ""))
        # See if another property already covers this key
        merged = False
        for existing_pid, existing_prop in properties.items():
            existing_key = make_dedup_key(
                existing_prop.get("address", ""), existing_prop.get("city", "")
            )
            if existing_key == key:
                # Merge RT IDs from the old entry into the surviving one
                old_rt_ids = set(prop.get("rt_ids", []))
                new_rt_ids = set(existing_prop.get("rt_ids", []))
                combined = sorted(old_rt_ids | new_rt_ids)
                existing_prop["rt_ids"] = combined
                existing_prop["transaction_count"] = len(combined)
                # Preserve sources
                old_sources = set(prop.get("sources", []))
                new_sources = set(existing_prop.get("sources", []))
                existing_prop["sources"] = sorted(old_sources | new_sources)
                merged = True
                break
        if not merged:
            properties[pid] = prop

    # Backfill physical property facts (building_sf, site_area) from linked
    # transactions.  For each property, scan all linked RT IDs and pick the
    # latest non-empty value (by sale_date_iso) for each field.  Values are
    # always recomputed from transactions so that fixing a bad link and
    # rebuilding cleanly removes stale data.
    for _pid, prop in properties.items():
        best_sf = ""
        best_sf_iso = ""
        best_area = ""
        best_area_iso = ""
        for rt_id in prop.get("rt_ids", []):
            facts = rt_facts.get(rt_id)
            if not facts:
                continue
            iso = facts.get("sale_date_iso", "")
            if facts["building_sf"] and iso >= best_sf_iso:
                best_sf = facts["building_sf"]
                best_sf_iso = iso
            if facts["site_area"] and iso >= best_area_iso:
                best_area = facts["site_area"]
                best_area_iso = iso
        prop["building_sf"] = best_sf
        prop["site_area"] = best_area

    # Sort by property ID
    properties = dict(sorted(properties.items()))

    # Summary stats
    total_props = len(properties)
    total_rt_ids = sum(len(p.get("rt_ids", [])) for p in properties.values())
    multi_tx = sum(1 for p in properties.values() if len(p.get("rt_ids", [])) > 1)

    meta = {
        "built": datetime.now().isoformat(timespec="seconds"),
        "source_dir": parsed_dir.name,
        "total_properties": total_props,
        "total_transactions_linked": total_rt_ids,
        "multi_transaction_properties": multi_tx,
    }
    if expanded_merges:
        meta["expanded_address_merges"] = expanded_merges

    return {"properties": properties, "meta": meta}


def save_registry(registry: dict, path: Path) -> None:
    """Atomically save the registry to disk."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def load_registry(path: Path) -> dict:
    """Load the registry from disk."""
    if not path.exists():
        return {"properties": {}, "meta": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def backfill_geocodes(
    registry: dict,
    cache_path: Path | None = None,
    extracted_dir: Path | None = None,
    coord_store=None,
    refresh_all: bool = False,
) -> dict:
    """Apply geocode coordinates to properties missing lat/lng.

    Matching strategy:
    1. Direct match: property (address, city) -> coordinate store or cache
    2. RT ID lookup: for RT-sourced properties, check extracted expanded addresses
    3. GW address build: for GW-sourced properties with no RT IDs, build
       geocodable address from (address, city, province, postal_code) and look up

    Args:
        registry: Property registry dict.
        cache_path: Path to legacy geocode_cache.json (used if coord_store is None).
        extracted_dir: Active extracted JSON directory.
        coord_store: CoordinateStore instance (preferred over cache_path).
        refresh_all: If True, re-compute coords for ALL properties using
            best multi-provider median, not just those missing lat/lng.

    Returns:
        {"updated": int, "already_had": int, "no_match": int, "refreshed": int}
    """
    props = registry.get("properties", {})

    def _norm(s: str) -> str:
        s = s.upper().strip()
        s = re.sub(r"[.,]", "", s)
        return re.sub(r"\s+", " ", s)

    # If using CoordinateStore, use its best_coords() method
    if coord_store is not None:
        return _backfill_from_coord_store(props, coord_store, extracted_dir, _norm, refresh_all)

    # Legacy path: use geocode_cache.json
    if cache_path is None or not cache_path.exists():
        return {"updated": 0, "already_had": len(props), "no_match": 0}

    cache = json.loads(cache_path.read_text(encoding="utf-8"))

    cache_by_addr_city: dict[tuple[str, str], tuple[float, float]] = {}
    cache_by_key_upper: dict[str, tuple[float, float]] = {}

    for key, val in cache.items():
        if val.get("failed") or val.get("lat") is None:
            continue
        coords = (val["lat"], val["lng"])
        cache_by_key_upper[key.upper().strip()] = coords
        parts = [p.strip() for p in key.split(",")]
        if len(parts) >= 2:
            k = (_norm(parts[0]), _norm(parts[1]))
            if k not in cache_by_addr_city:
                cache_by_addr_city[k] = coords

    updated = 0
    already_had = 0
    no_match = 0

    for pid, prop in props.items():
        if prop.get("lat") is not None:
            already_had += 1
            continue

        # Strategy 1: direct (address, city) match
        k = (_norm(prop.get("address", "")), _norm(prop.get("city", "")))
        if k in cache_by_addr_city:
            lat, lng = cache_by_addr_city[k]
            prop["lat"] = lat
            prop["lng"] = lng
            updated += 1
            continue

        # Strategy 2: look up via RT ID -> extracted expanded addresses
        if extracted_dir:
            matched = False
            for rt_id in prop.get("rt_ids", []):
                ext_path = extracted_dir / f"{rt_id}.json"
                if not ext_path.exists():
                    continue
                ext = json.loads(ext_path.read_text(encoding="utf-8"))
                for addr_entry in ext.get("property", {}).get("addresses", []):
                    for expanded in addr_entry.get("expanded", []):
                        cache_key = expanded.upper().strip()
                        if cache_key in cache_by_key_upper:
                            lat, lng = cache_by_key_upper[cache_key]
                            prop["lat"] = lat
                            prop["lng"] = lng
                            matched = True
                            break
                    if matched:
                        break
                if matched:
                    break
            if matched:
                updated += 1
                continue

        no_match += 1

    return {"updated": updated, "already_had": already_had, "no_match": no_match, "refreshed": 0}


def _resolve_best_coords(prop, coord_store, extracted_dir):
    """Try all strategies to find best coords for a property.

    Returns (lat, lng) or None.
    """
    address = prop.get("address", "").strip()
    city = prop.get("city", "").strip()

    # Strategy 1: Direct (address, city, province) lookup
    province = prop.get("province", "Ontario")
    postal = prop.get("postal_code", "")
    candidates = []
    if address and city:
        if postal:
            candidates.append(f"{address}, {city}, {province}, {postal}")
        candidates.append(f"{address}, {city}, {province}")
        candidates.append(f"{address}, {city}")

    for candidate in candidates:
        coords = coord_store.best_coords(candidate)
        if coords:
            return coords

    # Strategy 2: RT ID -> extracted expanded addresses
    if extracted_dir and prop.get("rt_ids"):
        for rt_id in prop["rt_ids"]:
            ext_path = extracted_dir / f"{rt_id}.json"
            if not ext_path.exists():
                continue
            ext = json.loads(ext_path.read_text(encoding="utf-8"))
            for addr_entry in ext.get("property", {}).get("addresses", []):
                for expanded in addr_entry.get("expanded", []):
                    coords = coord_store.best_coords(expanded)
                    if coords:
                        return coords

    # Strategy 3: GW-sourced properties — build geocodable address
    if "gw" in prop.get("sources", []) and address and city:
        gw_candidates = [
            f"{address}, {city}, ONTARIO",
            f"{address.upper()}, {city.title()}, ONTARIO",
        ]
        if postal:
            gw_candidates.insert(0, f"{address}, {city}, ONTARIO, {postal}")
        for candidate in gw_candidates:
            coords = coord_store.best_coords(candidate)
            if coords:
                return coords

    return None


def _backfill_from_coord_store(
    props: dict,
    coord_store,
    extracted_dir: Path | None,
    _norm,
    refresh_all: bool = False,
) -> dict:
    """Backfill using CoordinateStore with best_coords() selection.

    If refresh_all is True, also re-computes coords for properties that
    already have lat/lng, updating them to the best multi-provider median.
    """
    updated = 0
    already_had = 0
    no_match = 0
    refreshed = 0

    for pid, prop in props.items():
        has_coords = prop.get("lat") is not None

        if has_coords and not refresh_all:
            already_had += 1
            continue

        coords = _resolve_best_coords(prop, coord_store, extracted_dir)

        if coords:
            if has_coords:
                # Already had coords — check if they changed
                old_lat, old_lng = prop["lat"], prop["lng"]
                if round(coords[0], 7) != round(old_lat, 7) or round(coords[1], 7) != round(old_lng, 7):
                    prop["lat"] = coords[0]
                    prop["lng"] = coords[1]
                    refreshed += 1
                else:
                    already_had += 1
            else:
                prop["lat"] = coords[0]
                prop["lng"] = coords[1]
                updated += 1
        else:
            if has_coords:
                # Keep existing coords even though we couldn't resolve new ones
                already_had += 1
            else:
                no_match += 1

    return {"updated": updated, "already_had": already_had, "no_match": no_match, "refreshed": refreshed}
