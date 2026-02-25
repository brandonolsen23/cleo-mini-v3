"""OSM tenant discovery enrichment orchestrator.

Queries Overpass API for commercial POIs near each property's coordinates.
Completely free — no API key, no quotas, no billing.
"""

from __future__ import annotations

import json
import logging
import time

from cleo.config import PROPERTIES_PATH, BRAND_MATCHES_PATH
from cleo.osm.client import OverpassClient
from cleo.osm.store import TenantStore
from cleo.properties.registry import load_registry

logger = logging.getLogger(__name__)

SAVE_INTERVAL = 25


def _prioritized_prop_ids() -> list[str]:
    """Return property IDs with coordinates, in priority order.

    1. Brand-matched properties with RT transactions
    2. Other RT transaction properties
    3. Brand-only / other properties
    """
    reg = load_registry(PROPERTIES_PATH)
    props = reg.get("properties", {})

    brand_matched: set[str] = set()
    if BRAND_MATCHES_PATH.exists():
        matches = json.loads(BRAND_MATCHES_PATH.read_text(encoding="utf-8"))
        if isinstance(matches, dict):
            brand_matched = set(matches.keys())

    tier1, tier2, tier3 = [], [], []

    for pid, prop in props.items():
        # Must have coordinates
        if prop.get("lat") is None or prop.get("lng") is None:
            continue

        sources = set(prop.get("sources", []))
        has_rt = "rt" in sources
        has_brand = pid in brand_matched

        if has_rt and has_brand:
            tier1.append(pid)
        elif has_rt:
            tier2.append(pid)
        else:
            tier3.append(pid)

    return sorted(tier1) + sorted(tier2) + sorted(tier3)


def run_tenant_discovery(
    limit: int | None = None,
    radius: int = 150,
    dry_run: bool = False,
) -> dict:
    """Query Overpass for tenants near each property.

    Args:
        limit: Max properties to process
        radius: Search radius in meters (default 150)
        dry_run: Report what would be done without making calls
    """
    store = TenantStore()
    reg = load_registry(PROPERTIES_PATH)
    props = reg.get("properties", {})

    all_ids = _prioritized_prop_ids()
    pending = store.pending(all_ids)

    if limit is not None:
        pending = pending[:limit]

    logger.info(
        "OSM tenant discovery: %d pending (of %d with coords)",
        len(pending), len(all_ids),
    )

    if dry_run:
        return {
            "dry_run": True,
            "total_with_coords": len(all_ids),
            "already_checked": len(all_ids) - len(store.pending(all_ids)),
            "pending": len(pending),
            "radius": radius,
        }

    client = OverpassClient()
    processed = 0
    total_tenants_found = 0

    try:
        for pid in pending:
            prop = props.get(pid, {})
            lat, lng = prop.get("lat"), prop.get("lng")
            if lat is None or lng is None:
                continue

            try:
                tenants = client.query_tenants(lat, lng, radius)
                store.set_tenants(pid, tenants, radius)
                total_tenants_found += len(tenants)
                processed += 1

                if tenants:
                    names = [t["name"] for t in tenants[:5]]
                    preview = ", ".join(names)
                    if len(tenants) > 5:
                        preview += f" (+{len(tenants) - 5} more)"
                    logger.info("%s: %d tenants — %s", pid, len(tenants), preview)
                else:
                    logger.info("%s: no tenants found", pid)

            except Exception as e:
                logger.error("Failed for %s: %s", pid, e)
                processed += 1

            if processed % SAVE_INTERVAL == 0:
                store.save()
                logger.info(
                    "Progress: %d/%d processed, %d tenants found",
                    processed, len(pending), total_tenants_found,
                )
    finally:
        store.save()
        client.close()

    return {
        "processed": processed,
        "total_tenants_found": total_tenants_found,
        "pending_remaining": len(pending) - processed,
        "radius": radius,
    }


def tenant_status() -> dict:
    """Return current tenant discovery stats."""
    store = TenantStore()
    all_ids = _prioritized_prop_ids()
    return {
        "total_with_coords": len(all_ids),
        "pending": len(store.pending(all_ids)),
        **store.stats(),
    }
