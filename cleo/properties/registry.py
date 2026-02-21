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

    for f in sorted(parsed_dir.glob("*.json")):
        if f.stem == "_meta":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        rt_id = data.get("rt_id", f.stem)
        tx = data.get("transaction", {})
        addr = tx.get("address", {})

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
    cache_path: Path,
    extracted_dir: Path | None = None,
) -> dict:
    """Apply geocode cache coordinates to properties missing lat/lng.

    Matching strategy:
    1. Direct match: property (address, city) -> cache key (addr, city) parts
    2. RT ID lookup: for unmatched RT-sourced properties, check their extracted
       expanded addresses against the cache

    Returns:
        {"updated": int, "already_had": int, "no_match": int}
    """
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    props = registry.get("properties", {})

    # Build cache lookup: (normalized_addr, normalized_city) -> (lat, lng)
    def _norm(s: str) -> str:
        s = s.upper().strip()
        s = re.sub(r"[.,]", "", s)
        return re.sub(r"\s+", " ", s)

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

    return {"updated": updated, "already_had": already_had, "no_match": no_match}
