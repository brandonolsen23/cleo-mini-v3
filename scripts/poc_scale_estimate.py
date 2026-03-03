"""Estimate scale: how many branded POIs per municipality in Ontario?

Runs a single Overpass query to fetch ALL branded POIs in Ontario,
groups them by approximate municipality (bounding box grid), and
estimates harvest time for ArcGIS parcel lookups.
"""

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "poc_parcel" / "osm_all_pois.json"

# Known municipality approximate bounding boxes (south, west, north, east)
# Just major ones for grouping — anything outside gets "other"
CITY_BOXES = {
    "London": (42.88, -81.38, 43.07, -81.12),
    "Barrie": (44.34, -79.76, 44.43, -79.62),
    "Brantford": (43.10, -80.32, 43.18, -80.22),
    "Hamilton": (43.20, -79.95, 43.30, -79.75),
    "Windsor": (42.27, -83.12, 42.35, -82.90),
    "Kingston": (44.20, -76.60, 44.28, -76.42),
    "Peterborough": (44.27, -78.38, 44.34, -78.28),
    "Sudbury": (46.44, -81.08, 46.54, -80.90),
    "Owen Sound": (44.55, -80.97, 44.60, -80.90),
    "Cambridge": (43.33, -80.38, 43.42, -80.28),
    "Waterloo": (43.43, -80.58, 43.50, -80.48),
    "Kitchener": (43.40, -80.55, 43.48, -80.42),
    "Oshawa": (43.85, -78.92, 43.92, -78.82),
    "Brampton": (43.67, -79.82, 43.78, -79.68),
    "Niagara Falls": (43.05, -79.12, 43.12, -79.02),
    "St. Catharines": (43.13, -79.28, 43.20, -79.18),
    "Guelph": (43.50, -80.32, 43.58, -80.20),
    "Cornwall": (45.00, -74.82, 45.05, -74.72),
    "North Bay": (46.28, -79.52, 46.35, -79.42),
    "Woodstock": (43.10, -80.80, 43.16, -80.72),
    "Orangeville": (43.89, -80.12, 43.94, -80.06),
    "St. Thomas": (42.76, -81.22, 42.80, -81.16),
    "Toronto": (43.60, -79.55, 43.85, -79.10),
    "Ottawa": (45.28, -75.82, 45.45, -75.55),
    "Mississauga": (43.52, -79.72, 43.62, -79.52),
    "Markham": (43.82, -79.40, 43.92, -79.22),
    "Vaughan": (43.78, -79.60, 43.88, -79.42),
    "Burlington": (43.30, -79.88, 43.40, -79.72),
    "Oakville": (43.40, -79.75, 43.48, -79.62),
    "Thunder Bay": (48.36, -89.32, 48.46, -89.18),
    "Sault Ste. Marie": (46.48, -84.38, 46.56, -84.28),
    "Belleville": (44.14, -77.42, 44.20, -77.32),
    "Sarnia": (42.95, -82.45, 43.02, -82.35),
    "Chatham": (42.38, -82.22, 42.44, -82.16),
}


def classify_city(lat: float, lng: float) -> str:
    """Classify a point into the nearest known municipality."""
    for city, (s, w, n, e) in CITY_BOXES.items():
        if s <= lat <= n and w <= lng <= e:
            return city
    return "other"


def main():
    print("Querying Overpass for ALL branded POIs in Ontario...")
    print("(This takes ~60-90 seconds)\n")

    # Use Overpass area filter for Ontario (relation 68841)
    query = """
[out:json][timeout:180];
area["name"="Ontario"]["admin_level"="4"]->.ontario;
(
  node["name"]["shop"](area.ontario);
  node["name"]["amenity"~"restaurant|fast_food|cafe|bar|bank|fuel|pharmacy"](area.ontario);
  node["brand"](area.ontario);
  way["name"]["shop"](area.ontario);
  way["name"]["amenity"~"restaurant|fast_food|cafe|bar|bank|fuel|pharmacy"](area.ontario);
  way["brand"](area.ontario);
);
out center tags;
"""

    start = time.time()
    resp = httpx.post(OVERPASS_URL, data={"data": query}, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    elapsed = time.time() - start

    elements = data.get("elements", [])
    print(f"Got {len(elements):,} POIs in {elapsed:.1f}s\n")

    # Process and classify
    pois = []
    city_counts = Counter()
    brand_counts = Counter()
    city_brands = defaultdict(set)

    for el in elements:
        tags = el.get("tags", {})
        if el["type"] == "node":
            lat, lng = el["lat"], el["lon"]
        elif "center" in el:
            lat, lng = el["center"]["lat"], el["center"]["lon"]
        else:
            continue

        name = tags.get("brand", tags.get("name", ""))
        city = classify_city(lat, lng)
        city_counts[city] += 1
        brand_counts[name] += 1
        city_brands[city].add(name)

        pois.append({
            "name": tags.get("name", ""),
            "brand": tags.get("brand", ""),
            "type": tags.get("shop") or tags.get("amenity") or "other",
            "lat": lat,
            "lng": lng,
            "osm_id": el["id"],
            "city": city,
        })

    # Save all POIs
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(pois, indent=2, ensure_ascii=False))
    print(f"Saved {len(pois):,} POIs to {OUTPUT_PATH}\n")

    # Report by city
    print("=" * 60)
    print(f"{'Municipality':<25s} {'POIs':>7s} {'Brands':>7s} {'ArcGIS est.':>12s}")
    print("-" * 60)
    for city, count in city_counts.most_common(40):
        # Estimate: ~0.5s per unique parcel query, assume ~60% of POIs share parcels
        unique_parcels = int(count * 0.6)
        est_time = unique_parcels * 0.5
        minutes = est_time / 60
        brand_count = len(city_brands[city])
        time_str = f"{minutes:.0f}m" if minutes < 60 else f"{minutes/60:.1f}h"
        has_service = "*" if city in ["London", "Barrie", "Brantford", "Woodstock", "Owen Sound"] else " "
        print(f"{has_service} {city:<24s} {count:>6,} {brand_count:>6,} {time_str:>11s}")

    print("-" * 60)
    print(f"  {'TOTAL':<24s} {len(pois):>6,}")
    print(f"\n  * = ArcGIS service already configured")

    # Report top brands
    print(f"\n{'Top 30 brands':}")
    print("-" * 40)
    for brand, count in brand_counts.most_common(30):
        if brand:
            print(f"  {brand:<30s} {count:>5,}")

    # Summary
    covered = sum(city_counts[c] for c in ["London", "Barrie", "Brantford", "Woodstock", "Owen Sound"] if c in city_counts)
    print(f"\nPOIs in covered municipalities: {covered:,}")
    print(f"POIs in uncovered municipalities: {len(pois) - covered:,}")

    # London deep dive
    london_pois = [p for p in pois if p["city"] == "London"]
    london_brands = sorted(set(p["brand"] or p["name"] for p in london_pois))
    print(f"\n=== LONDON DEEP DIVE ===")
    print(f"Total POIs: {len(london_pois)}")
    print(f"Unique brands: {len(london_brands)}")
    print(f"Estimated unique parcels: ~{int(len(london_pois) * 0.6)}")
    print(f"Estimated harvest time: ~{int(len(london_pois) * 0.6 * 0.5 / 60)}m")


if __name__ == "__main__":
    main()
