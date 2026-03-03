"""Geocoded engine: reads expanded JSON, looks up coordinates, writes versioned output.

This is a lookup/assembly step — it does NOT call geocoding APIs. It reads each
expanded record, looks up coordinates for each address from the CoordinateStore,
and writes a geocoded record with coordinates embedded in each address entry.

API calls happen separately via `cleo geocode --provider mapbox`.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from cleo.geocode.store import CoordinateStore

logger = logging.getLogger(__name__)


def _lookup_address(canonical: str, coord_store: CoordinateStore) -> Optional[Dict]:
    """Look up best coordinates for a canonical address string.

    Returns dict with lat, lng, provider, geocoded_at — or None if not found.
    """
    best = coord_store.best_coords(canonical)
    if best is None:
        return None

    lat, lng = best

    # Find which provider(s) contributed
    entry = coord_store.get(canonical) or {}
    providers_used = [p for p in entry if entry[p].get("lat") is not None]

    # Build provider_details from best single provider (for accuracy metadata)
    provider_details = {}
    for p in ["geocodio", "mapbox", "here", "scraper"]:
        if p in entry and entry[p].get("lat") is not None:
            provider_details = {
                "provider": p,
                "accuracy": entry[p].get("accuracy", ""),
                "match_code": entry[p].get("match_code", ""),
            }
            break

    return {
        "lat": lat,
        "lng": lng,
        "providers": providers_used,
        "geocoded_at": datetime.now().isoformat(timespec="seconds"),
        "provider_details": provider_details,
    }


def _geocode_address_block(block: Optional[Dict], coord_store: CoordinateStore) -> Optional[Dict]:
    """Add coordinates to each address in an address block.

    Returns a new block dict with coordinates embedded, or None if input is None.
    """
    if not block or "addresses" not in block:
        return block

    new_addresses = []
    for addr in block["addresses"]:
        new_addr = dict(addr)
        canonical = addr.get("canonical", "")
        skip = addr.get("skip_geocode", False)

        if canonical and not skip:
            coords = _lookup_address(canonical, coord_store)
            if coords:
                new_addr["coords"] = {
                    "lat": coords["lat"],
                    "lng": coords["lng"],
                }
                new_addr["geocoded_at"] = coords["geocoded_at"]
                new_addr["provider_details"] = coords["provider_details"]
            else:
                new_addr["coords"] = None
        else:
            new_addr["coords"] = None

        new_addresses.append(new_addr)

    return {"addresses": new_addresses}


def geocode_record(data: Dict, coord_store: CoordinateStore) -> Dict:
    """Geocode a single expanded record by looking up coordinates.

    Adds coords to each address entry in property, property_alt, seller,
    buyer, and owner_address blocks.
    """
    result: Dict = {
        "id": data.get("id", ""),
        "source": data.get("source", ""),
        "source_version": data.get("source_version", ""),
    }

    # Process each address block
    for role in ("property", "seller", "buyer", "owner_address"):
        block = data.get(role)
        if block:
            result[role] = _geocode_address_block(block, coord_store)

    # Property alternatives
    prop_alt = data.get("property_alt", [])
    if prop_alt:
        alts = []
        for alt in prop_alt:
            geocoded_alt = _geocode_address_block(alt, coord_store)
            if geocoded_alt:
                alts.append(geocoded_alt)
        if alts:
            result["property_alt"] = alts

    # Pass through raw_coords (brand scraper coordinates)
    if "raw_coords" in data:
        result["raw_coords"] = data["raw_coords"]

    return result


def geocode_all(
    source_dir: Path,
    output_dir: Path,
    coord_store: CoordinateStore,
    source_version: str = "",
) -> Dict:
    """Geocode all expanded JSON files by looking up coordinates.

    Reads each {ID}.json in source_dir (expanded output), looks up
    coordinates from the CoordinateStore, and writes geocoded output
    to output_dir/{ID}.json.

    Returns summary dict.
    """
    start = time.time()
    total = 0
    geocoded = 0
    errors = 0
    error_ids: List[str] = []
    by_source: Dict[str, int] = {}

    # Count geocoding hits
    addr_total = 0
    addr_geocoded = 0
    addr_skipped = 0
    addr_missing = 0

    source_files = sorted(source_dir.glob("*.json"))

    for src_path in source_files:
        if src_path.stem == "_meta":
            continue
        total += 1

        try:
            data = json.loads(src_path.read_text(encoding="utf-8"))

            if source_version:
                data["source_version"] = source_version

            result = geocode_record(data, coord_store)

            # Count address-level stats
            for role in ("property", "seller", "buyer", "owner_address"):
                block = result.get(role)
                if block and "addresses" in block:
                    for addr in block["addresses"]:
                        addr_total += 1
                        if addr.get("skip_geocode"):
                            addr_skipped += 1
                        elif addr.get("coords") is not None:
                            addr_geocoded += 1
                        else:
                            addr_missing += 1
            for alt in result.get("property_alt", []):
                if "addresses" in alt:
                    for addr in alt["addresses"]:
                        addr_total += 1
                        if addr.get("skip_geocode"):
                            addr_skipped += 1
                        elif addr.get("coords") is not None:
                            addr_geocoded += 1
                        else:
                            addr_missing += 1

            out_path = output_dir / src_path.name
            out_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            geocoded += 1

            src = data.get("source", "unknown")
            by_source[src] = by_source.get(src, 0) + 1

        except Exception as e:
            errors += 1
            error_ids.append(src_path.stem)
            logger.error("Error geocoding %s: %s", src_path.stem, e)

        if total % 5000 == 0:
            logger.info("Progress: %d records", total)

    elapsed = time.time() - start
    logger.info(
        "Done: %d records, %d addr geocoded, %d missing, %d skipped in %.1fs",
        geocoded, addr_geocoded, addr_missing, addr_skipped, elapsed,
    )

    return {
        "total": total,
        "geocoded": geocoded,
        "errors": errors,
        "error_ids": error_ids,
        "elapsed": elapsed,
        "by_source": by_source,
        "addr_total": addr_total,
        "addr_geocoded": addr_geocoded,
        "addr_skipped": addr_skipped,
        "addr_missing": addr_missing,
    }
