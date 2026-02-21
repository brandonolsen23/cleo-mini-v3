"""Scraper for Pizza Hut via the Yum! REST API.

Endpoint: GET https://api.pizzahut.io/v1/huts?longitude=X&latitude=Y&sector=ca-1
No auth required. Returns all Canadian stores in a single request.
Filter to Ontario by region == "ON".
"""

from __future__ import annotations

from pathlib import Path

import httpx

from .base import StoreRecord, now_iso, write_brand_json

# ── Constants ─────────────────────────────────────────────────────────

API_URL = "https://api.pizzahut.io/v1/huts"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept": "application/json",
}

# Center of Ontario — API returns all Canadian stores regardless of distance
PARAMS = {
    "latitude": 43.65,
    "longitude": -79.38,
    "sector": "ca-1",
}


# ── Public API ────────────────────────────────────────────────────────

def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Pizza Hut stores in Ontario."""
    ts = now_iso()
    records: list[StoreRecord] = []

    client = httpx.Client(headers=HEADERS, timeout=30)
    try:
        resp = client.get(API_URL, params=PARAMS)
        resp.raise_for_status()
        stores = resp.json()

        if not isinstance(stores, list):
            # Some API versions wrap in an object
            stores = stores.get("huts", stores.get("results", []))

        for s in stores:
            addr = s.get("address", {})
            region = (addr.get("region") or "").upper().strip()
            if region != "ON":
                continue

            # Address lines is an array: [street, city, province_code]
            lines = addr.get("lines", [])
            street = (lines[0] if lines else "").strip()
            city = (lines[1] if len(lines) > 1 else "").strip()

            if not street or not city:
                continue

            store_id = s.get("id") or s.get("storeId") or ""

            records.append(StoreRecord(
                brand="Pizza Hut",
                store_name=f"Pizza Hut - {city}",
                address=street,
                city=city,
                province="ON",
                postal_code=addr.get("postcode"),
                phone=s.get("phone"),
                lat=s.get("latitude"),
                lng=s.get("longitude"),
                source_url=f"https://www.pizzahut.ca/store/{store_id}",
                scraped_at=ts,
            ))
    finally:
        client.close()

    path = write_brand_json("pizza_hut", records)

    coord_count = sum(1 for r in records if r.lat is not None)
    print(f"  Pizza Hut: {len(records)} Ontario stores ({coord_count}/{len(records)} have coordinates)")

    return records, path
