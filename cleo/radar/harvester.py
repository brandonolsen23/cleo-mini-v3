"""Radar Places API harvester — fetch branded POIs across Ontario by chain.

Uses Radar's /v1/search/places endpoint to pull POI locations for each
master brand across major Ontario city centres. Outputs records in the
same schema as OSM POIs so they can enter the pipeline at the parcelled stage.

Strategy:
  - Map 137 master CSV brands to Radar chain slugs
  - For each chain, search near ~40 Ontario city centres (radius=10km, limit=100)
  - Deduplicate by Radar place coordinates (same chain at same location)
  - Assign stable RADAR_XXXXX IDs
  - Write versioned output to data/radar_pois/
"""

from __future__ import annotations

import csv
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from cleo.config import MASTER_BRANDS_CSV, RADAR_API_KEY, DATA_DIR

logger = logging.getLogger(__name__)

PLACES_URL = "https://api.radar.io/v1/search/places"

# Major Ontario city centres (lat, lng) — covers all populated areas within 10km radius.
# Core markets plus major population centres for comprehensive coverage.
ONTARIO_CITIES: list[tuple[str, float, float]] = [
    # User's core markets
    ("London", 42.9849, -81.2453),
    ("Barrie", 44.3894, -79.6903),
    ("Windsor", 42.3149, -83.0364),
    ("Kingston", 44.2312, -76.4860),
    ("Peterborough", 44.3091, -78.3197),
    ("Sudbury", 46.4917, -80.9930),
    ("Owen Sound", 44.5671, -80.9406),
    ("Orangeville", 43.9200, -80.0943),
    ("Cambridge", 43.3616, -80.3144),
    ("Waterloo", 43.4643, -80.5204),
    ("Oshawa", 43.8971, -78.8658),
    ("Brampton", 43.7315, -79.7624),
    ("Hamilton", 43.2557, -79.8711),
    ("St. Catharines", 43.1594, -79.2469),
    ("Brantford", 43.1394, -80.2644),
    ("Bradford", 44.1145, -79.5633),
    ("St. Thomas", 42.7740, -81.1832),
    ("Woodstock", 43.1306, -80.7467),
    ("Cornwall", 45.0218, -74.7302),
    ("Brighton", 44.1152, -77.7575),
    ("North Bay", 46.3091, -79.4608),
    ("Kingsville", 42.0388, -82.7382),
    # Additional major centres
    ("Toronto Downtown", 43.6532, -79.3832),
    ("Toronto North", 43.7615, -79.4111),
    ("Toronto East", 43.7001, -79.2577),
    ("Scarborough", 43.7731, -79.2578),
    ("Etobicoke", 43.6205, -79.5132),
    ("Mississauga", 43.5890, -79.6441),
    ("Vaughan", 43.8361, -79.4983),
    ("Markham", 43.8561, -79.3370),
    ("Richmond Hill", 43.8828, -79.4403),
    ("Newmarket", 44.0592, -79.4613),
    ("Oakville", 43.4675, -79.6877),
    ("Burlington", 43.3255, -79.7990),
    ("Guelph", 43.5448, -80.2482),
    ("Kitchener", 43.4516, -80.4925),
    ("Niagara Falls", 43.0896, -79.0849),
    ("Thunder Bay", 48.3809, -89.2477),
    ("Sault Ste. Marie", 46.5136, -84.3358),
    ("Belleville", 44.1628, -77.3832),
    ("Sarnia", 42.9745, -82.4066),
    ("Chatham", 42.4048, -82.1910),
    ("Stratford", 43.3700, -80.9822),
    ("Orillia", 44.6082, -79.4197),
    ("Cobourg", 43.9593, -78.1677),
    ("Lindsay", 44.3521, -78.7382),
    ("Huntsville", 45.3293, -79.2169),
    ("Timmins", 48.4758, -81.3305),
    ("Ottawa", 45.4215, -75.6972),
]

# Mapping: CSV brand name → Radar chain slug.
# Built by matching CSV names to Radar's chain list.
# Brands with no known Radar slug are omitted (they won't be fetched).
BRAND_TO_SLUG: dict[str, str] = {
    # Grocery (verified slugs)
    "Loblaws": "loblaws",
    "NoFrills": "nofrills",
    "Shoppers Drug Mart": "shoppers-drug-mart",
    "Sobeys": "sobeys",
    "Longos": "longos",
    "Farm Boy": "farm-boy",
    "Food Basics": "food-basics",
    # Big-Box Retail
    "Walmart": "walmart",
    "Canadian Tire": "canadian-tire",
    "Rona": "rona",
    "Home Hardware": "home-hardware",
    "Home Depot": "home-depot",
    "Costco": "costco",
    # Discount Retail
    "Dollarama": "dollarama",
    "Dollar Tree": "dollar-tree",
    "Winners": "winners",
    # Specialty Retail
    "Best Buy": "best-buy",
    "Staples": "staples",
    "Indigo / Chapters": "indigo",
    "Pet Smart": "petsmart",
    "Pet Valu": "pet-valu",
    "Mark's": "marks",
    "Mastermind Toys": "mastermind-toys",
    # QSR (keys must match CSV "Brand Name" exactly)
    "McDonalds": "mcdonalds",
    "Tim Hortons": "tim-hortons",
    "Subway": "subway",
    "Burger King": "burger-king",
    "Wendy's": "wendys",
    "A&W": "a-and-w-canada",
    "Popeyes Louisiana Kitchen": "popeyes",
    "KFC": "kfc",
    "Taco Bell": "taco-bell",
    "Pizza Pizza": "pizza-pizza",
    "Dominos Pizza": "dominos",
    "Pizza Hut": "pizza-hut",
    "Little Caesars": "little-caesars",
    "Five Guys": "five-guys",
    "Chipotle Mexican Grill": "chipotle",
    "Chick-fil-A": "chick-fil-a",
    "Pita Pit": "pita-pit",
    "Papa John's": "papa-johns",
    "Pizza Nova": "pizza-nova",
    "Firehouse Subs": "firehouse-subs",
    # Take-out / Cafe
    "Starbucks": "starbucks",
    "Second Cup": "second-cup",
    "Booster Juice": "booster-juice",
    "Baskin Robbins": "baskin-robbins",
    "Dairy Queen": "dairy-queen",
    # Full-Service
    "Swiss Chalet": "swiss-chalet",
    "Boston Pizza": "boston-pizza",
    "Harvey's": "harveys",
    "Denny's": "dennys",
    "Red Lobster": "red-lobster",
    "Freshii": "freshii",
    "Panera Bread": "panera-bread",
    # Automotive / Fuel
    "Petro Can": "petro-canada",
    "Shell": "shell",
    "Esso": "esso",
    "Mr. Lube": "mr-lube",
    # Specialty Retail (continued)
    "LCBO": "lcbo",
    "Rexall": "rexall",
    "Bulk Barn": "bulkbarn",
    "Marble Slab Creamery": "marble-slab-creamery",
}


def _normalize_key(lat: float, lng: float) -> str:
    """Round coords to 5 decimal places (~1m) for dedup."""
    return f"{lat:.5f},{lng:.5f}"


def load_master_brands() -> dict[str, str]:
    """Load master brands from CSV. Returns {brand_name: category}."""
    if not MASTER_BRANDS_CSV.exists():
        logger.warning("Master brands CSV not found: %s", MASTER_BRANDS_CSV)
        return {}
    result = {}
    with open(MASTER_BRANDS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("Brand Name", "").strip()
            cat = row.get("Category", "").strip()
            if name and cat:
                result[name] = cat
    return result


def fetch_chain_near(
    client: httpx.Client,
    chain_slug: str,
    lat: float,
    lng: float,
    radius: int = 10000,
    limit: int = 100,
) -> list[dict]:
    """Fetch POIs for a chain near a point. Returns raw Radar place dicts.

    Retries once on 429 with a 2-second backoff.
    """
    for attempt in range(2):
        resp = client.get(
            PLACES_URL,
            params={
                "chains": chain_slug,
                "near": f"{lat},{lng}",
                "radius": radius,
                "limit": limit,
            },
        )
        if resp.status_code == 429:
            if attempt == 0:
                time.sleep(2.0)
                continue
            logger.warning("Radar 429 (after retry) for %s near %.4f,%.4f", chain_slug, lat, lng)
            return []
        if resp.status_code != 200:
            logger.warning("Radar %d for %s near %.4f,%.4f", resp.status_code, chain_slug, lat, lng)
            return []
        data = resp.json()
        return data.get("places", [])
    return []


def harvest_all(
    dry_run: bool = False,
    limit_chains: int | None = None,
) -> dict:
    """Fetch all master brand POIs across Ontario via Radar Places API.

    Returns summary dict with stats.
    """
    if not RADAR_API_KEY:
        return {"error": "RADAR_API_KEY not set in .env"}

    master = load_master_brands()
    if not master:
        return {"error": "No master brands loaded"}

    # Build work list: only brands we have a slug for
    work: list[tuple[str, str, str]] = []  # (brand_name, category, slug)
    unmapped = []
    for brand_name, category in master.items():
        slug = BRAND_TO_SLUG.get(brand_name)
        if slug:
            work.append((brand_name, category, slug))
        else:
            unmapped.append(brand_name)

    logger.info(
        "Radar harvest: %d brands mapped to slugs, %d unmapped",
        len(work), len(unmapped),
    )
    if unmapped:
        logger.info("Unmapped brands: %s", ", ".join(sorted(unmapped)))

    if limit_chains:
        work = work[:limit_chains]

    if dry_run:
        return {
            "dry_run": True,
            "mapped_brands": len(work),
            "unmapped_brands": len(unmapped),
            "unmapped": sorted(unmapped),
            "cities": len(ONTARIO_CITIES),
            "estimated_requests": len(work) * len(ONTARIO_CITIES),
        }

    client = httpx.Client(
        timeout=30.0,
        headers={"Authorization": RADAR_API_KEY},
    )

    # Collect all POIs, dedup by (chain_slug, rounded coords)
    seen: set[str] = set()  # "slug|lat,lng"
    all_pois: list[dict] = []
    total_requests = 0
    total_raw = 0

    try:
        for brand_name, category, slug in work:
            brand_count = 0
            for city_name, city_lat, city_lng in ONTARIO_CITIES:
                places = fetch_chain_near(client, slug, city_lat, city_lng)
                total_requests += 1
                total_raw += len(places)

                for place in places:
                    loc = place.get("location", {})
                    coords = loc.get("coordinates", [])
                    if len(coords) < 2:
                        continue
                    lng, lat = coords[0], coords[1]
                    dedup_key = f"{slug}|{_normalize_key(lat, lng)}"
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)

                    poi = {
                        "source": "radar",
                        "radar_name": place.get("name", brand_name),
                        "brand": brand_name,
                        "tracked_brand": brand_name,
                        "category": category,
                        "chain_slug": slug,
                        "coords": {
                            "lat": lat,
                            "lng": lng,
                            "provider": "radar",
                        },
                        "address": {
                            "housenumber": "",
                            "street": "",
                            "city": "",
                            "postal_code": "",
                        },
                        "categories": place.get("categories", []),
                    }
                    all_pois.append(poi)
                    brand_count += 1

                # Free tier rate limit — stay under 10 req/sec
                time.sleep(0.12)

            logger.info("  %s (%s): %d unique locations", brand_name, slug, brand_count)

            # Progress every 10 brands
            brand_idx = work.index((brand_name, category, slug)) + 1
            if brand_idx % 10 == 0:
                logger.info(
                    "Progress: %d/%d brands, %d requests, %d unique POIs",
                    brand_idx, len(work), total_requests, len(all_pois),
                )
    finally:
        client.close()

    # Sort by brand then coords for deterministic ID assignment
    all_pois.sort(key=lambda p: (p["brand"], p["coords"]["lat"], p["coords"]["lng"]))

    # Assign RADAR_XXXXX IDs
    for i, poi in enumerate(all_pois, start=1):
        poi["id"] = f"RADAR_{i:05d}"

    logger.info(
        "Harvest complete: %d API requests, %d raw results, %d unique POIs",
        total_requests, total_raw, len(all_pois),
    )

    # Brand breakdown
    brand_counts: dict[str, int] = {}
    for poi in all_pois:
        b = poi["tracked_brand"]
        brand_counts[b] = brand_counts.get(b, 0) + 1

    return {
        "total_requests": total_requests,
        "total_raw_results": total_raw,
        "unique_pois": len(all_pois),
        "brands_with_results": len(brand_counts),
        "mapped_brands": len(work),
        "unmapped_brands": len(unmapped),
        "unmapped": sorted(unmapped),
        "pois": all_pois,
        "brand_counts": dict(sorted(brand_counts.items(), key=lambda x: -x[1])),
    }


def write_snapshot(pois: list[dict], output_dir: Path) -> int:
    """Write POI records to a directory (one JSON per POI). Returns count."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for poi in pois:
        path = output_dir / f"{poi['id']}.json"
        path.write_text(json.dumps(poi, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(pois)
