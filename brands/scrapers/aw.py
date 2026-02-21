"""A&W Canada scraper via public REST API.

339 Ontario locations. The A&W website exposes a JSON API at
web.aw.ca/api/locations with full store data including lat/lng.
"""

from __future__ import annotations

from pathlib import Path

from .base import StoreRecord, make_client, now_iso, write_brand_json

API_URL = "https://web.aw.ca/api/locations"


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all A&W stores in Ontario."""
    client = make_client()
    ts = now_iso()

    resp = client.get(API_URL)
    resp.raise_for_status()
    all_stores = resp.json()

    records: list[StoreRecord] = []
    for store in all_stores:
        if store.get("province_code") != "ON":
            continue

        lat = store.get("latitude")
        lng = store.get("longitude")
        if lat:
            lat = float(lat)
        if lng:
            lng = float(lng)

        name = store.get("restaurant_name", "").strip()

        records.append(
            StoreRecord(
                brand="A&W",
                store_name=f"A&W - {name}" if name else f"A&W - {store.get('city_name', '')}",
                address=store.get("address1", ""),
                city=store.get("city_name", ""),
                province="ON",
                postal_code=store.get("postal_code"),
                phone=store.get("phone_number"),
                lat=lat,
                lng=lng,
                source_url=f"https://web.aw.ca/en/locations/{store.get('slug', '')}",
                scraped_at=ts,
            )
        )

    path = write_brand_json("aw", records)
    return records, path
