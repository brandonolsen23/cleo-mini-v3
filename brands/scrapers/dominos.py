"""Scraper for Domino's Pizza via the Power store-locator API.

The API returns nearby stores for a given postal code and city. We query
a grid of ~30 Ontario cities to ensure full provincial coverage, then
dedup by StoreID.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from .base import StoreRecord, now_iso, write_brand_json

API_URL = "https://order.dominos.ca/power/store-locator"

# Seed cities covering all major Ontario regions
_SEED_CITIES: list[tuple[str, str]] = [
    ("Toronto, ON", "M5V 3L9"),
    ("Ottawa, ON", "K1A 0B1"),
    ("London, ON", "N6A 1B7"),
    ("Hamilton, ON", "L8P 1A1"),
    ("Sudbury, ON", "P3E 1A1"),
    ("Thunder Bay, ON", "P7B 1A1"),
    ("Windsor, ON", "N9A 1A1"),
    ("Barrie, ON", "L4M 1A1"),
    ("Kingston, ON", "K7L 1A1"),
    ("Kitchener, ON", "N2G 1A1"),
    ("Oshawa, ON", "L1H 1A1"),
    ("St Catharines, ON", "L2R 1A1"),
    ("Guelph, ON", "N1H 1A1"),
    ("Peterborough, ON", "K9H 1A1"),
    ("Brampton, ON", "L6V 1A1"),
    ("Markham, ON", "L3R 1A1"),
    ("North Bay, ON", "P1B 1A1"),
    ("Sault Ste Marie, ON", "P6A 1A1"),
    ("Sarnia, ON", "N7T 1A1"),
    ("Cornwall, ON", "K6H 1A1"),
    ("Belleville, ON", "K8P 1A1"),
    ("Chatham, ON", "N7L 1A1"),
    ("Brockville, ON", "K6V 1A1"),
    ("Timmins, ON", "P4N 1A1"),
    ("Kenora, ON", "P9N 1A1"),
    ("Orillia, ON", "L3V 1A1"),
    ("Orangeville, ON", "L9W 1A1"),
    ("Owen Sound, ON", "N4K 1A1"),
]


def _to_record(store: dict, ts: str) -> StoreRecord | None:
    addr = store.get("Address", {})
    street = (addr.get("Street") or "").strip()
    city = (addr.get("City") or "").strip()
    province = (addr.get("Region") or "").strip()
    postal_code = addr.get("PostalCode")

    if not street or not city:
        return None

    coords = store.get("StoreCoordinates", {})
    lat = coords.get("StoreLatitude")
    lng = coords.get("StoreLongitude")

    return StoreRecord(
        brand="Domino's",
        store_name=f"Domino's - {city}",
        address=street,
        city=city,
        province=province,
        postal_code=postal_code,
        phone=store.get("Phone"),
        lat=float(lat) if lat else None,
        lng=float(lng) if lng else None,
        source_url=f"https://order.dominos.ca/en/pages/order/#!/stores/{store.get('StoreID', '')}",
        scraped_at=ts,
    )


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Domino's Ontario locations via the Power API."""
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
        timeout=30,
    )
    ts = now_iso()

    all_stores: dict[str, dict] = {}
    try:
        for city, postal in _SEED_CITIES:
            resp = client.get(API_URL, params={
                "s": postal,
                "c": city,
                "type": "Delivery",
            })
            resp.raise_for_status()
            data = resp.json()
            for store in data.get("Stores", []):
                addr = store.get("Address", {})
                if addr.get("Region") == "ON" and store["StoreID"] not in all_stores:
                    all_stores[store["StoreID"]] = store
    finally:
        client.close()

    records: list[StoreRecord] = []
    for store in all_stores.values():
        rec = _to_record(store, ts)
        if rec:
            records.append(rec)

    coord_count = sum(1 for r in records if r.lat is not None)
    path = write_brand_json("dominos", records)
    print(f"  Domino's: {len(records)} Ontario stores ({coord_count}/{len(records)} have coordinates)")
    return records, path
