"""Parcel registry builder — creates the master parcel-centric registry.

Builds data/parcel_registry.json by:
  Pass 1: Seed from branded_parcels/*.json (instant, no API)
  Pass 2: Resolve RT records to parcels via ARN/PIN/coords
  Pass 3: Resolve GW records to parcels via ARN/PIN
  Pass 4: Enrich with population from markets.json
  Pass 5: Assign stable P-IDs

Output: A single JSON file keyed by 20-digit ARN with all enrichment merged.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cleo.config import (
    BRANDED_PARCELS_DIR,
    COORDINATES_PATH,
    GW_PARSED_DIR,
    MARKETS_PATH,
    PARCEL_REGISTRY_PATH,
    PARSED_DIR,
    PROPERTIES_PATH,
)
from cleo.parcels.cache import ParcelCache, polygon_centroid
from cleo.parcels.resolver import ParcelResolver, normalize_pin, pad_arn_15_to_20

logger = logging.getLogger(__name__)


def _parse_price(price_str: str) -> Optional[int]:
    """Parse '$3,160,000' to 3160000."""
    if not price_str:
        return None
    try:
        return int(float(price_str.replace("$", "").replace(",", "").strip()))
    except (ValueError, TypeError):
        return None


def _load_markets() -> dict[str, int]:
    """Load markets.json and return uppercase city -> population."""
    if not MARKETS_PATH.exists():
        return {}
    data = json.loads(MARKETS_PATH.read_text(encoding="utf-8"))
    return {k.upper(): v["population"] for k, v in data.get("markets", {}).items()}


def _load_coordinate_store() -> dict[str, dict]:
    """Load coordinates.json for lat/lng lookups by address string."""
    if not COORDINATES_PATH.exists():
        return {}
    data = json.loads(COORDINATES_PATH.read_text(encoding="utf-8"))
    addresses = data.get("addresses", {})
    result = {}
    for addr, rec in addresses.items():
        best = rec.get("best")
        if best and best.get("lat") and best.get("lng"):
            result[addr] = {"lat": best["lat"], "lng": best["lng"]}
    return result


def _load_legacy_pid_map() -> dict[str, dict]:
    """Load existing properties.json to preserve P-ID assignments.
    Returns {dedup_key: {"pid": "P00001", "rt_ids": [...], "lat": ..., "lng": ...}}."""
    if not PROPERTIES_PATH.exists():
        return {}
    data = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
    props = data.get("properties", {})
    result = {}
    for pid, prop in props.items():
        addr = (prop.get("address", "") or "").upper().strip()
        city = (prop.get("city", "") or "").upper().strip()
        key = f"{addr}|{city}"
        result[key] = {
            "pid": pid,
            "rt_ids": prop.get("rt_ids", []),
            "lat": prop.get("lat"),
            "lng": prop.get("lng"),
        }
    return result


def _next_pid(used_pids: set[str]) -> str:
    """Generate next P-prefixed ID."""
    max_num = 0
    for pid in used_pids:
        if pid.startswith("P") and pid[1:].isdigit():
            max_num = max(max_num, int(pid[1:]))
    return f"P{max_num + 1:05d}"


def _make_empty_parcel(
    arn: str,
    pin: str | None = None,
    geometry: dict | None = None,
    centroid: list | None = None,
    city: str | None = None,
    discovered_via: str = "unknown",
) -> dict:
    """Create an empty parcel record template."""
    return {
        "arn": arn,
        "pid": None,
        "pin": pin,
        "geometry": geometry,
        "centroid": centroid,
        "city": city,
        "addresses": [],
        "area_sqm": None,
        "zoning": None,
        "population": None,
        "brands": [],
        "transactions": [],
        "assessment": None,
        "discovered_via": discovered_via,
        "sources": [],
    }


def build_registry(
    skip_api: bool = False,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Build the master parcel registry from all sources.

    Args:
        skip_api: If True, skip provincial API queries (cache-only mode).
        limit: Max RT records to process (for testing).
        dry_run: If True, don't save output files.

    Returns:
        Summary dict with stats.
    """
    start = time.time()

    # Initialize cache and resolver
    cache = ParcelCache()
    resolver = ParcelResolver(cache=cache, skip_api=skip_api)

    # Registry: arn_20 -> parcel dict
    registry: dict[str, dict] = {}

    # Reverse indexes
    pin_to_arn: dict[str, str] = {}
    rt_to_arn: dict[str, str] = {}
    pid_to_arn: dict[str, str] = {}

    # ----- Pass 1: Seed from branded parcels -----
    logger.info("Pass 1: Seeding from branded parcels...")
    branded_count = 0

    if BRANDED_PARCELS_DIR.exists():
        for f in sorted(BRANDED_PARCELS_DIR.iterdir()):
            if not f.name.endswith(".json"):
                continue
            try:
                file_data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            city_name = file_data.get("city", f.stem)

            for arn, parcel in file_data.get("parcels", {}).items():
                if arn not in registry:
                    geom = parcel.get("geometry")
                    centroid = polygon_centroid(geom) if geom else None

                    registry[arn] = _make_empty_parcel(
                        arn=arn,
                        pin=parcel.get("pin"),
                        geometry=geom,
                        centroid=centroid,
                        city=city_name.title(),
                        discovered_via="branded_harvest",
                    )
                    registry[arn]["sources"].append("branded")
                    registry[arn]["zoning"] = parcel.get("zoning")
                    branded_count += 1

                # Merge brands
                existing_brand_names = {b["name"] for b in registry[arn]["brands"]}
                for brand in parcel.get("brands", []):
                    if isinstance(brand, dict) and brand.get("name") not in existing_brand_names:
                        registry[arn]["brands"].append(brand)
                        existing_brand_names.add(brand["name"])

                # Merge addresses
                for addr in parcel.get("addresses", []):
                    if addr and addr not in registry[arn]["addresses"]:
                        registry[arn]["addresses"].append(addr)

                # Track PIN
                pin = parcel.get("pin")
                if pin:
                    pin_to_arn[normalize_pin(str(pin))] = arn

    # Also seed the resolver cache
    cache.seed_from_branded_parcels(BRANDED_PARCELS_DIR)

    logger.info("Pass 1 complete: %d branded parcels", branded_count)

    # ----- Pass 2: Resolve RT records -----
    logger.info("Pass 2: Resolving RT records...")
    rt_resolved = 0
    rt_unresolved = 0
    rt_total = 0

    # Pre-load coordinate store for spatial lookups
    coord_store = _load_coordinate_store() if not skip_api else {}

    parsed_active = PARSED_DIR / "active"
    if parsed_active.exists():
        rt_files = sorted(parsed_active.glob("*.json"))
        if limit:
            rt_files = rt_files[:limit]

        for f in rt_files:
            if f.stem == "_meta":
                continue
            rt_total += 1

            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            rt_id = data.get("rt_id", f.stem)
            txn = data.get("transaction", {})
            addr_obj = txn.get("address", {})
            site = data.get("site", {})

            # Get identifiers
            arn_15 = txn.get("arn", "")
            pins_raw = txn.get("pins", [])
            pins = [normalize_pin(str(p)) for p in pins_raw if p]

            # Also check site.pins (string, comma-separated or single)
            site_pins_str = site.get("pins", "")
            if site_pins_str:
                for sp in str(site_pins_str).split(","):
                    np = normalize_pin(sp)
                    if np and len(np) >= 9 and np not in pins:
                        pins.append(np)

            prop_address = addr_obj.get("address", "")
            prop_city = addr_obj.get("city", "")

            # Resolve parcel
            parcel = None

            # Method 1: ARN
            if arn_15 and len(arn_15) >= 15:
                parcel = resolver.resolve_by_arn(arn_15)

            # Method 2: PIN
            if not parcel:
                for pin in pins:
                    if len(pin) >= 9:
                        parcel = resolver.resolve_by_pin(pin)
                        if parcel:
                            break

            # Method 3: Spatial (only if we have coords and API is enabled)
            if not parcel and not skip_api and prop_address and prop_city:
                addr_str = f"{prop_address}, {prop_city}, Ontario"
                gc = coord_store.get(addr_str)
                if gc:
                    lat, lng = gc.get("lat"), gc.get("lng")
                    if lat and lng:
                        parcel = resolver.resolve_by_coords(float(lat), float(lng))

            if parcel:
                arn_20 = parcel["arn"]
                rt_resolved += 1
                rt_to_arn[rt_id] = arn_20

                # Ensure registry entry exists
                if arn_20 not in registry:
                    registry[arn_20] = _make_empty_parcel(
                        arn=arn_20,
                        pin=parcel.get("pin"),
                        geometry=parcel.get("geometry"),
                        centroid=parcel.get("centroid"),
                        city=prop_city or None,
                        discovered_via="rt_resolve",
                    )

                rec = registry[arn_20]
                if "rt" not in rec["sources"]:
                    rec["sources"].append("rt")

                # Merge address
                if prop_address and prop_address not in rec["addresses"]:
                    rec["addresses"].append(prop_address)
                for alt in addr_obj.get("alternate_addresses", []):
                    if alt and alt not in rec["addresses"]:
                        rec["addresses"].append(alt)

                # Merge city (prefer non-empty)
                if prop_city and not rec.get("city"):
                    rec["city"] = prop_city

                # Merge PIN
                for pin in pins:
                    if pin and not rec.get("pin"):
                        rec["pin"] = pin
                        pin_to_arn[pin] = arn_20

                # Add transaction summary
                price = _parse_price(txn.get("sale_price", ""))
                rec["transactions"].append({
                    "rt_id": rt_id,
                    "date": txn.get("sale_date_iso", ""),
                    "price": price,
                    "buyer": data.get("transferee", {}).get("name", ""),
                    "seller": data.get("transferor", {}).get("name", ""),
                })

                # Site area and zoning
                if site.get("site_area") and not rec.get("area_sqm"):
                    try:
                        acres = float(site["site_area"])
                        rec["area_sqm"] = round(acres * 4046.86, 1)
                    except (ValueError, TypeError):
                        pass
                if site.get("zoning") and not rec.get("zoning"):
                    rec["zoning"] = site["zoning"]
            else:
                rt_unresolved += 1

    logger.info("Pass 2 complete: %d/%d RT records resolved", rt_resolved, rt_total)

    # ----- Pass 3: Resolve GW records -----
    logger.info("Pass 3: Resolving GW records...")
    gw_resolved = 0
    gw_total = 0

    gw_dir = GW_PARSED_DIR / "v001"
    if gw_dir.exists():
        for f in sorted(gw_dir.glob("*.json")):
            if f.stem == "_meta":
                continue
            gw_total += 1

            try:
                gw_data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            gw_id = gw_data.get("gw_id", f.stem)
            site_struct = gw_data.get("site_structure", {})
            registry_info = gw_data.get("registry", {})
            summary = gw_data.get("summary", {})

            arn = site_struct.get("arn", "")
            pin = registry_info.get("pin", "") or gw_data.get("pin", "")

            parcel = None
            if arn and len(arn) >= 15:
                parcel = resolver.resolve_by_arn(arn)
            if not parcel and pin:
                parcel = resolver.resolve_by_pin(pin)

            if parcel:
                arn_20 = parcel["arn"]
                gw_resolved += 1

                if arn_20 not in registry:
                    registry[arn_20] = _make_empty_parcel(
                        arn=arn_20,
                        pin=parcel.get("pin"),
                        geometry=parcel.get("geometry"),
                        centroid=parcel.get("centroid"),
                        discovered_via="gw_resolve",
                    )

                rec = registry[arn_20]
                if "gw" not in rec["sources"]:
                    rec["sources"].append("gw")

                # Merge PIN
                if pin and not rec.get("pin"):
                    norm_pin = normalize_pin(pin)
                    rec["pin"] = norm_pin
                    pin_to_arn[norm_pin] = arn_20

                # Merge assessment data
                assessed_value = site_struct.get("current_assessed_value", "")
                if assessed_value:
                    rec["assessment"] = {
                        "value": _parse_price(assessed_value),
                        "property_code": site_struct.get("property_code", ""),
                        "property_description": site_struct.get("property_description", ""),
                        "legal_desc": site_struct.get("assessment_legal_description", ""),
                        "zoning": site_struct.get("zoning", ""),
                        "frontage": site_struct.get("frontage", ""),
                        "owner": summary.get("owner_names", ""),
                        "owner_address": site_struct.get("owner_mailing_address", ""),
                    }

                # Merge zoning
                if site_struct.get("zoning") and not rec.get("zoning"):
                    rec["zoning"] = site_struct["zoning"]

                # Merge address from GW (format: "121 CONCESSION ST E, TILLSONBURG, N4G4W4")
                gw_address = summary.get("address", "")
                if gw_address:
                    addr_parts = gw_address.split(",")
                    street = addr_parts[0].strip() if addr_parts else ""
                    city_part = addr_parts[1].strip() if len(addr_parts) > 1 else ""
                    if street and street not in rec["addresses"]:
                        rec["addresses"].append(street)
                    if city_part and not rec.get("city"):
                        rec["city"] = city_part.title()

                # Merge sales history (only if no RT transactions for this parcel)
                existing_rt_ids = {t["rt_id"] for t in rec["transactions"]}
                if not existing_rt_ids:
                    for sale in gw_data.get("sales_history", []):
                        price = _parse_price(sale.get("sale_amount", ""))
                        rec["transactions"].append({
                            "rt_id": f"GW:{gw_id}",
                            "date": sale.get("sale_date", ""),
                            "price": price,
                            "buyer": sale.get("party_to", "").rstrip(";").strip(),
                            "seller": "",
                        })

    logger.info("Pass 3 complete: %d/%d GW records resolved", gw_resolved, gw_total)

    # ----- Pass 4: Population enrichment -----
    logger.info("Pass 4: Enriching with population data...")
    markets = _load_markets()
    pop_enriched = 0

    for rec in registry.values():
        city = rec.get("city")
        if city:
            pop = markets.get(city.upper().strip())
            if pop:
                rec["population"] = pop
                pop_enriched += 1

    logger.info("Pass 4 complete: %d parcels with population data", pop_enriched)

    # ----- Pass 5: Assign stable P-IDs -----
    logger.info("Pass 5: Assigning P-IDs...")
    legacy = _load_legacy_pid_map()
    used_pids: set[str] = set()

    # First pass: assign P-IDs from legacy property registry
    for arn, rec in registry.items():
        for addr in rec.get("addresses", []):
            city = (rec.get("city") or "").upper().strip()
            key = f"{addr.upper().strip()}|{city}"
            if key in legacy:
                pid = legacy[key]["pid"]
                rec["pid"] = pid
                pid_to_arn[pid] = arn
                used_pids.add(pid)
                break

    # Second pass: assign new P-IDs to unassigned parcels
    for arn, rec in registry.items():
        if rec.get("pid") is None:
            pid = _next_pid(used_pids)
            rec["pid"] = pid
            pid_to_arn[pid] = arn
            used_pids.add(pid)

    # Sort transactions by date (descending) within each parcel
    for rec in registry.values():
        rec["transactions"].sort(
            key=lambda t: t.get("date", "") or "0000",
            reverse=True,
        )

    # ----- Build output -----
    elapsed = round(time.time() - start, 1)

    output = {
        "meta": {
            "total": len(registry),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_s": elapsed,
            "sources": {
                "branded": sum(1 for r in registry.values() if "branded" in r.get("sources", [])),
                "rt": sum(1 for r in registry.values() if "rt" in r.get("sources", [])),
                "gw": sum(1 for r in registry.values() if "gw" in r.get("sources", [])),
            },
            "stats": {
                "with_transactions": sum(1 for r in registry.values() if r.get("transactions")),
                "with_brands": sum(1 for r in registry.values() if r.get("brands")),
                "with_assessment": sum(1 for r in registry.values() if r.get("assessment")),
                "with_geometry": sum(1 for r in registry.values() if r.get("geometry")),
                "with_population": pop_enriched,
                "rt_resolved": rt_resolved,
                "rt_unresolved": rt_unresolved,
                "gw_resolved": gw_resolved,
            },
        },
        "parcels": registry,
        "indexes": {
            "pin_to_arn": pin_to_arn,
            "rt_to_arn": rt_to_arn,
            "pid_to_arn": pid_to_arn,
        },
    }

    if not dry_run:
        cache.save()
        PARCEL_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = PARCEL_REGISTRY_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fp:
            json.dump(output, fp, ensure_ascii=False)
        tmp.rename(PARCEL_REGISTRY_PATH)
        logger.info("Saved parcel registry: %d parcels to %s", len(registry), PARCEL_REGISTRY_PATH)

    return {
        "total_parcels": len(registry),
        "branded": branded_count,
        "rt_resolved": rt_resolved,
        "rt_unresolved": rt_unresolved,
        "gw_resolved": gw_resolved,
        "with_population": pop_enriched,
        "elapsed_s": elapsed,
        "resolver_stats": resolver.get_stats(),
        "dry_run": dry_run,
    }
