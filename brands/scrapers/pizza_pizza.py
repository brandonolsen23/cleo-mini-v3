"""Scraper for Pizza Pizza via their Angular SPA backend API.

Uses two endpoints:
  1. /ajax/store/api/v1/province_cities — get all Ontario cities
  2. /ajax/store/api/v1/search/store_locator?province=ON&city=X — 10 stores per city

Requires session-token header (any UUID).
~379 stores in Ontario.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import httpx

from .base import StoreRecord, now_iso, write_brand_json

# ── Constants ─────────────────────────────────────────────────────────

API_BASE = "https://www.pizzapizza.ca/ajax/store/api/v1"


def _make_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json",
        "session-token": str(uuid.uuid4()),
        "lang": "en",
        "x-request-id": str(uuid.uuid4()),
    }


# ── Public API ────────────────────────────────────────────────────────

def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Pizza Pizza stores in Ontario."""
    ts = now_iso()
    seen_ids: set[int] = set()
    records: list[StoreRecord] = []

    client = httpx.Client(headers=_make_headers(), timeout=30)
    try:
        # Step 1: Get all Ontario cities
        resp = client.get(f"{API_BASE}/province_cities")
        resp.raise_for_status()
        provinces = resp.json()

        on_cities: list[str] = []
        for prov in provinces:
            if prov.get("province_slug") == "ON" or prov.get("province") == "ON":
                on_cities = [c["city_slug"] for c in prov.get("cities", [])]
                break

        if not on_cities:
            # Fallback: look through all provinces for ON
            for prov in provinces:
                cities = prov.get("cities", [])
                if cities and any("Toronto" in c.get("city", "") for c in cities):
                    on_cities = [c["city_slug"] for c in cities]
                    break

        # Step 2: Query store_locator for each city
        for city_slug in on_cities:
            try:
                resp = client.get(
                    f"{API_BASE}/search/store_locator",
                    params={"province": "ON", "city": city_slug},
                )
                if resp.status_code != 200:
                    continue

                data = resp.json()
                stores = data.get("stores", [])

                for s in stores:
                    store_id = s.get("store_id")
                    if not store_id or store_id in seen_ids:
                        continue
                    seen_ids.add(store_id)

                    address = (s.get("address") or s.get("name") or "").strip()
                    city = (s.get("city") or "").strip()
                    if not address or not city:
                        continue

                    records.append(StoreRecord(
                        brand="Pizza Pizza",
                        store_name=f"Pizza Pizza - {city}",
                        address=address,
                        city=city,
                        province="ON",
                        postal_code=s.get("postal_code"),
                        phone=s.get("market_phone_number"),
                        lat=s.get("latitude"),
                        lng=s.get("longitude"),
                        source_url=f"https://www.pizzapizza.ca/store/store-{store_id}",
                        scraped_at=ts,
                    ))

                time.sleep(0.1)  # be polite
            except (httpx.HTTPError, ValueError):
                continue

        # Step 3: Fill gaps via store_details enumeration for missed stores
        # The store_locator returns max 10 per city, so big cities miss stores.
        # Enumerate IDs to catch the rest.
        for store_id in range(1, 800):
            if store_id in seen_ids:
                continue
            try:
                resp = client.get(
                    f"{API_BASE}/store_details/",
                    params={"store_id": store_id},
                )
                if resp.status_code != 200:
                    continue

                data = resp.json()
                if not data or not isinstance(data, dict):
                    continue

                province = (data.get("province") or "").upper()
                if province != "ON":
                    continue

                seen_ids.add(store_id)
                address = (data.get("address") or "").strip()
                city = (data.get("city") or "").strip()
                if not address or not city:
                    continue

                records.append(StoreRecord(
                    brand="Pizza Pizza",
                    store_name=f"Pizza Pizza - {city}",
                    address=address,
                    city=city,
                    province="ON",
                    postal_code=data.get("postal_code"),
                    phone=data.get("market_phone_number"),
                    lat=data.get("lat"),
                    lng=data.get("lng"),
                    source_url=f"https://www.pizzapizza.ca/store/store-{store_id}",
                    scraped_at=ts,
                ))
            except (httpx.HTTPError, ValueError):
                continue
    finally:
        client.close()

    path = write_brand_json("pizza_pizza", records)

    coord_count = sum(1 for r in records if r.lat is not None)
    print(f"  Pizza Pizza: {len(records)} Ontario stores ({coord_count}/{len(records)} have coordinates)")

    return records, path
