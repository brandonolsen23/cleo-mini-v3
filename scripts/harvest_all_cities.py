"""Harvest branded parcels for ALL cities using the provincial parcel layer.

Runs through every city with a bounding box, fetches POIs from Overpass,
queries the provincial Assessment Parcel MapServer for parcel polygons,
and saves results. Automatically refreshes the AgMaps token when it expires.

Usage:
    .venv/bin/python scripts/harvest_all_cities.py
    .venv/bin/python scripts/harvest_all_cities.py --skip london  # skip already-done cities
    .venv/bin/python scripts/harvest_all_cities.py --only hamilton windsor kingston
    .venv/bin/python scripts/harvest_all_cities.py --dry-run  # just count POIs
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.harvest_city_parcels import (
    CITY_BBOX,
    OUTPUT_DIR,
    fetch_city_pois,
    harvest_parcels_provincial,
    save_results,
)
from cleo.parcels.provincial import ProvincialParcelClient, TokenExpiredError

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def refresh_token() -> str:
    """Get a fresh AgMaps token using Playwright."""
    logger.info("\n" + "=" * 60)
    logger.info("REFRESHING AGMAPS TOKEN...")
    logger.info("=" * 60)

    from scripts.fetch_agmaps_token import fetch_token, save_token_to_env

    token = fetch_token(headed=False)
    save_token_to_env(token)
    logger.info("Token refreshed: %s...%s (%d chars)",
                token[:15], token[-8:], len(token))
    return token


def get_completed_cities() -> set[str]:
    """Return set of cities that already have harvest files."""
    completed = set()
    if OUTPUT_DIR.exists():
        for f in OUTPUT_DIR.glob("*.json"):
            if f.stem != "summary":
                completed.add(f.stem)
    return completed


def main():
    parser = argparse.ArgumentParser(description="Harvest ALL cities using provincial parcels")
    parser.add_argument("--skip", nargs="*", default=[], help="Cities to skip")
    parser.add_argument("--only", nargs="*", default=[], help="Only harvest these cities")
    parser.add_argument("--dry-run", action="store_true", help="Just count POIs, don't query parcels")
    parser.add_argument("--resume", action="store_true", help="Skip cities that already have output files")
    parser.add_argument("--token", help="AgMaps token (will auto-fetch if not provided)")
    args = parser.parse_args()

    # Determine which cities to harvest
    if args.only:
        cities = [c.lower().replace(" ", "-") for c in args.only]
        missing = [c for c in cities if c not in CITY_BBOX]
        if missing:
            logger.error("Unknown cities: %s", ", ".join(missing))
            logger.info("Available: %s", ", ".join(sorted(CITY_BBOX.keys())))
            sys.exit(1)
    else:
        cities = sorted(CITY_BBOX.keys())

    skip = set(c.lower().replace(" ", "-") for c in args.skip)
    if args.resume:
        completed = get_completed_cities()
        skip |= completed
        if completed:
            logger.info("Resuming: skipping %d already-completed cities: %s",
                        len(completed), ", ".join(sorted(completed)))

    cities = [c for c in cities if c not in skip]

    if not cities:
        logger.info("No cities to harvest.")
        return

    logger.info("=" * 60)
    logger.info("PROVINCIAL PARCEL HARVEST: %d CITIES", len(cities))
    logger.info("=" * 60)
    logger.info("Cities: %s", ", ".join(cities))

    if args.dry_run:
        logger.info("\nDRY RUN — counting POIs only\n")
        total_pois = 0
        for city in cities:
            bbox = CITY_BBOX[city]
            try:
                pois = fetch_city_pois(city, bbox)
                total_pois += len(pois)
                logger.info("  %-20s %5d POIs", city, len(pois))
            except Exception as e:
                logger.warning("  %-20s FAILED: %s", city, e)
            time.sleep(2)  # be nice to Overpass
        logger.info("\nTotal: %d POIs across %d cities", total_pois, len(cities))
        return

    # Get or refresh token
    token = args.token
    if not token:
        from cleo.config import AGMAPS_TOKEN
        token = AGMAPS_TOKEN
    if not token:
        token = refresh_token()

    # Harvest loop
    grand_start = time.time()
    results_summary = {}
    failed_cities = []

    for i, city in enumerate(cities):
        bbox = CITY_BBOX[city]
        logger.info("\n" + "=" * 60)
        logger.info("[%d/%d] HARVESTING: %s", i + 1, len(cities), city.upper())
        logger.info("=" * 60)

        # Step 1: Fetch POIs
        try:
            pois = fetch_city_pois(city, bbox)
        except Exception as e:
            logger.error("Overpass failed for %s: %s", city, e)
            failed_cities.append((city, f"Overpass: {e}"))
            continue

        if not pois:
            logger.info("No POIs found for %s, skipping", city)
            results_summary[city] = {"pois": 0, "parcels": 0, "status": "no_pois"}
            continue

        # Step 2: Harvest parcels (with token refresh on expiry)
        city_start = time.time()
        attempt = 0
        harvest = None

        while attempt < 2:
            try:
                client = ProvincialParcelClient(token=token, throttle=0.4)
                client.test_connection()
                harvest = harvest_parcels_provincial(pois, client)
                client.close()
                break
            except TokenExpiredError:
                client.close()
                if attempt == 0:
                    logger.warning("Token expired. Refreshing...")
                    token = refresh_token()
                    attempt += 1
                else:
                    logger.error("Token expired again after refresh. Stopping.")
                    failed_cities.append((city, "Token expired"))
                    break
            except Exception as e:
                logger.error("Harvest failed for %s: %s", city, e)
                failed_cities.append((city, str(e)))
                try:
                    client.close()
                except Exception:
                    pass
                break

        if harvest is None:
            continue

        city_elapsed = time.time() - city_start
        stats = harvest["stats"]
        logger.info("  Completed in %.1f minutes", city_elapsed / 60)

        # Step 3: Save
        save_results(city, pois, harvest)

        results_summary[city] = {
            "pois": stats["total_pois"],
            "parcels": stats["unique_parcels"],
            "no_parcel": stats["no_parcel"],
            "brands": stats["total_brands"],
            "time_min": round(city_elapsed / 60, 1),
            "status": "ok",
        }

        # Brief pause between cities (be nice to Overpass)
        if i < len(cities) - 1:
            time.sleep(3)

    # Final summary
    grand_elapsed = time.time() - grand_start
    logger.info("\n\n" + "=" * 60)
    logger.info("HARVEST COMPLETE")
    logger.info("=" * 60)
    logger.info("Total time: %.1f minutes", grand_elapsed / 60)
    logger.info("")
    logger.info("%-20s %7s %8s %8s %8s", "City", "POIs", "Parcels", "Brands", "Time")
    logger.info("-" * 60)

    total_pois = 0
    total_parcels = 0
    total_brands = 0

    for city, info in sorted(results_summary.items()):
        status = info.get("status", "?")
        if status == "ok":
            logger.info("%-20s %7d %8d %8d %7.1fm",
                        city, info["pois"], info["parcels"], info["brands"], info["time_min"])
            total_pois += info["pois"]
            total_parcels += info["parcels"]
            total_brands += info["brands"]
        elif status == "no_pois":
            logger.info("%-20s %7s", city, "no POIs")

    logger.info("-" * 60)
    logger.info("%-20s %7d %8d %8d %7.1fm",
                "TOTAL", total_pois, total_parcels, total_brands, grand_elapsed / 60)

    if failed_cities:
        logger.info("\nFailed cities:")
        for city, reason in failed_cities:
            logger.info("  %s: %s", city, reason)

    # Save summary
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps({
        "harvested_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_time_min": round(grand_elapsed / 60, 1),
        "cities": results_summary,
        "failed": {c: r for c, r in failed_cities},
    }, indent=2))
    logger.info("\nSummary saved to %s", summary_path)


if __name__ == "__main__":
    main()
