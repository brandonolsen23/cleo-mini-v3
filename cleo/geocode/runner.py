"""Geocoding runner: collects addresses, checks cache, calls Mapbox API."""

import logging
import time
from pathlib import Path
from typing import Dict, Optional

from .cache import GeocodeCache
from .client import MapboxClient
from .collector import collect_addresses

logger = logging.getLogger(__name__)


def run_geocode(
    extracted_dir: Path,
    reviews_path: Path,
    cache: GeocodeCache,
    client: Optional[MapboxClient],
    dry_run: bool = False,
    limit: Optional[int] = None,
    retry_failures: bool = False,
    batch_size: int = 50,
    delay: float = 0.15,
) -> Dict:
    """Main geocoding orchestrator.

    Steps:
    1. Collect all unique geocodable addresses from extracted data
    2. Apply overrides from extract reviews
    3. Optionally clear failed entries (--retry-failures)
    4. Check which addresses are already cached
    5. If dry_run, report stats and return
    6. Call Mapbox batch API for uncached addresses
    7. Store results in cache
    8. Return summary stats
    """
    start = time.time()

    # Step 1-2: Collect addresses
    address_refs, unique_addresses = collect_addresses(extracted_dir, reviews_path)

    # Step 3: Retry failures
    cleared_failures = 0
    if retry_failures:
        cleared_failures = cache.clear_failures()

    # Step 4: Check cache
    uncached = cache.uncached_from(unique_addresses)

    # Apply limit
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

    # Step 5: Dry run
    if dry_run:
        summary["elapsed"] = time.time() - start
        return summary

    if not uncached:
        logger.info("All addresses already cached.")
        summary["elapsed"] = time.time() - start
        return summary

    if client is None:
        logger.error("No Mapbox client — cannot geocode. Set MAPBOX_TOKEN in .env.")
        summary["elapsed"] = time.time() - start
        return summary

    # Step 6: Batch geocode
    to_geocode = sorted(uncached)  # Deterministic order
    total = len(to_geocode)

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = to_geocode[batch_start:batch_end]

        try:
            results = client.batch_forward(batch, delay=delay)
            summary["batch_requests"] += 1

            # Store results
            items = list(zip(batch, results))
            cache.put_batch(items)

            for addr, result in items:
                summary["geocoded"] += 1
                if result is not None:
                    summary["successes"] += 1
                else:
                    summary["failures"] += 1

        except Exception as e:
            logger.error(
                "Batch request failed at offset %d: %s", batch_start, e
            )
            # Cache what we can — mark remaining as failed
            for addr in batch:
                if cache.get(addr) is None:
                    cache.put_failure(addr, reason=str(e))
                    summary["geocoded"] += 1
                    summary["failures"] += 1
            summary["batch_requests"] += 1

        # Save cache periodically (every 10 batches = 500 addresses)
        if (summary["batch_requests"] % 10) == 0:
            cache.save()
            logger.info(
                "Progress: %d / %d geocoded (%d successes, %d failures)",
                summary["geocoded"], total, summary["successes"], summary["failures"],
            )

    # Final save
    cache.save()

    summary["elapsed"] = time.time() - start
    logger.info(
        "Done: %d geocoded (%d successes, %d failures) in %.1fs via %d batch requests",
        summary["geocoded"],
        summary["successes"],
        summary["failures"],
        summary["elapsed"],
        summary["batch_requests"],
    )

    return summary
