"""Scraper for Ultramar and Pioneer via Parkland/Journie API.

Single unauthenticated API call returns all ~2,780 Parkland stations.
Filter client-side by province and fuel brand.

Source: https://ceep.parkland.ca/locations/v1/summary?pageSize=3000
"""

from __future__ import annotations

from pathlib import Path

from .base import StoreRecord, make_client, now_iso, write_brand_json

API_URL = "https://ceep.parkland.ca/locations/v1/summary"

BRANDS: dict[str, tuple[str, str]] = {
    "pioneer": ("pioneer", "Pioneer"),
    "ultramar": ("ultramar", "Ultramar"),
}


def _fetch_all(client) -> list[dict]:
    """Fetch all Parkland locations in a single call."""
    resp = client.get(API_URL, params={"pageSize": "3000"})
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


def _get_fuel_brand(location: dict) -> str | None:
    """Extract the fuel brand from the services array (Forecourt type)."""
    for svc in location.get("services", []):
        if svc.get("serviceType") == "Forecourt":
            return svc.get("serviceBrand")
    return None


def _to_record(loc: dict, brand_name: str, ts: str, source_url: str) -> StoreRecord:
    coords = loc.get("coordinates", {})
    lat = coords.get("latitude")
    lng = coords.get("longitude")

    return StoreRecord(
        brand=brand_name,
        store_name=f"{brand_name} - {loc.get('siteCity', '')}",
        address=loc.get("siteAddressLine1", ""),
        city=loc.get("siteCity", ""),
        province=loc.get("siteStateProvince", "ON"),
        postal_code=loc.get("sitePostalCode"),
        phone=None,
        lat=float(lat) if lat else None,
        lng=float(lng) if lng else None,
        source_url=source_url,
        scraped_at=ts,
    )


def scrape_brand(slug: str) -> tuple[list[StoreRecord], Path]:
    """Scrape a single brand from the Parkland API."""
    out_slug, brand_name = BRANDS[slug]
    client = make_client()
    ts = now_iso()

    all_locations = _fetch_all(client)
    records: list[StoreRecord] = []

    for loc in all_locations:
        if loc.get("siteStateProvince") != "ON":
            continue
        fuel_brand = _get_fuel_brand(loc)
        if fuel_brand != brand_name:
            continue

        records.append(
            _to_record(loc, brand_name, ts, f"https://journie.ca/{slug}/on-en/locations")
        )

    path = write_brand_json(out_slug, records)
    return records, path


def scrape_all() -> list[tuple[str, int, Path]]:
    """Scrape both Pioneer and Ultramar in a single API call."""
    client = make_client()
    ts = now_iso()
    all_locations = _fetch_all(client)

    by_brand: dict[str, list[StoreRecord]] = {slug: [] for slug in BRANDS}

    for loc in all_locations:
        if loc.get("siteStateProvince") != "ON":
            continue
        fuel_brand = _get_fuel_brand(loc)
        for slug, (_, brand_name) in BRANDS.items():
            if fuel_brand == brand_name:
                by_brand[slug].append(
                    _to_record(loc, brand_name, ts, f"https://journie.ca/{slug}/on-en/locations")
                )

    results = []
    for slug, records in by_brand.items():
        out_slug = BRANDS[slug][0]
        path = write_brand_json(out_slug, records)
        results.append((out_slug, len(records), path))

    return results


# Individual brand functions for run.py registration
def scrape_pioneer() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("pioneer")


def scrape_ultramar() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("ultramar")
