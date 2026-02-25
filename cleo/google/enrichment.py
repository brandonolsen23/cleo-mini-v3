"""Enrichment orchestrator — batch processing with priority queue.

Loads properties, prioritizes them (brand-matched > RT transactions > brand-only),
and runs enrichment phases: text-search, details (by tier), streetview.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from cleo.config import (
    GOOGLE_API_KEY,
    PROPERTIES_PATH,
    BRAND_MATCHES_PATH,
    STREETVIEW_DIR,
)
from cleo.google.budget import BudgetGuardian, BudgetExhausted
from cleo.google.client import GooglePlacesClient
from cleo.google.streetview import StreetViewClient
from cleo.google.store import PlacesStore, StreetViewMetaStore
from cleo.properties.registry import load_registry

logger = logging.getLogger(__name__)

SAVE_INTERVAL = 25  # save stores every N items processed


def _prioritized_prop_ids() -> list[str]:
    """Return property IDs in enrichment priority order.

    1. Brand-matched properties with RT transactions (~7,500)
    2. Other RT transaction properties (~4,900)
    3. Brand-only properties (~6,300)
    """
    reg = load_registry(PROPERTIES_PATH)
    props = reg.get("properties", {})

    # Load brand matches to identify brand-matched properties
    # brand_matches.json is a dict keyed by prop_id -> list of match entries
    brand_matched: set[str] = set()
    if BRAND_MATCHES_PATH.exists():
        matches = json.loads(BRAND_MATCHES_PATH.read_text(encoding="utf-8"))
        if isinstance(matches, dict):
            brand_matched = set(matches.keys())
        elif isinstance(matches, list):
            for entry in matches:
                pid = entry.get("prop_id")
                if pid:
                    brand_matched.add(pid)

    tier1 = []  # brand-matched + RT
    tier2 = []  # RT only
    tier3 = []  # brand only / other

    for pid, prop in props.items():
        sources = set(prop.get("sources", []))
        has_rt = "rt" in sources
        has_brand = pid in brand_matched

        if has_rt and has_brand:
            tier1.append(pid)
        elif has_rt:
            tier2.append(pid)
        else:
            tier3.append(pid)

    # Sort within each tier for deterministic ordering
    return sorted(tier1) + sorted(tier2) + sorted(tier3)


def _build_search_query(prop: dict) -> str:
    """Build a text search query from a property's address fields."""
    parts = [prop.get("address", "")]
    if prop.get("city"):
        parts.append(prop["city"])
    parts.append("ON")  # Ontario, Canada
    return ", ".join(p for p in parts if p)


def run_text_search(
    limit: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Phase 1: Text Search (IDs Only) — find place_ids for properties.

    Returns summary dict with counts.
    """
    budget = BudgetGuardian()
    store = PlacesStore()
    reg = load_registry(PROPERTIES_PATH)
    props = reg.get("properties", {})

    all_ids = _prioritized_prop_ids()
    pending = store.pending_text_search(all_ids)

    if limit is not None:
        pending = pending[:limit]

    logger.info("Text search: %d pending (of %d total)", len(pending), len(all_ids))

    if dry_run:
        return {
            "phase": "text_search",
            "dry_run": True,
            "total_properties": len(all_ids),
            "pending": len(pending),
            "would_process": len(pending),
        }

    client = GooglePlacesClient(GOOGLE_API_KEY, budget)
    processed = 0
    found = 0

    try:
        for pid in pending:
            prop = props.get(pid, {})
            query = _build_search_query(prop)
            if not query.strip(", "):
                continue

            try:
                place_id = client.text_search(query)
                if place_id:
                    store.set_place_id(pid, place_id, query)
                    found += 1
                processed += 1
            except BudgetExhausted:
                logger.warning("Budget exhausted at %d/%d", processed, len(pending))
                break
            except Exception as e:
                logger.error("Text search failed for %s (%s): %s", pid, query, e)
                processed += 1

            if processed % SAVE_INTERVAL == 0:
                store.save()
                logger.info("Progress: %d/%d processed, %d found", processed, len(pending), found)

            time.sleep(0.1)  # rate limiting
    finally:
        store.save()
        client.close()

    return {
        "phase": "text_search",
        "processed": processed,
        "found": found,
        "pending_remaining": len(pending) - processed,
    }


def run_details(
    tier: str,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Phase 2: Place Details — fetch details at a specific tier.

    Args:
        tier: "essentials", "pro", or "enterprise"
    """
    budget = BudgetGuardian()
    store = PlacesStore()

    all_ids = _prioritized_prop_ids()
    pending = store.pending_details(all_ids, tier)

    if limit is not None:
        pending = pending[:limit]

    logger.info("Details (%s): %d pending", tier, len(pending))

    if dry_run:
        return {
            "phase": "details",
            "tier": tier,
            "dry_run": True,
            "pending": len(pending),
            "would_process": len(pending),
        }

    client = GooglePlacesClient(GOOGLE_API_KEY, budget)
    processed = 0
    fetched = 0

    try:
        for pid in pending:
            place_id = store.place_id_for(pid)
            if not place_id:
                continue

            try:
                data = client.place_details(place_id, tier)
                if data:
                    store.set_details(pid, tier, data)
                    fetched += 1
                processed += 1
            except BudgetExhausted:
                logger.warning("Budget exhausted at %d/%d", processed, len(pending))
                break
            except Exception as e:
                logger.error("Details (%s) failed for %s: %s", tier, pid, e)
                processed += 1

            if processed % SAVE_INTERVAL == 0:
                store.save()
                logger.info("Progress: %d/%d processed, %d fetched", processed, len(pending), fetched)

            time.sleep(0.1)
    finally:
        store.save()
        client.close()

    return {
        "phase": "details",
        "tier": tier,
        "processed": processed,
        "fetched": fetched,
        "pending_remaining": len(pending) - processed,
    }


def run_streetview(
    limit: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Phase 3: Street View — check metadata (free) + fetch images (budget-gated).

    Two sub-steps:
    1. Metadata check for all properties with coordinates (free)
    2. Image fetch for properties with coverage (budget-gated)
    """
    budget = BudgetGuardian()
    sv_meta = StreetViewMetaStore()
    reg = load_registry(PROPERTIES_PATH)
    props = reg.get("properties", {})

    # Only properties with coordinates
    all_ids = _prioritized_prop_ids()
    with_coords = [
        pid for pid in all_ids
        if props.get(pid, {}).get("lat") is not None
        and props.get(pid, {}).get("lng") is not None
    ]

    # Step 1: metadata check (free)
    pending_meta = sv_meta.pending_metadata(with_coords)
    # Step 2: image fetch (gated)
    pending_images = sv_meta.pending_images(with_coords)

    if limit is not None:
        pending_meta = pending_meta[:limit]
        # Images limited separately after metadata is done
        pending_images = pending_images[:limit]

    logger.info(
        "Street View: %d pending metadata, %d pending images (of %d with coords)",
        len(pending_meta), len(pending_images), len(with_coords),
    )

    if dry_run:
        return {
            "phase": "streetview",
            "dry_run": True,
            "with_coordinates": len(with_coords),
            "pending_metadata": len(pending_meta),
            "pending_images": len(pending_images),
        }

    client = StreetViewClient(GOOGLE_API_KEY, budget)
    meta_checked = 0
    meta_with_coverage = 0
    images_fetched = 0

    try:
        # Step 1: Metadata checks (free)
        for pid in pending_meta:
            prop = props.get(pid, {})
            lat, lng = prop.get("lat"), prop.get("lng")
            if lat is None or lng is None:
                continue

            try:
                meta = client.check_metadata(lat, lng)
                sv_meta.set_metadata(pid, meta)
                meta_checked += 1
                if meta["has_coverage"]:
                    meta_with_coverage += 1
            except Exception as e:
                logger.error("Metadata check failed for %s: %s", pid, e)

            if meta_checked % SAVE_INTERVAL == 0:
                sv_meta.save()
                logger.info("Metadata: %d/%d checked, %d with coverage",
                            meta_checked, len(pending_meta), meta_with_coverage)

            time.sleep(0.05)  # light rate limiting for free calls

        sv_meta.save()

        # Step 2: Image fetches (budget-gated)
        # Recompute pending after metadata step added new entries
        pending_images = sv_meta.pending_images(with_coords)
        if limit is not None:
            pending_images = pending_images[:limit]

        for pid in pending_images:
            prop = props.get(pid, {})
            lat, lng = prop.get("lat"), prop.get("lng")
            if lat is None or lng is None:
                continue

            try:
                path = client.fetch_image(lat, lng, pid)
                if path:
                    sv_meta.set_image_fetched(pid)
                    images_fetched += 1
            except BudgetExhausted:
                logger.warning("Image budget exhausted at %d", images_fetched)
                break
            except Exception as e:
                logger.error("Image fetch failed for %s: %s", pid, e)

            if images_fetched % SAVE_INTERVAL == 0 and images_fetched > 0:
                sv_meta.save()
                logger.info("Images: %d fetched", images_fetched)

            time.sleep(0.1)
    finally:
        sv_meta.save()
        client.close()

    return {
        "phase": "streetview",
        "metadata_checked": meta_checked,
        "metadata_with_coverage": meta_with_coverage,
        "images_fetched": images_fetched,
    }


def enrichment_status() -> dict:
    """Return combined status of budget + enrichment progress."""
    budget = BudgetGuardian()
    places_store = PlacesStore()
    sv_store = StreetViewMetaStore()

    return {
        "budget": budget.status(),
        "places": places_store.enrichment_stats(),
        "streetview": sv_store.stats(),
    }
