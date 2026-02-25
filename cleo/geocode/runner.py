"""Geocoding runner: multi-provider orchestrator using CoordinateStore.

Supports Mapbox, Geocodio, and HERE providers. Reads pending addresses
from the unified CoordinateStore and writes results back.

Also maintains backward-compatible geocode_cache.json for Mapbox/HERE results.
"""

import logging
import time
from pathlib import Path
from typing import Dict, Optional

from .cache import GeocodeCache
from .store import CoordinateStore

logger = logging.getLogger(__name__)


def run_geocode(
    provider: str,
    store: CoordinateStore,
    client,
    dry_run: bool = False,
    limit: Optional[int] = None,
    batch_size: int = 50,
    delay: float = 0.15,
    cache: Optional[GeocodeCache] = None,
) -> Dict:
    """Multi-provider geocoding orchestrator.

    Args:
        provider: One of "mapbox", "geocodio", "here".
        store: CoordinateStore instance (reads pending, writes results).
        client: Provider client (MapboxClient, GeocodioClient, or HereClient).
        dry_run: If True, report stats without calling API.
        limit: Max addresses to geocode.
        batch_size: Addresses per batch API call (Mapbox=50, Geocodio=10000).
        delay: Seconds between batch calls.
        cache: Optional GeocodeCache for backward compat (Mapbox/HERE writes).

    Returns:
        Summary dict with stats.
    """
    start = time.time()

    # Get pending addresses for this provider
    if provider == "geocodio":
        pending = store.pending_geocodio()
    elif provider == "here":
        pending = store.pending_here()
    else:
        pending = store.pending_mapbox()

    # Sort by address for deterministic order
    pending.sort()

    # Apply limit
    if limit is not None and len(pending) > limit:
        pending = pending[:limit]

    total_in_store = len(store.addresses)

    summary = {
        "provider": provider,
        "total_in_store": total_in_store,
        "pending_for_provider": len(pending),
        "to_geocode": len(pending),
        "geocoded": 0,
        "successes": 0,
        "failures": 0,
        "batch_requests": 0,
        "elapsed": 0.0,
    }

    if dry_run:
        summary["elapsed"] = time.time() - start
        return summary

    if not pending:
        logger.info("No pending addresses for %s.", provider)
        summary["elapsed"] = time.time() - start
        return summary

    if client is None:
        logger.error("No %s client available.", provider)
        summary["elapsed"] = time.time() - start
        return summary

    # Batch geocode
    total = len(pending)

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = pending[batch_start:batch_end]

        try:
            if provider == "geocodio":
                results = client.batch_forward(batch)
            else:
                results = client.batch_forward(batch, delay=delay)
            summary["batch_requests"] += 1

            # Write to coordinate store
            if provider == "geocodio":
                added = store.add_geocodio_batch(batch, results)
            elif provider == "here":
                added = store.add_here_batch(batch, results)
            else:
                added = store.add_mapbox_batch(batch, results)

            # Also write to legacy geocode_cache.json for Mapbox/HERE
            if cache is not None and provider in ("mapbox", "here"):
                items = list(zip(batch, results))
                cache.put_batch(items)

            for result in results:
                summary["geocoded"] += 1
                if result is not None:
                    summary["successes"] += 1
                else:
                    summary["failures"] += 1

        except Exception as e:
            logger.error(
                "Batch request failed at offset %d: %s", batch_start, e
            )
            summary["batch_requests"] += 1
            for _ in batch:
                summary["geocoded"] += 1
                summary["failures"] += 1

        # Save periodically (every 10 batches)
        if (summary["batch_requests"] % 10) == 0:
            store.save()
            if cache is not None and provider in ("mapbox", "here"):
                cache.save()
            logger.info(
                "Progress: %d / %d geocoded (%d successes, %d failures)",
                summary["geocoded"], total, summary["successes"], summary["failures"],
            )

    # Final save
    store.save()
    if cache is not None and provider in ("mapbox", "here"):
        cache.save()

    summary["elapsed"] = time.time() - start
    logger.info(
        "Done: %d geocoded (%d successes, %d failures) in %.1fs via %d batch requests [%s]",
        summary["geocoded"],
        summary["successes"],
        summary["failures"],
        summary["elapsed"],
        summary["batch_requests"],
        provider,
    )

    return summary


# --- Legacy runner for backward compatibility ---
# The old run_geocode signature is preserved as run_geocode_legacy so that
# any existing callers (tests, scripts) continue to work.

def run_geocode_legacy(
    extracted_dir: Path,
    reviews_path: Path,
    cache: GeocodeCache,
    client,
    dry_run: bool = False,
    limit: Optional[int] = None,
    retry_failures: bool = False,
    batch_size: int = 50,
    delay: float = 0.15,
) -> Dict:
    """Legacy geocoding orchestrator (Mapbox-only, cache-based).

    Kept for backward compatibility. New code should use run_geocode().
    """
    from .collector import collect_addresses

    start = time.time()
    address_refs, unique_addresses = collect_addresses(extracted_dir, reviews_path)

    cleared_failures = 0
    if retry_failures:
        cleared_failures = cache.clear_failures()

    uncached = cache.uncached_from(unique_addresses)
    if limit is not None and len(uncached) > limit:
        uncached = set(list(uncached)[:limit])

    summary = {
        "total_unique": len(unique_addresses),
        "total_references": sum(len(refs) for refs in address_refs.values()),
        "already_cached": len(unique_addresses) - len(uncached),
        "cleared_failures": cleared_failures,
        "to_geocode": len(uncached),
        "geocoded": 0,
        "successes": 0,
        "failures": 0,
        "batch_requests": 0,
        "elapsed": 0.0,
    }

    if dry_run:
        summary["elapsed"] = time.time() - start
        return summary

    if not uncached:
        summary["elapsed"] = time.time() - start
        return summary

    if client is None:
        summary["elapsed"] = time.time() - start
        return summary

    to_geocode = sorted(uncached)
    total = len(to_geocode)

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = to_geocode[batch_start:batch_end]

        try:
            results = client.batch_forward(batch, delay=delay)
            summary["batch_requests"] += 1
            items = list(zip(batch, results))
            cache.put_batch(items)

            for addr, result in items:
                summary["geocoded"] += 1
                if result is not None:
                    summary["successes"] += 1
                else:
                    summary["failures"] += 1

        except Exception as e:
            logger.error("Batch request failed at offset %d: %s", batch_start, e)
            for addr in batch:
                if cache.get(addr) is None:
                    cache.put_failure(addr, reason=str(e))
                    summary["geocoded"] += 1
                    summary["failures"] += 1
            summary["batch_requests"] += 1

        if (summary["batch_requests"] % 10) == 0:
            cache.save()

    cache.save()
    summary["elapsed"] = time.time() - start
    return summary
