"""GeoWarehouse → Property Registry matching engine.

Matches GW records to the existing property registry using normalized
address dedup keys. Enriches matched properties with GW data and
creates new properties for unmatched GW records.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from cleo.geowarehouse.address import parse_mpac_address
from cleo.properties.normalize import (
    make_dedup_key,
    normalize_address_for_dedup,
    normalize_city_for_dedup,
)

logger = logging.getLogger(__name__)


def _extract_gw_data(record: dict) -> dict:
    """Extract a snapshot of key GW fields for embedding in the property registry."""
    site = record.get("site_structure", {})
    reg = record.get("registry", {})
    summary = record.get("summary", {})

    return {
        "pin": record.get("pin", ""),
        "arn": site.get("arn", ""),
        "zoning": site.get("zoning", ""),
        "assessed_value": site.get("current_assessed_value", ""),
        "valuation_date": site.get("valuation_date", ""),
        "property_code": site.get("property_code", ""),
        "property_description": site.get("property_description", ""),
        "ownership_type": reg.get("ownership_type", ""),
        "property_type": reg.get("property_type", ""),
        "owner_names": site.get("owner_names_mpac", "") or summary.get("owner_names", ""),
        "owner_mailing_address": site.get("owner_mailing_address", ""),
    }


def match_gw_to_registry(gw_dir: Path, registry: dict) -> dict:
    """Match GW records to the property registry.

    Args:
        gw_dir: Directory containing GW parsed JSON files (e.g. data/gw_parsed/v001/).
        registry: The full registry dict (with "properties" key).

    Returns:
        {
            "matched": [{"gw_id": ..., "prop_id": ..., "street": ..., "city": ...}, ...],
            "unmatched": [{"gw_id": ..., "street": ..., "city": ...}, ...],
            "stats": {"total_gw": N, "matched": N, "unmatched": N, "new_properties": N},
        }
    """
    props = registry.get("properties", {})

    # Build dedup key index from existing registry
    key_to_pid: dict[str, str] = {}
    for pid, prop in props.items():
        key = make_dedup_key(prop.get("address", ""), prop.get("city", ""))
        key_to_pid[key] = pid

    matched = []
    unmatched = []

    _DIRECTIONS = ("NORTH", "SOUTH", "EAST", "WEST")
    _TRAILING_DIR_RE = re.compile(
        r"\s+(?:NORTH|SOUTH|EAST|WEST|NORTHEAST|NORTHWEST|SOUTHEAST|SOUTHWEST)$"
    )

    gw_files = sorted(gw_dir.glob("*.json"))
    for f in gw_files:
        if f.stem == "_meta":
            continue

        record = json.loads(f.read_text(encoding="utf-8"))
        gw_id = record.get("gw_id", f.stem)
        site = record.get("site_structure", {})
        summary = record.get("summary", {})

        # Parse MPAC address
        parsed = parse_mpac_address(
            property_address=site.get("property_address", ""),
            municipality=site.get("municipality", ""),
            summary_address=summary.get("address", ""),
        )

        street = parsed["street"]
        city = parsed["city"]

        if not street:
            logger.warning("No street parsed for %s, skipping", gw_id)
            unmatched.append({"gw_id": gw_id, "street": street, "city": city, "reason": "no_street"})
            continue

        key = make_dedup_key(street, city)
        pid = key_to_pid.get(key)

        # Fallback: try adding or stripping trailing direction
        if not pid:
            norm_addr = normalize_address_for_dedup(street)
            norm_city = normalize_city_for_dedup(city)
            # Try stripping direction
            stripped = _TRAILING_DIR_RE.sub("", norm_addr)
            if stripped != norm_addr:
                pid = key_to_pid.get(f"{stripped}|{norm_city}")
            # Try appending each direction
            if not pid:
                for d in _DIRECTIONS:
                    pid = key_to_pid.get(f"{norm_addr} {d}|{norm_city}")
                    if pid:
                        break

        if pid:
            matched.append({
                "gw_id": gw_id,
                "prop_id": pid,
                "street": street,
                "city": city,
            })
        else:
            unmatched.append({
                "gw_id": gw_id,
                "street": street,
                "city": city,
            })

    return {
        "matched": matched,
        "unmatched": unmatched,
        "stats": {
            "total_gw": len(matched) + len(unmatched),
            "matched": len(matched),
            "unmatched": len(unmatched),
        },
    }


def apply_matches(registry: dict, match_result: dict, gw_dir: Path) -> dict:
    """Apply match results to the registry, enriching matched and adding new properties.

    Args:
        registry: The full registry dict (mutated in place).
        match_result: Output from match_gw_to_registry().
        gw_dir: GW parsed dir (to load full records for gw_data).

    Returns:
        {"enriched": N, "created": N, "postal_filled": N}
    """
    props = registry.get("properties", {})
    today = datetime.now().strftime("%Y-%m-%d")
    enriched = 0
    created = 0
    postal_filled = 0

    # Process matched records
    for m in match_result["matched"]:
        gw_id = m["gw_id"]
        pid = m["prop_id"]
        prop = props[pid]

        # Load full GW record
        gw_path = gw_dir / f"{gw_id}.json"
        record = json.loads(gw_path.read_text(encoding="utf-8"))

        # Add gw_id to property's gw_ids list
        gw_ids = prop.get("gw_ids", [])
        if gw_id not in gw_ids:
            gw_ids.append(gw_id)
            gw_ids.sort()
        prop["gw_ids"] = gw_ids

        # Add "gw" to sources
        sources = prop.get("sources", [])
        if "gw" not in sources:
            sources.append("gw")
            sources.sort()
        prop["sources"] = sources

        # Store gw_data snapshot
        prop["gw_data"] = _extract_gw_data(record)

        # Fill empty postal_code from GW
        parsed = parse_mpac_address(
            property_address=record.get("site_structure", {}).get("property_address", ""),
            municipality=record.get("site_structure", {}).get("municipality", ""),
            summary_address=record.get("summary", {}).get("address", ""),
        )
        if not prop.get("postal_code") and parsed["postal_code"]:
            prop["postal_code"] = parsed["postal_code"]
            postal_filled += 1

        prop["updated"] = today
        enriched += 1

    # Process unmatched — create new properties
    # Find next available P-ID
    used_ids = set(props.keys())
    max_num = 0
    for pid in used_ids:
        if pid.startswith("P") and pid[1:].isdigit():
            max_num = max(max_num, int(pid[1:]))

    for u in match_result["unmatched"]:
        gw_id = u["gw_id"]
        street = u["street"]
        city = u["city"]

        if not street:
            continue

        gw_path = gw_dir / f"{gw_id}.json"
        record = json.loads(gw_path.read_text(encoding="utf-8"))

        parsed = parse_mpac_address(
            property_address=record.get("site_structure", {}).get("property_address", ""),
            municipality=record.get("site_structure", {}).get("municipality", ""),
            summary_address=record.get("summary", {}).get("address", ""),
        )

        max_num += 1
        pid = f"P{max_num:05d}"
        used_ids.add(pid)

        props[pid] = {
            "address": street,
            "city": city,
            "municipality": "",
            "province": parsed["province"],
            "postal_code": parsed["postal_code"],
            "lat": None,
            "lng": None,
            "rt_ids": [],
            "transaction_count": 0,
            "gw_ids": [gw_id],
            "gw_data": _extract_gw_data(record),
            "sources": ["gw"],
            "created": today,
            "updated": today,
        }
        created += 1

    # Re-sort properties by ID
    registry["properties"] = dict(sorted(props.items()))

    return {"enriched": enriched, "created": created, "postal_filled": postal_filled}
